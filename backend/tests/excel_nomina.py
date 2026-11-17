"""Ayudante de pruebas: fabrica un Nomina.xlsx en memoria con la misma estructura del real."""
import io
from datetime import datetime

from openpyxl import Workbook

ENCABEZADO_EMPLEADOS = ["CÓDIGO", "NOMBRE DEL EMPLEADO", "DEPENDENCIA", "CARGO", "FECHA INGRESO", "EPS", "ARL", "PENSIÓN", "SUELDO"]
ENCABEZADO_NOVEDADES = [
    "CÓDIGO", "NOVEDAD INCAPACIDAD", "NOVEDAD VACACIONES", "NUMERO DIAS TRABAJADOS EN EL MES",
    "NUMERO DIAS INCAPACIDADES EN EL MES", "NUMERO DE DIAS VACACIONES", "FECHA DE INICIO DE VACACIONES",
    "FECHA TERMINACION DE VACACIONES", "FECHA INICIO INCAPACIDAD", "FECHA TERMINACIÓN INCAPACIDAD",
    "BONIFICACIÓN", "TRANSPORTE",
]


def empleado(codigo=5001, nombre="PEREZ GOMEZ ANA", dependencia="Tecnología", cargo="Analista", ingreso=20210311,
             eps="Nueva EPS", arl="Positiva", pension="Colpensiones", sueldo=3_000_000):
    return [codigo, nombre, dependencia, cargo, ingreso, eps, arl, pension, sueldo]


def novedad(codigo=5001, marca_inc=None, marca_vac=None, trabajados=30, dias_inc=0, dias_vac=0,
            vac_ini=None, vac_fin=None, inc_ini=None, inc_fin=None, bonificacion=100_000, transporte=20_000):
    return [codigo, marca_inc, marca_vac, trabajados, dias_inc, dias_vac, vac_ini, vac_fin, inc_ini, inc_fin, bonificacion, transporte]


def d(anio, mes, dia):
    return datetime(anio, mes, dia)


def libro_excel(empleados=None, novedades=None, nombres=("Table 1", "Table 3"), encabezados=None) -> io.BytesIO:
    """Libro con la hoja de empleados y la de novedades (en ese orden salvo que se indique otro)."""
    empleados = [empleado()] if empleados is None else empleados
    novedades = [novedad()] if novedades is None else novedades
    libro = Workbook()
    hoja_e = libro.active
    hoja_e.title = nombres[0]
    hoja_e.append((encabezados or {}).get("empleados", ENCABEZADO_EMPLEADOS))
    for f in empleados:
        hoja_e.append(f)
    hoja_n = libro.create_sheet(nombres[1])
    hoja_n.append((encabezados or {}).get("novedades", ENCABEZADO_NOVEDADES))
    for f in novedades:
        hoja_n.append(f)
    salida = io.BytesIO()
    libro.save(salida)
    salida.seek(0)
    return salida
