"""Pruebas de los reportes de nómina (1 a 4). Los datos de prueba son pocos para poder calcular a mano cada resultado.

   cod  nombre           dependencia  cargo         EPS        pensión       sueldo
  5001  ANA              Tecnología   Analista      Nueva EPS  Colpensiones  3.000.000
  5002  BETO             Tecnología   Analista      Sura       Porvenir      2.000.000
  5003  CARLA            Tecnología   Desarrollador Nueva EPS  Porvenir      4.000.000
  5004  DANIEL           Ventas       Director      Sura       Colpensiones  5.000.000
  5005  ÁNGEL            Ventas       Director      Nueva EPS  Colpensiones  1.000.000
  (ÁNGEL lleva tilde: con la colación de la base debe ordenarse entre ANA y BETO, no al final)

  Novedades 03/2022: 5001 incapacidad 02-05/03 (4 d) y 5004 vacaciones 10-19/03 (10 d)
  Novedades 04/2022: 5001 vacaciones 11-12/04 (2 d) y 5002 incapacidad 01-03/04 (3 d)
"""
import pytest

from app.etl.nomina.service import PeriodoNomina, cargar_nomina
from excel_nomina import d, empleado, libro_excel, novedad

BASE = "/api/v1/reportes"
EMPLEADOS = [
    empleado(5001, "ANA", "Tecnología", "Analista", 20210311, "Nueva EPS", "Positiva", "Colpensiones", 3_000_000),
    empleado(5002, "BETO", "Tecnología", "Analista", 20200101, "Sura", "Positiva", "Porvenir", 2_000_000),
    empleado(5003, "CARLA", "Tecnología", "Desarrollador", 20190505, "Nueva EPS", "Positiva", "Porvenir", 4_000_000),
    empleado(5004, "DANIEL", "Ventas", "Director", 20180901, "Sura", "Positiva", "Colpensiones", 5_000_000),
    empleado(5005, "ÁNGEL", "Ventas", "Director", 20220115, "Nueva EPS", "Positiva", "Colpensiones", 1_000_000),
]
NOMBRES_ASC = ["ANA", "ÁNGEL", "BETO", "CARLA", "DANIEL"]


@pytest.fixture
def datos(sesion):
    marzo = [
        novedad(5001, marca_inc="X", trabajados=26, dias_inc=4, inc_ini=d(2022, 3, 2), inc_fin=d(2022, 3, 5)),
        novedad(5002), novedad(5003),
        novedad(5004, marca_vac="X", trabajados=20, dias_vac=10, vac_ini=d(2022, 3, 10), vac_fin=d(2022, 3, 19)),
        novedad(5005),
    ]
    abril = [
        novedad(5001, marca_vac="X", trabajados=28, dias_vac=2, vac_ini=d(2022, 4, 11), vac_fin=d(2022, 4, 12)),
        novedad(5002, marca_inc="X", trabajados=27, dias_inc=3, inc_ini=d(2022, 4, 1), inc_fin=d(2022, 4, 3)),
    ]
    cargar_nomina(libro_excel(EMPLEADOS, marzo), sesion, PeriodoNomina(2022, 3))
    cargar_nomina(libro_excel(EMPLEADOS, abril), sesion, PeriodoNomina(2022, 4))


def nombres(lista):
    return [e["nombre"] for e in lista]


# ============================================================ 1. NÓMINA
def test_1a_lista_y_total_ascendente(cliente, datos):
    r = cliente.get(f"{BASE}/nomina/empleados").json()
    assert r["total"] == 5
    assert nombres(r["empleados"]) == NOMBRES_ASC                 # ÁNGEL queda entre ANA y BETO


def test_1a_descendente(cliente, datos):
    r = cliente.get(f"{BASE}/nomina/empleados?orden=desc").json()
    assert nombres(r["empleados"]) == NOMBRES_ASC[::-1]


def test_orden_invalido_es_422(cliente, datos):
    assert cliente.get(f"{BASE}/nomina/empleados?orden=zigzag").status_code == 422


