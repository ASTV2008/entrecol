"""Inicio de sesión, MFA obligatorio y administración de cuentas."""
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.seguridad import CodigoRecuperacion, EventoAuditoria, SesionAuth, Usuario
from app.schemas.seguridad import (
    ActualizarUsuario, CambioPassword, Credenciales, EventoAuditoriaPublico,
    RespuestaCodigosRecuperacion, RespuestaSesion, UsuarioNuevo, UsuarioProvisionado,
    UsuarioPublico, VerificacionTotp,
)
from app.security.dependencies import (
    AuthContext, get_auth_context, require_admin, require_admin_csrf, require_csrf,
)
from app.security.service import (
    accept_totp_code, clear_session_cookie, consume_recovery_code, create_session,
    create_session_cookie, csrf_token_for, decrypt_totp_secret, generate_recovery_codes, hash_password,
    public_user, record_audit, totp_setup_details, utc_now, verify_password,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])
_settings = get_settings()
PREAUTH_COOKIE_SECONDS = 5 * 60


def _create_or_rotate_session(
    db: Session,
    response: Response,
    user: Usuario,
    state: str,
    old_session: SesionAuth | None = None,
) -> dict:
    if old_session is not None:
        db.delete(old_session)
    _, token, csrf_token = create_session(db, user, state)
    max_age = (
        PREAUTH_COOKIE_SECONDS
        if state != "active"
        else _settings.session_absolute_timeout_hours * 60 * 60
    )
    create_session_cookie(response, token, max_age)
    return {
        "state": state,
        "csrf_token": csrf_token,
        "user": public_user(user),
        "recovery_codes": None,
    }


def _registrar_fallo_login(db: Session, user: Usuario | None, request: Request) -> None:
    now = utc_now()
    if user is not None and user.is_active:
        user.failed_login_attempts = min(user.failed_login_attempts + 1, 5)
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
    record_audit(
        db,
        request,
        event_type="login_failed",
        success=False,
        target_user_id=user.id if user else None,
    )
    db.commit()


