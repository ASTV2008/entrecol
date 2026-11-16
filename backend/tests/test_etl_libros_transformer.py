"""Pruebas del paso TRANSFORMAR de libros (no usan la base de datos)."""
from datetime import date
from decimal import Decimal

import pytest

from app.etl.common import Rechazo
from app.etl.libros.extractor import RegistroCrudo
from app.etl.libros.transformer import LibroLimpio, TransformadorLibros


def base(**cambios) -> dict:
    """Un registro válido (el primero de Books.json); los tests le cambian lo que necesiten."""
    registro = {
        "bookID": 1, "title": "Harry Potter and the Half-Blood Prince (Harry Potter  #6)",
        "authors": "J.K. Rowling/Mary GrandPré", "average_rating": "4.57", "isbn": "0439785960",
        "isbn13": "9780439785969", "language_code": "eng", "num_pages": "652", "ratings_count": 2095690,
        "text_reviews_count": 27591, "publication_date": "9/16/2006", "publisher": "Scholastic Inc.", "FIELD13": "",
    }
    registro.update(cambios)
    return registro


def transformar(datos, numero=1, transformador=None):
    t = transformador or TransformadorLibros()
    return t.transformar(RegistroCrudo(numero, datos)), t


# Los 4 registros desplazados REALES de Books.json, tal cual vienen en el archivo
DESPLAZADOS = [
    {"bookID": 12224, "title": "Streetcar Suburbs: The Process of Growth in Boston  1870-1900", "authors": "Sam Bass Warner",
     "average_rating": " Jr./Sam B. Warner", "isbn": "3.58", "isbn13": "0674842111", "language_code": "9780674842113",
     "num_pages": "en-US", "ratings_count": 236, "text_reviews_count": 61, "publication_date": "6",
     "publisher": "4/20/2004", "FIELD13": "Harvard University Press"},
    {"bookID": 16914, "title": "The Tolkien Fan's Medieval Reader", "authors": "David E. Smith (Turgon of TheOneRing.net",
     "average_rating": " one of the founding members of this Tolkien website)/Verlyn Flieger/Turgon (=David E. Smith)",
     "isbn": "3.58", "isbn13": "1593600119", "language_code": "9781593600112", "num_pages": "eng", "ratings_count": 400,
     "text_reviews_count": 26, "publication_date": "4", "publisher": "4/6/2004", "FIELD13": "Cold Spring Press"},
    {"bookID": 22128, "title": "Patriots (The Coming Collapse)", "authors": "James Wesley", "average_rating": " Rawles",
     "isbn": "3.63", "isbn13": "156384155X", "language_code": "9781563841552", "num_pages": "eng", "ratings_count": 342,
     "text_reviews_count": 38, "publication_date": "4", "publisher": "1/15/1999", "FIELD13": "Huntington House Publishers"},
    {"bookID": 34889, "title": "Brown's Star Atlas: Showing All The Bright Stars", "authors": "Brown",
     "average_rating": " Son & Ferguson", "isbn": "0.00", "isbn13": "0851742718", "language_code": "9780851742717",
     "num_pages": "eng", "ratings_count": 49, "text_reviews_count": 0, "publication_date": "0",
     "publisher": "5/1/1977", "FIELD13": "Brown Son & Ferguson Ltd."},
]


# --------------------------------------------------------------------- registro normal
def test_registro_normal():
    libro, t = transformar(base())
    assert libro == LibroLimpio(
        id_libro=1, titulo="Harry Potter and the Half-Blood Prince (Harry Potter  #6)", isbn="0439785960",
        isbn13="9780439785969", num_paginas=652, fecha_publicacion=date(2006, 9, 16),
        calificacion_promedio=Decimal("4.57"), num_calificaciones=2095690, num_resenas=27591,
        editorial="Scholastic Inc.", idioma="eng", autores=("J.K. Rowling", "Mary GrandPré"),
    )
    assert t.avisos == {}


def test_titulo_con_espacios_sobrantes_se_recorta_pero_no_se_altera_por_dentro():
    libro, _ = transformar(base(title="  Harry  Potter  "))
    assert libro.titulo == "Harry  Potter"


def test_autores_se_parten_por_barra_con_su_orden_y_sin_espacios():
    libro, _ = transformar(base(authors=" A / B /C "))
    assert libro.autores == ("A", "B", "C")


