"""Pruebas del paso CARGAR y del servicio completo de libros.

Usan la base de pruebas (fixture `sesion`): cada prueba se deshace sola.
"""
import io
import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.etl.common import ErrorDeArchivo
from app.etl.libros.loader import CargadorLibros
from app.etl.libros.service import cargar_libros
from app.etl.libros.transformer import LibroLimpio
from app.models import Autor, Editorial, Idioma, Libro, LibroAutor


def libro(id_, titulo="T", editorial="Ed", idioma="eng", autores=("A",), **otros) -> LibroLimpio:
    datos = dict(
        id_libro=id_, titulo=titulo, isbn="0123456789", isbn13="9780123456789", num_paginas=100,
        fecha_publicacion=date(2000, 1, 1), calificacion_promedio=Decimal("4.00"), num_calificaciones=10,
        num_resenas=1, editorial=editorial, idioma=idioma, autores=tuple(autores),
    )
    datos.update(otros)
    return LibroLimpio(**datos)


def contar(sesion, modelo) -> int:
    return sesion.execute(select(func.count()).select_from(modelo)).scalar_one()


def autores_de(sesion, id_libro) -> list[str]:
    """Autores del libro en su orden de autoría."""
    filas = sesion.execute(
        select(Autor.nombre).join(LibroAutor, LibroAutor.id_autor == Autor.id_autor)
        .where(LibroAutor.id_libro == id_libro).order_by(LibroAutor.orden_autoria)
    )
    return [n for (n,) in filas]


def fila(sesion, id_libro) -> Libro:
    return sesion.get(Libro, id_libro)


# ----------------------------------------------------------------------- cargador
def test_carga_inicial_crea_libros_y_catalogos(sesion):
    r = CargadorLibros(sesion).cargar([
        libro(1, editorial="Scholastic", autores=("J.K. Rowling", "Mary GrandPré")),
        libro(2, editorial="Penguin", idioma="spa", autores=("Mary GrandPré",)),
    ])
    assert (r.nuevas, r.actualizadas, r.sin_cambios, r.vinculos) == (2, 0, 0, 3)
    assert (r.editoriales.nuevos, r.idiomas.nuevos, r.autores.nuevos) == (2, 2, 2)    # Mary GrandPré se comparte
    assert (contar(sesion, Libro), contar(sesion, Autor), contar(sesion, LibroAutor)) == (2, 2, 3)
    assert autores_de(sesion, 1) == ["J.K. Rowling", "Mary GrandPré"]


def test_se_guardan_todos_los_valores_del_libro(sesion):
    CargadorLibros(sesion).cargar([libro(5, titulo="Mi libro", isbn="156384155X", isbn13="9781563841552", num_paginas=342,
                                         fecha_publicacion=date(1999, 1, 15), calificacion_promedio=Decimal("3.63"),
                                         num_calificaciones=38, num_resenas=4, editorial="Huntington", idioma="eng")])
    sesion.expire_all()
    l = fila(sesion, 5)
    assert (l.titulo, l.isbn, l.isbn13, l.num_paginas, l.fecha_publicacion, l.calificacion_promedio,
            l.num_calificaciones, l.num_resenas) == ("Mi libro", "156384155X", "9781563841552", 342,
                                                      date(1999, 1, 15), Decimal("3.63"), 38, 4)
    assert l.editorial.nombre == "Huntington" and l.idioma.codigo == "eng"


def test_editoriales_equivalentes_para_la_base_son_una_sola(sesion):
    r = CargadorLibros(sesion).cargar([
        libro(1, editorial="Ace"), libro(2, editorial="ACE"), libro(3, editorial="Éditions 10/18"), libro(4, editorial="Editions 10/18"),
    ])
    assert contar(sesion, Editorial) == 2
    assert r.editoriales.unificados == 2
    assert {fila(sesion, i).id_editorial for i in (1, 2)} == {fila(sesion, 1).id_editorial}


def test_el_mismo_autor_con_dos_grafias_equivalentes_cuenta_una_vez_por_libro(sesion):
    r = CargadorLibros(sesion).cargar([libro(1, autores=("Gabriel García Márquez", "Gabriel Garcia Marquez", "Otro"))])
    assert autores_de(sesion, 1) == ["Gabriel García Márquez", "Otro"]
    assert r.vinculos == 2 and r.equivalentes_en_libros == [1]


