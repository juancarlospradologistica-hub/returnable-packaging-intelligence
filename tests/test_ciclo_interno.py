"""
Ciclo dentro de la planta (ADR-017 a ADR-019): traslados, daño, reparación,
scrap, baja y stock inicial.

Dos tests fijan stock_inicial: el stock no queda negativo (la flota alcanza)
y la holgura cae en su rango (la flota no sobra). Con uno solo, un bug que
infla la flota pasaría en verde. Lo mismo con el scrap: la baja cuadra con lo
que entra a SCRP y el scrap anual cae en el rango del supuesto.
"""

import numpy as np
import polars as pl
import pytest

from rpi.config import GeneratorConfig

# Clase de movimiento → tramos (origen, destino) que puede llevar.
TRAMOS = {
    "311": {("VACI", "LINE"), ("LINE", "LLEN"), ("SUCI", "VACI"), ("REPA", "VACI")},
    "344": {("SUCI", "SUCI")},
    "325": {("SUCI", "REPA"), ("REPA", "SCRP")},
    "343": {("REPA", "REPA")},
}
INTERNOS = [*TRAMOS, "555"]
ALMACENES_CICLO = ["VACI", "LINE", "LLEN", "SUCI", "REPA", "SCRP"]
DOC = ["Werks", "Mjahr", "Mblnr"]

# Supuestos de ADR-016 y ADR-017 (rango completo).
DANO = {"KLT": (0.01, 0.03), "RCK": (0.03, 0.08)}
SCRAP_ANUAL = {"KLT": (0.005, 0.02), "RCK": (0.01, 0.03)}

# ADR-017, punto 3: el tipo de stock sale de Bwart y signo.
BLOQUEADO = (
    pl.col("Bwart").is_in(["325", "555"])
    | ((pl.col("Bwart") == "344") & (pl.col("Menge") > 0))
    | ((pl.col("Bwart") == "343") & (pl.col("Menge") < 0))
)


def _docs(df: pl.DataFrame, bwart: str) -> pl.DataFrame:
    """Un renglón por documento de traslado con su origen, destino y cantidad."""
    t = df.filter(pl.col("Bwart") == bwart)
    sale = t.filter(pl.col("Zeile") == "0001").select(
        *DOC, "Matnr", "Budat", pl.col("Lgort").alias("origen"), (-pl.col("Menge")).alias("sale")
    )
    entra = t.filter(pl.col("Zeile") == "0002").select(
        *DOC, pl.col("Matnr").alias("Matnr_2"), pl.col("Lgort").alias("destino"), "Menge"
    )
    return sale.join(entra, on=DOC, how="full", coalesce=True)


def _saldos_diarios(df: pl.DataFrame, stock: pl.DataFrame) -> pl.DataFrame:
    """Stock por almacén y tipo de stock al cierre de cada día: foto inicial más movimientos."""
    llave = ["Werks", "Matnr", "Lgort", "bloqueado"]
    movimientos = (
        df.filter(pl.col("Lgort").is_in(ALMACENES_CICLO))
        .with_columns(BLOQUEADO.alias("bloqueado"))
        .group_by(*llave, "Budat")
        .agg(pl.col("Menge").sum())
    )
    inicial = stock.select(
        "Werks",
        "Matnr",
        "Lgort",
        pl.lit(False).alias("bloqueado"),
        pl.col("Fecha").alias("Budat"),
        "Menge",
    )
    return (
        pl.concat([inicial, movimientos])
        .sort(*llave, "Budat")
        .with_columns(pl.col("Menge").cum_sum().over(llave).alias("saldo"))
    )


@pytest.mark.parametrize("bwart", list(TRAMOS))
def test_traslado_en_pareja(df_ci: pl.DataFrame, bwart: str) -> None:
    t = df_ci.filter(pl.col("Bwart") == bwart)
    posiciones = t.group_by(DOC).agg(pl.len().alias("n"), pl.col("Menge").sum().alias("suma"))
    assert posiciones["n"].unique().to_list() == [2], f"{bwart} sin dos posiciones"
    assert posiciones["suma"].unique().to_list() == [0], f"{bwart} que no suma cero"

    docs = _docs(df_ci, bwart)
    assert docs.filter(pl.col("Matnr") != pl.col("Matnr_2")).is_empty()
    assert docs.filter(pl.col("sale") <= 0).is_empty(), "Posición 1 tiene que salir"
    pares = set(docs.select("origen", "destino").unique().iter_rows())
    assert pares == TRAMOS[bwart], f"Tramos de {bwart}: {sorted(pares)}"


