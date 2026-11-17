"""Consultas SQL de los reportes de nómina.

Esta es la ÚNICA capa que sabe cómo se llaman las tablas. Devuelve filas planas ya
ordenadas por la base de datos (que usa la colación utf8mb4_unicode_ci: ordena ignorando
tildes y mayúsculas, como espera un usuario hispanohablante). Agrupar y dar formato es
trabajo de los servicios.
"""
from collections.abc import Sequence
from typing import Literal

from sqlalchemy import Row, func, literal, select, tuple_, union_all
from sqlalchemy.orm import Session

from app.models import (
    Arl, Cargo, Dependencia, Empleado, Eps, FondoPension, Incapacidad, NovedadMensual, Periodo, Vacacion,
)
from app.schemas.reportes import Orden

TipoEntidad = Literal["eps", "pension"]

# Lista blanca: el usuario solo puede elegir una de estas claves, nunca un nombre de tabla arbitrario.
_ENTIDADES = {
    "eps": (Eps, Eps.id_eps, Eps.nombre, Empleado.id_eps),
    "pension": (FondoPension, FondoPension.id_fondo_pension, FondoPension.nombre, Empleado.id_fondo_pension),
}


def _sentido(columna, orden: Orden):
    return columna.asc() if orden is Orden.asc else columna.desc()


