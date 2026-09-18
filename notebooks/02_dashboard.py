import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import duckdb
    import polars as pl
    import marimo as mo

    con = duckdb.connect('data/rpi.duckdb', read_only=True)
    return con, mo


@app.cell
def _(con, mo):
    kpis = con.execute("""
        SELECT
            ROUND(SUM(perdida_usd), 0)    AS perdida_total_usd,
            COUNT(DISTINCT planta)         AS plantas,
            COUNT(DISTINCT material)       AS materiales_con_merma,
            ROUND(AVG(tasa_merma_pct), 2)  AS tasa_merma_promedio
        FROM mart_perdidas_usd
    """).pl()

    mo.stat(
        label="Pérdida total USD",
        value=f"${kpis['perdida_total_usd'][0]:,.0f}",
    )
    return (kpis,)


@app.cell
def _(kpis, mo):
    mo.hstack([
        mo.stat(label="Pérdida total USD",        value=f"${kpis['perdida_total_usd'][0]:,.0f}"),
        mo.stat(label="Plantas",                  value=str(kpis['plantas'][0])),
        mo.stat(label="Materiales con merma",     value=str(kpis['materiales_con_merma'][0])),
        mo.stat(label="Tasa merma promedio %",    value=f"{kpis['tasa_merma_promedio'][0]:.2f}%"),
    ])
    return


@app.cell
def _(con, mo):
    rutas = con.execute("""
        SELECT
            planta,
            cliente,
            salidas,
            mermas,
            ROUND(tasa_merma_pct, 1) AS tasa_merma_pct
        FROM mart_rutas_rotas
        ORDER BY tasa_merma_pct DESC
        LIMIT 20
    """).pl()

    mo.ui.table(rutas)
    return


@app.cell
def _(con, mo):
    rotacion = con.execute("""
        SELECT *
        FROM mart_rotacion_planta
        ORDER BY mes, planta
    """).pl()

    mo.ui.table(rotacion)
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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Returnable Packaging Intelligence — Dashboard de Pérdidas y Rotación

    Flota multi-planta · 18 meses · 14 plantas · datos MB51 sintéticos
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Rutas con mayor tasa de merma

    Combinaciones planta-cliente ordenadas por porcentaje de contenedores sin retorno.
    Una tasa > 20% indica ruta candidata a auditoría de flota.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Rotación mensual por planta

    Salidas, retornos y mermas absolutas por planta y mes.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Ciclo promedio de retorno por planta

    Días promedio entre movimiento 601 (salida a cliente) y 602 (retorno).
    Media de diseño: 25 días. Desviaciones sostenidas indican flota fantasma acumulándose.
    """)
    return


if __name__ == "__main__":
    app.run()
