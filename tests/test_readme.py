"""
Cuadre de las cifras del README contra los marts.

El README publica cifras del dataset completo (14 plantas, 18 meses, seed 42).
CI genera un dataset reducido, así que aquí el test se salta; corre en local
antes de cada commit, que es cuando el README y los marts pueden separarse.
"""

import json
import re
from pathlib import Path

import duckdb
import polars as pl
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


def test_entrada(con, readme):
    # Las cifras de la entrada salen de los mismos marts que las tablas de cada fase.
    p = uno(con, "SELECT SUM(perdida_usd) AS total FROM mart_perdidas_usd")
    r = uno(
        con,
        """
        SELECT COUNT_IF(ruta_rota)::BIGINT AS rotas, COUNT(*) AS total,
               SUM(perdida_acum_usd) FILTER (WHERE ruta_rota) AS perdida
        FROM mart_rutas
        """,
    )
    pct = round(r["perdida"] * 100 / p["total"])
    assert f"{usd(p['total'])} USD, {pct}% en {r['rotas']} de {r['total']} rutas" in fila(
        readme, "Pérdida reconocida"
    )

    ahorro = dict(
        con.execute(
            "SELECT tipo_material, SUM(ahorro_neto_usd) / SUM(viajes) "
            "FROM mart_tco_comparativo GROUP BY 1"
        ).fetchall()
    )
    assert f"${ahorro['RACK']:.2f} por viaje en Rack y ${ahorro['KLT']:.2f} en KLT" in fila(
        readme, "Ahorro contra desechable"
    )

    b = uno(
        con,
        """
        SELECT SUM(usd_flete + usd_compra + usd_desechable) AS brecha,
               SUM(usd_capital_ocioso) AS ocioso
        FROM mart_brecha_flota
        """,
    )
    assert (
        f"${b['brecha'] / 1e3:,.1f}k para cubrirla, con ${b['ocioso'] / 1e6:,.1f}M de flota parada"
        in fila(readme, "Brecha de flota contra el plan")
    )

    defectos = con.execute("SELECT COUNT(DISTINCT defecto) FROM mart_impacto_defectos").fetchone()
    assert f"{defectos[0]} defectos de un extracto real" in fila(readme, "Calidad de datos")


def test_adrs(readme):
    proyecto = (README.parent / "PROYECTO.md").read_text(encoding="utf-8")
    # ADR-017 y ADR-018 van con sangría; markdown acepta hasta tres espacios.
    adrs = set(re.findall(r"^ {0,3}### (ADR-\d{3})", proyecto, flags=re.MULTILINE))
    assert f"{len(adrs)} ADRs en `PROYECTO.md`" in readme


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


def k(v: float) -> str:
    return f"${v / 1e3:,.0f}k"


