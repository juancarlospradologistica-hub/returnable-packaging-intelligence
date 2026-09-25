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


def test_perdidas_solo_en_meses_de_conciliacion(con):
    """El 702 se reconoce en conciliación trimestral: marzo, junio, septiembre, diciembre."""
    fuera = con.execute("""
        SELECT COUNT(*) FROM mart_perdidas_usd
        WHERE month(mes) NOT IN (3, 6, 9, 12)
    """).fetchone()[0]
    assert fuera == 0, f"{fuera} filas con pérdida fuera de mes de conciliación"


def test_tasa_merma_entre_0_y_100(con):
    """tasa_merma_pct debe estar en [0, 100]."""
    fuera = con.execute("""
        SELECT COUNT(*) FROM mart_rutas_rotas
        WHERE tasa_merma_pct < 0 OR tasa_merma_pct > 100
    """).fetchone()[0]
    assert fuera == 0, f"{fuera} rutas con tasa_merma_pct fuera de [0, 100]"


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
    El ciclo no debe superar el cap del generador (180 días) y los
    percentiles deben venir en orden.
    """
    fuera = con.execute("""
        SELECT COUNT(*) FROM mart_rotacion_planta
        WHERE ciclo_promedio_dias > 180
           OR ciclo_p50_dias > ciclo_p90_dias
    """).fetchone()[0]
    assert fuera == 0, f"{fuera} filas con ciclo fuera de rango o percentiles invertidos"


def test_rutas_rotas_cumplen_criterio(con):
    """
    Toda ruta en mart_rutas_rotas cumple al menos un criterio de ADR-012:
    merma > 1.0 % por viaje o ciclo > 45 días.
    """
    sin_criterio = con.execute("""
        SELECT COUNT(*) FROM mart_rutas_rotas
        WHERE (tasa_merma_pct IS NULL OR tasa_merma_pct <= 1.0)
          AND (ciclo_promedio_dias IS NULL OR ciclo_promedio_dias <= 45)
    """).fetchone()[0]
    assert sin_criterio == 0, (
        f"{sin_criterio} rutas en mart_rutas_rotas que no cumplen "
        "ningún criterio de clasificación"
    )


def test_tco_costo_retornable_positivo(con):
    """El costo por ciclo del retornable debe ser mayor que cero."""
    invalidos = con.execute("""
        SELECT COUNT(*) FROM mart_tco_comparativo
        WHERE costo_retornable_por_ciclo_usd <= 0
    """).fetchone()[0]
    assert invalidos == 0, f"{invalidos} filas con costo_retornable_por_ciclo_usd <= 0"


def test_tco_ciclos_payback_positivo(con):
    """Donde exista payback calculado, debe ser un entero positivo."""
    invalidos = con.execute("""
        SELECT COUNT(*) FROM mart_tco_comparativo
        WHERE ciclos_payback IS NOT NULL
          AND ciclos_payback <= 0
    """).fetchone()[0]
    assert invalidos == 0, f"{invalidos} filas con ciclos_payback <= 0"


def test_tco_tipos_validos(con):
    """Solo KLT y RACK: el cartón es desechable y no entra al TCO (ADR-011)."""
    invalidos = con.execute("""
        SELECT COUNT(*) FROM mart_tco_comparativo
        WHERE tipo_material NOT IN ('KLT', 'RACK')
    """).fetchone()[0]
    assert invalidos == 0, f"{invalidos} filas con tipo_material invalido"


def test_tco_vida_esperada_en_rango(con):
    """Con merma, la vida esperada es positiva y no pasa de la vida útil."""
    fuera = con.execute("""
        SELECT COUNT(*) FROM mart_tco_comparativo
        WHERE vida_esperada_ciclos <= 0
           OR vida_esperada_ciclos > vida_util_ciclos
    """).fetchone()[0]
    assert fuera == 0, f"{fuera} filas con vida esperada fuera de (0, vida útil]"
