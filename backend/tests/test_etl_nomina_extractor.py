"""Pruebas del paso EXTRAER de nómina."""
import io
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.etl.common import ErrorDeArchivo
from app.etl.nomina.extractor import leer_nomina
from excel_nomina import ENCABEZADO_EMPLEADOS, ENCABEZADO_NOVEDADES, d, empleado, libro_excel, novedad

ARCHIVO_REAL = Path("/data/Nomina.xlsx")


def test_lee_ambas_hojas_con_nombres_de_columna():
    lectura = leer_nomina(libro_excel([empleado(5001), empleado(5002)], [novedad(5001, inc_ini=d(2022, 3, 2))]))
    assert [f.valores["codigo"] for f in lectura.empleados] == [5001, 5002]
    assert lectura.empleados[0].valores["dependencia"] == "Tecnología"
    assert lectura.novedades[0].valores["inc_inicio"].day == 2
    assert (lectura.empleados[0].hoja, lectura.novedades[0].hoja) == ("Table 1", "Table 3")


def test_numera_las_filas_como_excel():
    lectura = leer_nomina(libro_excel([empleado(5001), empleado(5002)], []))
    assert [f.numero for f in lectura.empleados] == [2, 3]      # la fila 1 es el encabezado


def test_reconoce_hojas_por_encabezado_no_por_nombre_ni_orden():
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Novedades de marzo"
    hoja.append(ENCABEZADO_NOVEDADES); hoja.append(novedad(5001))
    otra = libro.create_sheet("Personal")
    otra.append(ENCABEZADO_EMPLEADOS); otra.append(empleado(5001))
    flujo = io.BytesIO(); libro.save(flujo); flujo.seek(0)
    lectura = leer_nomina(flujo)
    assert (len(lectura.empleados), len(lectura.novedades)) == (1, 1)


def test_encabezados_sin_tildes_ni_mayusculas_ni_espacios_extra():
    enc = [c.lower().replace("ó", "o").replace("í", "i") + "  " for c in ENCABEZADO_EMPLEADOS]
    assert len(leer_nomina(libro_excel(encabezados={"empleados": enc})).empleados) == 1


def test_ignora_filas_vacias_y_columnas_extra():
    lectura = leer_nomina(libro_excel([empleado(5001) + ["extra"], [None] * 9, ["  "] + [None] * 8, empleado(5002)], []))
    assert [f.valores["codigo"] for f in lectura.empleados] == [5001, 5002]


def test_falta_la_hoja_de_empleados():
    libro = Workbook(); libro.active.append(ENCABEZADO_NOVEDADES)
    flujo = io.BytesIO(); libro.save(flujo); flujo.seek(0)
    with pytest.raises(ErrorDeArchivo, match="hoja de empleados"):
        leer_nomina(flujo)


def test_falta_la_hoja_de_novedades():
    libro = Workbook(); libro.active.append(ENCABEZADO_EMPLEADOS)
    flujo = io.BytesIO(); libro.save(flujo); flujo.seek(0)
    with pytest.raises(ErrorDeArchivo, match="hoja de novedades"):
        leer_nomina(flujo)


def test_columna_faltante_invalida_la_hoja():
    with pytest.raises(ErrorDeArchivo, match="hoja de empleados"):
        leer_nomina(libro_excel(encabezados={"empleados": ENCABEZADO_EMPLEADOS[:-1]}))


@pytest.mark.parametrize("contenido", [b"", b"esto no es excel", b"PK\x03\x04roto"])
def test_archivo_que_no_es_excel(contenido):
    with pytest.raises(ErrorDeArchivo, match="Excel"):
        leer_nomina(io.BytesIO(contenido))


@pytest.mark.skipif(not ARCHIVO_REAL.exists(), reason="Nomina.xlsx real no está montado")
def test_archivo_real():
    with ARCHIVO_REAL.open("rb") as f:
        lectura = leer_nomina(f)
    assert (len(lectura.empleados), len(lectura.novedades)) == (20, 20)
