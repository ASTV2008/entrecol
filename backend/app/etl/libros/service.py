"""Orquesta el ETL de libros: extraer -> transformar -> cargar -> informe."""
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.etl.common import ErrorDeArchivo, InformeCarga, Rechazo
from app.etl.libros.extractor import leer_registros
from app.etl.libros.loader import CargadorLibros
from app.etl.libros.transformer import LibroLimpio, TransformadorLibros

FUENTE = "Books.json (libros)"

_AVISOS = {
    "reparado": "{n} registro(s) venían desplazados por una coma dentro de 'authors' y se repararon (bookID {ej}).",
    "fecha_invalida": "{n} libro(s) con fecha de publicación inexistente se cargaron SIN fecha (bookID {ej}).",
    "autor_repetido": "{n} libro(s) repetían un mismo autor en su lista; se conservó una sola vez (bookID {ej}).",
    "sin_autores": "{n} libro(s) sin ningún autor (bookID {ej}).",
    "isbn_longitud": "{n} libro(s) con ISBN de longitud distinta de 10; se cargó tal como viene (bookID {ej}).",
    "isbn13_longitud": "{n} libro(s) con ISBN13 de longitud distinta de 13; se cargó tal como viene (bookID {ej}).",
}


def _ejemplos(ids: list[int], cuantos: int = 5) -> str:
    texto = ", ".join(str(i) for i in ids[:cuantos])
    return texto + (", ..." if len(ids) > cuantos else "")


def cargar_libros(flujo: BinaryIO, sesion: Session) -> InformeCarga:
    """Carga un archivo Books.json. NO hace commit: lo decide quien llama.

    Lanza ErrorDeArchivo si el archivo completo no sirve. Los registros malos
    individuales NO detienen la carga: se descartan y quedan en el informe.
    """
    informe = InformeCarga(fuente=FUENTE, unidad_fila="registro")
    transformador = TransformadorLibros()
    limpios: list[LibroLimpio] = []

    for registro in leer_registros(flujo):
        informe.leidas += 1
        resultado = transformador.transformar(registro)
        if isinstance(resultado, Rechazo):
            informe.rechazos.append(resultado)
        else:
            limpios.append(resultado)

    if informe.leidas == 0:
        raise ErrorDeArchivo("El archivo no contiene ningún libro (la lista está vacía).")
    if not limpios:
        raise ErrorDeArchivo("Ningún registro es válido. ¿Es realmente el archivo Books.json?")
    informe.aceptadas = len(limpios)

    cargado = CargadorLibros(sesion).cargar(limpios)
    informe.nuevas = cargado.nuevas
    informe.actualizadas = cargado.actualizadas
    informe.sin_cambios = cargado.sin_cambios

    informe.detalles["Autores nuevos"] = cargado.autores.nuevos
    informe.detalles["Editoriales nuevas"] = cargado.editoriales.nuevos
    informe.detalles["Idiomas nuevos"] = cargado.idiomas.nuevos
    informe.detalles["Vínculos libro-autor"] = cargado.vinculos
    informe.detalles["Libros sin calificaciones"] = sum(1 for l in limpios if l.num_calificaciones == 0)
    informe.detalles["Libros con 0 páginas"] = sum(1 for l in limpios if l.num_paginas == 0)

    for categoria, plantilla in _AVISOS.items():
        ids = transformador.avisos.get(categoria)
        if ids:
            informe.advertencias.append(plantilla.format(n=len(ids), ej=_ejemplos(ids)))
    if cargado.editoriales.unificados:
        ejemplo = " = ".join(f"'{n}'" for n in cargado.editoriales.equivalentes[0])
        informe.advertencias.append(
            f"{cargado.editoriales.unificados} nombre(s) de editorial se unificaron con otro equivalente "
            f"(mayúsculas o tildes), por ejemplo {ejemplo}."
        )
    if cargado.autores.unificados:
        ejemplo = " = ".join(f"'{n}'" for n in cargado.autores.equivalentes[0])
        informe.advertencias.append(f"{cargado.autores.unificados} nombre(s) de autor se unificaron, por ejemplo {ejemplo}.")
    if informe.rechazadas > informe.aceptadas:
        informe.advertencias.append("Se rechazaron más registros de los que se aceptaron: revise el archivo.")
    return informe
