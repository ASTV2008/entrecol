"""Reporte 1 - NÓMINA: listas y conteos de empleados, y los dos gráficos pedidos."""
from itertools import groupby

from app.repositories.nomina import RepositorioNomina
from app.schemas.reportes import (
    EmpleadoItem, Grafico, GrupoCargo, GrupoDependencia, GrupoDependenciaCargos, ListaEmpleados, Orden,
    ReporteCargos, ReporteDependencias, Serie,
)


class ServicioReporteNomina:
    def __init__(self, repo: RepositorioNomina) -> None:
        self._repo = repo

    # a) cantidad y lista de empleados
    def lista_empleados(self, orden: Orden) -> ListaEmpleados:
        filas = self._repo.empleados(orden)
        return ListaEmpleados(total=len(filas), empleados=[EmpleadoItem(codigo=f.codigo, nombre=f.nombre) for f in filas])

    # b) por dependencia (dependencias ascendentes; nombres según el usuario)
    def por_dependencia(self, orden: Orden) -> ReporteDependencias:
        filas = self._repo.empleados_por_dependencia(orden)
        grupos = []
        for _, miembros in groupby(filas, key=lambda f: f.id_dependencia):
            miembros = list(miembros)
            grupos.append(GrupoDependencia(
                dependencia=miembros[0].dependencia, cantidad=len(miembros),
                empleados=[EmpleadoItem(codigo=f.codigo, nombre=f.nombre) for f in miembros],
            ))
        return ReporteDependencias(total=len(filas), dependencias=grupos)

    # c) por cargo por dependencia
    def por_cargo(self, orden: Orden) -> ReporteCargos:
        filas = self._repo.empleados_por_cargo(orden)
        dependencias = []
        for _, de_dependencia in groupby(filas, key=lambda f: f.id_dependencia):
            de_dependencia = list(de_dependencia)
            cargos = []
            for _, de_cargo in groupby(de_dependencia, key=lambda f: f.id_cargo):
                de_cargo = list(de_cargo)
                cargos.append(GrupoCargo(
                    cargo=de_cargo[0].cargo, cantidad=len(de_cargo),
                    empleados=[EmpleadoItem(codigo=f.codigo, nombre=f.nombre) for f in de_cargo],
                ))
            dependencias.append(GrupoDependenciaCargos(
                dependencia=de_dependencia[0].dependencia, cantidad=len(de_dependencia), cargos=cargos))
        return ReporteCargos(total=len(filas), dependencias=dependencias)

    # d) gráfico de torta: empleados por dependencia
    def grafico_dependencias(self) -> Grafico:
        filas = self._repo.conteo_por_dependencia()
        return Grafico(
            titulo="Empleados por dependencia", tipo="torta",
            etiquetas=[f.dependencia for f in filas],
            series=[Serie(nombre="Empleados", valores=[f.cantidad for f in filas])],
        )

    # e) barras comparativas: empleados por cargo, agrupados por su dependencia
    def grafico_cargos_por_dependencia(self) -> Grafico:
        filas = self._repo.conteo_por_cargo()
        return Grafico(
            titulo="Empleados por cargo y dependencia", tipo="barras",
            etiquetas=[f.cargo for f in filas],
            grupos=[f.dependencia for f in filas],
            series=[Serie(nombre="Empleados", valores=[f.cantidad for f in filas])],
        )
