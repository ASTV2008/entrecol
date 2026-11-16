"""TRANSFORMAR: valida y limpia un registro de Books.json.

Lo que se resuelve aquí (ver el MER, etapa 3):
    - 'authors' viene como un solo texto 'Autor1/Autor2': se parte en una lista ORDENADA.
    - Los 4 registros DESPLAZADOS (ver _reparar_desplazamiento).
    - Valores como texto ("4.57", "652") se convierten a su tipo real.
    - Fechas 'M/D/AAAA' inexistentes (31 de noviembre) se cargan sin fecha, con un aviso.

Lo que NO se hace: inventar datos. Un ISBN raro o una calificación de 0 se cargan
tal cual vienen; las reglas de negocio (p. ej. ignorar libros sin calificaciones en
un ranking) se aplican en los reportes, no aquí.
"""
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.etl.common import Rechazo
from app.etl.libros.extractor import RegistroCrudo

# Límites: deben coincidir con database/init/02_entretenimiento.sql
LARGO_MAX_TITULO = 300
LARGO_MAX_ISBN = 13
LARGO_MAX_IDIOMA = 15
LARGO_MAX_EDITORIAL = 120
LARGO_MAX_AUTOR = 120
ID_MAX = 4_294_967_295        # INT UNSIGNED
PAGINAS_MAX = 65_535          # SMALLINT UNSIGNED
CONTADOR_MAX = 4_294_967_295  # INT UNSIGNED

COLUMNAS_ESPERADAS = (
    "bookID", "title", "authors", "average_rating", "isbn", "isbn13",
    "language_code", "num_pages", "ratings_count", "text_reviews_count",
    "publication_date", "publisher",
)
CLAVE_EXTRA = "FIELD13"

_PATRON_ENTERO = re.compile(r"\d+", re.ASCII)
_PATRON_DECIMAL = re.compile(r"\d+(\.\d+)?", re.ASCII)
_PATRON_FECHA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})", re.ASCII)


@dataclass(frozen=True)
class LibroLimpio:
    """Un libro ya validado, listo para cargarse."""

    id_libro: int
    titulo: str
    isbn: str
    isbn13: str
    num_paginas: int
    fecha_publicacion: date | None
    calificacion_promedio: Decimal
    num_calificaciones: int
    num_resenas: int
    editorial: str
    idioma: str
    autores: tuple[str, ...]   # en orden de aparición, sin repetidos; puede estar vacía


class _Invalido(Exception):
    """Un valor no cumple las reglas. Se convierte en un Rechazo de la fila."""


# ------------------------------------------------------------------ reparación
def _reparar_desplazamiento(d: dict) -> dict:
    """Repara un registro desplazado una posición a la derecha.

    CAUSA: el campo 'authors' traía una coma dentro del nombre ('Sam Bass Warner, Jr.').
    Al convertir el archivo original (CSV) a JSON, esa coma partió el campo en dos y TODO lo
    que venía después quedó corrido un lugar; la editorial terminó en la clave extra FIELD13.

        clave del JSON        contiene en realidad
        authors            -> primera parte de los autores
        average_rating     -> segunda parte de los autores
        isbn               -> average_rating        isbn13        -> isbn
        language_code      -> isbn13                num_pages     -> language_code
        ratings_count      -> num_pages             text_reviews_count -> ratings_count
        publication_date   -> text_reviews_count    publisher     -> publication_date
        FIELD13            -> publisher

    Los autores se reconstruyen volviendo a unir las dos partes con la coma que se perdió.
    """
    return {
        "bookID": d["bookID"],
        "title": d["title"],
        "authors": f"{d['authors']},{d['average_rating']}",
        "average_rating": d["isbn"],
        "isbn": d["isbn13"],
        "isbn13": d["language_code"],
        "language_code": d["num_pages"],
        "num_pages": d["ratings_count"],
        "ratings_count": d["text_reviews_count"],
        "text_reviews_count": d["publication_date"],
        "publication_date": d["publisher"],
        "publisher": d[CLAVE_EXTRA],
    }


# ------------------------------------------------------------------ validadores
def _texto(valor: Any, campo: str, maximo: int, obligatorio: bool = True) -> str:
    if not isinstance(valor, str):
        raise _Invalido(f"'{campo}' debe ser texto")
    texto = valor.strip()
    if obligatorio and not texto:
        raise _Invalido(f"'{campo}' está vacío")
    if len(texto) > maximo:
        raise _Invalido(f"'{campo}' tiene {len(texto)} caracteres (máximo {maximo})")
    return texto


def _entero(valor: Any, campo: str, maximo: int, minimo: int = 0) -> int:
    """Acepta un entero o un texto de dígitos ('652'): en el JSON vienen mezclados."""
    if isinstance(valor, bool):
        raise _Invalido(f"'{campo}' no es un número entero")
    if isinstance(valor, int):
        numero = valor
    elif isinstance(valor, str) and _PATRON_ENTERO.fullmatch(valor.strip()):
        numero = int(valor.strip())
    else:
        raise _Invalido(f"'{campo}' no es un número entero ({valor!r})")
    if not minimo <= numero <= maximo:
        raise _Invalido(f"'{campo}' = {numero} está fuera del rango {minimo}-{maximo}")
    return numero


