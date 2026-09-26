import polars as pl
import pytest

from rpi.config import Country, GeneratorConfig, PlantConfig
from rpi.generator import generate


@pytest.fixture(scope="session")
def cfg_ci() -> GeneratorConfig:
    """
    2 plantas MX, 12 meses, volumen bajo. 12 meses dan tres conciliaciones
    con salidas de más de 120 días, suficientes para medir merma.
    """
    plants = [
        PlantConfig(
            werks=f"PLNT_MX{i:02d}",
            country=Country.MX,
            monthly_movements_min=3_000,
            monthly_movements_max=5_000,
        )
        for i in (1, 2)
    ]
    return GeneratorConfig(
        plants=plants,
        horizon_months=12,
        global_matnr_pool=100,
        random_seed=42,
    )


@pytest.fixture(scope="session")
def df_ci(cfg_ci: GeneratorConfig, tmp_path_factory: pytest.TempPathFactory) -> pl.DataFrame:
    # tmp_path: correr pytest en local no debe pisar data/raw.
    return generate(cfg=cfg_ci, output_dir=str(tmp_path_factory.mktemp("raw"))).collect()
