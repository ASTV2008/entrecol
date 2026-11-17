"""Pruebas del reporte 5 (películas y libros). Datos sembrados a mano para calcular cada resultado.

PELÍCULAS (id título año [géneros])
   1 Beta        1990 [Action, Comedy]          4 Delta       2000 [Drama]
   2 Alfa        1990 [Comedy]                  5 Sin genero  1995 []
   3 Ángel       1995 [Action, Comedy, Drama]   6 Épsilon     1991 [Action, Comedy]
   (Ángel y Épsilon llevan tilde: la base debe ordenarlas entre A/B y D/F, no al final)

LIBROS (id título rating votos año)
   2000: 10 Libro A 5.00/5 · 11 Libro B 5.00/50 · 12 Libro C 4.50/10 · 13 Libro D 4.00/10 · 14 Libro E 3.00/10
         15 Libro F 2.00/10 · 16 Libro G 1.00/10 · 17 Libro Sin 0.00/0 (sin calificar)
   2001: 20 Único 3.50/3 · 21 Ábaco 4.00/1        (solo 2 libros: cada uno sale en "mejores" y en "peores")
   2003: 50 Tres 4.80/7        1999: 40 Solo sin votos 0.00/0        sin fecha: 30 Sin fecha 5.00/100
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import insert

from app.models import Editorial, Genero, Idioma, Libro, Pelicula, pelicula_genero

BASE = "/api/v1/reportes/entretenimiento"
PELICULAS = [(1, "Beta", 1990, ["Action", "Comedy"]), (2, "Alfa", 1990, ["Comedy"]),
             (3, "Ángel", 1995, ["Action", "Comedy", "Drama"]), (4, "Delta", 2000, ["Drama"]),
             (5, "Sin genero", 1995, []), (6, "Épsilon", 1991, ["Action", "Comedy"])]
LIBROS = [(10, "Libro A", "5.00", 5, date(2000, 1, 1)), (11, "Libro B", "5.00", 50, date(2000, 2, 1)),
          (12, "Libro C", "4.50", 10, date(2000, 3, 1)), (13, "Libro D", "4.00", 10, date(2000, 4, 1)),
          (14, "Libro E", "3.00", 10, date(2000, 5, 1)), (15, "Libro F", "2.00", 10, date(2000, 6, 1)),
          (16, "Libro G", "1.00", 10, date(2000, 7, 1)), (17, "Libro Sin", "0.00", 0, date(2000, 8, 1)),
          (20, "Único", "3.50", 3, date(2001, 1, 1)), (21, "Ábaco", "4.00", 1, date(2001, 2, 1)),
          (50, "Tres", "4.80", 7, date(2003, 5, 5)), (40, "Solo sin votos", "0.00", 0, date(1999, 9, 9)),
          (30, "Sin fecha", "5.00", 100, None)]


@pytest.fixture
def datos(sesion):
    # Ids EXPLÍCITOS: id_genero es TINYINT (máx. 255) y un rollback no devuelve los autoincrementales,
    # así que numerar 4 géneros por prueba agotaría el contador a mitad de la ejecución.
    ids = {nombre: i for i, nombre in enumerate(("Action", "Comedy", "Drama", "Romance"), start=1)}
    for nombre, id_ in ids.items():
        sesion.execute(insert(Genero).values(id_genero=id_, nombre=nombre))
    for id_, titulo, anio, generos in PELICULAS:
        sesion.execute(insert(Pelicula).values(id_pelicula=id_, titulo=titulo, anio_estreno=anio))
        for g in generos:
            sesion.execute(insert(pelicula_genero).values(id_pelicula=id_, id_genero=ids[g]))
    id_ed, id_idioma = 1, 1
    sesion.execute(insert(Editorial).values(id_editorial=id_ed, nombre="Ed"))
    sesion.execute(insert(Idioma).values(id_idioma=id_idioma, codigo="eng"))
    for id_, titulo, rating, votos, fecha in LIBROS:
        sesion.execute(insert(Libro).values(
            id_libro=id_, titulo=titulo, isbn="0", isbn13="0", num_paginas=100, fecha_publicacion=fecha,
            calificacion_promedio=Decimal(rating), num_calificaciones=votos, num_resenas=0, id_editorial=id_ed, id_idioma=id_idioma))


titulos = lambda lista: [x["titulo"] for x in lista]
resumen = lambda lista: [(x["posicion"], x["titulo"]) for x in lista]


# ======================================================== 5a películas por género
def test_5a_rango_corto(cliente, datos):
    r = cliente.get(f"{BASE}/peliculas-por-genero?desde=1990&hasta=1991").json()
    assert [(g["genero"], g["cantidad"], titulos(g["peliculas"])) for g in r["generos"]] == [
        ("Action", 2, ["Beta", "Épsilon"]), ("Comedy", 3, ["Alfa", "Beta", "Épsilon"])]
    assert r["total_peliculas"] == 3                      # Beta y Épsilon están en 2 géneros pero cuentan 1 vez
    assert "varios géneros" in r["nota"]


def test_5a_todo_el_rango_y_orden_descendente(cliente, datos):
    r = cliente.get(f"{BASE}/peliculas-por-genero?desde=1990&hasta=2000").json()
    assert [(g["genero"], g["cantidad"]) for g in r["generos"]] == [("Action", 3), ("Comedy", 4), ("Drama", 2)]
    assert titulos(r["generos"][1]["peliculas"]) == ["Alfa", "Ángel", "Beta", "Épsilon"]      # tilde bien ordenada
    assert r["total_peliculas"] == 5                       # la película sin géneros no está en ningún grupo
    d = cliente.get(f"{BASE}/peliculas-por-genero?desde=1990&hasta=2000&orden=desc").json()
    assert titulos(d["generos"][1]["peliculas"]) == ["Épsilon", "Beta", "Ángel", "Alfa"]
    assert [g["genero"] for g in d["generos"]] == ["Action", "Comedy", "Drama"]               # géneros siempre ascendentes


def test_5a_limites_inclusivos_y_rango_vacio(cliente, datos):
    assert cliente.get(f"{BASE}/peliculas-por-genero?desde=1995&hasta=1995").json()["total_peliculas"] == 1   # solo Ángel
    r = cliente.get(f"{BASE}/peliculas-por-genero?desde=1900&hasta=1950").json()
    assert (r["generos"], r["total_peliculas"]) == ([], 0)


@pytest.mark.parametrize("consulta", ["desde=1990", "hasta=2000", "desde=2000&hasta=1990", "desde=0&hasta=2000", "desde=abc&hasta=2000",
                                      "desde=1990&hasta=10000", "desde=1990&hasta=2000&orden=zigzag"])
def test_5a_parametros_invalidos(cliente, datos, consulta):
    assert cliente.get(f"{BASE}/peliculas-por-genero?{consulta}").status_code == 422


# ================================================== 5d películas con N géneros
@pytest.mark.parametrize("n,esperado", [
    (0, [("Sin genero", [])]), (1, [("Alfa", ["Comedy"]), ("Delta", ["Drama"])]),
    (2, [("Beta", ["Action", "Comedy"]), ("Épsilon", ["Action", "Comedy"])]), (3, [("Ángel", ["Action", "Comedy", "Drama"])]), (4, [])])
def test_5d_exactamente_n_generos(cliente, datos, n, esperado):
    r = cliente.get(f"{BASE}/peliculas/por-numero-de-generos?n={n}").json()
    assert (r["n"], r["total"]) == (n, len(esperado))
    assert [(p["titulo"], p["generos"]) for p in r["peliculas"]] == esperado


def test_5d_descendente_y_anio(cliente, datos):
    r = cliente.get(f"{BASE}/peliculas/por-numero-de-generos?n=1&orden=desc").json()
    assert [(p["titulo"], p["anio"]) for p in r["peliculas"]] == [("Delta", 2000), ("Alfa", 1990)]


@pytest.mark.parametrize("consulta", ["", "n=-1", "n=31", "n=x", "n=1&orden=zigzag"])
def test_5d_parametros_invalidos(cliente, datos, consulta):
    assert cliente.get(f"{BASE}/peliculas/por-numero-de-generos?{consulta}").status_code == 422


# ========================================================== 5e gráfico de géneros
def test_5e_frecuencia_por_genero(cliente, datos):
    g = cliente.get(f"{BASE}/graficos/peliculas-por-genero").json()
    assert g["tipo"] == "barras"
    assert list(zip(g["etiquetas"], g["series"][0]["valores"])) == [("Action", 3), ("Comedy", 4), ("Drama", 2), ("Romance", 0)]
    assert "varios géneros" in g["nota"]


# ============================================================== 5b Top N libros
def test_5b_top_3_con_desempate_por_votos(cliente, datos):
    r = cliente.get(f"{BASE}/libros/top?n=3").json()
    assert (r["n"], r["total"]) == (3, 3)
    # Hay tres libros de 5,0: gana el de más votos (Sin fecha=100), luego B (50), luego A (5). Se muestran por título.
    assert resumen(r["libros"]) == [(3, "Libro A"), (2, "Libro B"), (1, "Sin fecha")]
    assert "Desempate" in r["criterio"]


def test_5b_orden_descendente_conserva_la_posicion(cliente, datos):
    r = cliente.get(f"{BASE}/libros/top?n=3&orden=desc").json()
    assert resumen(r["libros"]) == [(1, "Sin fecha"), (2, "Libro B"), (3, "Libro A")]


def test_5b_campos_del_libro(cliente, datos):
    b = next(x for x in cliente.get(f"{BASE}/libros/top?n=3").json()["libros"] if x["titulo"] == "Libro B")
    assert (b["id_libro"], b["calificacion"], b["num_calificaciones"], b["anio"]) == (11, 5.0, 50, 2000)
    s = next(x for x in cliente.get(f"{BASE}/libros/top?n=1").json()["libros"])
    assert (s["titulo"], s["anio"]) == ("Sin fecha", None)            # el libro sin fecha sí entra al Top global


def test_5b_top_posiciones_siguen_el_orden_completo(cliente, datos):
    r = cliente.get(f"{BASE}/libros/top?n=7").json()
    por_pos = {x["posicion"]: x["titulo"] for x in r["libros"]}
    assert por_pos == {1: "Sin fecha", 2: "Libro B", 3: "Libro A", 4: "Tres", 5: "Libro C", 6: "Libro D", 7: "Ábaco"}
    # 4,0: Libro D (10 votos) antes que Ábaco (1 voto)


def test_5b_n_mayor_que_los_libros_calificados_devuelve_los_que_hay(cliente, datos):
    assert cliente.get(f"{BASE}/libros/top?n=100").json()["total"] == 11        # 13 libros menos los 2 sin calificar


def test_5b_libros_sin_calificar_nunca_entran(cliente, datos):
    ids = [x["id_libro"] for x in cliente.get(f"{BASE}/libros/top?n=100").json()["libros"]]
    assert 17 not in ids and 40 not in ids


def test_5b_minimo_de_calificaciones(cliente, datos):
    r = cliente.get(f"{BASE}/libros/top?n=3&min_calificaciones=20").json()
    assert (r["total"], resumen(r["libros"])) == (2, [(2, "Libro B"), (1, "Sin fecha")])
    assert "al menos 20" in r["criterio"]


@pytest.mark.parametrize("consulta", ["", "n=0", "n=101", "n=x", "n=3&min_calificaciones=0", "n=3&orden=zigzag"])
def test_5b_parametros_invalidos(cliente, datos, consulta):
    assert cliente.get(f"{BASE}/libros/top?{consulta}").status_code == 422


# ========================================================= 5c Top 5 por año
def por_anio(r):
    return {a["anio"]: a for a in r["anios"]}


def test_5c_anio_con_mas_de_cinco_libros(cliente, datos):
    a = por_anio(cliente.get(f"{BASE}/libros/top-por-anio").json())[2000]
    assert resumen(a["mejores"]) == [(2, "Libro A"), (1, "Libro B"), (3, "Libro C"), (4, "Libro D"), (5, "Libro E")]
    assert resumen(a["peores"]) == [(5, "Libro C"), (4, "Libro D"), (3, "Libro E"), (2, "Libro F"), (1, "Libro G")]


def test_5c_el_libro_sin_calificar_no_es_el_peor(cliente, datos):
    a = por_anio(cliente.get(f"{BASE}/libros/top-por-anio").json())[2000]
    assert "Libro Sin" not in titulos(a["peores"]) + titulos(a["mejores"])


def test_5c_anios_incluidos_y_excluidos(cliente, datos):
    r = cliente.get(f"{BASE}/libros/top-por-anio").json()
    assert [a["anio"] for a in r["anios"]] == [2000, 2001, 2003]       # 1999 (solo sin calificar) y el libro sin fecha no salen


def test_5c_anio_chico_el_mismo_libro_sale_en_mejores_y_en_peores(cliente, datos):
    a = por_anio(cliente.get(f"{BASE}/libros/top-por-anio").json())[2001]
    assert resumen(a["mejores"]) == [(1, "Ábaco"), (2, "Único")]        # 4,0 y 3,5; 'Ábaco' ordenado entre las A
    assert resumen(a["peores"]) == [(2, "Ábaco"), (1, "Único")]
    a = por_anio(cliente.get(f"{BASE}/libros/top-por-anio").json())[2003]
    assert (resumen(a["mejores"]), resumen(a["peores"])) == ([(1, "Tres")], [(1, "Tres")])


def test_5c_orden_descendente(cliente, datos):
    a = por_anio(cliente.get(f"{BASE}/libros/top-por-anio?orden=desc").json())[2000]
    assert titulos(a["mejores"]) == ["Libro E", "Libro D", "Libro C", "Libro B", "Libro A"]
    assert titulos(a["peores"]) == ["Libro G", "Libro F", "Libro E", "Libro D", "Libro C"]


def test_5c_filtro_por_rango_de_anios(cliente, datos):
    assert [a["anio"] for a in cliente.get(f"{BASE}/libros/top-por-anio?desde=2001&hasta=2003").json()["anios"]] == [2001, 2003]
    assert [a["anio"] for a in cliente.get(f"{BASE}/libros/top-por-anio?desde=2002").json()["anios"]] == [2003]
    assert [a["anio"] for a in cliente.get(f"{BASE}/libros/top-por-anio?hasta=2000").json()["anios"]] == [2000]
    assert cliente.get(f"{BASE}/libros/top-por-anio?desde=2010&hasta=2020").json()["anios"] == []


def test_5c_minimo_de_calificaciones(cliente, datos):
    r = cliente.get(f"{BASE}/libros/top-por-anio?min_calificaciones=10").json()
    assert [a["anio"] for a in r["anios"]] == [2000]
    assert titulos(r["anios"][0]["mejores"]) == ["Libro B", "Libro C", "Libro D", "Libro E", "Libro F"]
    assert titulos(r["anios"][0]["peores"]) == ["Libro C", "Libro D", "Libro E", "Libro F", "Libro G"]


@pytest.mark.parametrize("consulta", ["desde=2010&hasta=2000", "desde=0", "hasta=10000", "orden=zigzag", "min_calificaciones=0"])
def test_5c_parametros_invalidos(cliente, datos, consulta):
    assert cliente.get(f"{BASE}/libros/top-por-anio?{consulta}").status_code == 422


# ============================================================= 5f libros por año
def test_5f_frecuencia_con_anios_vacios_en_cero(cliente, datos):
    g = cliente.get(f"{BASE}/graficos/libros-por-anio?desde=2000&hasta=2003").json()
    assert g["tipo"] == "barras"
    assert list(zip(g["etiquetas"], g["series"][0]["valores"])) == [("2000", 8), ("2001", 2), ("2002", 0), ("2003", 1)]


def test_5f_cuenta_todos_los_libros_aunque_no_esten_calificados(cliente, datos):
    g = cliente.get(f"{BASE}/graficos/libros-por-anio?desde=1999&hasta=2000").json()
    assert g["series"][0]["valores"] == [1, 8]


def test_5f_un_solo_anio_y_sin_fecha_no_cuenta(cliente, datos):
    assert cliente.get(f"{BASE}/graficos/libros-por-anio?desde=2003&hasta=2003").json()["series"][0]["valores"] == [1]
    g = cliente.get(f"{BASE}/graficos/libros-por-anio?desde=1900&hasta=2100").json()
    assert sum(g["series"][0]["valores"]) == 12                       # 13 libros menos el que no tiene fecha


@pytest.mark.parametrize("consulta,detalle", [("desde=2010&hasta=2000", "posterior"), ("desde=1&hasta=9999", "máximo"),
                                              ("desde=1000&hasta=1300", "máximo")])      # 301 años: un año de más
def test_5f_rangos_invalidos(cliente, datos, consulta, detalle):
    r = cliente.get(f"{BASE}/graficos/libros-por-anio?{consulta}")
    assert r.status_code == 422 and detalle in r.json()["detail"]


def test_5f_rango_de_300_anios_es_el_maximo_permitido(cliente, datos):
    assert len(cliente.get(f"{BASE}/graficos/libros-por-anio?desde=1000&hasta=1299").json()["etiquetas"]) == 300


@pytest.mark.parametrize("consulta", ["", "desde=2000", "hasta=2003", "desde=x&hasta=2003"])
def test_5f_faltan_parametros(cliente, datos, consulta):
    assert cliente.get(f"{BASE}/graficos/libros-por-anio?{consulta}").status_code == 422


def test_sin_datos_todo_vacio(cliente):
    assert cliente.get(f"{BASE}/libros/top?n=5").json()["libros"] == []
    assert cliente.get(f"{BASE}/libros/top-por-anio").json()["anios"] == []
    assert cliente.get(f"{BASE}/peliculas/por-numero-de-generos?n=1").json()["peliculas"] == []
    assert cliente.get(f"{BASE}/peliculas-por-genero?desde=1900&hasta=2020").json()["generos"] == []
    assert cliente.get(f"{BASE}/graficos/peliculas-por-genero").json()["etiquetas"] == []


def test_5c_desempate_final_por_id_cuando_empatan_rating_y_votos(cliente, sesion, datos):
    """Dos libros con el mismo rating Y los mismos votos: manda el id menor (resultado determinista), no el título."""
    id_ed, id_idioma = 1, 1                      # los que sembró el fixture `datos`
    for id_, titulo in ((61, "Aaa"), (60, "Zzz")):
        sesion.execute(insert(Libro).values(
            id_libro=id_, titulo=titulo, isbn="0", isbn13="0", num_paginas=1, fecha_publicacion=date(2010, 1, 1),
            calificacion_promedio=Decimal("4.00"), num_calificaciones=5, num_resenas=0, id_editorial=id_ed, id_idioma=id_idioma))
    a = por_anio(cliente.get(f"{BASE}/libros/top-por-anio?desde=2010&hasta=2010").json())[2010]
    assert {x["titulo"]: x["posicion"] for x in a["mejores"]} == {"Zzz": 1, "Aaa": 2}
    assert {x["titulo"]: x["posicion"] for x in a["peores"]} == {"Zzz": 1, "Aaa": 2}