def test_sin_datos_devuelve_listas_vacias(cliente):
    r = cliente.get(f"{BASE}/nomina/empleados").json()
    assert r == {"total": 0, "empleados": []}
    assert cliente.get(f"{BASE}/nomina/por-cargo").json() == {"total": 0, "dependencias": []}
    assert cliente.get(f"{BASE}/nomina/grafico-dependencias").json()["etiquetas"] == []


def test_1b_por_dependencia(cliente, datos):
    r = cliente.get(f"{BASE}/nomina/por-dependencia").json()
    assert r["total"] == 5
    assert [(g["dependencia"], g["cantidad"]) for g in r["dependencias"]] == [("Tecnología", 3), ("Ventas", 2)]
    assert nombres(r["dependencias"][0]["empleados"]) == ["ANA", "BETO", "CARLA"]
    assert nombres(r["dependencias"][1]["empleados"]) == ["ÁNGEL", "DANIEL"]


def test_1b_descendente_invierte_nombres_no_dependencias(cliente, datos):
    r = cliente.get(f"{BASE}/nomina/por-dependencia?orden=desc").json()
    assert [g["dependencia"] for g in r["dependencias"]] == ["Tecnología", "Ventas"]       # siempre ascendentes
    assert nombres(r["dependencias"][0]["empleados"]) == ["CARLA", "BETO", "ANA"]


def test_1c_por_cargo_por_dependencia(cliente, datos):
    r = cliente.get(f"{BASE}/nomina/por-cargo").json()
    resumen = [(g["dependencia"], g["cantidad"], [(c["cargo"], c["cantidad"], nombres(c["empleados"])) for c in g["cargos"]])
               for g in r["dependencias"]]
    assert resumen == [
        ("Tecnología", 3, [("Analista", 2, ["ANA", "BETO"]), ("Desarrollador", 1, ["CARLA"])]),
        ("Ventas", 2, [("Director", 2, ["ÁNGEL", "DANIEL"])]),
    ]


def test_1c_descendente(cliente, datos):
    r = cliente.get(f"{BASE}/nomina/por-cargo?orden=desc").json()
    assert nombres(r["dependencias"][0]["cargos"][0]["empleados"]) == ["BETO", "ANA"]
    assert [c["cargo"] for c in r["dependencias"][0]["cargos"]] == ["Analista", "Desarrollador"]   # cargos siempre asc


def test_1d_grafico_torta(cliente, datos):
    g = cliente.get(f"{BASE}/nomina/grafico-dependencias").json()
    assert (g["tipo"], g["etiquetas"], g["series"][0]["valores"]) == ("torta", ["Tecnología", "Ventas"], [3, 2])


def test_1e_grafico_barras_por_cargo(cliente, datos):
    g = cliente.get(f"{BASE}/nomina/grafico-cargos").json()
    assert g["tipo"] == "barras"
    assert list(zip(g["grupos"], g["etiquetas"], g["series"][0]["valores"])) == [
        ("Tecnología", "Analista", 2), ("Tecnología", "Desarrollador", 1), ("Ventas", "Director", 2)]


def test_los_graficos_suman_el_total_de_empleados(cliente, datos):
    for ruta in ("nomina/grafico-dependencias", "nomina/grafico-cargos", "salud-pension/grafico-eps",
                 "salud-pension/grafico-pension"):
        assert sum(cliente.get(f"{BASE}/{ruta}").json()["series"][0]["valores"]) == 5, ruta
    for ruta in ("salud-pension/grafico-eps-dependencia", "salud-pension/grafico-pension-dependencia"):
        assert sum(sum(s["valores"]) for s in cliente.get(f"{BASE}/{ruta}").json()["series"]) == 5, ruta


