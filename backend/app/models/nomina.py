"""Modelos ORM del módulo NÓMINA (reflejan database/init/01_nomina.sql).

El DDL (los scripts .sql) es la fuente de verdad del esquema; estos modelos lo
describen para poder usarlo desde Python. tests/test_models_sync.py comprueba
que ambos coincidan, así un cambio en uno que olvide al otro se detecta.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UInt, USmallInt, UTinyInt


# --------------------------------------------------------------------- Catálogos
class Dependencia(Base):
    __tablename__ = "dependencia"

    id_dependencia: Mapped[int] = mapped_column(USmallInt, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)

    cargos: Mapped[list["Cargo"]] = relationship(back_populates="dependencia")


class Cargo(Base):
    """Entidad débil: su nombre solo es único dentro de una dependencia."""

    __tablename__ = "cargo"
    __table_args__ = (UniqueConstraint("id_dependencia", "nombre", name="uk_cargo_dependencia_nombre"),)

    id_cargo: Mapped[int] = mapped_column(USmallInt, primary_key=True, autoincrement=True)
    id_dependencia: Mapped[int] = mapped_column(
        USmallInt, ForeignKey("dependencia.id_dependencia", onupdate="CASCADE", ondelete="RESTRICT")
    )
    nombre: Mapped[str] = mapped_column(String(80))

    dependencia: Mapped["Dependencia"] = relationship(back_populates="cargos")
    empleados: Mapped[list["Empleado"]] = relationship(back_populates="cargo")


class Eps(Base):
    __tablename__ = "eps"

    id_eps: Mapped[int] = mapped_column(USmallInt, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)

    empleados: Mapped[list["Empleado"]] = relationship(back_populates="eps")


class Arl(Base):
    __tablename__ = "arl"

    id_arl: Mapped[int] = mapped_column(USmallInt, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)

    empleados: Mapped[list["Empleado"]] = relationship(back_populates="arl")


class FondoPension(Base):
    __tablename__ = "fondo_pension"

    id_fondo_pension: Mapped[int] = mapped_column(USmallInt, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)

    empleados: Mapped[list["Empleado"]] = relationship(back_populates="fondo_pension")


# ---------------------------------------------------------------------- Empleado
class Empleado(Base):
    """La llave es el código que entrega el cliente (no se autogenera)."""

    __tablename__ = "empleado"
    __table_args__ = (CheckConstraint("sueldo > 0", name="ck_empleado_sueldo"),)

    codigo: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=False)
    nombre_empleado: Mapped[str] = mapped_column(String(100))
    fecha_ingreso: Mapped[date] = mapped_column(Date)
    sueldo: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    id_cargo: Mapped[int] = mapped_column(
        USmallInt, ForeignKey("cargo.id_cargo", onupdate="CASCADE", ondelete="RESTRICT")
    )
    id_eps: Mapped[int] = mapped_column(
        USmallInt, ForeignKey("eps.id_eps", onupdate="CASCADE", ondelete="RESTRICT")
    )
    id_arl: Mapped[int] = mapped_column(
        USmallInt, ForeignKey("arl.id_arl", onupdate="CASCADE", ondelete="RESTRICT")
    )
    id_fondo_pension: Mapped[int] = mapped_column(
        USmallInt, ForeignKey("fondo_pension.id_fondo_pension", onupdate="CASCADE", ondelete="RESTRICT")
    )

    cargo: Mapped["Cargo"] = relationship(back_populates="empleados")
    eps: Mapped["Eps"] = relationship(back_populates="empleados")
    arl: Mapped["Arl"] = relationship(back_populates="empleados")
    fondo_pension: Mapped["FondoPension"] = relationship(back_populates="empleados")
    novedades: Mapped[list["NovedadMensual"]] = relationship(back_populates="empleado")


# --------------------------------------------------------------------- Novedades
class Periodo(Base):
    __tablename__ = "periodo"
    __table_args__ = (
        UniqueConstraint("anio", "mes", name="uk_periodo_anio_mes"),
        CheckConstraint("mes BETWEEN 1 AND 12", name="ck_periodo_mes"),
        CheckConstraint("anio BETWEEN 1990 AND 2100", name="ck_periodo_anio"),
    )

    id_periodo: Mapped[int] = mapped_column(USmallInt, primary_key=True, autoincrement=True)
    anio: Mapped[int] = mapped_column(USmallInt)
    mes: Mapped[int] = mapped_column(UTinyInt)

    novedades: Mapped[list["NovedadMensual"]] = relationship(back_populates="periodo")


class NovedadMensual(Base):
    """Una fila por empleado y mes. Los días trabajados NO se guardan: se derivan."""

    __tablename__ = "novedad_mensual"
    __table_args__ = (
        UniqueConstraint("codigo", "id_periodo", name="uk_novedad_empleado_periodo"),
        CheckConstraint("bonificacion >= 0", name="ck_novedad_bonificacion"),
        CheckConstraint("transporte >= 0", name="ck_novedad_transporte"),
    )

    id_novedad: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    codigo: Mapped[int] = mapped_column(
        UInt, ForeignKey("empleado.codigo", onupdate="CASCADE", ondelete="RESTRICT")
    )
    id_periodo: Mapped[int] = mapped_column(
        USmallInt, ForeignKey("periodo.id_periodo", onupdate="CASCADE", ondelete="RESTRICT")
    )
    bonificacion: Mapped[Decimal] = mapped_column(Numeric(14, 2), server_default="0")
    transporte: Mapped[Decimal] = mapped_column(Numeric(14, 2), server_default="0")

    empleado: Mapped["Empleado"] = relationship(back_populates="novedades")
    periodo: Mapped["Periodo"] = relationship(back_populates="novedades")
    incapacidades: Mapped[list["Incapacidad"]] = relationship(
        back_populates="novedad", cascade="all, delete-orphan", passive_deletes=True
    )
    vacaciones: Mapped[list["Vacacion"]] = relationship(
        back_populates="novedad", cascade="all, delete-orphan", passive_deletes=True
    )


class Incapacidad(Base):
    """dias_reportados se guarda como lo entrega el cliente (no siempre coincide con las fechas)."""

    __tablename__ = "incapacidad"
    __table_args__ = (
        UniqueConstraint("id_novedad", "fecha_inicio", name="uk_incapacidad_novedad_inicio"),
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_incapacidad_fechas"),
        CheckConstraint("dias_reportados BETWEEN 1 AND 31", name="ck_incapacidad_dias"),
    )

    id_incapacidad: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    id_novedad: Mapped[int] = mapped_column(
        UInt, ForeignKey("novedad_mensual.id_novedad", onupdate="CASCADE", ondelete="CASCADE")
    )
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    dias_reportados: Mapped[int] = mapped_column(UTinyInt)

    novedad: Mapped["NovedadMensual"] = relationship(back_populates="incapacidades")


class Vacacion(Base):
    __tablename__ = "vacacion"
    __table_args__ = (
        UniqueConstraint("id_novedad", "fecha_inicio", name="uk_vacacion_novedad_inicio"),
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_vacacion_fechas"),
        CheckConstraint("dias_reportados BETWEEN 1 AND 31", name="ck_vacacion_dias"),
    )

    id_vacacion: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    id_novedad: Mapped[int] = mapped_column(
        UInt, ForeignKey("novedad_mensual.id_novedad", onupdate="CASCADE", ondelete="CASCADE")
    )
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    dias_reportados: Mapped[int] = mapped_column(UTinyInt)

    novedad: Mapped["NovedadMensual"] = relationship(back_populates="vacaciones")