class RepositorioNomina:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------ listas de empleados
    def empleados(self, orden: Orden) -> Sequence[Row]:
        """(codigo, nombre) de todos los empleados."""
        consulta = select(Empleado.codigo, Empleado.nombre_empleado.label("nombre")).order_by(
            _sentido(Empleado.nombre_empleado, orden), Empleado.codigo
        )
        return self._db.execute(consulta).all()

    def empleados_por_dependencia(self, orden: Orden) -> Sequence[Row]:
        """(id_dependencia, dependencia, codigo, nombre): dependencia ascendente, nombres según `orden`."""
        consulta = (
            select(Dependencia.id_dependencia, Dependencia.nombre.label("dependencia"),
                   Empleado.codigo, Empleado.nombre_empleado.label("nombre"))
            .join(Cargo, Cargo.id_cargo == Empleado.id_cargo)
            .join(Dependencia, Dependencia.id_dependencia == Cargo.id_dependencia)
            .order_by(Dependencia.nombre, Dependencia.id_dependencia, _sentido(Empleado.nombre_empleado, orden), Empleado.codigo)
        )
        return self._db.execute(consulta).all()

    def empleados_por_cargo(self, orden: Orden) -> Sequence[Row]:
        """(id_dependencia, dependencia, id_cargo, cargo, codigo, nombre), dependencia y cargo ascendentes."""
        consulta = (
            select(
                Dependencia.id_dependencia, Dependencia.nombre.label("dependencia"),
                Cargo.id_cargo, Cargo.nombre.label("cargo"),
                Empleado.codigo, Empleado.nombre_empleado.label("nombre"),
            )
            .join(Cargo, Cargo.id_cargo == Empleado.id_cargo)
            .join(Dependencia, Dependencia.id_dependencia == Cargo.id_dependencia)
            .order_by(Dependencia.nombre, Dependencia.id_dependencia, Cargo.nombre, Cargo.id_cargo,
                      _sentido(Empleado.nombre_empleado, orden), Empleado.codigo)
        )
        return self._db.execute(consulta).all()

    def empleados_por_cargo_y_entidad(self, entidad: TipoEntidad, orden: Orden) -> Sequence[Row]:
        """(cargo, id_entidad, entidad, codigo, nombre). Cargo y entidad ascendentes.

        Se agrupa por NOMBRE de cargo (lectura literal del enunciado: 'por cargo y por EPS').
        """
        _, col_id, col_nombre, col_fk = _ENTIDADES[entidad]
        consulta = (
            select(
                Cargo.nombre.label("cargo"), col_id.label("id_entidad"), col_nombre.label("entidad"),
                Empleado.codigo, Empleado.nombre_empleado.label("nombre"),
            )
            .join(Cargo, Cargo.id_cargo == Empleado.id_cargo)
            .join(col_id.class_, col_id == col_fk)
            .order_by(Cargo.nombre, col_nombre, col_id, _sentido(Empleado.nombre_empleado, orden), Empleado.codigo)
        )
        return self._db.execute(consulta).all()

    # -------------------------------------------------------------------- conteos
    def conteo_por_dependencia(self) -> Sequence[Row]:
        """(dependencia, cantidad) solo de dependencias con empleados, ascendente."""
        consulta = (
            select(Dependencia.nombre.label("dependencia"), func.count(Empleado.codigo).label("cantidad"))
            .join(Cargo, Cargo.id_dependencia == Dependencia.id_dependencia)
            .join(Empleado, Empleado.id_cargo == Cargo.id_cargo)
            .group_by(Dependencia.id_dependencia, Dependencia.nombre)
            .order_by(Dependencia.nombre, Dependencia.id_dependencia)
        )
        return self._db.execute(consulta).all()

    def conteo_por_cargo(self) -> Sequence[Row]:
        """(dependencia, cargo, cantidad) de los cargos con empleados."""
        consulta = (
            select(Dependencia.nombre.label("dependencia"), Cargo.nombre.label("cargo"),
                   func.count(Empleado.codigo).label("cantidad"))
            .join(Cargo, Cargo.id_cargo == Empleado.id_cargo)
            .join(Dependencia, Dependencia.id_dependencia == Cargo.id_dependencia)
            .group_by(Dependencia.id_dependencia, Dependencia.nombre, Cargo.id_cargo, Cargo.nombre)
            .order_by(Dependencia.nombre, Dependencia.id_dependencia, Cargo.nombre, Cargo.id_cargo)
        )
        return self._db.execute(consulta).all()

    def conteo_por_entidad(self, entidad: TipoEntidad) -> Sequence[Row]:
        """(entidad, cantidad) para toda la empresa."""
        _, col_id, col_nombre, col_fk = _ENTIDADES[entidad]
        consulta = (
            select(col_nombre.label("entidad"), func.count(Empleado.codigo).label("cantidad"))
            .join(Empleado, col_fk == col_id)
            .group_by(col_id, col_nombre)
            .order_by(col_nombre, col_id)
        )
        return self._db.execute(consulta).all()

    def conteo_entidad_por_dependencia(self, entidad: TipoEntidad) -> Sequence[Row]:
        """(dependencia, entidad, cantidad)."""
        _, col_id, col_nombre, col_fk = _ENTIDADES[entidad]
        consulta = (
            select(Dependencia.nombre.label("dependencia"), col_nombre.label("entidad"),
                   func.count(Empleado.codigo).label("cantidad"))
            .join(Cargo, Cargo.id_cargo == Empleado.id_cargo)
            .join(Dependencia, Dependencia.id_dependencia == Cargo.id_dependencia)
            .join(col_id.class_, col_id == col_fk)
            .group_by(Dependencia.id_dependencia, Dependencia.nombre, col_id, col_nombre)
            .order_by(Dependencia.nombre, Dependencia.id_dependencia, col_nombre, col_id)
        )
        return self._db.execute(consulta).all()

    # ---------------------------------------------------------- información personal
    def fichas(self, orden: Orden, codigo: int | None = None) -> Sequence[Row]:
        consulta = (
            select(
                Empleado.codigo, Empleado.nombre_empleado.label("nombre"), Dependencia.nombre.label("dependencia"),
                Cargo.nombre.label("cargo"), Empleado.fecha_ingreso, Eps.nombre.label("eps"),
                FondoPension.nombre.label("fondo_pension"), Empleado.sueldo,
            )
            .join(Cargo, Cargo.id_cargo == Empleado.id_cargo)
            .join(Dependencia, Dependencia.id_dependencia == Cargo.id_dependencia)
            .join(Eps, Eps.id_eps == Empleado.id_eps)
            .join(FondoPension, FondoPension.id_fondo_pension == Empleado.id_fondo_pension)
            .order_by(_sentido(Empleado.nombre_empleado, orden), Empleado.codigo)
        )
        if codigo is not None:
            consulta = consulta.where(Empleado.codigo == codigo)
        return self._db.execute(consulta).all()

    def novedades_de(self, codigos: Sequence[int]) -> Sequence[Row]:
        """(codigo, id_novedad, anio, mes, bonificacion, transporte) de esos empleados, por periodo."""
        if not codigos:
            return []
        consulta = (
            select(NovedadMensual.codigo, NovedadMensual.id_novedad, Periodo.anio, Periodo.mes,
                   NovedadMensual.bonificacion, NovedadMensual.transporte)
            .join(Periodo, Periodo.id_periodo == NovedadMensual.id_periodo)
            .where(NovedadMensual.codigo.in_(codigos))
            .order_by(NovedadMensual.codigo, Periodo.anio, Periodo.mes)
        )
        return self._db.execute(consulta).all()

    def eventos_de(self, ids_novedad: Sequence[int]) -> Sequence[Row]:
        """(id_novedad, tipo, fecha_inicio, fecha_fin, dias) de incapacidades y vacaciones."""
        if not ids_novedad:
            return []
        filas: list[Row] = []
        for tipo, modelo in (("Incapacidad", Incapacidad), ("Vacaciones", Vacacion)):
            consulta = (
                select(modelo.id_novedad, literal(tipo).label("tipo"), modelo.fecha_inicio, modelo.fecha_fin,
                       modelo.dias_reportados.label("dias"))
                .where(modelo.id_novedad.in_(ids_novedad))
                .order_by(modelo.id_novedad, modelo.fecha_inicio)
            )
            filas.extend(self._db.execute(consulta).all())
        return filas

    # ------------------------------------------------------------------- novedades
    def eventos_en_rango(self, desde: tuple[int, int], hasta: tuple[int, int], orden: Orden) -> Sequence[Row]:
        """Incapacidades y vacaciones de los periodos entre desde y hasta (ambos (año, mes), inclusive).

        Devuelve (codigo, nombre, dependencia, cargo, tipo, anio, mes, fecha_inicio, fecha_fin, dias), con los
        nombres ordenados por la base (un UNION ALL evita ordenar en Python y perder la colación).
        """
        partes = []
        for tipo, modelo in (("Incapacidad", Incapacidad), ("Vacaciones", Vacacion)):
            partes.append(
                select(
                    Empleado.codigo.label("codigo"), Empleado.nombre_empleado.label("nombre"),
                    Dependencia.nombre.label("dependencia"), Cargo.nombre.label("cargo"),
                    literal(tipo).label("tipo"), Periodo.anio.label("anio"), Periodo.mes.label("mes"),
                    modelo.fecha_inicio.label("fecha_inicio"), modelo.fecha_fin.label("fecha_fin"),
                    modelo.dias_reportados.label("dias"),
                )
                .join(NovedadMensual, NovedadMensual.id_novedad == modelo.id_novedad)
                .join(Periodo, Periodo.id_periodo == NovedadMensual.id_periodo)
                .join(Empleado, Empleado.codigo == NovedadMensual.codigo)
                .join(Cargo, Cargo.id_cargo == Empleado.id_cargo)
                .join(Dependencia, Dependencia.id_dependencia == Cargo.id_dependencia)
                .where(tuple_(Periodo.anio, Periodo.mes) >= tuple_(*desde))
                .where(tuple_(Periodo.anio, Periodo.mes) <= tuple_(*hasta))
            )
        union = union_all(*partes).subquery("eventos")
        consulta = select(union).order_by(
            _sentido(union.c.nombre, orden), union.c.codigo, union.c.anio, union.c.mes, union.c.fecha_inicio, union.c.tipo
        )
        return self._db.execute(consulta).all()
