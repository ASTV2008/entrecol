"""Modelos para cuentas, sesiones revocables y auditoría de seguridad."""
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UInt


class Usuario(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'report_reader')", name="ck_app_user_role"),
        UniqueConstraint("email", name="uq_app_user_email"),
    )

    id: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="report_reader")
    is_active: Mapped[bool] = mapped_column(TINYINT(1), nullable=False, server_default="1")
    must_change_password: Mapped[bool] = mapped_column(TINYINT(1), nullable=False, server_default="0")
    totp_secret_encrypted: Mapped[str | None] = mapped_column(String(512))
    totp_enabled: Mapped[bool] = mapped_column(TINYINT(1), nullable=False, server_default="0")
    last_totp_step: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(6),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(6),
        onupdate=func.current_timestamp(6),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))


class SesionAuth(Base):
    __tablename__ = "auth_session"
    __table_args__ = (
        CheckConstraint(
            "state IN ('password_change', 'totp_setup', 'totp_required', 'active')",
            name="ck_auth_session_state",
        ),
        Index("ix_auth_session_user_expires", "user_id", "expires_at"),
    )

    token_hash: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        UInt, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False,
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(6),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(6),
    )
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)


class CodigoRecuperacion(Base):
    __tablename__ = "user_recovery_code"
    __table_args__ = (UniqueConstraint("code_hash", name="uq_user_recovery_code_hash"),)

    id: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        UInt, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(6),
    )
    used_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))


class EventoAuditoria(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_created", "created_at"),
        Index("ix_audit_event_actor_created", "actor_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        UInt, ForeignKey("app_user.id", ondelete="SET NULL"),
    )
    target_user_id: Mapped[int | None] = mapped_column(
        UInt, ForeignKey("app_user.id", ondelete="SET NULL"),
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(128))
    success: Mapped[bool] = mapped_column(TINYINT(1), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(6),
    )