def _calificacion(valor: Any) -> Decimal:
    if isinstance(valor, bool) or not isinstance(valor, (str, int, float)):
        raise _Invalido(f"'average_rating' no es un número ({valor!r})")
    texto = str(valor).strip()
    if not _PATRON_DECIMAL.fullmatch(texto):
        raise _Invalido(f"'average_rating' no es un número decimal ({valor!r})")
    numero = Decimal(texto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not Decimal("0") <= numero <= Decimal("5"):
        raise _Invalido(f"'average_rating' = {numero} está fuera del rango 0-5")
    return numero


def _fecha(valor: Any) -> date | None:
    """'4/20/2004' (mes/día/año) -> date. Devuelve None si no es una fecha de calendario real."""
    if not isinstance(valor, str):
        return None
    coincidencia = _PATRON_FECHA.fullmatch(valor.strip())
    if coincidencia is None:
        return None
    mes, dia, anio = (int(x) for x in coincidencia.groups())
    try:
        return date(anio, mes, dia)
    except ValueError:   # p. ej. 11/31/2000
        return None


def _autores(valor: Any) -> tuple[tuple[str, ...], int]:
    """'A/B/a' -> (('A', 'B'), 1): devuelve los autores únicos en orden y cuántos repetidos se quitaron."""
    if not isinstance(valor, str):
        raise _Invalido("'authors' debe ser texto")
    vistos: set[str] = set()
    autores: list[str] = []
    repetidos = 0
    for parte in valor.split("/"):
        nombre = parte.strip()
        if not nombre:
            continue
        if len(nombre) > LARGO_MAX_AUTOR:
            raise _Invalido(f"El autor '{nombre[:30]}…' tiene {len(nombre)} caracteres (máximo {LARGO_MAX_AUTOR})")
        if nombre.casefold() in vistos:
            repetidos += 1
            continue
        vistos.add(nombre.casefold())
        autores.append(nombre)
    return tuple(autores), repetidos


# ----------------------------------------------------------------- transformador
class TransformadorLibros:
    """Transforma registro por registro y acumula avisos por categoría.

    self.avisos: {categoría: [bookID, ...]}. Los avisos NO son errores: el libro se carga.
    """

    def __init__(self) -> None:
        self._ids_vistos: set[int] = set()
        self.avisos: dict[str, list[int]] = {}

    def _avisar(self, categoria: str, id_libro: int) -> None:
        self.avisos.setdefault(categoria, []).append(id_libro)

    def transformar(self, registro: RegistroCrudo) -> LibroLimpio | Rechazo:
        """Devuelve el libro limpio o un Rechazo con el motivo. Nunca lanza error por datos malos."""
        datos = registro.datos

        def rechazar(motivo: str) -> Rechazo:
            try:
                contenido = json.dumps(datos, ensure_ascii=False)
            except (TypeError, ValueError):
                contenido = repr(datos)
            return Rechazo(registro.numero, motivo, contenido[:200])

        if not isinstance(datos, dict):
            return rechazar("El registro no es un objeto JSON {...}")

        faltan = [c for c in COLUMNAS_ESPERADAS if c not in datos]
        if faltan:
            return rechazar(f"Faltan campos: {', '.join(faltan)}")
        sobran = {k: v for k, v in datos.items() if k not in COLUMNAS_ESPERADAS and v not in ("", None)}

        desplazado = False
        if set(sobran) == {CLAVE_EXTRA}:
            datos = _reparar_desplazamiento(datos)
            desplazado = True
        elif sobran:
            return rechazar(f"Campos inesperados con contenido: {', '.join(sobran)}")

        try:
            libro, avisos = self._validar(datos)
        except _Invalido as error:
            prefijo = "Registro desplazado que no se pudo reparar: " if desplazado else ""
            return rechazar(f"{prefijo}{error}")

        if libro.id_libro in self._ids_vistos:
            return rechazar(f"El bookID {libro.id_libro} está duplicado en el archivo (se conserva la primera aparición)")
        self._ids_vistos.add(libro.id_libro)
        if desplazado:
            avisos.append("reparado")
        for categoria in avisos:
            self._avisar(categoria, libro.id_libro)
        return libro

    def _validar(self, d: dict) -> tuple[LibroLimpio, list[str]]:
        avisos: list[str] = []
        id_libro = _entero(d["bookID"], "bookID", ID_MAX, minimo=1)
        autores, repetidos = _autores(d["authors"])
        if repetidos:
            avisos.append("autor_repetido")
        if not autores:
            avisos.append("sin_autores")

        isbn = _texto(d["isbn"], "isbn", LARGO_MAX_ISBN, obligatorio=False)
        isbn13 = _texto(d["isbn13"], "isbn13", LARGO_MAX_ISBN, obligatorio=False)
        if len(isbn) != 10:
            avisos.append("isbn_longitud")
        if len(isbn13) != 13:
            avisos.append("isbn13_longitud")

        fecha = _fecha(d["publication_date"])
        if fecha is None:
            avisos.append("fecha_invalida")

        libro = LibroLimpio(
            id_libro=id_libro,
            titulo=_texto(d["title"], "title", LARGO_MAX_TITULO),
            isbn=isbn,
            isbn13=isbn13,
            num_paginas=_entero(d["num_pages"], "num_pages", PAGINAS_MAX),
            fecha_publicacion=fecha,
            calificacion_promedio=_calificacion(d["average_rating"]),
            num_calificaciones=_entero(d["ratings_count"], "ratings_count", CONTADOR_MAX),
            num_resenas=_entero(d["text_reviews_count"], "text_reviews_count", CONTADOR_MAX),
            editorial=_texto(d["publisher"], "publisher", LARGO_MAX_EDITORIAL),
            idioma=_texto(d["language_code"], "language_code", LARGO_MAX_IDIOMA),
            autores=autores,
        )
        return libro, avisos
