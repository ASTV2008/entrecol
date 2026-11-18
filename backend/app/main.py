"""Punto de entrada de la aplicación FastAPI."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errores import ErrorDeParametro


def create_app() -> FastAPI:
    """Fábrica de la aplicación: facilita crear instancias distintas en las pruebas."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(api_router, prefix="/api/v1")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith(("/api/v1/auth", "/api/v1/reportes", "/api/v1/cargas")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ErrorDeParametro)
    async def parametro_invalido(_: Request, error: ErrorDeParametro) -> JSONResponse:
        """Los servicios no conocen HTTP: aquí un parámetro inválido se vuelve un 422 con su explicación."""
        return JSONResponse(status_code=422, content={"detail": str(error)})

    directorios_frontend = (Path("/frontend"), Path(__file__).resolve().parents[2] / "frontend")
    for directorio in directorios_frontend:
        if directorio.is_dir():
            app.mount("/", StaticFiles(directory=directorio, html=True), name="frontend")
            break

    return app


app = create_app()
