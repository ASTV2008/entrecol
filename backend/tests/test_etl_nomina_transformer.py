"""Pruebas del paso TRANSFORMAR de nómina: cada regla de rechazo y de aviso."""
from datetime import date
from decimal import Decimal

import pytest

from app.etl.common import Rechazo
from app.etl.nomina.extractor import COLUMNAS_EMPLEADOS, COLUMNAS_NOVEDADES, FilaCruda
from app.etl.nomina.transformer import EmpleadoLimpio, TransformadorEmpleados, TransformadorNovedades
from excel_nomina import d


def fila_emp(numero=2, **cambios) -> FilaCruda:
    v = dict(codigo=5001, nombre="PEREZ ANA", dependencia="Tecnología", cargo="Analista", fecha_ingreso=20210311,
             eps="Nueva EPS", arl="Positiva", pension="Colpensiones", sueldo=3_000_000)
    v.update(cambios)
    assert set(v) == set(COLUMNAS_EMPLEADOS)
    return FilaCruda(numero, "Table 1", v)


def fila_nov(numero=2, **cambios) -> FilaCruda:
    v = dict(codigo=5001, marca_incapacidad=None, marca_vacaciones=None, dias_trabajados=30, dias_incapacidad=0,
             dias_vacaciones=0, vac_inicio=None, vac_fin=None, inc_inicio=None, inc_fin=None, bonificacion=100, transporte=20)
    v.update(cambios)
    assert set(v) == set(COLUMNAS_NOVEDADES)
    return FilaCruda(numero, "Table 3", v)


def nov(**cambios):
    t = TransformadorNovedades(2022, 3)
    return t, t.transformar(fila_nov(**cambios))


# ----------------------------------------------------------------- empleados
def test_empleado_valido():
    e = TransformadorEmpleados().transformar(fila_emp(nombre="  PEREZ   ANA ", sueldo="3500000.5"))
    assert e == EmpleadoLimpio(5001, "PEREZ ANA", "Tecnología", "Analista", date(2021, 3, 11), "Nueva EPS", "Positiva",
                               "Colpensiones", Decimal("3500000.50"))


@pytest.mark.parametrize("campo,valor,motivo", [
    ("codigo", None, "CÓDIGO"), ("codigo", 0, "CÓDIGO"), ("codigo", "abc", "CÓDIGO"),
    ("nombre", " ", "NOMBRE"), ("nombre", "x" * 101, "NOMBRE"),
    ("dependencia", None, "DEPENDENCIA"), ("cargo", None, "CARGO"), ("eps", None, "EPS"),
    ("arl", None, "ARL"), ("pension", None, "PENSIÓN"),
    ("fecha_ingreso", None, "FECHA INGRESO"), ("fecha_ingreso", 20210231, "FECHA INGRESO"),
    ("sueldo", 0, "SUELDO"), ("sueldo", -5, "SUELDO"), ("sueldo", "mucho", "SUELDO"), ("sueldo", None, "SUELDO"),
    ("cargo", "x" * 81, "CARGO"), ("dependencia", "x" * 61, "DEPENDENCIA"),
])
def test_empleado_rechazado(campo, valor, motivo):
    r = TransformadorEmpleados().transformar(fila_emp(numero=7, **{campo: valor}))
    assert isinstance(r, Rechazo)
    assert motivo in r.motivo
    assert (r.linea, r.origen) == (7, "Table 1")


def test_empleado_repetido_en_el_archivo_se_rechaza_el_segundo():
    t = TransformadorEmpleados()
    assert isinstance(t.transformar(fila_emp()), EmpleadoLimpio)
    r = t.transformar(fila_emp(numero=3))
    assert isinstance(r, Rechazo) and "repetido" in r.motivo


def test_empleado_rechazado_no_bloquea_su_codigo():
    t = TransformadorEmpleados()
    assert isinstance(t.transformar(fila_emp(sueldo=0)), Rechazo)
    assert isinstance(t.transformar(fila_emp()), EmpleadoLimpio)     # la versión buena sí entra


