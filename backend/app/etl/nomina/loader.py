"""CARGAR: guarda en la base los empleados y las novedades de UN periodo.

Mismas reglas que los demás cargadores:
    - Repetible (idempotente): cargar el mismo archivo dos veces no duplica ni cambia nada.
    - Solo AGREGA y ACTUALIZA; nunca borra empleados ni novedades que no vengan en el archivo.
    - NO hace commit: la transacción la controla quien llama (todo-o-nada y simulacro).
Los nombres de catálogo (dependencia, cargo, EPS, ARL, fondo) los resuelve la base de datos.
"""
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.etl.catalogos import ResultadoCatalogo, ResultadoCatalogoConPadre, asegurar_catalogo, asegurar_catalogo_con_padre
from app.etl.nomina.transformer import EmpleadoLimpio, EventoLimpio, NovedadLimpia
from app.models import Arl, Cargo, Dependencia, Empleado, Eps, FondoPension, Incapacidad, NovedadMensual, Periodo, Vacacion


@dataclass
class ResultadoCargaNomina:
    nuevas: int = 0               # empleados + novedades creados
    actualizadas: int = 0
    sin_cambios: int = 0
    empleados_nuevos: int = 0
    novedades_nuevas: int = 0
    incapacidades: int = 0        # eventos que debe tener la base según el archivo
    vacaciones: int = 0
    periodo_nuevo: bool = False
    dependencias: ResultadoCatalogo | None = None
    cargos: ResultadoCatalogoConPadre | None = None
    eps: ResultadoCatalogo | None = None
    arl: ResultadoCatalogo | None = None
    fondos: ResultadoCatalogo | None = None


def _como_tupla(evento: EventoLimpio | None) -> tuple:
    return () if evento is None else ((evento.inicio, evento.fin, evento.dias_reportados),)


