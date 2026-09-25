import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Returnable Packaging Intelligence — Dashboard

    Flota multi-planta · 18 meses · 14 plantas · datos MB51 sintéticos
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import duckdb
    import marimo as mo
    import polars as pl

    db_path = Path("data/rpi.duckdb")

    if not db_path.exists():
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**Base de datos no encontrada.**\n\n"
                    "Corre el pipeline completo antes de abrir el dashboard:\n\n"
                    "```bash\n"
                    "uv run python -m rpi\n"
                    "uv run python -c \"from rpi.db import ingest; ingest()\"\n"
                    "uv run dbt run --profiles-dir .\n"
                    "```"
                ),
                kind="warn",
            ),
        )

    con = duckdb.connect(str(db_path), read_only=True)
    return con, mo, pl


@app.cell
def _(con, mo):
    try:
        kpis = con.execute("""
            SELECT
                ROUND(SUM(perdida_usd), 0)    AS perdida_total_usd,
                COUNT(DISTINCT planta)         AS plantas,
                COUNT(DISTINCT material)       AS materiales_con_merma,
                ROUND(AVG(tasa_merma_pct), 2)  AS tasa_merma_promedio
            FROM mart_perdidas_usd
        """).pl()
    except Exception:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**Marts no encontrados.**\n\n"
                    "Corre `uv run dbt run --profiles-dir .` para generarlos."
                ),
                kind="warn",
            ),
        )

    return (kpis,)


@app.cell
def _(kpis, mo):
    vista_kpis = mo.hstack([
        mo.stat(label="Pérdida total USD",        value=f"${kpis['perdida_total_usd'][0]:,.0f}"),
        mo.stat(label="Plantas",                  value=str(kpis['plantas'][0])),
        mo.stat(label="Materiales con merma",     value=str(kpis['materiales_con_merma'][0])),
        mo.stat(label="Tasa merma promedio %",    value=f"{kpis['tasa_merma_promedio'][0]:.2f}%"),
    ])
    return (vista_kpis,)


@app.cell
def _(con, mo, pl):
    import base64
    import io

    import matplotlib.pyplot as plt

    _mensual = con.execute("""
        SELECT
            mes::DATE           AS mes,
            SUM(perdida_usd)    AS perdida_usd
        FROM mart_perdidas_usd
        GROUP BY mes
        ORDER BY mes
    """).pl()

    _fig, _ax = plt.subplots(figsize=(11, 3))
    _ax.bar(
        _mensual["mes"].cast(pl.String),
        _mensual["perdida_usd"],
        color="#c0392b",
        width=0.7,
    )
    _ax.set_ylabel("USD")
    _ax.set_title("Pérdidas mensuales en USD")
    _step = max(1, len(_mensual) // 6)
    _ax.set_xticks(range(0, len(_mensual), _step))
    _ax.set_xticklabels(
        _mensual["mes"].cast(pl.String)[::_step].to_list(),
        rotation=45,
        ha="right",
        fontsize=9,
    )
    _ax.spines["top"].set_visible(False)
    _ax.spines["right"].set_visible(False)
    plt.tight_layout()

    _buf = io.BytesIO()
    _fig.savefig(_buf, format="png", dpi=120)
    _buf.seek(0)
    _img_b64 = base64.b64encode(_buf.read()).decode()
    plt.close(_fig)

    grafica_mensual = mo.image(src=f"data:image/png;base64,{_img_b64}")
    return (grafica_mensual,)


@app.cell
def _(con, mo):
    _rutas = con.execute("""
        SELECT
            planta,
            cliente,
            salidas,
            mermas,
            ROUND(tasa_merma_pct, 1) AS tasa_merma_pct,
            ROUND(ciclo_promedio_dias, 1) AS ciclo_promedio_dias,
            perdida_acum_usd
        FROM mart_rutas_rotas
        ORDER BY tasa_merma_pct DESC
        LIMIT 20
    """).pl()

    tabla_rutas = mo.ui.table(_rutas)
    return (tabla_rutas,)


@app.cell
def _(con, mo):
    _rotacion = con.execute("""
        SELECT
            planta,
            mes::DATE       AS mes,
            salidas_totales,
            retornos_totales,
            mermas_totales,
            tasa_merma_pct,
            ciclo_promedio_dias
        FROM mart_rotacion_planta
        ORDER BY mes, planta
    """).pl()

    tabla_rotacion = mo.ui.table(_rotacion)
    return (tabla_rotacion,)


@app.cell
def _(con, mo):
    _ciclo = con.execute("""
        SELECT
            planta,
            ROUND(AVG(dias_ciclo), 1) AS dias_ciclo_promedio,
            COUNT(*)                   AS movimientos
        FROM int_ciclo_retorno
        GROUP BY planta
        ORDER BY dias_ciclo_promedio DESC
    """).pl()

    tabla_ciclo = mo.ui.table(_ciclo)
    return (tabla_ciclo,)


@app.cell
def _(grafica_mensual, mo, tabla_ciclo, tabla_rotacion, tabla_rutas, vista_kpis):
    vista_fase1 = mo.vstack([
        mo.md("## KPIs globales"),
        vista_kpis,
        mo.md("""
        ## Pérdidas mensuales

        Tendencia de pérdidas en USD por mes sobre las 14 plantas.
        """),
        grafica_mensual,
        mo.md("""
        ## Rutas con mayor tasa de merma

        Combinaciones planta-cliente con merma > 5% o ciclo > 45 días,
        ordenadas por porcentaje de contenedores sin retorno.
        """),
        tabla_rutas,
        mo.md("""
        ## Rotación mensual por planta

        Salidas, retornos y mermas absolutas por planta y mes.
        """),
        tabla_rotacion,
        mo.md("""
        ## Ciclo promedio de retorno por planta

        Días promedio entre movimiento 601 (salida a cliente) y 602 (retorno).
        Media de diseño: 25 días.
        """),
        tabla_ciclo,
    ])
    return (vista_fase1,)


@app.cell
def _(con, mo, pl):
    try:
        # HUGEINT de las sumas en dbt se castea a BIGINT para Polars
        tco_planta = con.execute("""
            SELECT
                planta,
                tipo_material,
                ciclos_totales_observados::BIGINT AS ciclos,
                ahorro_por_ciclo_usd,
                ciclos_payback::INTEGER           AS ciclos_payback,
                ahorro_total_vs_desechable_usd    AS ahorro_bruto_usd,
                perdida_acum_usd                  AS costo_merma_usd,
                ahorro_neto_usd
            FROM mart_tco_comparativo
        """).pl()
    except Exception:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**mart_tco_comparativo no encontrado.**\n\n"
                    "Corre `uv run dbt run --profiles-dir .` para generarlo."
                ),
                kind="warn",
            ),
        )

    # Cartón es la línea base del comparativo: ahorro y payback contra sí
    # mismo no significan nada, pero su costo de merma sí es real.
    _es_base = pl.col("tipo_material") == "CARTON"

    tco_tipo = (
        tco_planta.group_by("tipo_material")
        .agg(
            pl.col("ciclos").sum(),
            pl.col("ahorro_por_ciclo_usd").max(),
            pl.col("ciclos_payback").max(),
            pl.col("ahorro_bruto_usd").sum(),
            pl.col("costo_merma_usd").sum(),
            pl.col("ahorro_neto_usd").sum(),
        )
        .with_columns(
            pl.when(_es_base).then(None)
            .otherwise(pl.col("costo_merma_usd") / pl.col("ahorro_bruto_usd") * 100)
            .round(1)
            .alias("merma_sobre_bruto_pct"),
            pl.when(_es_base).then(None).otherwise(pl.col("ahorro_neto_usd"))
            .alias("ahorro_neto_usd"),
            pl.when(_es_base).then(None).otherwise(pl.col("ciclos_payback"))
            .alias("ciclos_payback"),
            pl.when(_es_base).then(None).otherwise(pl.col("ahorro_por_ciclo_usd"))
            .alias("ahorro_por_ciclo_usd"),
        )
        .sort("ahorro_neto_usd", descending=True, nulls_last=True)
    )
    return tco_planta, tco_tipo


