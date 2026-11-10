"""Endpoint de salud: sirve para saber si la API y la base de datos están vivas."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["Salud"])


@router.get("/health", response_model=HealthResponse, summary="Estado de la API y la base de datos")
def health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    database_up = HealthService(db).database_is_up()
    if not database_up:
        # 503 permite que Docker, balanceadores o monitores detecten el problema
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_up else "degraded",
        database="up" if database_up else "down",
    )
