"""
Ciclo dentro de la planta (ADR-017, ADR-018): traslados 311 y stock inicial.

Dos tests fijan stock_inicial: el stock no queda negativo (la flota alcanza)
y la holgura cae en su rango (la flota no sobra). Con uno solo, un bug que
infla la flota pasaría en verde.
"""

import polars as pl

from rpi.config import GeneratorConfig

TRAMOS = {("VACI", "LINE"), ("LINE", "LLEN"), ("SUCI", "VACI")}
ALMACENES_CICLO = ["VACI", "LINE", "LLEN", "SUCI"]
DOC = ["Werks", "Mjahr", "Mblnr"]


def _docs_311(df: pl.DataFrame) -> pl.DataFrame:
    """Un renglón por documento 311 con su origen, destino y cantidad."""
    t = df.filter(pl.col("Bwart") == "311")
    sale = t.filter(pl.col("Zeile") == "0001").select(
        *DOC, "Matnr", "Budat", pl.col("Lgort").alias("origen"), (-pl.col("Menge")).alias("sale")
    )
    entra = t.filter(pl.col("Zeile") == "0002").select(
        *DOC, pl.col("Matnr").alias("Matnr_2"), pl.col("Lgort").alias("destino"), "Menge"
    )
    return sale.join(entra, on=DOC, how="full", coalesce=True)


def test_311_en_pareja(df_ci: pl.DataFrame) -> None:
    t = df_ci.filter(pl.col("Bwart") == "311")
    posiciones = t.group_by(DOC).agg(pl.len().alias("n"), pl.col("Menge").sum().alias("suma"))
    assert posiciones["n"].unique().to_list() == [2], "Documento 311 sin dos posiciones"
    assert posiciones["suma"].unique().to_list() == [0], "Documento 311 que no suma cero"

    docs = _docs_311(df_ci)
    assert docs.filter(pl.col("Matnr") != pl.col("Matnr_2")).is_empty()
    assert docs.filter(pl.col("sale") <= 0).is_empty(), "Posición 1 tiene que salir"
    pares = set(docs.select("origen", "destino").unique().iter_rows())
    assert pares == TRAMOS, f"Tramos: {sorted(pares)}"


def test_311_un_documento_por_dia_material_y_tramo(df_ci: pl.DataFrame) -> None:
    # ADR-017, punto 4: conteo al cierre de turno.
    dup = _docs_311(df_ci).select("Werks", "Matnr", "Budat", "origen", "destino").is_duplicated()
    assert dup.sum() == 0


def test_311_registro(df_ci: pl.DataFrame) -> None:
    t = df_ci.filter(pl.col("Bwart") == "311")
    assert t.filter(pl.col("Cpudt") != pl.col("Budat")).is_empty()
    assert t.filter(pl.col("Budat").dt.weekday() > 5).is_empty(), "311 en fin de semana"
    assert t.select(pl.col("Kunnr", "Lifnr", "Xblnr").null_count()).row(0) == (t.height,) * 3


def test_stock_inicial_contrato(
    df_ci: pl.DataFrame, stock_ci: pl.DataFrame, cfg_ci: GeneratorConfig
) -> None:
    assert not stock_ci.select("Werks", "Lgort", "Matnr").is_duplicated().any()
    assert stock_ci.filter(pl.col("Menge") <= 0).is_empty()
    assert set(stock_ci["Lgort"].unique()) == {"VACI", "LINE", "LLEN"}
    assert stock_ci.filter(pl.col("Matnr").str.starts_with("CTN")).is_empty()
    assert stock_ci["Kunnr"].null_count() == stock_ci.height
    assert set(stock_ci["Werks"].unique()) == {p.werks for p in cfg_ci.plants}
    # Foto al cierre del día anterior al primer movimiento (MB5B).
    assert stock_ci["Fecha"].n_unique() == 1
    assert stock_ci["Fecha"][0] < df_ci["Budat"].min()


def test_stock_no_negativo_por_dia(df_ci: pl.DataFrame, stock_ci: pl.DataFrame) -> None:
    """Stock por almacén al cierre de cada día: foto inicial más movimientos."""
    llave = ["Werks", "Matnr", "Lgort"]
    movimientos = (
        df_ci.filter(pl.col("Lgort").is_in(ALMACENES_CICLO))
        .group_by(*llave, "Budat")
        .agg(pl.col("Menge").sum())
    )
    inicial = stock_ci.select(*llave, pl.col("Fecha").alias("Budat"), "Menge")
    saldos = (
        pl.concat([inicial, movimientos])
        .sort(*llave, "Budat")
        .with_columns(pl.col("Menge").cum_sum().over(llave).alias("saldo"))
    )
    negativos = saldos.filter(pl.col("saldo") < 0)
    assert negativos.is_empty(), f"Stock negativo:\n{negativos.head()}"


def test_holgura_en_rango(
    df_ci: pl.DataFrame, stock_ci: pl.DataFrame, cfg_ci: GeneratorConfig
) -> None:
    """
    Peor saldo de VACI = saldo al cierre anterior menos salidas del día. Con
    flota = ceil(mínimo × (1 + h)) y h ≤ holgura máxima, el peor saldo queda
    entre 0 y holgura × mínimo, más una unidad por el redondeo.
    """
    llave = ["Werks", "Matnr"]
    vaci = (
        df_ci.filter(pl.col("Lgort") == "VACI")
        .group_by(*llave, "Budat")
        .agg(
            pl.col("Menge").filter(pl.col("Menge") > 0).sum().alias("entra"),
            pl.col("Menge").filter(pl.col("Menge") < 0).sum().alias("sale"),
        )
        .join(
            stock_ci.filter(pl.col("Lgort") == "VACI").select(*llave, "Menge"),
            on=llave,
            how="left",
        )
        .with_columns(pl.col("Menge").fill_null(0).alias("inicial"))
        .sort(*llave, "Budat")
        .with_columns(
            (pl.col("inicial") + (pl.col("entra") + pl.col("sale")).cum_sum().over(llave)).alias(
                "cierre"
            )
        )
        .with_columns(
            (
                pl.col("cierre").shift(1).over(llave).fill_null(pl.col("inicial")) + pl.col("sale")
            ).alias("peor")
        )
        .group_by(llave)
        .agg(pl.col("peor").min(), pl.col("inicial").first())
        .with_columns((pl.col("inicial") - pl.col("peor")).alias("minimo"))
    )
    holgura = cfg_ci.internal.fleet_slack_max
    fuera = vaci.filter((pl.col("peor") < 0) | (pl.col("peor") > holgura * pl.col("minimo") + 1))
    assert fuera.is_empty(), f"Holgura fuera de rango:\n{fuera.head()}"
    # Que la prueba no pase con todo en cero.
    assert vaci["peor"].sum() > 0
