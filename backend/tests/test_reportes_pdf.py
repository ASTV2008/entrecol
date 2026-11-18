import re

import pytest

from app.reports.pdf import generar_pdf, respuesta_pdf
from app.schemas.reportes import Grafico, Serie
from app.schemas.reportes_entretenimiento import LibroPuesto, ReporteTopPorAnio, TopDelAnio


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


def test_endpoint_pdf_es_vista_previa_y_admite_descarga(cliente):
    url = "/api/v1/reportes/nomina/grafico-dependencias/pdf"
    vista_previa = cliente.get(url)
    assert vista_previa.status_code == 200
    assert vista_previa.headers["content-type"] == "application/pdf"
    assert vista_previa.headers["content-disposition"].startswith("inline;")
    assert vista_previa.content.startswith(b"%PDF-")

    descarga = cliente.get(f"{url}?descargar=true")
    assert descarga.status_code == 200
    assert descarga.headers["content-disposition"].startswith("attachment;")


def test_pagina_de_reportes_y_recursos_estaticos(cliente):
    pagina = cliente.get("/")
    script = cliente.get("/js/pages/reportes.js")
    pdfjs = cliente.get("/js/vendor/pdf.min.mjs")
    trabajador_pdfjs = cliente.get("/js/vendor/pdf.worker.min.mjs")

    assert pagina.status_code == 200
    assert "Explora las cinco áreas" in pagina.text
    assert 'data-report-category="Nómina"' in pagina.text
    assert 'id="report-data-button"' in pagina.text
    assert 'id="pdf-canvas"' in pagina.text
    assert script.status_code == 200
    assert "Top de libros por año" in script.text
    assert pdfjs.status_code == 200
    assert trabajador_pdfjs.status_code == 200


def test_endpoint_pdf_conserva_validacion_de_parametros(cliente):
    assert cliente.get("/api/v1/reportes/entretenimiento/libros/top/pdf").status_code == 422
    assert cliente.get(
        "/api/v1/reportes/entretenimiento/libros/top/pdf?n=3&min_calificaciones=0"
    ).status_code == 422


def test_nombre_pdf_de_descarga_preserva_letras_accentuadas():
    reporte = ReporteTopPorAnio(desde=None, hasta=None, criterio="Prueba", anios=[])

    respuesta = respuesta_pdf("Top de libros por año", reporte, descargar=True)

    assert respuesta.headers["content-disposition"] == 'attachment; filename="top-de-libros-por-ano.pdf"'


@pytest.mark.parametrize("ruta", [
    "/nomina/empleados/pdf",
    "/nomina/por-dependencia/pdf",
    "/nomina/por-cargo/pdf",
    "/nomina/grafico-dependencias/pdf",
    "/nomina/grafico-cargos/pdf",
    "/personal/pdf",
    "/salud-pension/grafico-eps/pdf",
    "/salud-pension/grafico-pension/pdf",
    "/salud-pension/grafico-eps-dependencia/pdf",
    "/salud-pension/grafico-pension-dependencia/pdf",
    "/salud-pension/por-cargo-eps/pdf",
    "/salud-pension/por-cargo-pension/pdf",
    "/novedades/empleados/pdf?desde=03%2F2022&hasta=03%2F2022",
    "/novedades/resumen/pdf?desde=03%2F2022&hasta=03%2F2022",
    "/entretenimiento/peliculas-por-genero/pdf?desde=1990&hasta=2000",
    "/entretenimiento/libros/top/pdf?n=5",
    "/entretenimiento/libros/top-por-anio/pdf",
    "/entretenimiento/peliculas/por-numero-de-generos/pdf?n=1",
    "/entretenimiento/graficos/peliculas-por-genero/pdf",
    "/entretenimiento/graficos/libros-por-anio/pdf?desde=2000&hasta=2001",
])
def test_todos_los_reportes_tienen_salida_pdf(cliente, ruta):
    respuesta = cliente.get(f"/api/v1/reportes{ruta}")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert respuesta.content.startswith(b"%PDF-")


def test_pdf_top_por_anio_pagina_listas_largas():
    anios = []
    for anio in range(1900, 1986):
        libros = [
            LibroPuesto(
                posicion=puesto,
                id_libro=anio * 10 + puesto,
                titulo=f"Libro de prueba {anio}-{puesto}",
                calificacion=4.5,
                num_calificaciones=100,
                anio=anio,
            )
            for puesto in range(1, 6)
        ]
        anios.append(TopDelAnio(anio=anio, mejores=libros, peores=libros))
    reporte = ReporteTopPorAnio(desde=1900, hasta=1985, criterio="Prueba", anios=anios)

    pdf = generar_pdf("Top de libros por año", reporte)

    assert pdf.startswith(b"%PDF-")
    assert _paginas(pdf) > 1


def test_pdf_dibuja_graficos_de_torta_y_barras():
    torta = Grafico(
        titulo="Empleados por dependencia",
        tipo="torta",
        etiquetas=["Administración", "Comercial"],
        series=[Serie(nombre="Empleados", valores=[3, 5])],
    )
    barras = Grafico(
        titulo="Libros por año",
        tipo="barras",
        etiquetas=["2000", "2001"],
        series=[
            Serie(nombre="Libros", valores=[4, 7]),
            Serie(nombre="Películas", valores=[2, 5]),
        ],
    )

    assert generar_pdf("Torta", torta).startswith(b"%PDF-")
    assert generar_pdf("Barras", barras).startswith(b"%PDF-")
