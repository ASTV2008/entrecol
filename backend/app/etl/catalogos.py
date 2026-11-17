"""Catálogos: tablas de nombres únicos (autor, editorial, idioma, género).

PROBLEMA QUE RESUELVE
La base compara los nombres IGNORANDO mayúsculas y tildes: 'Ace' = 'ACE' y
'Editions 10/18' = 'Éditions 10/18'. Python no lo sabe. Si el programa decidiera
la igualdad por su cuenta, intentaría crear dos filas que la base considera la
misma y fallaría con un error de llave duplicada (en Books.json pasa con 35
editoriales). Por eso aquí la igualdad la decide SIEMPRE la propia base de datos.

CÓMO
    1. Pregunta a la base qué nombres ya existen (una unión con la tabla, que usa su colación).
    2. Crea los que faltan con "INSERT ... ON DUPLICATE KEY UPDATE <no hacer nada>".
    3. Vuelve a preguntar para conocer el id de cada nombre.
"""
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field

from sqlalchemy import Integer, String, literal, select, union_all
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import InstrumentedAttribute, Session

TAMANO_CONSULTA = 500     # nombres por consulta de búsqueda
TAMANO_INSERCION = 1000   # nombres por inserción


@dataclass
class ResultadoCatalogo:
    ids: dict[str, int]                                   # nombre (tal como vino) -> id
    nuevos: int = 0                                       # filas creadas en esta carga
    equivalentes: list[tuple[str, ...]] = field(default_factory=list)   # nombres distintos que la base trata como uno

    @property
    def unificados(self) -> int:
        """Cuántos nombres sobran por ser equivalentes a otro."""
        return sum(len(grupo) - 1 for grupo in self.equivalentes)


def _lotes(elementos: Sequence[str], tamano: int) -> Iterator[Sequence[str]]:
    for inicio in range(0, len(elementos), tamano):
        yield elementos[inicio : inicio + tamano]


def _resolver_ids(
    sesion: Session, columna_id: InstrumentedAttribute, columna_nombre: InstrumentedAttribute, nombres: Sequence[str]
) -> dict[str, int]:
    """{nombre: id} de los nombres que ya existen, comparando con la colación de la base."""
    modelo = columna_id.class_
    ids: dict[str, int] = {}
    for lote in _lotes(nombres, TAMANO_CONSULTA):
        pedidos = union_all(*(select(literal(nombre, String).label("n")) for nombre in lote)).subquery("pedidos")
        consulta = (
            select(pedidos.c.n, columna_id).select_from(pedidos).join(modelo, columna_nombre == pedidos.c.n)
        )
        for nombre, id_ in sesion.execute(consulta):
            ids[nombre] = id_
    return ids


def asegurar_catalogo(
    sesion: Session,
    columna_id: InstrumentedAttribute,
    columna_nombre: InstrumentedAttribute,
    nombres: Iterable[str],
) -> ResultadoCatalogo:
    """Garantiza que cada nombre exista en el catálogo y devuelve su id.

    Ejemplo:  asegurar_catalogo(sesion, Editorial.id_editorial, Editorial.nombre, ["Ace", "ACE"])
    crea UNA sola editorial y devuelve el mismo id para "Ace" y para "ACE".
    No hace commit. Si todos los nombres ya existen no inserta nada (no consume ids).
    """
    unicos = list(dict.fromkeys(nombres))        # sin repetidos exactos, en orden de aparición
    ids = _resolver_ids(sesion, columna_id, columna_nombre, unicos)

    faltantes = [nombre for nombre in unicos if nombre not in ids]
    if faltantes:
        tabla = columna_id.class_.__table__
        sentencia = mysql_insert(tabla).on_duplicate_key_update({columna_id.key: tabla.c[columna_id.key]})
        for lote in _lotes(faltantes, TAMANO_INSERCION):
            sesion.execute(sentencia, [{columna_nombre.key: nombre} for nombre in lote])
        ids.update(_resolver_ids(sesion, columna_id, columna_nombre, faltantes))
        sin_resolver = [nombre for nombre in faltantes if nombre not in ids]
        if sin_resolver:   # no debería ocurrir; si ocurre, es mejor fallar que seguir con datos incompletos
            raise RuntimeError(f"No se pudo resolver el id de {len(sin_resolver)} nombres, p. ej. {sin_resolver[:3]}")

    grupos: dict[int, list[str]] = {}
    for nombre in unicos:
        grupos.setdefault(ids[nombre], []).append(nombre)
    return ResultadoCatalogo(
        ids=ids,
        nuevos=len({ids[nombre] for nombre in faltantes}),
        equivalentes=[tuple(g) for g in grupos.values() if len(g) > 1],
    )


# ----------------------------------------------------------------- con padre
@dataclass
class ResultadoCatalogoConPadre:
    ids: dict[tuple[int, str], int]    # (id del padre, nombre tal como vino) -> id
    nuevos: int = 0


def _resolver_ids_con_padre(
    sesion: Session,
    columna_id: InstrumentedAttribute,
    columna_padre: InstrumentedAttribute,
    columna_nombre: InstrumentedAttribute,
    pares: Sequence[tuple[int, str]],
) -> dict[tuple[int, str], int]:
    modelo = columna_id.class_
    ids: dict[tuple[int, str], int] = {}
    for lote in _lotes(pares, TAMANO_CONSULTA):
        pedidos = union_all(
            *(select(literal(padre, Integer).label("p"), literal(nombre, String).label("n")) for padre, nombre in lote)
        ).subquery("pedidos")
        consulta = (
            select(pedidos.c.p, pedidos.c.n, columna_id)
            .select_from(pedidos)
            .join(modelo, (columna_padre == pedidos.c.p) & (columna_nombre == pedidos.c.n))
        )
        for padre, nombre, id_ in sesion.execute(consulta):
            ids[(padre, nombre)] = id_
    return ids


def asegurar_catalogo_con_padre(
    sesion: Session,
    columna_id: InstrumentedAttribute,
    columna_padre: InstrumentedAttribute,
    columna_nombre: InstrumentedAttribute,
    pares: Iterable[tuple[int, str]],
) -> ResultadoCatalogoConPadre:
    """Como asegurar_catalogo, pero el nombre solo es único DENTRO de su padre.

    Ejemplo: el cargo 'Director' puede existir en Ventas y en Contabilidad (son dos filas
    distintas); dentro de Ventas, 'Director' y 'DIRECTOR' son la misma. Recibe pares
    (id_dependencia, nombre_cargo) y devuelve el id de cada uno. No hace commit.
    """
    unicos = list(dict.fromkeys(pares))
    ids = _resolver_ids_con_padre(sesion, columna_id, columna_padre, columna_nombre, unicos)
    faltantes = [par for par in unicos if par not in ids]
    if faltantes:
        tabla = columna_id.class_.__table__
        sentencia = mysql_insert(tabla).on_duplicate_key_update({columna_id.key: tabla.c[columna_id.key]})
        for lote in _lotes(faltantes, TAMANO_INSERCION):
            sesion.execute(sentencia, [{columna_padre.key: padre, columna_nombre.key: nombre} for padre, nombre in lote])
        ids.update(_resolver_ids_con_padre(sesion, columna_id, columna_padre, columna_nombre, faltantes))
        if any(par not in ids for par in faltantes):
            raise RuntimeError("No se pudo resolver el id de algunos registros recién creados")
    return ResultadoCatalogoConPadre(ids=ids, nuevos=len({ids[par] for par in faltantes}))
