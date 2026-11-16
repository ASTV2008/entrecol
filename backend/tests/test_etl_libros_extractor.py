"""Pruebas del paso EXTRAER de libros (no usan la base de datos)."""
import io
import json

import pytest

from app.etl.common import ErrorDeArchivo
from app.etl.libros.extractor import RegistroCrudo, leer_registros


def _leer(contenido: bytes) -> list[RegistroCrudo]:
    return list(leer_registros(io.BytesIO(contenido)))


def test_entrega_cada_registro_con_su_posicion():
    regs = _leer(json.dumps([{"bookID": 1}, {"bookID": 2}]).encode())
    assert regs == [RegistroCrudo(1, {"bookID": 1}), RegistroCrudo(2, {"bookID": 2})]


def test_lista_vacia_no_entrega_registros():
    assert _leer(b"[]") == []


def test_ignora_el_bom_inicial():
    assert _leer(b"\xef\xbb\xbf" + json.dumps([{"a": 1}]).encode())[0].datos == {"a": 1}


def test_conserva_tildes_y_enes():
    assert _leer(json.dumps([{"t": "Cien años de soledad"}], ensure_ascii=False).encode("utf-8"))[0].datos["t"] == "Cien años de soledad"


def test_elementos_que_no_son_objetos_se_entregan_para_que_el_transformador_los_rechace():
    assert [r.datos for r in _leer(b'[1, "x", null]')] == [1, "x", None]


def test_json_invalido_cancela_la_carga_indicando_donde():
    with pytest.raises(ErrorDeArchivo, match="JSON válido.*línea"):
        _leer(b'[{"bookID": 1},\n{"bookID": ]')


def test_si_no_es_una_lista_cancela_la_carga():
    with pytest.raises(ErrorDeArchivo, match="lista de libros"):
        _leer(b'{"bookID": 1}')


def test_codificacion_invalida_cancela_la_carga():
    with pytest.raises(ErrorDeArchivo, match="UTF-8"):
        _leer(b'[{"t": "Am\xe9lie"}]')


def test_archivo_vacio_cancela_la_carga():
    with pytest.raises(ErrorDeArchivo, match="JSON válido"):
        _leer(b"")
