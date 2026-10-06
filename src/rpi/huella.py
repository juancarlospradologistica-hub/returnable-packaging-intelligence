"""Huella de las filas del ciclo con cliente: 621, 622 y 702.

Fase 3a agrega movimientos internos sin tocar estas filas (ADR-017, punto 10).
Uso sha256 sobre CSV ordenado: hash_rows de Polars no es estable entre versiones.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import polars as pl

BWART_CICLO = ["621", "622", "702"]
ORDEN = ["Werks", "Bwart", "Matnr", "Kunnr", "Budat", "Cpudt", "Menge", "Costo_cts"]


def filas_ciclo(path: Path) -> pl.DataFrame:
    return (
        pl.scan_parquet(path)
        .filter(pl.col("Bwart").cast(pl.Utf8).is_in(BWART_CICLO))
        .select(
            pl.col("Werks").cast(pl.Utf8),
            pl.col("Bwart").cast(pl.Utf8),
            pl.col("Matnr").cast(pl.Utf8),
            pl.col("Kunnr").cast(pl.Utf8),
            pl.col("Budat").cast(pl.Date),
            pl.col("Cpudt").cast(pl.Date),
            pl.col("Menge").cast(pl.Int64, strict=True),
            (pl.col("Costo_usd") * 100).round(0).cast(pl.Int64).alias("Costo_cts"),
        )
        .sort(ORDEN)
        .collect()
    )


def huella_archivo(path: Path) -> dict:
    df = filas_ciclo(path)
    csv = df.write_csv(date_format="%Y-%m-%d", null_value="")
    por_bwart = (
        df.group_by("Bwart")
        .agg(pl.len().alias("filas"), pl.col("Menge").sum().alias("menge"))
        .sort("Bwart")
    )
    return {
        "filas": df.height,
        "sha256": hashlib.sha256(csv.encode("utf-8")).hexdigest(),
        "por_bwart": {
            r["Bwart"]: {"filas": r["filas"], "menge": r["menge"]}
            for r in por_bwart.iter_rows(named=True)
        },
    }


def huella_dir(raw_dir: Path) -> dict[str, dict[str, int | str]]:
    archivos = sorted(Path(raw_dir).glob("mb51_*.parquet"))
    if not archivos:
        raise FileNotFoundError(f"Sin mb51_*.parquet en {raw_dir}")
    return {p.stem: huella_archivo(p) for p in archivos}


if __name__ == "__main__":
    raw_dir, destino = Path(sys.argv[1]), Path(sys.argv[2])
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(huella_dir(raw_dir), indent=2) + "\n", encoding="utf-8")
    print(f"{destino}: {len(json.loads(destino.read_text(encoding='utf-8')))} plantas")
