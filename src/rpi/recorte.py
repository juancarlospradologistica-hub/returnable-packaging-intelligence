"""
Ventana recortada (ADR-036): el dataset del generador desde una fecha, con la
foto de stock armada con lo que pasó antes. Así se ve un extracto real: el
primer día ya hay contenedores en cliente.

El generador arranca con los clientes vacíos. Un MB51 real no: los 622 de los
primeros meses recogen contenedores que salieron antes de la ventana. Con la
foto bien leída, el pipeline sobre la ventana recortada tiene que dar lo mismo
que sobre la completa en todo lo que comparten; tests/test_recorte.py lo exige.

Solo para el dataset limpio: la bitácora de defectos no se recorta.

Uso:
    uv run python -m rpi.recorte 2025-04-07 --salida data/recorte
"""

from __future__ import annotations

import argparse
import shutil
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from rpi.generator import INSTRUCCION, MAESTRO, PARTES, PLAN, STOCK_INICIAL

SEEDS = Path("seeds")
COPIADOS = (MAESTRO, PARTES, INSTRUCCION, PLAN)


def _seed(nombre: str, seeds: Path) -> pl.DataFrame:
    return pl.read_csv(seeds / f"{nombre}.csv", infer_schema=False)


def foto_al(origen: Path, desde: date, seeds: Path = SEEDS) -> pl.DataFrame:
    """Foto al cierre del día anterior a desde: la original más lo que se movió antes."""
    almacenes = _seed("almacenes", seeds).filter(pl.col("estado") != "fuera_ciclo")["lgort"]
    clases = _seed("clases_movimiento", seeds)
    salida = clases.filter(pl.col("evento") == "salida_cliente")["bwart"]
    cuenta = clases.filter(
        pl.col("evento").is_in(["salida_cliente", "recogida_cliente", "faltante_cliente"])
    )["bwart"]

    foto = pl.read_parquet(origen / STOCK_INICIAL)
    antes = pl.scan_parquet(origen / "mb51_*.parquet").filter(pl.col("Budat") < desde)
    llave = ["Werks", "Lgort", "Matnr", "Kunnr"]
    # Mismos almacenes que la foto del generador: los del ciclo, sin el cartón.
    en_almacen = antes.filter(pl.col("Lgort").is_in(almacenes.implode())).select(
        "Werks", "Lgort", "Matnr", pl.lit(None, dtype=pl.String).alias("Kunnr"), "Menge"
    )
    # Stock V: la salida sube la cuenta del cliente, la recogida y el faltante la bajan.
    en_cliente = antes.filter(pl.col("Bwart").is_in(cuenta.implode())).select(
        "Werks",
        pl.lit(None, dtype=pl.String).alias("Lgort"),
        "Matnr",
        "Kunnr",
        pl.when(pl.col("Bwart").is_in(salida.implode()))
        .then(pl.col("Menge").abs())
        .otherwise(-pl.col("Menge").abs())
        .alias("Menge"),
    )
    return (
        pl.concat([foto.lazy().select(*llave, "Menge"), en_almacen, en_cliente])
        .group_by(llave)
        .agg(pl.col("Menge").sum())
        .filter(pl.col("Menge") != 0)
        .with_columns(pl.lit(desde - timedelta(days=1)).alias("Fecha"))
        .sort(llave, nulls_last=True)
        .collect()
    )


def recorta(origen: Path, salida: Path, desde: date, seeds: Path = SEEDS) -> None:
    budat = pl.scan_parquet(origen / "mb51_*.parquet").select(
        pl.col("Budat").min().alias("ini"), pl.col("Budat").max().alias("fin")
    )
    ini, fin = budat.collect().row(0)
    if not ini < desde <= fin:
        raise ValueError(f"desde {desde} fuera de la ventana del dataset ({ini} a {fin})")
    if origen.resolve() == salida.resolve():
        raise ValueError("La salida no puede ser el mismo directorio que el origen")

    salida.mkdir(parents=True, exist_ok=True)
    for viejo in salida.glob("*.parquet"):
        viejo.unlink()
    foto_al(origen, desde, seeds).write_parquet(salida / STOCK_INICIAL)
    for nombre in COPIADOS:
        shutil.copy(origen / nombre, salida / nombre)
    for f in sorted(origen.glob("mb51_*.parquet")):
        pl.scan_parquet(f).filter(pl.col("Budat") >= desde).sink_parquet(salida / f.name)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m rpi.recorte", description=__doc__.split("\n")[1])
    p.add_argument("desde", type=date.fromisoformat, help="Primer día de la ventana recortada.")
    p.add_argument("--origen", type=Path, default=Path("data/raw"))
    p.add_argument("--salida", type=Path, default=Path("data/recorte"))
    a = p.parse_args(argv)
    recorta(a.origen, a.salida, a.desde)
    foto = pl.read_parquet(a.salida / STOCK_INICIAL)
    en_cliente = foto.filter(pl.col("Kunnr").is_not_null())
    print(
        f"Ventana desde {a.desde} en {a.salida}: foto con {foto.height:,} filas, "
        f"{en_cliente['Menge'].sum():,} contenedores en cliente"
    )


if __name__ == "__main__":
    main()
