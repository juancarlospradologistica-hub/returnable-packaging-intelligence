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
def con():
    if not (Path(LIMPIA).exists() and Path(RECORTE).exists()):
        pytest.skip("Sin data/rpi.duckdb y data/recorte.duckdb construidas.")
    # Cada base se adjunta con el nombre de su archivo: sus vistas lo llevan.
    c = duckdb.connect()
    for base in (LIMPIA, RECORTE):
        c.execute(f"ATTACH '{base}' AS {Path(base).stem} (READ_ONLY)")
    yield c
    c.close()


LA, RC = Path(LIMPIA).stem, Path(RECORTE).stem


@pytest.fixture(scope="module")
def corte(con) -> date:
    return con.sql(f"SELECT min(fecha) + 1 FROM {RC}.stg_stock_inicial").fetchone()[0]


def _iguales(con, sql: str) -> None:
    """Las mismas filas en las dos bases. sql lleva {db}; la diferencia la cuenta DuckDB."""
    limpia, corta = sql.format(db=LA), sql.format(db=RC)
    assert con.sql(f"SELECT count(*) FROM ({limpia})").fetchone()[0] > 0
    diferentes = con.sql(
        f"SELECT (SELECT count(*) FROM (({limpia}) EXCEPT ALL ({corta}))) "
        f"+ (SELECT count(*) FROM (({corta}) EXCEPT ALL ({limpia})))"
    ).fetchone()[0]
    assert diferentes == 0


def _iguales_con_decimales(con, sql: str) -> None:
    # Tablas chicas con decimales: el orden de las sumas mueve el último dígito.
    limpia, corta = (con.sql(sql.format(db=db)).pl() for db in (LA, RC))
    assert limpia.height > 0
    assert_frame_equal(
        corta.sort(corta.columns, nulls_last=True),
        limpia.sort(limpia.columns, nulls_last=True),
        check_exact=False,
        rel_tol=1e-9,
    )


def test_saldo_por_cuenta(con):
    _iguales(
        con,
        "SELECT planta, cliente, material, sum(delta_saldo) AS saldo "
        "FROM {db}.int_mov_cuenta GROUP BY ALL HAVING saldo <> 0",
    )


def test_stock_diario_desde_el_corte(con, corte):
    _iguales(
        con,
        "SELECT planta, material, estado, tipo_stock, fecha, saldo FROM {db}.int_stock_diario "
        f"WHERE fecha >= DATE '{corte}'",
    )


def test_ciclo_de_las_salidas_posteriores(con, corte):
    _iguales(
        con,
        "SELECT * EXCLUDE (salida_en_foto) FROM {db}.int_tramos_fifo "
        f"WHERE NOT salida_en_foto AND fecha_salida >= DATE '{corte}'",
    )


def test_flota_semanal_desde_el_corte(con, corte):
    _iguales(con, f"SELECT * FROM {{db}}.mart_flota_semanal WHERE semana >= DATE '{corte}'")


@pytest.mark.parametrize(
    "tabla", ["int_variabilidad_uso", "int_z_economico", "mart_necesidad_flota"]
)
def test_necesidad(con, tabla):
    _iguales_con_decimales(con, f"SELECT * FROM {{db}}.{tabla}")


def test_brecha_dentro_de_la_materialidad(con):
    sql = (
        "SELECT sum(usd_flete + usd_compra + usd_desechable), sum(usd_capital_ocioso) "
        "FROM {db}.mart_brecha_flota"
    )
    (brecha, ocioso), (brecha_corta, ocioso_corto) = (
        con.sql(sql.format(db=db)).fetchone() for db in (LA, RC)
    )
    assert abs(brecha_corta / brecha - 1) < MATERIALIDAD
    assert abs(ocioso_corto / ocioso - 1) < MATERIALIDAD