def test_un_documento_por_dia_material_y_tramo(df_ci: pl.DataFrame) -> None:
    # ADR-017, punto 4: conteo al cierre de turno.
    docs = pl.concat([_docs(df_ci, b).with_columns(pl.lit(b).alias("Bwart")) for b in TRAMOS])
    dup = docs.select("Werks", "Matnr", "Budat", "Bwart", "origen", "destino").is_duplicated()
    assert dup.sum() == 0


def test_baja_en_lote_mensual(df_ci: pl.DataFrame) -> None:
    """555: un documento por planta y mes, el último día hábil, una posición por material."""
    baja = df_ci.filter(pl.col("Bwart") == "555")
    assert baja.height > 0, "Sin bajas: el test no prueba nada"
    assert baja.filter(pl.col("Menge") >= 0).is_empty(), "555 tiene que restar"
    assert set(baja["Lgort"].unique()) == {"SCRP"}

    fecha = baja["Budat"].to_numpy().astype("datetime64[D]")
    fin_mes = baja["Budat"].dt.month_end().to_numpy().astype("datetime64[D]")
    assert (fecha == np.busday_offset(fin_mes, 0, roll="backward")).all(), "555 fuera de cierre"

    por_mes = baja.group_by("Werks", pl.col("Budat").dt.truncate("1mo")).agg(
        pl.col("Mblnr").n_unique().alias("docs"), pl.col("Matnr").is_duplicated().any()
    )
    assert por_mes["docs"].unique().to_list() == [1], "Más de un lote por planta y mes"
    assert not por_mes["Matnr"].any(), "Material repetido dentro del lote"


def test_registro_interno(df_ci: pl.DataFrame) -> None:
    t = df_ci.filter(pl.col("Bwart").is_in(INTERNOS))
    assert t.filter(pl.col("Cpudt") != pl.col("Budat")).is_empty()
    assert t.filter(pl.col("Budat").dt.weekday() > 5).is_empty(), (
        "Movimiento interno en fin de semana"
    )
    assert t.select(pl.col("Kunnr", "Lifnr", "Xblnr").null_count()).row(0) == (t.height,) * 3
    # Un documento se registra una sola vez: todas sus posiciones comparten hora.
    assert t.group_by(DOC).agg(pl.col("Cputm").n_unique())["Cputm"].max() == 1


def test_stock_inicial_contrato(
    df_ci: pl.DataFrame, stock_ci: pl.DataFrame, cfg_ci: GeneratorConfig
) -> None:
    assert not stock_ci.select("Werks", "Lgort", "Matnr").is_duplicated().any()
    assert stock_ci.filter(pl.col("Menge") <= 0).is_empty()
    # Sin 622 antes de la ventana no hay daño previo: nada en REPA ni SCRP (ADR-019).
    assert set(stock_ci["Lgort"].unique()) == {"VACI", "LINE", "LLEN"}
    assert stock_ci.filter(pl.col("Matnr").str.starts_with("CTN")).is_empty()
    assert stock_ci["Kunnr"].null_count() == stock_ci.height
    assert set(stock_ci["Werks"].unique()) == {p.werks for p in cfg_ci.plants}
    # Foto al cierre del día anterior al primer movimiento (MB5B).
    assert stock_ci["Fecha"].n_unique() == 1
    assert stock_ci["Fecha"][0] < df_ci["Budat"].min()


def test_stock_no_negativo_por_dia(df_ci: pl.DataFrame, stock_ci: pl.DataFrame) -> None:
    negativos = _saldos_diarios(df_ci, stock_ci).filter(pl.col("saldo") < 0)
    assert negativos.is_empty(), f"Stock negativo:\n{negativos.head()}"