def test_brecha_fase3b(con, readme):
    # Misma agregación que el notebook 04: mart_brecha_flota por tipo, flota de
    # int_flota_proyectada en la última semana del plan.
    b = {
        r["tipo_material"]: r
        for r in con.execute(
            """
            WITH brecha AS (
                SELECT tipo_material,
                       COUNT(*) FILTER (WHERE deficit_pico > 0)      AS materiales,
                       SUM(deficit_pico)                             AS deficit,
                       SUM(recibido_mismo_pais)                      AS mismo_pais,
                       SUM(recibido_otro_pais)                       AS otro_pais,
                       SUM(compra)::BIGINT                           AS compra,
                       SUM(viajes_desechable)                        AS viajes,
                       SUM(usd_flete + usd_compra + usd_desechable)  AS usd_brecha,
                       SUM(usd_compra)                               AS usd_compra,
                       SUM(usd_desechable)                           AS usd_desechable,
                       SUM(usd_capital_ocioso)                       AS usd_ocioso
                FROM mart_brecha_flota
                GROUP BY 1
            ),
            flota AS (
                SELECT f.tipo_material,
                       SUM(f.flota_proyectada)                       AS flota,
                       SUM(n.necesidad)::BIGINT                      AS necesidad
                FROM int_flota_proyectada f
                JOIN mart_necesidad_flota n USING (planta, material, semana)
                WHERE f.semana = (SELECT MAX(semana) FROM int_flota_proyectada)
                GROUP BY 1
            )
            SELECT s.tipo_material, s.z_servicio, s.necesidad_semana_1, b.*, f.flota,
                   f.necesidad AS necesidad_12
            FROM mart_sensibilidad_brecha s
            JOIN brecha b USING (tipo_material)
            JOIN flota f USING (tipo_material)
            WHERE s.escenario = 'base'
            """
        )
        .pl()
        .iter_rows(named=True)
    }
    klt, rack = b["KLT"], b["RACK"]

    def celdas(etiqueta: str, fmt) -> None:
        assert f"| {fmt(klt)} | {fmt(rack)} |" in fila(readme, etiqueta), etiqueta

    celdas("z por costo", lambda t: f"{t['z_servicio']:.2f}")
    celdas("Necesidad semana 1", lambda t: f"{t['necesidad_semana_1']:,}")
    celdas("Flota proyectada semana 12", lambda t: f"{t['flota']:,.0f}")
    celdas("Materiales en déficit", lambda t: f"{t['materiales']:,}")
    celdas("Déficit pico", lambda t: f"{t['deficit']:,.0f}")
    celdas("Préstamo dentro del país", lambda t: f"{t['mismo_pais']:,.0f}")
    celdas("Préstamo entre países", lambda t: f"{t['otro_pais']:,.0f}")
    celdas("Compra", lambda t: f"{t['compra']:,}")
    celdas("Viajes en desechable", lambda t: f"{t['viajes']:,.0f}")
    celdas("Costo de la brecha", lambda t: usd(t["usd_brecha"]))
    celdas("Capital ocioso", lambda t: f"${t['usd_ocioso'] / 1e6:,.1f}M")

    def sobra(t: dict) -> str:
        return f"{(t['flota'] - t['necesidad_12']) * 100 / t['necesidad_12']:.1f}%"

    brecha = klt["usd_brecha"] + rack["usd_brecha"]
    ocioso = klt["usd_ocioso"] + rack["usd_ocioso"]
    cubre = (
        sum(t["mismo_pais"] + t["otro_pais"] for t in (klt, rack))
        * 100
        / (klt["deficit"] + rack["deficit"])
    )
    assert f"{sobra(klt)} sobre la necesidad en KLT y {sobra(rack)} en Rack" in readme
    assert f"{klt['materiales']:,} KLT y {rack['materiales']:,} Rack quedan cortos" in readme
    assert f"El préstamo cubre el {cubre:.1f}% del déficit" in readme
    assert f"cubrir la brecha cuesta ${brecha / 1e3:,.1f}k" in readme
    assert f"quedan ${ocioso / 1e6:,.1f}M de flota parada, {ocioso / brecha:.0f} veces" in readme
    desechable = rack["usd_desechable"] * 100 / rack["usd_compra"]
    assert (
        f"el desechable ({usd(rack['usd_desechable'])}) cuesta {desechable:.0f}% de la compra "
        f"({usd(rack['usd_compra'])})"
    ) in readme


