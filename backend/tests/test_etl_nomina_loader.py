"""Pruebas del paso CARGAR y del servicio completo de nómina (usan la base de pruebas; cada prueba se deshace sola)."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.etl.common import ErrorDeArchivo
from app.etl.nomina.loader import CargadorNomina
from app.etl.nomina.service import PeriodoNomina, cargar_nomina
from app.etl.nomina.transformer import EmpleadoLimpio, EventoLimpio, NovedadLimpia
from app.models import Arl, Cargo, Dependencia, Empleado, Eps, FondoPension, Incapacidad, NovedadMensual, Periodo, Vacacion
from excel_nomina import d, empleado, libro_excel, novedad

PERIODO = PeriodoNomina(2022, 3)


def emp(codigo=5001, **cambios) -> EmpleadoLimpio:
    datos = dict(codigo=codigo, nombre="PEREZ ANA", dependencia="Tecnología", cargo="Analista", fecha_ingreso=date(2021, 3, 11),
                 eps="Nueva EPS", arl="Positiva", fondo_pension="Colpensiones", sueldo=Decimal("3000000.00"))
    datos.update(cambios)
    return EmpleadoLimpio(**datos)


def nv(codigo=5001, incapacidad=None, vacacion=None, bonificacion="100.00", transporte="20.00") -> NovedadLimpia:
    return NovedadLimpia(codigo, Decimal(bonificacion), Decimal(transporte), incapacidad, vacacion)


def contar(sesion, modelo) -> int:
    return sesion.execute(select(func.count()).select_from(modelo)).scalar_one()


def cargar(sesion, empleados, novedades, anio=2022, mes=3):
    return CargadorNomina(sesion, anio, mes).cargar(empleados, novedades)


# ----------------------------------------------------------------------- cargador
def test_carga_inicial(sesion):
    r = cargar(sesion, [emp(5001), emp(5002, cargo="Auditor")], [nv(5001), nv(5002)])
    assert (r.nuevas, r.actualizadas, r.sin_cambios, r.empleados_nuevos, r.novedades_nuevas) == (4, 0, 0, 2, 2)
    assert r.periodo_nuevo
    assert (r.dependencias.nuevos, r.cargos.nuevos, r.eps.nuevos, r.arl.nuevos, r.fondos.nuevos) == (1, 2, 1, 1, 1)
    assert (contar(sesion, Empleado), contar(sesion, NovedadMensual), contar(sesion, Periodo)) == (2, 2, 1)


def test_se_guardan_todos_los_valores(sesion):
    cargar(sesion, [emp(5009, nombre="ÑANDÚ", fecha_ingreso=date(2020, 5, 21), sueldo=Decimal("2560603.00"))],
           [nv(5009, bonificacion="336775.00", transporte="14345.00")])
    e = sesion.get(Empleado, 5009)
    assert (e.nombre_empleado, e.fecha_ingreso, e.sueldo) == ("ÑANDÚ", date(2020, 5, 21), Decimal("2560603.00"))
    assert (e.cargo.nombre, e.cargo.dependencia.nombre, e.eps.nombre, e.arl.nombre, e.fondo_pension.nombre) == (
        "Analista", "Tecnología", "Nueva EPS", "Positiva", "Colpensiones")
    n = sesion.execute(select(NovedadMensual).where(NovedadMensual.codigo == 5009)).scalar_one()
    assert (n.bonificacion, n.transporte, (n.periodo.anio, n.periodo.mes)) == (Decimal("336775.00"), Decimal("14345.00"), (2022, 3))


def test_eventos_se_guardan_con_los_dias_reportados(sesion):
    inc = EventoLimpio(date(2022, 3, 2), date(2022, 3, 19), 18)
    vac = EventoLimpio(date(2022, 4, 12), date(2022, 4, 28), 15)     # 17 días entre fechas, reporta 15
    r = cargar(sesion, [emp()], [nv(incapacidad=inc, vacacion=vac)])
    assert (r.incapacidades, r.vacaciones) == (1, 1)
    assert sesion.execute(select(Incapacidad.fecha_inicio, Incapacidad.fecha_fin, Incapacidad.dias_reportados)).one() == (date(2022, 3, 2), date(2022, 3, 19), 18)
    assert sesion.execute(select(Vacacion.dias_reportados)).scalar_one() == 15


def test_recarga_identica_no_cambia_nada(sesion):
    datos = ([emp(5001), emp(5002)], [nv(5001, incapacidad=EventoLimpio(date(2022, 3, 2), date(2022, 3, 5), 4)), nv(5002)])
    cargar(sesion, *datos)
    r = cargar(sesion, *datos)
    assert (r.nuevas, r.actualizadas, r.sin_cambios) == (0, 0, 4)
    assert not r.periodo_nuevo
    assert (r.dependencias.nuevos, r.cargos.nuevos) == (0, 0)
    assert (contar(sesion, Empleado), contar(sesion, NovedadMensual), contar(sesion, Incapacidad), contar(sesion, Periodo)) == (2, 2, 1, 1)


@pytest.mark.parametrize("cambio", [
    dict(nombre="OTRO NOMBRE"), dict(sueldo=Decimal("3000001.00")), dict(fecha_ingreso=date(2021, 3, 12)),
    dict(cargo="Otro cargo"), dict(dependencia="Otra dep"), dict(eps="Otra EPS"), dict(arl="Otra ARL"), dict(fondo_pension="Otro fondo"),
])
def test_cambio_en_un_empleado_se_actualiza(sesion, cambio):
    cargar(sesion, [emp()], [])
    r = cargar(sesion, [emp(**cambio)], [])
    assert (r.nuevas, r.actualizadas, r.sin_cambios) == (0, 1, 0)
    e = sesion.get(Empleado, 5001)
    sesion.refresh(e)
    esperado = {"nombre": e.nombre_empleado, "sueldo": e.sueldo, "fecha_ingreso": e.fecha_ingreso, "cargo": e.cargo.nombre,
                "dependencia": e.cargo.dependencia.nombre, "eps": e.eps.nombre, "arl": e.arl.nombre, "fondo_pension": e.fondo_pension.nombre}
    for clave, valor in cambio.items():
        assert esperado[clave] == valor


@pytest.mark.parametrize("nueva", [
    nv(bonificacion="101.00"), nv(transporte="21.00"),
    nv(incapacidad=EventoLimpio(date(2022, 3, 2), date(2022, 3, 4), 3)),
    nv(vacacion=EventoLimpio(date(2022, 3, 2), date(2022, 3, 4), 3)),
])
def test_cambio_en_una_novedad_se_actualiza(sesion, nueva):
    cargar(sesion, [emp()], [nv()])
    r = cargar(sesion, [emp()], [nueva])
    assert (r.nuevas, r.actualizadas, r.sin_cambios) == (0, 1, 1)     # la novedad cambió; el empleado sigue igual
    n = sesion.execute(select(NovedadMensual)).scalar_one()
    sesion.refresh(n)
    assert (n.bonificacion, n.transporte) == (nueva.bonificacion, nueva.transporte)
    assert contar(sesion, Incapacidad) == (1 if nueva.incapacidad else 0)
    assert contar(sesion, Vacacion) == (1 if nueva.vacacion else 0)


def test_evento_que_cambia_sus_dias_o_fechas_se_reemplaza(sesion):
    cargar(sesion, [emp()], [nv(incapacidad=EventoLimpio(date(2022, 3, 2), date(2022, 3, 5), 4))])
    cargar(sesion, [emp()], [nv(incapacidad=EventoLimpio(date(2022, 3, 3), date(2022, 3, 9), 7))])
    assert sesion.execute(select(Incapacidad.fecha_inicio, Incapacidad.dias_reportados)).one() == (date(2022, 3, 3), 7)
    assert contar(sesion, Incapacidad) == 1


def test_evento_que_desaparece_se_elimina(sesion):
    cargar(sesion, [emp()], [nv(vacacion=EventoLimpio(date(2022, 3, 2), date(2022, 3, 5), 4))])
    r = cargar(sesion, [emp()], [nv()])
    assert r.actualizadas == 1 and contar(sesion, Vacacion) == 0


def test_no_borra_lo_que_no_viene_en_el_archivo(sesion):
    cargar(sesion, [emp(5001), emp(5002)], [nv(5001), nv(5002)])
    cargar(sesion, [emp(5001)], [nv(5001)])
    assert (contar(sesion, Empleado), contar(sesion, NovedadMensual)) == (2, 2)


def test_mismo_empleado_en_otro_periodo_crea_otra_novedad(sesion):
    cargar(sesion, [emp()], [nv()], mes=3)
    r = cargar(sesion, [], [nv(bonificacion="5.00")], mes=4)
    assert (r.nuevas, r.novedades_nuevas, r.periodo_nuevo) == (1, 1, True)
    assert (contar(sesion, NovedadMensual), contar(sesion, Periodo)) == (2, 2)


def test_catalogos_se_comparten_y_cargo_es_por_dependencia(sesion):
    cargar(sesion, [emp(5001, dependencia="Ventas", cargo="Director"), emp(5002, dependencia="Contabilidad", cargo="Director"),
                    emp(5003, dependencia="VENTAS", cargo="DIRECTOR")], [])
    assert (contar(sesion, Dependencia), contar(sesion, Cargo), contar(sesion, Eps), contar(sesion, Arl), contar(sesion, FondoPension)) == (2, 2, 1, 1, 1)
    assert sesion.get(Empleado, 5001).id_cargo == sesion.get(Empleado, 5003).id_cargo != sesion.get(Empleado, 5002).id_cargo


def test_cargar_vacio_no_falla(sesion):
    r = cargar(sesion, [], [])
    assert (r.nuevas, r.actualizadas, r.sin_cambios, contar(sesion, Periodo)) == (0, 0, 0, 0)


# ---------------------------------------------------------------------- servicio
def test_servicio_carga_y_la_recarga_es_idempotente(sesion):
    datos = dict(empleados=[empleado(5001), empleado(5002, cargo="Auditor")], novedades=[novedad(5001), novedad(5002)])
    i = cargar_nomina(libro_excel(**datos), sesion, PERIODO)
    assert (i.leidas, i.aceptadas, i.rechazadas, i.nuevas, i.actualizadas, i.sin_cambios) == (4, 4, 0, 4, 0, 0)
    assert i.aceptadas == i.nuevas + i.actualizadas + i.sin_cambios
    assert "03/2022" in i.fuente
    j = cargar_nomina(libro_excel(**datos), sesion, PERIODO)
    assert (j.nuevas, j.actualizadas, j.sin_cambios) == (0, 0, 4)


def test_servicio_detalles_y_a_dict(sesion):
    i = cargar_nomina(libro_excel([empleado(5001)], [novedad(5001, marca_inc="X", trabajados=26, dias_inc=4, inc_ini=d(2022, 3, 2), inc_fin=d(2022, 3, 5))]), sesion, PERIODO)
    assert i.detalles["Incapacidades"] == 1 and i.detalles["Vacaciones"] == 0
    assert (i.detalles["Dependencias nuevas"], i.detalles["Cargos nuevos"]) == (1, 1)
    dic = i.a_dict()
    assert dic["aceptadas"] == 2 and dic["rechazos"] == []


def test_servicio_rechaza_fila_mala_y_sigue(sesion):
    i = cargar_nomina(libro_excel([empleado(5001), empleado(5002, sueldo=0)], [novedad(5001)]), sesion, PERIODO)
    assert (i.leidas, i.aceptadas, i.rechazadas) == (3, 2, 1)
    assert (i.rechazos[0].origen, i.rechazos[0].linea) == ("Table 1", 3)
    assert contar(sesion, Empleado) == 1


def test_novedad_de_empleado_inexistente_se_rechaza(sesion):
    i = cargar_nomina(libro_excel([empleado(5001)], [novedad(5001), novedad(9999)]), sesion, PERIODO)
    assert i.rechazadas == 1 and "9999" in i.rechazos[0].motivo and "no existe" in i.rechazos[0].motivo
    assert (i.rechazos[0].origen, i.rechazos[0].linea) == ("Table 3", 3)
    assert i.aceptadas == 2 and contar(sesion, NovedadMensual) == 1


def test_novedad_de_empleado_que_ya_esta_en_la_base_se_acepta(sesion):
    cargar_nomina(libro_excel([empleado(5001)], []), sesion, PERIODO)
    i = cargar_nomina(libro_excel([], [novedad(5001, bonificacion=777)]), sesion, PeriodoNomina(2022, 4))
    assert (i.rechazadas, i.nuevas) == (0, 1)


def test_novedad_cuyo_empleado_fue_rechazado_tambien_se_rechaza(sesion):
    i = cargar_nomina(libro_excel([empleado(5001), empleado(5002, sueldo=-1)], [novedad(5001), novedad(5002)]), sesion, PERIODO)
    assert i.rechazadas == 2 and i.aceptadas == 2
    assert {r.origen for r in i.rechazos} == {"Table 1", "Table 3"}


def test_avisos_en_el_informe(sesion):
    i = cargar_nomina(libro_excel(
        [empleado(5001), empleado(5002), empleado(5003)],
        [novedad(5001, marca_inc="X", trabajados=25, dias_inc=5, inc_ini=d(2022, 5, 7), inc_fin=d(2022, 5, 12)),
         novedad(5002, trabajados=25), novedad(5003)]), sesion, PERIODO)
    texto = " ".join(i.advertencias)
    assert "distinto al de sus fechas" in texto and "no tocan el mes 03/2022" in texto and "no suman 30" in texto
    assert "5001" in texto and "5002" in texto
    assert i.rechazadas == 0


def test_avisos_de_filas_rechazadas_no_aparecen(sesion):
    i = cargar_nomina(libro_excel([empleado(5001)], [novedad(5001, trabajados=10), novedad(9999, trabajados=10)]), sesion, PERIODO)
    assert "no suman 30" in " ".join(i.advertencias)
    assert "9999" not in " ".join(i.advertencias)


@pytest.mark.parametrize("flujo,motivo", [
    (lambda: libro_excel([], []), "ninguna fila"),
    (lambda: libro_excel([empleado(sueldo=0)], [novedad(9999)]), "Ninguna fila es válida"),
])
def test_archivo_sin_filas_validas_cancela_la_carga(sesion, flujo, motivo):
    with pytest.raises(ErrorDeArchivo, match=f"(?i){motivo}"):
        cargar_nomina(flujo(), sesion, PERIODO)
    assert contar(sesion, Empleado) == 0


def test_mas_rechazos_que_aceptadas_avisa(sesion):
    i = cargar_nomina(libro_excel([empleado(5001), empleado(5002, sueldo=0), empleado(5003, sueldo=0), empleado(5004, sueldo=0)], [novedad(5001)]), sesion, PERIODO)
    assert any("más filas de las que se aceptaron" in a for a in i.advertencias)


# ---------------------------------------------------------------------- periodo
@pytest.mark.parametrize("texto,esperado", [("2022-03", (2022, 3)), ("2022-3", (2022, 3)), (" 2030-12 ", (2030, 12))])
def test_periodo_desde_texto(texto, esperado):
    p = PeriodoNomina.desde_texto(texto)
    assert (p.anio, p.mes) == esperado


@pytest.mark.parametrize("texto", ["2022", "03/2022", "2022-13", "2022-00", "1800-05", "abc", "", "2022-03-01"])
def test_periodo_invalido(texto):
    with pytest.raises(ValueError):
        PeriodoNomina.desde_texto(texto)


def test_periodo_como_texto():
    assert str(PeriodoNomina(2022, 3)) == "03/2022"
