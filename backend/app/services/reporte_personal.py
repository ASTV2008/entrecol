"""Reporte 2 - INFORMACIÓN PERSONAL: ficha de cada empleado con la discriminación de sus novedades."""
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from app.repositories.nomina import RepositorioNomina
from app.schemas.reportes import EventoNovedad, FichaPersonal, NovedadPeriodo, Orden, ReportePersonal
from app.services.periodos import texto_periodo

# Aporte del TRABAJADOR a pensión: 4 % del salario (Ley 797 de 2003; el 12 % restante lo paga el empleador).
# Se CALCULA en cada consulta y no se guarda: es un dato derivado del sueldo (guardarlo violaría la 3FN).
TASA_APORTE_PENSION = Decimal("0.04")
DIAS_DEL_MES_LABORAL = 30      # misma base que usa el ETL: días trabajados = 30 - incapacidad - vacaciones


def formato_fecha(fecha) -> str:
    """DD/MM/AAAA, el formato que pide el enunciado."""
    return fecha.strftime("%d/%m/%Y")


def aporte_pension(sueldo: Decimal) -> Decimal:
    return (Decimal(sueldo) * TASA_APORTE_PENSION).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ServicioReportePersonal:
    def __init__(self, repo: RepositorioNomina) -> None:
        self._repo = repo

    def reporte(self, orden: Orden, codigo: int | None = None) -> ReportePersonal:
        fichas = self._repo.fichas(orden, codigo)
        codigos = [f.codigo for f in fichas]
        novedades = self._repo.novedades_de(codigos)
        eventos = defaultdict(lambda: {"Incapacidad": [], "Vacaciones": []})
        for e in self._repo.eventos_de([n.id_novedad for n in novedades]):
            eventos[e.id_novedad][e.tipo].append(EventoNovedad(
                fecha_inicio=formato_fecha(e.fecha_inicio), fecha_fin=formato_fecha(e.fecha_fin), dias=e.dias))

        por_empleado: dict[int, list[NovedadPeriodo]] = defaultdict(list)
        for n in novedades:
            inc, vac = eventos[n.id_novedad]["Incapacidad"], eventos[n.id_novedad]["Vacaciones"]
            trabajados = max(0, DIAS_DEL_MES_LABORAL - sum(e.dias for e in inc) - sum(e.dias for e in vac))
            por_empleado[n.codigo].append(NovedadPeriodo(
                periodo=texto_periodo(n.anio, n.mes), dias_trabajados=trabajados, incapacidades=inc, vacaciones=vac,
                bonificacion=float(n.bonificacion), transporte=float(n.transporte)))

        return ReportePersonal(
            total=len(fichas), tasa_aporte_pension=float(TASA_APORTE_PENSION),
            empleados=[
                FichaPersonal(
                    codigo=f.codigo, nombre=f.nombre, dependencia=f.dependencia, cargo=f.cargo,
                    fecha_ingreso=formato_fecha(f.fecha_ingreso), eps=f.eps, fondo_pension=f.fondo_pension,
                    aporte_pension=float(aporte_pension(f.sueldo)), sueldo=float(f.sueldo),
                    novedades=por_empleado.get(f.codigo, []),
                )
                for f in fichas
            ],
        )
