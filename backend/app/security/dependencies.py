"""Dependencias FastAPI para sesiones, CSRF, permisos y auditoría de reportes."""
import hmac
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.seguridad import SesionAuth, Usuario
from app.security.service import csrf_token_for, hash_token, record_audit, utc_now

_settings = get_settings()


@dataclass(frozen=True)
class AuthContext:
    user: Usuario
    session: SesionAuth
    session_token: str


def _session_cookie_name() -> str:
    return "__Host-entrecol_session" if _settings.cookie_secure else "entrecol_session"


def get_auth_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    token = request.cookies.get(_session_cookie_name())
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida.")
    session = db.get(SesionAuth, hash_token(token))
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida.")

    now = utc_now()
    idle_expiry = session.last_seen_at + timedelta(minutes=_settings.session_idle_timeout_minutes)
    if session.expires_at <= now or session.absolute_expires_at <= now or (
        session.state == "active" and idle_expiry <= now
    ):
        record_audit(
            db,
            request,
            event_type="session_expired",
            success=False,
            target_user_id=session.user_id,
        )
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión expirada.")

    user = db.get(Usuario, session.user_id)
    if user is None or not user.is_active:
        record_audit(
            db,
            request,
            event_type="inactive_account_session",
            success=False,
            target_user_id=session.user_id,
        )
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cuenta inactiva.")

    if session.state == "active":
        session.last_seen_at = now
        db.commit()
    return AuthContext(user=user, session=session, session_token=token)


def require_active_user(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if context.session.state != "active" or not context.user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación multifactor requerida.")
    return context


def require_admin(context: AuthContext = Depends(require_active_user)) -> AuthContext:
    if context.user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere el rol administrador.")
    return context


def require_csrf(
    request: Request,
    context: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    supplied = request.headers.get("x-csrf-token", "")
    expected = csrf_token_for(context.session_token)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token CSRF inválido.")
    return context


def require_admin_csrf(
    request: Request,
    context: AuthContext = Depends(require_admin),
) -> AuthContext:
    supplied = request.headers.get("x-csrf-token", "")
    expected = csrf_token_for(context.session_token)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token CSRF inválido.")
    return context


def audit_report_access(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    route = request.scope.get("route")
    resource = getattr(route, "path", request.url.path)
    try:
        context = get_auth_context(request, db)
    except HTTPException:
        record_audit(
            db,
            request,
            event_type="report_access_denied",
            success=False,
            resource=resource,
        )
        db.commit()
        raise
    if context.session.state != "active" or not context.user.totp_enabled:
        record_audit(
            db,
            request,
            event_type="report_access_denied",
            success=False,
            actor_user_id=context.user.id,
            target_user_id=context.user.id,
            resource=resource,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación multifactor requerida.",
        )
    record_audit(
        db,
        request,
        event_type="report_access",
        success=True,
        actor_user_id=context.user.id,
        resource=resource,
    )
    db.commit()


def log_access_denied(
    db: Session,
    request: Request,
    event_type: str,
    target_user_id: int | None = None,
) -> None:
    record_audit(
        db,
        request,
        event_type=event_type,
        success=False,
        target_user_id=target_user_id,
    )
