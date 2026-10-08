"""
Cuadre de las cifras del README contra los marts.

El README publica cifras del dataset completo (14 plantas, 18 meses, seed 42).
CI genera un dataset reducido, así que aquí el test se salta; corre en local
antes de cada commit, que es cuando el README y los marts pueden separarse.
"""

import re
from pathlib import Path

import duckdb
import pytest

DB_PATH = "data/rpi.duckdb"
README = Path(__file__).resolve().parents[1] / "README.md"
PLANTAS_COMPLETO = 14


@pytest.fixture(scope="module")
def con():
    try:
        c = duckdb.connect(DB_PATH, read_only=True)
        plantas = c.execute("SELECT COUNT(DISTINCT planta) FROM stg_mb51").fetchone()[0]
    except Exception:
        pytest.skip("DuckDB o marts no disponibles en este entorno.")
    if plantas != PLANTAS_COMPLETO:
        c.close()
        pytest.skip(f"Dataset reducido ({plantas} plantas): el README es del completo.")
    yield c
    c.close()


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


def fila(readme: str, etiqueta: str) -> str:
    """Fila de una tabla markdown cuya primera celda es la etiqueta."""
    patron = rf"^\|\s*{re.escape(etiqueta)}\s*\|.*$"
    encontradas = re.findall(patron, readme, flags=re.MULTILINE)
    assert len(encontradas) == 1, f"'{etiqueta}': {len(encontradas)} filas en el README"
    return encontradas[0]


def usd(v: float) -> str:
    return f"${v:,.0f}"


def millones(v: float) -> str:
    return f"${v / 1e6:,.1f}M"


def uno(con, sql: str) -> dict:
    return con.execute(sql).pl().row(0, named=True)


def test_filas_del_dataset(con, readme):
    filas = con.execute("SELECT COUNT(*) FROM raw_mb51").fetchone()[0]
    assert f"{filas:,} movimientos" in readme


def test_kpis_fase1(con, readme):
    p = uno(
        con,
        """
        SELECT
            SUM(perdida_usd)                                        AS total,
            SUM(unidades_perdidas)::BIGINT                          AS contenedores,
            SUM(perdida_usd) FILTER (WHERE tipo_material = 'RACK')  AS rack,
            SUM(perdida_usd) FILTER (WHERE tipo_material = 'KLT')   AS klt
        FROM mart_perdidas_usd
        """,
    )
    t = uno(
        con,
        """
        SELECT SUM(faltantes) * 100.0 / SUM(salidas_conciliadas) AS tasa
        FROM mart_tco_comparativo
        """,
    )
    r = uno(
        con,
        """
        SELECT
            COUNT_IF(ruta_rota)::BIGINT                     AS rotas,
            COUNT(*)                                        AS total,
            SUM(perdida_acum_usd) FILTER (WHERE ruta_rota)  AS perdida
        FROM mart_rutas
        """,
    )

    assert usd(p["total"]) in fila(readme, "Pérdida reconocida (702)")
    assert f"{p['contenedores']:,}" in fila(readme, "Contenedores perdidos")
    assert f"{usd(p['rack'])} / {usd(p['klt'])}" in fila(readme, "Pérdida Rack / KLT")
    assert f"{t['tasa']:.3f}%" in fila(readme, "Tasa de merma de flota")
    assert f"{r['rotas']} de {r['total']}" in fila(readme, "Rutas rotas")

    pct = round(r["perdida"] * 100 / p["total"])
    assert f"{usd(r['perdida'])} ({pct}%)" in fila(readme, "Pérdida en rutas rotas")


def test_ciclo_de_flota(con, readme):
    c = uno(
        con,
        """
        SELECT ciclo_promedio_dias, ciclo_p50_dias, ciclo_p90_dias
        FROM mart_ciclo_cohortes
        WHERE nivel = 'flota'
        """,
    )
    esperado = (
        f"promedio {c['ciclo_promedio_dias']:.1f} días, "
        f"p50 {c['ciclo_p50_dias']}, p90 {c['ciclo_p90_dias']}"
    )
    assert esperado in fila(readme, "Ciclo de flota")


