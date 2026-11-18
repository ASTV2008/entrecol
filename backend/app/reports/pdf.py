"""Generación de PDF para los reportes de la API."""
from __future__ import annotations

import re
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any
import unicodedata

import reportlab
from fastapi import Response
from pydantic import BaseModel
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.reportes import Grafico

PAGE_WIDTH, _ = landscape(letter)
_MARGEN = 13 * mm
_ANCHO_TABLA = PAGE_WIDTH - 2 * _MARGEN
_FUENTE = "Helvetica"
_FUENTE_NEGRITA = "Helvetica-Bold"
_ETIQUETAS = {
    "anio": "Año",
    "anio_estreno": "Año de estreno",
    "calificacion": "Calificación",
    "calificacion_promedio": "Calificación promedio",
    "codigo": "Código",
    "fecha_fin": "Fecha fin",
    "fecha_ingreso": "Fecha de ingreso",
    "fecha_inicio": "Fecha de inicio",
    "id_libro": "ID libro",
    "id_pelicula": "ID película",
    "min_calificaciones": "Mínimo de calificaciones",
    "num_calificaciones": "Número de calificaciones",
    "num_resenas": "Número de reseñas",
    "num_paginas": "Número de páginas",
    "tasa_aporte_pension": "Tasa de aporte a pensión",
}


def _registrar_fuentes() -> None:
    global _FUENTE, _FUENTE_NEGRITA
    if "Entrecol" in pdfmetrics.getRegisteredFontNames():
        _FUENTE, _FUENTE_NEGRITA = "Entrecol", "Entrecol-Bold"
        return
    fuentes = Path(reportlab.__file__).parent / "fonts"
    regular, negrita = fuentes / "Vera.ttf", fuentes / "VeraBd.ttf"
    if regular.is_file() and negrita.is_file():
        pdfmetrics.registerFont(TTFont("Entrecol", str(regular)))
        pdfmetrics.registerFont(TTFont("Entrecol-Bold", str(negrita)))
        _FUENTE, _FUENTE_NEGRITA = "Entrecol", "Entrecol-Bold"


def _label(clave: str) -> str:
    return _ETIQUETAS.get(clave, clave.replace("_", " ").capitalize())


def _texto(valor: Any) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, float):
        return f"{valor:,.2f}"
    return str(valor)


def _parrafo(valor: Any, estilo: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_texto(valor)).replace("\n", "<br/>"), estilo)


def _estilos():
    _registrar_fuentes()
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(
        name="EntrecolTitle", parent=estilos["Title"], fontName=_FUENTE_NEGRITA,
        fontSize=20, leading=24, alignment=TA_CENTER, textColor=colors.HexColor("#183B56"),
        spaceAfter=5 * mm,
    ))
    estilos.add(ParagraphStyle(
        name="EntrecolHeading", parent=estilos["Heading2"], fontName=_FUENTE_NEGRITA,
        fontSize=13, leading=16, textColor=colors.HexColor("#183B56"),
        spaceBefore=4 * mm, spaceAfter=2 * mm, keepWithNext=True,
    ))
    estilos.add(ParagraphStyle(
        name="EntrecolBody", parent=estilos["BodyText"], fontName=_FUENTE,
        fontSize=8, leading=10, alignment=TA_LEFT,
    ))
    estilos.add(ParagraphStyle(
        name="EntrecolSmall", parent=estilos["BodyText"], fontName=_FUENTE,
        fontSize=7, leading=8.5, alignment=TA_LEFT,
    ))
    estilos.add(ParagraphStyle(
        name="EntrecolHeader", parent=estilos["BodyText"], fontName=_FUENTE_NEGRITA,
        fontSize=7, leading=8, textColor=colors.white,
    ))
    return estilos


