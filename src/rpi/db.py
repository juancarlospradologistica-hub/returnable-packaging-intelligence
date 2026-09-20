"""Ingesta de archivos Parquet MB51 a DuckDB."""

from pathlib import Path

import duckdb

RAW_DIR = Path("data/raw")
DB_PATH = Path("data/rpi.duckdb")


def ingest(db_path: Path = DB_PATH, raw_dir: Path = RAW_DIR) -> None:
    con = duckdb.connect(str(db_path))

    parquet_glob = str(raw_dir / "mb51_*.parquet")
    con.execute(f"""
        CREATE OR REPLACE TABLE raw_mb51 AS
        SELECT * FROM read_parquet('{parquet_glob}')
    """)

    count = con.execute("SELECT COUNT(*) FROM raw_mb51").fetchone()[0]
    print(f"raw_mb51: {count:,} filas cargadas")
    con.close()


if __name__ == "__main__":
    ingest()