"""Consultas SQL del reporte de entretenimiento (películas y libros).

Misma regla que RepositorioNomina: aquí vive el SQL; agrupar y dar formato es de los servicios.
"""
from collections.abc import Sequence

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from app.models import Genero, Libro, Pelicula, pelicula_genero
from app.schemas.reportes import Orden


def _sentido(columna, orden: Orden):
    return columna.asc() if orden is Orden.asc else columna.desc()


class RepositorioEntretenimiento:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------ películas
    def peliculas_por_genero(self, desde: int, hasta: int, orden: Orden) -> Sequence[Row]:
        """(id_genero, genero, id_pelicula, titulo, anio): géneros ascendentes, títulos según `orden`."""
        consulta = (
            select(Genero.id_genero, Genero.nombre.label("genero"), Pelicula.id_pelicula, Pelicula.titulo,
                   Pelicula.anio_estreno.label("anio"))
            .join(pelicula_genero, pelicula_genero.c.id_genero == Genero.id_genero)
            .join(Pelicula, Pelicula.id_pelicula == pelicula_genero.c.id_pelicula)
            .where(Pelicula.anio_estreno.between(desde, hasta))
            .order_by(Genero.nombre, Genero.id_genero, _sentido(Pelicula.titulo, orden), Pelicula.id_pelicula)
        )
        return self._db.execute(consulta).all()

    def total_peliculas_distintas(self, desde: int, hasta: int) -> int:
        """Películas del rango que tienen al menos un género (las que aparecen en el reporte por género)."""
        consulta = (
            select(func.count(func.distinct(Pelicula.id_pelicula)))
            .join(pelicula_genero, pelicula_genero.c.id_pelicula == Pelicula.id_pelicula)
            .where(Pelicula.anio_estreno.between(desde, hasta))
        )
        return self._db.execute(consulta).scalar_one()

    def peliculas_con_n_generos(self, n: int, orden: Orden) -> Sequence[Row]:
        """(id_pelicula, titulo, anio, genero) de las películas con EXACTAMENTE n géneros.

        Con n = 0 devuelve las películas sin géneros (genero = None). Títulos según `orden`; géneros ascendentes.
        """
        cuenta = (
            select(Pelicula.id_pelicula.label("id_pelicula"), func.count(pelicula_genero.c.id_genero).label("n"))
            .select_from(Pelicula)
            .outerjoin(pelicula_genero, pelicula_genero.c.id_pelicula == Pelicula.id_pelicula)
            .group_by(Pelicula.id_pelicula)
            .having(func.count(pelicula_genero.c.id_genero) == n)
            .subquery("cuenta")
        )
        consulta = (
            select(Pelicula.id_pelicula, Pelicula.titulo, Pelicula.anio_estreno.label("anio"), Genero.nombre.label("genero"))
            .join(cuenta, cuenta.c.id_pelicula == Pelicula.id_pelicula)
            .outerjoin(pelicula_genero, pelicula_genero.c.id_pelicula == Pelicula.id_pelicula)
            .outerjoin(Genero, Genero.id_genero == pelicula_genero.c.id_genero)
            .order_by(_sentido(Pelicula.titulo, orden), Pelicula.id_pelicula, Genero.nombre)
        )
        return self._db.execute(consulta).all()

    def conteo_peliculas_por_genero(self) -> Sequence[Row]:
        """(genero, cantidad), géneros ascendentes (incluye géneros sin películas con 0)."""
        consulta = (
            select(Genero.nombre.label("genero"), func.count(pelicula_genero.c.id_pelicula).label("cantidad"))
            .outerjoin(pelicula_genero, pelicula_genero.c.id_genero == Genero.id_genero)
            .group_by(Genero.id_genero, Genero.nombre)
            .order_by(Genero.nombre, Genero.id_genero)
        )
        return self._db.execute(consulta).all()

    # --------------------------------------------------------------------- libros
    # Regla de negocio: solo cuentan los libros CALIFICADOS (num_calificaciones > 0). Un libro sin
    # calificaciones tiene rating 0 por ausencia de datos, no porque sea malo. Desempate: más
    # calificaciones primero (más confiable) y luego id_libro (resultado determinista).
    def _clasificados(self, mejor: bool, particion_por_anio: bool, min_calificaciones: int):
        rating = Libro.calificacion_promedio.desc() if mejor else Libro.calificacion_promedio.asc()
        ventana = dict(order_by=(rating, Libro.num_calificaciones.desc(), Libro.id_libro))
        if particion_por_anio:
            ventana["partition_by"] = func.year(Libro.fecha_publicacion)
        return (
            select(
                Libro.id_libro, Libro.titulo, Libro.calificacion_promedio.label("calificacion"), Libro.num_calificaciones,
                func.year(Libro.fecha_publicacion).label("anio"),
                func.row_number().over(**ventana).label("posicion"),
            )
            .where(Libro.num_calificaciones >= max(1, min_calificaciones))
        )

    def top_libros(self, n: int, orden: Orden, min_calificaciones: int = 1) -> Sequence[Row]:
        """Los n libros de mejor rating: (posicion, id_libro, titulo, calificacion, num_calificaciones, anio).

        El Top se DEFINE por rating; `orden` solo decide cómo se ordenan los títulos dentro de ese Top.
        """
        clasificados = self._clasificados(True, False, min_calificaciones).subquery("clasificados")
        consulta = (
            select(clasificados)
            .where(clasificados.c.posicion <= n)
            .order_by(_sentido(clasificados.c.titulo, orden), clasificados.c.posicion)
        )
        return self._db.execute(consulta).all()

    def top_por_anio(self, mejor: bool, por_anio: int, desde: int | None, hasta: int | None, orden: Orden,
                     min_calificaciones: int = 1) -> Sequence[Row]:
        """Los `por_anio` mejores (o peores) libros de cada año: mismas columnas que top_libros.

        Se ignoran los libros sin fecha de publicación válida (no pertenecen a ningún año).
        """
        base = self._clasificados(mejor, True, min_calificaciones).where(Libro.fecha_publicacion.is_not(None))
        if desde is not None:
            base = base.where(func.year(Libro.fecha_publicacion) >= desde)
        if hasta is not None:
            base = base.where(func.year(Libro.fecha_publicacion) <= hasta)
        sub = base.subquery("por_anio")
        consulta = (
            select(sub)
            .where(sub.c.posicion <= por_anio)
            .order_by(sub.c.anio, _sentido(sub.c.titulo, orden), sub.c.posicion)
        )
        return self._db.execute(consulta).all()

    def conteo_libros_por_anio(self, desde: int, hasta: int) -> Sequence[Row]:
        """(anio, cantidad) de los años del rango que tienen libros, ascendente."""
        anio = func.year(Libro.fecha_publicacion)
        consulta = (
            select(anio.label("anio"), func.count(Libro.id_libro).label("cantidad"))
            .where(Libro.fecha_publicacion.is_not(None))
            .where(anio.between(desde, hasta))
            .group_by(anio)
            .order_by(anio)
        )
        return self._db.execute(consulta).all()
