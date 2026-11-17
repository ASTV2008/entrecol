"""TRANSFORMAR: valida y limpia las filas de empleados y de novedades.

Reglas (decididas con el cliente / el equipo):
  RECHAZAN la fila (no se carga, queda en el informe con su motivo):
    - campos obligatorios vacíos o inválidos, sueldo <= 0, código repetido en el archivo
    - marca 'X' sin fechas · días > 0 sin fechas · fechas con 0 días · fecha fin < inicio · fechas incompletas
  SOLO AVISAN (se carga igual):
    - días reportados distintos de los días entre las fechas (el valor del cliente se conserva)
    - fechas sin la marca 'X'
    - evento que no toca el mes del periodo
    - días trabajados + incapacidad + vacaciones distinto de 30
  Que el empleado de una novedad exista lo comprueba el servicio (puede estar en la base).
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.etl.common import Rechazo
from app.etl.nomina.extractor import FilaCruda
from app.etl.validadores import ErrorDeValor, dinero, entero, fecha_excel, texto

# Límites: deben coincidir con database/init/01_nomina.sql
LARGO_NOMBRE_EMPLEADO = 100
LARGO_DEPENDENCIA = LARGO_EPS = LARGO_ARL = LARGO_PENSION = 60
LARGO_CARGO = 80
DIAS_DEL_MES_LABORAL = 30


@dataclass(frozen=True)
class EmpleadoLimpio:
    codigo: int
    nombre: str
    dependencia: str
    cargo: str
    fecha_ingreso: date
    eps: str
    arl: str
    fondo_pension: str
    sueldo: Decimal


@dataclass(frozen=True)
class EventoLimpio:
    """Una incapacidad o un periodo de vacaciones."""

    inicio: date
    fin: date
    dias_reportados: int


@dataclass(frozen=True)
class NovedadLimpia:
    codigo: int
    bonificacion: Decimal
    transporte: Decimal
    incapacidad: EventoLimpio | None
    vacacion: EventoLimpio | None
    # Dónde estaba en el archivo (para informar si el servicio la rechaza después); no cuenta al comparar
    fila: int = field(default=0, compare=False)
    hoja: str = field(default="", compare=False)


def _contenido(fila: FilaCruda) -> str:
    partes = ", ".join(f"{k}={v!r}" for k, v in fila.valores.items() if v is not None)
    return partes[:200]


def _es_marca(valor: object) -> bool:
    return isinstance(valor, str) and valor.strip().upper() == "X"


def _marca_valida(valor: object, campo: str) -> bool:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return False
    if _es_marca(valor):
        return True
    raise ErrorDeValor(f"'{campo}' solo admite 'X' o vacío: {valor!r}")


class TransformadorEmpleados:
    def __init__(self) -> None:
        self._vistos: set[int] = set()

    def transformar(self, fila: FilaCruda) -> EmpleadoLimpio | Rechazo:
        v = fila.valores
        try:
            codigo = entero(v["codigo"], "CÓDIGO", minimo=1)
            if codigo in self._vistos:
                raise ErrorDeValor(f"el código {codigo} está repetido en el archivo")
            limpio = EmpleadoLimpio(
                codigo=codigo,
                nombre=texto(v["nombre"], "NOMBRE DEL EMPLEADO", LARGO_NOMBRE_EMPLEADO),
                dependencia=texto(v["dependencia"], "DEPENDENCIA", LARGO_DEPENDENCIA),
                cargo=texto(v["cargo"], "CARGO", LARGO_CARGO),
                fecha_ingreso=fecha_excel(v["fecha_ingreso"], "FECHA INGRESO"),
                eps=texto(v["eps"], "EPS", LARGO_EPS),
                arl=texto(v["arl"], "ARL", LARGO_ARL),
                fondo_pension=texto(v["pension"], "PENSIÓN", LARGO_PENSION),
                sueldo=dinero(v["sueldo"], "SUELDO", minimo=Decimal("0.01")),
            )
        except ErrorDeValor as error:
            return Rechazo(fila.numero, str(error), _contenido(fila), fila.hoja)
        self._vistos.add(codigo)
        return limpio


class TransformadorNovedades:
    def __init__(self, anio: int, mes: int) -> None:
        self._anio, self._mes = anio, mes
        self._vistos: set[int] = set()
        self.avisos: dict[str, list[int]] = {}    # categoría -> códigos de empleado afectados

    def _toca_el_mes(self, inicio: date, fin: date) -> bool:
        primero = date(self._anio, self._mes, 1)
        ultimo = date(self._anio + (self._mes == 12), self._mes % 12 + 1, 1)   # primer día del mes siguiente
        return inicio < ultimo and fin >= primero

    def _evento(self, v: dict, nombre: str, marca: str, dias: str, inicio: str, fin: str, avisos: list[str]) -> EventoLimpio | None:
        con_marca = _marca_valida(v[marca], f"NOVEDAD {nombre.upper()}")
        dias_n = entero(v[dias], f"NUMERO DE DIAS {nombre.upper()}", minimo=0, maximo=31)
        f_ini = fecha_excel(v[inicio], f"FECHA INICIO {nombre.upper()}", obligatorio=False)
        f_fin = fecha_excel(v[fin], f"FECHA FIN {nombre.upper()}", obligatorio=False)

        if (f_ini is None) != (f_fin is None):
            raise ErrorDeValor(f"{nombre}: las fechas están incompletas (falta la de inicio o la de fin)")
        if f_ini is None:      # sin fechas
            if con_marca:
                raise ErrorDeValor(f"{nombre}: tiene la marca 'X' pero no tiene fechas")
            if dias_n > 0:
                raise ErrorDeValor(f"{nombre}: reporta {dias_n} día(s) pero no tiene fechas")
            return None
        if f_fin < f_ini:
            raise ErrorDeValor(f"{nombre}: la fecha de fin ({f_fin}) es anterior a la de inicio ({f_ini})")
        if dias_n == 0:
            raise ErrorDeValor(f"{nombre}: tiene fechas pero reporta 0 días")

        if not con_marca:
            avisos.append(f"sin_marca_{nombre}")
        if dias_n != (f_fin - f_ini).days + 1:
            avisos.append(f"dias_distintos_{nombre}")
        if not self._toca_el_mes(f_ini, f_fin):
            avisos.append(f"fuera_del_mes_{nombre}")
        return EventoLimpio(f_ini, f_fin, dias_n)

    def transformar(self, fila: FilaCruda) -> NovedadLimpia | Rechazo:
        v = fila.valores
        avisos: list[str] = []      # solo se registran si la fila se acepta
        try:
            codigo = entero(v["codigo"], "CÓDIGO", minimo=1)
            if codigo in self._vistos:
                raise ErrorDeValor(f"el código {codigo} tiene más de una fila de novedades en el archivo")
            incapacidad = self._evento(v, "incapacidad", "marca_incapacidad", "dias_incapacidad", "inc_inicio", "inc_fin", avisos)
            vacacion = self._evento(v, "vacaciones", "marca_vacaciones", "dias_vacaciones", "vac_inicio", "vac_fin", avisos)
            trabajados = entero(v["dias_trabajados"], "NUMERO DIAS TRABAJADOS EN EL MES", minimo=0, maximo=31)
            limpia = NovedadLimpia(
                codigo=codigo,
                bonificacion=dinero(v["bonificacion"], "BONIFICACIÓN"),
                transporte=dinero(v["transporte"], "TRANSPORTE"),
                incapacidad=incapacidad,
                vacacion=vacacion,
                fila=fila.numero,
                hoja=fila.hoja,
            )
        except ErrorDeValor as error:
            return Rechazo(fila.numero, str(error), _contenido(fila), fila.hoja)
        self._vistos.add(codigo)
        total = trabajados + (incapacidad.dias_reportados if incapacidad else 0) + (vacacion.dias_reportados if vacacion else 0)
        if total != DIAS_DEL_MES_LABORAL:
            avisos.append("suma_distinta_de_30")
        for categoria in avisos:
            self.avisos.setdefault(categoria, []).append(codigo)
        return limpia