def test_el_orden_de_autoria_empieza_en_1_y_sigue_el_orden_del_archivo(sesion):
    CargadorLibros(sesion).cargar([libro(1, autores=("Tercero", "Primero", "Segundo"))])
    ordenes = sesion.execute(
        select(LibroAutor.orden_autoria, Autor.nombre)
        .join(Autor, Autor.id_autor == LibroAutor.id_autor).where(LibroAutor.id_libro == 1).order_by(LibroAutor.orden_autoria)
    ).all()
    assert [tuple(f) for f in ordenes] == [(1, "Tercero"), (2, "Primero"), (3, "Segundo")]


def test_cargar_dos_veces_lo_mismo_no_duplica_nada(sesion):
    datos = [libro(1, autores=("A", "B")), libro(2, editorial="Otra", autores=("B",))]
    CargadorLibros(sesion).cargar(datos)
    r = CargadorLibros(sesion).cargar(datos)
    assert (r.nuevas, r.actualizadas, r.sin_cambios) == (0, 0, 2)
    assert (r.editoriales.nuevos, r.idiomas.nuevos, r.autores.nuevos) == (0, 0, 0)
    assert (contar(sesion, Libro), contar(sesion, Autor), contar(sesion, LibroAutor), contar(sesion, Editorial)) == (2, 2, 3, 2)


@pytest.mark.parametrize("cambio", [
    {"titulo": "Otro título"}, {"isbn": "9999999999"}, {"num_paginas": 200}, {"calificacion_promedio": Decimal("3.50")},
    {"num_calificaciones": 11}, {"num_resenas": 2}, {"fecha_publicacion": date(2001, 2, 2)}, {"fecha_publicacion": None},
    {"editorial": "Otra editorial"}, {"idioma": "spa"},
])
def test_cualquier_cambio_en_un_campo_actualiza_el_libro(sesion, cambio):
    CargadorLibros(sesion).cargar([libro(1)])
    r = CargadorLibros(sesion).cargar([libro(1, **cambio)])
    assert (r.nuevas, r.actualizadas, r.sin_cambios) == (0, 1, 0)
    sesion.expire_all()
    for campo, valor in cambio.items():
        if campo == "editorial":
            assert fila(sesion, 1).editorial.nombre == valor
        elif campo == "idioma":
            assert fila(sesion, 1).idioma.codigo == valor
        else:
            assert getattr(fila(sesion, 1), campo) == valor


def test_cambiar_el_orden_o_la_lista_de_autores_actualiza_los_vinculos(sesion):
    CargadorLibros(sesion).cargar([libro(1, autores=("A", "B", "C"))])
    r = CargadorLibros(sesion).cargar([libro(1, autores=("C", "A"))])
    assert (r.actualizadas, r.sin_cambios) == (1, 0)
    assert autores_de(sesion, 1) == ["C", "A"]
    assert contar(sesion, Autor) == 3          # "B" sigue existiendo: la carga no borra


def test_fecha_sin_valor_se_guarda_como_null(sesion):
    CargadorLibros(sesion).cargar([libro(1, fecha_publicacion=None)])
    sesion.expire_all()
    assert fila(sesion, 1).fecha_publicacion is None


def test_libro_sin_autores(sesion):
    CargadorLibros(sesion).cargar([libro(1, autores=())])
    assert autores_de(sesion, 1) == [] and contar(sesion, Autor) == 0


def test_no_borra_libros_que_no_vienen_en_el_archivo(sesion):
    CargadorLibros(sesion).cargar([libro(1), libro(2)])
    CargadorLibros(sesion).cargar([libro(1)])
    assert contar(sesion, Libro) == 2


def test_funciona_con_lotes_pequenos(sesion, monkeypatch):
    monkeypatch.setattr(CargadorLibros, "TAMANO_LOTE", 2)
    datos = [libro(i, titulo=f"L{i}", autores=(f"Autor {i % 3}", "Común")) for i in range(1, 6)]    # 5 libros, 3 lotes
    assert CargadorLibros(sesion).cargar(datos).nuevas == 5
    r = CargadorLibros(sesion).cargar(datos)
    assert (r.nuevas, r.sin_cambios) == (0, 5)
    assert (contar(sesion, Libro), contar(sesion, Autor), contar(sesion, LibroAutor)) == (5, 4, 10)


def test_lista_vacia_no_hace_nada(sesion):
    r = CargadorLibros(sesion).cargar([])
    assert (r.nuevas, r.actualizadas, r.sin_cambios, r.vinculos) == (0, 0, 0, 0)


# ----------------------------------------------------------------------- servicio
def archivo(registros) -> io.BytesIO:
    return io.BytesIO(json.dumps(registros, ensure_ascii=False).encode("utf-8"))


