"""
Plan de producción e instrucción de empaque derivados de los embarques
(ADR-017, punto 8; ADR-022).

El plan se valida contra los 621 de la ventana base: la semana 1 de cada
material y cliente tiene que devolver los contenedores por semana de la base,
y el escenario solo puede mover el volumen desde su semana de cambio.
"""

import math

import polars as pl
import pytest

from rpi.config import GeneratorConfig
from rpi.generator import plan_calendar

LLAVE = ["Werks", "Parte"]
# Las piezas del plan se redondean por parte: media pieza de error por parte.
REDONDEO = 0.5


def _base(df: pl.DataFrame, cfg: GeneratorConfig) -> pl.DataFrame:
    """Contenedores por semana de cada material y cliente en la ventana base."""
    inicio, fin, _ = plan_calendar(cfg)
    return (
        df.filter((pl.col("Bwart") == "621") & pl.col("Budat").is_between(inicio, fin))
        .group_by("Werks", "Matnr", "Kunnr")
        .agg((-pl.col("Menge").sum() / cfg.plan.base_weeks).alias("base"))
    )


def _partes(partes: pl.DataFrame, instruccion: pl.DataFrame) -> pl.DataFrame:
    return partes.join(instruccion.rename({"Piezas": "por_contenedor"}), on=LLAVE)