# ====================================================== 2. INFORMACIÓN PERSONAL
def test_2_ficha_completa(cliente, datos):
    r = cliente.get(f"{BASE}/personal?codigo=5001").json()
    assert (r["total"], r["tasa_aporte_pension"]) == (1, 0.04)
    f = r["empleados"][0]
    assert (f["codigo"], f["nombre"], f["dependencia"], f["cargo"]) == (5001, "ANA", "Tecnología", "Analista")
    assert (f["fecha_ingreso"], f["eps"], f["fondo_pension"]) == ("11/03/2021", "Nueva EPS", "Colpensiones")
    assert (f["sueldo"], f["aporte_pension"]) == (3_000_000, 120_000)           # 4 % de 3.000.000


def test_2_aporte_redondea_a_centavos(cliente, sesion, datos):
    cargar_nomina(libro_excel([empleado(5009, "ZETA", sueldo="1234567.89")], []), sesion, PeriodoNomina(2022, 3))
    f = cliente.get(f"{BASE}/personal?codigo=5009").json()["empleados"][0]
    assert f["aporte_pension"] == 49382.72                                       # 1.234.567,89 x 0,04 = 49.382,7156


def test_2_discriminacion_de_novedades_por_periodo(cliente, datos):
    f = cliente.get(f"{BASE}/personal?codigo=5001").json()["empleados"][0]
    assert [n["periodo"] for n in f["novedades"]] == ["03/2022", "04/2022"]
    marzo, abril = f["novedades"]
    assert marzo["incapacidades"] == [{"fecha_inicio": "02/03/2022", "fecha_fin": "05/03/2022", "dias": 4}]
    assert (marzo["vacaciones"], marzo["dias_trabajados"]) == ([], 26)
    assert abril["vacaciones"] == [{"fecha_inicio": "11/04/2022", "fecha_fin": "12/04/2022", "dias": 2}]
    assert (abril["incapacidades"], abril["dias_trabajados"]) == ([], 28)
    assert (marzo["bonificacion"], marzo["transporte"]) == (100_000, 20_000)


def test_2_empleado_sin_eventos_tiene_30_dias(cliente, datos):
    f = cliente.get(f"{BASE}/personal?codigo=5003").json()["empleados"][0]
    assert f["novedades"][0]["dias_trabajados"] == 30


def test_2_todos_los_empleados_y_orden(cliente, datos):
    r = cliente.get(f"{BASE}/personal?orden=desc").json()
    assert (r["total"], nombres(r["empleados"])) == (5, NOMBRES_ASC[::-1])


def test_2_codigo_inexistente_devuelve_vacio_y_codigo_invalido_422(cliente, datos):
    assert cliente.get(f"{BASE}/personal?codigo=9999").json()["total"] == 0
    assert cliente.get(f"{BASE}/personal?codigo=0").status_code == 422
    assert cliente.get(f"{BASE}/personal?codigo=abc").status_code == 422


# ========================================================= 3. SALUD y PENSIÓN
def test_3a_3b_frecuencias(cliente, datos):
    eps = cliente.get(f"{BASE}/salud-pension/grafico-eps").json()
    assert dict(zip(eps["etiquetas"], eps["series"][0]["valores"])) == {"Nueva EPS": 3, "Sura": 2}
    pen = cliente.get(f"{BASE}/salud-pension/grafico-pension").json()
    assert dict(zip(pen["etiquetas"], pen["series"][0]["valores"])) == {"Colpensiones": 3, "Porvenir": 2}


def test_3c_eps_por_dependencia(cliente, datos):
    g = cliente.get(f"{BASE}/salud-pension/grafico-eps-dependencia").json()
    assert g["etiquetas"] == ["Tecnología", "Ventas"]
    assert {s["nombre"]: s["valores"] for s in g["series"]} == {"Nueva EPS": [2, 1], "Sura": [1, 1]}


def test_3d_pension_por_dependencia_rellena_con_ceros(cliente, datos):
    g = cliente.get(f"{BASE}/salud-pension/grafico-pension-dependencia").json()
    assert {s["nombre"]: s["valores"] for s in g["series"]} == {"Colpensiones": [1, 2], "Porvenir": [2, 0]}


