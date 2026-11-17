"""Orquesta el ETL de nómina: extraer -> transformar -> verificar empleados -> cargar -> informe.

El Excel NO dice a qué mes pertenecen las novedades, por eso el periodo es un parámetro.
"""
import re
from dataclasses import dataclass
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.etl.common import ErrorDeArchivo, InformeCarga, Rechazo
from app.etl.nomina.extractor import leer_nomina
from app.etl.nomina.loader import CargadorNomina
from app.etl.nomina.transformer import EmpleadoLimpio, NovedadLimpia, TransformadorEmpleados, TransformadorNovedades
from app.models import Empleado

_AVISOS = {
    "dias_distintos_incapacidad": "{n} incapacidad(es) reportan un número de días distinto al de sus fechas; se conservó el valor reportado (código {ej}).",
    "dias_distintos_vacaciones": "{n} vacación(es) reportan un número de días distinto al de sus fechas; se conservó el valor reportado (código {ej}).",
    "fuera_del_mes_incapacidad": "{n} incapacidad(es) no tocan el mes {mes}; se cargaron igual (código {ej}).",
    "fuera_del_mes_vacaciones": "{n} vacación(es) no tocan el mes {mes}; se cargaron igual (código {ej}).",
    "sin_marca_incapacidad": "{n} incapacidad(es) tienen fechas pero no la marca 'X'; se cargaron igual (código {ej}).",
    "sin_marca_vacaciones": "{n} vacación(es) tienen fechas pero no la marca 'X'; se cargaron igual (código {ej}).",
    "suma_distinta_de_30": "{n} empleado(s) cuyos días trabajados + incapacidad + vacaciones no suman 30 (código {ej}).",
}


@dataclass(frozen=True)
class PeriodoNomina:
    anio: int
    mes: int

    def __post_init__(self) -> None:
        if not (1990 <= self.anio <= 2100 and 1 <= self.mes <= 12):
            raise ValueError(f"Periodo inválido: {self.mes}/{self.anio} (mes 1-12, año 1990-2100)")

    @classmethod
    def desde_texto(cls, texto: str) -> "PeriodoNomina":
        """Interpreta 'AAAA-MM' (por ejemplo '2022-03')."""
        coincide = re.fullmatch(r"(\d{4})-(\d{1,2})", texto.strip())
        if not coincide:
            raise ValueError(f"Periodo inválido: '{texto}'. Use el formato AAAA-MM, por ejemplo 2022-03.")
        return cls(int(coincide.group(1)), int(coincide.group(2)))

    def __str__(self) -> str:
        return f"{self.mes:02d}/{self.anio}"


def _ejemplos(codigos: list[int], cuantos: int = 5) -> str:
    unicos = list(dict.fromkeys(codigos))
    return ", ".join(str(c) for c in unicos[:cuantos]) + (", ..." if len(unicos) > cuantos else "")


def cargar_nomina(flujo: BinaryIO, sesion: Session, periodo: PeriodoNomina) -> InformeCarga:
    """Carga un Nomina.xlsx para el periodo dado. NO hace commit: lo decide quien llama.

    Lanza ErrorDeArchivo si el archivo completo no sirve. Las filas malas individuales
    se descartan y quedan en el informe con su motivo.
    """
    informe = InformeCarga(fuente=f"Nomina.xlsx (nómina, periodo {periodo})", unidad_fila="fila")
    lectura = leer_nomina(flujo)
    informe.leidas = len(lectura.empleados) + len(lectura.novedades)
    if informe.leidas == 0:
        raise ErrorDeArchivo("El archivo no contiene ninguna fila de empleados ni de novedades.")

    t_emp = TransformadorEmpleados()
    empleados: list[EmpleadoLimpio] = []
    for fila in lectura.empleados:
        resultado = t_emp.transformar(fila)
        (informe.rechazos if isinstance(resultado, Rechazo) else empleados).append(resultado)

    t_nov = TransformadorNovedades(periodo.anio, periodo.mes)
    novedades: list[NovedadLimpia] = []
    for fila in lectura.novedades:
        resultado = t_nov.transformar(fila)
        (informe.rechazos if isinstance(resultado, Rechazo) else novedades).append(resultado)

    # Una novedad necesita un empleado: del mismo archivo o ya guardado en la base.
    codigos_archivo = {e.codigo for e in empleados}
    pendientes = {n.codigo for n in novedades} - codigos_archivo
    en_base = set(sesion.execute(select(Empleado.codigo).where(Empleado.codigo.in_(pendientes))).scalars()) if pendientes else set()
    existentes = codigos_archivo | en_base
    validas: list[NovedadLimpia] = []
    for n in novedades:
        if n.codigo in existentes:
            validas.append(n)
        else:
            informe.rechazos.append(Rechazo(n.fila, f"el empleado {n.codigo} no existe (ni en el archivo ni en la base)", f"codigo={n.codigo}", n.hoja))
    informe.rechazos.sort(key=lambda r: (r.origen, r.linea))

    if not empleados and not validas:
        raise ErrorDeArchivo("Ninguna fila es válida. ¿Es realmente el archivo Nomina.xlsx?")
    informe.aceptadas = len(empleados) + len(validas)

    cargado = CargadorNomina(sesion, periodo.anio, periodo.mes).cargar(empleados, validas)
    informe.nuevas, informe.actualizadas, informe.sin_cambios = cargado.nuevas, cargado.actualizadas, cargado.sin_cambios

    informe.detalles["Empleados aceptados"] = len(empleados)
    informe.detalles["Novedades aceptadas"] = len(validas)
    informe.detalles["Dependencias nuevas"] = cargado.dependencias.nuevos if cargado.dependencias else 0
    informe.detalles["Cargos nuevos"] = cargado.cargos.nuevos if cargado.cargos else 0
    informe.detalles["EPS nuevas"] = cargado.eps.nuevos if cargado.eps else 0
    informe.detalles["ARL nuevas"] = cargado.arl.nuevos if cargado.arl else 0
    informe.detalles["Fondos de pensión nuevos"] = cargado.fondos.nuevos if cargado.fondos else 0
    informe.detalles["Incapacidades"] = cargado.incapacidades
    informe.detalles["Vacaciones"] = cargado.vacaciones

    aceptados = {n.codigo for n in validas}
    for categoria, plantilla in _AVISOS.items():
        codigos = [c for c in t_nov.avisos.get(categoria, []) if c in aceptados]
        if codigos:
            informe.advertencias.append(plantilla.format(n=len(codigos), ej=_ejemplos(codigos), mes=str(periodo)))
    if informe.rechazadas > informe.aceptadas:
        informe.advertencias.append("Se rechazaron más filas de las que se aceptaron: revise el archivo.")
    return informe
