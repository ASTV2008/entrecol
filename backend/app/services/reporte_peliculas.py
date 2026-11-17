"""Reporte 5 (películas): 5a por género y rango de años, 5d con N géneros y 5e frecuencia por género."""
from itertools import groupby

from app.repositories.entretenimiento import RepositorioEntretenimiento
from app.schemas.reportes import Grafico, Orden, Serie
from app.schemas.reportes_entretenimiento import (
    GrupoGenero, PeliculaConGeneros, PeliculaItem, ReportePeliculasPorGenero, ReportePeliculasPorNGeneros,
)
from app.services.periodos import leer_anios

NOTA_MULTIGENERO = ("Una película pertenece a varios géneros: aparece en cada uno de ellos, "
                    "por eso la suma de los grupos puede superar el total de películas distintas.")


class ServicioReportePeliculas:
    def __init__(self, repo: RepositorioEntretenimiento) -> None:
        self._repo = repo

    # 5a) películas por género entre F1 y F2 (años)
    def por_genero(self, desde: int, hasta: int, orden: Orden) -> ReportePeliculasPorGenero:
        leer_anios(desde, hasta)
        filas = self._repo.peliculas_por_genero(desde, hasta, orden)
        grupos = []
        for _, de_genero in groupby(filas, key=lambda f: f.id_genero):
            de_genero = list(de_genero)
            grupos.append(GrupoGenero(
                genero=de_genero[0].genero, cantidad=len(de_genero),
                peliculas=[PeliculaItem(id_pelicula=f.id_pelicula, titulo=f.titulo, anio=f.anio) for f in de_genero]))
        return ReportePeliculasPorGenero(
            desde=desde, hasta=hasta, total_peliculas=self._repo.total_peliculas_distintas(desde, hasta),
            nota=NOTA_MULTIGENERO, generos=grupos)

    # 5d) películas con exactamente N géneros
    def por_numero_de_generos(self, n: int, orden: Orden) -> ReportePeliculasPorNGeneros:
        filas = self._repo.peliculas_con_n_generos(n, orden)
        peliculas = []
        for _, de_pelicula in groupby(filas, key=lambda f: f.id_pelicula):
            de_pelicula = list(de_pelicula)
            primera = de_pelicula[0]
            peliculas.append(PeliculaConGeneros(
                id_pelicula=primera.id_pelicula, titulo=primera.titulo, anio=primera.anio,
                generos=[f.genero for f in de_pelicula if f.genero is not None]))
        return ReportePeliculasPorNGeneros(n=n, total=len(peliculas), peliculas=peliculas)

    # 5e) gráfico de frecuencia de películas por género
    def grafico_por_genero(self) -> Grafico:
        filas = self._repo.conteo_peliculas_por_genero()
        return Grafico(
            titulo="Películas por género", tipo="barras", etiquetas=[f.genero for f in filas],
            series=[Serie(nombre="Películas", valores=[f.cantidad for f in filas])], nota=NOTA_MULTIGENERO)
