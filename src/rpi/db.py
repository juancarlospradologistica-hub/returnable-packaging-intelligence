"""Ingesta a DuckDB: MB51, foto de stock inicial, plan de producción y maestro de materiales."""

from pathlib import Path

import duckdb

from rpi.defectos import BITACORA
from rpi.generator import INSTRUCCION, MAESTRO, PARTES, PLAN, STOCK_INICIAL

RAW_DIR = Path("data/raw")
DB_PATH = Path("data/rpi.duckdb")


def ingest(db_path: Path = DB_PATH, raw_dir: Path = RAW_DIR) -> None:
    raw_dir = Path(raw_dir)
    tablas = {
        "raw_mb51": raw_dir / "mb51_*.parquet",
        "raw_stock_inicial": raw_dir / STOCK_INICIAL,
        "raw_partes": raw_dir / PARTES,
        "raw_instruccion_empaque": raw_dir / INSTRUCCION,
        "raw_plan_produccion": raw_dir / PLAN,
        "raw_maestro_materiales": raw_dir / MAESTRO,
    }
    # Sin foto inicial no hay stock por almacén, sin plan no hay necesidad y
    # sin maestro no hay tipo ni costo; mejor fallar aquí que en dbt.
    faltan = [p.name for t, p in tablas.items() if t != "raw_mb51" and not p.exists()]
    if faltan:
        raise FileNotFoundError(f"Faltan {faltan} en {raw_dir}: regenerar con python -m rpi")

    con = duckdb.connect(str(db_path))
    for tabla, archivo in tablas.items():
        con.execute(f"CREATE OR REPLACE TABLE {tabla} AS SELECT * FROM read_parquet('{archivo}')")
    # La bitácora solo existe si el generador inyectó defectos; un extracto real
    # no la trae. Sin archivo se borra la de una corrida anterior.
    bitacora = raw_dir / BITACORA
    if bitacora.exists():
        con.execute(
            "CREATE OR REPLACE TABLE raw_bitacora_defectos AS "
            f"SELECT * FROM read_parquet('{bitacora}')"
        )
        tablas["raw_bitacora_defectos"] = bitacora
    else:
        con.execute("DROP TABLE IF EXISTS raw_bitacora_defectos")

    for tabla in tablas:
        count = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        print(f"{tabla}: {count:,} filas cargadas")
    con.close()


if __name__ == "__main__":
    ingest()
