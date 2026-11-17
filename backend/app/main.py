"""Punto de entrada de la aplicación FastAPI."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errores import ErrorDeParametro


def create_app() -> FastAPI:
    """Fábrica de la aplicación: facilita crear instancias distintas en las pruebas."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(api_router, prefix="/api/v1")

    @app.exception_handler(ErrorDeParametro)
    async def parametro_invalido(_: Request, error: ErrorDeParametro) -> JSONResponse:
        """Los servicios no conocen HTTP: aquí un parámetro inválido se vuelve un 422 con su explicación."""
        return JSONResponse(status_code=422, content={"detail": str(error)})

    return app


app = create_app()