def test_autor_repetido_se_conserva_una_vez_y_avisa():
    libro, t = transformar(base(authors="Stephen King/Stephen King/Peter Straub/stephen king"))
    assert libro.autores == ("Stephen King", "Peter Straub")
    assert t.avisos == {"autor_repetido": [1]}


@pytest.mark.parametrize("autores", ["", " / ", "///"])
def test_sin_autores_se_carga_con_aviso(autores):
    libro, t = transformar(base(authors=autores))
    assert libro.autores == () and t.avisos == {"sin_autores": [1]}


# ------------------------------------------------------------------ reparación de desplazados
def test_repara_los_cuatro_registros_desplazados_reales():
    esperado = [
        ("Sam Bass Warner, Jr.", "Sam B. Warner"),
        ("David E. Smith (Turgon of TheOneRing.net, one of the founding members of this Tolkien website)",
         "Verlyn Flieger", "Turgon (=David E. Smith)"),
        ("James Wesley, Rawles",),
        ("Brown, Son & Ferguson",),
    ]
    detalles = [  # calificación, isbn, isbn13, idioma, páginas, votos, reseñas, fecha, editorial
        (Decimal("3.58"), "0674842111", "9780674842113", "en-US", 236, 61, 6, date(2004, 4, 20), "Harvard University Press"),
        (Decimal("3.58"), "1593600119", "9781593600112", "eng", 400, 26, 4, date(2004, 4, 6), "Cold Spring Press"),
        (Decimal("3.63"), "156384155X", "9781563841552", "eng", 342, 38, 4, date(1999, 1, 15), "Huntington House Publishers"),
        (Decimal("0.00"), "0851742718", "9780851742717", "eng", 49, 0, 0, date(1977, 5, 1), "Brown Son & Ferguson Ltd."),
    ]
    t = TransformadorLibros()
    for crudo, autores, d in zip(DESPLAZADOS, esperado, detalles):
        libro = t.transformar(RegistroCrudo(1, crudo))
        assert isinstance(libro, LibroLimpio), libro
        assert libro.autores == autores
        assert (libro.calificacion_promedio, libro.isbn, libro.isbn13, libro.idioma, libro.num_paginas,
                libro.num_calificaciones, libro.num_resenas, libro.fecha_publicacion, libro.editorial) == d
    assert t.avisos["reparado"] == [12224, 16914, 22128, 34889]


def test_un_registro_con_FIELD13_vacio_no_se_repara():
    libro, t = transformar(base(FIELD13=""))
    assert libro.autores == ("J.K. Rowling", "Mary GrandPré") and "reparado" not in t.avisos


def test_desplazado_que_no_se_puede_reparar_se_rechaza_con_motivo():
    roto = dict(DESPLAZADOS[0], isbn13="no-es-un-isbn-valido-de-13-caracteres")   # tras reparar, isbn sería demasiado largo
    r, _ = transformar(roto)
    assert isinstance(r, Rechazo) and r.motivo.startswith("Registro desplazado que no se pudo reparar")


def test_campo_extra_con_contenido_que_no_es_FIELD13_se_rechaza():
    r, _ = transformar(base(OTRO="algo"))
    assert isinstance(r, Rechazo) and "Campos inesperados" in r.motivo


# --------------------------------------------------------------------------- rechazos
@pytest.mark.parametrize(
    "cambios, fragmento",
    [
        ({"bookID": 0}, "fuera del rango"),
        ({"bookID": "abc"}, "no es un número entero"),
        ({"bookID": True}, "no es un número entero"),
        ({"bookID": -5}, "fuera del rango"),
        ({"title": ""}, "'title' está vacío"),
        ({"title": "   "}, "'title' está vacío"),
        ({"title": "T" * 301}, "301 caracteres"),
        ({"title": 123}, "debe ser texto"),
        ({"average_rating": "abc"}, "no es un número decimal"),
        ({"average_rating": "5.5"}, "fuera del rango 0-5"),
        ({"average_rating": "-1"}, "no es un número decimal"),
        ({"average_rating": None}, "no es un número"),
        ({"num_pages": "mil"}, "no es un número entero"),
        ({"num_pages": "65536"}, "fuera del rango"),
        ({"ratings_count": -1}, "fuera del rango"),
        ({"text_reviews_count": "x"}, "no es un número entero"),
        ({"publisher": ""}, "'publisher' está vacío"),
        ({"publisher": "E" * 121}, "121 caracteres"),
        ({"language_code": ""}, "'language_code' está vacío"),
        ({"language_code": "x" * 16}, "16 caracteres"),
        ({"authors": "A" * 121}, "máximo 120"),
        ({"authors": 7}, "'authors' debe ser texto"),
        ({"isbn": "1" * 14}, "14 caracteres"),
    ],
)
def test_registros_invalidos_se_rechazan_con_motivo(cambios, fragmento):
    r, _ = transformar(base(**cambios), numero=7)
    assert isinstance(r, Rechazo), r
    assert fragmento in r.motivo
    assert r.linea == 7 and len(r.contenido) <= 200


