# tests/test_marts.py
"""
Tests de dominio sobre los marts dbt.
Validan que los resultados tienen sentido de negocio,
no solo que el pipeline puede fallar.
"""

import duckdb
import pytest

DB_PATH = "data/rpi.duckdb"


@pytest.fixture(scope="module")
def con():
    try:
        c = duckdb.connect(DB_PATH, read_only=True)
        c.execute("SELECT 1 FROM mart_perdidas_usd LIMIT 1")
        yield c
        c.close()
    except Exception:
        pytest.skip("DuckDB o marts no disponibles en este entorno.")


def test_perdida_usd_positiva(con):
    """Ninguna pérdida puede ser negativa o cero."""
    invalidas = con.execute(
        "SELECT COUNT(*) FROM mart_perdidas_usd WHERE perdida_usd <= 0"
    ).fetchone()[0]
    assert invalidas == 0, f"{invalidas} filas con perdida_usd <= 0"


def test_tasa_merma_entre_0_y_100(con):
    """tasa_merma_pct debe estar en [0, 100]."""
    fuera = con.execute("""
        SELECT COUNT(*) FROM mart_perdidas_usd
        WHERE tasa_merma_pct < 0 OR tasa_merma_pct > 100
    """).fetchone()[0]
    assert fuera == 0, f"{fuera} filas con tasa_merma_pct fuera de [0, 100]"


def test_ciclo_promedio_positivo(con):
    """El ciclo promedio de retorno debe ser mayor que cero."""
    invalidos = con.execute("""
        SELECT COUNT(*) FROM mart_rotacion_planta
        WHERE ciclo_promedio_dias IS NOT NULL
          AND ciclo_promedio_dias <= 0
    """).fetchone()[0]
    assert invalidos == 0, f"{invalidos} filas con ciclo_promedio_dias <= 0"


def test_ciclo_dentro_de_rango_razonable(con):
    """
    El ciclo promedio no debe superar el cap del generador (180 días).
    Un promedio > 180 indica un problema en el cálculo del join 601→602.
    """
    fuera = con.execute("""
        SELECT COUNT(*) FROM mart_rotacion_planta
        WHERE ciclo_promedio_dias > 180
    """).fetchone()[0]
    assert fuera == 0, f"{fuera} plantas con ciclo promedio > 180 días"


def test_rutas_rotas_tienen_merma_o_ciclo_largo(con):
    """
    Toda ruta en mart_rutas_rotas debe cumplir al menos uno
    de los dos criterios de clasificación: merma > 5% o ciclo > 45 días.
    """
    sin_criterio = con.execute("""
        SELECT COUNT(*) FROM mart_rutas_rotas
        WHERE tasa_merma_pct <= 5
          AND (ciclo_promedio_dias IS NULL OR ciclo_promedio_dias <= 45)
    """).fetchone()[0]
    assert sin_criterio == 0, (
        f"{sin_criterio} rutas en mart_rutas_rotas que no cumplen "
        "ningún criterio de clasificación"
    )