# ------------------------------------------------------------------ novedades
def test_novedad_sin_eventos():
    t, n = nov()
    assert (n.codigo, n.bonificacion, n.transporte, n.incapacidad, n.vacacion) == (5001, Decimal("100.00"), Decimal("20.00"), None, None)
    assert t.avisos == {}
    assert (n.fila, n.hoja) == (2, "Table 3")


def test_incapacidad_correcta_sin_avisos():
    t, n = nov(marca_incapacidad="X", dias_trabajados=12, dias_incapacidad=18, inc_inicio=d(2022, 3, 2), inc_fin=d(2022, 3, 19))
    assert (n.incapacidad.inicio, n.incapacidad.fin, n.incapacidad.dias_reportados) == (date(2022, 3, 2), date(2022, 3, 19), 18)
    assert n.vacacion is None and t.avisos == {}


def test_vacaciones_correctas_sin_avisos():
    t, n = nov(marca_vacaciones="x", dias_trabajados=20, dias_vacaciones=10, vac_inicio=d(2022, 3, 10), vac_fin=d(2022, 3, 19))
    assert n.vacacion.dias_reportados == 10 and t.avisos == {}


def test_fechas_como_serie_de_excel():
    _, n = nov(marca_incapacidad="X", dias_trabajados=26, dias_incapacidad=4, inc_inicio=44622, inc_fin=44625)
    assert n.incapacidad.inicio == date(2022, 3, 2)


@pytest.mark.parametrize("cambios,motivo", [
    (dict(marca_incapacidad="X", dias_incapacidad=3), "marca 'X' pero no tiene fechas"),
    (dict(marca_vacaciones="X", dias_vacaciones=3), "marca 'X' pero no tiene fechas"),
    (dict(dias_incapacidad=3), "reporta 3 día(s) pero no tiene fechas"),
    (dict(dias_vacaciones=3), "reporta 3 día(s) pero no tiene fechas"),
    (dict(marca_incapacidad="X", dias_incapacidad=0, inc_inicio=d(2022, 3, 2), inc_fin=d(2022, 3, 4)), "0 días"),
    (dict(marca_vacaciones="X", dias_vacaciones=0, vac_inicio=d(2022, 3, 2), vac_fin=d(2022, 3, 4)), "0 días"),
    (dict(marca_incapacidad="X", dias_incapacidad=3, inc_inicio=d(2022, 3, 5), inc_fin=d(2022, 3, 2)), "anterior a la de inicio"),
    (dict(marca_vacaciones="X", dias_vacaciones=3, vac_inicio=d(2022, 3, 5), vac_fin=d(2022, 3, 2)), "anterior a la de inicio"),
    (dict(marca_incapacidad="X", dias_incapacidad=3, inc_inicio=d(2022, 3, 5)), "incompletas"),
    (dict(marca_vacaciones="X", dias_vacaciones=3, vac_fin=d(2022, 3, 5)), "incompletas"),
    (dict(marca_incapacidad="SI"), "solo admite 'X'"),
    (dict(marca_incapacidad="X", dias_incapacidad=3, inc_inicio="no es fecha", inc_fin=d(2022, 3, 5)), "fecha válida"),
    (dict(dias_trabajados=None), "DIAS TRABAJADOS"),
    (dict(dias_trabajados=32), "DIAS TRABAJADOS"),
    (dict(bonificacion=-1), "BONIFICACIÓN"),
    (dict(transporte="x"), "TRANSPORTE"),
    (dict(bonificacion=None), "BONIFICACIÓN"),
    (dict(codigo=None), "CÓDIGO"),
])
def test_novedad_rechazada(cambios, motivo):
    t, r = nov(**cambios)
    assert isinstance(r, Rechazo), cambios
    assert motivo in r.motivo
    assert t.avisos == {}                      # una fila rechazada no deja avisos


def test_fila_rechazada_no_deja_avisos_aunque_se_hayan_detectado_antes():
    # incapacidad con días distintos (aviso) + vacaciones inválidas (rechazo): no debe quedar el aviso
    t, r = nov(marca_incapacidad="X", dias_incapacidad=9, inc_inicio=d(2022, 3, 2), inc_fin=d(2022, 3, 4), dias_trabajados=21,
               marca_vacaciones="X", dias_vacaciones=3)
    assert isinstance(r, Rechazo) and t.avisos == {}


