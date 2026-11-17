"""Línea de comandos del ETL.

Uso (dentro del contenedor de la API):
    python -m app.etl.cli peliculas /data/movies.dat              # carga y guarda
    python -m app.etl.cli libros /data/Books.json                 # ídem para libros
    python -m app.etl.cli nomina /data/Nomina.xlsx --periodo 2022-03   # nómina: el Excel no trae mes, se indica aquí
    python -m app.etl.cli peliculas /data/movies.dat --simulacro  # carga, muestra el informe y DESHACE todo

Nota: un simulacro (o una carga cancelada) no devuelve los números autoincrementales que consumió,
por lo que pueden quedar huecos en los id de las tablas de catálogo. Es normal en MariaDB e inofensivo.

Códigos de salida: 0 = bien, 2 = el archivo no sirve, no se pudo abrir o los argumentos son inválidos.
"""
import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.etl.common import ErrorDeArchivo, InformeCarga
from app.etl.libros.service import cargar_libros
from app.etl.nomina.service import PeriodoNomina, cargar_nomina
from app.etl.peliculas.service import cargar_peliculas


@dataclass(frozen=True)
class Fuente:
    """Una fuente de datos que el CLI sabe cargar."""

    cargar: Callable[[BinaryIO, Session, PeriodoNomina | None], InformeCarga]
    requiere_periodo: bool = False


# Cada fuente se registra aquí. Agregar una nueva es añadir una línea, sin tocar el resto
# del programa (principio abierto/cerrado).
FUENTES: dict[str, Fuente] = {
    "peliculas": Fuente(lambda flujo, sesion, periodo: cargar_peliculas(flujo, sesion)),
    "libros": Fuente(lambda flujo, sesion, periodo: cargar_libros(flujo, sesion)),
    "nomina": Fuente(lambda flujo, sesion, periodo: cargar_nomina(flujo, sesion, periodo), requiere_periodo=True),
}


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.etl.cli", description="Carga archivos de datos en la base.")
    parser.add_argument("fuente", choices=sorted(FUENTES), help="Tipo de archivo a cargar")
    parser.add_argument("archivo", help="Ruta del archivo (dentro del contenedor)")
    parser.add_argument("--periodo", help="Mes de las novedades, AAAA-MM (obligatorio para nómina)")
    parser.add_argument("--simulacro", action="store_true", help="Muestra el informe pero no guarda nada (puede dejar huecos en los id autoincrementales)")
    args = parser.parse_args(argumentos)
    fuente = FUENTES[args.fuente]

    periodo = None
    if fuente.requiere_periodo:
        if not args.periodo:
            print(f"La carga de {args.fuente} necesita --periodo AAAA-MM (el archivo no indica a qué mes pertenece).", file=sys.stderr)
            return 2
        try:
            periodo = PeriodoNomina.desde_texto(args.periodo)
        except ValueError as error:
            print(error, file=sys.stderr)
            return 2
    elif args.periodo:
        print(f"Aviso: --periodo no se usa al cargar {args.fuente}; se ignora.", file=sys.stderr)

    try:
        flujo = open(args.archivo, "rb")
    except OSError as error:
        print(f"No se pudo abrir '{args.archivo}': {error.strerror}", file=sys.stderr)
        return 2

    with flujo, SessionLocal() as sesion:
        try:
            informe = fuente.cargar(flujo, sesion, periodo)
        except ErrorDeArchivo as error:
            sesion.rollback()
            print(f"CARGA CANCELADA: {error}", file=sys.stderr)
            return 2
        if args.simulacro:
            sesion.rollback()
        else:
            sesion.commit()

    print(informe.resumen())
    print("\nSIMULACRO: no se guardó nada." if args.simulacro else "\nCarga guardada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