def test_sensibilidad_fase3b(con, readme):
    t = dict(
        con.execute(
            "SELECT escenario, SUM(usd_brecha) FROM mart_sensibilidad_brecha GROUP BY 1"
        ).fetchall()
    )
    o = dict(
        con.execute(
            "SELECT escenario, SUM(usd_capital_ocioso) FROM mart_sensibilidad_brecha GROUP BY 1"
        ).fetchall()
    )
    klt = dict(
        con.execute(
            """
            SELECT escenario, usd_brecha FROM mart_sensibilidad_brecha
            WHERE tipo_material = 'KLT'
            """
        ).fetchall()
    )
    nec = dict(
        con.execute(
            """
            SELECT escenario, necesidad_semana_1 FROM mart_sensibilidad_brecha
            WHERE tipo_material = 'KLT'
            """
        ).fetchall()
    )
    costo = con.execute(
        "SELECT MAX(costo_unitario_usd) FROM mart_tco_comparativo WHERE tipo_material = 'KLT'"
    ).fetchone()[0]
    ss = dict(
        con.execute(
            "SELECT tipo_material, MIN(stock_seguridad_dias) FROM mart_necesidad_flota GROUP BY 1"
        ).fetchall()
    )
    filas, en_piso = con.execute(
        "SELECT COUNT(*), COUNT(*) FILTER (WHERE stock_seguridad_dias <= 7) "
        "FROM mart_necesidad_flota"
    ).fetchone()

    assert f"de {k(t['quiebre_1'])} con factor 1 a {k(t['quiebre_3'])} con factor 3" in readme
    assert f"{k(t['optimista'])} de brecha y ${o['optimista'] / 1e6:,.1f}M ociosos" in readme
    assert f"{k(t['conservador'])} y ${o['conservador'] / 1e6:,.1f}M" in readme
    assert f"ADR-021: {k(t['z_fija_3'])} y ${o['z_fija_3'] / 1e6:,.1f}M" in readme
    libera = nec["base"] - nec["lavado_klt_1_dia"]
    assert (
        f"vale {libera:,} contenedores de necesidad, ${libera * float(costo) / 1e6:,.2f}M"
    ) in readme
    assert (
        f"la brecha KLT va de {k(klt['lavado_klt_1_dia'])} a {k(klt['lavado_klt_3_dias'])}"
    ) in readme
    assert en_piso == 0
    assert f"ninguna de las {filas:,} filas" in readme
    assert f"{ss['KLT']:.1f} días en KLT y {ss['RACK']:.1f} en Rack" in readme


def test_conteos_dbt(readme):
    """Los conteos de dbt del README salen del manifest de la última corrida."""
    manifest = Path(__file__).resolve().parents[1] / "target" / "manifest.json"
    if not manifest.exists():
        pytest.skip("Sin target/manifest.json: corre dbt build antes.")
    m = json.loads(manifest.read_text(encoding="utf-8"))
    nodos = [n for n in m["nodes"].values() if n["package_name"] == "rpi"]

    def cuenta(tipo: str) -> int:
        return sum(n["resource_type"] == tipo for n in nodos)

    texto = (
        f"{cuenta('model')} modelos, {cuenta('seed')} seeds, {cuenta('test')} tests de datos "
        f"y {len(m['unit_tests'])} unit tests"
    )
    assert texto in readme, texto
    assert (
        texto.replace(" modelos, ", " modelos dbt y ").replace(" seeds, ", " seeds con ") in readme
    )
    # La entrada no cuenta los seeds.
    assert texto.replace(f"{cuenta('seed')} seeds, ", "") in readme


# Fase 4: la medición del arnés no depende del dataset abierto (docs/calidad),
# así que estas cifras se cuadran también en CI.
NOMBRE = {
    "perdida": "Pérdida",
    "tco": "Ahorro TCO",
    "brecha": "Brecha",
    "ocioso": "Ocioso",
    "ciclo": "Ciclo",
    "necesidad": "Necesidad",
    "flota": "Flota",
}
IDENTIDAD = {"llave": "llave", "stock": "stock", "saldo": "saldo", "conservacion": "conservación"}
USD_CIFRAS = ["perdida", "tco", "brecha", "ocioso"]


@pytest.fixture(scope="module")
def impacto() -> pl.DataFrame:
    try:
        c = duckdb.connect(DB_PATH, read_only=True)
        df = c.execute("SELECT * FROM mart_impacto_defectos").pl()
        c.close()
    except Exception:
        pytest.skip("Sin mart_impacto_defectos: corre dbt antes.")
    return df


def _cifras(impacto: pl.DataFrame) -> pl.DataFrame:
    return impacto.filter(pl.col("tipo") == "cifra")


