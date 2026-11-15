"""CARGAR: guarda en la base de datos las películas ya limpias.

Reglas de la carga:
    - Repetible (idempotente): cargar el mismo archivo dos veces no duplica nada.
    - Solo AGREGA y ACTUALIZA; nunca borra películas que no vengan en el archivo.
    - NO hace commit: la transacción la controla quien llama (así la carga es
      "todo o nada" y se puede hacer un simulacro con rollback).
"""
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.etl.peliculas.transformer import PeliculaLimpia
from app.models import Genero, Pelicula, pelicula_genero


@dataclass
class ResultadoCarga:
    nuevas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    generos_nuevos: int = 0


class CargadorPeliculas:
    TAMANO_LOTE = 1000   # filas por consulta: equilibra velocidad y memoria

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def cargar(self, peliculas: Sequence[PeliculaLimpia]) -> ResultadoCarga:
        resultado = ResultadoCarga()
        ids_genero = self._asegurar_generos(peliculas, resultado)
        for inicio in range(0, len(peliculas), self.TAMANO_LOTE):
            lote = peliculas[inicio : inicio + self.TAMANO_LOTE]
            self._cargar_lote(lote, ids_genero, resultado)
        return resultado

    # ------------------------------------------------------------------ géneros
    def _asegurar_generos(self, peliculas: Sequence[PeliculaLimpia], resultado: ResultadoCarga) -> dict[str, int]:
        """Crea los géneros que falten y devuelve {nombre_en_minúsculas: id_genero}.

        La base trata 'Sci-Fi' y 'sci-fi' como el mismo género (colación _ci),
        por eso se busca sin distinguir mayúsculas y se conserva la primera grafía.
        """
        pedidos: dict[str, str] = {}
        for pelicula in peliculas:
            for genero in pelicula.generos:
                pedidos.setdefault(genero.casefold(), genero)

        existentes = self._ids_de_generos()
        faltantes = [nombre for clave, nombre in pedidos.items() if clave not in existentes]
        if faltantes:
            self._sesion.execute(insert(Genero), [{"nombre": nombre} for nombre in faltantes])
            existentes = self._ids_de_generos()
        resultado.generos_nuevos = len(faltantes)
        return existentes

    def _ids_de_generos(self) -> dict[str, int]:
        filas = self._sesion.execute(select(Genero.id_genero, Genero.nombre))
        return {nombre.casefold(): id_genero for id_genero, nombre in filas}

    # ---------------------------------------------------------------- películas
    def _cargar_lote(self, lote: Sequence[PeliculaLimpia], ids_genero: dict[str, int], resultado: ResultadoCarga) -> None:
        ids = [p.id_pelicula for p in lote]

        # Estado actual en la base de las películas de este lote
        datos_actuales = {
            fila.id_pelicula: (fila.titulo, fila.anio_estreno)
            for fila in self._sesion.execute(
                select(Pelicula.id_pelicula, Pelicula.titulo, Pelicula.anio_estreno).where(Pelicula.id_pelicula.in_(ids))
            )
        }
        generos_actuales: dict[int, set[int]] = defaultdict(set)
        for id_pelicula, id_genero in self._sesion.execute(
            select(pelicula_genero.c.id_pelicula, pelicula_genero.c.id_genero).where(
                pelicula_genero.c.id_pelicula.in_(ids)
            )
        ):
            generos_actuales[id_pelicula].add(id_genero)

        # Clasificar: nueva / cambiada / igual
        nuevas: list[PeliculaLimpia] = []
        cambiadas: list[PeliculaLimpia] = []
        for pelicula in lote:
            deseados = {ids_genero[g.casefold()] for g in pelicula.generos}
            if pelicula.id_pelicula not in datos_actuales:
                nuevas.append(pelicula)
            elif (
                datos_actuales[pelicula.id_pelicula] != (pelicula.titulo, pelicula.anio_estreno)
                or generos_actuales.get(pelicula.id_pelicula, set()) != deseados
            ):
                cambiadas.append(pelicula)
            else:
                resultado.sin_cambios += 1

        # Escribir solo lo que cambió
        if nuevas:
            self._sesion.execute(insert(Pelicula), [self._fila(p) for p in nuevas])
        if cambiadas:
            self._sesion.execute(update(Pelicula), [self._fila(p) for p in cambiadas])  # por llave primaria
        resultado.nuevas += len(nuevas)
        resultado.actualizadas += len(cambiadas)

        # Géneros: se reescriben por completo los vínculos de las películas nuevas o cambiadas
        a_reescribir = nuevas + cambiadas
        if a_reescribir:
            self._sesion.execute(
                delete(pelicula_genero).where(pelicula_genero.c.id_pelicula.in_([p.id_pelicula for p in a_reescribir]))
            )
            vinculos = [
                {"id_pelicula": p.id_pelicula, "id_genero": ids_genero[g.casefold()]}
                for p in a_reescribir
                for g in p.generos
            ]
            if vinculos:
                self._sesion.execute(insert(pelicula_genero), vinculos)

    @staticmethod
    def _fila(pelicula: PeliculaLimpia) -> dict:
        return {"id_pelicula": pelicula.id_pelicula, "titulo": pelicula.titulo, "anio_estreno": pelicula.anio_estreno}
