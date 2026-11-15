"""EXTRAER: convierte el flujo de bytes de movies.dat en líneas de texto numeradas.

Recibe un flujo de bytes (no una ruta de archivo): así el mismo código sirve para
un archivo abierto desde la terminal y para un archivo subido desde el navegador.
"""
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO

from app.etl.common import ErrorDeArchivo


@dataclass(frozen=True)
class LineaCruda:
    numero: int   # número de línea en el archivo (la primera es la 1)
    texto: str


def leer_lineas(flujo: BinaryIO) -> Iterator[LineaCruda]:
    """Entrega cada línea con contenido, conservando su número original.

    - Acepta saltos de línea de Linux (\\n) y de Windows (\\r\\n).
    - Ignora un BOM inicial (marca invisible que algunos editores agregan).
    - Ignora las líneas en blanco, pero igual las cuenta para numerar bien.
    - Si una línea no es UTF-8 válido, cancela la carga: casi seguro es otro archivo.
    """
    for numero, bruta in enumerate(flujo, start=1):
        codificacion = "utf-8-sig" if numero == 1 else "utf-8"
        try:
            texto = bruta.decode(codificacion)
        except UnicodeDecodeError as error:
            raise ErrorDeArchivo(
                f"La línea {numero} no está codificada en UTF-8. "
                "Verifique que sea el archivo correcto y que se haya guardado como UTF-8."
            ) from error
        texto = texto.rstrip("\r\n")
        if texto.strip():
            yield LineaCruda(numero, texto)