def test_registro_con_campos_faltantes_se_rechaza():
    datos = base()
    del datos["publisher"], datos["isbn"]
    r, _ = transformar(datos)
    assert isinstance(r, Rechazo) and "Faltan campos: isbn, publisher" in r.motivo


@pytest.mark.parametrize("no_objeto", ["texto", 42, None, ["lista"]])
def test_elemento_que_no_es_un_objeto_se_rechaza(no_objeto):
    r, _ = transformar(no_objeto)
    assert isinstance(r, Rechazo) and "no es un objeto" in r.motivo


def test_bookid_duplicado_conserva_el_primero_y_rechaza_el_segundo():
    t = TransformadorLibros()
    primero = t.transformar(RegistroCrudo(1, base()))
    segundo = t.transformar(RegistroCrudo(2, base(title="Otro título")))
    assert isinstance(primero, LibroLimpio)
    assert isinstance(segundo, Rechazo) and "duplicado" in segundo.motivo


def test_un_registro_rechazado_no_bloquea_su_bookid():
    t = TransformadorLibros()
    assert isinstance(t.transformar(RegistroCrudo(1, base(title=""))), Rechazo)
    assert isinstance(t.transformar(RegistroCrudo(2, base())), LibroLimpio)


# ------------------------------------------------------------------ valores y avisos
@pytest.mark.parametrize("texto, esperado", [("4.567", "4.57"), ("4.5", "4.50"), ("0", "0.00"), ("5", "5.00"), (4.57, "4.57"), (5, "5.00")])
def test_calificacion_se_normaliza_a_dos_decimales(texto, esperado):
    libro, _ = transformar(base(average_rating=texto))
    assert libro.calificacion_promedio == Decimal(esperado)


def test_calificacion_cero_con_cero_votos_se_carga_tal_cual():
    libro, t = transformar(base(average_rating="0.00", ratings_count=0))
    assert (libro.calificacion_promedio, libro.num_calificaciones) == (Decimal("0.00"), 0) and t.avisos == {}


def test_cero_paginas_se_acepta():
    assert transformar(base(num_pages="0"))[0].num_paginas == 0


@pytest.mark.parametrize("texto", ["11/31/2000", "6/31/1982", "2/30/2001", "13/1/2000", "2004-04-20", "abril", "", "4/20/04"])
def test_fecha_inexistente_o_con_otro_formato_se_carga_sin_fecha_y_avisa(texto):
    libro, t = transformar(base(publication_date=texto))
    assert libro.fecha_publicacion is None and t.avisos == {"fecha_invalida": [1]}


@pytest.mark.parametrize("texto, esperada", [("4/20/2004", date(2004, 4, 20)), ("1/5/1999", date(1999, 1, 5)), ("12/31/2020", date(2020, 12, 31)), ("2/29/2000", date(2000, 2, 29))])
def test_fecha_mes_dia_anio(texto, esperada):
    assert transformar(base(publication_date=texto))[0].fecha_publicacion == esperada


def test_isbn_con_longitud_rara_se_carga_con_aviso():
    libro, t = transformar(base(isbn="084386874", isbn13="978084238687"))
    assert libro.isbn == "084386874" and t.avisos == {"isbn_longitud": [1], "isbn13_longitud": [1]}


def test_isbn_con_letra_final_es_valido():
    libro, t = transformar(base(isbn="156384155X"))
    assert libro.isbn == "156384155X" and t.avisos == {}
