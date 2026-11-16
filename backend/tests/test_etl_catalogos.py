"""Pruebas del asegurador de catálogos: la BASE decide qué nombres son el mismo."""
from sqlalchemy import func, select

from app.etl import catalogos
from app.etl.catalogos import asegurar_catalogo
from app.models import Editorial


def _asegurar(sesion, *nombres):
    return asegurar_catalogo(sesion, Editorial.id_editorial, Editorial.nombre, nombres)


def _filas(sesion) -> list[str]:
    return [n for (n,) in sesion.execute(select(Editorial.nombre).order_by(Editorial.id_editorial))]


def test_crea_los_nombres_nuevos_y_devuelve_sus_ids(sesion):
    r = _asegurar(sesion, "Penguin", "Scholastic")
    assert r.nuevos == 2 and set(r.ids) == {"Penguin", "Scholastic"}
    assert len(set(r.ids.values())) == 2


def test_mayusculas_y_tildes_son_el_mismo_nombre_y_se_conserva_la_primera_grafia(sesion):
    r = _asegurar(sesion, "Ace", "ACE", "ace", "Éditions 10/18", "Editions 10/18")
    assert r.nuevos == 2
    assert r.ids["Ace"] == r.ids["ACE"] == r.ids["ace"]
    assert r.ids["Éditions 10/18"] == r.ids["Editions 10/18"]
    assert _filas(sesion) == ["Ace", "Éditions 10/18"]
    assert r.unificados == 3                                   # ACE, ace y Editions sobran
    assert ("Ace", "ACE", "ace") in r.equivalentes


def test_un_nombre_que_ya_existe_con_otra_grafia_no_crea_filas(sesion):
    _asegurar(sesion, "Éditions 10/18")
    r = _asegurar(sesion, "EDITIONS 10/18")
    assert r.nuevos == 0
    assert _filas(sesion) == ["Éditions 10/18"]


def test_repetir_la_llamada_no_crea_nada(sesion):
    primera = _asegurar(sesion, "A", "B", "C")
    segunda = _asegurar(sesion, "A", "B", "C")
    assert segunda.nuevos == 0 and segunda.ids == primera.ids


def test_lista_vacia(sesion):
    r = _asegurar(sesion)
    assert r.ids == {} and r.nuevos == 0 and r.unificados == 0


def test_repetidos_exactos_cuentan_una_vez(sesion):
    r = _asegurar(sesion, "A", "A", "A")
    assert r.nuevos == 1 and len(r.ids) == 1


def test_funciona_con_mas_nombres_que_el_tamano_de_los_lotes(sesion, monkeypatch):
    monkeypatch.setattr(catalogos, "TAMANO_CONSULTA", 3)
    monkeypatch.setattr(catalogos, "TAMANO_INSERCION", 2)
    nombres = [f"Editorial {i}" for i in range(10)] + ["EDITORIAL 3", "editorial 7", "Éditorial 5"]
    r = _asegurar(sesion, *nombres)
    assert r.nuevos == 10
    assert r.ids["EDITORIAL 3"] == r.ids["Editorial 3"] and r.ids["Éditorial 5"] == r.ids["Editorial 5"]
    assert sesion.execute(select(func.count()).select_from(Editorial)).scalar_one() == 10
    assert _asegurar(sesion, *nombres).nuevos == 0
