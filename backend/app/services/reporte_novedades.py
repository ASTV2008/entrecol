"""Reporte 4 - NOVEDADES: empleados con incapacidades o vacaciones en un rango de periodos MM/AAAA."""
from itertools import groupby

from app.repositories.nomina import RepositorioNomina
from app.schemas.reportes import (
    ConteoCargo, ConteoDependencia, EmpleadoConNovedades, EventoDetalle, Orden, ReporteNovedades, ResumenNovedades,
)
from app.services.periodos import leer_rango, texto_periodo
from app.services.reporte_personal import formato_fecha
from app.services.texto import clave_texto


class ServicioReporteNovedades:
    """Una 'novedad' es una incapacidad o unas vacaciones (las columnas NOVEDAD ... del Excel).

    Pertenece al PERIODO de nómina con el que se cargó, no a las fechas del evento: es el dato
    que reporta el cliente y el rango pedido es de periodos (MM/AAAA).
    """

    def __init__(self, repo: RepositorioNomina) -> None:
        self._repo = repo

    # a) lista de empleados con novedades entre F1 y F2
    def empleados(self, desde: str, hasta: str, orden: Orden) -> ReporteNovedades:
        inicio, fin = leer_rango(desde, hasta)
        filas = self._repo.eventos_en_rango(inicio, fin, orden)
        empleados = []
        for _, eventos in groupby(filas, key=lambda f: f.codigo):
            eventos = list(eventos)
            primero = eventos[0]
            empleados.append(EmpleadoConNovedades(
                codigo=primero.codigo, nombre=primero.nombre, dependencia=primero.dependencia, cargo=primero.cargo,
                novedades=[EventoDetalle(
                    tipo=e.tipo, periodo=texto_periodo(e.anio, e.mes), fecha_inicio=formato_fecha(e.fecha_inicio),
                    fecha_fin=formato_fecha(e.fecha_fin), dias=e.dias) for e in eventos]))
        return ReporteNovedades(desde=desde, hasta=hasta, total=len(empleados), empleados=empleados)

    # b) cantidad de empleados con novedades, por dependencia y por cargo
    def resumen(self, desde: str, hasta: str) -> ResumenNovedades:
        inicio, fin = leer_rango(desde, hasta)
        filas = self._repo.eventos_en_rango(inicio, fin, Orden.asc)
        # Un empleado cuenta UNA vez aunque tenga varias novedades.
        unicos = {f.codigo: (f.dependencia, f.cargo) for f in filas}
        por_dep: dict[str, dict[str, int]] = {}
        for dependencia, cargo in unicos.values():
            por_dep.setdefault(dependencia, {}).setdefault(cargo, 0)
            por_dep[dependencia][cargo] += 1
        dependencias = [
            ConteoDependencia(
                dependencia=d, cantidad=sum(c.values()),
                cargos=[ConteoCargo(cargo=nombre, cantidad=n) for nombre, n in sorted(c.items(), key=lambda x: clave_texto(x[0]))])
            for d, c in sorted(por_dep.items(), key=lambda x: clave_texto(x[0]))
        ]
        return ResumenNovedades(desde=desde, hasta=hasta, total=len(unicos), dependencias=dependencias)
