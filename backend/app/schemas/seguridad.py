"""Contratos HTTP para autenticación, cuentas y auditoría."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

Role = Literal["admin", "report_reader"]
LoginState = Literal["password_change", "totp_setup", "totp_required", "active"]


class Credenciales(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.strip().casefold()


class CambioPassword(BaseModel):
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def passwords_coinciden(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Las contraseñas no coinciden.")
        return self


class VerificacionTotp(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class UsuarioPublico(BaseModel):
    id: int
    email: str
    role: Role
    is_active: bool
    must_change_password: bool
    totp_enabled: bool
    created_at: datetime
    last_login_at: datetime | None


class RespuestaSesion(BaseModel):
    state: LoginState
    csrf_token: str
    user: UsuarioPublico | None = None
    recovery_codes: list[str] | None = None


class RespuestaCodigosRecuperacion(BaseModel):
    recovery_codes: list[str]


class UsuarioNuevo(BaseModel):
    email: EmailStr
    role: Role = "report_reader"

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.strip().casefold()


class ActualizarUsuario(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class UsuarioProvisionado(BaseModel):
    user: UsuarioPublico
    temporary_password: str


class EventoAuditoriaPublico(BaseModel):
    id: int
    actor_user_id: int | None
    target_user_id: int | None
    event_type: str
    resource: str | None
    success: bool
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