def _por_cargo(r):
    return [(c["cargo"], c["cantidad"], [(e["entidad"], e["cantidad"], nombres(e["empleados"])) for e in c["entidades"]])
            for c in r["cargos"]]


def test_3e_por_cargo_y_eps(cliente, datos):
    r = cliente.get(f"{BASE}/salud-pension/por-cargo-eps").json()
    assert (r["total"], r["entidad_tipo"]) == (5, "EPS")
    assert _por_cargo(r) == [
        ("Analista", 2, [("Nueva EPS", 1, ["ANA"]), ("Sura", 1, ["BETO"])]),
        ("Desarrollador", 1, [("Nueva EPS", 1, ["CARLA"])]),
        ("Director", 2, [("Nueva EPS", 1, ["ÁNGEL"]), ("Sura", 1, ["DANIEL"])]),
    ]


def test_3f_por_cargo_y_pension_descendente(cliente, datos):
    r = cliente.get(f"{BASE}/salud-pension/por-cargo-pension?orden=desc").json()
    assert r["entidad_tipo"] == "Pensión"
    assert _por_cargo(r) == [
        ("Analista", 2, [("Colpensiones", 1, ["ANA"]), ("Porvenir", 1, ["BETO"])]),
        ("Desarrollador", 1, [("Porvenir", 1, ["CARLA"])]),
        ("Director", 2, [("Colpensiones", 2, ["DANIEL", "ÁNGEL"])]),      # nombres descendentes; cargo/entidad asc
    ]


# ============================================================ 4. NOVEDADES
def test_4a_un_solo_mes(cliente, datos):
    r = cliente.get(f"{BASE}/novedades/empleados?desde=03/2022&hasta=03/2022").json()
    assert (r["total"], nombres(r["empleados"])) == (2, ["ANA", "DANIEL"])
    ana = r["empleados"][0]
    assert (ana["dependencia"], ana["cargo"]) == ("Tecnología", "Analista")
    assert ana["novedades"] == [{"tipo": "Incapacidad", "periodo": "03/2022", "fecha_inicio": "02/03/2022",
                                 "fecha_fin": "05/03/2022", "dias": 4}]


def test_4a_rango_de_dos_meses_agrupa_por_empleado(cliente, datos):
    r = cliente.get(f"{BASE}/novedades/empleados?desde=03/2022&hasta=04/2022").json()
    assert (r["total"], nombres(r["empleados"])) == (3, ["ANA", "BETO", "DANIEL"])     # ANA cuenta una sola vez
    assert [(n["tipo"], n["periodo"]) for n in r["empleados"][0]["novedades"]] == [("Incapacidad", "03/2022"), ("Vacaciones", "04/2022")]


def test_4a_descendente(cliente, datos):
    r = cliente.get(f"{BASE}/novedades/empleados?desde=03/2022&hasta=04/2022&orden=desc").json()
    assert nombres(r["empleados"]) == ["DANIEL", "BETO", "ANA"]


def test_4a_rango_sin_novedades(cliente, datos):
    r = cliente.get(f"{BASE}/novedades/empleados?desde=01/2021&hasta=12/2021").json()
    assert (r["total"], r["empleados"]) == (0, [])


def test_4a_limites_del_rango_son_inclusivos_y_cruzan_de_anio(cliente, sesion, datos):
    cargar_nomina(libro_excel([empleado(5001)], [novedad(5001, marca_inc="X", trabajados=28, dias_inc=2, inc_ini=d(2023, 1, 1), inc_fin=d(2023, 1, 2))]),
                  sesion, PeriodoNomina(2023, 1))
    assert cliente.get(f"{BASE}/novedades/empleados?desde=12/2022&hasta=01/2023").json()["total"] == 1
    assert cliente.get(f"{BASE}/novedades/empleados?desde=01/2023&hasta=01/2023").json()["total"] == 1
    assert cliente.get(f"{BASE}/novedades/empleados?desde=02/2023&hasta=03/2023").json()["total"] == 0
    assert cliente.get(f"{BASE}/novedades/empleados?desde=11/2022&hasta=12/2022").json()["total"] == 0


