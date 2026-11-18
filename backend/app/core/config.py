"""Configuración central de la aplicación.

Todos los valores salen de variables de entorno (en Docker las inyecta
docker-compose desde el archivo .env). Así NO hay contraseñas en el código y
el mismo código funciona en desarrollo, pruebas y producción.
"""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Ajustes tipados. Si falta una variable obligatoria, la app no arranca
    y el error indica cuál (falla rápido en vez de fallar tarde)."""

    # Lee un .env local si existe (útil al correr fuera de Docker)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Entrecol API"
    app_version: str = "0.1.0"

    # Base de datos (obligatorias: no tienen valor por defecto)
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str

    # Clave de aplicación usada para derivar tokens CSRF
    secret_key: str
    totp_encryption_key: str

    # Sesiones: 30 minutos de inactividad y un máximo absoluto de 8 horas.
    session_idle_timeout_minutes: int = Field(default=30, ge=1, le=240)
    session_absolute_timeout_hours: int = Field(default=8, ge=1, le=24)
    audit_retention_days: int = Field(default=365, ge=30, le=3650)
    cookie_secure: bool = True

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_long_enough(cls, value: str) -> str:
        if len(value.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY debe contener al menos 32 bytes aleatorios.")
        return value

    @property
    def database_url(self) -> URL:
        """URL de conexión construida con URL.create para que caracteres
        especiales en la contraseña no rompan la cadena."""
        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de Settings (se lee el entorno una sola vez)."""
    return Settings()
