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
    import base64
    import io
    from pathlib import Path

    import duckdb
    import marimo as mo
    import matplotlib.pyplot as plt
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
                    "uv run dbt build --profiles-dir .\n"
                    "```"
                ),
                kind="warn",
            ),
        )

    con = duckdb.connect(str(db_path), read_only=True)

    def a_imagen(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        return mo.image(src=f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}")

    return a_imagen, con, mo, pl, plt


@app.cell
def _(con, mo):
    # Las sumas de dbt salen como HUGEINT o DECIMAL(38); se castean para Polars.
    try:
        kpis = con.execute("""
            WITH perdida AS (
                SELECT
                    SUM(perdida_usd)                    AS perdida_usd,
                    SUM(unidades_perdidas)::BIGINT      AS contenedores
                FROM mart_perdidas_usd
            ),
            tasa AS (
                SELECT SUM(faltantes) * 100.0 / SUM(salidas_conciliadas) AS tasa_flota_pct
                FROM mart_tco_comparativo
            ),
            rutas AS (
                SELECT
                    (SELECT COUNT(*) FROM mart_rutas_rotas)                     AS rotas,
                    (SELECT COUNT(DISTINCT (planta, cliente))
                     FROM mart_exceso_saldo_ruta)                               AS total
            )
            SELECT * FROM perdida, tasa, rutas
        """).pl().row(0, named=True)
    except Exception:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**Marts no encontrados.**\n\n"
                    "Corre `uv run dbt build --profiles-dir .` para generarlos."
                ),
                kind="warn",
            ),
        )
    return (kpis,)


@app.cell
def _(kpis, mo):
    vista_kpis = mo.hstack([
        mo.stat(
            label="Pérdida reconocida",
            value=f"${kpis['perdida_usd']:,.0f}",
            caption="702 en conciliación",
        ),
        mo.stat(label="Contenedores perdidos", value=f"{kpis['contenedores']:,}"),
        mo.stat(
            label="Tasa de merma de flota",
            value=f"{kpis['tasa_flota_pct']:.3f}%",
            caption="por viaje, ventana conciliada",
        ),
        mo.stat(label="Rutas rotas", value=f"{kpis['rotas']} de {kpis['total']}"),
    ])
    return (vista_kpis,)


@app.cell
def _(a_imagen, con, plt):
    _mensual = (
        con.execute("""
            SELECT mes, tipo_material, SUM(perdida_usd) AS perdida_usd
            FROM mart_perdidas_usd
            GROUP BY mes, tipo_material
        """).pl()
        .pivot(on="tipo_material", index="mes", values="perdida_usd")
        .fill_null(0)
        .sort("mes")
    )
    _etiquetas = _mensual["mes"].dt.strftime("%Y-%m").to_list()

    _fig, _ax = plt.subplots(figsize=(9, 3))
    _ax.bar(_etiquetas, _mensual["KLT"] / 1e3, label="KLT", color="#2c7fb8", width=0.6)
    _ax.bar(
        _etiquetas, _mensual["RACK"] / 1e3, bottom=_mensual["KLT"] / 1e3,
        label="Rack", color="#c0392b", width=0.6,
    )
    _ax.set_ylabel("miles de USD")
    _ax.set_title("Pérdida reconocida por mes de conciliación")
    _ax.legend(frameon=False)
    _ax.spines[["top", "right"]].set_visible(False)
    _fig.tight_layout()

    grafica_perdidas = a_imagen(_fig)
    return (grafica_perdidas,)


@app.cell
def _(con, mo):
    _rutas = con.execute("""
        SELECT
            planta,
            cliente,
            contenedores_salida::BIGINT     AS contenedores_salida,
            salidas_conciliadas::BIGINT     AS salidas_conciliadas,
            faltantes::BIGINT               AS faltantes,
            tasa_merma_pct,
            ciclo_promedio_dias,
            perdida_acum_usd
        FROM mart_rutas_rotas
        ORDER BY perdida_acum_usd DESC
    """).pl()

    tabla_rutas = mo.ui.table(_rutas, selection=None)
    return (tabla_rutas,)


@app.cell
def _(con):
    # Solo filas con ventana válida: antes del horizonte de la curva el
    # esperado está incompleto y el exceso sale sesgado.
    exceso = con.execute("""
        SELECT
            e.planta,
            e.cliente,
            e.mes,
            e.saldo_fin_mes,
            e.saldo_esperado,
            e.exceso_saldo,
            e.exceso_pct,
            e.exceso_pct_ciclo,
            r.planta IS NOT NULL            AS ruta_rota
        FROM mart_exceso_saldo_ruta e
        LEFT JOIN mart_rutas_rotas r
            ON r.planta = e.planta AND r.cliente = e.cliente
        WHERE e.alerta_valida
    """).pl()
    return (exceso,)