@app.cell
def _(mo, pl, tco_planta, tco_tipo):
    _ret = tco_tipo.filter(pl.col("tipo_material") != "CARTON")
    _klt = _ret.filter(pl.col("tipo_material") == "KLT").row(0, named=True)
    _rack = _ret.filter(pl.col("tipo_material") == "RACK").row(0, named=True)

    _por_planta = (
        tco_planta.filter(pl.col("tipo_material") != "CARTON")
        .pivot(on="tipo_material", index="planta", values="ahorro_neto_usd")
        .with_columns(pl.sum_horizontal("KLT", "RACK").round(2).alias("total_usd"))
        .sort("total_usd", descending=True)
    )

    vista_tco = mo.vstack([
        mo.md("## Ahorro neto retornable vs desechable"),
        mo.hstack([
            mo.stat(
                label="Ahorro neto retornable",
                value=f"${_ret['ahorro_neto_usd'].sum() / 1e6:,.1f}M",
                caption="KLT + Rack contra cartón + tarima",
            ),
            mo.stat(label="Ahorro neto Rack", value=f"${_rack['ahorro_neto_usd'] / 1e6:,.1f}M"),
            mo.stat(label="Ahorro neto KLT", value=f"${_klt['ahorro_neto_usd'] / 1e6:,.1f}M"),
        ]),
        mo.hstack([
            mo.stat(label="Payback Rack", value=f"{_rack['ciclos_payback']} ciclos"),
            mo.stat(label="Payback KLT", value=f"{_klt['ciclos_payback']} ciclos"),
        ]),
        mo.md("""
        ## Costo de la merma

        Cuánto del ahorro bruto se come el empaque que sale y no vuelve.
        """),
        mo.hstack([
            mo.stat(
                label="Costo de la merma retornable",
                value=f"${_ret['costo_merma_usd'].sum() / 1e6:,.2f}M",
            ),
            mo.stat(label="Merma / bruto Rack", value=f"{_rack['merma_sobre_bruto_pct']}%"),
            mo.stat(label="Merma / bruto KLT", value=f"{_klt['merma_sobre_bruto_pct']}%"),
        ]),
        mo.md("""
        ## Detalle por tipo

        Cartón es la línea base del comparativo: no tiene ahorro ni payback
        propio. Su costo de merma sí es pérdida real y se muestra.
        """),
        mo.ui.table(tco_tipo, selection=None),
        mo.md("## Ahorro neto por planta"),
        mo.ui.table(_por_planta, selection=None),
    ])
    return (vista_tco,)


@app.cell
def _(mo, vista_fase1, vista_tco):
    mo.ui.tabs({
        "Rotación y pérdidas": vista_fase1,
        "TCO": vista_tco,
    })
    return


if __name__ == "__main__":
    app.run()
