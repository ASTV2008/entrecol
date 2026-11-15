"""Orquesta el ETL de películas: extraer -> transformar -> cargar -> informe."""
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.etl.common import ErrorDeArchivo, InformeCarga, Rechazo
from app.etl.peliculas.extractor import leer_lineas
from app.etl.peliculas.loader import CargadorPeliculas
from app.etl.peliculas.transformer import PeliculaLimpia, TransformadorPeliculas

FUENTE = "movies.dat (películas)"


def cargar_peliculas(flujo: BinaryIO, sesion: Session) -> InformeCarga:
    """Carga un archivo movies.dat. NO hace commit: lo decide quien llama.

    Lanza ErrorDeArchivo si el archivo completo no sirve (vacío, mal codificado
    o sin ninguna fila válida). Las filas malas individuales NO detienen la carga:
    se descartan y quedan en el informe con su motivo.
    """
    informe = InformeCarga(fuente=FUENTE)
    transformador = TransformadorPeliculas()
    limpias: list[PeliculaLimpia] = []

    for linea in leer_lineas(flujo):
        informe.leidas += 1
        resultado = transformador.transformar(linea)
        if isinstance(resultado, Rechazo):
            informe.rechazos.append(resultado)
        else:
            limpias.append(resultado)

    if informe.leidas == 0:
        raise ErrorDeArchivo("El archivo está vacío o solo tiene líneas en blanco.")
    if not limpias:
        raise ErrorDeArchivo("Ninguna fila es válida. ¿Es realmente el archivo movies.dat?")
    informe.aceptadas = len(limpias)

    resultado = CargadorPeliculas(sesion).cargar(limpias)
    informe.nuevas = resultado.nuevas
    informe.actualizadas = resultado.actualizadas
    informe.sin_cambios = resultado.sin_cambios
    informe.detalles["Géneros nuevos"] = resultado.generos_nuevos
    informe.detalles["Películas sin géneros"] = sum(1 for p in limpias if not p.generos)

    if informe.rechazadas > informe.aceptadas:
        informe.advertencias.append("Se rechazaron más filas de las que se aceptaron: revise el archivo.")
    return informe
