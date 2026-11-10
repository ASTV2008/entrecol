"""Conexión a la base de datos y manejo de sesiones.

- engine: administra el pool de conexiones hacia MariaDB.
- SessionLocal: fábrica de sesiones (una por petición HTTP).
- get_db: dependencia de FastAPI que entrega una sesión y la cierra siempre.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # verifica que la conexión siga viva antes de usarla
    pool_recycle=1800,    # renueva conexiones cada 30 min (MariaDB cierra las inactivas)
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Entrega una sesión por petición y garantiza su cierre."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