class CargadorNomina:
    TAMANO_LOTE = 500

    def __init__(self, sesion: Session, anio: int, mes: int) -> None:
        self._sesion = sesion
        self._anio, self._mes = anio, mes

    def cargar(self, empleados: Sequence[EmpleadoLimpio], novedades: Sequence[NovedadLimpia]) -> ResultadoCargaNomina:
        resultado = ResultadoCargaNomina()
        self._cargar_empleados(empleados, resultado)
        self._cargar_novedades(novedades, resultado)
        return resultado

    # ------------------------------------------------------------ empleados
    def _cargar_empleados(self, empleados: Sequence[EmpleadoLimpio], r: ResultadoCargaNomina) -> None:
        if not empleados:
            return
        s = self._sesion
        r.dependencias = asegurar_catalogo(s, Dependencia.id_dependencia, Dependencia.nombre, (e.dependencia for e in empleados))
        r.eps = asegurar_catalogo(s, Eps.id_eps, Eps.nombre, (e.eps for e in empleados))
        r.arl = asegurar_catalogo(s, Arl.id_arl, Arl.nombre, (e.arl for e in empleados))
        r.fondos = asegurar_catalogo(s, FondoPension.id_fondo_pension, FondoPension.nombre, (e.fondo_pension for e in empleados))
        r.cargos = asegurar_catalogo_con_padre(
            s, Cargo.id_cargo, Cargo.id_dependencia, Cargo.nombre,
            ((r.dependencias.ids[e.dependencia], e.cargo) for e in empleados),
        )
        for inicio in range(0, len(empleados), self.TAMANO_LOTE):
            lote = empleados[inicio : inicio + self.TAMANO_LOTE]
            codigos = [e.codigo for e in lote]
            actuales = {
                f[0]: tuple(f[1:])
                for f in s.execute(
                    select(Empleado.codigo, Empleado.nombre_empleado, Empleado.fecha_ingreso, Empleado.sueldo,
                           Empleado.id_cargo, Empleado.id_eps, Empleado.id_arl, Empleado.id_fondo_pension)
                    .where(Empleado.codigo.in_(codigos))
                )
            }
            nuevos, cambiados = [], []
            for e in lote:
                fila = self._fila_empleado(e, r)
                esperado = (fila["nombre_empleado"], fila["fecha_ingreso"], fila["sueldo"], fila["id_cargo"],
                            fila["id_eps"], fila["id_arl"], fila["id_fondo_pension"])
                if e.codigo not in actuales:
                    nuevos.append(fila)
                elif actuales[e.codigo] != esperado:
                    cambiados.append(fila)
                else:
                    r.sin_cambios += 1
            if nuevos:
                s.execute(insert(Empleado), nuevos)
            if cambiados:
                s.execute(update(Empleado), cambiados)
            r.nuevas += len(nuevos)
            r.empleados_nuevos += len(nuevos)
            r.actualizadas += len(cambiados)

    @staticmethod
    def _fila_empleado(e: EmpleadoLimpio, r: ResultadoCargaNomina) -> dict:
        return {
            "codigo": e.codigo, "nombre_empleado": e.nombre, "fecha_ingreso": e.fecha_ingreso, "sueldo": e.sueldo,
            "id_cargo": r.cargos.ids[(r.dependencias.ids[e.dependencia], e.cargo)],
            "id_eps": r.eps.ids[e.eps], "id_arl": r.arl.ids[e.arl], "id_fondo_pension": r.fondos.ids[e.fondo_pension],
        }

    # ------------------------------------------------------------ novedades
    def _id_periodo(self, r: ResultadoCargaNomina) -> int:
        s = self._sesion
        id_ = s.execute(select(Periodo.id_periodo).where(Periodo.anio == self._anio, Periodo.mes == self._mes)).scalar_one_or_none()
        if id_ is None:
            id_ = s.execute(insert(Periodo).values(anio=self._anio, mes=self._mes)).inserted_primary_key[0]
            r.periodo_nuevo = True
        return id_

    def _cargar_novedades(self, novedades: Sequence[NovedadLimpia], r: ResultadoCargaNomina) -> None:
        if not novedades:
            return
        s = self._sesion
        id_periodo = self._id_periodo(r)
        for inicio in range(0, len(novedades), self.TAMANO_LOTE):
            lote = novedades[inicio : inicio + self.TAMANO_LOTE]
            codigos = [n.codigo for n in lote]
            actuales = {
                f[0]: (f[1], f[2], f[3])
                for f in s.execute(
                    select(NovedadMensual.codigo, NovedadMensual.id_novedad, NovedadMensual.bonificacion, NovedadMensual.transporte)
                    .where(NovedadMensual.id_periodo == id_periodo, NovedadMensual.codigo.in_(codigos))
                )
            }
            ids_actuales = [v[0] for v in actuales.values()]
            eventos_actuales = {
                "inc": self._eventos_en_base(Incapacidad, ids_actuales),
                "vac": self._eventos_en_base(Vacacion, ids_actuales),
            }
            nuevas, cambiadas = [], []
            for n in lote:
                r.incapacidades += len(_como_tupla(n.incapacidad))
                r.vacaciones += len(_como_tupla(n.vacacion))
                if n.codigo not in actuales:
                    nuevas.append(n)
                    continue
                id_nov, bonif, transp = actuales[n.codigo]
                igual = (
                    (bonif, transp) == (n.bonificacion, n.transporte)
                    and eventos_actuales["inc"].get(id_nov, ()) == _como_tupla(n.incapacidad)
                    and eventos_actuales["vac"].get(id_nov, ()) == _como_tupla(n.vacacion)
                )
                if igual:
                    r.sin_cambios += 1
                else:
                    cambiadas.append(n)

            if nuevas:
                s.execute(insert(NovedadMensual), [self._fila_novedad(n, id_periodo) for n in nuevas])
            if cambiadas:
                s.execute(update(NovedadMensual), [
                    {"id_novedad": actuales[n.codigo][0], "bonificacion": n.bonificacion, "transporte": n.transporte}
                    for n in cambiadas
                ])
            r.nuevas += len(nuevas)
            r.novedades_nuevas += len(nuevas)
            r.actualizadas += len(cambiadas)

            a_reescribir = nuevas + cambiadas
            if a_reescribir:
                self._reescribir_eventos(a_reescribir, id_periodo)

    @staticmethod
    def _fila_novedad(n: NovedadLimpia, id_periodo: int) -> dict:
        return {"codigo": n.codigo, "id_periodo": id_periodo, "bonificacion": n.bonificacion, "transporte": n.transporte}

    def _eventos_en_base(self, modelo, ids_novedad: list[int]) -> dict[int, tuple]:
        if not ids_novedad:
            return {}
        filas = self._sesion.execute(
            select(modelo.id_novedad, modelo.fecha_inicio, modelo.fecha_fin, modelo.dias_reportados)
            .where(modelo.id_novedad.in_(ids_novedad)).order_by(modelo.id_novedad, modelo.fecha_inicio)
        )
        resultado: dict[int, list] = {}
        for id_nov, ini, fin, dias in filas:
            resultado.setdefault(id_nov, []).append((ini, fin, dias))
        return {k: tuple(v) for k, v in resultado.items()}

    def _reescribir_eventos(self, novedades: Sequence[NovedadLimpia], id_periodo: int) -> None:
        """Reemplaza las incapacidades y vacaciones de las novedades nuevas o cambiadas."""
        s = self._sesion
        id_por_codigo = {
            codigo: id_nov
            for codigo, id_nov in s.execute(
                select(NovedadMensual.codigo, NovedadMensual.id_novedad)
                .where(NovedadMensual.id_periodo == id_periodo, NovedadMensual.codigo.in_([n.codigo for n in novedades]))
            )
        }
        ids = list(id_por_codigo.values())
        for modelo in (Incapacidad, Vacacion):
            s.execute(delete(modelo).where(modelo.id_novedad.in_(ids)).execution_options(synchronize_session=False))
        for modelo, atributo in ((Incapacidad, "incapacidad"), (Vacacion, "vacacion")):
            filas = [
                {"id_novedad": id_por_codigo[n.codigo], "fecha_inicio": ev.inicio, "fecha_fin": ev.fin, "dias_reportados": ev.dias_reportados}
                for n in novedades if (ev := getattr(n, atributo)) is not None
            ]
            if filas:
                s.execute(insert(modelo), filas)
