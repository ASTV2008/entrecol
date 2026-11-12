"""Tipos de columna de MariaDB reutilizables (enteros SIN signo).

Los nombres indican el tamaño: la tabla de dependencias necesita pocos valores
(SMALLINT) y la de empleados puede crecer (INT). Deben coincidir con el DDL.
"""
from sqlalchemy.dialects.mysql import INTEGER, SMALLINT, TINYINT

UInt = INTEGER(unsigned=True)         # 0 a 4.294.967.295
USmallInt = SMALLINT(unsigned=True)   # 0 a 65.535
UTinyInt = TINYINT(unsigned=True)     # 0 a 255