def _mas_mueve(impacto: pl.DataFrame, defecto: str, nivel: str) -> str:
    s = _cifras(impacto).filter((pl.col("defecto") == defecto) & (pl.col("nivel") == nivel))
    if s["delta_pct"].null_count():
        return f"{NOMBRE[s.filter(pl.col('delta_pct').is_null())['medida'][0]]} sin valor"
    r = s.sort(pl.col("delta_pct").abs(), descending=True).row(0, named=True)
    return "nada" if abs(r["delta_pct"]) < 0.05 else f"{NOMBRE[r['medida']]} {r['delta_pct']:+.1f}%"


def _delta(impacto: pl.DataFrame, defecto: str, nivel: str, cifra: str) -> float:
    return (
        _cifras(impacto)
        .filter(
            (pl.col("defecto") == defecto)
            & (pl.col("nivel") == nivel)
            & (pl.col("medida") == cifra)
        )["delta_pct"]
        .item()
    )


def test_fase4_tabla_por_defecto(impacto, readme):
    rotas = impacto.filter((pl.col("tipo") == "identidad") & (pl.col("valor") > 0))
    for d in sorted(impacto["defecto"].unique()):
        r = impacto.filter(pl.col("defecto") == d).row(0, named=True)
        medidas = set(rotas.filter(pl.col("defecto") == d)["medida"])
        identidad = ", ".join(v for k, v in IDENTIDAD.items() if k in medidas) or "—"
        esperado = (
            f"| {d} | `{r['regla']}` | {r['severidad']} | {identidad} | "
            f"{_mas_mueve(impacto, d, 'tasa')} | {_mas_mueve(impacto, d, 'techo')} |"
        )
        assert esperado == fila(readme, d), d


def test_fase4_hallazgos(impacto, readme):
    corridas = impacto.unique(["defecto", "nivel"])
    assert (corridas["detectados"] == corridas["casos"]).all()
    defectos = corridas["defecto"].n_unique()
    assert f"El catálogo tiene hoy {defectos} defectos" in readme
    assert "reporta el 100% de lo inyectado en los dos niveles" in readme

    d = lambda *a: f"{_delta(impacto, *a):+.1f}%"  # noqa: E731
    assert f"pérdida reconocida {d('D18', 'tasa', 'perdida')} y el capital ocioso " in readme
    assert f"{d('D18', 'tasa', 'ocioso')}." in readme
    assert f"mueve la brecha {d('D05', 'tasa', 'brecha')} a la tasa del catálogo y " in readme
    assert f"{d('D05', 'techo', 'brecha')} en el techo" in readme
    assert f"el ciclo de flota baja {d('D06', 'tasa', 'ciclo')}" in readme
    assert _delta(impacto, "D06", "techo", "ciclo") is None

    ocioso = _cifras(impacto).filter((pl.col("medida") == "ocioso") & pl.col("supera_materialidad"))
    assert f"La mueven {ocioso['defecto'].n_unique()} de los {defectos} defectos" in readme

    expuesto = impacto.filter(
        (pl.col("tipo") == "regla")
        & (pl.col("nivel") == "tasa")
        & (pl.col("medida") == pl.col("regla"))
        & pl.col("usd_expuesto").is_not_null()
    ).select("defecto", "usd_expuesto")
    maximo = (
        _cifras(impacto)
        .filter((pl.col("nivel") == "tasa") & pl.col("medida").is_in(USD_CIFRAS))
        .group_by("defecto")
        .agg(pl.col("delta_pct").abs().max().alias("delta"))
    )
    puntos = expuesto.join(maximo, on="defecto")
    rangos = (
        puntos.with_columns(
            pl.col("usd_expuesto").rank().alias("rx"), pl.col("delta").rank().alias("ry")
        )
        .select(pl.corr("rx", "ry"))
        .item()
    )
    p = {r["defecto"]: r for r in puntos.iter_rows(named=True)}
    assert (
        f"D06 expone {millones(p['D06']['usd_expuesto'])} y mueve {p['D06']['delta']:.1f}% "
        f"una cifra en USD; D05 expone {millones(p['D05']['usd_expuesto'])} y mueve la brecha "
        f"{p['D05']['delta']:.1f}%"
    ) in readme
    assert f"en los {puntos.height} defectos con valor expuesto, es {rangos:.2f}" in readme

    otras = dict(
        impacto.filter(
            (pl.col("tipo") == "regla")
            & (pl.col("nivel") == "tasa")
            & (pl.col("medida") == "recogida_sin_saldo")
            & (pl.col("regla") != "recogida_sin_saldo")
        )
        .select("defecto", "valor")
        .iter_rows()
    )
    assert (
        f"D01, D02 y D04 dejan {otras['D01']:,.0f}, {otras['D02']:,.0f} y {otras['D04']:,.0f} "
        "recogidas sin saldo"
    ) in readme


