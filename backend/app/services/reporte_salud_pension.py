"""Reporte 3 - SALUD y PENSIÓN: frecuencias por EPS y por fondo de pensión, y listas por cargo."""
from itertools import groupby

from app.repositories.nomina import RepositorioNomina, TipoEntidad
from app.services.texto import clave_texto
from app.schemas.reportes import (
    EmpleadoItem, Grafico, GrupoCargoEntidad, GrupoEntidad, Orden, ReporteCargoEntidad, Serie,
)

_ROTULO = {"eps": "EPS", "pension": "Pensión"}


class ServicioReporteSaludPension:
    def __init__(self, repo: RepositorioNomina) -> None:
        self._repo = repo

    # a / b) frecuencia por EPS / por fondo de pensión, toda la empresa
    def grafico_entidad(self, entidad: TipoEntidad) -> Grafico:
        filas = self._repo.conteo_por_entidad(entidad)
        return Grafico(
            titulo=f"Empleados por {_ROTULO[entidad]}", tipo="torta",
            etiquetas=[f.entidad for f in filas],
            series=[Serie(nombre="Empleados", valores=[f.cantidad for f in filas])],
        )

    # c / d) barras comparativas: una serie por EPS (o fondo), una etiqueta por dependencia
    def grafico_entidad_por_dependencia(self, entidad: TipoEntidad) -> Grafico:
        filas = self._repo.conteo_entidad_por_dependencia(entidad)
        dependencias = list(dict.fromkeys(f.dependencia for f in filas))        # ya vienen ascendentes
        entidades = sorted({f.entidad for f in filas}, key=clave_texto)
        cantidades = {(f.dependencia, f.entidad): f.cantidad for f in filas}
        return Grafico(
            titulo=f"Empleados por {_ROTULO[entidad]} y dependencia", tipo="barras", etiquetas=dependencias,
            series=[Serie(nombre=e, valores=[cantidades.get((d, e), 0) for d in dependencias]) for e in entidades],
        )

    # e / f) cantidad y lista de empleados por cargo y por EPS / pensión
    def por_cargo_y_entidad(self, entidad: TipoEntidad, orden: Orden) -> ReporteCargoEntidad:
        filas = self._repo.empleados_por_cargo_y_entidad(entidad, orden)
        cargos = []
        for nombre_cargo, de_cargo in groupby(filas, key=lambda f: clave_texto(f.cargo)):
            de_cargo = list(de_cargo)
            entidades = []
            for _, de_entidad in groupby(de_cargo, key=lambda f: f.id_entidad):
                de_entidad = list(de_entidad)
                entidades.append(GrupoEntidad(
                    entidad=de_entidad[0].entidad, cantidad=len(de_entidad),
                    empleados=[EmpleadoItem(codigo=f.codigo, nombre=f.nombre) for f in de_entidad]))
            cargos.append(GrupoCargoEntidad(cargo=de_cargo[0].cargo, cantidad=len(de_cargo), entidades=entidades))
        return ReporteCargoEntidad(total=len(filas), entidad_tipo=_ROTULO[entidad], cargos=cargos)
