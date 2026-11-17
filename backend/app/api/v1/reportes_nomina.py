"""Endpoints de los reportes de NÓMINA (reportes 1 a 4 del enunciado). Capa HTTP delgada: valida
parámetros y delega en los servicios."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.nomina import RepositorioNomina
from app.schemas.reportes import (
    Grafico, ListaEmpleados, Orden, ReporteCargoEntidad, ReporteCargos, ReporteDependencias, ReporteNovedades,
    ReportePersonal, ResumenNovedades,
)
from app.services.reporte_nomina import ServicioReporteNomina
from app.services.reporte_novedades import ServicioReporteNovedades
from app.services.reporte_personal import ServicioReportePersonal
from app.services.reporte_salud_pension import ServicioReporteSaludPension

router = APIRouter(prefix="/reportes", tags=["Reportes de nómina"])

OrdenNombres = Annotated[Orden, Query(description="Sentido del orden de los NOMBRES: asc o desc")]
# F1 y F2 en formato MM/AAAA (el servicio valida además que F1 <= F2)
Desde = Annotated[str, Query(description="Periodo inicial MM/AAAA", examples=["03/2022"])]
Hasta = Annotated[str, Query(description="Periodo final MM/AAAA", examples=["03/2022"])]


def _repo(db: Session = Depends(get_db)) -> RepositorioNomina:
    return RepositorioNomina(db)


Repo = Annotated[RepositorioNomina, Depends(_repo)]


# ------------------------------------------------------------- 1. Nómina
@router.get("/nomina/empleados", response_model=ListaEmpleados, summary="1a. Cantidad y lista de empleados")
def empleados(repo: Repo, orden: OrdenNombres = Orden.asc):
    return ServicioReporteNomina(repo).lista_empleados(orden)


@router.get("/nomina/por-dependencia", response_model=ReporteDependencias, summary="1b. Empleados por dependencia")
def por_dependencia(repo: Repo, orden: OrdenNombres = Orden.asc):
    return ServicioReporteNomina(repo).por_dependencia(orden)


@router.get("/nomina/por-cargo", response_model=ReporteCargos, summary="1c. Empleados por cargo por dependencia")
def por_cargo(repo: Repo, orden: OrdenNombres = Orden.asc):
    return ServicioReporteNomina(repo).por_cargo(orden)


@router.get("/nomina/grafico-dependencias", response_model=Grafico, summary="1d. Torta: empleados por dependencia")
def grafico_dependencias(repo: Repo):
    return ServicioReporteNomina(repo).grafico_dependencias()


@router.get("/nomina/grafico-cargos", response_model=Grafico, summary="1e. Barras: empleados por cargo y dependencia")
def grafico_cargos(repo: Repo):
    return ServicioReporteNomina(repo).grafico_cargos_por_dependencia()


# ---------------------------------------------------- 2. Información personal
@router.get("/personal", response_model=ReportePersonal, summary="2. Información personal de los empleados")
def personal(repo: Repo, orden: OrdenNombres = Orden.asc,
             codigo: Annotated[int | None, Query(description="Código de UN empleado (opcional)", ge=1)] = None):
    return ServicioReportePersonal(repo).reporte(orden, codigo)


# -------------------------------------------------------- 3. Salud y pensión
@router.get("/salud-pension/grafico-eps", response_model=Grafico, summary="3a. Frecuencia por EPS")
def grafico_eps(repo: Repo):
    return ServicioReporteSaludPension(repo).grafico_entidad("eps")


@router.get("/salud-pension/grafico-pension", response_model=Grafico, summary="3b. Frecuencia por pensión")
def grafico_pension(repo: Repo):
    return ServicioReporteSaludPension(repo).grafico_entidad("pension")


@router.get("/salud-pension/grafico-eps-dependencia", response_model=Grafico, summary="3c. Barras: EPS por dependencia")
def grafico_eps_dependencia(repo: Repo):
    return ServicioReporteSaludPension(repo).grafico_entidad_por_dependencia("eps")


@router.get("/salud-pension/grafico-pension-dependencia", response_model=Grafico, summary="3d. Barras: pensión por dependencia")
def grafico_pension_dependencia(repo: Repo):
    return ServicioReporteSaludPension(repo).grafico_entidad_por_dependencia("pension")


@router.get("/salud-pension/por-cargo-eps", response_model=ReporteCargoEntidad, summary="3e. Empleados por cargo y EPS")
def por_cargo_eps(repo: Repo, orden: OrdenNombres = Orden.asc):
    return ServicioReporteSaludPension(repo).por_cargo_y_entidad("eps", orden)


@router.get("/salud-pension/por-cargo-pension", response_model=ReporteCargoEntidad, summary="3f. Empleados por cargo y pensión")
def por_cargo_pension(repo: Repo, orden: OrdenNombres = Orden.asc):
    return ServicioReporteSaludPension(repo).por_cargo_y_entidad("pension", orden)


# ------------------------------------------------------------- 4. Novedades
@router.get("/novedades/empleados", response_model=ReporteNovedades, summary="4a. Empleados con novedades entre F1 y F2")
def novedades_empleados(repo: Repo, desde: Desde, hasta: Hasta, orden: OrdenNombres = Orden.asc):
    return ServicioReporteNovedades(repo).empleados(desde, hasta, orden)


@router.get("/novedades/resumen", response_model=ResumenNovedades, summary="4b. Cantidad con novedades por dependencia y cargo")
def novedades_resumen(repo: Repo, desde: Desde, hasta: Hasta):
    return ServicioReporteNovedades(repo).resumen(desde, hasta)