@app.cell
def _(a_imagen, exceso, pl, plt):
    _serie = (
        exceso.group_by("mes", "ruta_rota")
        .agg(pl.col("exceso_pct_ciclo").median().alias("mediana"))
        .sort("mes")
    )

    _fig, _ax = plt.subplots(figsize=(9, 3))
    for _rota, _color, _nombre in [
        (True, "#c0392b", "Rutas rotas"),
        (False, "#7f8c8d", "Resto de la flota"),
    ]:
        _s = _serie.filter(pl.col("ruta_rota") == _rota)
        _ax.plot(
            _s["mes"].dt.strftime("%Y-%m").to_list(), _s["mediana"],
            marker="o", color=_color, label=_nombre,
        )
    _ax.set_ylabel("% sobre esperado")
    _ax.set_title("Exceso de saldo en cliente, últimos 3 cierres (mediana por grupo)")
    _ax.tick_params(axis="x", rotation=45, labelsize=8)
    _ax.legend(frameon=False)
    _ax.spines[["top", "right"]].set_visible(False)
    _fig.tight_layout()

    grafica_exceso = a_imagen(_fig)
    return (grafica_exceso,)


@app.cell
def _(exceso, mo, pl):
    _ultimo = exceso["mes"].max()
    _tabla = (
        exceso.filter(pl.col("mes") == _ultimo)
        .select(
            "planta", "cliente", "saldo_fin_mes", "saldo_esperado",
            "exceso_pct", "exceso_pct_ciclo", "ruta_rota",
        )
        .sort("exceso_pct_ciclo", descending=True)
        .head(20)
    )

    tabla_exceso = mo.vstack([
        mo.md(f"Cierre de {_ultimo:%Y-%m}. Top 20 rutas por exceso de los últimos 3 cierres."),
        mo.ui.table(_tabla, selection=None),
    ])
    return (tabla_exceso,)


@app.cell
def _(con, mo):
    # Solo cohortes completas: en las recientes aún no regresan los ciclos
    # largos y el promedio sale bajo.
    _ciclo = con.execute("""
        SELECT
            planta,
            ROUND(SUM(ciclo_promedio_dias * contenedores_recogidos)
                / SUM(contenedores_recogidos), 1)   AS ciclo_promedio_dias,
            ROUND(AVG(ciclo_p50_dias), 1)           AS ciclo_p50_dias,
            ROUND(AVG(ciclo_p90_dias), 1)           AS ciclo_p90_dias,
            SUM(contenedores_recogidos)::BIGINT     AS contenedores_recogidos
        FROM mart_rotacion_planta
        WHERE cohorte_completa
        GROUP BY planta
        ORDER BY ciclo_promedio_dias DESC
    """).pl()

    _flota = con.execute("""
        SELECT
            SUM(ciclo_promedio_dias * contenedores_recogidos)
                / SUM(contenedores_recogidos)       AS promedio,
            AVG(ciclo_p50_dias)                     AS p50,
            AVG(ciclo_p90_dias)                     AS p90
        FROM mart_rotacion_planta
        WHERE cohorte_completa
    """).pl().row(0, named=True)

    vista_ciclo = mo.vstack([
        mo.hstack([
            mo.stat(label="Ciclo promedio", value=f"{_flota['promedio']:.1f} días"),
            mo.stat(label="p50", value=f"{_flota['p50']:.0f} días"),
            mo.stat(label="p90", value=f"{_flota['p90']:.1f} días"),
        ]),
        mo.ui.table(_ciclo, selection=None),
    ])
    return (vista_ciclo,)


@app.cell
def _(
    grafica_exceso,
    grafica_perdidas,
    mo,
    tabla_exceso,
    tabla_rutas,
    vista_ciclo,
    vista_kpis,
):
    vista_fase1 = mo.vstack([
        mo.md("## KPIs globales"),
        vista_kpis,
        mo.md("""
        ## Pérdida por mes de conciliación

        El faltante se reconoce con 702 en la conciliación trimestral, sobre
        saldo con al menos 120 días. La pérdida cae en el mes de conciliación,
        no en el mes en que el contenedor dejó de volver.
        """),
        grafica_perdidas,
        mo.md("""
        ## Rutas rotas

        Rutas planta × cliente con merma conciliada mayor a 1.0 % por viaje o
        ciclo promedio mayor a 45 días. Ordenadas por pérdida acumulada.
        """),
        tabla_rutas,
        mo.md("""
        ## Alerta temprana: exceso de saldo en cliente

        Saldo real en stock especial V contra el saldo esperado por la curva
        de supervivencia del ciclo. El exceso es merma que la conciliación
        todavía no reconoce.

        Un cierre aislado no sirve para comparar: toda la flota sube y baja
        entre conciliaciones. El indicador suma los últimos 3 cierres. Es
        alerta, no clasificador; la ruta rota se define por tasa conciliada.
        """),
        grafica_exceso,
        tabla_exceso,
        mo.md("""
        ## Ciclo de retorno por planta

        Días entre 621 y 622 con antigüedad FIFO, ponderados por contenedor.
        Solo cohortes de salida completas.
        """),
        vista_ciclo,
    ])
    return (vista_fase1,)


