"""Carga autenticada de archivos de datos usando los ETL existentes."""
import hashlib
import io
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.etl.common import ErrorDeArchivo, InformeCarga
from app.etl.libros.service import cargar_libros
from app.etl.nomina.service import PeriodoNomina, cargar_nomina
from app.etl.peliculas.service import cargar_peliculas
from app.models.cargas import CargaArchivo
from app.schemas.cargas import RespuestaCargaArchivo, TipoArchivo, CargaArchivoPublica
from app.security.dependencies import AuthContext, require_admin, require_admin_csrf
from app.security.service import record_audit, utc_now

router = APIRouter(prefix="/cargas", tags=["Carga de archivos"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
EXTENSIONES = {"nomina": ".xlsx", "peliculas": ".dat", "libros": ".json"}


def _cargar_etl(
    tipo: TipoArchivo,
    contenido: bytes,
    db: Session,
    periodo: PeriodoNomina | None,
) -> InformeCarga:
    flujo = io.BytesIO(contenido)
    if tipo == "nomina":
        if periodo is None:
            raise RuntimeError("La carga de nómina requiere un período validado.")
        return cargar_nomina(flujo, db, periodo)
    if tipo == "peliculas":
        return cargar_peliculas(flujo, db)
    return cargar_libros(flujo, db)


def _guardar_registro(
    db: Session,
    request: Request,
    context: AuthContext,
    *,
    tipo: TipoArchivo,
    nombre_archivo: str,
    periodo: str | None,
    tamano_bytes: int,
    sha256: str,
    estado: str,
    informe: InformeCarga | None = None,
    mensaje: str | None = None,
) -> CargaArchivo:
    carga = CargaArchivo(
        usuario_id=context.user.id,
        usuario_email=context.user.email,
        nombre_archivo=nombre_archivo,
        tipo=tipo,
        periodo=periodo,
        tamano_bytes=tamano_bytes,
        sha256=sha256,
        estado=estado,
        filas_leidas=informe.leidas if informe else 0,
        filas_aceptadas=informe.aceptadas if informe else 0,
        filas_rechazadas=informe.rechazadas if informe else 0,
        mensaje=mensaje[:512] if mensaje else None,
        fecha_carga=utc_now(),
    )
    db.add(carga)
    db.flush()
    record_audit(
        db,
        request,
        event_type="file_upload_succeeded" if estado == "succeeded" else "file_upload_failed",
        success=estado == "succeeded",
        actor_user_id=context.user.id,
        resource=tipo,
    )
    db.commit()
    return carga


@router.post(
    "",
    response_model=RespuestaCargaArchivo,
    status_code=status.HTTP_201_CREATED,
)
def subir_archivo(
    request: Request,
    tipo: Annotated[TipoArchivo, Form()],
    archivo: Annotated[UploadFile, File()],
    context: Annotated[AuthContext, Depends(require_admin_csrf)],
    db: Annotated[Session, Depends(get_db)],
    periodo: Annotated[str | None, Form()] = None,
) -> RespuestaCargaArchivo:
    nombre_original = (archivo.filename or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    nombre_archivo = "".join(caracter for caracter in nombre_original if caracter.isprintable())
    if not nombre_archivo or len(nombre_archivo) > 255:
        raise HTTPException(status_code=422, detail="El nombre del archivo no es válido.")
    if PurePosixPath(nombre_archivo).suffix.casefold() != EXTENSIONES[tipo]:
        raise HTTPException(
            status_code=422,
            detail=f"El tipo {tipo} requiere un archivo {EXTENSIONES[tipo]}.",
        )

    periodo_nomina = None
    periodo_guardado = None
    if tipo == "nomina":
        if not periodo:
            raise HTTPException(status_code=422, detail="La carga de nómina requiere el período AAAA-MM.")
        try:
            periodo_nomina = PeriodoNomina.desde_texto(periodo)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        periodo_guardado = f"{periodo_nomina.anio:04d}-{periodo_nomina.mes:02d}"
    elif periodo:
        raise HTTPException(status_code=422, detail="El período solo se usa al cargar nómina.")

    if archivo.size is not None and archivo.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 20 MiB.")
    contenido = archivo.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contenido) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 20 MiB.")
    digest = hashlib.sha256(contenido).hexdigest()

    try:
        informe = _cargar_etl(tipo, contenido, db, periodo_nomina)
    except ErrorDeArchivo as error:
        db.rollback()
        _guardar_registro(
            db,
            request,
            context,
            tipo=tipo,
            nombre_archivo=nombre_archivo,
            periodo=periodo_guardado,
            tamano_bytes=len(contenido),
            sha256=digest,
            estado="failed",
            mensaje=str(error),
        )
        raise HTTPException(status_code=422, detail=str(error)) from error

    carga = _guardar_registro(
        db,
        request,
        context,
        tipo=tipo,
        nombre_archivo=nombre_archivo,
        periodo=periodo_guardado,
        tamano_bytes=len(contenido),
        sha256=digest,
        estado="succeeded",
        informe=informe,
    )
    return RespuestaCargaArchivo(carga=carga, informe=informe.a_dict())


@router.get("", response_model=list[CargaArchivoPublica])
def listar_cargas(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[CargaArchivo]:
    return list(db.scalars(
        select(CargaArchivo)
        .order_by(CargaArchivo.fecha_carga.desc(), CargaArchivo.id.desc())
        .limit(limit),
    ))
