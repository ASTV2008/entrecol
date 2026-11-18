"""Modelo del historial de cargas de archivos."""
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UInt


class CargaArchivo(Base):
    __tablename__ = "carga_archivo"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('nomina', 'peliculas', 'libros')",
            name="ck_carga_archivo_tipo",
        ),
        CheckConstraint(
            "estado IN ('succeeded', 'failed')",
            name="ck_carga_archivo_estado",
        ),
        Index("ix_carga_archivo_fecha", "fecha_carga"),
        Index("ix_carga_archivo_usuario_fecha", "usuario_id", "fecha_carga"),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    usuario_id: Mapped[int | None] = mapped_column(
        UInt, ForeignKey("app_user.id", ondelete="SET NULL"),
    )
    usuario_email: Mapped[str] = mapped_column(String(254), nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    periodo: Mapped[str | None] = mapped_column(CHAR(7))
    tamano_bytes: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False)
    filas_leidas: Mapped[int] = mapped_column(UInt, nullable=False, server_default="0")
    filas_aceptadas: Mapped[int] = mapped_column(UInt, nullable=False, server_default="0")
    filas_rechazadas: Mapped[int] = mapped_column(UInt, nullable=False, server_default="0")
    mensaje: Mapped[str | None] = mapped_column(String(512))
    fecha_carga: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(6),
    )
