"""
Extracto sin plan de producción (ADR-037). Un extracto real puede traer MB51,
foto y maestro sin partes, instrucción de empaque ni plan. La ingesta crea esas
tablas vacías con las columnas del contrato: la necesidad de flota, la brecha y
la red de préstamos salen sin filas, todo lo demás sale igual que con plan y el
dashboard avisa en lugar de tronar.

Corre con data/rpi.duckdb y data/sinplan.duckdb construidas (CI las arma); sin
ellas se salta.
"""

import html
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

RAIZ = Path(__file__).resolve().parents[1]
LIMPIA = "data/rpi.duckdb"
SIN_PLAN = os.environ.get("RPI_DB_SIN_PLAN", "data/sinplan.duckdb")
LA, SP = Path(LIMPIA).stem, Path(SIN_PLAN).stem

DEL_PLAN = [
    "mart_necesidad_flota",
    "mart_brecha_flota",
    "mart_sensibilidad_brecha",
    "mart_red_prestamos",
]
SIN_PLAN_IGUAL = [
    "mart_rutas",
    "mart_rutas_rotas",
    "mart_perdidas_usd",
    "mart_tco_comparativo",
    "mart_flota_semanal",
    "mart_rotacion_planta",
    "mart_ciclo_cohortes",
    "mart_exceso_saldo_ruta",
    "mart_calidad_datos",
]


@pytest.fixture(scope="module")
def con():
    if not (Path(LIMPIA).exists() and Path(SIN_PLAN).exists()):
        pytest.skip("Sin data/rpi.duckdb y data/sinplan.duckdb construidas.")
    c = duckdb.connect()
    for base in (LIMPIA, SIN_PLAN):
        c.execute(f"ATTACH '{base}' AS {Path(base).stem} (READ_ONLY)")
    yield c
    c.close()


def test_sin_plan_en_la_base(con):
    for tabla in ("raw_partes", "raw_instruccion_empaque", "raw_plan_produccion"):
        assert con.sql(f"SELECT count(*) FROM {SP}.{tabla}").fetchone()[0] == 0


@pytest.mark.parametrize("mart", DEL_PLAN)
def test_lo_del_plan_sale_vacio(con, mart):
    assert con.sql(f"SELECT count(*) FROM {LA}.{mart}").fetchone()[0] > 0
    assert con.sql(f"SELECT count(*) FROM {SP}.{mart}").fetchone()[0] == 0


@pytest.mark.parametrize("mart", SIN_PLAN_IGUAL)
def test_lo_demas_no_cambia(con, mart):
    limpia, sin = f"SELECT * FROM {LA}.{mart}", f"SELECT * FROM {SP}.{mart}"
    diferentes = con.sql(
        f"SELECT (SELECT count(*) FROM (({limpia}) EXCEPT ALL ({sin}))) "
        f"+ (SELECT count(*) FROM (({sin}) EXCEPT ALL ({limpia})))"
    ).fetchone()[0]
    assert diferentes == 0


def test_dashboard_avisa_sin_plan(con, tmp_path):
    salida = tmp_path / "dashboard.html"
    r = subprocess.run(
        # Sin el código: un comentario de la celda dice lo mismo que el aviso.
        [sys.executable, "-m", "marimo", "export", "html", "notebooks/02_dashboard.py"]
        + ["--no-include-code", "-o", str(salida)],
        cwd=RAIZ,
        env=os.environ | {"RPI_DB": SIN_PLAN},
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    # El HTML trae las salidas como JSON: la ó llega escapada.
    assert "Sin plan de producci" in html.unescape(salida.read_text(encoding="utf-8"))
