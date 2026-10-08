"""
Las clases de movimiento válidas estan en tres lugares: BWART_VALIDOS en el
schema, accepted_values del source y el seed clases_movimiento. Si se separan,
un Bwart nuevo pasa en uno y truena en otro, o peor, pasa en los tres sin
que los modelos de Fase 3 sepan qué evento es.
"""

from pathlib import Path

import polars as pl
import yaml

from rpi.schema import BWART_VALIDOS

RAIZ = Path(__file__).resolve().parents[1]
COLUMNA_SEED = "bwart"


def _bwart_del_source() -> set[str]:
    sources = yaml.safe_load((RAIZ / "models/staging/sources.yml").read_text(encoding="utf-8"))
    for source in sources["sources"]:
        for tabla in source["tables"]:
            for columna in tabla.get("columns", []):
                if columna["name"] != "bwart":
                    continue
                # dbt acepta tests y data_tests; el repo usa tests.
                for test in columna.get("tests", []) + columna.get("data_tests", []):
                    if isinstance(test, dict) and "accepted_values" in test:
                        valores = test["accepted_values"]["arguments"]["values"]
                        return {str(v) for v in valores}
    raise AssertionError("sources.yml no tiene accepted_values en bwart")


def _bwart_del_seed() -> set[str]:
    seed = pl.read_csv(RAIZ / "seeds/clases_movimiento.csv", infer_schema=False)
    return set(seed[COLUMNA_SEED].to_list())


def _diferencia(a: set[str], b: set[str], nombre_b: str) -> str:
    return f"solo en schema: {sorted(a - b)}; solo en {nombre_b}: {sorted(b - a)}"


def test_bwart_schema_igual_a_source():
    schema, source = set(BWART_VALIDOS), _bwart_del_source()
    assert schema == source, _diferencia(schema, source, "sources.yml")


def test_bwart_schema_igual_a_seed():
    schema, seed = set(BWART_VALIDOS), _bwart_del_seed()
    assert schema == seed, _diferencia(schema, seed, "clases_movimiento.csv")