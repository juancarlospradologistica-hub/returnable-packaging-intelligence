"""Ingesta de archivos Parquet MB51 y de la foto de stock inicial a DuckDB."""

from pathlib import Path

import duckdb

from rpi.generator import STOCK_INICIAL

RAW_DIR = Path("data/raw")
DB_PATH = Path("data/rpi.duckdb")


def ingest(db_path: Path = DB_PATH, raw_dir: Path = RAW_DIR) -> None:
    raw_dir = Path(raw_dir)
    # Sin foto inicial no hay stock por almacén; mejor fallar aquí que en dbt.
    stock = raw_dir / STOCK_INICIAL
    if not stock.exists():
        raise FileNotFoundError(f"Falta {stock}: regenerar con python -m rpi")

    con = duckdb.connect(str(db_path))
    con.execute(f"""
        CREATE OR REPLACE TABLE raw_mb51 AS
        SELECT * FROM read_parquet('{raw_dir / "mb51_*.parquet"}')
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE raw_stock_inicial AS
        SELECT * FROM read_parquet('{stock}')
    """)

    for tabla in ("raw_mb51", "raw_stock_inicial"):
        count = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        print(f"{tabla}: {count:,} filas cargadas")
    con.close()


if __name__ == "__main__":
    ingest()
