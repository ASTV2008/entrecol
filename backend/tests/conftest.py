"""Preparación común de las pruebas.

Las pruebas que escriben datos usan una base SEPARADA llamada <DB_NAME>_test
(por ejemplo entrecol_test), nunca la base real. Cada prueba corre dentro de una
transacción que se deshace al terminar, así no queda rastro entre pruebas.
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.core.config import get_settings
from app.db.base import Base


@pytest.fixture(scope="session")
def motor_pruebas():
    """Motor conectado a la base de pruebas, con las tablas creadas desde los modelos."""
    ajustes = get_settings()
    nombre = f"{ajustes.db_name}_test"
    motor = create_engine(ajustes.database_url.set(database=nombre), pool_pre_ping=True)
    try:
        with motor.connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except Exception as error:  # noqa: BLE001
        pytest.fail(
            f"No se pudo usar la base de pruebas '{nombre}': {error.__class__.__name__}. "
            "Debe existir y el usuario de la aplicación debe tener permisos sobre ella "
            "(la crea el script etapa7b.sh).",
            pytrace=False,
        )
    Base.metadata.drop_all(motor)
    Base.metadata.create_all(motor)
    yield motor
    Base.metadata.drop_all(motor)
    motor.dispose()


@pytest.fixture
def sesion(motor_pruebas):
    """Sesión aislada: todo lo que haga la prueba se deshace al terminar."""
    conexion = motor_pruebas.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    yield sesion
    sesion.close()
    transaccion.rollback()
    conexion.close()


@pytest.fixture
def cliente(sesion):
    """Cliente HTTP de la API real, pero conectado a la sesión de pruebas (se deshace al terminar)."""
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: sesion
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
