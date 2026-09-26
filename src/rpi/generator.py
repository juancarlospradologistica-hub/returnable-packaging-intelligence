# src/rpi/generator.py
"""
Generador sintético de movimientos MB51 (ADR-011).

Ciclo del retornable con cliente como stock especial V:
621 salida, 622 recogida, 702 faltante reconocido en conciliación.
El cartón es desechable: sale con 601 y no regresa.
Ningún movimiento se emite después de cfg.reference_date.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from rpi.config import GeneratorConfig, MaterialType

_MATERIAL_PREFIX: dict[MaterialType, str] = {
    MaterialType.KLT: "KLT",
    MaterialType.RACK: "RCK",
    MaterialType.CARTON: "CTN",
}

_MAKTX_LABEL: dict[MaterialType, str] = {
    MaterialType.KLT: "KLT Plastico",
    MaterialType.RACK: "Rack Metalico",
    MaterialType.CARTON: "Caja Carton",
}

# "SHIP" es la salida a cliente: 621 para retornables, 601 para cartón.
_KIND_WEIGHTS: dict[str, float] = {
    "SHIP": 0.22,
    "501": 0.18,
    "502": 0.10,
    "311": 0.12,
    "411": 0.08,
    "101": 0.04,
    "102": 0.02,
    "261": 0.03,
    "309": 0.01,
}
_KINDS = list(_KIND_WEIGHTS)
_KIND_PROBS = np.array([_KIND_WEIGHTS[k] for k in _KINDS]) / sum(_KIND_WEIGHTS.values())

# Traslados: se emiten en pareja (sale de un almacén, entra a otro) con el mismo documento.
_TRANSFERS = {"311", "411", "309"}
# Signo SAP: salidas negativas, entradas positivas.
_NEGATIVE = {"502", "102", "261", "601", "621", "702"}

_OVERDUE_DAYS = 120


# ---------------------------------------------------------------------------
# Maestros: materiales, asignación a plantas, clientes
# ---------------------------------------------------------------------------


def build_matnr_pool(cfg: GeneratorConfig) -> pl.DataFrame:
    """Universo global de Matnr con tipo, descripción y costo."""
    mix = cfg.material_mix
    n_klt = round(cfg.global_matnr_pool * mix.klt)
    n_rack = round(cfg.global_matnr_pool * mix.rack)
    n_carton = cfg.global_matnr_pool - n_klt - n_rack
    cost = {
        MaterialType.KLT: cfg.cost.klt,
        MaterialType.RACK: cfg.cost.rack,
        MaterialType.CARTON: cfg.cost.carton,
    }

    rows = []
    for mat_type, count in [
        (MaterialType.KLT, n_klt),
        (MaterialType.RACK, n_rack),
        (MaterialType.CARTON, n_carton),
    ]:
        for i in range(1, count + 1):
            rows.append(
                {
                    "Matnr": f"{_MATERIAL_PREFIX[mat_type]}-{i:05d}",
                    "Maktx": f"{_MAKTX_LABEL[mat_type]} {i:05d}",
                    "tipo": mat_type.value,
                    "Costo_usd": cost[mat_type],
                }
            )
    return pl.DataFrame(rows)


def assign_matnr_to_plants(
    cfg: GeneratorConfig,
    pool: pl.DataFrame,
    rng: np.random.Generator,
) -> dict[str, list[str]]:
    """
    Globales en todas las plantas (ADR-007) y locales repartidos sin repetir
    entre plantas (ADR-011).
    """
    all_matnr = pool["Matnr"].to_list()
    n_global = round(len(all_matnr) * cfg.global_matnr_share)
    shuffled = list(rng.permutation(all_matnr))
    global_matnr = shuffled[:n_global]
    local_chunks = np.array_split(np.array(shuffled[n_global:]), len(cfg.plants))

    return {
        plant.werks: global_matnr + list(chunk)
        for plant, chunk in zip(cfg.plants, local_chunks, strict=True)
    }


def assign_customers(
    cfg: GeneratorConfig,
    rng: np.random.Generator,
) -> tuple[dict[str, list[str]], dict[tuple[str, str], bool]]:
    """
    Clientes por planta y marca de ruta problema (planta × cliente).
    La merma se concentra por ruta: ahí se ve en mart_rutas_rotas.
    """
    c = cfg.customers
    universe = [f"CUST-{i:04d}" for i in range(1, c.global_count + 1)]

    by_plant: dict[str, list[str]] = {}
    problem: dict[tuple[str, str], bool] = {}
    for plant in cfg.plants:
        n = int(rng.integers(c.per_plant_min, c.per_plant_max + 1))
        kunnrs = [str(k) for k in rng.choice(universe, size=n, replace=False)]
        by_plant[plant.werks] = kunnrs
        flags = rng.random(n) < cfg.loss.problem_account_share
        for k, f in zip(kunnrs, flags, strict=True):
            problem[(plant.werks, k)] = bool(f)
    return by_plant, problem


def build_date_range(cfg: GeneratorConfig) -> list[date]:
    """Días hábiles del horizonte que termina en reference_date."""
    end = cfg.reference_date
    start = end - timedelta(days=cfg.horizon_months * 30)
    return [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
    ]


def reconciliation_dates(cfg: GeneratorConfig) -> list[date]:
    """Fines de mes cada reconciliation_months, alineados a reference_date."""
    out: list[date] = []
    y, m = cfg.reference_date.year, cfg.reference_date.month
    start = cfg.reference_date - timedelta(days=cfg.horizon_months * 30)
    while True:
        first_next = date(y + (m == 12), m % 12 + 1, 1)
        eom = first_next - timedelta(days=1)
        if eom < start:
            break
        out.append(eom)
        m -= cfg.reconciliation_months
        while m <= 0:
            m += 12
            y -= 1
    return sorted(out)


# ---------------------------------------------------------------------------
# Emisión por planta
# ---------------------------------------------------------------------------


def _sample_menge(
    cfg: GeneratorConfig,
    tipos: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Geométrica truncada: valores bajos frecuentes, cola corta hasta max."""
    out = np.empty(len(tipos), dtype=np.int64)
    for mat_type in MaterialType:
        mask = tipos == mat_type.value
        r = cfg.menge.for_type(mat_type)
        span = r.max - r.min
        p = 3 / (span + 3)
        draws = r.min + rng.geometric(p, size=int(mask.sum())) - 1
        out[mask] = np.minimum(draws, r.max)
    return out