def test_fase4_tiempo_del_arnes(readme):
    # El limpio no está en el mart: el tiempo total sale de la medición completa.
    try:
        c = duckdb.connect(DB_PATH, read_only=True)
        corridas, segundos = c.execute(
            """
            SELECT COUNT(*), SUM(segundos)
            FROM (SELECT DISTINCT defecto, nivel, segundos FROM stg_impacto_defectos)
            """
        ).fetchone()
        c.close()
    except Exception:
        pytest.skip("Sin stg_impacto_defectos: corre dbt antes.")
    assert f"{corridas} corridas en {round(segundos / 60)} min" in readme


# Fase 4c: los ciegos antes y después de su regla (ADR-033, ADR-034).
SIMULA = {
    "B01": "Matnr con ceros a la izquierda desde una fecha",
    "B02": "Kunnr de las recogidas con ceros desde una fecha",
    "B03": "Documento 621 contabilizado otra vez con otro número",
    "B04": "Budat después de la fecha del extracto",
}


def reglas_md(texto: str | None) -> str:
    """'a 1, b 3100' del mart como '`a` 1, `b` 3,100'."""
    if texto is None:
        return "ninguna regla"
    partes = (p.rsplit(" ", 1) for p in texto.split(", "))
    return ", ".join(f"`{regla}` {int(n):,}" for regla, n in partes)


def fila_ciego(r: dict) -> str:
    despues = f"`{r['regla']}` {r['pct_detectados_despues']:.0f}%"
    if r["otras_reglas_despues"]:
        despues += f"; también {reglas_md(r['otras_reglas_despues'])}"
    return (
        f"| {SIMULA[r['defecto']]} | {r['defecto']} | {r['casos']:,} | "
        f"{reglas_md(r['otras_reglas_antes'])} | {despues} |"
    )


@pytest.fixture(scope="module")
def ciegos() -> pl.DataFrame:
    try:
        c = duckdb.connect(DB_PATH, read_only=True)
        df = c.execute("SELECT * FROM mart_deteccion_ciegos ORDER BY defecto, nivel").pl()
        c.close()
    except Exception:
        pytest.skip("Sin mart_deteccion_ciegos: corre dbt antes.")
    return df