def _tabla(filas: list[list[Any]], estilos, anchos=None) -> Table:
    if not filas:
        filas = [["Sin datos"]]
    celdas = [
        [_parrafo(valor, estilos["EntrecolHeader"] if i == 0 else estilos["EntrecolSmall"])
         for valor in fila]
        for i, fila in enumerate(filas)
    ]
    if anchos is None:
        anchos = [_ANCHO_TABLA / len(filas[0])] * len(filas[0])
    tabla = Table(celdas, colWidths=anchos, repeatRows=1, hAlign="LEFT", splitByRow=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#183B56")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F8")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C7D1D8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tabla


def _resumen(filas: list[tuple[str, Any]], estilos) -> Table:
    contenido = [[_parrafo(_label(clave), estilos["EntrecolHeader"]), _parrafo(valor, estilos["EntrecolSmall"])]
                 for clave, valor in filas]
    tabla = Table(contenido, colWidths=[48 * mm, PAGE_WIDTH - 2 * _MARGEN - 48 * mm], hAlign="LEFT")
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#183B56")),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, colors.HexColor("#F1F5F8")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C7D1D8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tabla


def _encabezado_item(item: dict[str, Any]) -> str:
    for clave in ("anio", "codigo", "id_libro", "id_pelicula", "titulo", "nombre", "dependencia"):
        if item.get(clave) is not None:
            return f"{_label(clave)}: {_texto(item[clave])}"
    return ""


def _agregar_valor(story: list, nombre: str, valor: Any, estilos, profundidad: int = 0) -> None:
    if isinstance(valor, list):
        story.append(Paragraph(escape(nombre), estilos["EntrecolHeading"]))
        if not valor:
            story.append(Paragraph("Sin datos.", estilos["EntrecolBody"]))
            return
        if not isinstance(valor[0], dict):
            story.append(_tabla([[_label(nombre)]] + [[v] for v in valor], estilos))
            return

        claves = list(dict.fromkeys(clave for item in valor for clave in item
                                    if not isinstance(item[clave], (dict, list))))
        if claves:
            filas = [[_label(clave) for clave in claves]]
            filas.extend([[_texto(item.get(clave)) for clave in claves] for item in valor])
            story.append(_tabla(filas, estilos))
        else:
            story.append(Paragraph("Sin datos.", estilos["EntrecolBody"]))

        for item in valor:
            hijos = [(clave, contenido) for clave, contenido in item.items()
                     if isinstance(contenido, (dict, list))]
            for clave, contenido in hijos:
                contexto = _encabezado_item(item)
                etiqueta = f"{_label(clave)} — {contexto}" if contexto else _label(clave)
                _agregar_valor(story, etiqueta, contenido, estilos, profundidad + 1)
        return

    if isinstance(valor, dict):
        _agregar_objeto(story, valor, estilos, profundidad, titulo=nombre)


def _agregar_objeto(story: list, datos: dict[str, Any], estilos, profundidad: int = 0, titulo: str | None = None) -> None:
    if titulo:
        story.append(Paragraph(escape(titulo), estilos["EntrecolHeading"]))
    simples = [(clave, valor) for clave, valor in datos.items() if not isinstance(valor, (dict, list))]
    if simples:
        story.append(_resumen(simples, estilos))
    for clave, valor in datos.items():
        if isinstance(valor, (dict, list)):
            _agregar_valor(story, _label(clave), valor, estilos, profundidad)


def _grafico(grafico: Grafico, estilos) -> Drawing | None:
    if not grafico.etiquetas or not grafico.series:
        return None
    ancho, alto = 470, 240
    dibujo = Drawing(ancho, alto)
    if grafico.tipo == "torta":
        valores = grafico.series[0].valores
        if not any(valores):
            return None
        torta = Pie()
        torta.x, torta.y, torta.width, torta.height = 15, 15, 190, 210
        torta.data = valores
        torta.labels = [""] * len(valores)
        torta.slices.strokeWidth = 0.5
        torta.slices.strokeColor = colors.white
        torta.slices[0].fillColor = colors.HexColor("#2878A5")
        for i in range(1, len(valores)):
            torta.slices[i].fillColor = colors.HexColor(
                ["#F2A541", "#5B9A8B", "#D96C75", "#8267A8", "#84A9C0"][i % 5]
            )
        dibujo.add(torta)
    elif grafico.tipo == "barras":
        barras = VerticalBarChart()
        barras.x, barras.y, barras.width, barras.height = 45, 50, 395, 160
        barras.data = [serie.valores for serie in grafico.series]
        barras.categoryAxis.categoryNames = [
            f"{etiqueta} ({grafico.grupos[i]})" if grafico.grupos else etiqueta
            for i, etiqueta in enumerate(grafico.etiquetas)
        ]
        barras.categoryAxis.labels.fontName = _FUENTE
        barras.categoryAxis.labels.fontSize = 6
        barras.categoryAxis.labels.angle = 45
        barras.categoryAxis.labels.dx = -5
        barras.categoryAxis.labels.dy = -2
        barras.valueAxis.labels.fontName = _FUENTE
        barras.valueAxis.labels.fontSize = 7
        barras.valueAxis.valueMin = 0
        barras.valueAxis.visibleGrid = True
        barras.valueAxis.gridStrokeColor = colors.HexColor("#D7E0E6")
        barras.barWidth = min(12, 340 / max(1, len(grafico.etiquetas)))
        barras.groupSpacing = 2
        barras.barSpacing = 1
        for i in range(len(grafico.series)):
            barras.bars[i].fillColor = colors.HexColor(
                ["#2878A5", "#F2A541", "#5B9A8B", "#D96C75", "#8267A8"][i % 5]
            )
        dibujo.add(barras)
    else:
        return None
    return dibujo


def _agregar_grafico(story: list, grafico: Grafico, estilos) -> None:
    story.append(Paragraph(escape(grafico.titulo), estilos["EntrecolHeading"]))
    dibujo = _grafico(grafico, estilos)
    if dibujo is not None:
        story.append(dibujo)
    elif grafico.etiquetas:
        story.append(Paragraph("No hay valores positivos para dibujar el gráfico.", estilos["EntrecolBody"]))
    if grafico.nota:
        story.append(Paragraph(escape(grafico.nota), estilos["EntrecolBody"]))

    filas = [["Etiqueta", "Grupo"] + [serie.nombre for serie in grafico.series]]
    for indice, etiqueta in enumerate(grafico.etiquetas):
        filas.append([etiqueta, grafico.grupos[indice] if grafico.grupos else ""] +
                     [serie.valores[indice] for serie in grafico.series])
    story.append(_tabla(filas, estilos))


def generar_pdf(titulo: str, reporte: BaseModel) -> bytes:
    """Convierte una respuesta de reporte en un PDF paginado con tablas y, si aplica, gráfico."""
    datos = reporte.model_dump(mode="json")
    estilos = _estilos()
    story = [
        Paragraph(escape(titulo), estilos["EntrecolTitle"]),
        Paragraph(
            f"Generado el {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M')}",
            estilos["EntrecolSmall"],
        ),
        Spacer(1, 3 * mm),
    ]
    if isinstance(reporte, Grafico):
        _agregar_grafico(story, reporte, estilos)
    elif isinstance(datos, dict):
        _agregar_objeto(story, datos, estilos)
    else:
        _agregar_valor(story, "Datos", datos, estilos)

    buffer = BytesIO()

    def pie_pagina(canvas, documento):
        canvas.saveState()
        canvas.setFont(_FUENTE, 7)
        canvas.setFillColor(colors.HexColor("#526471"))
        canvas.drawString(_MARGEN, 7 * mm, "Entrecol · Reporte generado desde la API")
        canvas.drawRightString(PAGE_WIDTH - _MARGEN, 7 * mm, f"Página {documento.page}")
        canvas.restoreState()

    documento = SimpleDocTemplate(
        buffer, pagesize=landscape(letter), leftMargin=_MARGEN, rightMargin=_MARGEN,
        topMargin=13 * mm, bottomMargin=14 * mm, title=titulo, author="Entrecol",
    )
    documento.build(story, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    return buffer.getvalue()


def respuesta_pdf(titulo: str, reporte: BaseModel, descargar: bool = False) -> Response:
    """Entrega el PDF en línea para vista previa o como adjunto para descargar."""
    titulo_ascii = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"[^a-zA-Z0-9_-]+", "-", titulo_ascii).strip("-").lower() or "reporte"
    disposicion = "attachment" if descargar else "inline"
    return PDFResponse(
        content=generar_pdf(titulo, reporte),
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposicion}; filename="{nombre}.pdf"'},
    )


class PDFResponse(Response):
    media_type = "application/pdf"
