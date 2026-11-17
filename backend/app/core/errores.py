"""Errores de negocio compartidos por los servicios.

Los servicios NO conocen HTTP: lanzan estos errores y una sola función en main.py los
convierte en respuestas 422 (parámetro inválido). Así la lógica se puede probar sin servidor.
"""


class ErrorDeParametro(ValueError):
    """Un parámetro de la consulta no es válido (formato, rango, valor fuera de límites)."""