def test_bloqueado_solo_donde_toca(df_ci: pl.DataFrame, stock_ci: pl.DataFrame) -> None:
    """
    Al cierre del día: lo dañado no se queda bloqueado en SUCI (344 y 325 el
    mismo día), lo reparado no se queda libre en REPA (343 y 311 el mismo día),
    y SCRP solo tiene bloqueado.
    """
    s = _saldos_diarios(df_ci, stock_ci)
    fuera = s.filter(
        ((pl.col("Lgort") == "SUCI") & pl.col("bloqueado") & (pl.col("saldo") != 0))
        | ((pl.col("Lgort") == "REPA") & ~pl.col("bloqueado") & (pl.col("saldo") != 0))
        | ((pl.col("Lgort") == "SCRP") & ~pl.col("bloqueado") & (pl.col("saldo") != 0))
    )
    assert fuera.is_empty(), f"Stock en tipo equivocado:\n{fuera.head()}"


def test_scrp_vacio_despues_de_la_baja(df_ci: pl.DataFrame) -> None:
    """
    El lote del mes se lleva todo lo que entró a SCRP hasta ese cierre. Se valida
    el total de la planta: con stock no negativo por material, total cero
    implica cero en cada material.
    """
    cierres = df_ci.filter(pl.col("Bwart") == "555").select("Werks", "Budat").unique()
    saldo = (
        df_ci.filter(pl.col("Lgort") == "SCRP")
        .group_by("Werks", "Budat")
        .agg(pl.col("Menge").sum())
        .sort("Werks", "Budat")
        .with_columns(pl.col("Menge").cum_sum().over("Werks").alias("saldo"))
    )
    al_cierre = cierres.join(saldo, on=["Werks", "Budat"]).filter(pl.col("saldo") != 0)
    assert al_cierre.is_empty(), f"SCRP con saldo después de la baja:\n{al_cierre.head()}"


@pytest.mark.parametrize("tipo", list(DANO))
def test_dano_y_scrap_en_rango(
    df_ci: pl.DataFrame, stock_ci: pl.DataFrame, cfg_ci: GeneratorConfig, tipo: str
) -> None:
    """
    Daño sobre lo recogido y scrap anual sobre la flota inicial dentro del rango
    del supuesto. El scrap anual depende de la rotación de la flota, no solo de
    scrap_share: un cambio en el ciclo que lo saque del rango se ve aquí (ADR-019).
    """
    d = df_ci.filter(pl.col("Matnr").str.starts_with(tipo))
    recogido = d.filter(pl.col("Bwart") == "622")["Menge"].sum()
    entra = d.filter(pl.col("Bwart") == "325", pl.col("Menge") > 0)
    a_repa = entra.filter(pl.col("Lgort") == "REPA")["Menge"].sum()
    a_scrp = entra.filter(pl.col("Lgort") == "SCRP")["Menge"].sum()
    flota = stock_ci.filter(pl.col("Matnr").str.starts_with(tipo))["Menge"].sum()
    anios = ((cfg_ci.reference_date - df_ci["Budat"].min()).days + 1) / 365.25

    dano = a_repa / recogido
    scrap = a_scrp / flota / anios
    lo, hi = DANO[tipo]
    assert lo <= dano <= hi, f"Daño {tipo} {dano:.2%} fuera de [{lo:.1%}, {hi:.1%}]"
    lo, hi = SCRAP_ANUAL[tipo]
    assert lo <= scrap <= hi, f"Scrap anual {tipo} {scrap:.2%} fuera de [{lo:.1%}, {hi:.1%}]"


def test_baja_cuadra_con_scrap(df_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    """Todo lo que llega a SCRP se da de baja; solo queda lo que entró en el mes del corte."""
    entra = df_ci.filter(
        (pl.col("Bwart") == "325") & (pl.col("Lgort") == "SCRP") & (pl.col("Menge") > 0)
    )
    baja = -df_ci.filter(pl.col("Bwart") == "555")["Menge"].sum()
    ultimo_lote = df_ci.filter(pl.col("Bwart") == "555")["Budat"].max()
    pendiente = entra.filter(pl.col("Budat") > ultimo_lote)["Menge"].sum()
    assert entra["Menge"].sum() == baja + pendiente


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
