import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(con, mo):
    # Plantas, meses y fecha de extracción salen de la base: el reducido, la
    # ventana recortada o un extracto real no tienen las del completo. Un Budat
    # posterior a la extracción es un defecto y no cuenta (ADR-034).
    _plantas, _meses, _corte = con.execute(
        """
        SELECT COUNT(DISTINCT m.planta), COUNT(DISTINCT date_trunc('month', m.fecha_contab)),
               ANY_VALUE(c.corte)
        FROM stg_mb51 m, int_calendario_necesidad c
        WHERE m.fecha_contab <= c.corte
        """
    ).fetchone()
    mo.md(
        f"""
    # Returnable Packaging Intelligence — Dashboard

    Flota multi-planta · {_meses} meses · {_plantas} plantas · extracto al {_corte:%d.%m.%Y}
    """
    )
    return


@app.cell
def _():
    import base64
    import io
    import os
    from pathlib import Path

    import duckdb
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import polars as pl

    from rpi import red as dibujos
    from rpi.publicacion import bloqueadas, cifras

    # RPI_DB abre otra base, por ejemplo la del dataset con defectos (ADR-030).
    db_path = Path(os.environ.get("RPI_DB", "data/rpi.duckdb"))

    if not db_path.exists():
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**Base de datos no encontrada.**\n\n"
                    "Corre el pipeline completo antes de abrir el dashboard:\n\n"
                    "```bash\n"
                    "uv run python -m rpi\n"
                    'uv run python -c "from rpi.db import ingest; ingest()"\n'
                    "uv run dbt build --profiles-dir .\n"
                    "```"
                ),
                kind="warn",
            ),
        )

    con = duckdb.connect(str(db_path), read_only=True)

    try:
        bloqueos = bloqueadas(con)
    except duckdb.Error:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**mart_calidad_datos no encontrado.**\n\n"
                    "Corre `uv run dbt seed --profiles-dir . --full-refresh` y "
                    "`uv run dbt build --profiles-dir .`."
                ),
                kind="warn",
            ),
        )

    def publica(vista, cifras):
        """
        La vista, o un aviso con las reglas que bloquean si alguna de sus
        cifras tiene una (ADR-031, punto 8). Nada de la sección se muestra.
        """
        _hay = {c: bloqueos[c] for c in cifras if c in bloqueos}
        if not _hay:
            return vista
        _lineas = "\n".join(f"- **{c}**: {', '.join(r)}" for c, r in _hay.items())
        return mo.callout(
            mo.md(f"**No se publica: hay reglas de calidad que bloquean.**\n\n{_lineas}"),
            kind="danger",
        )

    def a_imagen(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        return mo.image(src=f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}")

    # Cuántas cifras publica el proyecto: salen del seed, no de un número fijo.
    total_cifras = len(cifras(con))
    return a_imagen, bloqueos, con, dibujos, mo, np, pl, plt, publica, total_cifras


@app.cell
def _(con, mo):
    # Los marts ya entregan BIGINT (ADR-013), pero SUM() y COUNT_IF() vuelven a
    # dar HUGEINT: al agregar aquí se castea.
    try:
        kpis = (
            con.execute("""
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
                    COUNT_IF(ruta_rota)::BIGINT         AS rotas,
                    COUNT(*)                            AS total
                FROM mart_rutas
            )
            SELECT * FROM perdida, tasa, rutas
        """)
            .pl()
            .row(0, named=True)
        )
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
    vista_kpis = mo.hstack(
        [
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
        ]
    )
    return (vista_kpis,)


@app.cell
def _(a_imagen, con, plt):
    _mensual = (
        con.execute("""
            SELECT mes, tipo_material, SUM(perdida_usd) AS perdida_usd
            FROM mart_perdidas_usd
            GROUP BY mes, tipo_material
        """)
        .pl()
        .pivot(on="tipo_material", index="mes", values="perdida_usd")
        .fill_null(0)
        .sort("mes")
    )
    _etiquetas = _mensual["mes"].dt.strftime("%Y-%m").to_list()

    _fig, _ax = plt.subplots(figsize=(9, 3))
    _ax.bar(_etiquetas, _mensual["KLT"] / 1e3, label="KLT", color="#2c7fb8", width=0.6)
    _ax.bar(
        _etiquetas,
        _mensual["RACK"] / 1e3,
        bottom=_mensual["KLT"] / 1e3,
        label="Rack",
        color="#c0392b",
        width=0.6,
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
            contenedores_salida,
            salidas_conciliadas,
            faltantes,
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
            r.ruta_rota
        FROM mart_exceso_saldo_ruta e
        INNER JOIN mart_rutas r
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
            _s["mes"].dt.strftime("%Y-%m").to_list(),
            _s["mediana"],
            marker="o",
            color=_color,
            label=_nombre,
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
        exceso.filter(pl.col("mes") == pl.col("mes").max())
        .select(
            "planta",
            "cliente",
            "saldo_fin_mes",
            "saldo_esperado",
            "exceso_pct",
            "exceso_pct_ciclo",
            "ruta_rota",
        )
        .sort("exceso_pct_ciclo", descending=True)
        .head(20)
    )

    # Sin cierres válidos (un extracto corto o con defectos) no hay tabla que
    # mostrar; la sección no debe tumbar la pestaña completa.
    tabla_exceso = (
        mo.md("Sin cierres con alerta válida.")
        if _ultimo is None
        else mo.vstack(
            [
                mo.md(
                    f"Cierre de {_ultimo:%Y-%m}. Top 20 rutas por exceso de los últimos 3 cierres."
                ),
                mo.ui.table(_tabla, selection=None),
            ]
        )
    )
    return (tabla_exceso,)


@app.cell
def _(con, mo, pl):
    # El mart ya filtra cohortes completas y calcula los percentiles sobre la
    # distribución completa (ADR-014). Promediar p90 mensuales no da el p90.
    _ciclo = con.execute("""
        SELECT
            nivel,
            planta,
            ciclo_promedio_dias,
            ciclo_p50_dias,
            ciclo_p90_dias,
            contenedores_recogidos
        FROM mart_ciclo_cohortes
    """).pl()

    # Sin cohortes completas el mart sale vacío: D06 en el techo de su rango
    # lo deja así (ADR-031).
    _flota = _ciclo.filter(pl.col("nivel") == "flota").rows(named=True)

    # El promedio casi no se mueve entre plantas; la diferencia está en la cola.
    _plantas = (
        _ciclo.filter(pl.col("nivel") == "planta")
        .drop("nivel")
        .sort(["ciclo_p90_dias", "ciclo_promedio_dias"], descending=True)
    )

    if not _flota:
        vista_ciclo = mo.callout(mo.md("Sin cohortes completas: no hay ciclo que medir."))
    else:
        _f = _flota[0]
        vista_ciclo = mo.vstack(
            [
                mo.hstack(
                    [
                        mo.stat(
                            label="Ciclo promedio", value=f"{_f['ciclo_promedio_dias']:.1f} días"
                        ),
                        mo.stat(label="p50", value=f"{_f['ciclo_p50_dias']} días"),
                        mo.stat(label="p90", value=f"{_f['ciclo_p90_dias']} días"),
                        mo.stat(
                            label="Contenedores recogidos",
                            value=f"{_f['contenedores_recogidos']:,}",
                            caption="cohortes completas",
                        ),
                    ]
                ),
                mo.ui.table(_plantas, selection=None),
            ]
        )
    return (vista_ciclo,)


@app.cell
def _(
    grafica_exceso,
    grafica_perdidas,
    mo,
    publica,
    tabla_exceso,
    tabla_rutas,
    vista_ciclo,
    vista_kpis,
):
    vista_fase1 = mo.vstack(
        [
            mo.md("## KPIs globales"),
            publica(vista_kpis, ["perdida"]),
            mo.md("""
        ## Pérdida por mes de conciliación

        El faltante se reconoce con 702 en la conciliación trimestral, sobre
        saldo con al menos 120 días. La pérdida cae en el mes de conciliación,
        no en el mes en que el contenedor dejó de volver.
        """),
            publica(grafica_perdidas, ["perdida", "serie_mensual"]),
            mo.md("""
        ## Rutas rotas

        Rutas planta × cliente con merma conciliada mayor a 1.0 % por viaje o
        ciclo promedio mayor a 45 días. Ordenadas por pérdida acumulada.
        """),
            publica(tabla_rutas, ["perdida"]),
            mo.md("""
        ## Alerta temprana: exceso de saldo en cliente

        Saldo real en stock especial V contra el saldo esperado por la curva
        de supervivencia del ciclo. El exceso es merma que la conciliación
        todavía no reconoce.

        Un cierre aislado no sirve para comparar: en el mes de conciliación
        el 702 borra el exceso acumulado y la ruta rota se ve sana. El
        indicador suma los últimos 3 cierres. Es alerta, no clasificador;
        la ruta rota se define por tasa conciliada.
        """),
            publica(mo.vstack([grafica_exceso, tabla_exceso]), ["saldo_cliente"]),
            mo.md("""
        ## Ciclo de retorno por planta

        Días entre 621 y 622 con antigüedad FIFO, ponderados por contenedor.
        Solo cohortes de salida completas. Plantas ordenadas por p90: el
        promedio casi no cambia entre plantas, la cola sí.
        """),
            publica(vista_ciclo, ["ciclo"]),
        ]
    )
    return (vista_fase1,)


@app.cell
def _(con, mo):
    try:
        tco_planta = con.execute("""
            SELECT
                planta,
                tipo_material,
                viajes,
                salidas_conciliadas,
                faltantes,
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
            .round(3)
            .alias("tasa_merma_pct"),
            pl.col("vida_util_ciclos").first(),
            ((pl.col("vida_esperada_ciclos") * _w).sum() / _w.sum())
            .round(1)
            .alias("vida_esperada_ciclos"),
            ((pl.col("costo_retornable_por_ciclo_usd") * _w).sum() / _w.sum())
            .round(2)
            .alias("costo_retornable_por_ciclo_usd"),
            pl.col("costo_retornable_por_ciclo_usd")
            .max()
            .round(2)
            .alias("costo_por_ciclo_peor_planta_usd"),
            pl.col("desechable_equiv_usd").first(),
            (pl.col("ahorro_neto_usd").sum() / _w.sum()).round(2).alias("ahorro_por_viaje_usd"),
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

    vista_tco = mo.vstack(
        [
            mo.md("""
        ## Economía por viaje

        Cada viaje de retornable reemplaza un desechable equivalente. El costo
        por ciclo del retornable es compra entre vida esperada más
        mantenimiento; la merma entra por la vida esperada, no se resta aparte.
        """),
            mo.hstack(
                [
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
                ]
            ),
            mo.ui.table(tco_tipo, selection=None),
            mo.md(f"""
        El Rack deja de convenir en toda la flota con un desechable por debajo
        de **\\${_rack["costo_retornable_por_ciclo_usd"]:.2f}** por embarque, y en
        la planta con más merma por debajo de
        **\\${_rack["costo_por_ciclo_peor_planta_usd"]:.2f}**. El supuesto
        vigente es \\${_rack["desechable_equiv_usd"]:.0f} (rango \\$34–66).
        """),
            mo.md("""
        ## Ahorro neto

        Ahorro por viaje multiplicado por los viajes de 18 meses. El total
        depende del volumen; la economía por viaje es lo que se compara.
        """),
            mo.hstack(
                [
                    mo.stat(
                        label="Ahorro neto retornable",
                        value=f"${tco_tipo['ahorro_neto_usd'].sum() / 1e6:,.1f}M",
                        caption="KLT + Rack contra desechable equivalente",
                    ),
                    mo.stat(
                        label="Ahorro neto Rack", value=f"${_rack['ahorro_neto_usd'] / 1e6:,.1f}M"
                    ),
                    mo.stat(
                        label="Ahorro neto KLT", value=f"${_klt['ahorro_neto_usd'] / 1e6:,.1f}M"
                    ),
                ]
            ),
            mo.md("## Ahorro neto por planta"),
            mo.ui.table(_por_planta, selection=None),
        ]
    )
    return (vista_tco,)


@app.cell
def _(con, mo, pl):
    try:
        sens = (
            con.execute("SELECT * FROM mart_sensibilidad_brecha")
            .pl()
            .with_columns(pl.col(pl.Decimal).cast(pl.Float64))
        )
        flota_semanal = con.execute("""
            SELECT f.tipo_material, f.semana,
                   SUM(f.flota_proyectada)          AS flota,
                   SUM(n.necesidad)::BIGINT         AS necesidad,
                   SUM(GREATEST(n.necesidad - f.flota_proyectada, 0)) AS deficit
            FROM int_flota_proyectada f
            JOIN mart_necesidad_flota n USING (planta, material, semana)
            GROUP BY ALL
            ORDER BY 1, 2
        """).pl()
        red = con.execute("""
            SELECT planta_origen, planta_destino, tipo_material, etapa,
                   materiales, contenedores, usd_flete
            FROM mart_red_prestamos
            ORDER BY contenedores DESC
        """).pl()
    except Exception:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**Marts de Fase 3 no encontrados.**\n\n"
                    "Corre `uv run dbt seed --profiles-dir . --full-refresh` y "
                    "`uv run dbt build --profiles-dir .`."
                ),
                kind="warn",
            ),
        )
    # Sin plan de producción los marts de necesidad salen vacíos (ADR-037).
    sin_plan = sens.is_empty()
    escenario = mo.ui.dropdown(
        options=sorted(sens["escenario"].unique().to_list()) or ["base"],
        value="base",
        label="Escenario",
    )
    return escenario, flota_semanal, red, sens, sin_plan


@app.cell
def _(a_imagen, flota_semanal, pl, plt, sin_plan):
    def _grafica():
        _fig, _axes = plt.subplots(1, 2, figsize=(10, 3.2))
        for _ax, _k, _nombre, _color in zip(
            _axes, ["KLT", "RACK"], ["KLT", "Rack"], ["#2c7fb8", "#c0392b"], strict=True
        ):
            _s = flota_semanal.filter(pl.col("tipo_material") == _k)
            _sem = list(range(1, _s.height + 1))
            _ax.plot(
                _sem, _s["flota"] / 1e3, color="#7f8c8d", marker="o", ms=3, label="flota proyectada"
            )
            _ax.plot(_sem, _s["necesidad"] / 1e3, color=_color, marker="o", ms=3, label="necesidad")
            _ax.set_title(f"{_nombre}: flota y necesidad, base")
            _ax.set_xlabel("semana del plan")
            _ax.set_ylabel("miles de contenedores")
            _ax.spines[["top", "right"]].set_visible(False)
        _axes[0].legend(frameon=False, fontsize=8)
        _fig.tight_layout()
        return a_imagen(_fig)

    grafica_necesidad = None if sin_plan else _grafica()
    return (grafica_necesidad,)


@app.cell
def _(mo, sin_plan):
    aviso_sin_plan = mo.callout(
        mo.md(
            "**Sin plan de producción.** El extracto no trae partes, instrucción "
            "de empaque ni plan, así que la necesidad de flota, la brecha y la "
            "red de préstamos no se calculan. Rotación, pérdidas, TCO, flota "
            "semanal y calidad de datos no dependen del plan."
        ),
        kind="info",
    )
    return (aviso_sin_plan,)


@app.cell
def _(escenario, grafica_necesidad, mo, pl, red, sens, sin_plan):
    def _vista():
        _sel = sens.filter(pl.col("escenario") == escenario.value)
        _base = sens.filter(pl.col("escenario") == "base")
        _t = {r["tipo_material"]: r for r in _sel.iter_rows(named=True)}
        _brecha = _sel["usd_brecha"].sum()
        _ocioso = _sel["usd_capital_ocioso"].sum()
        _d_brecha = _brecha - _base["usd_brecha"].sum()
        _d_ocioso = _ocioso - _base["usd_capital_ocioso"].sum()

        _tabla_escenario = _sel.select(
            "tipo_material",
            "z_servicio",
            pl.col("objetivo_quiebre").mul(100).round(2).alias("objetivo_quiebre_pct"),
            "ajuste_ciclo_dias",
            "necesidad_semana_1",
            "materiales_deficit",
            "deficit",
            "compra",
            "viajes_desechable",
            "usd_flete",
            "usd_compra",
            "usd_desechable",
            "usd_brecha",
            "usd_capital_ocioso",
        )
        _todos = (
            sens.group_by("escenario")
            .agg(
                pl.col("usd_brecha").sum().round(0).alias("usd_brecha"),
                pl.col("usd_capital_ocioso").sum().round(0).alias("usd_capital_ocioso"),
                pl.col("compra").sum().alias("compra"),
            )
            .sort("usd_brecha")
        )
        _por_etapa = (
            red.group_by("tipo_material", "etapa")
            .agg(
                pl.len().alias("flujos"),
                pl.col("contenedores").sum().round(0),
                pl.col("usd_flete").sum().round(2),
            )
            .sort("tipo_material", "etapa")
        )

        return mo.vstack(
            [
                mo.md("""
            ## Necesidad contra flota

            Necesidad = d_plan × ciclo + z × σ del stock en uso, por planta,
            material y semana del plan de 12 semanas. La flota proyectada es la
            del corte menos la merma pendiente de conciliar y lo que se pierde
            por viaje del plan. En total sobra flota; material por material, no.
            """),
                grafica_necesidad,
                mo.md("""
            ## Brecha por escenario

            Préstamo entre plantas con el mismo material (primero dentro del
            país), compra al corte de lo que falta y desechable mientras la
            compra llega. Lo que sobra después de prestar es capital ocioso.
            Cada escenario corre por la misma lógica que el base; la tabla
            completa está en `mart_sensibilidad_brecha`.
            """),
                escenario,
                mo.hstack(
                    [
                        mo.stat(
                            label="Costo de la brecha",
                            value=f"${_brecha:,.0f}",
                            caption=f"{_d_brecha:+,.0f} contra base",
                        ),
                        mo.stat(
                            label="Capital ocioso",
                            value=f"${_ocioso / 1e6:,.2f}M",
                            caption=f"{_d_ocioso / 1e6:+,.2f}M contra base",
                        ),
                        mo.stat(
                            label="z KLT / Rack",
                            value=f"{_t['KLT']['z_servicio']:.2f} / {_t['RACK']['z_servicio']:.2f}",
                        ),
                        mo.stat(
                            label="Compra KLT / Rack",
                            value=f"{_t['KLT']['compra']:,} / {_t['RACK']['compra']:,}",
                        ),
                    ]
                ),
                mo.ui.table(_tabla_escenario, selection=None),
                mo.md("## Todos los escenarios, KLT + Rack"),
                mo.ui.table(_todos, selection=None),
                mo.md("""
            ## Red de préstamos, escenario base

            Flujos entre plantas: cada receptor recibe de cada donante en
            proporción a lo que el donante presta. Cruzar frontera cuesta 15%
            del costo unitario contra 5% dentro del país.
            """),
                mo.ui.table(_por_etapa, selection=None),
                mo.ui.table(red, selection=None, page_size=10),
            ]
        )

    vista_necesidad = None if sin_plan else _vista()
    return (vista_necesidad,)


@app.cell
def _(con, mo, pl):
    # Tablero del extracto abierto (ADR-031, punto 9): las 23 reglas, con o sin
    # violaciones, y la tasa por planta sobre el universo de cada regla.
    calidad_reglas = (
        con.execute("""
            SELECT r.regla, r.defecto, r.severidad, r.unidad, r.cifra_afectada,
                   COALESCE(SUM(m.violaciones), 0)::BIGINT     AS violaciones,
                   COUNT(DISTINCT m.planta)::BIGINT            AS plantas,
                   SUM(m.usd_expuesto)                         AS usd_expuesto
            FROM reglas_calidad r
            LEFT JOIN mart_calidad_datos m USING (regla)
            GROUP BY ALL
            ORDER BY r.severidad, violaciones DESC, r.regla
        """)
        .pl()
        .with_columns(pl.col("usd_expuesto").round(0))
    )
    calidad_plantas = con.execute("""
            SELECT regla, severidad, planta,
                   SUM(violaciones)::BIGINT                    AS violaciones,
                   ANY_VALUE(universo_planta)                  AS universo,
                   ROUND(SUM(violaciones) * 100.0 / ANY_VALUE(universo_planta), 3) AS tasa_pct
            FROM mart_calidad_datos
            WHERE planta IS NOT NULL
            GROUP BY ALL
            ORDER BY tasa_pct DESC
        """).pl()
    # Medición del arnés: no depende de la base abierta (docs/calidad).
    try:
        impacto = con.execute("SELECT * FROM mart_impacto_defectos").pl()
    except Exception:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**mart_impacto_defectos no encontrado.**\n\n"
                    "Corre `uv run dbt build --profiles-dir .` sobre esta base."
                ),
                kind="warn",
            ),
        )
    nivel_impacto = mo.ui.dropdown(
        options={"Tasa del catálogo": "tasa", "Techo del rango": "techo"},
        value="Tasa del catálogo",
        label="Nivel",
    )
    return calidad_plantas, calidad_reglas, impacto, nivel_impacto


@app.cell
def _(impacto, nivel_impacto, pl):
    _nombres = {
        "perdida": "Pérdida",
        "tco": "Ahorro TCO",
        "brecha": "Brecha",
        "ocioso": "Ocioso",
        "ciclo": "Ciclo",
        "necesidad": "Necesidad",
        "flota": "Flota",
    }
    _sel = impacto.filter(pl.col("nivel") == nivel_impacto.value)
    _cifras = (
        _sel.filter(pl.col("tipo") == "cifra")
        .with_columns(pl.col("medida").replace_strict(_nombres))
        .pivot(on="medida", index="defecto", values="delta_pct")
    )
    _orden = {"llave": 0, "stock": 1, "saldo": 2, "conservacion": 3}
    _rotas = (
        _sel.filter((pl.col("tipo") == "identidad") & (pl.col("valor") > 0))
        .sort(pl.col("medida").replace_strict(_orden))
        .with_columns(pl.col("medida").replace({"conservacion": "conservación"}))
        .group_by("defecto", maintain_order=True)
        .agg(pl.col("medida").str.join(", ").alias("identidad_rota"))
    )
    tabla_impacto = (
        _sel.unique("defecto")
        .select("defecto", "regla", "severidad", "casos", "detectados")
        .join(_rotas, on="defecto", how="left")
        .join(_cifras.with_columns(pl.exclude("defecto").round(1)), on="defecto")
        .with_columns(pl.col("identidad_rota").fill_null("—"))
        .sort("defecto")
    )
    return (tabla_impacto,)


@app.cell
def _(
    bloqueos,
    calidad_plantas,
    calidad_reglas,
    mo,
    nivel_impacto,
    pl,
    tabla_impacto,
    total_cifras,
):
    _total = int(calidad_reglas["violaciones"].sum())
    _con = calidad_reglas.filter(pl.col("violaciones") > 0).height
    _lineas = "\n".join(f"- **{c}**: {', '.join(r)}" for c, r in bloqueos.items())
    vista_calidad = mo.vstack(
        [
            mo.md(f"""
        ## Tablero del extracto abierto

        Violaciones de las {calidad_reglas.height} reglas por causa sobre la base que abre el
        dashboard (`RPI_DB`). Una regla que bloquea con violaciones deja sin
        publicar las cifras que afecta; las alertas solo avisan.
        """),
            mo.hstack(
                [
                    mo.stat(label="Violaciones", value=f"{_total:,}"),
                    mo.stat(
                        label="Reglas con violaciones",
                        value=f"{_con} de {calidad_reglas.height}",
                    ),
                    mo.stat(label="Cifras bloqueadas", value=f"{len(bloqueos)} de {total_cifras}"),
                ]
            ),
            mo.callout(mo.md(f"**Cifras que no se publican:**\n\n{_lineas}"), kind="danger")
            if bloqueos
            else mo.md("Ninguna cifra bloqueada."),
            mo.ui.table(calidad_reglas, selection=None, page_size=calidad_reglas.height),
            mo.md("## Tasa de violaciones por regla y planta"),
            mo.ui.table(calidad_plantas, selection=None, page_size=10)
            if calidad_plantas.height
            else mo.md("Sin violaciones por planta."),
            mo.md("""
        ## Impacto de cada defecto, medido por el arnés

        Cada defecto del catálogo, solo, contra el dataset limpio: casos
        inyectados, detectados por la regla de su defecto, identidades que
        rompe y delta en % de cada cifra publicada (`mart_impacto_defectos`).
        No depende de la base abierta.
        """),
            nivel_impacto,
            mo.ui.table(tabla_impacto, selection=None, page_size=tabla_impacto.height),
        ]
    )
    return (vista_calidad,)


@app.cell
def _(con, mo, pl):
    # Gemelo de la red RPL (ADR-038, ADR-039): flujos y stock de la traza por
    # semana, red planta × cliente y escenarios de capacidad del simulador.
    try:
        flujos_sem = con.execute("SELECT * FROM mart_flujos_semanales").pl()
        red_sem = con.execute("SELECT * FROM mart_red_semanal").pl()
        flota_sem = con.execute("""
            SELECT planta, tipo_material, semana, ANY_VALUE(fecha_cierre) AS fecha_cierre,
                   SUM(vacios)::BIGINT AS vacios, SUM(linea)::BIGINT AS linea,
                   SUM(llenos)::BIGINT AS llenos, SUM(cliente)::BIGINT AS cliente,
                   SUM(sucios)::BIGINT AS sucios, SUM(reparacion)::BIGINT AS reparacion,
                   SUM(scrap)::BIGINT AS scrap
            FROM mart_flota_semanal
            GROUP BY ALL
        """).pl()
        sim_cap = con.execute("SELECT * FROM mart_sim_capacidad").pl()
        sim_dia = con.execute("SELECT * FROM mart_sim_vacios_diario").pl()
        politica = dict(
            con.execute("SELECT tipo_material, dias_cobertura FROM parametros_flota").fetchall()
        )
        pais = dict(con.execute("SELECT planta, pais FROM plantas").fetchall())
    except Exception:
        mo.stop(
            True,
            mo.callout(
                mo.md(
                    "**Marts del gemelo no encontrados.**\n\n"
                    "Corre `uv run dbt seed --profiles-dir .` y "
                    "`uv run dbt build --profiles-dir .`."
                ),
                kind="warn",
            ),
        )
    semanas = sorted(flota_sem["semana"].unique().to_list())
    # Con defectos hay filas sin planta o sin tipo; no tienen lugar en la red.
    _plantas = sorted(flota_sem["planta"].drop_nulls().unique().to_list())
    _escenarios = sorted(sim_cap["escenario"].unique().to_list())
    planta_red = mo.ui.dropdown(options=_plantas, value=_plantas[0], label="Planta")
    tipo_red = mo.ui.dropdown(options={"KLT": "KLT", "Rack": "RACK"}, value="KLT", label="Tipo")
    _esc_inicial = "paro_lavado_5" if "paro_lavado_5" in _escenarios else _escenarios[0]
    escenario_red = mo.ui.dropdown(options=_escenarios, value=_esc_inicial, label="Escenario")
    reproducir = mo.ui.switch(label="Reproducir")
    # La semana arranca en la del peor paro del escenario por default, que es
    # donde vacíos se acerca a cero.
    _peor = sim_cap.filter(
        (pl.col("escenario") == _esc_inicial)
        & (pl.col("planta") == _plantas[0])
        & (pl.col("tipo_material") == "KLT")
    )["inicio_peor"].to_list()
    _inicio = _peor[0] if _peor and _peor[0] is not None else semanas[-1]
    get_semana, set_semana = mo.state(
        max(i for i, s in enumerate(semanas) if s <= _inicio) if semanas else 0
    )
    return (
        escenario_red,
        flota_sem,
        flujos_sem,
        get_semana,
        pais,
        planta_red,
        politica,
        red_sem,
        reproducir,
        semanas,
        set_semana,
        sim_cap,
        sim_dia,
        tipo_red,
    )


@app.cell
def _(get_semana, mo, semanas, set_semana):
    semana_red = mo.ui.slider(
        start=0,
        stop=max(len(semanas) - 1, 0),
        value=get_semana(),
        on_change=set_semana,
        label="Semana",
        full_width=True,
    )
    return (semana_red,)


@app.cell
def _(mo, reproducir):
    # Con Reproducir encendido, cada segundo avanza una semana.
    tic = mo.ui.refresh(default_interval="1s") if reproducir.value else None
    return (tic,)


@app.cell
def _(get_semana, reproducir, semanas, set_semana, tic):
    if tic is not None and reproducir.value and semanas:
        set_semana((get_semana() + 1) % len(semanas))
    return


@app.cell
def _(
    dibujos,
    escenario_red,
    flota_sem,
    flujos_sem,
    pais,
    pl,
    planta_red,
    politica,
    red_sem,
    semana_red,
    semanas,
    sim_dia,
    tipo_red,
):
    _semana = semanas[semana_red.value]
    _tipo = tipo_red.value
    _f = flota_sem.filter((pl.col("tipo_material") == _tipo) & (pl.col("semana") == _semana))
    _cierre = _f["fecha_cierre"].max()
    _esc = sim_dia.filter(
        (pl.col("escenario") == escenario_red.value)
        & (pl.col("tipo_material") == _tipo)
        & (pl.col("fecha") == _cierre)
    )
    _flujos = flujos_sem.filter((pl.col("tipo_material") == _tipo) & (pl.col("semana") == _semana))
    _salidas = dict(
        _flujos.filter(pl.col("destino") == "cliente").select("planta", "contenedores").iter_rows()
    )
    _vac_esc = dict(_esc.select("planta", "vacios").iter_rows())
    _desechable = dict(
        sim_dia.filter(
            (pl.col("escenario") == escenario_red.value)
            & (pl.col("tipo_material") == _tipo)
            & pl.col("fecha").is_between(_semana, _cierre)
        )
        .group_by("planta")
        .agg(pl.col("faltante").sum())
        .iter_rows()
    )

    # Anillo de la planta: flujos y stock de la traza; vacíos, del escenario.
    _p = planta_red.value
    _fila = _f.filter(pl.col("planta") == _p)
    _stock = _fila.row(0, named=True) if _fila.height else {}
    _e = _esc.filter(pl.col("planta") == _p)
    _notas = {}
    _alerta = False
    if _e.height:
        _r = _e.row(0, named=True)
        _stock = dict(_stock) | {"vacios": _r["vacios"]}
        _cob = dibujos.cobertura(_r["vacios"], _salidas.get(_p, 0))
        _des = _desechable.get(_p, 0)
        _alerta = dibujos.en_alerta(_r["vacios"], _salidas.get(_p, 0), _des, politica[_tipo])
        _notas["vacios"] = (
            f"traza {_r['vacios_replay']:,}"
            + (f" · {_cob:.1f} días" if _cob is not None else "")
            + (f" · desechable {_des:,}" if _des else "")
        )
        if _r["cola_lavado"]:
            _notas["sucios"] = f"cola de lavado {_r['cola_lavado']:,}"
        if _r["cola_reparacion"]:
            _notas["reparacion"] = f"cola {_r['cola_reparacion']:,}"
    _todos_flujos = flujos_sem.filter((pl.col("tipo_material") == _tipo) & (pl.col("planta") == _p))
    svg_anillo = dibujos.anillo(
        _stock,
        {
            (o, d): v
            for o, d, v in _flujos.filter(pl.col("planta") == _p)
            .select("origen", "destino", "contenedores")
            .iter_rows()
        },
        escala=float(_todos_flujos["contenedores"].max() or 0),
        alerta=_alerta,
        notas=_notas,
        titulo=f"{_p} · {_tipo} · semana del {_semana:%d.%m.%Y}",
    )

    # Red: rutas planta × cliente de la semana; planta en rojo con la misma
    # regla que vacíos en el anillo.
    _rutas = red_sem.filter((pl.col("tipo_material") == _tipo) & (pl.col("semana") == _semana))
    _plantas = []
    for _pl in sorted(flota_sem["planta"].drop_nulls().unique().to_list()):
        _alerta_pl = dibujos.en_alerta(
            _vac_esc.get(_pl, 0), _salidas.get(_pl, 0), _desechable.get(_pl, 0), politica[_tipo]
        )
        _plantas.append((_pl, pais.get(_pl, "—"), _alerta_pl))
    svg_red = dibujos.red(
        _plantas,
        sorted(
            red_sem.filter(pl.col("tipo_material") == _tipo)["cliente"]
            .drop_nulls()
            .unique()
            .to_list()
        ),
        list(_rutas.select("planta", "cliente", "salidas").iter_rows()),
        escala=float(red_sem.filter(pl.col("tipo_material") == _tipo)["salidas"].max() or 0),
        resalta=_p,
        titulo=f"Salidas a cliente, {_tipo}, semana del {_semana:%d.%m.%Y}",
    )
    return svg_anillo, svg_red


@app.cell
def _(
    a_imagen,
    escenario_red,
    np,
    pl,
    planta_red,
    plt,
    semana_red,
    semanas,
    sim_cap,
    sim_dia,
    tipo_red,
):
    _d = sim_dia.filter(
        (pl.col("escenario") == escenario_red.value)
        & (pl.col("planta") == planta_red.value)
        & (pl.col("tipo_material") == tipo_red.value)
    ).sort("fecha")
    _c = sim_cap.filter(
        (pl.col("escenario") == escenario_red.value)
        & (pl.col("planta") == planta_red.value)
        & (pl.col("tipo_material") == tipo_red.value)
    )
    gemelo_fila = _c.row(0, named=True) if _c.height else None

    def _grafica():
        _fig, (_a1, _a2) = plt.subplots(
            2, 1, figsize=(10, 4.2), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
        )
        _x = _d["fecha"].to_list()
        _a1.plot(_x, _d["vacios_replay"] / 1e3, color="#7f8c8d", lw=1, label="traza del MB51")
        _a1.plot(_x, _d["vacios"] / 1e3, color="#2c7fb8", lw=1.2, label="escenario")
        _a1.set_ylabel("vacíos, miles")
        _a2.fill_between(_x, _d["cola_lavado"], color="#c0392b", alpha=0.5, step="mid")
        _a2.set_ylabel("cola de lavado")
        if gemelo_fila and gemelo_fila["inicio_peor"] is not None:
            _ini = np.datetime64(gemelo_fila["inicio_peor"], "D")
            _fin = np.busday_offset(_ini, gemelo_fila["paro_dias"], roll="forward")
            for _ax in (_a1, _a2):
                _ax.axvspan(_ini, _fin, color="#f39c12", alpha=0.2, lw=0)
        for _ax in (_a1, _a2):
            _ax.axvline(semanas[semana_red.value], color="#2c3e50", lw=0.8, ls=":")
            _ax.spines[["top", "right"]].set_visible(False)
        _a1.legend(frameon=False, fontsize=8)
        _fig.tight_layout()
        return a_imagen(_fig)

    grafica_gemelo = _grafica() if _d.height else None
    return gemelo_fila, grafica_gemelo


@app.cell
def _(
    escenario_red,
    gemelo_fila,
    grafica_gemelo,
    mo,
    planta_red,
    reproducir,
    semana_red,
    sim_cap,
    svg_anillo,
    svg_red,
    tic,
    tipo_red,
):
    def _stats():
        if gemelo_fila is None:
            return mo.md("Sin escenario para esta planta y tipo.")
        _r = gemelo_fila
        _rep = sim_cap.filter(
            (sim_cap["escenario"] == "replay")
            & (sim_cap["planta"] == _r["planta"])
            & (sim_cap["tipo_material"] == _r["tipo_material"])
        )
        _sobra_rep = _rep["flota_sobra"][0] if _rep.height else _r["flota_sobra"]
        _cap = _r["capacidad_lavado"]
        return mo.hstack(
            [
                mo.stat(
                    label="Capacidad de lavado",
                    value="sin límite" if _cap is None else f"{_cap:,.0f} por día",
                    caption=f"salida media {_r['salida_media_lavado']:,.0f}",
                ),
                mo.stat(label="Espera en lavado", value=f"{_r['espera_lavado_dias']:.2f} días"),
                mo.stat(
                    label="Desechable",
                    value=f"{_r['faltante']:,}",
                    caption=f"${_r['faltante_usd']:,.0f}",
                ),
                mo.stat(
                    label="Flota que sobra",
                    value=f"{_r['flota_sobra']:,}",
                    caption=f"{_r['flota_sobra'] - _sobra_rep:+,} contra la traza",
                ),
            ]
        )

    vista_red = mo.vstack(
        [
            mo.md("""
        ## Gemelo de la red RPL

        El gemelo corre sobre la traza del MB51: las salidas de sucios y de
        reparación dicen cuándo quedó listo cada contenedor, y con capacidad
        por día lo que no cabe espera su turno. Sin límite reproduce el MB51.
        Vacíos y planta en rojo: en la semana algún material salió en
        desechable, o vacíos cubre menos días de salidas a cliente que la
        política de `parametros_flota`.
        """),
            mo.hstack([planta_red, tipo_red, escenario_red, reproducir], justify="start"),
            semana_red,
            tic if tic is not None else mo.md(""),
            mo.md("### La planta: ciclo del empaque en la semana"),
            mo.Html(svg_anillo),
            mo.md(
                "Flujos y stock de la traza; vacíos, sucios y reparación muestran "
                "el escenario. Faltante y baja son salidas definitivas de la flota."
            ),
            mo.md("### Lavado de empaques día por día"),
            _stats(),
            grafica_gemelo if grafica_gemelo is not None else mo.md("Sin serie diaria."),
            mo.md(
                "Naranja: el peor paro del escenario en esta planta. La línea "
                "punteada es la semana del anillo."
            ),
            mo.md("### La red: salidas a cliente en la semana"),
            mo.Html(svg_red),
        ]
    )
    return (vista_red,)


@app.cell
def _(
    aviso_sin_plan,
    mo,
    publica,
    sin_plan,
    vista_calidad,
    vista_fase1,
    vista_necesidad,
    vista_red,
    vista_tco,
):
    mo.ui.tabs(
        {
            "Rotación y pérdidas": vista_fase1,
            "TCO": publica(vista_tco, ["perdida", "tco"]),
            "Necesidad de flota": aviso_sin_plan
            if sin_plan
            else publica(vista_necesidad, ["necesidad", "brecha", "ocioso", "flota"]),
            "Red RPL": publica(vista_red, ["flota", "saldo_cliente", "capacidad"]),
            # Sin bloqueo: es la vista que explica los bloqueos.
            "Calidad de datos": vista_calidad,
        }
    )
    return


if __name__ == "__main__":
    app.run()
