"""Utilidades de texto para agrupar y ordenar igual que la base de datos."""
import unicodedata


def clave_texto(texto: str) -> str:
    """Clave que ignora mayúsculas y tildes (equivale a la colación utf8mb4_unicode_ci de la base)."""
    sin_tildes = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.casefold()
