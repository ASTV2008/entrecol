"""Reporte 5 (libros): 5b Top N, 5c Top 5 mejores/peores por año y 5f frecuencia por año de publicación."""
from app.core.errores import ErrorDeParametro
from app.repositories.entretenimiento import RepositorioEntretenimiento
from app.schemas.reportes import Grafico, Orden, Serie
from app.schemas.reportes_entretenimiento import (
    TOP_POR_ANIO, LibroPuesto, ReporteTopLibros, ReporteTopPorAnio, TopDelAnio,
)
from app.services.periodos import MAX_ANIOS_GRAFICO, leer_anios

CRITERIO = ("Solo cuentan los libros calificados (al menos {min} calificaciones). Desempate: más calificaciones "
            "y luego menor id. El orden elegido se aplica a los títulos; la posición indica el puesto en el ranking.")


def _puesto(f) -> LibroPuesto:
    return LibroPuesto(posicion=f.posicion, id_libro=f.id_libro, titulo=f.titulo, calificacion=float(f.calificacion),
                       num_calificaciones=f.num_calificaciones, anio=f.anio)


class ServicioReporteLibros:
    def __init__(self, repo: RepositorioEntretenimiento) -> None:
        self._repo = repo

    # 5b) Top N con mejor rating
    def top(self, n: int, orden: Orden, min_calificaciones: int = 1) -> ReporteTopLibros:
        filas = self._repo.top_libros(n, orden, min_calificaciones)
        return ReporteTopLibros(n=n, total=len(filas), criterio=CRITERIO.format(min=max(1, min_calificaciones)),
                                libros=[_puesto(f) for f in filas])

    # 5c) Top 5 mejores y Top 5 peores por año
    def top_por_anio(self, orden: Orden, desde: int | None = None, hasta: int | None = None,
                     min_calificaciones: int = 1) -> ReporteTopPorAnio:
        leer_anios(desde, hasta, obligatorio=False)
        mejores = self._repo.top_por_anio(True, TOP_POR_ANIO, desde, hasta, orden, min_calificaciones)
        peores = self._repo.top_por_anio(False, TOP_POR_ANIO, desde, hasta, orden, min_calificaciones)
        por_anio: dict[int, dict[str, list[LibroPuesto]]] = {}
        for clave, filas in (("mejores", mejores), ("peores", peores)):
            for f in filas:
                por_anio.setdefault(f.anio, {"mejores": [], "peores": []})[clave].append(_puesto(f))
        return ReporteTopPorAnio(
            desde=desde, hasta=hasta, criterio=CRITERIO.format(min=max(1, min_calificaciones)),
            anios=[TopDelAnio(anio=a, mejores=v["mejores"], peores=v["peores"]) for a, v in sorted(por_anio.items())])

    # 5f) gráfico de frecuencia de libros por año de publicación entre F1 y F2
    def grafico_por_anio(self, desde: int, hasta: int) -> Grafico:
        leer_anios(desde, hasta)
        if hasta - desde + 1 > MAX_ANIOS_GRAFICO:
            raise ErrorDeParametro(f"El rango abarca {hasta - desde + 1} años; el máximo para el gráfico es {MAX_ANIOS_GRAFICO}.")
        cantidades = {f.anio: f.cantidad for f in self._repo.conteo_libros_por_anio(desde, hasta)}
        anios = range(desde, hasta + 1)       # los años sin libros salen con 0 para que el eje sea continuo
        return Grafico(titulo=f"Libros por año de publicación ({desde}-{hasta})", tipo="barras",
                       etiquetas=[str(a) for a in anios],
                       series=[Serie(nombre="Libros", valores=[cantidades.get(a, 0) for a in anios])],
                       nota="Los libros sin fecha de publicación válida no se incluyen.")
