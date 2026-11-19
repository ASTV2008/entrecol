from datetime import datetime, timezone
import hashlib
import time

import pyotp
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.seguridad import CodigoRecuperacion, EventoAuditoria, Usuario
from app.security import cli
from app.security.service import (
    decrypt_totp_secret, encrypt_totp_secret, generate_recovery_codes, hash_password,
    verify_password,
)


def crear_usuario(
    sesion,
    email="admin@example.org",
    password="Correct Horse Battery 42!",
    role="admin",
    totp_secret=None,
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    usuario = Usuario(
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        must_change_password=False,
        totp_secret_encrypted=encrypt_totp_secret(totp_secret) if totp_secret else None,
        totp_enabled=totp_secret is not None,
        created_at=now,
        updated_at=now,
    )
    sesion.add(usuario)
    sesion.flush()
    return usuario


def completar_configuracion_totp(cliente, email, password):
    login = cliente.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    result = login.json()
    assert result["state"] == "totp_setup"
    setup = cliente.get("/api/v1/auth/totp/setup")
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    verify = cliente.post(
        "/api/v1/auth/totp/verify",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": result["csrf_token"]},
    )
    assert verify.status_code == 200
    assert verify.json()["state"] == "active"
    return verify.json()


def test_reportes_json_y_pdf_requieren_sesion(cliente_sin_auth, sesion):
    for path in (
        "/api/v1/reportes/nomina/empleados",
        "/api/v1/reportes/nomina/empleados/pdf",
        "/api/v1/reportes/entretenimiento/libros/top?n=1",
    ):
        response = cliente_sin_auth.get(path)
        assert response.status_code == 401
    denied = list(sesion.scalars(
        select(EventoAuditoria).where(EventoAuditoria.event_type == "report_access_denied")
    ))
    assert len(denied) == 3


def test_login_exige_totp_cifra_semilla_y_entrega_codigos_una_vez(
    cliente_sin_auth, sesion,
):
    usuario = crear_usuario(sesion)
    assert usuario.password_hash.startswith("$argon2id$")
    response = cliente_sin_auth.post(
        "/api/v1/auth/login",
        json={"email": usuario.email, "password": "Correct Horse Battery 42!"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "totp_setup"
    assert "__Host-entrecol_session" in response.headers["set-cookie"]
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "secure" in response.headers["set-cookie"].lower()

    setup = cliente_sin_auth.get("/api/v1/auth/totp/setup")
    assert setup.status_code == 200
    details = setup.json()
    assert details["qr_png_data_url"].startswith("data:image/png;base64,")
    sesion.refresh(usuario)
    assert details["secret"] not in usuario.totp_secret_encrypted
    assert decrypt_totp_secret(usuario.totp_secret_encrypted) == details["secret"]

    verified = cliente_sin_auth.post(
        "/api/v1/auth/totp/verify",
        json={"code": pyotp.TOTP(details["secret"]).now()},
        headers={"X-CSRF-Token": response.json()["csrf_token"]},
    )
    assert verified.status_code == 200
    assert verified.json()["state"] == "active"
    recovery_codes = verified.json()["recovery_codes"]
    assert len(recovery_codes) == 10
    recovery_hashes = {row.code_hash for row in sesion.scalars(select(CodigoRecuperacion))}
    assert len(recovery_hashes) == 10
    assert all(code.replace("-", "").lower() not in recovery_hashes for code in recovery_codes)
    event_types = set(sesion.scalars(select(EventoAuditoria.event_type)))
    assert {"login_password_accepted", "totp_enrolled", "login_success"} <= event_types
    assert all(details["secret"] not in event.resource for event in sesion.scalars(
        select(EventoAuditoria).where(EventoAuditoria.resource.is_not(None))
    ))


def test_totp_replay_is_rejected_and_recovery_code_is_single_use(
    cliente_sin_auth, sesion,
):
    usuario = crear_usuario(sesion)
    active = completar_configuracion_totp(
        cliente_sin_auth, usuario.email, "Correct Horse Battery 42!",
    )
    recovery_code = active["recovery_codes"][0]
    logout = cliente_sin_auth.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": active["csrf_token"]},
    )
    assert logout.status_code == 204

    login = cliente_sin_auth.post(
        "/api/v1/auth/login",
        json={"email": usuario.email, "password": "Correct Horse Battery 42!"},
    )
    replay = cliente_sin_auth.post(
        "/api/v1/auth/totp/verify",
        json={
            "code": pyotp.TOTP(decrypt_totp_secret(usuario.totp_secret_encrypted)).generate_otp(
                usuario.last_totp_step,
            ),
        },
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
    )
    assert replay.status_code == 401

    recovered = cliente_sin_auth.post(
        "/api/v1/auth/totp/verify",
        json={"code": recovery_code},
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
    )
    assert recovered.status_code == 200
    assert recovered.json()["state"] == "active"

    cliente_sin_auth.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": recovered.json()["csrf_token"]},
    )
    login_again = cliente_sin_auth.post(
        "/api/v1/auth/login",
        json={"email": usuario.email, "password": "Correct Horse Battery 42!"},
    )
    reused = cliente_sin_auth.post(
        "/api/v1/auth/totp/verify",
        json={"code": recovery_code},
        headers={"X-CSRF-Token": login_again.json()["csrf_token"]},
    )
    assert reused.status_code == 401


def test_admin_crea_usuarios_y_no_puede_quedar_sin_admin(
    cliente_sin_auth, sesion,
):
    admin = crear_usuario(sesion)
    active = completar_configuracion_totp(
        cliente_sin_auth, admin.email, "Correct Horse Battery 42!",
    )
    headers = {"X-CSRF-Token": active["csrf_token"]}

    no_csrf = cliente_sin_auth.post(
        "/api/v1/auth/admin/users",
        json={"email": "lector@example.org", "role": "report_reader"},
    )
    assert no_csrf.status_code == 403

    created = cliente_sin_auth.post(
        "/api/v1/auth/admin/users",
        json={"email": "lector@example.org", "role": "report_reader"},
        headers=headers,
    )
    assert created.status_code == 201
    provisioned = created.json()
    assert provisioned["user"]["must_change_password"] is True
    assert len(provisioned["temporary_password"]) >= 24
    assert "password_hash" not in provisioned["user"]

    self_disable = cliente_sin_auth.patch(
        f"/api/v1/auth/admin/users/{admin.id}",
        json={"is_active": False},
        headers=headers,
    )
    assert self_disable.status_code == 409
    assert cliente_sin_auth.get("/api/v1/auth/admin/users").status_code == 200

    cliente_sin_auth.post("/api/v1/auth/logout", headers=headers)
    user_login = cliente_sin_auth.post(
        "/api/v1/auth/login",
        json={
            "email": provisioned["user"]["email"],
            "password": provisioned["temporary_password"],
        },
    )
    assert user_login.status_code == 200
    assert user_login.json()["state"] == "password_change"
    password_change = cliente_sin_auth.post(
        "/api/v1/auth/password/change",
        json={
            "new_password": "New Secure Password 37!",
            "confirm_password": "New Secure Password 37!",
        },
        headers={"X-CSRF-Token": user_login.json()["csrf_token"]},
    )
    assert password_change.status_code == 200
    assert password_change.json()["state"] == "totp_setup"
    assert cliente_sin_auth.get("/api/v1/auth/totp/setup").status_code == 200


def test_lector_no_puede_administrar_usuarios(cliente_sin_auth, sesion):
    secret = pyotp.random_base32()
    reader = crear_usuario(
        sesion,
        email="reader@example.org",
        role="report_reader",
        totp_secret=secret,
    )
    login = cliente_sin_auth.post(
        "/api/v1/auth/login",
        json={"email": reader.email, "password": "Correct Horse Battery 42!"},
    )
    assert login.json()["state"] == "totp_required"
    verified = cliente_sin_auth.post(
        "/api/v1/auth/totp/verify",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
    )
    assert verified.status_code == 200
    assert cliente_sin_auth.get("/api/v1/auth/admin/users").status_code == 403
    assert cliente_sin_auth.get("/api/v1/reportes/nomina/empleados").status_code == 200
    assert sesion.scalar(
        select(EventoAuditoria.id).where(
            EventoAuditoria.event_type == "report_access",
            EventoAuditoria.actor_user_id == reader.id,
        )
    ) is not None


def test_codigos_recuperacion_se_renuevan_con_un_totp_no_reutilizado(
    cliente_sin_auth, sesion,
):
    user = crear_usuario(sesion)
    active = completar_configuracion_totp(
        cliente_sin_auth, user.email, "Correct Horse Battery 42!",
    )
    old_code = active["recovery_codes"][0]
    secret = decrypt_totp_secret(user.totp_secret_encrypted)
    current_step = int(time.time()) // 30
    next_code = pyotp.TOTP(secret).generate_otp(current_step + 1)

    rotated = cliente_sin_auth.post(
        "/api/v1/auth/recovery-codes",
        json={"code": next_code},
        headers={"X-CSRF-Token": active["csrf_token"]},
    )
    assert rotated.status_code == 200
    new_codes = rotated.json()["recovery_codes"]
    assert len(new_codes) == 10
    old_digest = hashlib.sha256(old_code.replace("-", "").upper().encode()).hexdigest()
    recovery_hashes = {row.code_hash for row in sesion.scalars(select(CodigoRecuperacion))}
    assert len(recovery_hashes) == 10
    assert old_digest not in recovery_hashes


def test_admin_puede_reiniciar_totp_de_otra_cuenta(cliente_sin_auth, sesion):
    admin = crear_usuario(sesion)
    old_secret = pyotp.random_base32()
    reader = crear_usuario(
        sesion,
        email="reset-me@example.org",
        role="report_reader",
        totp_secret=old_secret,
    )
    generate_recovery_codes(sesion, reader.id)
    active = completar_configuracion_totp(
        cliente_sin_auth, admin.email, "Correct Horse Battery 42!",
    )
    reset = cliente_sin_auth.post(
        f"/api/v1/auth/admin/users/{reader.id}/reset-totp",
        headers={"X-CSRF-Token": active["csrf_token"]},
    )
    assert reset.status_code == 200
    assert reset.json()["totp_enabled"] is False
    assert reader.totp_secret_encrypted is None
    assert sesion.scalar(
        select(CodigoRecuperacion.id).where(CodigoRecuperacion.user_id == reader.id)
    ) is None

    cliente_sin_auth.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": active["csrf_token"]},
    )
    login = cliente_sin_auth.post(
        "/api/v1/auth/login",
        json={"email": reader.email, "password": "Correct Horse Battery 42!"},
    )
    assert login.status_code == 200
    assert login.json()["state"] == "totp_setup"
    setup = cliente_sin_auth.get("/api/v1/auth/totp/setup")
    assert setup.status_code == 200
    assert setup.json()["secret"] != old_secret


def test_cli_restablece_password_y_revoca_sesiones(sesion, monkeypatch, capsys):
    usuario = crear_usuario(sesion)
    monkeypatch.setattr(
        cli,
        "SessionLocal",
        lambda: Session(bind=sesion.get_bind(), join_transaction_mode="create_savepoint"),
    )

    cli.reset_password(usuario.email, True)

    output = capsys.readouterr().out
    temporary_password = next(
        line.split(": ", 1)[1]
        for line in output.splitlines()
        if line.startswith("Contraseña temporal:")
    )
    assert usuario.must_change_password is True
    assert verify_password(temporary_password, usuario.password_hash)
