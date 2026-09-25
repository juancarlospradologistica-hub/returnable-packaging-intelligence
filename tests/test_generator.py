from datetime import timedelta

import polars as pl
import pytest

from rpi.config import GeneratorConfig
from rpi.generator import generate, reconciliation_dates


def test_filas_dentro_de_rango(df_ci: pl.DataFrame) -> None:
    n = df_ci.height
    assert 50_000 < n < 300_000, f"Volumen fuera de rango: {n}"


def test_plantas_en_df(df_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    assert set(df_ci["Werks"].unique()) == {p.werks for p in cfg_ci.plants}


def test_reproducibilidad(cfg_ci: GeneratorConfig, tmp_path) -> None:
    """Misma seed, mismo dataset fila por fila."""
    df1 = generate(cfg=cfg_ci, output_dir=str(tmp_path / "a")).collect()
    df2 = generate(cfg=cfg_ci, output_dir=str(tmp_path / "b")).collect()
    assert df1.equals(df2)


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


def test_traslados_suman_cero(df_ci: pl.DataFrame) -> None:
    no_cero = (
        df_ci.filter(pl.col("Bwart").is_in(["309", "311", "411"]))
        .group_by("Mblnr", "Mjahr")
        .agg(pl.col("Menge").sum())
        .filter(pl.col("Menge") != 0)
        .height
    )
    assert no_cero == 0, f"{no_cero} documentos de traslado que no suman cero"


def test_carton_no_entra_al_ciclo(df_ci: pl.DataFrame) -> None:
    ciclo = df_ci.filter(
        pl.col("Matnr").str.starts_with("CTN") & pl.col("Bwart").is_in(["621", "622", "702"])
    ).height
    assert ciclo == 0


def test_rack_dedicado_a_un_cliente(df_ci: pl.DataFrame) -> None:
    max_clientes = (
        df_ci.filter((pl.col("Bwart") == "621") & pl.col("Matnr").str.starts_with("RCK"))
        .group_by("Werks", "Matnr")
        .agg(pl.col("Kunnr").n_unique())
        ["Kunnr"]
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
    salidas = -df_ci.filter((pl.col("Bwart") == "621") & (pl.col("Budat") <= limite))[
        "Menge"
    ].sum()
    perdidos = -df_ci.filter(pl.col("Bwart") == "702")["Menge"].sum()
    if salidas == 0:
        pytest.skip("Sin salidas con antigüedad suficiente")

    tasa = perdidos / salidas
    assert cfg_ci.loss.rate_low * 0.5 <= tasa <= cfg_ci.loss.rate_high, (
        f"Merma observada {tasa:.4f} fuera de "
        f"[{cfg_ci.loss.rate_low * 0.5:.4f}, {cfg_ci.loss.rate_high:.4f}]"
    )
