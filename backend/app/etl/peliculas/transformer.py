"""TRANSFORMAR: valida y limpia una línea de movies.dat.

Formato de cada línea:   id::Título (año)::Género1|Género2|...
Ejemplo:                 1::Toy Story (1995)::Adventure|Animation|Children|Comedy|Fantasy

Lo que se resuelve aquí (ver el MER, etapa 3):
    - El año viaja dentro del título: se separa en su propio dato (atributo compuesto).
    - Los géneros vienen en un solo texto: se parten en una lista (atributo multivalor).
    - "(no genres listed)" NO es un género: significa que la película no tiene ninguno.
"""
import re
from dataclasses import dataclass

from app.etl.common import Rechazo
from app.etl.peliculas.extractor import LineaCruda

# Límites: deben coincidir con las columnas y restricciones de database/init/02_entretenimiento.sql
LARGO_MAX_TITULO = 200
LARGO_MAX_GENERO = 30
ANIO_MIN, ANIO_MAX = 1800, 2100
ID_MAX = 4_294_967_295   # INT UNSIGNED

SEPARADOR_CAMPOS = "::"
SEPARADOR_GENEROS = "|"
SIN_GENEROS = "(no genres listed)"

# "Título (1995)" -> título + año. El título puede tener paréntesis propios:
# "Hellraiser (a.k.a. X) (2002)": solo el ÚLTIMO paréntesis de 4 dígitos es el año.
_PATRON_TITULO_Y_ANIO = re.compile(r"^(?P<titulo>.+?)\s*\((?P<anio>\d{4})\)\s*$")
_PATRON_ENTERO = re.compile(r"\d+", re.ASCII)


@dataclass(frozen=True)
class PeliculaLimpia:
    """Una película ya validada, lista para cargarse."""

    id_pelicula: int
    titulo: str
    anio_estreno: int
    generos: tuple[str, ...]   # puede estar vacía


class TransformadorPeliculas:
    """Transforma línea por línea. Guarda los ids ya vistos para detectar duplicados."""

    def __init__(self) -> None:
        self._ids_vistos: set[int] = set()

    def transformar(self, linea: LineaCruda) -> PeliculaLimpia | Rechazo:
        """Devuelve la película limpia o un Rechazo con el motivo. Nunca lanza error por datos malos."""

        def rechazar(motivo: str) -> Rechazo:
            return Rechazo(linea.numero, motivo, linea.texto[:200])

        campos = linea.texto.split(SEPARADOR_CAMPOS)
        if len(campos) != 3:
            return rechazar(f"Se esperaban 3 campos separados por '::' y hay {len(campos)}")
        texto_id, texto_titulo, texto_generos = (campo.strip() for campo in campos)

        # --- id ---
        if not _PATRON_ENTERO.fullmatch(texto_id):
            return rechazar(f"El id '{texto_id}' no es un número entero")
        id_pelicula = int(texto_id)
        if not 1 <= id_pelicula <= ID_MAX:
            return rechazar(f"El id {id_pelicula} está fuera del rango permitido")
        if id_pelicula in self._ids_vistos:
            return rechazar(f"El id {id_pelicula} está duplicado en el archivo (se conserva la primera aparición)")

        # --- título y año ---
        coincidencia = _PATRON_TITULO_Y_ANIO.match(texto_titulo)
        if coincidencia is None:
            return rechazar("El título no termina con un año entre paréntesis, por ejemplo 'Toy Story (1995)'")
        titulo = coincidencia["titulo"].strip()
        anio = int(coincidencia["anio"])
        if not titulo:
            return rechazar("El título está vacío")
        if len(titulo) > LARGO_MAX_TITULO:
            return rechazar(f"El título tiene {len(titulo)} caracteres (máximo {LARGO_MAX_TITULO})")
        if not ANIO_MIN <= anio <= ANIO_MAX:
            return rechazar(f"El año {anio} está fuera del rango {ANIO_MIN}-{ANIO_MAX}")

        # --- géneros ---
        generos = self._partir_generos(texto_generos)
        demasiado_largo = next((g for g in generos if len(g) > LARGO_MAX_GENERO), None)
        if demasiado_largo is not None:
            return rechazar(f"El género '{demasiado_largo}' supera {LARGO_MAX_GENERO} caracteres")

        self._ids_vistos.add(id_pelicula)
        return PeliculaLimpia(id_pelicula, titulo, anio, generos)

    @staticmethod
    def _partir_generos(texto: str) -> tuple[str, ...]:
        """'A|B|a' -> ('A', 'B'). Quita espacios, vacíos y repetidos (sin distinguir mayúsculas)."""
        if texto.casefold() == SIN_GENEROS.casefold():
            return ()
        vistos: set[str] = set()
        generos: list[str] = []
        for parte in texto.split(SEPARADOR_GENEROS):
            genero = parte.strip()
            if genero and genero.casefold() not in vistos:
                vistos.add(genero.casefold())
                generos.append(genero)
        return tuple(generos)
