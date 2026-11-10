"""Lógica de negocio del chequeo de salud (separada del router HTTP)."""
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class HealthService:
    """Verifica que los componentes de los que depende la API respondan."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def database_is_up(self) -> bool:
        """True si la base de datos contesta una consulta trivial."""
        try:
            self._db.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False
