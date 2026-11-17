"""EXTRAER: lee Nomina.xlsx y entrega las filas de cada hoja con sus valores por nombre de columna.

Recibe BYTES (no una ruta): sirve igual desde la terminal y desde una subida web.

Las hojas se reconocen por sus ENCABEZADOS, no por su nombre: el archivo original las llama
'Table 1' y 'Table 3', pero un archivo nuevo de igual estructura puede traerlas con otro nombre
o en otro orden. Los encabezados se comparan sin tildes ni mayúsculas.
"""
import unicodedata
from dataclasses import dataclass
from typing import BinaryIO
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.etl.common import ErrorDeArchivo

COLUMNAS_EMPLEADOS = {
    "codigo": "CODIGO", "nombre": "NOMBRE DEL EMPLEADO", "dependencia": "DEPENDENCIA", "cargo": "CARGO",
    "fecha_ingreso": "FECHA INGRESO", "eps": "EPS", "arl": "ARL", "pension": "PENSION", "sueldo": "SUELDO",
}
COLUMNAS_NOVEDADES = {
    "codigo": "CODIGO", "marca_incapacidad": "NOVEDAD INCAPACIDAD", "marca_vacaciones": "NOVEDAD VACACIONES",
    "dias_trabajados": "NUMERO DIAS TRABAJADOS EN EL MES", "dias_incapacidad": "NUMERO DIAS INCAPACIDADES EN EL MES",
    "dias_vacaciones": "NUMERO DE DIAS VACACIONES", "vac_inicio": "FECHA DE INICIO DE VACACIONES",
    "vac_fin": "FECHA TERMINACION DE VACACIONES", "inc_inicio": "FECHA INICIO INCAPACIDAD",
    "inc_fin": "FECHA TERMINACION INCAPACIDAD", "bonificacion": "BONIFICACION", "transporte": "TRANSPORTE",
}


@dataclass(frozen=True)
class FilaCruda:
    numero: int               # número de fila en la hoja (la del encabezado es la 1)
    hoja: str
    valores: dict[str, object]   # clave interna -> valor de la celda


@dataclass(frozen=True)
class LecturaNomina:
    empleados: list[FilaCruda]
    novedades: list[FilaCruda]


def _normalizar(encabezado: object) -> str:
    texto = unicodedata.normalize("NFD", str(encabezado or "")).encode("ascii", "ignore").decode()
    return " ".join(texto.upper().split())


def _fila_vacia(fila: tuple) -> bool:
    return all(c is None or (isinstance(c, str) and not c.strip()) for c in fila)


def _leer_hoja(hoja, columnas: dict[str, str]) -> list[FilaCruda] | None:
    """Filas de la hoja si sus encabezados incluyen todas las columnas esperadas; si no, None."""
    filas = hoja.iter_rows(values_only=True)
    encabezado = next(filas, None)
    if encabezado is None:
        return None
    posicion = {_normalizar(nombre): i for i, nombre in enumerate(encabezado) if nombre is not None}
    if any(esperado not in posicion for esperado in columnas.values()):
        return None
    resultado = []
    for numero, fila in enumerate(filas, start=2):
        if _fila_vacia(fila):
            continue
        valores = {clave: (fila[posicion[esperado]] if posicion[esperado] < len(fila) else None) for clave, esperado in columnas.items()}
        resultado.append(FilaCruda(numero, hoja.title, valores))
    return resultado


def leer_nomina(flujo: BinaryIO) -> LecturaNomina:
    """Lee el libro completo. Lanza ErrorDeArchivo si no es un Excel válido o faltan hojas."""
    try:
        libro = load_workbook(flujo, read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as error:
        raise ErrorDeArchivo("El archivo no es un libro de Excel (.xlsx) válido.") from error
    try:
        empleados = novedades = None
        for hoja in libro.worksheets:
            if empleados is None and (filas := _leer_hoja(hoja, COLUMNAS_EMPLEADOS)) is not None:
                empleados = filas
            elif novedades is None and (filas := _leer_hoja(hoja, COLUMNAS_NOVEDADES)) is not None:
                novedades = filas
    finally:
        libro.close()
    if empleados is None:
        raise ErrorDeArchivo("No se encontró la hoja de empleados (con las columnas CÓDIGO, NOMBRE DEL EMPLEADO, DEPENDENCIA, CARGO, FECHA INGRESO, EPS, ARL, PENSIÓN y SUELDO).")
    if novedades is None:
        raise ErrorDeArchivo("No se encontró la hoja de novedades (con las columnas CÓDIGO, NOVEDAD INCAPACIDAD, … BONIFICACIÓN y TRANSPORTE).")
    return LecturaNomina(empleados, novedades)
