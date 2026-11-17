"""Pruebas de la línea de comandos del ETL.

El CLI usa SessionLocal (la base REAL); aquí se sustituye por una sesión de la base de pruebas
para no tocar datos verdaderos. Cada prueba se deshace sola.
"""
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.etl import cli
from app.models import Empleado, NovedadMensual
from excel_nomina import empleado, libro_excel, novedad


@pytest.fixture
def usar_base_de_pruebas(sesion, monkeypatch):
    monkeypatch.setattr(cli, "SessionLocal", lambda: Session(bind=sesion.get_bind(), join_transaction_mode="create_savepoint"))


@pytest.fixture
def excel(tmp_path):
    ruta = tmp_path / "Nomina.xlsx"
    ruta.write_bytes(libro_excel([empleado(5001), empleado(5002)], [novedad(5001), novedad(5002)]).getvalue())
    return str(ruta)


def contar(sesion, modelo):
    return sesion.execute(select(func.count()).select_from(modelo)).scalar_one()


def test_registro_incluye_las_tres_fuentes():
    assert set(cli.FUENTES) == {"peliculas", "libros", "nomina"}
    assert [n for n, f in cli.FUENTES.items() if f.requiere_periodo] == ["nomina"]


def test_nomina_carga_con_periodo(usar_base_de_pruebas, sesion, excel, capsys):
    assert cli.main(["nomina", excel, "--periodo", "2022-03"]) == 0
    salida = capsys.readouterr().out
    assert "periodo 03/2022" in salida and "Carga guardada." in salida
    assert (contar(sesion, Empleado), contar(sesion, NovedadMensual)) == (2, 2)


def test_nomina_simulacro_no_guarda(usar_base_de_pruebas, sesion, excel, capsys):
    assert cli.main(["nomina", excel, "--periodo", "2022-03", "--simulacro"]) == 0
    assert "SIMULACRO" in capsys.readouterr().out
    assert contar(sesion, Empleado) == 0


def test_nomina_sin_periodo_falla_y_no_guarda(usar_base_de_pruebas, sesion, excel, capsys):
    assert cli.main(["nomina", excel]) == 2
    assert "--periodo" in capsys.readouterr().err
    assert contar(sesion, Empleado) == 0


@pytest.mark.parametrize("periodo", ["2022", "2022-13", "marzo"])
def test_periodo_invalido_falla(usar_base_de_pruebas, sesion, excel, capsys, periodo):
    assert cli.main(["nomina", excel, "--periodo", periodo]) == 2
    assert "Periodo inválido" in capsys.readouterr().err
    assert contar(sesion, Empleado) == 0


def test_archivo_inexistente(capsys):
    assert cli.main(["nomina", "/no/existe.xlsx", "--periodo", "2022-03"]) == 2
    assert "No se pudo abrir" in capsys.readouterr().err


def test_archivo_que_no_es_excel_cancela(usar_base_de_pruebas, sesion, tmp_path, capsys):
    malo = tmp_path / "malo.xlsx"
    malo.write_bytes(b"no es excel")
    assert cli.main(["nomina", str(malo), "--periodo", "2022-03"]) == 2
    assert "CARGA CANCELADA" in capsys.readouterr().err
    assert contar(sesion, Empleado) == 0


def test_otras_fuentes_ignoran_periodo_con_aviso(usar_base_de_pruebas, tmp_path, capsys):
    vacio = tmp_path / "movies.dat"
    vacio.write_bytes(b"")
    cli.main(["peliculas", str(vacio), "--periodo", "2022-03"])
    assert "--periodo no se usa" in capsys.readouterr().err


def test_peliculas_sigue_funcionando(usar_base_de_pruebas, tmp_path, capsys):
    archivo = tmp_path / "movies.dat"
    archivo.write_bytes("1::Toy Story (1995)::Animation|Comedy\n".encode())
    assert cli.main(["peliculas", str(archivo)]) == 0
    assert "Carga guardada." in capsys.readouterr().out
