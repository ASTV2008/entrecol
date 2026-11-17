"""Piezas compartidas por todos los ETL (películas, libros y nómina).

Un ETL tiene tres pasos, y cada uno vive en su propio módulo para poder
probarlo por separado:
    1. Extraer     -> lee el archivo y entrega filas "crudas" (tal como vienen)
    2. Transformar -> valida y limpia cada fila; si no sirve, la RECHAZA con un motivo
    3. Cargar      -> guarda en la base de datos las filas ya limpias
"""
from dataclasses import dataclass, field


class ErrorDeArchivo(Exception):
    """El archivo completo no sirve (vacío, mal codificado, no es el esperado).

    No confundir con un Rechazo: un Rechazo descarta UNA fila y la carga sigue;
    este error cancela la carga completa y no se guarda nada.
    """


@dataclass(frozen=True)
class Rechazo:
    """Una fila descartada, con el motivo, para que el usuario pueda corregirla."""

    linea: int       # posición de la fila en el archivo origen
    motivo: str      # explicación en lenguaje claro
    contenido: str   # fila original (recortada)
    origen: str = ""  # dónde estaba la fila si el archivo tiene varias partes (p. ej. la hoja del Excel)


@dataclass
class InformeCarga:
    """Resultado de una carga: qué se leyó, qué se guardó y qué se rechazó."""

    fuente: str
    unidad_fila: str = "línea"   # cómo llamar a una fila en los mensajes ("línea" en texto, "registro" en JSON)
    leidas: int = 0
    aceptadas: int = 0
    nuevas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    rechazos: list[Rechazo] = field(default_factory=list)
    detalles: dict[str, int] = field(default_factory=dict)   # contadores propios de cada fuente
    advertencias: list[str] = field(default_factory=list)    # datos raros que NO son errores

    @property
    def rechazadas(self) -> int:
        return len(self.rechazos)

    def resumen(self, max_rechazos: int = 10) -> str:
        """Texto legible para la terminal."""
        filas = [
            ("Filas leídas", self.leidas),
            ("Aceptadas", self.aceptadas),
            ("Rechazadas", self.rechazadas),
            ("Nuevas", self.nuevas),
            ("Actualizadas", self.actualizadas),
            ("Sin cambios", self.sin_cambios),
        ] + list(self.detalles.items())
        texto = [f"Informe de carga: {self.fuente}"]
        texto += [f"  {nombre:<24}{valor:>8}" for nombre, valor in filas]
        for aviso in self.advertencias:
            texto.append(f"  AVISO: {aviso}")
        if self.rechazos:
            texto.append(f"  Primeras {min(max_rechazos, self.rechazadas)} filas rechazadas:")
            for r in self.rechazos[:max_rechazos]:
                donde = f"{r.origen}, " if r.origen else ""
                texto.append(f"    {donde}{self.unidad_fila} {r.linea}: {r.motivo} -> {r.contenido!r}")
        return "\n".join(texto)

    def a_dict(self) -> dict:
        """Forma serializable (la usará la API cuando la carga se haga desde el navegador)."""
        return {
            "fuente": self.fuente,
            "leidas": self.leidas,
            "aceptadas": self.aceptadas,
            "rechazadas": self.rechazadas,
            "nuevas": self.nuevas,
            "actualizadas": self.actualizadas,
            "sin_cambios": self.sin_cambios,
            "detalles": dict(self.detalles),
            "advertencias": list(self.advertencias),
            "rechazos": [
                {"linea": r.linea, "motivo": r.motivo, "contenido": r.contenido, "origen": r.origen}
                for r in self.rechazos
            ],
        }
