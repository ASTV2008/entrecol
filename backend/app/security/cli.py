"""Comandos de operación segura para bootstrap y retención de auditoría."""
import argparse
import getpass
import secrets
from datetime import timedelta

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.seguridad import CodigoRecuperacion, EventoAuditoria, SesionAuth, Usuario
from app.security.service import hash_password, utc_now


def create_admin() -> None:
    email_input = input("Correo del primer administrador: ").strip()
    try:
        email = validate_email(email_input, check_deliverability=False).normalized.casefold()
    except EmailNotValidError as error:
        raise SystemExit(f"Correo inválido: {error}") from error

    password = getpass.getpass("Contraseña inicial (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirma la contraseña: ")
    if not 12 <= len(password) <= 128:
        raise SystemExit("La contraseña debe tener entre 12 y 128 caracteres.")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")

    with SessionLocal.begin() as db:
        existing_admin = db.scalar(
            select(Usuario.id).where(Usuario.role == "admin", Usuario.is_active.is_(True)).limit(1)
        )
        if existing_admin is not None:
            raise SystemExit("Ya existe un administrador activo; no se creó otra cuenta inicial.")
        if db.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
            raise SystemExit("Ya existe una cuenta con ese correo.")
        now = utc_now()
        user = Usuario(
            email=email,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
            must_change_password=False,
            totp_enabled=False,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()
        db.add(
            EventoAuditoria(
                target_user_id=user.id,
                event_type="admin_bootstrapped",
                success=True,
                created_at=now,
            )
        )
    print("Administrador creado. En el primer inicio de sesión deberá configurar TOTP.")


def purge_audit(confirm: bool) -> None:
    if not confirm:
        raise SystemExit("La purga requiere --confirm; se eliminarán eventos anteriores a la retención configurada.")
    settings = get_settings()
    cutoff = utc_now() - timedelta(days=settings.audit_retention_days)
    with SessionLocal.begin() as db:
        deleted = db.execute(delete(EventoAuditoria).where(EventoAuditoria.created_at < cutoff)).rowcount
        db.add(
            EventoAuditoria(
                event_type="audit_retention_purge",
                success=True,
                resource=f"deleted={deleted};retention_days={settings.audit_retention_days}",
                created_at=utc_now(),
            )
        )
    print(f"Se eliminaron {deleted} eventos anteriores al período de retención.")


def reset_password(email_input: str, confirm: bool) -> None:
    if not confirm:
        raise SystemExit("El restablecimiento requiere --confirm.")
    try:
        email = validate_email(email_input, check_deliverability=False).normalized.casefold()
    except EmailNotValidError as error:
        raise SystemExit(f"Correo inválido: {error}") from error
    temporary_password = secrets.token_urlsafe(24)
    with SessionLocal.begin() as db:
        user = db.scalar(select(Usuario).where(Usuario.email == email).with_for_update())
        if user is None:
            raise SystemExit("No existe una cuenta con ese correo.")
        user.password_hash = hash_password(temporary_password)
        user.must_change_password = True
        user.failed_login_attempts = 0
        user.locked_until = None
        db.query(SesionAuth).filter(SesionAuth.user_id == user.id).delete(synchronize_session=False)
        db.add(
            EventoAuditoria(
                target_user_id=user.id,
                event_type="user_password_reset",
                success=True,
                resource="local_cli",
                created_at=utc_now(),
            )
        )
    print("Contraseña restablecida.")
    print(f"Contraseña temporal: {temporary_password}")
    print("El usuario deberá reemplazarla al iniciar sesión.")


def reset_totp(email_input: str, confirm: bool) -> None:
    if not confirm:
        raise SystemExit("El restablecimiento requiere --confirm.")
    try:
        email = validate_email(email_input, check_deliverability=False).normalized.casefold()
    except EmailNotValidError as error:
        raise SystemExit(f"Correo inválido: {error}") from error
    with SessionLocal.begin() as db:
        user = db.scalar(select(Usuario).where(Usuario.email == email).with_for_update())
        if user is None:
            raise SystemExit("No existe una cuenta con ese correo.")
        user.totp_secret_encrypted = None
        user.totp_enabled = False
        user.last_totp_step = None
        user.failed_login_attempts = 0
        user.locked_until = None
        db.query(CodigoRecuperacion).filter(CodigoRecuperacion.user_id == user.id).delete(
            synchronize_session=False,
        )
        db.query(SesionAuth).filter(SesionAuth.user_id == user.id).delete(synchronize_session=False)
        db.add(
            EventoAuditoria(
                target_user_id=user.id,
                event_type="user_totp_reset",
                success=True,
                resource="local_cli",
                created_at=utc_now(),
            )
        )
    print("TOTP restablecido. La cuenta deberá enrolar un nuevo autenticador al volver a iniciar sesión.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Operaciones de seguridad de Entrecol")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("create-admin", help="Crear el primer administrador de forma interactiva")
    purge = commands.add_parser("purge-audit", help="Eliminar auditoría vencida")
    purge.add_argument("--confirm", action="store_true", help="Confirmar la eliminación de registros vencidos")
    reset_password_parser = commands.add_parser("reset-password", help="Restablecer la contraseña de una cuenta")
    reset_password_parser.add_argument("--email", required=True, help="Correo exacto de la cuenta")
    reset_password_parser.add_argument("--confirm", action="store_true", help="Confirmar el restablecimiento")
    reset = commands.add_parser("reset-totp", help="Restablecer MFA de una cuenta bloqueada")
    reset.add_argument("--email", required=True, help="Correo exacto de la cuenta")
    reset.add_argument("--confirm", action="store_true", help="Confirmar el restablecimiento")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin()
    elif args.command == "purge-audit":
        purge_audit(args.confirm)
    elif args.command == "reset-password":
        reset_password(args.email, args.confirm)
    elif args.command == "reset-totp":
        reset_totp(args.email, args.confirm)


if __name__ == "__main__":
    main()
