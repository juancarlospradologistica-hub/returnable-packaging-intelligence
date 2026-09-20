import duckdb
import polars as pl

from rpi.db import ingest
from rpi.schema import MB51Schema, BWART_VALIDOS


def test_schema_valida_df_ci(df_ci: pl.DataFrame) -> None:
    """El dataset generado en CI pasa el schema MB51 sin errores."""
    MB51Schema.validate(df_ci)


def test_columnas_core_presentes(df_ci: pl.DataFrame) -> None:
    columnas_core = [
        "Werks", "Lgort", "Matnr", "Maktx", "Bwart",
        "Mjahr", "Budat", "Cpudt", "Cputm",
        "Menge", "Meins", "Mblnr", "Zeile",
        "Lifnr", "Kunnr", "Xblnr",
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


def test_ingest_crea_tabla_con_filas(df_ci, tmp_path):
    """ingest() crea raw_mb51 en DuckDB con filas y columnas esperadas."""
    parquet_path = tmp_path / "mb51_ci.parquet"
    df_ci.write_parquet(str(parquet_path))

    db_path = tmp_path / "test.duckdb"
    ingest(db_path=db_path, raw_dir=tmp_path)

    con = duckdb.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM raw_mb51").fetchone()[0]
    columnas = [r[0] for r in con.execute("DESCRIBE raw_mb51").fetchall()]
    con.close()

    assert count > 0, "raw_mb51 está vacía después de ingest()"
    for col in ["Werks", "Matnr", "Bwart", "Budat", "Menge"]:
        assert col in columnas, f"Columna {col} no encontrada en raw_mb51"