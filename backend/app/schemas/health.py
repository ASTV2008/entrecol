"""Esquemas (DTOs) del endpoint de salud: definen la forma exacta de la respuesta."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str    # "ok" o "degraded"
    database: str  # "up" o "down"