def test_4b_resumen_por_dependencia_y_cargo(cliente, datos):
    r = cliente.get(f"{BASE}/novedades/resumen?desde=03/2022&hasta=04/2022").json()
    assert r["total"] == 3
    assert [(d["dependencia"], d["cantidad"], [(c["cargo"], c["cantidad"]) for c in d["cargos"]]) for d in r["dependencias"]] == [
        ("Tecnología", 2, [("Analista", 2)]),         # ANA y BETO (ANA tiene 2 novedades pero cuenta 1 vez)
        ("Ventas", 1, [("Director", 1)]),
    ]


@pytest.mark.parametrize("desde,hasta,mensaje", [
    ("3/2022", "03/2022", "formato MM/AAAA"), ("03/22", "03/2022", "formato MM/AAAA"), ("13/2022", "03/2022", "formato MM/AAAA"),
    ("00/2022", "03/2022", "formato MM/AAAA"), ("2022-03", "03/2022", "formato MM/AAAA"), ("03/2022", "abc", "'hasta'"),
    ("05/2022", "03/2022", "posterior"),
])
@pytest.mark.parametrize("ruta", ["novedades/empleados", "novedades/resumen"])
def test_4_rangos_invalidos_son_422_con_mensaje(cliente, datos, ruta, desde, hasta, mensaje):
    r = cliente.get(f"{BASE}/{ruta}", params={"desde": desde, "hasta": hasta})
    assert r.status_code == 422 and mensaje in r.json()["detail"]


@pytest.mark.parametrize("ruta", ["novedades/empleados", "novedades/resumen"])
def test_4_faltan_parametros_es_422(cliente, datos, ruta):
    assert cliente.get(f"{BASE}/{ruta}").status_code == 422
    assert cliente.get(f"{BASE}/{ruta}?desde=03/2022").status_code == 422


def test_3e_cargos_que_solo_difieren_en_tilde_se_agrupan(cliente, sesion, datos):
    """'Director' (Ventas) y 'Dírector' (Tecnología) son el mismo nombre para la base; el reporte no debe partirlos."""
    cargar_nomina(libro_excel([empleado(5006, "ZOE", "Tecnología", "Dírector", 20220101, "Sura", "Positiva", "Porvenir", 1_000_000)], []),
                  sesion, PeriodoNomina(2022, 3))
    r = cliente.get(f"{BASE}/salud-pension/por-cargo-eps").json()
    directores = [c for c in r["cargos"] if c["cargo"].lower().replace("í", "i") == "director"]
    assert len(directores) == 1 and directores[0]["cantidad"] == 3


def test_3a_3b_las_etiquetas_salen_en_orden_ascendente(cliente, datos):
    assert cliente.get(f"{BASE}/salud-pension/grafico-eps").json()["etiquetas"] == ["Nueva EPS", "Sura"]
    assert cliente.get(f"{BASE}/salud-pension/grafico-pension").json()["etiquetas"] == ["Colpensiones", "Porvenir"]


def test_2_orden_por_defecto_es_ascendente(cliente, datos):
    assert nombres(cliente.get(f"{BASE}/personal").json()["empleados"]) == NOMBRES_ASC
    assert nombres(cliente.get(f"{BASE}/novedades/empleados?desde=03/2022&hasta=04/2022").json()["empleados"]) == ["ANA", "BETO", "DANIEL"]


def test_3e_cargos_que_solo_difieren_en_mayusculas_se_agrupan(cliente, sesion, datos):
    cargar_nomina(libro_excel([empleado(5006, "ZOE", "Tecnología", "DIRECTOR", 20220101, "Sura", "Positiva", "Porvenir", 1_000_000)], []),
                  sesion, PeriodoNomina(2022, 3))
    r = cliente.get(f"{BASE}/salud-pension/por-cargo-eps").json()
    assert [c["cantidad"] for c in r["cargos"] if c["cargo"].lower() == "director"] == [3]
