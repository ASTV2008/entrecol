"""Base declarativa de la que heredan todos los modelos ORM.

Un modelo ORM es una clase Python que representa una tabla: cada atributo es una
columna y cada objeto es una fila. Todos heredan de Base, que va reuniendo en
Base.metadata el catálogo de tablas conocidas por la aplicación.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base común de todos los modelos."""
