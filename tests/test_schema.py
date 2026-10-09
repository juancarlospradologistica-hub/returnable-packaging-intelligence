import duckdb
import polars as pl
import pytest

from rpi.db import ingest
from rpi.generator import INSTRUCCION, PLAN
from rpi.schema import (
    BWART_VALIDOS,
    InstruccionEmpaqueSchema,
    MB51Schema,
    PartesSchema,
    PlanProduccionSchema,
)


def test_schema_valida_df_ci(df_ci: pl.DataFrame) -> None:
    """El dataset generado en CI pasa el schema MB51 sin errores."""
    MB51Schema.validate(df_ci)


def test_columnas_core_presentes(df_ci: pl.DataFrame) -> None:
    columnas_core = [
        "Werks",
        "Lgort",
        "Matnr",
        "Maktx",
        "Bwart",
        "Mjahr",
        "Budat",
        "Cpudt",
        "Cputm",
        "Menge",
        "Meins",
        "Mblnr",
        "Zeile",
        "Lifnr",
        "Kunnr",
        "Xblnr",
    ]
    faltantes = [c for c in columnas_core if c not in df_ci.columns]
    assert not faltantes, f"Columnas faltantes: {faltantes}"


def test_bwart_solo_valores_validos(df_ci: pl.DataFrame) -> None:
    valores_en_df = set(df_ci["Bwart"].unique().to_list())
    invalidos = valores_en_df - set(BWART_VALIDOS)
    assert not invalidos, f"Bwart con valores fuera del enum: {invalidos}"


def test_menge_no_cero(df_ci: pl.DataFrame) -> None:
    ceros = df_ci.filter(pl.col("Menge") == 0).shape[0]
    assert ceros == 0, f"{ceros} filas con Menge == 0 (inválido en MB51)"


def test_ingest_crea_tablas_con_filas(raw_ci, tmp_path):
    """ingest() carga MB51, la foto de stock inicial y el plan con las columnas del contrato."""
    db_path = tmp_path / "test.duckdb"
    ingest(db_path=db_path, raw_dir=raw_ci)

    con = duckdb.connect(str(db_path))
    tablas = {}
    for tabla in (
        "raw_mb51",
        "raw_stock_inicial",
        "raw_partes",
        "raw_instruccion_empaque",
        "raw_plan_produccion",
    ):
        count = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        columnas = [r[0] for r in con.execute(f"DESCRIBE {tabla}").fetchall()]
        tablas[tabla] = (count, columnas)
    con.close()

    count, columnas = tablas["raw_mb51"]
    assert count > 0, "raw_mb51 está vacía después de ingest()"
    for col in ["Werks", "Matnr", "Bwart", "Budat", "Menge"]:
        assert col in columnas, f"Columna {col} no encontrada en raw_mb51"
    count, columnas = tablas["raw_stock_inicial"]
    assert count > 0, "raw_stock_inicial está vacía después de ingest()"
    assert columnas == ["Werks", "Lgort", "Matnr", "Kunnr", "Menge", "Fecha"]
    contrato = {
        "raw_partes": ["Werks", "Parte", "Kunnr", "Escenario"],
        "raw_instruccion_empaque": ["Werks", "Parte", "Matnr", "Piezas"],
        "raw_plan_produccion": ["Werks", "Parte", "Semana", "Piezas"],
    }
    for tabla, esperadas in contrato.items():
        count, columnas = tablas[tabla]
        assert count > 0, f"{tabla} está vacía después de ingest()"
        assert columnas == esperadas, f"{tabla}: {columnas}"


def test_ingest_sin_stock_inicial_falla(df_ci, tmp_path):
    df_ci.write_parquet(tmp_path / "mb51_ci.parquet")
    with pytest.raises(FileNotFoundError, match="stock_inicial"):
        ingest(db_path=tmp_path / "test.duckdb", raw_dir=tmp_path)


def test_ingest_sin_plan_falla(raw_ci, tmp_path):
    # Copia todo menos el plan: el error tiene que nombrar lo que falta.
    for archivo in raw_ci.glob("*.parquet"):
        if archivo.name != PLAN:
            (tmp_path / archivo.name).write_bytes(archivo.read_bytes())
    with pytest.raises(FileNotFoundError, match=PLAN) as error:
        ingest(db_path=tmp_path / "test.duckdb", raw_dir=tmp_path)
    assert INSTRUCCION not in str(error.value)


def test_plan_cumple_schemas(partes_ci, instruccion_ci, plan_ci):
    PartesSchema.validate(partes_ci)
    InstruccionEmpaqueSchema.validate(instruccion_ci)
    PlanProduccionSchema.validate(plan_ci)
