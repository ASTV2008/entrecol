"""Contratos HTTP para la carga y consulta de archivos."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

TipoArchivo = Literal["nomina", "peliculas", "libros"]
EstadoCarga = Literal["succeeded", "failed"]


class CargaArchivoPublica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None
    usuario_email: str
    nombre_archivo: str
    tipo: TipoArchivo
    periodo: str | None
    tamano_bytes: int
    sha256: str
    estado: EstadoCarga
    filas_leidas: int
    filas_aceptadas: int
    filas_rechazadas: int
    mensaje: str | None
    fecha_carga: datetime


class RespuestaCargaArchivo(BaseModel):
    carga: CargaArchivoPublica
    informe: dict[str, Any]
