"""
Ventana recortada (ADR-036). El generador arranca con los clientes vacíos y un
extracto real no: el primer día ya hay contenedores afuera. rpi.recorte corta
el limpio en una fecha y arma la foto con lo que pasó antes.

Sobre la ventana recortada, todo lo que no depende del largo de la historia
tiene que salir igual que sobre la completa: saldo por cuenta, stock diario,
ciclo de las salidas posteriores al corte, flota semanal, variabilidad, z y
necesidad. La tasa de merma y la curva de supervivencia se estiman con menos
historia; la brecha que mueven tiene que quedar dentro de la materialidad.

Los tests de integración corren con data/rpi.duckdb y data/recorte.duckdb
construidas (CI las arma); sin ellas se saltan.
"""

import os
from datetime import date, timedelta
from pathlib import Path

import duckdb
import polars as pl
import pytest
from polars.testing import assert_frame_equal

from rpi.db import fallas_de_schema
from rpi.generator import STOCK_INICIAL
from rpi.recorte import main, recorta

LIMPIA = "data/rpi.duckdb"
RECORTE = os.environ.get("RPI_DB_RECORTE", "data/recorte.duckdb")
# Materialidad de ADR-031: 1% de una cifra publicada.
MATERIALIDAD = 0.01


@pytest.fixture(scope="module")
def desde(df_ci: pl.DataFrame) -> date:
    # Trece semanas después del arranque, en lunes.
    ini = df_ci["Budat"].min()
    return ini + timedelta(days=91 - ini.weekday())


@pytest.fixture(scope="module")
def recortado(raw_ci: Path, desde: date, tmp_path_factory) -> Path:
    salida = tmp_path_factory.mktemp("recorte")
    recorta(raw_ci, salida, desde)
    return salida


def _saldo(foto: pl.DataFrame, mb51: pl.DataFrame) -> pl.DataFrame:
    """Stock por almacén y por cuenta V al cierre: la foto más todo lo que se movió."""
    almacen = mb51.filter(~pl.col("Lgort").is_in(["RM01", "EXPE"])).select(
        "Werks", "Lgort", "Matnr", pl.lit(None, dtype=pl.String).alias("Kunnr"), "Menge"
    )
    cliente = mb51.filter(pl.col("Bwart").is_in(["621", "622", "702"])).select(
        "Werks",
        pl.lit(None, dtype=pl.String).alias("Lgort"),
        "Matnr",
        "Kunnr",
        pl.when(pl.col("Bwart") == "621")
        .then(pl.col("Menge").abs())
        .otherwise(-pl.col("Menge").abs())
        .alias("Menge"),
    )
    llave = ["Werks", "Lgort", "Matnr", "Kunnr"]
    return (
        pl.concat(
            [foto.select(*llave, "Menge"), almacen.filter(pl.col("Lgort").is_not_null()), cliente]
        )
        .group_by(llave)
        .agg(pl.col("Menge").sum())
        .filter(pl.col("Menge") != 0)
        .sort(llave, nulls_last=True)
    )


def test_foto_mas_lo_que_sigue_da_el_mismo_cierre(raw_ci, recortado, df_ci):
    completo = _saldo(pl.read_parquet(raw_ci / STOCK_INICIAL), df_ci)
    corto = _saldo(
        pl.read_parquet(recortado / STOCK_INICIAL),
        pl.scan_parquet(recortado / "mb51_*.parquet").collect(),
    )
    assert corto.equals(completo)


def test_la_foto_trae_stock_en_cliente(recortado):
    foto = pl.read_parquet(recortado / STOCK_INICIAL)
    en_cliente = foto.filter(pl.col("Kunnr").is_not_null())
    assert en_cliente.height > 0
    assert en_cliente["Lgort"].is_null().all()


def test_mb51_desde_el_corte(raw_ci, recortado, desde):
    originales = sorted(f.name for f in raw_ci.glob("mb51_*.parquet"))
    assert sorted(f.name for f in recortado.glob("mb51_*.parquet")) == originales
    for nombre in originales:
        esperado = pl.read_parquet(raw_ci / nombre).filter(pl.col("Budat") >= desde)
        assert pl.read_parquet(recortado / nombre).equals(esperado), nombre


