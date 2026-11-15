"""Pruebas del paso CARGAR y del servicio completo de películas.

Usan la base de pruebas (fixture `sesion`): cada prueba se deshace sola.
"""
import io

import pytest
from sqlalchemy import func, select

from app.etl.common import ErrorDeArchivo
from app.etl.peliculas.loader import CargadorPeliculas
from app.etl.peliculas.service import cargar_peliculas
from app.etl.peliculas.transformer import PeliculaLimpia
from app.models import Genero, Pelicula, pelicula_genero


def peli(id_, titulo, anio, *generos):
    return PeliculaLimpia(id_, titulo, anio, tuple(generos))


def contar(sesion, tabla) -> int:
    return sesion.execute(select(func.count()).select_from(tabla)).scalar_one()


def generos_de(sesion, id_pelicula) -> set[str]:
    filas = sesion.execute(
        select(Genero.nombre)
        .join(pelicula_genero, pelicula_genero.c.id_genero == Genero.id_genero)
        .where(pelicula_genero.c.id_pelicula == id_pelicula)
    )
    return {nombre for (nombre,) in filas}


def archivo(*lineas: str) -> io.BytesIO:
    return io.BytesIO("\n".join(lineas).encode("utf-8"))


# ----------------------------------------------------------------------- cargador
def test_carga_inicial(sesion):
    r = CargadorPeliculas(sesion).cargar(
        [peli(1, "Toy Story", 1995, "Animation", "Comedy"), peli(2, "Heat", 1995, "Action"), peli(3, "Sin genero", 1958)]
    )
    assert (r.nuevas, r.actualizadas, r.sin_cambios, r.generos_nuevos) == (3, 0, 0, 3)
    assert contar(sesion, Pelicula) == 3
    assert contar(sesion, Genero) == 3
    assert contar(sesion, pelicula_genero) == 3          # 2 + 1 + 0
    assert generos_de(sesion, 1) == {"Animation", "Comedy"}
    assert generos_de(sesion, 3) == set()


def test_cargar_dos_veces_lo_mismo_no_duplica_nada(sesion):
    datos = [peli(1, "Toy Story", 1995, "Animation", "Comedy"), peli(2, "Heat", 1995, "Action")]
    CargadorPeliculas(sesion).cargar(datos)
    r = CargadorPeliculas(sesion).cargar(datos)
    assert (r.nuevas, r.actualizadas, r.sin_cambios, r.generos_nuevos) == (0, 0, 2, 0)
    assert (contar(sesion, Pelicula), contar(sesion, Genero), contar(sesion, pelicula_genero)) == (2, 3, 3)


def test_cambio_de_titulo_o_anio_actualiza_la_pelicula(sesion):
    CargadorPeliculas(sesion).cargar([peli(1, "Toy Story", 1995, "Comedy")])
    r = CargadorPeliculas(sesion).cargar([peli(1, "Toy Story 1", 1996, "Comedy")])
    assert (r.nuevas, r.actualizadas, r.sin_cambios) == (0, 1, 0)
    fila = sesion.execute(select(Pelicula.titulo, Pelicula.anio_estreno)).one()
    assert tuple(fila) == ("Toy Story 1", 1996)


def test_cambio_solo_de_generos_se_detecta_y_reescribe_los_vinculos(sesion):
    CargadorPeliculas(sesion).cargar([peli(1, "X", 2000, "Comedy", "Drama")])
    r = CargadorPeliculas(sesion).cargar([peli(1, "X", 2000, "Comedy", "Action")])
    assert (r.actualizadas, r.sin_cambios) == (1, 0)
    assert generos_de(sesion, 1) == {"Comedy", "Action"}
    assert contar(sesion, Genero) == 3     # "Drama" sigue existiendo: la carga no borra


def test_quitar_todos_los_generos_borra_los_vinculos(sesion):
    CargadorPeliculas(sesion).cargar([peli(1, "X", 2000, "Comedy")])
    CargadorPeliculas(sesion).cargar([peli(1, "X", 2000)])
    assert generos_de(sesion, 1) == set()


def test_generos_con_distinta_capitalizacion_son_un_solo_genero(sesion):
    CargadorPeliculas(sesion).cargar([peli(1, "A", 2000, "Sci-Fi"), peli(2, "B", 2001, "sci-fi")])
    assert contar(sesion, Genero) == 1
    assert generos_de(sesion, 1) == generos_de(sesion, 2) == {"Sci-Fi"}


