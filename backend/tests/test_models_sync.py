"""Comprueba que los modelos ORM coinciden con la base de datos REAL.

El esquema nace de los scripts SQL (database/init). Si alguien cambia un script
y olvida el modelo (o al revés), estas pruebas fallan y dicen exactamente qué
tabla y columna difieren. Solo LEEN la base: no insertan ni modifican nada.
"""
import re

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, configure_mappers

import app.models  # noqa: F401  (importarlo registra todos los modelos en Base.metadata)
from app.db.base import Base
from app.db.session import engine

TABLAS = sorted(Base.metadata.tables)


@pytest.fixture(scope="module")
def inspector():
    return inspect(engine)


def _normalizar_tipo(tipo) -> str:
    """Pasa un tipo a texto comparable (la base y el modelo lo escriben distinto)."""
    texto = str(tipo.compile(dialect=engine.dialect)).upper()
    texto = re.sub(r"\s+CHARACTER SET \S+", "", texto)
    texto = re.sub(r"\s+COLLATE \S+", "", texto)
    texto = re.sub(r"^(INTEGER|SMALLINT|TINYINT|BIGINT)\(\d+\)", r"\1", texto)  # ancho de pantalla
    return texto.replace("NUMERIC", "DECIMAL")


def test_las_tablas_son_las_mismas(inspector):
    en_bd = set(inspector.get_table_names())
    en_modelos = set(Base.metadata.tables)
    assert en_modelos == en_bd, f"Solo en modelos: {en_modelos - en_bd} | Solo en BD: {en_bd - en_modelos}"


@pytest.mark.parametrize("tabla", TABLAS)
def test_columnas_tipos_y_nulabilidad(inspector, tabla):
    modelo = {c.name: (_normalizar_tipo(c.type), c.nullable) for c in Base.metadata.tables[tabla].columns}
    real = {c["name"]: (_normalizar_tipo(c["type"]), c["nullable"]) for c in inspector.get_columns(tabla)}
    assert modelo == real, f"Tabla {tabla}: modelo={modelo} | bd={real}"


@pytest.mark.parametrize("tabla", TABLAS)
def test_llave_primaria(inspector, tabla):
    modelo = {c.name for c in Base.metadata.tables[tabla].primary_key.columns}
    real = set(inspector.get_pk_constraint(tabla)["constrained_columns"])
    assert modelo == real, f"Tabla {tabla}: modelo={modelo} | bd={real}"


@pytest.mark.parametrize("tabla", TABLAS)
def test_llaves_foraneas(inspector, tabla):
    modelo = {
        (tuple(sorted(c.name for c in fk.columns)), fk.referred_table.name)
        for fk in Base.metadata.tables[tabla].foreign_key_constraints
    }
    real = {
        (tuple(sorted(fk["constrained_columns"])), fk["referred_table"])
        for fk in inspector.get_foreign_keys(tabla)
    }
    assert modelo == real, f"Tabla {tabla}: modelo={modelo} | bd={real}"


@pytest.mark.parametrize("tabla", TABLAS)
def test_restricciones_unicas(inspector, tabla):
    from sqlalchemy import UniqueConstraint

    modelo = {
        tuple(sorted(c.name for c in uc.columns))
        for uc in Base.metadata.tables[tabla].constraints
        if isinstance(uc, UniqueConstraint)
    }
    real = {tuple(sorted(uc["column_names"])) for uc in inspector.get_unique_constraints(tabla)}
    assert modelo == real, f"Tabla {tabla}: modelo={modelo} | bd={real}"


def test_las_relaciones_entre_modelos_estan_bien_definidas():
    configure_mappers()  # lanza error si algún relationship() está mal escrito


@pytest.mark.parametrize("mapper", list(Base.registry.mappers), ids=lambda m: m.class_.__name__)
def test_cada_modelo_puede_consultar_su_tabla(mapper):
    """Un SELECT de TODAS las columnas mapeadas: falla si alguna no existe en la BD."""
    with Session(engine) as sesion:
        sesion.execute(select(mapper.class_).limit(1)).all()