@router.post("/login", response_model=RespuestaSesion)
def login(
    credentials: Credenciales,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(credentials.email).casefold()
    user = db.scalar(select(Usuario).where(Usuario.email == email))
    password_ok = verify_password(credentials.password, user.password_hash if user else None)
    now = utc_now()
    locked = user is not None and user.locked_until is not None and user.locked_until > now
    if not password_ok or user is None or not user.is_active or locked:
        _registrar_fallo_login(db, user, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o cuenta temporalmente bloqueada.",
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    state = (
        "password_change" if user.must_change_password
        else "totp_required" if user.totp_enabled
        else "totp_setup"
    )
    result = _create_or_rotate_session(db, response, user, state)
    record_audit(
        db,
        request,
        event_type="login_password_accepted",
        success=True,
        target_user_id=user.id,
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/me", response_model=RespuestaSesion)
def session_info(response: Response, context: AuthContext = Depends(get_auth_context)):
    response.headers["Cache-Control"] = "no-store"
    return {
        "state": context.session.state,
        "csrf_token": csrf_token_for(context.session_token),
        "user": public_user(context.user),
        "recovery_codes": None,
    }


@router.post("/password/change", response_model=RespuestaSesion)
def change_password(
    payload: CambioPassword,
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    if context.session.state == "active":
        if not payload.current_password or not verify_password(
            payload.current_password, context.user.password_hash,
        ):
            record_audit(
                db,
                request,
                event_type="password_change_failed",
                success=False,
                actor_user_id=context.user.id,
                target_user_id=context.user.id,
            )
            db.commit()
            raise HTTPException(status_code=403, detail="La contraseña actual es incorrecta.")
        db.query(SesionAuth).filter(
            SesionAuth.user_id == context.user.id,
            SesionAuth.token_hash != context.session.token_hash,
        ).delete(synchronize_session=False)
        next_state = "active"
    elif context.session.state == "password_change":
        next_state = "totp_required" if context.user.totp_enabled else "totp_setup"
    else:
        raise HTTPException(status_code=409, detail="No hay un cambio de contraseña pendiente.")
    context.user.password_hash = hash_password(payload.new_password)
    context.user.must_change_password = False
    result = _create_or_rotate_session(db, response, context.user, next_state, context.session)
    record_audit(
        db,
        request,
        event_type="password_changed",
        success=True,
        actor_user_id=context.user.id,
        target_user_id=context.user.id,
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/totp/setup")
def totp_setup(
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    if context.session.state != "totp_setup":
        raise HTTPException(status_code=409, detail="No hay una configuración TOTP pendiente.")
    first_setup_request = context.user.totp_secret_encrypted is None
    try:
        details = totp_setup_details(context.user)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if first_setup_request:
        record_audit(
            db,
            request,
            event_type="totp_setup_started",
            success=True,
            actor_user_id=context.user.id,
            target_user_id=context.user.id,
        )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return details


@router.post("/totp/verify", response_model=RespuestaSesion)
def verify_totp(
    payload: VerificacionTotp,
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    if context.session.state not in {"totp_setup", "totp_required"}:
        raise HTTPException(status_code=409, detail="No hay una verificación TOTP pendiente.")

    user = context.user
    setup = context.session.state == "totp_setup"
    accepted = False
    recovery_used = False
    if setup:
        if user.totp_enabled or user.totp_secret_encrypted is None:
            raise HTTPException(status_code=409, detail="Primero solicita la configuración TOTP.")
        secret = decrypt_totp_secret(user.totp_secret_encrypted)
        accepted = accept_totp_code(db, user, secret, payload.code)
    elif user.totp_enabled and user.totp_secret_encrypted:
        secret = decrypt_totp_secret(user.totp_secret_encrypted)
        accepted = accept_totp_code(db, user, secret, payload.code)
        if not accepted:
            recovery_used = consume_recovery_code(db, user.id, payload.code)
            accepted = recovery_used

    if not accepted:
        user.failed_login_attempts = min(user.failed_login_attempts + 1, 5)
        if user.failed_login_attempts >= 5:
            user.locked_until = utc_now() + timedelta(minutes=15)
            db.query(SesionAuth).filter(SesionAuth.user_id == user.id).delete(
                synchronize_session=False,
            )
        record_audit(
            db,
            request,
            event_type="totp_failed",
            success=False,
            target_user_id=user.id,
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Código multifactor inválido o expirado.")

    recovery_codes = None
    if setup:
        user.totp_enabled = True
        recovery_codes = generate_recovery_codes(db, user.id)
        event_type = "totp_enrolled"
    else:
        event_type = "recovery_code_used" if recovery_used else "totp_verified"
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = utc_now()
    result = _create_or_rotate_session(db, response, user, "active", context.session)
    result["recovery_codes"] = recovery_codes
    record_audit(
        db,
        request,
        event_type=event_type,
        success=True,
        actor_user_id=user.id,
        target_user_id=user.id,
    )
    record_audit(
        db,
        request,
        event_type="login_success",
        success=True,
        actor_user_id=user.id,
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    record_audit(
        db,
        request,
        event_type="logout",
        success=True,
        actor_user_id=context.user.id,
    )
    db.delete(context.session)
    db.commit()
    clear_session_cookie(response)
    response.headers["Cache-Control"] = "no-store"


@router.post("/recovery-codes", response_model=RespuestaCodigosRecuperacion)
def rotate_recovery_codes(
    payload: VerificacionTotp,
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    if context.session.state != "active" or not context.user.totp_enabled:
        raise HTTPException(status_code=401, detail="Se requiere una sesión MFA activa.")
    if not context.user.totp_secret_encrypted or not accept_totp_code(
        db,
        context.user,
        decrypt_totp_secret(context.user.totp_secret_encrypted),
        payload.code,
    ):
        record_audit(
            db,
            request,
            event_type="recovery_codes_rotation_failed",
            success=False,
            actor_user_id=context.user.id,
            target_user_id=context.user.id,
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Código TOTP inválido o ya utilizado.")
    codes = generate_recovery_codes(db, context.user.id)
    record_audit(
        db,
        request,
        event_type="recovery_codes_rotated",
        success=True,
        actor_user_id=context.user.id,
        target_user_id=context.user.id,
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"recovery_codes": codes}


@router.get("/admin/users", response_model=list[UsuarioPublico])
def list_users(
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.scalars(select(Usuario).order_by(Usuario.email)).all()


@router.post("/admin/users", response_model=UsuarioProvisionado, status_code=201)
def create_user(
    payload: UsuarioNuevo,
    request: Request,
    context: AuthContext = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    if context.user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requiere el rol administrador.")
    temporary_password = secrets.token_urlsafe(24)
    user = Usuario(
        email=str(payload.email).casefold(),
        password_hash=hash_password(temporary_password),
        role=payload.role,
        is_active=True,
        must_change_password=True,
        totp_enabled=False,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.") from error
    record_audit(
        db,
        request,
        event_type="user_created",
        success=True,
        actor_user_id=context.user.id,
        target_user_id=user.id,
        resource=user.role,
    )
    db.commit()
    return {"user": public_user(user), "temporary_password": temporary_password}


@router.patch("/admin/users/{user_id}", response_model=UsuarioPublico)
def update_user(
    user_id: int,
    payload: ActualizarUsuario,
    request: Request,
    context: AuthContext = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    if context.user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requiere el rol administrador.")
    db.scalars(
        select(Usuario.id)
        .where(Usuario.role == "admin", Usuario.is_active.is_(True))
        .with_for_update()
    ).all()
    user = db.scalar(select(Usuario).where(Usuario.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    if user.id == context.user.id and (
        payload.is_active is False or payload.role == "report_reader"
    ):
        raise HTTPException(status_code=409, detail="No puedes desactivar ni degradar tu propia cuenta.")
    if not payload.model_fields_set:
        raise HTTPException(status_code=422, detail="Indica al menos un campo para actualizar.")

    requested_role = payload.role if "role" in payload.model_fields_set else user.role
    requested_active = payload.is_active if "is_active" in payload.model_fields_set else user.is_active
    if user.role == "admin" and user.is_active and (
        requested_role != "admin" or not requested_active
    ):
        active_admins = db.scalar(
            select(func.count()).select_from(Usuario).where(
                Usuario.role == "admin", Usuario.is_active.is_(True),
            )
        )
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="No se puede dejar el sistema sin un administrador activo.")

    old_role, old_active = user.role, user.is_active
    if "role" in payload.model_fields_set and payload.role is not None:
        user.role = payload.role
    if "is_active" in payload.model_fields_set and payload.is_active is not None:
        user.is_active = payload.is_active
    if old_role != user.role:
        record_audit(
            db, request, "user_role_changed", True, context.user.id, user.id, f"{old_role}->{user.role}",
        )
    if old_active != user.is_active:
        if not user.is_active:
            db.query(SesionAuth).filter(SesionAuth.user_id == user.id).delete(synchronize_session=False)
        record_audit(
            db,
            request,
            "user_deactivated" if not user.is_active else "user_activated",
            True,
            context.user.id,
            user.id,
        )
    db.commit()
    return public_user(user)


@router.post("/admin/users/{user_id}/reset-password", response_model=UsuarioProvisionado)
def reset_user_password(
    user_id: int,
    request: Request,
    context: AuthContext = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    if context.user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requiere el rol administrador.")
    user = db.get(Usuario, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    if user.id == context.user.id:
        raise HTTPException(status_code=409, detail="Usa el cambio de contraseña de tu propia sesión.")
    temporary_password = secrets.token_urlsafe(24)
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    db.query(SesionAuth).filter(SesionAuth.user_id == user.id).delete(synchronize_session=False)
    record_audit(
        db, request, "user_password_reset", True, context.user.id, user.id,
    )
    db.commit()
    return {"user": public_user(user), "temporary_password": temporary_password}


@router.post("/admin/users/{user_id}/reset-totp", response_model=UsuarioPublico)
def reset_user_totp(
    user_id: int,
    request: Request,
    context: AuthContext = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    user = db.get(Usuario, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    if user.id == context.user.id:
        raise HTTPException(status_code=409, detail="No puedes restablecer tu propio TOTP desde esta sesión.")
    user.totp_secret_encrypted = None
    user.totp_enabled = False
    user.last_totp_step = None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.query(CodigoRecuperacion).filter(CodigoRecuperacion.user_id == user.id).delete(
        synchronize_session=False,
    )
    db.query(SesionAuth).filter(SesionAuth.user_id == user.id).delete(synchronize_session=False)
    record_audit(
        db,
        request,
        event_type="user_totp_reset",
        success=True,
        actor_user_id=context.user.id,
        target_user_id=user.id,
    )
    db.commit()
    return public_user(user)


@router.get("/admin/audit", response_model=list[EventoAuditoriaPublico])
def list_audit_events(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    before_id: int | None = Query(default=None, ge=1),
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(EventoAuditoria).order_by(EventoAuditoria.id.desc()).limit(limit)
    if before_id is not None:
        query = query.where(EventoAuditoria.id < before_id)
    return db.scalars(query).all()


@router.get("/admin/audit/retention")
def audit_retention(_: AuthContext = Depends(require_admin)):
    return {"retention_days": _settings.audit_retention_days}
