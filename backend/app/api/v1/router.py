"""Agrupa todos los routers de la versión 1 de la API."""
from fastapi import APIRouter

from app.api.v1 import health, reportes_entretenimiento, reportes_nomina

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(reportes_nomina.router)
api_router.include_router(reportes_entretenimiento.router)