def test_no_borra_peliculas_que_no_vienen_en_el_archivo(sesion):
    CargadorPeliculas(sesion).cargar([peli(1, "A", 2000, "Comedy"), peli(2, "B", 2001, "Drama")])
    CargadorPeliculas(sesion).cargar([peli(1, "A", 2000, "Comedy")])
    assert contar(sesion, Pelicula) == 2


def test_funciona_con_lotes_pequenos(sesion, monkeypatch):
    monkeypatch.setattr(CargadorPeliculas, "TAMANO_LOTE", 2)
    datos = [peli(i, f"P{i}", 2000 + i, "Comedy" if i % 2 else "Drama") for i in range(1, 6)]   # 5 películas, 3 lotes
    assert CargadorPeliculas(sesion).cargar(datos).nuevas == 5
    r = CargadorPeliculas(sesion).cargar(datos)
    assert (r.nuevas, r.sin_cambios) == (0, 5)
    assert (contar(sesion, Pelicula), contar(sesion, pelicula_genero)) == (5, 5)


def test_lista_vacia_no_hace_nada(sesion):
    r = CargadorPeliculas(sesion).cargar([])
    assert (r.nuevas, r.actualizadas, r.sin_cambios, r.generos_nuevos) == (0, 0, 0, 0)


# ----------------------------------------------------------------------- servicio
def test_servicio_completo_con_filas_buenas_y_malas(sesion):
    informe = cargar_peliculas(
        archivo(
            "1::Toy Story (1995)::Adventure|Animation|Children|Comedy|Fantasy",
            "",
            "2::Sin anio::Comedy",
            "8606::Pull My Daisy (1958)::(no genres listed)",
            "abc::Roto (2000)::Drama",
            "1::Duplicada (2000)::Drama",
        ),
        sesion,
    )
    assert informe.leidas == 5            # la línea en blanco no cuenta
    assert informe.aceptadas == 2
    assert informe.rechazadas == 3
    assert (informe.nuevas, informe.actualizadas, informe.sin_cambios) == (2, 0, 0)
    assert informe.detalles["Géneros nuevos"] == 5
    assert informe.detalles["Películas sin géneros"] == 1
    assert [r.linea for r in informe.rechazos] == [3, 5, 6]     # numeración original del archivo
    assert contar(sesion, Pelicula) == 2
    assert "Pull My Daisy" in {t for (t,) in sesion.execute(select(Pelicula.titulo))}
    assert len(informe.advertencias) == 1      # 3 rechazadas > 2 aceptadas: el aviso es correcto


def test_servicio_advierte_si_se_rechaza_mas_de_lo_que_se_acepta(sesion):
    informe = cargar_peliculas(archivo("1::Bien (2000)::A", "x", "y", "z"), sesion)
    assert informe.advertencias


def test_servicio_cargar_el_mismo_archivo_dos_veces(sesion):
    contenido = b"1::Toy Story (1995)::Comedy\n2::Heat (1995)::Action\n"
    cargar_peliculas(io.BytesIO(contenido), sesion)
    informe = cargar_peliculas(io.BytesIO(contenido), sesion)
    assert (informe.nuevas, informe.actualizadas, informe.sin_cambios) == (0, 0, 2)
    assert contar(sesion, Pelicula) == 2


def test_servicio_archivo_vacio_cancela_la_carga(sesion):
    with pytest.raises(ErrorDeArchivo, match="vacío"):
        cargar_peliculas(io.BytesIO(b"\n\n  \n"), sesion)


def test_servicio_sin_ninguna_fila_valida_cancela_la_carga(sesion):
    with pytest.raises(ErrorDeArchivo, match="Ninguna fila es válida"):
        cargar_peliculas(archivo("esto no", "es un archivo", "de peliculas"), sesion)
    assert contar(sesion, Pelicula) == 0


def test_servicio_informe_se_puede_serializar_para_la_api(sesion):
    informe = cargar_peliculas(archivo("1::A (2000)::Comedy", "mala"), sesion)
    datos = informe.a_dict()
    assert datos["leidas"] == 2 and datos["rechazadas"] == 1
    assert datos["rechazos"][0]["linea"] == 2
