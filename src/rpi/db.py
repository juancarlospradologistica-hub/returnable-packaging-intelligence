"""
Ingesta a DuckDB: MB51, foto de stock inicial, plan de producción y maestro de
materiales.

Cada tabla pasa por su schema Pandera en modo lazy antes de cargarse. Las
fallas de estructura no detienen la ingesta: van a raw_errores_schema y la
regla error_de_schema de dbt las reporta (ADR-028, punto 9).

MB51, foto inicial y maestro son obligatorios: sin ellos no hay stock, tipo ni
costo. Partes, instrucción y plan son opcionales, porque un extracto real
puede no traer plan de producción: si falta un archivo, su tabla se crea vacía
con las columnas del contrato y la necesidad de flota sale sin filas (ADR-037).
"""

import os
from pathlib import Path

import duckdb
import pandera.polars as pa
import polars as pl
from pandera.errors import SchemaErrors

from rpi.defectos import BITACORA
from rpi.generator import INSTRUCCION, MAESTRO, PARTES, PLAN, STOCK_INICIAL
from rpi.schema import (
    InstruccionEmpaqueSchema,
    MaestroMaterialesSchema,
    MB51Schema,
    PartesSchema,
    PlanProduccionSchema,
    StockInicialSchema,
)

RAW_DIR = Path("data/raw")
# RPI_DB permite una base aparte para la corrida con defectos; profiles.yml
# lee la misma variable.
DB_PATH = Path(os.environ.get("RPI_DB", "data/rpi.duckdb"))

ESQUEMAS: dict[str, type[pa.DataFrameModel]] = {
    "raw_mb51": MB51Schema,
    "raw_stock_inicial": StockInicialSchema,
    "raw_partes": PartesSchema,
    "raw_instruccion_empaque": InstruccionEmpaqueSchema,
    "raw_plan_produccion": PlanProduccionSchema,
    "raw_maestro_materiales": MaestroMaterialesSchema,
}

ERRORES = {
    "tabla": pl.String,
    "archivo": pl.String,
    "columna": pl.String,
    "check": pl.String,
    "valor": pl.String,
    "fila": pl.Int64,
}


def fallas_de_schema(tabla: str, archivo: Path) -> pl.DataFrame:
    """Fallas de Pandera de un archivo, una fila por falla. Vacío si cumple."""
    try:
        ESQUEMAS[tabla].validate(pl.read_parquet(archivo), lazy=True)
    except SchemaErrors as e:
        return e.failure_cases.select(
            pl.lit(tabla).alias("tabla"),
            pl.lit(archivo.name).alias("archivo"),
            pl.col("column").cast(pl.String).alias("columna"),
            pl.col("check").cast(pl.String),
            pl.col("failure_case").cast(pl.String).alias("valor"),
            pl.col("index").cast(pl.Int64).alias("fila"),
        )
    return pl.DataFrame(schema=ERRORES)


def carga(con: duckdb.DuckDBPyConnection, tabla: str, archivo: Path) -> None:
    con.execute(f"CREATE OR REPLACE TABLE {tabla} AS SELECT * FROM read_parquet('{archivo}')")


OPCIONALES = ("raw_partes", "raw_instruccion_empaque", "raw_plan_produccion")


def vacia(tabla: str) -> pl.DataFrame:
    """Tabla sin filas con las columnas y tipos del contrato."""
    columnas = ESQUEMAS[tabla].to_schema().columns
    return pl.DataFrame(schema={nombre: c.dtype.type for nombre, c in columnas.items()})


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
    # Sin MB51, foto o maestro no hay stock, tipo ni costo: mejor fallar aquí
    # que en dbt.
    if not any(raw_dir.glob(tablas["raw_mb51"].name)):
        raise FileNotFoundError(f"No hay mb51_*.parquet en {raw_dir}")
    faltan = [
        p.name
        for t, p in tablas.items()
        if t not in OPCIONALES and t != "raw_mb51" and not p.exists()
    ]
    if faltan:
        raise FileNotFoundError(f"Faltan {faltan} en {raw_dir}: regenerar con python -m rpi")
    sin_archivo = [t for t in OPCIONALES if not tablas[t].exists()]

    # MB51 se valida por planta: el completo no cabe junto en memoria.
    errores = pl.concat(
        [
            fallas_de_schema(tabla, archivo)
            for tabla, patron in tablas.items()
            for archivo in sorted(raw_dir.glob(patron.name))
        ]
    )

    con = duckdb.connect(str(db_path))
    for tabla, archivo in tablas.items():
        if tabla in sin_archivo:
            con.register("_vacia", vacia(tabla).to_arrow())
            con.execute(f"CREATE OR REPLACE TABLE {tabla} AS SELECT * FROM _vacia")
            con.unregister("_vacia")
        else:
            carga(con, tabla, archivo)
    con.register("_errores", errores.to_arrow())
    con.execute("CREATE OR REPLACE TABLE raw_errores_schema AS SELECT * FROM _errores")
    con.unregister("_errores")
    tablas["raw_errores_schema"] = Path("")
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
        nota = ", sin archivo" if tabla in sin_archivo else ""
        print(f"{tabla}: {count:,} filas cargadas{nota}")
    con.close()


if __name__ == "__main__":
    ingest()
