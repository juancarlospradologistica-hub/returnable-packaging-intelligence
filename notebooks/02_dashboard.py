import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Returnable Packaging Intelligence — Dashboard de Pérdidas y Rotación

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


@app.cell(hide_code=True)
def _(mo):
    mo.md("## KPIs globales")
    return


@app.cell
def _(kpis, mo):
    mo.hstack([
        mo.stat(label="Pérdida total USD",        value=f"${kpis['perdida_total_usd'][0]:,.0f}"),
        mo.stat(label="Plantas",                  value=str(kpis['plantas'][0])),
        mo.stat(label="Materiales con merma",     value=str(kpis['materiales_con_merma'][0])),
        mo.stat(label="Tasa merma promedio %",    value=f"{kpis['tasa_merma_promedio'][0]:.2f}%"),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Pérdidas mensuales

    Tendencia de pérdidas en USD por mes sobre las 14 plantas.
    """)
    return


@app.cell
def _(con, mo, pl):
    import base64
    import io

    import matplotlib.pyplot as plt

    mensual = con.execute("""
        SELECT
            mes::DATE           AS mes,
            SUM(perdida_usd)    AS perdida_usd
        FROM mart_perdidas_usd
        GROUP BY mes
        ORDER BY mes
    """).pl()

    fig, ax = plt.subplots(figsize=(11, 3))
    ax.bar(
        mensual["mes"].cast(pl.String),
        mensual["perdida_usd"],
        color="#c0392b",
        width=0.7,
    )
    ax.set_ylabel("USD")
    ax.set_title("Pérdidas mensuales en USD")
    step = max(1, len(mensual) // 6)
    ax.set_xticks(range(0, len(mensual), step))
    ax.set_xticklabels(
        mensual["mes"].cast(pl.String)[::step].to_list(),
        rotation=45,
        ha="right",
        fontsize=9,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)

    mo.image(src=f"data:image/png;base64,{img_b64}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Rutas con mayor tasa de merma

    Combinaciones planta-cliente con merma > 5% o ciclo > 45 días,
    ordenadas por porcentaje de contenedores sin retorno.
    """)
    return


@app.cell
def _(con, mo):
    rutas = con.execute("""
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

    mo.ui.table(rutas)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Rotación mensual por planta

    Salidas, retornos y mermas absolutas por planta y mes.
    """)
    return


@app.cell
def _(con, mo):
    rotacion = con.execute("""
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

    mo.ui.table(rotacion)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Ciclo promedio de retorno por planta

    Días promedio entre movimiento 601 (salida a cliente) y 602 (retorno).
    Media de diseño: 25 días.
    """)
    return


@app.cell
def _(con, mo):
    ciclo = con.execute("""
        SELECT
            planta,
            ROUND(AVG(dias_ciclo), 1) AS dias_ciclo_promedio,
            COUNT(*)                   AS movimientos
        FROM int_ciclo_retorno
        GROUP BY planta
        ORDER BY dias_ciclo_promedio DESC
    """).pl()

    mo.ui.table(ciclo)
    return


if __name__ == "__main__":
    app.run()