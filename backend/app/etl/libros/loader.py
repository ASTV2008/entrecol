"""CARGAR: guarda en la base de datos los libros ya limpios.

Mismas reglas que el cargador de películas:
    - Repetible (idempotente): cargar el mismo archivo dos veces no duplica nada.
    - Solo AGREGA y ACTUALIZA; nunca borra libros que no vengan en el archivo.
    - NO hace commit: la transacción la controla quien llama.

Además crea, si faltan, las filas de los catálogos de autor, editorial e idioma.
La igualdad de nombres la decide la base de datos (ver catalogos.py).
"""
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.etl.catalogos import ResultadoCatalogo, asegurar_catalogo
from app.etl.libros.transformer import LibroLimpio
from app.models import Autor, Editorial, Idioma, Libro, LibroAutor


@dataclass
class ResultadoCargaLibros:
    nuevas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    vinculos: int = 0                      # relaciones libro-autor que debe tener la base según el archivo
    editoriales: ResultadoCatalogo | None = None
    idiomas: ResultadoCatalogo | None = None
    autores: ResultadoCatalogo | None = None
    equivalentes_en_libros: list[int] = field(default_factory=list)   # libros cuyos autores la base unificó


class CargadorLibros:
    TAMANO_LOTE = 500

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def cargar(self, libros: Sequence[LibroLimpio]) -> ResultadoCargaLibros:
        resultado = ResultadoCargaLibros()
        resultado.editoriales = asegurar_catalogo(self._sesion, Editorial.id_editorial, Editorial.nombre, (l.editorial for l in libros))
        resultado.idiomas = asegurar_catalogo(self._sesion, Idioma.id_idioma, Idioma.codigo, (l.idioma for l in libros))
        resultado.autores = asegurar_catalogo(self._sesion, Autor.id_autor, Autor.nombre, (a for l in libros for a in l.autores))
        for inicio in range(0, len(libros), self.TAMANO_LOTE):
            self._cargar_lote(libros[inicio : inicio + self.TAMANO_LOTE], resultado)
        return resultado

    def _cargar_lote(self, lote: Sequence[LibroLimpio], resultado: ResultadoCargaLibros) -> None:
        ids = [libro.id_libro for libro in lote]
        ids_editorial = resultado.editoriales.ids
        ids_idioma = resultado.idiomas.ids
        ids_autor = resultado.autores.ids

        # Estado actual en la base de los libros de este lote
        actuales = {
            fila[0]: tuple(fila[1:])
            for fila in self._sesion.execute(
                select(
                    Libro.id_libro, Libro.titulo, Libro.isbn, Libro.isbn13, Libro.num_paginas,
                    Libro.fecha_publicacion, Libro.calificacion_promedio, Libro.num_calificaciones,
                    Libro.num_resenas, Libro.id_editorial, Libro.id_idioma,
                ).where(Libro.id_libro.in_(ids))
            )
        }
        autores_actuales: dict[int, list[int]] = defaultdict(list)
        for id_libro, id_autor in self._sesion.execute(
            select(LibroAutor.id_libro, LibroAutor.id_autor)
            .where(LibroAutor.id_libro.in_(ids))
            .order_by(LibroAutor.id_libro, LibroAutor.orden_autoria)
        ):
            autores_actuales[id_libro].append(id_autor)

        # Clasificar: nuevo / cambiado / igual
        nuevos: list[LibroLimpio] = []
        cambiados: list[LibroLimpio] = []
        autores_deseados: dict[int, list[int]] = {}
        for libro in lote:
            # Dos nombres que la base considera el mismo autor cuentan UNA vez (llave primaria libro+autor)
            deseados = list(dict.fromkeys(ids_autor[nombre] for nombre in libro.autores))
            if len(deseados) != len(libro.autores):
                resultado.equivalentes_en_libros.append(libro.id_libro)
            autores_deseados[libro.id_libro] = deseados
            resultado.vinculos += len(deseados)

            if libro.id_libro not in actuales:
                nuevos.append(libro)
            elif (
                actuales[libro.id_libro] != self._valores(libro, ids_editorial, ids_idioma)
                or autores_actuales.get(libro.id_libro, []) != deseados
            ):
                cambiados.append(libro)
            else:
                resultado.sin_cambios += 1

        # Escribir solo lo que cambió
        if nuevos:
            self._sesion.execute(insert(Libro), [self._fila(l, ids_editorial, ids_idioma) for l in nuevos])
        if cambiados:
            self._sesion.execute(update(Libro), [self._fila(l, ids_editorial, ids_idioma) for l in cambiados])
        resultado.nuevas += len(nuevos)
        resultado.actualizadas += len(cambiados)

        # Autores: se reescriben por completo los vínculos de los libros nuevos o cambiados
        a_reescribir = nuevos + cambiados
        if a_reescribir:
            self._sesion.execute(
                delete(LibroAutor)
                .where(LibroAutor.id_libro.in_([l.id_libro for l in a_reescribir]))
                .execution_options(synchronize_session=False)
            )
            vinculos = [
                {"id_libro": l.id_libro, "id_autor": id_autor, "orden_autoria": orden}
                for l in a_reescribir
                for orden, id_autor in enumerate(autores_deseados[l.id_libro], start=1)
            ]
            if vinculos:
                self._sesion.execute(insert(LibroAutor), vinculos)

    @staticmethod
    def _valores(libro: LibroLimpio, ids_editorial: dict[str, int], ids_idioma: dict[str, int]) -> tuple:
        """Los valores del libro en el MISMO orden que la consulta de estado actual (sin el id)."""
        return (
            libro.titulo, libro.isbn, libro.isbn13, libro.num_paginas, libro.fecha_publicacion,
            libro.calificacion_promedio, libro.num_calificaciones, libro.num_resenas,
            ids_editorial[libro.editorial], ids_idioma[libro.idioma],
        )

    @classmethod
    def _fila(cls, libro: LibroLimpio, ids_editorial: dict[str, int], ids_idioma: dict[str, int]) -> dict:
        return {
            "id_libro": libro.id_libro, "titulo": libro.titulo, "isbn": libro.isbn, "isbn13": libro.isbn13,
            "num_paginas": libro.num_paginas, "fecha_publicacion": libro.fecha_publicacion,
            "calificacion_promedio": libro.calificacion_promedio, "num_calificaciones": libro.num_calificaciones,
            "num_resenas": libro.num_resenas, "id_editorial": ids_editorial[libro.editorial],
            "id_idioma": ids_idioma[libro.idioma],
        }
