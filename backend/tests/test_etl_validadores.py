"""Pruebas de los validadores compartidos."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.etl.validadores import ErrorDeValor, dinero, entero, espacios_normalizados, fecha_excel, texto


def test_espacios_normalizados():
    assert espacios_normalizados("  Ing.   de \t Soporte ") == "Ing. de Soporte"


def test_texto_limpia_y_valida():
    assert texto("  Ana   Pérez ", "n", 20) == "Ana Pérez"
    assert texto("x" * 20, "n", 20) == "x" * 20
    with pytest.raises(ErrorDeValor, match="supera los 20"):
        texto("x" * 21, "n", 20)


@pytest.mark.parametrize("vacio", [None, "", "   "])
def test_texto_vacio(vacio):
    with pytest.raises(ErrorDeValor, match="vacío"):
        texto(vacio, "n", 20)
    assert texto(vacio, "n", 20, obligatorio=False) is None


def test_texto_convierte_numeros():
    assert texto(123, "n", 10) == "123"


@pytest.mark.parametrize("valor,esperado", [(5, 5), (5.0, 5), ("5", 5), (" 7 ", 7), (0, 0)])
def test_entero_acepta(valor, esperado):
    assert entero(valor, "c") == esperado


@pytest.mark.parametrize("valor", [5.5, "5.5", "abc", "", None, True, "-3", [1]])
def test_entero_rechaza(valor):
    with pytest.raises(ErrorDeValor):
        entero(valor, "c")


def test_entero_limites():
    assert entero(1, "c", minimo=1, maximo=3) == 1
    assert entero(3, "c", minimo=1, maximo=3) == 3
    for fuera in (0, 4):
        with pytest.raises(ErrorDeValor, match="entre 1 y 3"):
            entero(fuera, "c", minimo=1, maximo=3)


@pytest.mark.parametrize("valor,esperado", [
    (3500000, "3500000.00"), (3500000.5, "3500000.50"), ("3500000.504", "3500000.50"),
    ("0.005", "0.01"), (Decimal("12.345"), "12.35"), (0, "0.00"),
])
def test_dinero_acepta_y_redondea(valor, esperado):
    assert dinero(valor, "s") == Decimal(esperado)


@pytest.mark.parametrize("valor", [None, True, "abc", "", "-5", "1,5", float("nan"), float("inf")])
def test_dinero_rechaza(valor):
    with pytest.raises(ErrorDeValor):
        dinero(valor, "s")


def test_dinero_limites():
    with pytest.raises(ErrorDeValor):
        dinero(0, "s", minimo=Decimal("0.01"))
    with pytest.raises(ErrorDeValor):
        dinero("1000000000000", "s")


@pytest.mark.parametrize("valor,esperada", [
    (datetime(2022, 3, 2, 10, 30), date(2022, 3, 2)),
    (date(2022, 3, 2), date(2022, 3, 2)),
    (44622, date(2022, 3, 2)),            # serie de Excel
    (44622.0, date(2022, 3, 2)),
    (20210311, date(2021, 3, 11)),        # AAAAMMDD numérico
    ("20210311", date(2021, 3, 11)),
    ("2021-03-11", date(2021, 3, 11)),
    (" 2021-03-11 ", date(2021, 3, 11)),
])
def test_fecha_excel_acepta(valor, esperada):
    assert fecha_excel(valor, "f") == esperada


@pytest.mark.parametrize("valor", [20210231, "20211301", "ayer", 0, -5, True, "2021-02-30", 2.5])
def test_fecha_excel_rechaza(valor):
    with pytest.raises(ErrorDeValor):
        fecha_excel(valor, "f")


def test_fecha_excel_vacia():
    assert fecha_excel(None, "f", obligatorio=False) is None
    assert fecha_excel("  ", "f", obligatorio=False) is None
    with pytest.raises(ErrorDeValor, match="vacía"):
        fecha_excel(None, "f")


def test_mensaje_incluye_nombre_del_campo():
    with pytest.raises(ErrorDeValor, match="'FECHA INGRESO'"):
        fecha_excel("ayer", "FECHA INGRESO")
