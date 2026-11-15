"""Línea de comandos del ETL.

Uso (dentro del contenedor de la API):
    python -m app.etl.cli peliculas /data/movies.dat              # carga y guarda
    python -m app.etl.cli peliculas /data/movies.dat --simulacro  # carga, muestra el informe y DESHACE todo

Nota: un simulacro (o una carga cancelada) no devuelve los números autoincrementales que consumió,
por lo que pueden quedar huecos en los id de las tablas de catálogo. Es normal en MariaDB e inofensivo.

Códigos de salida: 0 = bien, 2 = el archivo no sirve o no se pudo abrir.
"""
import argparse
import sys
from collections.abc import Callable
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.etl.common import ErrorDeArchivo, InformeCarga
from app.etl.peliculas.service import cargar_peliculas

# Cada fuente de datos se registra aquí. Agregar libros o nómina será añadir una línea,
# sin modificar el resto del programa (principio abierto/cerrado).
CARGADORES: dict[str, Callable[[BinaryIO, Session], InformeCarga]] = {
    "peliculas": cargar_peliculas,
}


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.etl.cli", description="Carga archivos de datos en la base.")
    parser.add_argument("fuente", choices=sorted(CARGADORES), help="Tipo de archivo a cargar")
    parser.add_argument("archivo", help="Ruta del archivo (dentro del contenedor)")
    parser.add_argument("--simulacro", action="store_true", help="Muestra el informe pero no guarda nada (puede dejar huecos en los id autoincrementales)")
    args = parser.parse_args(argumentos)

    try:
        flujo = open(args.archivo, "rb")
    except OSError as error:
        print(f"No se pudo abrir '{args.archivo}': {error.strerror}", file=sys.stderr)
        return 2

    with flujo, SessionLocal() as sesion:
        try:
            informe = CARGADORES[args.fuente](flujo, sesion)
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
