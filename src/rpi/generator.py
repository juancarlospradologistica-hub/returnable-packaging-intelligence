# src/rpi/generator.py
"""
Generador sintético de movimientos MB51 para el proyecto RPI.
Produce un dataset Parquet de 18 meses con reglas de negocio realistas
según los parámetros definidos en PROYECTO.md §4.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import polars as pl
from faker import Faker

from rpi.config import Country, GeneratorConfig, MaterialType
# ---------------------------------------------------------------------------
# Utilidades de nomenclatura
# ---------------------------------------------------------------------------

_MATERIAL_PREFIX: dict[MaterialType, str] = {
    MaterialType.KLT: "KLT",
    MaterialType.RACK: "RCK",
    MaterialType.CARTON: "CTN",
}


# ---------------------------------------------------------------------------
# Construcción del pool de materiales
# ---------------------------------------------------------------------------


def build_matnr_pool(
    cfg: GeneratorConfig,
    rng: np.random.Generator,
) -> dict[str, dict]:
    """
    Genera el universo global de Matnr y sus atributos estáticos.

    Retorna un dict keyed por Matnr con:
        - matnr: str
        - maktx: str  (descripción legible)
        - material_type: MaterialType
    """
    pool_size = cfg.global_matnr_pool
    mix = cfg.material_mix

    # Cuántos materiales por tipo según el mix definido en PROYECTO.md §4
    n_klt = round(pool_size * mix.klt)
    n_rack = round(pool_size * mix.rack)
    n_carton = pool_size - n_klt - n_rack  # el resto para cuadrar exacto

    records: dict[str, dict] = {}

    for mat_type, count in [
        (MaterialType.KLT, n_klt),
        (MaterialType.RACK, n_rack),
        (MaterialType.CARTON, n_carton),
    ]:
        prefix = _MATERIAL_PREFIX[mat_type]
        for i in range(1, count + 1):
            matnr = f"{prefix}-{i:05d}"
            records[matnr] = {
                "matnr": matnr,
                "maktx": _maktx(mat_type, i),
                "material_type": mat_type,
            }

    return records


def _maktx(mat_type: MaterialType, idx: int) -> str:
    """Descripción breve del material. Legible sin cruzar MAKT."""
    labels = {
        MaterialType.KLT: "KLT Plastico",
        MaterialType.RACK: "Rack Metalico",
        MaterialType.CARTON: "Caja Carton",
    }
    return f"{labels[mat_type]} {idx:05d}"
# ---------------------------------------------------------------------------
# Asignación de Matnr por planta con solape controlado
# ---------------------------------------------------------------------------


def assign_matnr_to_plants(
    cfg: GeneratorConfig,
    pool: dict[str, dict],
    rng: np.random.Generator,
) -> dict[str, list[str]]:
    """
    Asigna un subconjunto de Matnr a cada planta con solape entre plantas.

    Estrategia:
    - 40% del pool son Matnr globales: todas las plantas los tienen.
    - 60% restante se reparte aleatoriamente hasta completar matnr_count.

    Retorna dict: werks → lista de Matnr asignados.
    """
    all_matnr = list(pool.keys())
    total = len(all_matnr)

    # Matnr que circulan en todas las plantas (solape garantizado)
    n_global = round(total * 0.40)
    global_matnr = list(rng.choice(all_matnr, size=n_global, replace=False))
    local_pool = [m for m in all_matnr if m not in set(global_matnr)]

    assignment: dict[str, list[str]] = {}

    for plant in cfg.plants:
        n_needed = plant.matnr_count - len(global_matnr)
        n_needed = max(n_needed, 0)

        if n_needed > 0 and len(local_pool) > 0:
            n_sample = min(n_needed, len(local_pool))
            local_sample = list(
                rng.choice(local_pool, size=n_sample, replace=False)
            )
        else:
            local_sample = []

        assignment[plant.werks] = global_matnr + local_sample

    return assignment

# ---------------------------------------------------------------------------
# Generación del horizonte de fechas
# ---------------------------------------------------------------------------


def build_date_range(
    cfg: GeneratorConfig,
    reference_date: date | None = None,
) -> list[date]:
    """
    Genera la lista de fechas hábiles del horizonte de 18 meses.
    reference_date: último día del horizonte. Default: hoy.
    """
    end = reference_date or date.today()
    start = end - timedelta(days=cfg.horizon_months * 30)

    dates = []
    current = start
    while current <= end:
        # Excluye sábados (5) y domingos (6)
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)

    return dates
# ---------------------------------------------------------------------------
# Pesos de Bwart (mix realista según PROYECTO.md §4)
# ---------------------------------------------------------------------------

# Bwart y su peso relativo de aparición en el dataset
_BWART_WEIGHTS: dict[str, float] = {
    "501": 0.18,  # Recepción sin PO (retorno de cliente)
    "502": 0.10,  # Devolución de recepción sin PO
    "601": 0.22,  # Salida a cliente
    "602": 0.20,  # Retorno de cliente
    "311": 0.12,  # Traslado entre almacenes
    "411": 0.08,  # Traslado inverso
    "101": 0.04,  # Recepción con PO
    "102": 0.02,  # Devolución de recepción con PO
    "261": 0.03,  # Consumo a orden
    "309": 0.01,  # Diferencia de inventario (esporádico)
}

_BWART_LIST = list(_BWART_WEIGHTS.keys())
_BWART_PROBS = [_BWART_WEIGHTS[b] for b in _BWART_LIST]
# ---------------------------------------------------------------------------
# Emisión de movimientos por planta
# ---------------------------------------------------------------------------


def emit_plant_movements(
    plant_werks: str,
    plant_matnrs: list[str],
    pool: dict[str, dict],
    dates: list[date],
    cfg: GeneratorConfig,
    rng: np.random.Generator,
    n_movements: int,
) -> list[dict]:
    """
    Genera n_movements registros MB51 para una planta.
    Cada registro sigue el schema de las 22 columnas definido en PROYECTO.md §4.
    """
    rows = []

    # Vectores base generados de una vez para velocidad
    chosen_dates = rng.choice(dates, size=n_movements)
    chosen_matnrs = rng.choice(plant_matnrs, size=n_movements)
    chosen_bwarts = rng.choice(_BWART_LIST, size=n_movements, p=_BWART_PROBS)
    quantities = rng.integers(1, 50, size=n_movements)

    # Lag Cpudt vs Budat
    lag_probs = [
        cfg.cpudt_lag.same_day,
        cfg.cpudt_lag.one_to_two_days,
        cfg.cpudt_lag.over_48h,
    ]
    lag_category = rng.choice([0, 1, 2], size=n_movements, p=lag_probs)

    for i in range(n_movements):
        budat = chosen_dates[i]
        matnr = str(chosen_matnrs[i])
        bwart = str(chosen_bwarts[i])
        menge = int(quantities[i])
        mat_info = pool[matnr]

        # Cpudt según lag definido en config
        lag_cat = int(lag_category[i])
        if lag_cat == 0:
            cpudt = budat
        elif lag_cat == 1:
            cpudt = budat + timedelta(days=int(rng.integers(1, 3)))
        else:
            cpudt = budat + timedelta(days=int(rng.integers(3, 10)))

        # Documento material sintético
        mblnr = f"50{rng.integers(10_000_000, 99_999_999)}"

        row = {
            "Werks": plant_werks,
            "Lgort": _pick_lgort(bwart, rng),
            "Matnr": matnr,
            "Maktx": mat_info["maktx"],
            "Bwart": bwart,
            "Mjahr": budat.year,
            "Budat": budat,
            "Cpudt": cpudt,
            "Cputm": f"{rng.integers(6,22):02d}:{rng.integers(0,60):02d}:00",
            "Menge": menge if bwart not in ("502", "102", "411") else -menge,
            "Meins": "PC",
            "Mblnr": mblnr,
            "Zeile": f"{rng.integers(1, 10):04d}",
            "Lifnr": _pick_lifnr(bwart, rng),
            "Kunnr": _pick_kunnr(bwart, rng),
            "Xblnr": f"REF-{rng.integers(100_000, 999_999)}",
        }
        rows.append(row)

    return rows


def _pick_lgort(bwart: str, rng: np.random.Generator) -> str:
    """Almacén según tipo de movimiento."""
    if bwart in ("601", "602"):
        return rng.choice(["EXPE", "RECP"])
    if bwart in ("311", "411"):
        return rng.choice(["TR01", "TR02"])
    return rng.choice(["RM01", "RM02", "QA01"])


def _pick_lifnr(bwart: str, rng: np.random.Generator) -> str | None:
    """Proveedor solo en movimientos de recepción con proveedor."""
    if bwart in ("101", "102", "501", "502"):
        return f"PROV-{rng.integers(1000, 9999)}"
    return None


def _pick_kunnr(bwart: str, rng: np.random.Generator) -> str | None:
    """Cliente solo en movimientos de salida/retorno a cliente."""
    if bwart in ("601", "602"):
        return f"CUST-{rng.integers(1000, 9999)}"
    return None
# ---------------------------------------------------------------------------
# Orquestador principal
# ---------------------------------------------------------------------------


def generate(
    cfg: GeneratorConfig | None = None,
    output_dir: str = "data/raw",
    reference_date: date | None = None,
) -> pl.DataFrame:
    """
    Genera el dataset MB51 completo y lo escribe en Parquet.

    Retorna el DataFrame completo para validación inmediata.
    """
    import os

    if cfg is None:
        cfg = GeneratorConfig()

    if cfg.random_seed is not None:
        rng = np.random.default_rng(cfg.random_seed)
    else:
        rng = np.random.default_rng()

    os.makedirs(output_dir, exist_ok=True)

    pool = build_matnr_pool(cfg, rng)
    assignment = assign_matnr_to_plants(cfg, pool, rng)
    dates = build_date_range(cfg, reference_date)

    all_rows: list[dict] = []

    for plant in cfg.plants:
        # Volumen mensual aleatorio dentro del rango de la planta
        monthly = int(
            rng.integers(
                plant.monthly_movements_min,
                plant.monthly_movements_max,
            )
        )
        total_movements = monthly * cfg.horizon_months

        print(f"  {plant.werks}: {total_movements:,} movimientos...")

        rows = emit_plant_movements(
            plant_werks=plant.werks,
            plant_matnrs=assignment[plant.werks],
            pool=pool,
            dates=dates,
            cfg=cfg,
            rng=rng,
            n_movements=total_movements,
        )
        all_rows.extend(rows)

    print(f"Total filas: {len(all_rows):,} — convirtiendo a Polars...")

    df = pl.DataFrame(all_rows)

    # Tipos correctos
    df = df.with_columns([
        pl.col("Budat").cast(pl.Date),
        pl.col("Cpudt").cast(pl.Date),
        pl.col("Mjahr").cast(pl.Int32),
        pl.col("Menge").cast(pl.Int64),
    ])

        # Ciclo 601 → 602 con merma (2% no-retorno)
    print("Aplicando ciclo 601 → 602 y merma...")
    df = apply_return_cycle(df, cfg, rng)

    # Escribir Parquet
    output_path = f"{output_dir}/mb51_synthetic.parquet"
    df.write_parquet(output_path)
    print(f"Parquet escrito: {output_path} ({df.shape[0]:,} filas, {df.shape[1]} columnas)")

    return df
# ---------------------------------------------------------------------------
# Ciclo 601 → 602 con merma
# ---------------------------------------------------------------------------


def _lognormal_cycle_days(
    cfg: GeneratorConfig,
    rng: np.random.Generator,
    n: int,
) -> np.ndarray:
    """
    Genera n duraciones de ciclo en días siguiendo distribución log-normal.
    Media ~25 días, cola hasta ~90 días, techo en cap_days.
    """
    # Parámetros log-normal para media=25 días con sigma definido en config
    mu = math.log(cfg.cycle.mean_days) - 0.5 * cfg.cycle.sigma ** 2
    raw = rng.lognormal(mean=mu, sigma=cfg.cycle.sigma, size=n)
    clipped = np.clip(raw, 1, cfg.cycle.cap_days)
    return np.round(clipped).astype(int)


def apply_return_cycle(
    df: pl.DataFrame,
    cfg: GeneratorConfig,
    rng: np.random.Generator,
) -> pl.DataFrame:
    """
    Post-proceso que reemplaza los movimientos 602 generados aleatoriamente
    por retornos reales vinculados a cada 601.

    - 98% de los 601 generan un 602 con ciclo log-normal (media 25 días).
    - 2% no generan 602 (merma / flota fantasma).

    Retorna el DataFrame con los 602 corregidos y los 601 huérfanos marcados.
    """
    # Separar 601 del resto
    df_601 = df.filter(pl.col("Bwart") == "601")
    df_rest = df.filter(pl.col("Bwart") != "601")

    # Eliminar los 602 generados aleatoriamente — los vamos a reconstruir
    df_rest = df_rest.filter(pl.col("Bwart") != "602")

    n_601 = len(df_601)
    loss_rate = cfg.loss_rate

    # Máscara de retorno: True = genera 602, False = merma
    returns_mask = rng.random(n_601) >= loss_rate
    n_returns = int(returns_mask.sum())

    # Ciclos en días para los que sí retornan
    cycle_days = _lognormal_cycle_days(cfg, rng, n_returns)

    # Construir los 602 como copia de sus 601 padre
    df_601_returns = df_601.filter(
        pl.Series("mask", returns_mask)
    )

    budats_601 = df_601_returns["Budat"].to_list()
    new_budats = [
        d + timedelta(days=int(c))
        for d, c in zip(budats_601, cycle_days)
    ]

    df_602 = df_601_returns.with_columns([
        pl.lit("602").alias("Bwart"),
        pl.Series("Budat", new_budats).cast(pl.Date),
        pl.Series("Cpudt", new_budats).cast(pl.Date),
        pl.col("Menge") * -1,  # retorno invierte cantidad
    ])

    # Marcar 601 huérfanos (merma) en Sgtxt via Xblnr
    loss_mask = ~returns_mask
    df_601_loss = df_601.filter(pl.Series("mask", loss_mask))
    df_601_loss = df_601_loss.with_columns(
        pl.lit("MERMA-NO-RETORNO").alias("Xblnr")
    )
    df_601_ok = df_601.filter(pl.Series("mask", returns_mask))

    # Reunir todo
    df_final = pl.concat([df_rest, df_601_ok, df_601_loss, df_602])
    df_final = df_final.sort(["Werks", "Budat"])

    return df_final