def test_fase4c_ciegos(ciegos, readme):
    tasa = ciegos.filter(pl.col("nivel") == "tasa")
    for r in tasa.iter_rows(named=True):
        assert fila_ciego(r) == fila(readme, SIMULA[r["defecto"]]), r["defecto"]

    def completos(columna: str) -> int:
        # Sin regla la detección es nula; .all() ignora nulos y la contaría completa.
        detectados = pl.col(columna).fill_null(-1)
        ok = ciegos.group_by("defecto").agg((detectados == pl.col("casos")).all().alias("ok"))
        return ok.filter(pl.col("ok")).height

    antes, despues = completos("detectados_antes"), completos("detectados_despues")
    assert f"**Detección por su causa: {antes} de 4 antes, {despues} de 4 después**" in readme
    assert f"con {antes} de 4 detectados por su causa, y después, con {despues} de 4" in readme

    vistos = tasa.filter(pl.col("otras_reglas_antes").is_not_null()).height
    assert f"**Antes, {vistos} de los 4 disparaban una regla de otro defecto" in readme

    b04 = {r["nivel"]: r for r in ciegos.filter(pl.col("defecto") == "B04").iter_rows(named=True)}
    assert (
        f"B04 movía la brecha {b04['tasa']['delta_pct_antes']:+.1f}% con cualquier volumen"
        in readme
    )
    assert (
        f"{b04['tasa']['casos']:,} líneas movían lo mismo que {b04['techo']['casos']:,}"
    ) in readme
    assert (
        f"{b04['tasa']['delta_pct_despues']:+.1f}% a tasa y "
        f"{b04['techo']['delta_pct_despues']:+.1f}% en el techo"
    ) in readme


# Fase 5: gemelo de la red RPL (ADR-038).
ESCENARIOS_GEMELO = {
    "replay": "Traza del MB51",
    "nominal": "Lavado y reparación al 80%",
    "lavado_95": "Lavado al 95%",
    "lavado_100": "Lavado al 100%",
    "reparacion_100": "Reparación al 100%",
    "paro_lavado_5": "Paro de lavado, 5 días",
    "paro_lavado_10": "Paro de lavado, 10 días",
}


def _gemelo(con) -> dict[str, dict]:
    filas = con.execute(
        """
        SELECT escenario,
            SUM(faltante) FILTER (WHERE tipo_material = 'KLT')::BIGINT       AS falta_klt,
            SUM(faltante) FILTER (WHERE tipo_material = 'RACK')::BIGINT      AS falta_rack,
            SUM(faltante_usd)                                                AS falta_usd,
            SUM(flota_sobra) FILTER (WHERE tipo_material = 'KLT')::BIGINT    AS sobra_klt,
            SUM(flota_sobra) FILTER (WHERE tipo_material = 'RACK')::BIGINT   AS sobra_rack,
            SUM(flota_sobra_usd)                                             AS sobra_usd
        FROM mart_sim_capacidad
        GROUP BY escenario
        """
    ).pl()
    return {r["escenario"]: r for r in filas.iter_rows(named=True)}


def filas_gemelo(con) -> str:
    """Las filas de la tabla de Fase 5, en el orden del README."""
    g = _gemelo(con)
    return "\n".join(
        f"| {etiqueta} | {g[e]['falta_klt']:,} | {g[e]['falta_rack']:,} | "
        f"{usd(g[e]['falta_usd'])} | {g[e]['sobra_klt']:,} | {g[e]['sobra_rack']:,} |"
        for e, etiqueta in ESCENARIOS_GEMELO.items()
    )


def test_gemelo_fase5(con, readme):
    g = _gemelo(con)
    assert filas_gemelo(con) in readme
    rep, lim = g["replay"], g["lavado_100"]
    assert (
        f"baja {rep['sobra_klt'] - lim['sobra_klt']:,} KLT y "
        f"{rep['sobra_rack'] - lim['sobra_rack']:,} Rack: "
        f"{millones(rep['sobra_usd'] - lim['sobra_usd'])} de flota"
    ) in readme
    assert f"cuestan {k(g['paro_lavado_5']['falta_usd'])} de desechable" in readme
    brecha = con.execute(
        "SELECT SUM(usd_flete + usd_compra + usd_desechable) FROM mart_brecha_flota"
    ).fetchone()[0]
    veces = g["paro_lavado_10"]["falta_usd"] / float(brecha)
    assert f"diez días, {k(g['paro_lavado_10']['falta_usd'])}, {veces:.1f} veces" in readme
    # La reparación al 100% no manda contenedores a desechable.
    assert g["reparacion_100"]["falta_klt"] == g["reparacion_100"]["falta_rack"] == 0
