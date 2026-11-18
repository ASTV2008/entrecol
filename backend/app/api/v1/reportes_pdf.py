"""Endpoints de exportación PDF: mismos servicios y parámetros que los reportes JSON."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.entretenimiento import RepositorioEntretenimiento
from app.repositories.nomina import RepositorioNomina
from app.reports.pdf import PDFResponse, respuesta_pdf
from app.schemas.reportes import Orden
from app.schemas.reportes_entretenimiento import N_MAX_GENEROS, N_MAX_LIBROS
from app.services.reporte_libros import ServicioReporteLibros
from app.services.reporte_nomina import ServicioReporteNomina
from app.services.reporte_novedades import ServicioReporteNovedades
from app.services.reporte_peliculas import ServicioReportePeliculas
from app.services.reporte_personal import ServicioReportePersonal
from app.services.reporte_salud_pension import ServicioReporteSaludPension
from app.security.dependencies import audit_report_access

router = APIRouter(
    prefix="/reportes",
    tags=["Exportación PDF"],
    default_response_class=PDFResponse,
    dependencies=[Depends(audit_report_access)],
)

OrdenQuery = Annotated[Orden, Query(description="Sentido del orden: asc o desc")]
Periodo = Annotated[str, Query(description="Periodo MM/AAAA", examples=["03/2022"])]
Anio = Annotated[int, Query(ge=1, le=9999, description="Año AAAA")]
AnioOpcional = Annotated[int | None, Query(ge=1, le=9999, description="Año AAAA (opcional)")]
Descargar = Annotated[bool, Query(description="true descarga como adjunto; false permite vista previa en el navegador")]
MinCalificaciones = Annotated[int, Query(ge=1, description="Mínimo de calificaciones")]


def _repo_nomina(db: Session = Depends(get_db)) -> RepositorioNomina:
    return RepositorioNomina(db)


def _repo_entretenimiento(db: Session = Depends(get_db)) -> RepositorioEntretenimiento:
    return RepositorioEntretenimiento(db)


RepoNomina = Annotated[RepositorioNomina, Depends(_repo_nomina)]
RepoEntretenimiento = Annotated[RepositorioEntretenimiento, Depends(_repo_entretenimiento)]


# Nómina
@router.get("/nomina/empleados/pdf", summary="PDF 1a. Cantidad y lista de empleados")
def pdf_empleados(repo: RepoNomina, orden: OrdenQuery = Orden.asc, descargar: Descargar = False):
    return respuesta_pdf("Empleados de nómina", ServicioReporteNomina(repo).lista_empleados(orden), descargar)


@router.get("/nomina/por-dependencia/pdf", summary="PDF 1b. Empleados por dependencia")
def pdf_por_dependencia(repo: RepoNomina, orden: OrdenQuery = Orden.asc, descargar: Descargar = False):
    return respuesta_pdf("Empleados por dependencia", ServicioReporteNomina(repo).por_dependencia(orden), descargar)


@router.get("/nomina/por-cargo/pdf", summary="PDF 1c. Empleados por cargo y dependencia")
def pdf_por_cargo(repo: RepoNomina, orden: OrdenQuery = Orden.asc, descargar: Descargar = False):
    return respuesta_pdf("Empleados por cargo y dependencia", ServicioReporteNomina(repo).por_cargo(orden), descargar)


@router.get("/nomina/grafico-dependencias/pdf", summary="PDF 1d. Gráfico de empleados por dependencia")
def pdf_grafico_dependencias(repo: RepoNomina, descargar: Descargar = False):
    datos = ServicioReporteNomina(repo).grafico_dependencias()
    return respuesta_pdf(datos.titulo, datos, descargar)


@router.get("/nomina/grafico-cargos/pdf", summary="PDF 1e. Gráfico de empleados por cargo")
def pdf_grafico_cargos(repo: RepoNomina, descargar: Descargar = False):
    datos = ServicioReporteNomina(repo).grafico_cargos_por_dependencia()
    return respuesta_pdf(datos.titulo, datos, descargar)


# Información personal
@router.get("/personal/pdf", summary="PDF 2. Información personal de empleados")
def pdf_personal(
    repo: RepoNomina,
    orden: OrdenQuery = Orden.asc,
    codigo: Annotated[int | None, Query(ge=1, description="Código de un empleado (opcional)")] = None,
    descargar: Descargar = False,
):
    return respuesta_pdf("Información personal de empleados", ServicioReportePersonal(repo).reporte(orden, codigo), descargar)


# Salud y pensión
@router.get("/salud-pension/grafico-eps/pdf", summary="PDF 3a. Frecuencia por EPS")
def pdf_grafico_eps(repo: RepoNomina, descargar: Descargar = False):
    datos = ServicioReporteSaludPension(repo).grafico_entidad("eps")
    return respuesta_pdf(datos.titulo, datos, descargar)


@router.get("/salud-pension/grafico-pension/pdf", summary="PDF 3b. Frecuencia por pensión")
def pdf_grafico_pension(repo: RepoNomina, descargar: Descargar = False):
    datos = ServicioReporteSaludPension(repo).grafico_entidad("pension")
    return respuesta_pdf(datos.titulo, datos, descargar)


@router.get("/salud-pension/grafico-eps-dependencia/pdf", summary="PDF 3c. EPS por dependencia")
def pdf_grafico_eps_dependencia(repo: RepoNomina, descargar: Descargar = False):
    datos = ServicioReporteSaludPension(repo).grafico_entidad_por_dependencia("eps")
    return respuesta_pdf(datos.titulo, datos, descargar)


@router.get("/salud-pension/grafico-pension-dependencia/pdf", summary="PDF 3d. Pensión por dependencia")
def pdf_grafico_pension_dependencia(repo: RepoNomina, descargar: Descargar = False):
    datos = ServicioReporteSaludPension(repo).grafico_entidad_por_dependencia("pension")
    return respuesta_pdf(datos.titulo, datos, descargar)


@router.get("/salud-pension/por-cargo-eps/pdf", summary="PDF 3e. Empleados por cargo y EPS")
def pdf_por_cargo_eps(repo: RepoNomina, orden: OrdenQuery = Orden.asc, descargar: Descargar = False):
    datos = ServicioReporteSaludPension(repo).por_cargo_y_entidad("eps", orden)
    return respuesta_pdf("Empleados por cargo y EPS", datos, descargar)


@router.get("/salud-pension/por-cargo-pension/pdf", summary="PDF 3f. Empleados por cargo y pensión")
def pdf_por_cargo_pension(repo: RepoNomina, orden: OrdenQuery = Orden.asc, descargar: Descargar = False):
    datos = ServicioReporteSaludPension(repo).por_cargo_y_entidad("pension", orden)
    return respuesta_pdf("Empleados por cargo y pensión", datos, descargar)


# Novedades
@router.get("/novedades/empleados/pdf", summary="PDF 4a. Empleados con novedades")
def pdf_novedades_empleados(
    repo: RepoNomina,
    desde: Periodo,
    hasta: Periodo,
    orden: OrdenQuery = Orden.asc,
    descargar: Descargar = False,
):
    datos = ServicioReporteNovedades(repo).empleados(desde, hasta, orden)
    return respuesta_pdf("Empleados con novedades", datos, descargar)


@router.get("/novedades/resumen/pdf", summary="PDF 4b. Resumen de novedades")
def pdf_novedades_resumen(repo: RepoNomina, desde: Periodo, hasta: Periodo, descargar: Descargar = False):
    datos = ServicioReporteNovedades(repo).resumen(desde, hasta)
    return respuesta_pdf("Resumen de novedades", datos, descargar)


# Entretenimiento
@router.get("/entretenimiento/peliculas-por-genero/pdf", summary="PDF 5a. Películas por género")
def pdf_peliculas_por_genero(
    repo: RepoEntretenimiento,
    desde: Anio,
    hasta: Anio,
    orden: OrdenQuery = Orden.asc,
    descargar: Descargar = False,
):
    datos = ServicioReportePeliculas(repo).por_genero(desde, hasta, orden)
    return respuesta_pdf("Películas por género", datos, descargar)


@router.get("/entretenimiento/libros/top/pdf", summary="PDF 5b. Top N libros")
def pdf_top_libros(
    repo: RepoEntretenimiento,
    n: Annotated[int, Query(ge=1, le=N_MAX_LIBROS, description="Cuántos libros mostrar")],
    orden: OrdenQuery = Orden.asc,
    min_calificaciones: MinCalificaciones = 1,
    descargar: Descargar = False,
):
    datos = ServicioReporteLibros(repo).top(n, orden, min_calificaciones)
    return respuesta_pdf("Top de libros", datos, descargar)


@router.get("/entretenimiento/libros/top-por-anio/pdf", summary="PDF 5c. Top de libros por año")
def pdf_top_por_anio(
    repo: RepoEntretenimiento,
    orden: OrdenQuery = Orden.asc,
    desde: AnioOpcional = None,
    hasta: AnioOpcional = None,
    min_calificaciones: MinCalificaciones = 1,
    descargar: Descargar = False,
):
    datos = ServicioReporteLibros(repo).top_por_anio(orden, desde, hasta, min_calificaciones)
    return respuesta_pdf("Top de libros por año", datos, descargar)


@router.get("/entretenimiento/peliculas/por-numero-de-generos/pdf", summary="PDF 5d. Películas por número de géneros")
def pdf_peliculas_por_numero_de_generos(
    repo: RepoEntretenimiento,
    n: Annotated[int, Query(ge=0, le=N_MAX_GENEROS, description="Cantidad de géneros")],
    orden: OrdenQuery = Orden.asc,
    descargar: Descargar = False,
):
    datos = ServicioReportePeliculas(repo).por_numero_de_generos(n, orden)
    return respuesta_pdf("Películas por número de géneros", datos, descargar)


@router.get("/entretenimiento/graficos/peliculas-por-genero/pdf", summary="PDF 5e. Películas por género")
def pdf_grafico_peliculas_por_genero(repo: RepoEntretenimiento, descargar: Descargar = False):
    datos = ServicioReportePeliculas(repo).grafico_por_genero()
    return respuesta_pdf(datos.titulo, datos, descargar)


@router.get("/entretenimiento/graficos/libros-por-anio/pdf", summary="PDF 5f. Libros por año")
def pdf_grafico_libros_por_anio(repo: RepoEntretenimiento, desde: Anio, hasta: Anio, descargar: Descargar = False):
    datos = ServicioReporteLibros(repo).grafico_por_anio(desde, hasta)
    return respuesta_pdf(datos.titulo, datos, descargar)
