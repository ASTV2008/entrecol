"""Endpoints del reporte 5 - BASE-ENTRETENIMIENTO. Capa HTTP delgada: valida y delega en los servicios."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.entretenimiento import RepositorioEntretenimiento
from app.schemas.reportes import Grafico, Orden
from app.schemas.reportes_entretenimiento import (
    N_MAX_GENEROS, N_MAX_LIBROS, ReportePeliculasPorGenero, ReportePeliculasPorNGeneros, ReporteTopLibros,
    ReporteTopPorAnio,
)
from app.services.reporte_libros import ServicioReporteLibros
from app.services.reporte_peliculas import ServicioReportePeliculas

router = APIRouter(prefix="/reportes/entretenimiento", tags=["Reportes de entretenimiento"])

OrdenTitulos = Annotated[Orden, Query(description="Sentido del orden de los TÍTULOS: asc o desc")]
Anio = Annotated[int, Query(ge=1, le=9999, description="Año AAAA")]
AnioOpcional = Annotated[int | None, Query(ge=1, le=9999, description="Año AAAA (opcional)")]
MinCalificaciones = Annotated[int, Query(ge=1, description="Mínimo de calificaciones que debe tener un libro para entrar al ranking")]


def _repo(db: Session = Depends(get_db)) -> RepositorioEntretenimiento:
    return RepositorioEntretenimiento(db)


Repo = Annotated[RepositorioEntretenimiento, Depends(_repo)]


@router.get("/peliculas-por-genero", response_model=ReportePeliculasPorGenero, summary="5a. Películas por género entre F1 y F2")
def peliculas_por_genero(repo: Repo, desde: Anio, hasta: Anio, orden: OrdenTitulos = Orden.asc):
    return ServicioReportePeliculas(repo).por_genero(desde, hasta, orden)


@router.get("/libros/top", response_model=ReporteTopLibros, summary="5b. Top N libros con mejor rating")
def top_libros(repo: Repo, n: Annotated[int, Query(ge=1, le=N_MAX_LIBROS, description="Cuántos libros mostrar")],
               orden: OrdenTitulos = Orden.asc, min_calificaciones: MinCalificaciones = 1):
    return ServicioReporteLibros(repo).top(n, orden, min_calificaciones)


@router.get("/libros/top-por-anio", response_model=ReporteTopPorAnio, summary="5c. Top 5 mejores y peores libros por año")
def top_por_anio(repo: Repo, orden: OrdenTitulos = Orden.asc, desde: AnioOpcional = None, hasta: AnioOpcional = None,
                 min_calificaciones: MinCalificaciones = 1):
    return ServicioReporteLibros(repo).top_por_anio(orden, desde, hasta, min_calificaciones)


@router.get("/peliculas/por-numero-de-generos", response_model=ReportePeliculasPorNGeneros,
            summary="5d. Películas con exactamente N géneros")
def peliculas_por_n_generos(repo: Repo, n: Annotated[int, Query(ge=0, le=N_MAX_GENEROS, description="Cantidad de géneros")],
                            orden: OrdenTitulos = Orden.asc):
    return ServicioReportePeliculas(repo).por_numero_de_generos(n, orden)


@router.get("/graficos/peliculas-por-genero", response_model=Grafico, summary="5e. Frecuencia de películas por género")
def grafico_peliculas_por_genero(repo: Repo):
    return ServicioReportePeliculas(repo).grafico_por_genero()


@router.get("/graficos/libros-por-anio", response_model=Grafico, summary="5f. Frecuencia de libros por año entre F1 y F2")
def grafico_libros_por_anio(repo: Repo, desde: Anio, hasta: Anio):
    return ServicioReporteLibros(repo).grafico_por_anio(desde, hasta)