def _lognormal_days(cfg: GeneratorConfig, rng: np.random.Generator, n: int) -> np.ndarray:
    mu = math.log(cfg.cycle.mean_days) - 0.5 * cfg.cycle.sigma**2
    raw = rng.lognormal(mean=mu, sigma=cfg.cycle.sigma, size=n)
    return np.round(np.clip(raw, 1, cfg.cycle.cap_days)).astype(np.int64)


def _sample_lag_days(cfg: GeneratorConfig, rng: np.random.Generator, n: int) -> np.ndarray:
    """Días entre Budat y Cpudt: 92% mismo día, 6% 1-2 días, 2% de 3 a 9."""
    lag = cfg.cpudt_lag
    cat = rng.choice([0, 1, 2], size=n, p=[lag.same_day, lag.one_to_two_days, lag.over_48h])
    return np.where(cat == 0, 0, np.where(cat == 1, rng.integers(1, 3, n), rng.integers(3, 10, n)))


def _next_business_day(d: np.ndarray) -> np.ndarray:
    return np.busday_offset(d, 0, roll="forward")


def emit_plant_movements(
    werks: str,
    plant_matnrs: list[str],
    kunnrs: list[str],
    problem: dict[tuple[str, str], bool],
    pool: pl.DataFrame,
    dates: list[date],
    recon: list[date],
    cfg: GeneratorConfig,
    rng: np.random.Generator,
    n_movements: int,
) -> pl.DataFrame:
    """Movimientos MB51 de una planta: ruido operativo + ciclo con cliente."""
    tipo_by_matnr = dict(zip(pool["Matnr"], pool["tipo"], strict=True))
    matnr_arr = np.array(plant_matnrs)
    tipo_arr = np.array([tipo_by_matnr[m] for m in plant_matnrs])

    # Rack dedicado a un cliente de la planta; KLT y cartón van a cualquiera.
    dedicated = {
        m: str(rng.choice(kunnrs))
        for m, t in zip(plant_matnrs, tipo_arr, strict=True)
        if t == MaterialType.RACK.value
    }

    idx = rng.integers(0, len(matnr_arr), n_movements)
    matnr = matnr_arr[idx]
    tipo = tipo_arr[idx]
    budat = np.array(dates, dtype="datetime64[D]")[rng.integers(0, len(dates), n_movements)]
    kind = rng.choice(_KINDS, size=n_movements, p=_KIND_PROBS)
    menge = _sample_menge(cfg, tipo, rng)
    doc_id = np.arange(n_movements, dtype=np.int64)

    bwart = kind.astype(object)
    ship = kind == "SHIP"
    bwart[ship & (tipo == MaterialType.CARTON.value)] = "601"
    bwart[ship & (tipo != MaterialType.CARTON.value)] = "621"
    bwart = bwart.astype(str)

    random_kunnr = rng.choice(kunnrs, size=n_movements)
    rack_ship = ship & (tipo == MaterialType.RACK.value)
    kunnr = [
        dedicated[m] if r else (k if s else None)
        for m, k, s, r in zip(matnr, random_kunnr, ship, rack_ship, strict=True)
    ]

    base = pl.DataFrame(
        {
            "doc_id": doc_id,
            "Zeile": np.ones(n_movements, dtype=np.int64),
            "Matnr": matnr,
            "tipo": tipo,
            "Bwart": bwart,
            "Budat": budat,
            "Menge": menge,
            "Kunnr": pl.Series(kunnr, dtype=pl.String),
            "lag_days": _sample_lag_days(cfg, rng, n_movements),
        }
    )

    # Traslados en pareja: posición 1 sale, posición 2 entra.
    transfers = base.filter(pl.col("Bwart").is_in(list(_TRANSFERS)))
    out_leg = transfers.with_columns(-pl.col("Menge"))
    in_leg = transfers.with_columns(pl.lit(2, dtype=pl.Int64).alias("Zeile"))
    others = base.filter(~pl.col("Bwart").is_in(list(_TRANSFERS)))

    # Ciclo 621 → 622 con merma por contenedor según la ruta.
    s621 = others.filter(pl.col("Bwart") == "621")
    is_problem = np.array(
        [problem[(werks, k)] for k in s621["Kunnr"].to_list()], dtype=bool
    )
    p_loss = np.where(is_problem, cfg.loss.rate_high, cfg.loss.rate_low)
    cutoff = np.datetime64(cfg.reference_date)
    budat_621 = s621["Budat"].to_numpy().astype("datetime64[D]")
    # Un 621 registrado después del corte no existe a la fecha de extracción.
    # Su 622 o 702 tampoco: SAP no deja recoger stock especial V que no se ha contabilizado.
    vivo = budat_621 + s621["lag_days"].to_numpy().astype("timedelta64[D]") <= cutoff
    m = s621["Menge"].to_numpy()
    lost = np.where(vivo, rng.binomial(m, p_loss), 0)
    returned = np.where(vivo, m - lost, 0)
    ret_date = _next_business_day(budat_621 + _lognormal_days(cfg, rng, len(m)))
    returns = (
        s621.select("Matnr", "tipo", "Kunnr")
        .with_columns(
            pl.Series("Budat", ret_date),
            pl.Series("Menge", returned),
        )
        .filter((pl.col("Menge") > 0) & (pl.col("Budat") <= cutoff))
        .group_by("Matnr", "tipo", "Kunnr", "Budat", maintain_order=True)
        .agg(pl.col("Menge").sum())
        .with_columns(pl.lit("622").alias("Bwart"))
    )

    # Faltante: se reconoce en la primera conciliación con al menos 120 días de antigüedad.
    recon_arr = np.array(recon, dtype="datetime64[D]")
    due = s621["Budat"].to_numpy().astype("datetime64[D]") + np.timedelta64(_OVERDUE_DAYS, "D")
    pos = np.searchsorted(recon_arr, due, side="left")
    has_recon = pos < len(recon_arr)
    recog = np.where(has_recon, recon_arr[np.minimum(pos, len(recon_arr) - 1)], cutoff)
    shortages = (
        s621.select("Matnr", "tipo", "Kunnr")
        .with_columns(
            pl.Series("Budat", recog),
            pl.Series("Menge", lost),
            pl.Series("has_recon", has_recon),
        )
        .filter((pl.col("Menge") > 0) & pl.col("has_recon"))
        .group_by("Matnr", "tipo", "Kunnr", "Budat", maintain_order=True)
        .agg(pl.col("Menge").sum())
        .with_columns(pl.lit("702").alias("Bwart"))
    )

    next_id = n_movements
    cycle_rows = pl.concat([returns, shortages], how="vertical_relaxed")
    cycle_rows = cycle_rows.with_columns(
        pl.int_range(next_id, next_id + cycle_rows.height, dtype=pl.Int64).alias("doc_id"),
        pl.lit(1, dtype=pl.Int64).alias("Zeile"),
        pl.Series("lag_days", _sample_lag_days(cfg, rng, cycle_rows.height)),
    )

    cols = ["doc_id", "Zeile", "Matnr", "tipo", "Bwart", "Budat", "Menge", "Kunnr", "lag_days"]
    df = pl.concat(
        [others.select(cols), out_leg.select(cols), in_leg.select(cols), cycle_rows.select(cols)],
        how="vertical_relaxed",
    )

    n = df.height
    hours = rng.integers(6, 22, n)
    minutes = rng.integers(0, 60, n)
    ref = rng.integers(10_000_000, 99_999_999, n)

    df = df.with_columns(
        pl.lit(werks).alias("Werks"),
        (pl.col("Budat") + pl.duration(days=pl.col("lag_days"))).alias("Cpudt"),
        pl.format(
            "{}:{}:00",
            pl.Series(hours).cast(pl.String).str.zfill(2),
            pl.Series(minutes).cast(pl.String).str.zfill(2),
        ).alias("Cputm"),
        pl.Series("_ref", ref),
    ).with_columns(
        # Un documento se registra una sola vez: ambas posiciones comparten hora y fecha.
        pl.col("Cpudt").first().over("doc_id"),
        pl.col("Cputm").first().over("doc_id"),
        pl.col("_ref").first().over("doc_id"),
    ).with_columns(
        pl.when(pl.col("Bwart").is_in(["601", "621"])).then(pl.lit("EXPE"))
        .when(pl.col("Bwart").is_in(["622", "702"])).then(pl.lit("RECP"))
        .when(pl.col("Bwart").is_in(list(_TRANSFERS)) & (pl.col("Zeile") == 1))
        .then(pl.lit("TR01"))
        .when(pl.col("Bwart").is_in(list(_TRANSFERS))).then(pl.lit("TR02"))
        .otherwise(pl.lit("RM01"))
        .alias("Lgort"),
        pl.when(pl.col("Bwart").is_in(["101", "102", "501", "502"]))
        .then(pl.format("PROV-{}", (pl.col("_ref") % 9000 + 1000).cast(pl.String)))
        .alias("Lifnr"),
        pl.when(pl.col("Bwart").is_in(["601", "621"]))
        .then(pl.format("80{}", pl.col("_ref").cast(pl.String)))
        .when(pl.col("Bwart") == "622")
        .then(pl.format("84{}", pl.col("_ref").cast(pl.String)))
        .when(pl.col("Bwart") == "702")
        .then(pl.format("INV-{}", pl.col("Budat").dt.strftime("%Y%m")))
        .otherwise(pl.format("REF-{}", (pl.col("_ref") % 900_000 + 100_000).cast(pl.String)))
        .alias("Xblnr"),
        pl.when(pl.col("Bwart").is_in(list(_NEGATIVE)))
        .then(-pl.col("Menge").abs())
        .when(pl.col("Bwart").is_in(list(_TRANSFERS)))
        .then(pl.col("Menge"))
        .otherwise(pl.col("Menge").abs())
        .alias("Menge"),
    )
    return df.drop("_ref", "lag_days")


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------


