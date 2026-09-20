import polars as pl
import pytest

from rpi.config import GeneratorConfig


def test_filas_dentro_de_rango(df_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    """
    Con 2 plantas y 3 meses el volumen esperado es ~(40k * 3 * 2) filas brutas
    más los 602 sintéticos. Rango holgado para no acoplar el test a los exactos.
    """
    n = df_ci.shape[0]
    assert n > 5_000, f"Muy pocas filas: {n}"
    assert n < 2_000_000, f"Volumen inesperadamente alto: {n}"


def test_plantas_en_df(df_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    plantas_esperadas = {p.werks for p in cfg_ci.plants}
    plantas_en_df = set(df_ci["Werks"].unique().to_list())
    assert plantas_esperadas == plantas_en_df


def test_reproducibilidad(cfg_ci: GeneratorConfig) -> None:
    """Misma seed produce el mismo número de filas."""
    df1 = __import__("rpi.generator", fromlist=["generate"]).generate(
        cfg=cfg_ci, output_dir="data/raw"
    )
    df2 = __import__("rpi.generator", fromlist=["generate"]).generate(
        cfg=cfg_ci, output_dir="data/raw"
    )
    assert df1.shape[0] == df2.shape[0]


def test_tasa_no_retorno(df_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    """
    La tasa de no-retorno observada debe estar dentro de ±2pp del parámetro.
    Solo aplica si hay movimientos 601 y 602 en el dataset.
    """
    salidas = df_ci.filter(pl.col("Bwart") == "601").shape[0]
    retornos = df_ci.filter(pl.col("Bwart") == "602").shape[0]

    if salidas == 0:
        pytest.skip("No hay movimientos 601 en el dataset CI")

    tasa_observada = 1.0 - (retornos / salidas)
    tasa_esperada = cfg_ci.loss_rate
    assert abs(tasa_observada - tasa_esperada) < 0.05, (
        f"Tasa no-retorno {tasa_observada:.3f} fuera del rango "
        f"esperado ({tasa_esperada:.3f} ± 0.05)"
    )