@app.cell
def _(con, mo):
    try:
        tco_planta = con.execute("""
            SELECT
                planta,
                tipo_material,
                viajes::BIGINT                  AS viajes,
                salidas_conciliadas::BIGINT     AS salidas_conciliadas,
                faltantes::BIGINT               AS faltantes,
                vida_util_ciclos,
                vida_esperada_ciclos,
                costo_unitario_usd,
                desechable_equiv_usd,
                costo_retornable_por_ciclo_usd,
                ciclos_payback,
                ahorro_neto_usd
            FROM mart_tco_comparativo
        """).pl()
    except Exception:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**mart_tco_comparativo no encontrado.**\n\n"
                    "Corre `uv run dbt build --profiles-dir .` para generarlo."
                ),
                kind="warn",
            ),
        )
    return (tco_planta,)


@app.cell
def _(pl, tco_planta):
    # Promedios ponderados por viaje: sumar ahorros y dividir, no promediar tasas.
    _w = pl.col("viajes")
    tco_tipo = (
        tco_planta.group_by("tipo_material")
        .agg(
            _w.sum().alias("viajes"),
            (pl.col("faltantes").sum() * 100 / pl.col("salidas_conciliadas").sum())
            .round(3).alias("tasa_merma_pct"),
            pl.col("vida_util_ciclos").first(),
            ((pl.col("vida_esperada_ciclos") * _w).sum() / _w.sum())
            .round(1).alias("vida_esperada_ciclos"),
            ((pl.col("costo_retornable_por_ciclo_usd") * _w).sum() / _w.sum())
            .round(2).alias("costo_retornable_por_ciclo_usd"),
            pl.col("costo_retornable_por_ciclo_usd").max().round(2)
            .alias("costo_por_ciclo_peor_planta_usd"),
            pl.col("desechable_equiv_usd").first(),
            (pl.col("ahorro_neto_usd").sum() / _w.sum())
            .round(2).alias("ahorro_por_viaje_usd"),
            pl.col("ciclos_payback").max(),
            pl.col("ahorro_neto_usd").sum(),
        )
        .sort("ahorro_neto_usd", descending=True)
    )
    return (tco_tipo,)


@app.cell
def _(mo, pl, tco_planta, tco_tipo):
    _klt = tco_tipo.filter(pl.col("tipo_material") == "KLT").row(0, named=True)
    _rack = tco_tipo.filter(pl.col("tipo_material") == "RACK").row(0, named=True)

    _por_planta = (
        tco_planta.pivot(on="tipo_material", index="planta", values="ahorro_neto_usd")
        .with_columns(pl.sum_horizontal("KLT", "RACK").round(2).alias("total_usd"))
        .sort("total_usd", descending=True)
    )

    vista_tco = mo.vstack([
        mo.md("""
        ## Economía por viaje

        Cada viaje de retornable reemplaza un desechable equivalente. El costo
        por ciclo del retornable es compra entre vida esperada más
        mantenimiento; la merma entra por la vida esperada, no se resta aparte.
        """),
        mo.hstack([
            mo.stat(
                label="Ahorro por viaje KLT",
                value=f"${_klt['ahorro_por_viaje_usd']:,.2f}",
                caption=f"desechable ${_klt['desechable_equiv_usd']:.2f}",
            ),
            mo.stat(
                label="Ahorro por viaje Rack",
                value=f"${_rack['ahorro_por_viaje_usd']:,.2f}",
                caption=f"desechable ${_rack['desechable_equiv_usd']:.2f}",
            ),
            mo.stat(label="Payback KLT", value=f"{_klt['ciclos_payback']} ciclos"),
            mo.stat(label="Payback Rack", value=f"{_rack['ciclos_payback']} ciclos"),
        ]),
        mo.ui.table(tco_tipo, selection=None),
        mo.md(f"""
        El Rack deja de convenir en toda la flota con un desechable por debajo
        de **\\${_rack['costo_retornable_por_ciclo_usd']:.2f}** por embarque, y en
        la planta con más merma por debajo de
        **\\${_rack['costo_por_ciclo_peor_planta_usd']:.2f}**. El supuesto
        vigente es \\${_rack['desechable_equiv_usd']:.0f} (rango \\$34–66).
        """),
        mo.md("""
        ## Ahorro neto

        Ahorro por viaje multiplicado por los viajes de 18 meses. El total
        depende del volumen; la economía por viaje es lo que se compara.
        """),
        mo.hstack([
            mo.stat(
                label="Ahorro neto retornable",
                value=f"${tco_tipo['ahorro_neto_usd'].sum() / 1e6:,.1f}M",
                caption="KLT + Rack contra desechable equivalente",
            ),
            mo.stat(label="Ahorro neto Rack", value=f"${_rack['ahorro_neto_usd'] / 1e6:,.1f}M"),
            mo.stat(label="Ahorro neto KLT", value=f"${_klt['ahorro_neto_usd'] / 1e6:,.1f}M"),
        ]),
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
