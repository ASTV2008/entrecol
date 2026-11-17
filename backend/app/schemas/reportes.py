"""Esquemas (DTOs) de los reportes: definen la forma exacta de cada respuesta de la API.

Se reutilizan formas genéricas (Grafico, lista de empleados) para que el frontend y el
generador de PDF traten todos los reportes de la misma manera.
"""
from enum import Enum

from pydantic import BaseModel


class Orden(str, Enum):
    """Sentido en que el usuario quiere ordenar los nombres."""

    asc = "asc"
    desc = "desc"


# ------------------------------------------------------------------- piezas comunes
class EmpleadoItem(BaseModel):
    codigo: int
    nombre: str


class Serie(BaseModel):
    nombre: str
    valores: list[int]


class Grafico(BaseModel):
    """Datos de un gráfico. El navegador (Chart.js) y el PDF lo dibujan a partir de esto."""

    titulo: str
    tipo: str                               # "torta" | "barras"
    etiquetas: list[str]                    # eje X (o porciones de la torta)
    series: list[Serie]                     # una serie en torta; varias en barras comparativas
    grupos: list[str] | None = None         # opcional: a qué grupo pertenece cada etiqueta (p. ej. su dependencia)


# --------------------------------------------------------- reporte 1: nómina
class ListaEmpleados(BaseModel):
    total: int
    empleados: list[EmpleadoItem]


class GrupoDependencia(BaseModel):
    dependencia: str
    cantidad: int
    empleados: list[EmpleadoItem]


class ReporteDependencias(BaseModel):
    total: int
    dependencias: list[GrupoDependencia]


class GrupoCargo(BaseModel):
    cargo: str
    cantidad: int
    empleados: list[EmpleadoItem]


class GrupoDependenciaCargos(BaseModel):
    dependencia: str
    cantidad: int
    cargos: list[GrupoCargo]


class ReporteCargos(BaseModel):
    total: int
    dependencias: list[GrupoDependenciaCargos]


# --------------------------------------------------- reporte 2: información personal
class EventoNovedad(BaseModel):
    fecha_inicio: str        # DD/MM/AAAA
    fecha_fin: str
    dias: int


class NovedadPeriodo(BaseModel):
    periodo: str             # MM/AAAA
    dias_trabajados: int
    incapacidades: list[EventoNovedad]
    vacaciones: list[EventoNovedad]
    bonificacion: float
    transporte: float


class FichaPersonal(BaseModel):
    codigo: int
    nombre: str
    dependencia: str
    cargo: str
    fecha_ingreso: str       # DD/MM/AAAA
    eps: str
    fondo_pension: str
    aporte_pension: float    # 4 % del sueldo (aporte del trabajador); se calcula, no se guarda
    sueldo: float
    novedades: list[NovedadPeriodo]


class ReportePersonal(BaseModel):
    total: int
    tasa_aporte_pension: float
    empleados: list[FichaPersonal]


# ----------------------------------------------------- reporte 3: salud y pensión
class GrupoEntidad(BaseModel):
    entidad: str             # nombre de la EPS o del fondo de pensión
    cantidad: int
    empleados: list[EmpleadoItem]


class GrupoCargoEntidad(BaseModel):
    cargo: str
    cantidad: int
    entidades: list[GrupoEntidad]


class ReporteCargoEntidad(BaseModel):
    total: int
    entidad_tipo: str        # "EPS" | "Pensión"
    cargos: list[GrupoCargoEntidad]


# ------------------------------------------------------------ reporte 4: novedades
class EventoDetalle(BaseModel):
    tipo: str                # "Incapacidad" | "Vacaciones"
    periodo: str             # MM/AAAA
    fecha_inicio: str
    fecha_fin: str
    dias: int


class EmpleadoConNovedades(BaseModel):
    codigo: int
    nombre: str
    dependencia: str
    cargo: str
    novedades: list[EventoDetalle]


class ReporteNovedades(BaseModel):
    desde: str
    hasta: str
    total: int
    empleados: list[EmpleadoConNovedades]


class ConteoCargo(BaseModel):
    cargo: str
    cantidad: int


class ConteoDependencia(BaseModel):
    dependencia: str
    cantidad: int
    cargos: list[ConteoCargo]


class ResumenNovedades(BaseModel):
    desde: str
    hasta: str
    total: int
    dependencias: list[ConteoDependencia]