def test_tco_por_tipo(con, readme):
    # Misma agregación que la pestaña TCO del dashboard: ponderada por viaje.
    tipos = {
        r["tipo_material"]: r
        for r in con.execute(
            """
            SELECT
                tipo_material,
                SUM(viajes)::BIGINT                                         AS viajes,
                SUM(costo_retornable_por_ciclo_usd * viajes) / SUM(viajes)  AS costo,
                SUM(ahorro_neto_usd) / SUM(viajes)                          AS ahorro_viaje,
                SUM(vida_esperada_ciclos * viajes) / SUM(viajes)            AS vida,
                MAX(ciclos_payback)                                         AS payback,
                SUM(ahorro_neto_usd)                                        AS ahorro
            FROM mart_tco_comparativo
            GROUP BY tipo_material
            """
        )
        .pl()
        .iter_rows(named=True)
    }
    klt, rack = tipos["KLT"], tipos["RACK"]

    assert f"| {klt['viajes']:,} | {rack['viajes']:,} |" in fila(readme, "Viajes, 18 meses")
    assert f"| ${klt['costo']:.2f} | ${rack['costo']:.2f} |" in fila(
        readme, "Costo por viaje retornable"
    )
    assert f"| ${klt['ahorro_viaje']:.2f} | ${rack['ahorro_viaje']:.2f} |" in fila(
        readme, "Ahorro por viaje"
    )
    assert f"{klt['vida']:.1f} (150)" in fila(readme, "Vida esperada (vida útil)")
    assert f"{rack['vida']:.1f} (80)" in fila(readme, "Vida esperada (vida útil)")
    assert f"| {klt['payback']} viajes | {rack['payback']} viajes |" in fila(readme, "Payback")
    assert f"| {millones(klt['ahorro'])} | {millones(rack['ahorro'])} |" in fila(
        readme, "Ahorro neto, 18 meses"
    )
    assert f"**{millones(klt['ahorro'] + rack['ahorro'])} USD**" in readme


def test_equilibrio_del_rack(con, readme):
    e = uno(
        con,
        """
        SELECT
            SUM(costo_retornable_por_ciclo_usd * viajes) / SUM(viajes)  AS flota,
            MAX(costo_retornable_por_ciclo_usd)                         AS peor_planta
        FROM mart_tco_comparativo
        WHERE tipo_material = 'RACK'
        """,
    )
    assert (
        f"por debajo de ${e['flota']:.2f} por embarque en la flota "
        f"y de ${e['peor_planta']:.2f} en la planta con más merma"
    ) in readme


def test_flota_fase3a(con, readme):
    # Flota del mart y pérdidas de staging por evento, igual que assert_conservacion_flota.
    tipos = {
        r["tipo_material"]: r
        for r in con.execute(
            """
            WITH limites AS (
                SELECT MIN(fecha_cierre) AS inicio, MAX(fecha_cierre) AS corte
                FROM mart_flota_semanal
            ),
            flota AS (
                SELECT
                    tipo_material,
                    SUM(flota) FILTER (WHERE fecha_cierre = l.inicio)::BIGINT    AS inicial,
                    SUM(flota) FILTER (WHERE fecha_cierre = l.corte)::BIGINT     AS al_corte,
                    SUM(cliente) FILTER (WHERE fecha_cierre = l.corte)::BIGINT   AS cliente,
                    ANY_VALUE(l.inicio)                                         AS inicio,
                    ANY_VALUE(l.corte)                                          AS corte
                FROM mart_flota_semanal, limites l
                GROUP BY tipo_material
            ),
            perdidas AS (
                SELECT
                    m.tipo_material,
                    SUM(ABS(m.cantidad)) FILTER (WHERE c.evento = 'faltante_cliente')::BIGINT
                        AS faltante,
                    SUM(ABS(m.cantidad)) FILTER (WHERE c.evento = 'baja')::BIGINT AS baja
                FROM stg_mb51 m
                JOIN clases_movimiento c ON c.bwart = m.mov_type
                GROUP BY m.tipo_material
            )
            SELECT * FROM flota JOIN perdidas USING (tipo_material)
            """
        )
        .pl()
        .iter_rows(named=True)
    }
    klt, rack = tipos["KLT"], tipos["RACK"]
    campos = ("inicial", "faltante", "baja", "al_corte", "cliente")
    total = {c: klt[c] + rack[c] for c in campos}

    etiquetas = {
        f"Inicial al {klt['inicio']}": "inicial",
        "Faltante en cliente (702)": "faltante",
        "Baja por scrap (555)": "baja",
        f"Al corte, {klt['corte']}": "al_corte",
        "En cliente al corte (stock V)": "cliente",
    }
    for etiqueta, c in etiquetas.items():
        assert f"| {klt[c]:,} | {rack[c]:,} | {total[c]:,} |" in fila(readme, etiqueta)

    def pierde(t: dict) -> str:
        return f"{(t['faltante'] + t['baja']) * 100 / t['inicial']:.1f}%"

    assert (
        f"la flota pierde {pierde(total)}: {pierde(klt)} en KLT y {pierde(rack)} en Rack"
    ) in readme
    assert f"({rack['baja']:,} contra {rack['faltante']:,})" in readme
