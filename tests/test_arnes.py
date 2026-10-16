"""
Arnés de impacto (ADR-031, punto 3).

Inyectar sobre el limpio ya escrito tiene que dar lo mismo que generar con
--defectos: si no, el arnés mide defectos distintos a los que prueba CI. La
medición versionada tiene que salir del dataset que publica el README.
"""

import shutil
from pathlib import Path

import duckdb
import polars as pl
import pytest

from rpi import calidad
from rpi.calidad import CIFRAS, ETAPAS, SALIDA, con_regla, inyecta_limpio, seleccion
from rpi.config import CIEGOS, DEFECTOS, GeneratorConfig
from rpi.defectos import BITACORA
from rpi.generator import generate

RAIZ = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("activos", [DEFECTOS, CIEGOS], ids=["todos", "ciegos"])
def test_inyectar_sobre_el_limpio_es_generar_con_defectos(cfg_ci, raw_ci, tmp_path, activos):
    datos = cfg_ci.model_dump()
    datos["defectos"]["activos"] = list(activos)
    cfg = GeneratorConfig.model_validate(datos)
    sucio = tmp_path / "sucio"
    generate(cfg=cfg, output_dir=str(sucio))
    # El limpio con el MB51 barajado: lo que se inyecta no puede depender del
    # orden en que quedó escrito el archivo.
    limpio = tmp_path / "limpio"
    shutil.copytree(raw_ci, limpio)
    for f in limpio.glob("mb51_*.parquet"):
        pl.read_parquet(f).sample(fraction=1.0, shuffle=True, seed=7).write_parquet(f)
    archivos, bitacora = inyecta_limpio(limpio, tmp_path / "arnes", cfg)

    escritos = {Path(a).name for a in archivos.values()}
    assert "mb51_*.parquet" in escritos
    for f in sorted(sucio.glob("*.parquet")):
        if f.name == BITACORA:
            continue
        # Lo que el arnés no reescribe tiene que ser igual al limpio.
        mb51 = f.name.startswith("mb51_")
        cambiado = (mb51 and "mb51_*.parquet" in escritos) or f.name in escritos
        actual = pl.read_parquet((tmp_path / "arnes" if cambiado else raw_ci) / f.name)
        assert actual.equals(pl.read_parquet(f)), f.name

    # Mismas filas; el orden dentro de un defecto puede variar.
    esperado = pl.read_parquet(sucio / BITACORA)
    assert bitacora.sort(bitacora.columns, nulls_last=True).equals(
        esperado.sort(esperado.columns, nulls_last=True)
    )


@pytest.mark.parametrize(
    ("argv", "esperado"),
    [
        (["--defectos", "todos"], list(DEFECTOS)),
        (["--defectos", "ciegos"], list(CIEGOS)),
        (["--defectos", "d07,B04"], ["D07", "B04"]),
        (["--defectos", "todos,ciegos"], [*DEFECTOS, *CIEGOS]),
        ([], [*DEFECTOS, *CIEGOS]),
    ],
)
def test_cli_del_arnes(monkeypatch, argv, esperado):
    corridas = []
    monkeypatch.setattr(calidad, "corre", lambda defectos, *_: corridas.append(defectos))
    calidad.main(argv)
    assert corridas == [esperado]


def test_ciegos_sin_regla_en_el_seed():
    # Cuando una regla de 4c.2 nombre a un ciego, este test cambia con ella.
    nombrados = con_regla()
    assert set(DEFECTOS) <= nombrados
    assert not nombrados & set(CIEGOS)


def test_seleccion_por_tabla():
    cifras, reglas = ETAPAS
    sel = seleccion(["raw_plan_produccion", "raw_partes"], cifras)
    assert len(sel) == 2 * len(cifras)
    assert "source:raw.raw_plan_produccion+,+mart_brecha_flota" in sel
    assert seleccion(["raw_mb51"], reglas) == ["source:raw.raw_mb51+,+int_calidad_violaciones"]


@pytest.fixture(scope="module")
def completo():
    try:
        c = duckdb.connect(str(RAIZ / "data" / "rpi.duckdb"), read_only=True)
        plantas = c.execute("SELECT COUNT(DISTINCT planta) FROM stg_mb51").fetchone()[0]
    except Exception:
        pytest.skip("DuckDB o marts no disponibles en este entorno.")
    if plantas != 14:
        c.close()
        pytest.skip(f"Dataset reducido ({plantas} plantas): la medición es del completo.")
    yield c
    c.close()


def test_limpio_del_arnes_cuadra_con_los_marts(completo):
    medicion = pl.read_csv(RAIZ / SALIDA, infer_schema_length=None)
    limpio = medicion.filter((pl.col("nivel") == "limpio") & (pl.col("tipo") == "cifra"))
    assert set(medicion["plantas"]) == {14}
    for cifra, sql in CIFRAS.items():
        valor = limpio.filter(pl.col("medida") == cifra)["valor"].item()
        assert valor == round(float(completo.execute(sql).fetchone()[0]), 2), cifra
