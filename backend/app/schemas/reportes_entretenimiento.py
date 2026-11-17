"""Esquemas del reporte 5 - BASE-ENTRETENIMIENTO (películas y libros)."""
from pydantic import BaseModel

# Límites de los parámetros N (evitan volcar tablas enteras por error; fuera de rango -> 422)
N_MAX_LIBROS = 100
N_MAX_GENEROS = 30
TOP_POR_ANIO = 5


# ---------------------------------------------------------------- películas
class PeliculaItem(BaseModel):
    id_pelicula: int
    titulo: str
    anio: int


class GrupoGenero(BaseModel):
    genero: str
    cantidad: int
    peliculas: list[PeliculaItem]


class ReportePeliculasPorGenero(BaseModel):
    desde: int
    hasta: int
    total_peliculas: int         # películas DISTINTAS (una película con 3 géneros aparece en 3 grupos pero cuenta 1)
    nota: str
    generos: list[GrupoGenero]


class PeliculaConGeneros(BaseModel):
    id_pelicula: int
    titulo: str
    anio: int
    generos: list[str]


class ReportePeliculasPorNGeneros(BaseModel):
    n: int
    total: int
    peliculas: list[PeliculaConGeneros]


# -------------------------------------------------------------------- libros
class LibroPuesto(BaseModel):
    posicion: int                # 1 = el mejor (o el peor, según la lista)
    id_libro: int
    titulo: str
    calificacion: float
    num_calificaciones: int
    anio: int | None             # None si la fecha de publicación no es válida en el origen


class ReporteTopLibros(BaseModel):
    n: int
    total: int
    criterio: str
    libros: list[LibroPuesto]


class TopDelAnio(BaseModel):
    anio: int
    mejores: list[LibroPuesto]
    peores: list[LibroPuesto]


class ReporteTopPorAnio(BaseModel):
    desde: int | None
    hasta: int | None
    criterio: str
    anios: list[TopDelAnio]
