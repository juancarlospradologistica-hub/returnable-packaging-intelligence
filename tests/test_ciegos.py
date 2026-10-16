"""
Defectos ciegos (ADR-033): lo mismo que el catálogo, todo lo que cambia contra
el limpio está en la bitácora, más la forma de cada uno. Ninguna regla los
nombra todavía; lo que se prueba aquí es que el generador inyecta lo que el
ADR describe y nada más.
"""

from datetime import timedelta
from pathlib import Path

import polars as pl
import pytest

from rpi.config import CIEGOS, GeneratorConfig
from rpi.defectos import BITACORA, inyecta
from rpi.generator import INSTRUCCION, MAESTRO, PARTES, PLAN, STOCK_INICIAL, generate
from tests.test_defectos import _cambiadas, _igual, _mb51, _tablas_planta

LLAVE = ["Werks", "Mjahr", "Mblnr", "Zeile"]
DOC = ["Werks", "Mjahr", "Mblnr"]


@pytest.fixture(scope="module")
def cfg_ciegos(cfg_ci: GeneratorConfig) -> GeneratorConfig:
    data = cfg_ci.model_dump()
    data["defectos"]["activos"] = list(CIEGOS)
    return GeneratorConfig.model_validate(data)


@pytest.fixture(scope="module")
def raw_ciegos(cfg_ciegos: GeneratorConfig, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("ciegos")
    generate(cfg=cfg_ciegos, output_dir=str(out))
    return out


@pytest.fixture(scope="module")
def bitacora(raw_ciegos: Path) -> pl.DataFrame:
    return pl.read_parquet(raw_ciegos / BITACORA)


@pytest.fixture(scope="module")
def limpio(raw_ci: Path) -> pl.DataFrame:
    return _mb51(raw_ci)


@pytest.fixture(scope="module")
def sucio(raw_ciegos: Path) -> pl.DataFrame:
    return _mb51(raw_ciegos)


def _de(bitacora: pl.DataFrame, defecto: str) -> pl.DataFrame:
    return bitacora.filter(pl.col("defecto") == defecto)


def test_mb51_solo_cambia_lo_de_la_bitacora(limpio, sucio, bitacora):
    cambiadas = _cambiadas(limpio, sucio, LLAVE)
    assert _igual(cambiadas, bitacora.select(LLAVE).unique())


@pytest.mark.parametrize("archivo", [STOCK_INICIAL, PARTES, INSTRUCCION, PLAN, MAESTRO])
def test_las_demas_tablas_no_cambian(raw_ci, raw_ciegos, archivo):
    # B01 cambia el Matnr del MB51 y deja el maestro como estaba.
    assert pl.read_parquet(raw_ciegos / archivo).equals(pl.read_parquet(raw_ci / archivo))


def test_al_menos_un_caso_por_planta(cfg_ci, bitacora):
    plantas = {p.werks for p in cfg_ci.plants}
    for d in CIEGOS:
        assert set(_de(bitacora, d)["Werks"]) == plantas, d


@pytest.mark.parametrize("campo", ["Matnr", "Kunnr", "Budat"])
def test_valores_de_la_bitacora(limpio, sucio, bitacora, campo):
    b = bitacora.filter(pl.col("campo") == campo)
    assert not b.is_empty()
    cruce = b.join(
        sucio.select(*LLAVE, pl.col(campo).cast(pl.String).alias("_sucio")), on=LLAVE
    ).join(limpio.select(*LLAVE, pl.col(campo).cast(pl.String).alias("_limpio")), on=LLAVE)
    assert cruce.height == b.height
    assert (cruce["valor_inyectado"] == cruce["_sucio"]).all()
    assert (cruce["valor_original"] == cruce["_limpio"]).all()


def test_b01_matnr_con_ceros_desde_una_fecha(cfg_ciegos, limpio, sucio, bitacora):
    b01 = _de(bitacora, "B01")
    ceros = "0" * cfg_ciegos.defectos.b01_ceros
    assert (b01["valor_inyectado"] == ceros + b01["valor_original"]).all()
    for (werks,), b in b01.group_by("Werks"):
        # Desde la primera línea cambiada, ningún movimiento del material sale
        # con el código de antes: es un cambio de formato, no ruido.
        desde = sucio.join(b.select(LLAVE), on=LLAVE)["Budat"].min()
        materiales = b["valor_original"].unique().implode()
        quedan = sucio.filter(
            (pl.col("Werks") == werks)
            & pl.col("Matnr").is_in(materiales)
            & (pl.col("Budat") >= desde)
        )
        assert quedan.is_empty(), werks
        antes = limpio.filter(
            (pl.col("Werks") == werks)
            & pl.col("Matnr").is_in(materiales)
            & (pl.col("Budat") < desde)
        )
        assert not antes.is_empty(), f"{werks}: el cambio no llega a media historia"


def test_b01_codigo_nuevo_fuera_del_maestro(raw_ciegos, bitacora):
    maestro = pl.read_parquet(raw_ciegos / MAESTRO).select("Werks", "Matnr")
    b01 = _de(bitacora, "B01")
    nuevos = b01.select("Werks", pl.col("valor_inyectado").alias("Matnr")).unique()
    viejos = b01.select("Werks", pl.col("valor_original").alias("Matnr")).unique()
    assert nuevos.join(maestro, on=["Werks", "Matnr"]).is_empty()
    assert viejos.join(maestro, on=["Werks", "Matnr"]).height == viejos.height


def test_b02_kunnr_con_ceros_desde_una_fecha(limpio, sucio, bitacora):
    b02 = _de(bitacora, "B02")
    assert (b02["valor_inyectado"] == "00" + b02["valor_original"]).all()
    assert (sucio.join(b02.select(LLAVE), on=LLAVE)["Bwart"] == "622").all()
    # Las líneas que B01 ya tomó quedan fuera; todo lo demás del cliente cambia.
    b01 = _de(bitacora, "B01")
    tomados = b01.select(DOC).unique()
    materiales = pl.concat(
        [
            b01.select("Werks", pl.col(c).alias("Matnr"))
            for c in ("valor_original", "valor_inyectado")
        ]
    ).unique()
    for (werks,), b in b02.group_by("Werks"):
        desde = sucio.join(b.select(LLAVE), on=LLAVE)["Budat"].min()
        quedan = (
            sucio.filter(
                (pl.col("Werks") == werks)
                & (pl.col("Bwart") == "622")
                & pl.col("Kunnr").is_in(b["valor_original"].unique().implode())
                & (pl.col("Budat") >= desde)
            )
            .join(tomados, on=DOC, how="anti")
            .join(materiales, on=["Werks", "Matnr"], how="anti")
        )
        assert quedan.is_empty(), werks


def test_b03_no_repite_la_llave(limpio, sucio, bitacora):
    b03 = _de(bitacora, "B03")
    assert sucio.group_by(LLAVE).len().filter(pl.col("len") > 1).is_empty()
    assert sucio.height == limpio.height + b03.height
    assert b03["Mblnr"].str.starts_with("4999").all()


def test_b03_copia_un_documento_621_al_dia_siguiente(cfg_ci, limpio, sucio, bitacora):
    dup = sucio.join(_de(bitacora, "B03").select(LLAVE), on=LLAVE)
    assert (dup["Bwart"] == "621").all()
    igual = [c for c in limpio.columns if c not in ("Mblnr", "Cpudt")]
    cruce = dup.with_columns(pl.col("Mblnr").str.slice(4).alias("_sufijo")).join(
        limpio.with_columns(pl.col("Mblnr").str.slice(4).alias("_sufijo")),
        on=[*igual, "_sufijo"],
        suffix="_orig",
        nulls_equal=True,
    )
    assert cruce.height == dup.height
    corte = cfg_ci.reference_date
    esperado = pl.min_horizontal(pl.col("Cpudt_orig") + pl.duration(days=1), pl.lit(corte))
    assert cruce.select((pl.col("Cpudt") == esperado).all()).item()


def test_b04_budat_despues_del_corte(cfg_ciegos, limpio, sucio, bitacora):
    b04 = _de(bitacora, "B04")
    corte = cfg_ciegos.reference_date
    lineas = sucio.join(b04.select(LLAVE), on=LLAVE).join(
        limpio.select(*LLAVE, pl.col("Budat").alias("_antes"), pl.col("Cpudt").alias("_cpudt")),
        on=LLAVE,
    )
    assert lineas.height == b04.height
    assert (lineas["Bwart"] == "621").all()
    assert lineas["Budat"].min() > corte
    assert lineas["Budat"].max() <= corte + timedelta(days=5)
    assert lineas["Cpudt"].max() <= corte
    assert lineas["Cpudt"].equals(lineas["_cpudt"], check_names=False)
    ventana = corte - timedelta(days=cfg_ciegos.defectos.b04_dias)
    assert lineas["_antes"].min() > ventana


def test_lo_tocado_por_d01_queda_fuera_de_los_ciegos(cfg_ci, raw_ci):
    # Forzado: los últimos tres días de la planta, cada ciego a tasa 1. Solo
    # tiene casos; con D01 duplicando los tres días, ninguno. Uno por uno: a
    # tasa 1, B01 se lleva todos los materiales y deja sin candidatos a B03 y B04.
    planta = cfg_ci.plants[0]
    tablas = _tablas_planta(raw_ci, planta.werks)
    dias = tablas["mb51"]["Budat"].unique().sort()
    tablas["mb51"] = tablas["mb51"].filter(pl.col("Budat") >= dias[-3])
    tasa_1 = {"b01_tasa": 1.0, "b02_clientes": 99, "b03_tasa": 1.0, "b04_tasa": 1.0, "d01_dias": 3}

    def corre(activos: list[str]) -> dict[str, int]:
        cfg = cfg_ci.defectos.model_copy(update=tasa_1 | {"activos": activos})
        _, b = inyecta(tablas, cfg, planta, True, cfg_ci.reference_date, 42, 0)
        return dict(b.group_by("defecto").len().iter_rows())

    for d in CIEGOS:
        assert corre([d]).get(d, 0) > 0, d
        con_d01 = corre(["D01", d])
        assert con_d01["D01"] == tablas["mb51"].height
        assert d not in con_d01, d
