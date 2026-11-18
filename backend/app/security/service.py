"""Funciones criptográficas y operaciones comunes de autenticación."""
import base64
import hashlib
import hmac
import io
import secrets
import time
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
from cryptography.fernet import Fernet
from pwdlib import PasswordHash
from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.seguridad import CodigoRecuperacion, EventoAuditoria, SesionAuth, Usuario

_password_hash = PasswordHash.recommended()
_dummy_password_hash = _password_hash.hash("constant-time-invalid-credential-placeholder")
_settings = get_settings()


def _fernet() -> Fernet:
    try:
        return Fernet(_settings.totp_encryption_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise RuntimeError("TOTP_ENCRYPTION_KEY debe ser una clave Fernet válida.") from error


_totp_cipher = _fernet()


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    candidate_hash = password_hash or _dummy_password_hash
    return _password_hash.verify(password, candidate_hash) and password_hash is not None


def encrypt_totp_secret(secret: str) -> str:
    return _totp_cipher.encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_totp_secret(encrypted: str) -> str:
    return _totp_cipher.decrypt(encrypted.encode("ascii")).decode("ascii")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def csrf_token_for(session_token: str) -> str:
    message = b"entrecol-csrf-v1:" + session_token.encode("ascii")
    return hmac.new(_settings.secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def create_session(db: Session, user: Usuario, state: str) -> tuple[SesionAuth, str, str]:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    if state == "active":
        absolute_expiry = now + timedelta(hours=_settings.session_absolute_timeout_hours)
        expiry = absolute_expiry
    else:
        expiry = now + timedelta(minutes=5)
        absolute_expiry = expiry
    session = SesionAuth(
        token_hash=hash_token(token),
        user_id=user.id,
        state=state,
        created_at=now,
        last_seen_at=now,
        expires_at=expiry,
        absolute_expires_at=absolute_expiry,
    )
    db.add(session)
    db.flush()
    return session, token, csrf_token_for(token)


def create_session_cookie(response, token: str, max_age: int) -> None:
    cookie_name = "__Host-entrecol_session" if _settings.cookie_secure else "entrecol_session"
    response.set_cookie(
        key=cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=_settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response) -> None:
    cookie_name = "__Host-entrecol_session" if _settings.cookie_secure else "entrecol_session"
    response.delete_cookie(
        key=cookie_name,
        httponly=True,
        secure=_settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def totp_setup_details(user: Usuario) -> dict[str, str]:
    if user.totp_enabled:
        raise ValueError("La cuenta ya tiene TOTP configurado.")
    if user.totp_secret_encrypted is None:
        secret = pyotp.random_base32()
        user.totp_secret_encrypted = encrypt_totp_secret(secret)
    else:
        secret = decrypt_totp_secret(user.totp_secret_encrypted)
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Entrecol")
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {
        "secret": secret,
        "otpauth_url": uri,
        "qr_png_data_url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
    }


def matching_totp_step(secret: str, code: str, last_step: int | None) -> int | None:
    normalized_code = code.strip().replace(" ", "")
    if len(normalized_code) != 6 or not normalized_code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    current_step = int(time.time()) // totp.interval
    for step in (current_step - 1, current_step, current_step + 1):
        if step > (last_step if last_step is not None else -1) and hmac.compare_digest(
            totp.generate_otp(step), normalized_code,
        ):
            return step
    return None


def accept_totp_code(db: Session, user: Usuario, secret: str, code: str) -> bool:
    step = matching_totp_step(secret, code, user.last_totp_step)
    if step is None:
        return False
    result = db.execute(
        update(Usuario)
        .where(
            Usuario.id == user.id,
            or_(Usuario.last_totp_step.is_(None), Usuario.last_totp_step < step),
        )
        .values(last_totp_step=step)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return False
    db.refresh(user)
    return True


def _recovery_code_hash(code: str) -> str:
    normalized = code.strip().replace("-", "").replace(" ", "").upper()
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()


def consume_recovery_code(db: Session, user_id: int, code: str) -> bool:
    try:
        digest = _recovery_code_hash(code)
    except UnicodeEncodeError:
        return False
    now = utc_now()
    result = db.execute(
        update(CodigoRecuperacion)
        .where(
            CodigoRecuperacion.user_id == user_id,
            CodigoRecuperacion.code_hash == digest,
            CodigoRecuperacion.used_at.is_(None),
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def generate_recovery_codes(db: Session, user_id: int, amount: int = 10) -> list[str]:
    db.query(CodigoRecuperacion).filter(CodigoRecuperacion.user_id == user_id).delete(
        synchronize_session=False,
    )
    codes = []
    for _ in range(amount):
        raw = secrets.token_hex(12).upper()
        formatted = "-".join(raw[index:index + 4] for index in range(0, len(raw), 4))
        codes.append(formatted)
        db.add(
            CodigoRecuperacion(
                user_id=user_id,
                code_hash=_recovery_code_hash(formatted),
                created_at=utc_now(),
            )
        )
    return codes


def record_audit(
    db: Session,
    request,
    event_type: str,
    success: bool,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    resource: str | None = None,
) -> None:
    client = request.client
    user_agent = request.headers.get("user-agent")
    db.add(
        EventoAuditoria(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            event_type=event_type,
            resource=resource[:128] if resource else None,
            success=success,
            ip_address=client.host[:45] if client else None,
            user_agent=user_agent[:255] if user_agent else None,
            created_at=utc_now(),
        )
    )


def public_user(user: Usuario) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "totp_enabled": user.totp_enabled,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


