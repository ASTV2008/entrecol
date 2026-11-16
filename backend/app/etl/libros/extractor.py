"""EXTRAER: convierte el flujo de bytes de Books.json en registros numerados.

Books.json es una lista de objetos: [ {"bookID": 1, "title": "...", ...}, {...} ].
Recibe bytes (no una ruta) para servir igual desde la terminal y desde el navegador.
"""
import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, BinaryIO

from app.etl.common import ErrorDeArchivo


@dataclass(frozen=True)
class RegistroCrudo:
    numero: int   # posición en la lista (el primero es el 1)
    datos: Any    # normalmente un dict; si es otra cosa, el transformador lo rechaza


def leer_registros(flujo: BinaryIO) -> Iterator[RegistroCrudo]:
    """Entrega cada elemento de la lista con su posición.

    Cancela la carga (ErrorDeArchivo) si el archivo no es UTF-8, no es JSON válido
    o no es una lista: casi seguro se subió el archivo equivocado.
    Lee el archivo completo en memoria (Books.json pesa unos 2 MB).
    """
    try:
        texto = flujo.read().decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ErrorDeArchivo("El archivo no está codificado en UTF-8.") from error
    try:
        contenido = json.loads(texto)
    except json.JSONDecodeError as error:
        raise ErrorDeArchivo(
            f"El archivo no es un JSON válido (línea {error.lineno}, columna {error.colno}): {error.msg}."
        ) from error
    if not isinstance(contenido, list):
        raise ErrorDeArchivo("Se esperaba una lista de libros, es decir, un JSON que empiece con '['.")
    for numero, datos in enumerate(contenido, start=1):
        yield RegistroCrudo(numero, datos)
