"""Modelos ORM del módulo ENTRETENIMIENTO (reflejan database/init/02_entretenimiento.sql)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Column, Date, ForeignKey, Index, Numeric, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UInt, USmallInt, UTinyInt

# ------------------------------------------------------------------- Películas
# Relación N:M película-género SIN atributos propios: basta una tabla de asociación.
pelicula_genero = Table(
    "pelicula_genero",
    Base.metadata,
    Column(
        "id_pelicula", UInt,
        ForeignKey("pelicula.id_pelicula", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True, autoincrement=False,
    ),
    Column(
        "id_genero", UTinyInt,
        ForeignKey("genero.id_genero", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True, autoincrement=False,
    ),
)


class Pelicula(Base):
    __tablename__ = "pelicula"
    __table_args__ = (Index("ix_pelicula_anio", "anio_estreno"),)

    id_pelicula: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=False)
    titulo: Mapped[str] = mapped_column(String(200))
    anio_estreno: Mapped[int] = mapped_column(USmallInt)

    generos: Mapped[list["Genero"]] = relationship(secondary=pelicula_genero, back_populates="peliculas")


class Genero(Base):
    __tablename__ = "genero"

    id_genero: Mapped[int] = mapped_column(UTinyInt, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True)

    peliculas: Mapped[list["Pelicula"]] = relationship(secondary=pelicula_genero, back_populates="generos")


# ---------------------------------------------------------------------- Libros
class Editorial(Base):
    __tablename__ = "editorial"

    id_editorial: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)

    libros: Mapped[list["Libro"]] = relationship(back_populates="editorial")


class Idioma(Base):
    __tablename__ = "idioma"

    id_idioma: Mapped[int] = mapped_column(UTinyInt, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(15), unique=True)

    libros: Mapped[list["Libro"]] = relationship(back_populates="idioma")


class Autor(Base):
    __tablename__ = "autor"

    id_autor: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)

    libros_asociados: Mapped[list["LibroAutor"]] = relationship(back_populates="autor")


class Libro(Base):
    """isbn/isbn13 NO son únicos (el origen trae un duplicado); la llave es id_libro."""

    __tablename__ = "libro"
    __table_args__ = (
        Index("ix_libro_calificacion", "calificacion_promedio"),
        Index("ix_libro_fecha_publicacion", "fecha_publicacion"),
    )

    id_libro: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=False)
    titulo: Mapped[str] = mapped_column(String(300))
    isbn: Mapped[str] = mapped_column(String(13))
    isbn13: Mapped[str] = mapped_column(String(13))
    num_paginas: Mapped[int] = mapped_column(USmallInt)
    fecha_publicacion: Mapped[date | None] = mapped_column(Date)  # NULL si el origen trae una fecha inválida
    calificacion_promedio: Mapped[Decimal] = mapped_column(Numeric(3, 2))
    num_calificaciones: Mapped[int] = mapped_column(UInt)
    num_resenas: Mapped[int] = mapped_column(UInt)
    id_editorial: Mapped[int] = mapped_column(
        UInt, ForeignKey("editorial.id_editorial", onupdate="CASCADE", ondelete="RESTRICT")
    )
    id_idioma: Mapped[int] = mapped_column(
        UTinyInt, ForeignKey("idioma.id_idioma", onupdate="CASCADE", ondelete="RESTRICT")
    )

    editorial: Mapped["Editorial"] = relationship(back_populates="libros")
    idioma: Mapped["Idioma"] = relationship(back_populates="libros")
    autores_asociados: Mapped[list["LibroAutor"]] = relationship(
        back_populates="libro",
        order_by="LibroAutor.orden_autoria",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class LibroAutor(Base):
    """Relación N:M libro-autor CON atributo propio (orden_autoria): por eso es una clase."""

    __tablename__ = "libro_autor"

    id_libro: Mapped[int] = mapped_column(
        UInt, ForeignKey("libro.id_libro", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True, autoincrement=False,
    )
    id_autor: Mapped[int] = mapped_column(
        UInt, ForeignKey("autor.id_autor", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True, autoincrement=False,
    )
    orden_autoria: Mapped[int] = mapped_column(UTinyInt)

    libro: Mapped["Libro"] = relationship(back_populates="autores_asociados")
    autor: Mapped["Autor"] = relationship(back_populates="libros_asociados")
