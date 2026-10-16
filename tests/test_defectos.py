"""
Catálogo de defectos (ADR-028, ADR-029): todo lo que cambia contra el limpio
está en la bitácora y todo lo que dice la bitácora cambió.
"""

from pathlib import Path

import duckdb
import polars as pl
import pytest
from pydantic import ValidationError

from rpi.__main__ import build_config, parse_args
from rpi.config import CIEGOS, DEFECTOS, GeneratorConfig
from rpi.db import ingest
from rpi.defectos import BITACORA, inyecta
from rpi.generator import INSTRUCCION, MAESTRO, PARTES, PLAN, STOCK_INICIAL, generate

LLAVE = ["Werks", "Mjahr", "Mblnr", "Zeile"]
LINEA = ["D02", "D03", "D04", "D05", "D06", "D07", "D08"]
POR_MATERIAL = ["D06", "D09", "D13", "D14", "D15", "D16", "D17"]


@pytest.fixture(scope="module")
def cfg_sucio(cfg_ci: GeneratorConfig) -> GeneratorConfig:
    data = cfg_ci.model_dump()
    data["defectos"]["activos"] = list(DEFECTOS)
    return GeneratorConfig.model_validate(data)


@pytest.fixture(scope="module")
def raw_sucio(cfg_sucio: GeneratorConfig, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("sucio")
    generate(cfg=cfg_sucio, output_dir=str(out))
    return out


@pytest.fixture(scope="module")
def bitacora(raw_sucio: Path) -> pl.DataFrame:
    return pl.read_parquet(raw_sucio / BITACORA)


def _mb51(raw: Path) -> pl.DataFrame:
    return pl.read_parquet(sorted(raw.glob("mb51_*.parquet")))


def _cambiadas(limpio: pl.DataFrame, sucio: pl.DataFrame, llave: list[str]) -> pl.DataFrame:
    """Llaves con alguna fila que no está igual en las dos tablas."""
    columnas = limpio.columns
    nuevas = sucio.join(limpio, on=columnas, how="anti", nulls_equal=True)
    quitadas = limpio.join(sucio, on=columnas, how="anti", nulls_equal=True)
    return pl.concat([nuevas.select(llave), quitadas.select(llave)]).unique()


def _llaves(b: pl.DataFrame, defectos: list[str], llave: list[str]) -> pl.DataFrame:
    return b.filter(pl.col("defecto").is_in(defectos)).select(llave).unique()


def _igual(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    cols = a.columns
    return a.sort(cols).equals(b.select(cols).sort(cols))


def test_mb51_solo_cambia_lo_de_la_bitacora(raw_ci, raw_sucio, bitacora):
    limpio, sucio = _mb51(raw_ci), _mb51(raw_sucio)
    cambiadas = _cambiadas(limpio, sucio, LLAVE)
    por_linea = _llaves(bitacora, LINEA, LLAVE)
    # Lo de D16 se registra por material: sus líneas solo cambian en Costo_usd.
    d16 = bitacora.filter(pl.col("defecto") == "D16").select("Werks", "Matnr")
    resto = cambiadas.join(por_linea, on=LLAVE, how="anti")
    solo_precio = (
        sucio.join(resto, on=LLAVE)
        .join(
            limpio.drop("Costo_usd"),
            on=[c for c in limpio.columns if c != "Costo_usd"],
            nulls_equal=True,
        )
        .join(d16, on=["Werks", "Matnr"])
        .select(LLAVE)
        .unique()
    )
    assert _igual(resto, solo_precio), "hay líneas cambiadas fuera de la bitácora"
    sin_cambio = por_linea.join(cambiadas, on=LLAVE, how="anti")
    assert sin_cambio.is_empty(), f"{sin_cambio.height} líneas en la bitácora no cambiaron"


def test_valor_inyectado_es_el_del_mb51(raw_sucio, bitacora):
    sucio = _mb51(raw_sucio)
    for campo in ("Bwart", "Lgort", "Kunnr", "Menge", "Cpudt"):
        b = bitacora.filter(pl.col("defecto").is_in(LINEA) & (pl.col("campo") == campo))
        cruce = b.join(sucio.select(*LLAVE, pl.col(campo).cast(pl.String).alias("_real")), on=LLAVE)
        assert cruce.height == b.height, campo
        distintos = cruce.filter(~pl.col("valor_inyectado").eq_missing(pl.col("_real")))
        assert distintos.is_empty(), f"{campo}: {distintos.head()}"


def test_duplicado_repite_la_llave(raw_ci, raw_sucio, bitacora):
    repetidas = (
        _mb51(raw_sucio).group_by(LLAVE).len().filter(pl.col("len") > 1).select(LLAVE).sort(LLAVE)
    )
    d01 = _llaves(bitacora, ["D01"], LLAVE).sort(LLAVE)
    assert not d01.is_empty()
    assert repetidas.equals(d01)
    assert _mb51(raw_sucio).height == _mb51(raw_ci).height + d01.height


@pytest.mark.parametrize(
    ("archivo", "llave", "defectos"),
    [
        (STOCK_INICIAL, ["Werks", "Matnr"], ["D09"]),
        (INSTRUCCION, ["Werks", "Parte"], ["D10", "D11", "D12"]),
        (MAESTRO, ["Werks", "Matnr"], ["D13", "D14", "D15", "D17", "D18"]),
        (PARTES, ["Werks", "Parte"], []),
        (PLAN, ["Werks", "Parte", "Semana"], []),
    ],
)
def test_tablas_solo_cambian_lo_de_la_bitacora(
    raw_ci, raw_sucio, bitacora, archivo, llave, defectos
):
    limpio = pl.read_parquet(raw_ci / archivo)
    sucio = pl.read_parquet(raw_sucio / archivo)
    llave_b = [c for c in llave if c in bitacora.columns]
    cambiadas = _cambiadas(limpio, sucio, llave).select(llave_b).unique()
    assert _igual(cambiadas, _llaves(bitacora, defectos, llave_b))


def test_al_menos_un_caso_por_planta(cfg_ci, bitacora):
    conteo = bitacora.group_by("defecto", "Werks").len()
    plantas = {p.werks for p in cfg_ci.plants}
    moneda_local = {cfg_ci.plants[0].werks}
    for d in DEFECTOS[:-1]:
        con_caso = set(conteo.filter(pl.col("defecto") == d)["Werks"])
        # D16 no cae donde el maestro queda en moneda local (ADR-030).
        esperadas = plantas - moneda_local if d == "D16" else plantas
        assert con_caso == esperadas, f"{d}: {con_caso}"
    # La moneda local cae en la primera planta de cada país con moneda propia.
    assert set(conteo.filter(pl.col("defecto") == "D18")["Werks"]) == moneda_local


def test_objetivos_no_se_repiten(bitacora):
    for (werks,), b in bitacora.group_by("Werks"):
        materiales = (
            b.filter(pl.col("defecto").is_in(POR_MATERIAL))
            .group_by("Matnr")
            .agg(pl.col("defecto").n_unique().alias("n"))
        )
        assert materiales.filter(pl.col("n") > 1).is_empty(), werks
        docs = (
            b.filter(pl.col("defecto").is_in(["D01", *LINEA]) & (pl.col("defecto") != "D06"))
            .group_by("Mjahr", "Mblnr")
            .agg(pl.col("defecto").n_unique().alias("n"))
        )
        assert docs.filter(pl.col("n") > 1).is_empty(), werks
        partes = b.filter(pl.col("Parte").is_not_null()).group_by("Parte").len()
        assert partes.filter(pl.col("len") > 1).is_empty(), werks
        # Una línea tocada después de D06 no cae en un material de D06.
        d06 = b.filter(pl.col("defecto") == "D06")["Matnr"].unique()
        despues = b.filter(pl.col("defecto").is_in(["D07", "D08"]))
        assert despues.filter(pl.col("Matnr").is_in(d06.implode())).is_empty(), werks


def test_defectos_reproducibles(cfg_sucio, bitacora, tmp_path):
    generate(cfg=cfg_sucio, output_dir=str(tmp_path))
    assert pl.read_parquet(tmp_path / BITACORA).equals(bitacora)


def test_bitacora_en_orden_canonico(bitacora):
    # El test de arriba corre con el config de CI, donde el orden sale estable
    # aunque no esté garantizado; este atrapa el desorden en cualquier tamaño.
    for _, g in bitacora.group_by("Werks", maintain_order=True):
        assert g.equals(g.sort(g.columns, nulls_last=True))


def test_limpio_sin_bitacora(raw_ci, cfg_ci, tmp_path):
    assert not (raw_ci / BITACORA).exists()
    # Una bitácora vieja en el directorio no sobrevive a una corrida limpia.
    pl.DataFrame({"defecto": ["D01"]}).write_parquet(tmp_path / BITACORA)
    generate(cfg=cfg_ci, output_dir=str(tmp_path))
    assert not (tmp_path / BITACORA).exists()


def test_ingesta_carga_y_borra_la_bitacora(raw_ci, raw_sucio, bitacora, tmp_path):
    db = tmp_path / "t.duckdb"
    ingest(db_path=db, raw_dir=raw_sucio)
    with duckdb.connect(str(db)) as con:
        n = con.execute("SELECT COUNT(*) FROM raw_bitacora_defectos").fetchone()[0]
    assert n == bitacora.height
    ingest(db_path=db, raw_dir=raw_ci)
    with duckdb.connect(str(db)) as con:
        tablas = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert "raw_bitacora_defectos" not in tablas


def test_cli_defectos():
    assert build_config(parse_args([])).defectos.activos == []
    assert build_config(parse_args(["--defectos", "todos"])).defectos.activos == list(DEFECTOS)
    assert build_config(parse_args(["--defectos", "ciegos"])).defectos.activos == list(CIEGOS)
    assert build_config(parse_args(["--defectos", "todos, ciegos"])).defectos.activos == [
        *DEFECTOS,
        *CIEGOS,
    ]
    assert build_config(parse_args(["--defectos", "D01,b03"])).defectos.activos == ["D01", "B03"]
    assert build_config(parse_args(["--defectos", "d05, D13"])).defectos.activos == ["D05", "D13"]
    with pytest.raises(ValidationError, match="D99"):
        build_config(parse_args(["--defectos", "D99"]))


def _tablas_planta(raw: Path, werks: str) -> dict[str, pl.DataFrame]:
    archivos = {
        "stock": STOCK_INICIAL,
        "partes": PARTES,
        "instruccion": INSTRUCCION,
        "plan": PLAN,
        "maestro": MAESTRO,
    }
    tablas = {
        k: pl.read_parquet(raw / f).filter(pl.col("Werks") == werks) for k, f in archivos.items()
    }
    tablas["mb51"] = pl.read_parquet(raw / f"mb51_{werks}.parquet")
    return tablas


def test_lo_tocado_queda_fuera_de_los_siguientes(cfg_ci, raw_ci):
    # Forzado: con un solo día, D01 duplica todo y D05 no tiene línea libre;
    # con un solo material, D13 lo toma y D15 se queda sin candidato.
    planta = cfg_ci.plants[0]
    tablas = _tablas_planta(raw_ci, planta.werks)
    dia = tablas["mb51"]["Budat"].min()
    material = tablas["mb51"].filter(pl.col("Budat") == dia)["Matnr"].min()
    tablas["mb51"] = tablas["mb51"].filter(pl.col("Budat") == dia)
    tablas["maestro"] = tablas["maestro"].filter(pl.col("Matnr") == material)
    cfg = cfg_ci.defectos.model_copy(update={"activos": ["D01", "D05", "D13", "D15"]})
    _, b = inyecta(tablas, cfg, planta, True, cfg_ci.reference_date, 42, 0)
    por_defecto = dict(b.group_by("defecto").len().iter_rows())
    assert por_defecto.get("D01", 0) == tablas["mb51"].height
    assert por_defecto.get("D13", 0) == 1
    assert "D05" not in por_defecto
    assert "D15" not in por_defecto
