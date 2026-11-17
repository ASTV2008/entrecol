"""Interpreta rangos de periodos en formato MM/AAAA (el formato que pide el cliente)."""
import re

from app.core.errores import ErrorDeParametro

_PATRON = re.compile(r"(0[1-9]|1[0-2])/(\d{4})")


def leer_periodo(texto: str, campo: str) -> tuple[int, int]:
    """'03/2022' -> (2022, 3). Lanza ErrorDeParametro si no tiene el formato MM/AAAA."""
    coincide = _PATRON.fullmatch(texto.strip())
    if not coincide:
        raise ErrorDeParametro(f"'{campo}' debe tener el formato MM/AAAA, por ejemplo 03/2022 (recibido: {texto!r}).")
    return int(coincide.group(2)), int(coincide.group(1))


def leer_rango(desde: str, hasta: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Valida F1 <= F2 y devuelve ((año, mes), (año, mes))."""
    inicio, fin = leer_periodo(desde, "desde"), leer_periodo(hasta, "hasta")
    if inicio > fin:
        raise ErrorDeParametro(f"El rango es inválido: 'desde' ({desde}) es posterior a 'hasta' ({hasta}).")
    return inicio, fin


def texto_periodo(anio: int, mes: int) -> str:
    return f"{mes:02d}/{anio}"
