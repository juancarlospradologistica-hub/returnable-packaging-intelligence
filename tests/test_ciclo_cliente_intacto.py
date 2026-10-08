"""El ciclo con cliente (621, 622, 702) no cambia con Fase 3a (ADR-017, punto 10)."""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from rpi.huella import huella_dir

BASE = Path(__file__).parent / "huella"
RAW = Path(__file__).parents[1] / "data" / "raw"
# Si cambian estos flags hay que regenerar ci.json.
FLAGS_CI = ["--plants", "2", "--months", "6", "--seed", "42"]
# Con 18 meses y corte 2026-06-30 el primer Budat cae en enero de 2025.
INICIO_MAXIMO_COMPLETO = date(2025, 1, 31)


def _diferencias(esperada: dict, actual: dict) -> str:
    difs = []
    for planta in sorted(set(esperada) | set(actual)):
        e, a = esperada.get(planta), actual.get(planta)
        if e is None or a is None:
            difs.append(f"{planta}: {'sobra' if e is None else 'falta'}")
            continue
        if e == a:
            continue
        cambios = [
            f"{planta} {b}: {e['por_bwart'].get(b)} -> {a['por_bwart'].get(b)}"
            for b in sorted(set(e["por_bwart"]) | set(a["por_bwart"]))
            if e["por_bwart"].get(b) != a["por_bwart"].get(b)
        ]
        difs.extend(cambios or [f"{planta}: mismas filas y Menge, cambian otras columnas"])
    return "\n".join(difs)


def _es_dataset_completo(plantas: set[str]) -> bool:
    archivos = sorted(RAW.glob("mb51_*.parquet"))
    if {p.stem for p in archivos} != plantas:
        return False
    inicio = pl.scan_parquet(archivos).select(pl.col("Budat").cast(pl.Date).min()).collect().item()
    return inicio <= INICIO_MAXIMO_COMPLETO


def test_ciclo_cliente_intacto_ci(tmp_path):
    subprocess.run(
        [sys.executable, "-m", "rpi", *FLAGS_CI, "--output", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    esperada = json.loads((BASE / "ci.json").read_text(encoding="utf-8"))
    actual = huella_dir(tmp_path)
    assert actual == esperada, _diferencias(esperada, actual)


def test_ciclo_cliente_intacto_completo():
    esperada = json.loads((BASE / "completo.json").read_text(encoding="utf-8"))
    if not _es_dataset_completo(set(esperada)):
        pytest.skip("data/raw no es el dataset completo de 14 plantas y 18 meses")
    actual = huella_dir(RAW)
    assert actual == esperada, _diferencias(esperada, actual)