def test_calendario(plan_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    inicio, fin, semanas = plan_calendar(cfg_ci)
    # La semana del corte está incompleta: no entra ni a la base ni al plan.
    assert inicio.weekday() == 0 and fin.weekday() == 6
    assert fin < cfg_ci.reference_date < semanas[0]
    assert (fin - inicio).days + 1 == 7 * cfg_ci.plan.base_weeks
    assert sorted(plan_ci["Semana"].unique()) == semanas
    assert all(s.weekday() == 0 for s in semanas)
    por_parte = plan_ci.group_by(LLAVE).agg(pl.col("Semana").n_unique())["Semana"]
    assert por_parte.unique().to_list() == [cfg_ci.plan.horizon_weeks]


def test_mismas_partes_en_las_tres_tablas(
    partes_ci: pl.DataFrame, instruccion_ci: pl.DataFrame, plan_ci: pl.DataFrame
) -> None:
    llaves = [
        set(t.select(LLAVE).unique().iter_rows()) for t in (partes_ci, instruccion_ci, plan_ci)
    ]
    assert llaves[0] == llaves[1] == llaves[2]
    assert partes_ci.height == len(llaves[0]), "Parte repetida"


def test_partes_por_empaque(
    df_ci: pl.DataFrame,
    partes_ci: pl.DataFrame,
    instruccion_ci: pl.DataFrame,
    cfg_ci: GeneratorConfig,
) -> None:
    """KLT: una parte por material y cliente de la base. Rack: 1 a 3 del cliente dedicado."""
    p = _partes(partes_ci, instruccion_ci)
    base = set(_base(df_ci, cfg_ci).select("Werks", "Matnr", "Kunnr").iter_rows())
    assert set(p.select("Werks", "Matnr", "Kunnr").unique().iter_rows()) == base

    klt = p.filter(pl.col("Matnr").str.starts_with("KLT"))
    assert not klt.select("Werks", "Matnr", "Kunnr").is_duplicated().any()

    rack = p.filter(pl.col("Matnr").str.starts_with("RCK")).group_by("Werks", "Matnr")
    rango = cfg_ci.plan.rack_parts
    conteo = rack.agg(pl.len().alias("partes"), pl.col("Kunnr").n_unique().alias("clientes"))
    assert conteo["clientes"].max() == 1, "Rack con partes de más de un cliente"
    assert conteo["partes"].min() >= rango.min and conteo["partes"].max() <= rango.max
    assert conteo["partes"].n_unique() > 1, "Todos los Rack con el mismo número de partes"
    assert not p.filter(pl.col("Matnr").str.starts_with("CTN")).height, "Instrucción con cartón"


def test_semana_1_cuadra_con_la_base(
    df_ci: pl.DataFrame,
    partes_ci: pl.DataFrame,
    instruccion_ci: pl.DataFrame,
    plan_ci: pl.DataFrame,
    cfg_ci: GeneratorConfig,
) -> None:
    """Antes de la primera semana de cambio el plan es la base, en piezas."""
    primera = plan_ci["Semana"].min()
    sin_volumen = plan_ci.filter((pl.col("Semana") == primera) & (pl.col("Piezas") == 0))
    assert sin_volumen.is_empty(), f"Partes con plan en cero:\n{sin_volumen.head()}"
    plan = (
        plan_ci.filter(pl.col("Semana") == primera)
        .join(_partes(partes_ci, instruccion_ci), on=LLAVE)
        .group_by("Werks", "Matnr", "Kunnr")
        .agg(
            (pl.col("Piezas") / pl.col("por_contenedor")).sum().alias("plan"),
            (REDONDEO / pl.col("por_contenedor")).sum().alias("tolerancia"),
        )
        .join(_base(df_ci, cfg_ci), on=["Werks", "Matnr", "Kunnr"])
    )
    fuera = plan.filter((pl.col("plan") - pl.col("base")).abs() > pl.col("tolerancia") + 1e-9)
    assert fuera.is_empty(), f"Plan que no cuadra con la base:\n{fuera.head()}"


def test_mezcla_de_escenarios(partes_ci: pl.DataFrame, cfg_ci: GeneratorConfig) -> None:
    n = partes_ci.height
    sc = cfg_ci.plan.scenario
    esperado = {
        "estable": sc.stable_share,
        "arranque": sc.ramp_up_share,
        "fin_serie": sc.phase_out_share,
    }
    conteo = dict(partes_ci.group_by("Escenario").len().iter_rows())
    for escenario, p in esperado.items():
        # Cuatro desviaciones de la binomial: falla por bug, no por azar.
        holgura = 4 * math.sqrt(n * p * (1 - p))
        assert abs(conteo.get(escenario, 0) - n * p) <= holgura, f"{escenario}: {conteo}"


@pytest.mark.parametrize("escenario", ["estable", "arranque", "fin_serie"])
def test_cambio_por_escenario(
    partes_ci: pl.DataFrame, plan_ci: pl.DataFrame, cfg_ci: GeneratorConfig, escenario: str
) -> None:
    """
    Estable no cambia. Arranque y fin de serie cambian una sola vez, en la semana
    sorteada, por el factor del supuesto. Las partes de pocas piezas se saltan
    el factor: el redondeo lo deforma.
    """
    sc = cfg_ci.plan.scenario
    factor = {
        "estable": 1.0,
        "arranque": 1 + sc.ramp_up_change,
        "fin_serie": 1 + sc.phase_out_change,
    }
    s = (
        plan_ci.join(partes_ci.filter(pl.col("Escenario") == escenario), on=LLAVE)
        .sort(*LLAVE, "Semana")
        .with_columns(pl.int_range(pl.len()).over(LLAVE).alias("n"))
        .group_by(LLAVE)
        .agg(
            pl.col("Piezas").first().alias("inicial"),
            pl.col("Piezas").last().alias("final"),
            (pl.col("Piezas").diff() != 0).sum().alias("cambios"),
            pl.col("n").filter(pl.col("Piezas").diff() != 0).first().alias("semana"),
        )
    )
    assert s.height > 0, f"Sin partes en {escenario}: el test no prueba nada"
    if escenario == "estable":
        assert s["cambios"].max() == 0
        return

    grandes = s.filter(pl.col("inicial") >= 20)
    semana = grandes["semana"] + 1
    rango = sc.change_week
    assert grandes["cambios"].max() == 1
    assert semana.min() >= rango.min and semana.max() <= rango.max
    razon = grandes["final"] / grandes["inicial"]
    # Las dos semanas se redondean por separado: media pieza en cada una.
    tolerancia = REDONDEO * (1 + factor[escenario]) / grandes["inicial"]
    assert ((razon - factor[escenario]).abs() <= tolerancia).all(), f"Razón fuera: {razon}"