def test_foto_cumple_el_contrato(recortado, desde):
    foto = pl.read_parquet(recortado / STOCK_INICIAL)
    assert fallas_de_schema("raw_stock_inicial", recortado / STOCK_INICIAL).is_empty()
    assert foto["Fecha"].unique().to_list() == [desde - timedelta(days=1)]
    assert (foto["Menge"] > 0).all()


def test_desde_fuera_de_la_ventana(raw_ci, df_ci, tmp_path):
    with pytest.raises(ValueError, match="fuera de la ventana"):
        recorta(raw_ci, tmp_path, df_ci["Budat"].min())


def test_salida_igual_al_origen(raw_ci, desde):
    with pytest.raises(ValueError, match="mismo directorio"):
        recorta(raw_ci, raw_ci, desde)


def test_cli(raw_ci, desde, tmp_path, capsys):
    main([desde.isoformat(), "--origen", str(raw_ci), "--salida", str(tmp_path)])
    assert "contenedores en cliente" in capsys.readouterr().out
    assert (tmp_path / STOCK_INICIAL).exists()


# --- Integración: el pipeline sobre las dos ventanas ---


@pytest.fixture(scope="module")
def bases():
    if not (Path(LIMPIA).exists() and Path(RECORTE).exists()):
        pytest.skip("Sin data/rpi.duckdb y data/recorte.duckdb construidas.")
    limpia = duckdb.connect(LIMPIA, read_only=True)
    corta = duckdb.connect(RECORTE, read_only=True)
    yield limpia, corta
    limpia.close()
    corta.close()


@pytest.fixture(scope="module")
def corte(bases) -> date:
    return bases[1].sql("SELECT min(fecha) + 1 FROM stg_stock_inicial").fetchone()[0]


def _iguales(bases, sql: str) -> None:
    limpia, corta = (c.sql(sql).pl() for c in bases)
    assert limpia.height > 0
    assert_frame_equal(
        corta.sort(corta.columns, nulls_last=True),
        limpia.sort(limpia.columns, nulls_last=True),
        check_exact=False,
        rel_tol=1e-9,
    )


def test_saldo_por_cuenta(bases):
    _iguales(
        bases,
        "SELECT planta, cliente, material, sum(delta_saldo) AS saldo "
        "FROM int_mov_cuenta GROUP BY ALL HAVING saldo <> 0",
    )


def test_stock_diario_desde_el_corte(bases, corte):
    _iguales(
        bases,
        "SELECT planta, material, estado, tipo_stock, fecha, saldo FROM int_stock_diario "
        f"WHERE fecha >= DATE '{corte}'",
    )


def test_ciclo_de_las_salidas_posteriores(bases, corte):
    _iguales(
        bases,
        "SELECT * EXCLUDE (salida_en_foto) FROM int_tramos_fifo "
        f"WHERE NOT salida_en_foto AND fecha_salida >= DATE '{corte}'",
    )


def test_flota_semanal_desde_el_corte(bases, corte):
    _iguales(bases, f"SELECT * FROM mart_flota_semanal WHERE semana >= DATE '{corte}'")


@pytest.mark.parametrize(
    "tabla", ["int_variabilidad_uso", "int_z_economico", "mart_necesidad_flota"]
)
def test_necesidad(bases, tabla):
    _iguales(bases, f"SELECT * FROM {tabla}")


def test_brecha_dentro_de_la_materialidad(bases):
    sql = (
        "SELECT sum(usd_flete + usd_compra + usd_desechable), sum(usd_capital_ocioso) "
        "FROM mart_brecha_flota"
    )
    (brecha, ocioso), (brecha_corta, ocioso_corto) = (c.sql(sql).fetchone() for c in bases)
    assert abs(brecha_corta / brecha - 1) < MATERIALIDAD
    assert abs(ocioso_corto / ocioso - 1) < MATERIALIDAD
