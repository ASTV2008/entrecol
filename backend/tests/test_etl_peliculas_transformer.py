"""Pruebas del paso TRANSFORMAR de películas (no usan la base de datos)."""
import pytest

from app.etl.common import Rechazo
from app.etl.peliculas.extractor import LineaCruda
from app.etl.peliculas.transformer import PeliculaLimpia, TransformadorPeliculas


def _transformar(texto: str, numero: int = 1):
    return TransformadorPeliculas().transformar(LineaCruda(numero, texto))


def test_linea_normal_separa_id_titulo_anio_y_generos():
    r = _transformar("1::Toy Story (1995)::Adventure|Animation|Children|Comedy|Fantasy")
    assert r == PeliculaLimpia(1, "Toy Story", 1995, ("Adventure", "Animation", "Children", "Comedy", "Fantasy"))


def test_titulo_con_parentesis_propios_solo_toma_el_ultimo_como_anio():
    r = _transformar("5::Hellraiser: Hellseeker (a.k.a. Hellraiser 6) (2002)::Horror")
    assert (r.titulo, r.anio_estreno) == ("Hellraiser: Hellseeker (a.k.a. Hellraiser 6)", 2002)


def test_titulo_que_empieza_con_parentesis_o_numero():
    assert _transformar("7::(500) Days of Summer (2009)::Romance").titulo == "(500) Days of Summer"
    assert _transformar("8::2001: A Space Odyssey (1968)::Sci-Fi").titulo == "2001: A Space Odyssey"


def test_sin_generos_listados_no_crea_ningun_genero():
    r = _transformar("8606::Pull My Daisy (1958)::(no genres listed)")
    assert r.generos == ()


def test_generos_se_limpian_espacios_vacios_y_repetidos():
    r = _transformar("1::X (2000):: Comedy | Drama ||comedy|")
    assert r.generos == ("Comedy", "Drama")


def test_un_solo_genero():
    assert _transformar("3::X (2000)::Comedy").generos == ("Comedy",)


def test_conserva_tildes():
    assert _transformar("9::Amélie (2001)::Comedy|Romance").titulo == "Amélie"


@pytest.mark.parametrize(
    "linea, fragmento_del_motivo",
    [
        ("1::Toy Story (1995)", "3 campos"),                        # faltan campos
        ("1::Toy Story (1995)::Comedy::sobra", "3 campos"),         # sobran campos
        ("abc::Toy Story (1995)::Comedy", "no es un número"),       # id no numérico
        ("-3::Toy Story (1995)::Comedy", "no es un número"),        # id negativo
        ("0::Toy Story (1995)::Comedy", "fuera del rango"),         # id cero
        ("99999999999::Toy Story (1995)::Comedy", "fuera del rango"),
        ("1::Toy Story::Comedy", "año entre paréntesis"),           # sin año
        ("1::Toy Story (95)::Comedy", "año entre paréntesis"),      # año de 2 dígitos
        ("1::(1995)::Comedy", "año entre paréntesis"),              # solo año, sin título
        ("1::Toy Story (1700)::Comedy", "fuera del rango"),         # año imposible
        ("1::Toy Story (2500)::Comedy", "fuera del rango"),
    ],
)
def test_filas_invalidas_se_rechazan_con_motivo(linea, fragmento_del_motivo):
    r = _transformar(linea, numero=42)
    assert isinstance(r, Rechazo)
    assert fragmento_del_motivo in r.motivo
    assert r.linea == 42
    assert r.contenido == linea[:200]


def test_titulo_demasiado_largo_se_rechaza():
    r = _transformar(f"1::{'A' * 201} (2000)::Comedy")
    assert isinstance(r, Rechazo) and "201 caracteres" in r.motivo


def test_titulo_en_el_limite_se_acepta():
    assert not isinstance(_transformar(f"1::{'A' * 200} (2000)::Comedy"), Rechazo)


def test_genero_demasiado_largo_se_rechaza():
    r = _transformar(f"1::X (2000)::{'G' * 31}")
    assert isinstance(r, Rechazo) and "supera 30" in r.motivo


def test_id_duplicado_conserva_la_primera_aparicion_y_rechaza_la_segunda():
    t = TransformadorPeliculas()
    primera = t.transformar(LineaCruda(1, "1::Toy Story (1995)::Comedy"))
    segunda = t.transformar(LineaCruda(2, "1::Otra cosa (2000)::Drama"))
    assert isinstance(primera, PeliculaLimpia)
    assert isinstance(segunda, Rechazo) and "duplicado" in segunda.motivo


def test_una_fila_rechazada_no_bloquea_su_id():
    """Si la primera aparición era inválida, la segunda (válida) sí se acepta."""
    t = TransformadorPeliculas()
    assert isinstance(t.transformar(LineaCruda(1, "1::Sin anio::Comedy")), Rechazo)
    assert isinstance(t.transformar(LineaCruda(2, "1::Con anio (2000)::Comedy")), PeliculaLimpia)
