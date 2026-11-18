import hashlib
import json
from datetime import datetime, timezone

import pyotp
import pytest
from sqlalchemy import func, select

from app.api.v1 import cargas
from app.models import CargaArchivo, Libro, Pelicula
from app.models.seguridad import EventoAuditoria, Usuario
from app.security.service import encrypt_totp_secret, hash_password
from excel_nomina import empleado, libro_excel, novedad


def _autenticar(cliente, sesion, role="admin"):
    secret = pyotp.random_base32()
    usuario = Usuario(
        email=f"{role}@example.org",
        password_hash=hash_password("Correct Horse Battery 42!"),
        role=role,
        is_active=True,
        must_change_password=False,
        totp_secret_encrypted=encrypt_totp_secret(secret),
        totp_enabled=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    sesion.add(usuario)
    sesion.flush()

    login = cliente.post(
        "/api/v1/auth/login",
        json={"email": usuario.email, "password": "Correct Horse Battery 42!"},
    )
    assert login.status_code == 200
    verified = cliente.post(
        "/api/v1/auth/totp/verify",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
    )
    assert verified.status_code == 200
    return usuario, {"X-CSRF-Token": verified.json()["csrf_token"]}


def _archivo(tipo):
    if tipo == "peliculas":
        return "movies.dat", b"1::Toy Story (1995)::Animation|Comedy\n", None
    if tipo == "libros":
        datos = [{
            "bookID": 1, "title": "Libro de prueba", "authors": "Autora Uno",
            "average_rating": "4.10", "isbn": "0439785960", "isbn13": "9780439785969",
            "language_code": "spa", "num_pages": "100", "ratings_count": 10,
            "text_reviews_count": 2, "publication_date": "1/2/2003", "publisher": "Editorial X",
            "FIELD13": "",
        }]
        return "Books.json", json.dumps(datos, ensure_ascii=False).encode(), None
    datos_nomina = libro_excel([empleado(5401)], [novedad(5401)])
    return "Nomina.xlsx", datos_nomina.getvalue(), "2022-03"


def _contar(sesion, modelo):
    return sesion.scalar(select(func.count()).select_from(modelo))


@pytest.mark.parametrize("tipo", ["peliculas", "libros", "nomina"])
def test_admin_carga_los_tres_tipos_con_el_etl_existente_y_consulta_historial(
    cliente_sin_auth, sesion, tipo,
):
    usuario, headers = _autenticar(cliente_sin_auth, sesion)
    nombre, contenido, periodo = _archivo(tipo)
    datos = {"tipo": tipo}
    if periodo:
        datos["periodo"] = periodo

    response = cliente_sin_auth.post(
        "/api/v1/cargas",
        data=datos,
        files={"archivo": (nombre, contenido)},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["carga"]["usuario_email"] == usuario.email
    assert body["carga"]["nombre_archivo"] == nombre
    assert body["carga"]["tipo"] == tipo
    assert body["carga"]["estado"] == "succeeded"
    assert body["carga"]["sha256"] == hashlib.sha256(contenido).hexdigest()
    assert body["informe"]["leidas"] > 0

    history = cliente_sin_auth.get("/api/v1/cargas")
    assert history.status_code == 200
    assert history.json()[0]["id"] == body["carga"]["id"]
    assert sesion.scalar(select(CargaArchivo)).usuario_id == usuario.id
    if tipo == "peliculas":
        assert _contar(sesion, Pelicula) == 1
    elif tipo == "libros":
        assert _contar(sesion, Libro) == 1
    assert sesion.scalar(
        select(func.count()).select_from(EventoAuditoria).where(
            EventoAuditoria.event_type == "file_upload_succeeded",
        ),
    ) == 1


def test_archivo_invalido_no_deja_datos_y_registra_fallo(cliente_sin_auth, sesion):
    _autenticar(cliente_sin_auth, sesion)
    response = cliente_sin_auth.post(
        "/api/v1/cargas",
        data={"tipo": "peliculas"},
        files={"archivo": ("movies.dat", b"\xff")},
        headers={"X-CSRF-Token": _csrf_token(cliente_sin_auth)},
    )

    assert response.status_code == 422
    assert _contar(sesion, Pelicula) == 0
    carga = sesion.scalar(select(CargaArchivo))
    assert carga.estado == "failed"
    assert carga.mensaje
    assert sesion.scalar(
        select(func.count()).select_from(EventoAuditoria).where(
            EventoAuditoria.event_type == "file_upload_failed",
        ),
    ) == 1


def _csrf_token(cliente):
    response = cliente.get("/api/v1/auth/me")
    return response.json()["csrf_token"]


def test_lector_no_puede_cargar_y_admin_necesita_csrf(cliente_sin_auth, sesion):
    _autenticar(cliente_sin_auth, sesion)
    nombre, contenido, _ = _archivo("peliculas")
    sin_csrf = cliente_sin_auth.post(
        "/api/v1/cargas",
        data={"tipo": "peliculas"},
        files={"archivo": (nombre, contenido)},
    )
    assert sin_csrf.status_code == 403

    cliente_sin_auth.post("/api/v1/auth/logout", headers={"X-CSRF-Token": _csrf_token(cliente_sin_auth)})
    _, headers = _autenticar(cliente_sin_auth, sesion, role="report_reader")
    denegado = cliente_sin_auth.post(
        "/api/v1/cargas",
        data={"tipo": "peliculas"},
        files={"archivo": (nombre, contenido)},
        headers=headers,
    )
    assert denegado.status_code == 403
    assert _contar(sesion, CargaArchivo) == 0


def test_rechaza_archivo_mayor_al_limite(cliente_sin_auth, sesion, monkeypatch):
    _autenticar(cliente_sin_auth, sesion)
    monkeypatch.setattr(cargas, "MAX_UPLOAD_BYTES", 3)
    response = cliente_sin_auth.post(
        "/api/v1/cargas",
        data={"tipo": "peliculas"},
        files={"archivo": ("movies.dat", b"1234")},
        headers={"X-CSRF-Token": _csrf_token(cliente_sin_auth)},
    )

    assert response.status_code == 413
    assert _contar(sesion, CargaArchivo) == 0
