"""Pruebas del paso EXTRAER de películas (no usan la base de datos)."""
import io

import pytest

from app.etl.common import ErrorDeArchivo
from app.etl.peliculas.extractor import LineaCruda, leer_lineas


def _leer(contenido: bytes) -> list[LineaCruda]:
    return list(leer_lineas(io.BytesIO(contenido)))


def test_lee_lineas_con_su_numero():
    assert _leer(b"a\nb\nc\n") == [LineaCruda(1, "a"), LineaCruda(2, "b"), LineaCruda(3, "c")]


def test_acepta_saltos_de_linea_de_windows():
    assert [l.texto for l in _leer(b"a\r\nb\r\n")] == ["a", "b"]


def test_ignora_lineas_en_blanco_pero_conserva_la_numeracion():
    lineas = _leer(b"a\n\n   \nb\n")
    assert [(l.numero, l.texto) for l in lineas] == [(1, "a"), (4, "b")]


def test_ultima_linea_sin_salto_final():
    assert [l.texto for l in _leer(b"a\nb")] == ["a", "b"]


def test_ignora_el_bom_inicial():
    assert _leer(b"\xef\xbb\xbf1::X (2000)::A\n")[0].texto == "1::X (2000)::A"


def test_conserva_tildes_y_enes():
    assert _leer("1::Amélie (2001)::Comedia\n2::El niño (2000)::Drama\n".encode("utf-8"))[0].texto.startswith("1::Amélie")


def test_archivo_vacio_no_entrega_lineas():
    assert _leer(b"") == []


def test_codificacion_invalida_cancela_la_carga_indicando_la_linea():
    contenido = b"1::Ok (2000)::A\n2::Am\xe9lie (2001)::B\n"   # \xe9 = 'é' en latin-1, no es UTF-8
    with pytest.raises(ErrorDeArchivo, match="línea 2"):
        _leer(contenido)
