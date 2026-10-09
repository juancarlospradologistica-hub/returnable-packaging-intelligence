from datetime import timedelta
from pathlib import Path

import polars as pl
import pytest

from rpi.config import GeneratorConfig
from rpi.generator import (
    INSTRUCCION,
    PARTES,
    PLAN,
    STOCK_INICIAL,
    generate,
    reconciliation_dates,
)

SEEDS = Path(__file__).parents[1] / "seeds"
RETORNABLE = ~pl.col("Matnr").str.starts_with("CTN")


def _llaves_seed(nombre: str) -> set[str]:
    # La llave es la primera columna. infer_schema=False deja "101" como texto.
    return set(pl.read_csv(SEEDS / nombre, infer_schema=False).to_series(0))


def test_filas_dentro_de_rango(df_ci: pl.DataFrame) -> None:
    # Con 2 plantas y 12 meses: ~50k filas de ciclo con cliente y cartón más los 311 internos.
    n = df_ci.height
    assert 100_000 < n < 300_000, f"Volumen fuera de rango: {n}"


def test_plantas_en_df(df_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    assert set(df_ci["Werks"].unique()) == {p.werks for p in cfg_ci.plants}


def test_reproducibilidad(cfg_ci: GeneratorConfig, tmp_path) -> None:
    """Misma seed, mismo dataset fila por fila."""
    df1 = generate(cfg=cfg_ci, output_dir=str(tmp_path / "a")).collect()
    df2 = generate(cfg=cfg_ci, output_dir=str(tmp_path / "b")).collect()
    assert df1.equals(df2)
    for archivo in (STOCK_INICIAL, PARTES, INSTRUCCION, PLAN):
        uno = pl.read_parquet(tmp_path / "a" / archivo)
        dos = pl.read_parquet(tmp_path / "b" / archivo)
        assert uno.equals(dos), archivo


def test_nada_despues_del_corte(df_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    assert df_ci["Budat"].max() <= cfg_ci.reference_date
    assert df_ci["Cpudt"].max() <= cfg_ci.reference_date


def test_llave_de_documento_unica(df_ci: pl.DataFrame) -> None:
    # Mblnr es único por año en todo el mandante, no solo dentro de la planta.
    dup = df_ci.select("Mjahr", "Mblnr", "Zeile").is_duplicated().sum()
    assert dup == 0, f"{dup} filas con llave de documento repetida"


def test_mjahr_coincide_con_budat(df_ci: pl.DataFrame) -> None:
    malos = df_ci.filter(pl.col("Mjahr") != pl.col("Budat").dt.year()).height
    assert malos == 0


def test_carton_no_entra_al_ciclo(df_ci: pl.DataFrame) -> None:
    ciclo = df_ci.filter(
        pl.col("Matnr").str.starts_with("CTN") & pl.col("Bwart").is_in(["621", "622", "702"])
    ).height
    assert ciclo == 0


def test_rack_dedicado_a_un_cliente(df_ci: pl.DataFrame) -> None:
    max_clientes = (
        df_ci.filter((pl.col("Bwart") == "621") & pl.col("Matnr").str.starts_with("RCK"))
        .group_by("Werks", "Matnr")
        .agg(pl.col("Kunnr").n_unique())["Kunnr"]
        .max()
    )
    assert max_clientes == 1


def test_merma_en_rango(df_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    """
    Merma reconocida (702) sobre salidas que ya pasaron por una conciliación
    con 120 días de antigüedad. Debe caer entre la tasa baja y la alta de LossConfig.
    """
    recon = reconciliation_dates(cfg_ci)
    limite = recon[-1] - timedelta(days=120)
    salidas = -df_ci.filter((pl.col("Bwart") == "621") & (pl.col("Budat") <= limite))["Menge"].sum()
    perdidos = -df_ci.filter(pl.col("Bwart") == "702")["Menge"].sum()
    if salidas == 0:
        pytest.skip("Sin salidas con antigüedad suficiente")

    tasa = perdidos / salidas
    assert cfg_ci.loss.rate_low * 0.5 <= tasa <= cfg_ci.loss.rate_high, (
        f"Merma observada {tasa:.4f} fuera de "
        f"[{cfg_ci.loss.rate_low * 0.5:.4f}, {cfg_ci.loss.rate_high:.4f}]"
    )


def test_saldo_en_cliente_nunca_negativo(df_ci: pl.DataFrame) -> None:
    """
    Saldo de stock especial V por cuenta (planta × cliente × material), en orden
    de contabilización. 621 suma; 622 y 702 restan. En SAP no se puede recoger
    ni dar de baja más de lo que hay en la cuenta.
    """
    minimo = (
        df_ci.filter(pl.col("Bwart").is_in(["621", "622", "702"]))
        .with_columns(
            pl.when(pl.col("Bwart") == "702")
            .then(pl.col("Menge"))
            .otherwise(-pl.col("Menge"))
            .alias("delta")
        )
        .sort("Budat", "Mjahr", "Mblnr", "Zeile")
        .with_columns(pl.col("delta").cum_sum().over("Werks", "Kunnr", "Matnr").alias("saldo"))[
            "saldo"
        ]
        .min()
    )
    assert minimo >= 0, f"Saldo en cliente negativo: {minimo}"


def test_clases_por_tipo_de_material(df_ci: pl.DataFrame) -> None:
    # ADR-017, punto 6. 311, 325, 343, 344 y 555 son el ciclo interno (ADR-018, ADR-019).
    retornable = set(df_ci.filter(RETORNABLE)["Bwart"].unique())
    carton = set(df_ci.filter(~RETORNABLE)["Bwart"].unique())
    assert retornable == {"311", "325", "343", "344", "555", "621", "622", "702"}, (
        f"Retornables: {sorted(retornable)}"
    )
    assert carton == {"101", "102", "261", "601"}, f"Cartón: {sorted(carton)}"


def test_lgort_por_bwart(df_ci: pl.DataFrame) -> None:
    # El 702 V va sin almacén: SAP lleva ese stock por cliente en MSKU.
    pares = set(df_ci.select("Bwart", "Lgort").unique().iter_rows())
    assert pares == {
        ("311", "VACI"),
        ("311", "LINE"),
        ("311", "LLEN"),
        ("311", "SUCI"),
        ("311", "REPA"),
        ("344", "SUCI"),
        ("325", "SUCI"),
        ("325", "REPA"),
        ("325", "SCRP"),
        ("343", "REPA"),
        ("555", "SCRP"),
        ("621", "LLEN"),
        ("622", "SUCI"),
        ("702", None),
        ("601", "EXPE"),
        ("101", "RM01"),
        ("102", "RM01"),
        ("261", "RM01"),
    }, f"Pares Bwart-Lgort: {sorted(pares, key=str)}"


def test_bwart_y_lgort_en_seeds(df_ci: pl.DataFrame) -> None:
    # Un código fuera del seed llega a los modelos sin estado ni evento.
    bwart = set(df_ci["Bwart"].unique()) - _llaves_seed("clases_movimiento.csv")
    lgort = set(df_ci["Lgort"].drop_nulls().unique()) - _llaves_seed("almacenes.csv")
    assert not bwart, f"Bwart fuera de clases_movimiento.csv: {sorted(bwart)}"
    assert not lgort, f"Lgort fuera de almacenes.csv: {sorted(lgort)}"
