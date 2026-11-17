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


MAX_ANIOS_GRAFICO = 300     # un rango más largo no cabe en un gráfico legible


def leer_anios(desde: int | None, hasta: int | None, obligatorio: bool = True) -> tuple[int | None, int | None]:
    """Valida un rango de años F1..F2 (AAAA). Con obligatorio=False se admite dejar uno o ambos extremos abiertos."""
    if obligatorio and (desde is None or hasta is None):
        raise ErrorDeParametro("Debe indicar 'desde' y 'hasta' (años en formato AAAA).")
    if desde is not None and hasta is not None and desde > hasta:
        raise ErrorDeParametro(f"El rango es inválido: 'desde' ({desde}) es posterior a 'hasta' ({hasta}).")
    return desde, hasta