def registro(id_=1, **cambios) -> dict:
    datos = {
        "bookID": id_, "title": f"Libro {id_}", "authors": "Autor Uno/Autor Dos", "average_rating": "4.10",
        "isbn": "0439785960", "isbn13": "9780439785969", "language_code": "eng", "num_pages": "100",
        "ratings_count": 10, "text_reviews_count": 2, "publication_date": "1/2/2003", "publisher": "Editorial X", "FIELD13": "",
    }
    datos.update(cambios)
    return datos


DESPLAZADO = {
    "bookID": 12224, "title": "Streetcar Suburbs", "authors": "Sam Bass Warner", "average_rating": " Jr./Sam B. Warner",
    "isbn": "3.58", "isbn13": "0674842111", "language_code": "9780674842113", "num_pages": "en-US", "ratings_count": 236,
    "text_reviews_count": 61, "publication_date": "6", "publisher": "4/20/2004", "FIELD13": "Harvard University Press",
}


def test_servicio_completo_con_registros_buenos_malos_y_reparados(sesion):
    informe = cargar_libros(
        archivo([
            registro(1),
            registro(2, publication_date="11/31/2000"),                 # fecha imposible: se carga sin fecha
            registro(3, authors="Ana/Ana/Beto", ratings_count=0, average_rating="0.00", num_pages="0"),
            DESPLAZADO,                                                  # se repara
            registro(5, average_rating="muy bueno"),                    # rechazado
            "no soy un objeto",                                          # rechazado
            registro(1, title="Duplicado"),                              # rechazado (bookID repetido)
        ]),
        sesion,
    )
    assert (informe.leidas, informe.aceptadas, informe.rechazadas) == (7, 4, 3)
    assert (informe.nuevas, informe.actualizadas, informe.sin_cambios) == (4, 0, 0)
    assert [r.linea for r in informe.rechazos] == [5, 6, 7]                      # posición en la lista
    assert informe.detalles["Libros sin calificaciones"] == 1
    assert informe.detalles["Libros con 0 páginas"] == 1
    assert informe.detalles["Vínculos libro-autor"] == 2 + 2 + 2 + 2             # libro 3 deduplica a Ana, Beto
    assert informe.detalles["Autores nuevos"] == 6                               # Uno, Dos, Ana, Beto y los 2 del desplazado
    texto = "\n".join(informe.advertencias)
    assert "desplazados" in texto and "12224" in texto
    assert "SIN fecha" in texto and "(bookID 2)" in texto
    assert "repetían un mismo autor" in texto and "(bookID 3)" in texto
    assert contar(sesion, Libro) == 4
    assert autores_de(sesion, 12224) == ["Sam Bass Warner, Jr.", "Sam B. Warner"]
    assert fila(sesion, 12224).editorial.nombre == "Harvard University Press"
    assert fila(sesion, 2).fecha_publicacion is None


def test_servicio_cargar_el_mismo_archivo_dos_veces(sesion):
    registros = [registro(1), registro(2, publisher="EDITORIAL X"), DESPLAZADO]
    cargar_libros(archivo(registros), sesion)
    informe = cargar_libros(archivo(registros), sesion)
    assert (informe.nuevas, informe.actualizadas, informe.sin_cambios) == (0, 0, 3)
    assert contar(sesion, Libro) == 3 and contar(sesion, Editorial) == 2


def test_servicio_avisa_cuando_unifica_editoriales_equivalentes(sesion):
    informe = cargar_libros(archivo([registro(1, publisher="Ace"), registro(2, publisher="ACE")]), sesion)
    assert any("se unificaron" in a and "'Ace' = 'ACE'" in a for a in informe.advertencias)


def test_servicio_lista_vacia_cancela_la_carga(sesion):
    with pytest.raises(ErrorDeArchivo, match="ningún libro"):
        cargar_libros(archivo([]), sesion)


def test_servicio_json_roto_cancela_la_carga(sesion):
    with pytest.raises(ErrorDeArchivo, match="JSON válido"):
        cargar_libros(io.BytesIO(b'[{"bookID": 1'), sesion)


def test_servicio_sin_ningun_registro_valido_cancela_la_carga(sesion):
    with pytest.raises(ErrorDeArchivo, match="Ningún registro es válido"):
        cargar_libros(archivo([{"a": 1}, {"b": 2}]), sesion)
    assert contar(sesion, Libro) == 0


def test_servicio_informe_serializable_para_la_api_y_habla_de_registros(sesion):
    informe = cargar_libros(archivo([registro(1), {"x": 1}]), sesion)
    datos = informe.a_dict()
    assert datos["leidas"] == 2 and datos["rechazadas"] == 1 and datos["rechazos"][0]["linea"] == 2
    assert "registro 2:" in informe.resumen()
