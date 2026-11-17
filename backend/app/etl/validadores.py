"""Validadores de valores sueltos, compartidos por los ETL.

Cada función recibe un valor "crudo" (lo que entrega el archivo) y devuelve el valor
ya convertido a su tipo real, o lanza ErrorDeValor con un mensaje en lenguaje claro
que menciona el nombre del campo. El transformador de cada fuente captura ErrorDeValor
y lo convierte en un Rechazo de la fila.
"""
import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_ESPACIOS = re.compile(r"\s+")
_ENTERO = re.compile(r"\d+", re.ASCII)
_DECIMAL = re.compile(r"\d+(\.\d+)?", re.ASCII)
_FECHA_COMPACTA = re.compile(r"(\d{4})(\d{2})(\d{2})", re.ASCII)
_ORIGEN_EXCEL = date(1899, 12, 30)       # día 0 del calendario de Excel
_SERIE_EXCEL_MAX = 2_958_465             # 31/12/9999


class ErrorDeValor(ValueError):
    """Un valor no cumple las reglas del campo."""


def espacios_normalizados(valor: str) -> str:
    """Quita espacios de los extremos y colapsa los repetidos ('Ing.  Soporte' -> 'Ing. Soporte')."""
    return _ESPACIOS.sub(" ", valor).strip()


def texto(valor: object, campo: str, largo_max: int, obligatorio: bool = True) -> str | None:
    """Texto limpio. Si es obligatorio y viene vacío, falla; si no, devuelve None."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            raise ErrorDeValor(f"'{campo}' está vacío")
        return None
    limpio = espacios_normalizados(str(valor))
    if len(limpio) > largo_max:
        raise ErrorDeValor(f"'{campo}' supera los {largo_max} caracteres ({len(limpio)})")
    return limpio


def entero(valor: object, campo: str, minimo: int = 0, maximo: int = 4_294_967_295) -> int:
    """Entero dentro de [minimo, maximo]. Acepta 5, 5.0 y '5'; rechaza 5.5, 'abc' y booleanos."""
    if isinstance(valor, bool):
        raise ErrorDeValor(f"'{campo}' no es un número entero: {valor!r}")
    if isinstance(valor, int):
        numero = valor
    elif isinstance(valor, float):
        if not valor.is_integer():
            raise ErrorDeValor(f"'{campo}' no es un número entero: {valor!r}")
        numero = int(valor)
    elif isinstance(valor, str) and _ENTERO.fullmatch(valor.strip()):
        numero = int(valor.strip())
    else:
        raise ErrorDeValor(f"'{campo}' no es un número entero: {valor!r}")
    if not minimo <= numero <= maximo:
        raise ErrorDeValor(f"'{campo}' debe estar entre {minimo} y {maximo}: {numero}")
    return numero


def dinero(valor: object, campo: str, minimo: Decimal = Decimal(0), maximo: Decimal = Decimal("999999999999.99")) -> Decimal:
    """Valor monetario con 2 decimales. Acepta números y texto como '3500000' o '3500000.50'."""
    if isinstance(valor, bool) or valor is None:
        raise ErrorDeValor(f"'{campo}' no es un valor numérico: {valor!r}")
    if isinstance(valor, (int, float, Decimal)):
        try:
            numero = Decimal(str(valor))
        except InvalidOperation as error:
            raise ErrorDeValor(f"'{campo}' no es un valor numérico: {valor!r}") from error
    elif isinstance(valor, str) and _DECIMAL.fullmatch(valor.strip()):
        numero = Decimal(valor.strip())
    else:
        raise ErrorDeValor(f"'{campo}' no es un valor numérico: {valor!r}")
    if not numero.is_finite():
        raise ErrorDeValor(f"'{campo}' no es un valor numérico: {valor!r}")
    numero = numero.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not minimo <= numero <= maximo:
        raise ErrorDeValor(f"'{campo}' debe estar entre {minimo} y {maximo}: {numero}")
    return numero


def fecha_excel(valor: object, campo: str, obligatorio: bool = True) -> date | None:
    """Fecha desde una celda de Excel.

    Acepta: fecha/fecha-hora real, número de serie de Excel (44622 = 02/03/2022),
    número o texto compacto AAAAMMDD (20210311) y texto AAAA-MM-DD.
    Una fecha imposible (20210231) se rechaza; nunca se corrige "adivinando".
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            raise ErrorDeValor(f"'{campo}' está vacía")
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, bool):
        raise ErrorDeValor(f"'{campo}' no es una fecha válida: {valor!r}")
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, int):
        if valor > _SERIE_EXCEL_MAX:      # 8 dígitos: AAAAMMDD (no puede confundirse con una serie de Excel)
            return _desde_compacto(str(valor), campo)
        if valor < 1:
            raise ErrorDeValor(f"'{campo}' no es una fecha válida: {valor!r}")
        return _ORIGEN_EXCEL + timedelta(days=valor)
    if isinstance(valor, str):
        limpio = valor.strip()
        if _FECHA_COMPACTA.fullmatch(limpio):
            return _desde_compacto(limpio, campo)
        try:
            return date.fromisoformat(limpio)
        except ValueError:
            pass
    raise ErrorDeValor(f"'{campo}' no es una fecha válida: {valor!r}")


def _desde_compacto(cadena: str, campo: str) -> date:
    coincide = _FECHA_COMPACTA.fullmatch(cadena)
    if not coincide:
        raise ErrorDeValor(f"'{campo}' no es una fecha válida: {cadena!r}")
    anio, mes, dia = (int(g) for g in coincide.groups())
    try:
        return date(anio, mes, dia)
    except ValueError as error:
        raise ErrorDeValor(f"'{campo}' es una fecha inexistente: {cadena}") from error
