from pathlib import Path

import polars as pl
import pytest

from rpi.config import Country, GeneratorConfig, PlantConfig
from rpi.generator import generate

PARQUET_PATH = Path("data/raw/mb51_synthetic_v1.parquet")


@pytest.fixture(scope="session")
def cfg_ci() -> GeneratorConfig:
    """Config mínima para CI: 2 plantas MX, 3 meses, seed fija."""
    return GeneratorConfig(
        plants=[
            PlantConfig(werks="PLNT_MX01", country=Country.MX),
            PlantConfig(werks="PLNT_MX02", country=Country.MX),
        ],
        horizon_months=3,
        global_matnr_pool=100,
        random_seed=42,
    )


@pytest.fixture(scope="session")
def df_ci(cfg_ci: GeneratorConfig) -> pl.DataFrame:
    """Dataset mínimo generado en memoria para todos los tests."""
    return generate(cfg=cfg_ci, output_dir="data/raw")


@pytest.fixture(scope="session")
def df_parquet() -> pl.DataFrame | None:
    """Carga el Parquet completo si existe; None si no."""
    if PARQUET_PATH.exists():
        return pl.read_parquet(PARQUET_PATH)
    return None