def _assign_document_numbers(
    df: pl.DataFrame,
    offsets: dict[int, int],
) -> pl.DataFrame:
    """
    Mblnr = 49 + 8 dígitos, secuencial por año contable. Las parejas de traslado
    comparten documento. offsets lleva el último número usado por año para que
    la numeración siga de una planta a la siguiente sin repetirse.
    """
    df = (
        df.sort(["Mjahr", "Budat", "doc_id", "Zeile"])
        .with_columns(
            (pl.col("doc_id") != pl.col("doc_id").shift(1))
            .fill_null(True)
            .cum_sum()
            .over("Mjahr")
            .alias("_seq")
        )
        .with_columns(
            pl.col("_seq")
            + pl.col("Mjahr").replace_strict(offsets, default=0, return_dtype=pl.Int64)
        )
    )
    for year, last in df.group_by("Mjahr").agg(pl.col("_seq").max()).iter_rows():
        offsets[year] = int(last)

    return df.with_columns(
        pl.format("49{}", pl.col("_seq").cast(pl.String).str.zfill(8)).alias("Mblnr"),
        pl.col("Zeile").cast(pl.String).str.zfill(4),
    ).drop("_seq", "doc_id")


_OUTPUT_COLUMNS = [
    "Werks", "Lgort", "Matnr", "Maktx", "Bwart", "Mjahr", "Budat", "Cpudt", "Cputm",
    "Menge", "Meins", "Mblnr", "Zeile", "Lifnr", "Kunnr", "Xblnr", "Costo_usd",
]