def test_aviso_dias_distintos_se_conserva_el_valor_reportado():
    t, n = nov(marca_vacaciones="X", dias_trabajados=18, dias_vacaciones=12, vac_inicio=d(2022, 3, 10), vac_fin=d(2022, 3, 19))
    assert n.vacacion.dias_reportados == 12                      # no se "corrige" a 10
    assert t.avisos == {"dias_distintos_vacaciones": [5001]}


def test_aviso_incapacidad_dias_distintos():
    t, _ = nov(marca_incapacidad="X", dias_trabajados=25, dias_incapacidad=5, inc_inicio=d(2022, 3, 2), inc_fin=d(2022, 3, 7))
    assert t.avisos == {"dias_distintos_incapacidad": [5001]}


def test_aviso_fechas_sin_marca_se_carga_igual():
    t, n = nov(dias_trabajados=27, dias_incapacidad=3, inc_inicio=d(2022, 3, 2), inc_fin=d(2022, 3, 4))
    assert n.incapacidad is not None
    assert t.avisos == {"sin_marca_incapacidad": [5001]}


@pytest.mark.parametrize("inicio,fin,fuera", [
    (d(2022, 2, 20), d(2022, 2, 28), True),     # termina antes del mes
    (d(2022, 4, 1), d(2022, 4, 5), True),       # empieza después
    (d(2022, 2, 25), d(2022, 3, 1), False),     # termina el primer día
    (d(2022, 3, 31), d(2022, 4, 2), False),     # empieza el último día
    (d(2022, 2, 1), d(2022, 4, 30), False),     # lo cubre entero
    (d(2022, 3, 10), d(2022, 3, 12), False),
])
def test_aviso_fuera_del_mes(inicio, fin, fuera):
    dias = (fin - inicio).days + 1
    t, n = nov(marca_incapacidad="X", dias_incapacidad=dias, inc_inicio=inicio, inc_fin=fin, dias_trabajados=30 - dias)
    assert n is not None
    assert ("fuera_del_mes_incapacidad" in t.avisos) is fuera


def test_mes_diciembre_considera_enero_siguiente():
    t = TransformadorNovedades(2022, 12)
    t.transformar(fila_nov(marca_incapacidad="X", dias_incapacidad=3, inc_inicio=d(2022, 12, 30), inc_fin=d(2023, 1, 1), dias_trabajados=27))
    assert "fuera_del_mes_incapacidad" not in t.avisos
    t.transformar(fila_nov(codigo=5002, marca_incapacidad="X", dias_incapacidad=3, inc_inicio=d(2023, 1, 1), inc_fin=d(2023, 1, 3), dias_trabajados=27))
    assert t.avisos["fuera_del_mes_incapacidad"] == [5002]


def test_aviso_suma_distinta_de_30():
    t, _ = nov(dias_trabajados=25)
    assert t.avisos == {"suma_distinta_de_30": [5001]}
    t2, _ = nov(marca_vacaciones="X", dias_trabajados=20, dias_vacaciones=10, vac_inicio=d(2022, 3, 1), vac_fin=d(2022, 3, 10))
    assert t2.avisos == {}


def test_codigo_con_dos_filas_de_novedades():
    t = TransformadorNovedades(2022, 3)
    assert not isinstance(t.transformar(fila_nov()), Rechazo)
    r = t.transformar(fila_nov(numero=3))
    assert isinstance(r, Rechazo) and "más de una fila" in r.motivo


def test_dos_eventos_en_la_misma_fila():
    _, n = nov(marca_incapacidad="X", marca_vacaciones="X", dias_trabajados=10, dias_incapacidad=10, dias_vacaciones=10,
               inc_inicio=d(2022, 3, 1), inc_fin=d(2022, 3, 10), vac_inicio=d(2022, 3, 11), vac_fin=d(2022, 3, 20))
    assert n.incapacidad is not None and n.vacacion is not None