def generate(
    cfg: GeneratorConfig | None = None,
    output_dir: str = "data/raw",
) -> pl.LazyFrame:
    """
    Genera el dataset MB51 y lo escribe como un Parquet por planta
    (mb51_<Werks>.parquet). Cada planta se escribe y se libera antes de la
    siguiente: el dataset completo no cabe en memoria en un laptop.
    Devuelve un LazyFrame sobre los archivos escritos.
    """
    cfg = cfg or GeneratorConfig()
    rng = np.random.default_rng(cfg.random_seed)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # El directorio es del generador: una corrida no se mezcla con restos de otra.
    for old in out.glob("mb51_*.parquet"):
        old.unlink()

    pool = build_matnr_pool(cfg)
    assignment = assign_matnr_to_plants(cfg, pool, rng)
    customers, problem = assign_customers(cfg, rng)
    dates = build_date_range(cfg)
    recon = reconciliation_dates(cfg)
    offsets: dict[int, int] = {}
    total_rows = 0

    for plant in cfg.plants:
        monthly = int(rng.integers(plant.monthly_movements_min, plant.monthly_movements_max))
        df = emit_plant_movements(
            werks=plant.werks,
            plant_matnrs=assignment[plant.werks],
            kunnrs=customers[plant.werks],
            problem=problem,
            pool=pool,
            dates=dates,
            recon=recon,
            cfg=cfg,
            rng=rng,
            n_movements=monthly * cfg.horizon_months,
        )
        df = (
            df.join(pool.select("Matnr", "Maktx", "Costo_usd"), on="Matnr", how="left")
            .with_columns(
                pl.col("Budat").cast(pl.Date),
                pl.col("Cpudt").cast(pl.Date),
                pl.col("Budat").dt.year().cast(pl.Int64).alias("Mjahr"),
                pl.col("Menge").cast(pl.Int64),
                pl.lit("PC").alias("Meins"),
            )
            # Documentos registrados después del corte todavía no existen
            # a la fecha de extracción.
            .filter(pl.col("Cpudt") <= cfg.reference_date)
        )
        df = (
            _assign_document_numbers(df, offsets)
            .select(_OUTPUT_COLUMNS)
            .sort(["Budat", "Mblnr", "Zeile"])
        )
        df.write_parquet(out / f"mb51_{plant.werks}.parquet")
        total_rows += df.height
        print(f"  {plant.werks}: {df.height:,} filas")
        del df

    print(f"Parquet escrito en {out}: {len(cfg.plants)} archivos, {total_rows:,} filas")
    return pl.scan_parquet(out / "mb51_*.parquet")
