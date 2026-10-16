"""
Arnés de impacto por defecto (ADR-028, punto 11; ADR-031).

Corre el dataset limpio y después cada defecto solo, a la tasa del catálogo y
en el techo de su rango, y mide cuánto mueve cada cifra publicada, qué
identidad rompe, qué reglas se disparan y cuánto de la bitácora reporta la
regla del defecto. Escribe docs/calidad/impacto_defectos.csv, que el repo
versiona y mart_impacto_defectos publica.

El defecto se inyecta sobre el limpio ya escrito, con el MB51 en el orden en
que lo inyecta el generador: sale igual que con --defectos y no hay que
regenerar 21M de filas por corrida. Cada corrida parte de una copia de la base
limpia y reconstruye solo los modelos que dependen de lo que cambió.

Uso:
    uv run python -m rpi.calidad                          # 18 defectos, tasa y techo
    uv run python -m rpi.calidad --defectos D05,D13 --niveles tasa
    uv run python -m rpi.calidad --months 18 --plants 2 --country MX --salida data/calidad/ci.csv
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import polars as pl

from rpi.config import DEFECTOS, TECHO_DEFECTOS, GeneratorConfig
from rpi.db import carga, ingest
from rpi.defectos import inyecta
from rpi.generator import INSTRUCCION, MAESTRO, PARTES, PLAN, STOCK_INICIAL

DIR = Path("data/calidad")
# dbt del mismo entorno que corre el arnés: Scripts\dbt.exe en Windows, bin/dbt en Linux.
DBT = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
SALIDA = Path("docs/calidad/impacto_defectos.csv")

# Tabla de cada defecto en el generador → tabla raw y archivo.
TABLAS = {
    "stock": ("raw_stock_inicial", STOCK_INICIAL),
    "partes": ("raw_partes", PARTES),
    "instruccion": ("raw_instruccion_empaque", INSTRUCCION),
    "plan": ("raw_plan_produccion", PLAN),
    "maestro": ("raw_maestro_materiales", MAESTRO),
}

# Las siete cifras del seed cifras que el arnés mide (medida_en_arnes).
CIFRAS = {
    "perdida": "select sum(perdida_usd) from mart_perdidas_usd",
    "tco": "select sum(ahorro_neto_usd) from mart_tco_comparativo",
    "brecha": "select sum(usd_flete + usd_compra + usd_desechable) from mart_brecha_flota",
    "ocioso": "select sum(usd_capital_ocioso) from mart_brecha_flota",
    "ciclo": "select ciclo_promedio_dias from mart_ciclo_cohortes where nivel = 'flota'",
    "necesidad": """
        select sum(necesidad) from mart_necesidad_flota
        where semana = (select min(semana) from mart_necesidad_flota)
    """,
    "flota": """
        select sum(flota) from mart_flota_semanal
        where fecha_cierre = (select max(fecha_cierre) from mart_flota_semanal)
    """,
}
# Modelos que el arnés construye, en dos etapas: los que publican las cifras y
# después las reglas. Juntas, int_calidad_mb51 corre en paralelo con
# int_stock_diario y con D02 en el techo DuckDB se queda sin los 4 GB del
# perfil.
ETAPAS = [
    [
        "mart_perdidas_usd",
        "mart_tco_comparativo",
        "mart_brecha_flota",
        "mart_ciclo_cohortes",
        "mart_necesidad_flota",
        "mart_flota_semanal",
    ],
    ["int_calidad_violaciones"],
]

# Identidades: la llave se cuenta en staging; las otras tres son los tests de
# síntoma que ya existen (ADR-028, punto 7).
LLAVE_MB51 = """
    select count(*) - count(distinct (planta, anio_contable, doc_material, posicion))
    from stg_mb51
"""
TESTS_IDENTIDAD = {
    "stock": "assert_stock_no_negativo",
    "saldo": "assert_saldo_cliente_no_negativo",
    "conservacion": "assert_conservacion_flota",
}

# Llave con la que la bitácora y las violaciones se encuentran, por defecto.
LINEA = ["planta", "anio_contable", "doc_material", "posicion"]
MATERIAL = ["planta", "material"]
PARTE = ["planta", "parte"]
LLAVE = {
    **dict.fromkeys(["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08"], LINEA),
    **dict.fromkeys(["D09", "D13", "D14", "D15", "D16", "D17", "D18"], MATERIAL),
    **dict.fromkeys(["D10", "D11", "D12"], PARTE),
}

COLUMNAS = {
    "defecto": pl.String,
    "nivel": pl.String,
    "parametro": pl.String,
    "casos": pl.Int64,
    "detectados": pl.Int64,
    "segundos": pl.Int64,
    "tipo": pl.String,
    "medida": pl.String,
    "valor": pl.Float64,
    "usd_expuesto": pl.Float64,
    "plantas": pl.Int64,
    "meses": pl.Int64,
    "seed": pl.Int64,
}


def _dbt(args: list[str], db: Path) -> subprocess.CompletedProcess:
    # target aparte: el arnés no pisa el manifest que lee test_readme.
    env = os.environ | {"RPI_DB": str(db), "DO_NOT_TRACK": "1"}
    return subprocess.run(
        [str(DBT), *args, "--profiles-dir", "."]
        + ["--target-path", str(DIR / "target"), "--quiet"],
        env=env,
        capture_output=True,
        text=True,
    )


def seleccion(fuentes: list[str], objetivos: list[str]) -> list[str]:
    """Modelos que dependen de lo que cambió y llevan a alguno de los objetivos."""
    return [f"source:raw.{f}+,+{m}" for f in fuentes for m in objetivos]


def _construye(db: Path, fuentes: list[str] | None = None) -> subprocess.CompletedProcess:
    """Corre las etapas; sin fuentes, todo el linaje de los objetivos."""
    for objetivos in ETAPAS:
        sel = [f"+{m}" for m in objetivos] if fuentes is None else seleccion(fuentes, objetivos)
        r = _dbt(["run", "--select", *sel], db)
        if r.returncode:
            return r
    return r


def bitacora_llaves(bitacora: pl.DataFrame) -> pl.DataFrame:
    return bitacora.select(
        "defecto",
        pl.col("Werks").alias("planta"),
        pl.col("Matnr").alias("material"),
        pl.col("Mjahr").alias("anio_contable"),
        pl.col("Mblnr").alias("doc_material"),
        pl.col("Zeile").cast(pl.Int32).alias("posicion"),
        pl.col("Parte").alias("parte"),
    )


def sin_reportar(bitacora: pl.DataFrame, violaciones: pl.DataFrame, defecto: str) -> int:
    """Casos de la bitácora del defecto que la regla de ese defecto no reporta."""
    llave = LLAVE[defecto]
    inyectado = bitacora.filter(pl.col("defecto") == defecto).select(llave).unique()
    reportado = violaciones.filter(pl.col("defecto") == defecto).select(llave).unique()
    return inyectado.join(reportado, on=llave, how="anti", nulls_equal=True).height


def _medidas(db: Path) -> tuple[dict[str, float | None], dict[str, int], pl.DataFrame]:
    """Cifras, identidades y violaciones de una base ya construida."""
    _dbt(["test", "--select", *TESTS_IDENTIDAD.values()], db)
    resultados = json.loads((DIR / "target" / "run_results.json").read_text(encoding="utf-8"))
    fallas = {r["unique_id"].split(".")[2]: r["failures"] for r in resultados["results"]}
    con = duckdb.connect(str(db), read_only=True)
    cifras = {}
    for k, sql in CIFRAS.items():
        # Nula si el mart queda sin la fila: D06 en el techo deja sin cohortes completas.
        fila = con.execute(sql).fetchone()
        cifras[k] = None if fila is None or fila[0] is None else round(float(fila[0]), 2)
    identidades = {"llave": con.execute(LLAVE_MB51).fetchone()[0]}
    identidades |= {k: fallas.get(t) for k, t in TESTS_IDENTIDAD.items()}
    violaciones = con.execute(
        """
        select regla, defecto, planta, material, anio_contable, doc_material, posicion,
               parte, usd_expuesto
        from int_calidad_violaciones
        """
    ).pl()
    con.close()
    return cifras, identidades, violaciones


def inyecta_limpio(
    limpio: Path, destino: Path, cfg: GeneratorConfig
) -> tuple[dict[str, Path], pl.DataFrame]:
    """
    Aplica los defectos de cfg a un directorio limpio ya escrito y escribe en
    destino solo las tablas que cambiaron. Devuelve tabla raw → archivo y la
    bitácora. El MB51 vuelve al orden en que el generador inyecta (año,
    documento, posición): así la selección de objetivos es la misma que con
    --defectos.
    """
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("*.parquet"):
        viejo.unlink()
    otras = {k: pl.read_parquet(limpio / f) for k, (_, f) in TABLAS.items()}
    sucias: dict[str, list[pl.DataFrame]] = {k: [] for k in TABLAS}
    cambio = dict.fromkeys(["mb51", *TABLAS], False)
    bitacoras = []
    paises: set[str] = set()
    for idx, planta in enumerate(cfg.plants):
        mb51 = pl.read_parquet(limpio / f"mb51_{planta.werks}.parquet").sort(
            "Mjahr", "Mblnr", "Zeile"
        )
        tablas = {"mb51": mb51} | {
            k: df.filter(pl.col("Werks") == planta.werks) for k, df in otras.items()
        }
        salida, bitacora = inyecta(
            tablas,
            cfg.defectos,
            planta,
            planta.country not in paises,
            cfg.reference_date,
            cfg.random_seed,
            idx,
        )
        paises.add(planta.country)
        bitacoras.append(bitacora)
        for k in sucias:
            sucias[k].append(salida[k])
            cambio[k] |= not salida[k].equals(tablas[k])
        # MB51 se escribe planta por planta, como en el generador: las 14 juntas
        # no caben en 8 GB. Se escribe siempre y se borra si ninguna cambió.
        cambio["mb51"] |= not salida["mb51"].equals(mb51)
        salida["mb51"].sort("Budat", "Mblnr", "Zeile").write_parquet(
            destino / f"mb51_{planta.werks}.parquet"
        )
        del mb51, tablas, salida

    archivos: dict[str, Path] = {}
    if cambio["mb51"]:
        archivos["raw_mb51"] = destino / "mb51_*.parquet"
    else:
        for f in destino.glob("mb51_*.parquet"):
            f.unlink()
    for k, (tabla, archivo) in TABLAS.items():
        if cambio[k]:
            df = pl.concat(sucias[k])
            df = df.sort("Werks", "Matnr") if k == "maestro" else df
            df.write_parquet(destino / archivo)
            archivos[tabla] = destino / archivo
    return archivos, pl.concat(bitacoras)


def _filas(corrida: dict, cifras: dict, identidades: dict, violaciones: pl.DataFrame) -> list:
    filas = [corrida | {"tipo": "cifra", "medida": k, "valor": v} for k, v in cifras.items()]
    filas += [
        corrida | {"tipo": "identidad", "medida": k, "valor": v} for k, v in identidades.items()
    ]
    por_regla = violaciones.group_by("regla").agg(
        pl.len().alias("valor"), pl.col("usd_expuesto").sum().round(2).alias("usd_expuesto")
    )
    filas += [
        corrida
        | {"tipo": "regla", "medida": r["regla"], "valor": r["valor"]}
        | {"usd_expuesto": r["usd_expuesto"] if r["usd_expuesto"] else None}
        for r in por_regla.sort("regla").iter_rows(named=True)
    ]
    return filas


def corre(
    defectos: list[str], niveles: list[str], limpio: Path, salida: Path, cfg: GeneratorConfig
) -> pl.DataFrame:
    faltan = [p.werks for p in cfg.plants if not (limpio / f"mb51_{p.werks}.parquet").exists()]
    if faltan:
        sys.exit(f"{limpio} no es el dataset de estas opciones: faltan {faltan}")
    meta = {"plantas": len(cfg.plants), "meses": cfg.horizon_months, "seed": cfg.random_seed}
    # Mismo nombre de archivo en las dos bases: DuckDB guarda el catálogo (el
    # nombre del archivo) en la definición de las vistas de staging.
    base = DIR / "limpio" / "arnes.duckdb"
    db = DIR / "corrida" / "arnes.duckdb"
    base.parent.mkdir(parents=True, exist_ok=True)
    db.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    base.unlink(missing_ok=True)
    ingest(base, limpio)
    _dbt(["seed", "--full-refresh"], base)
    r = _construye(base)
    if r.returncode:
        sys.exit(f"dbt run del limpio falló:\n{r.stdout}")
    cifras, identidades, violaciones = _medidas(base)
    corrida = {"nivel": "limpio", "casos": 0, "segundos": round(time.perf_counter() - t0)}
    filas = _filas(corrida | meta, cifras, identidades, violaciones)
    limpias = cifras
    print(f"limpio: {corrida['segundos']} s")

    for defecto in defectos:
        for nivel in niveles:
            t = time.perf_counter()
            ajuste = TECHO_DEFECTOS[defecto] if nivel == "techo" else {}
            datos = cfg.model_dump()
            datos["defectos"] = datos["defectos"] | ajuste | {"activos": [defecto]}
            archivos, bitacora = inyecta_limpio(
                limpio, DIR / "raw", GeneratorConfig.model_validate(datos)
            )
            shutil.copyfile(base, db)
            con = duckdb.connect(str(db))
            for tabla, archivo in archivos.items():
                carga(con, tabla, archivo)
            con.close()
            llaves = bitacora_llaves(bitacora)
            corrida = {
                "defecto": defecto,
                "nivel": nivel,
                "parametro": ", ".join(f"{k}={v}" for k, v in ajuste.items()) or "catálogo",
                "casos": llaves.select(LLAVE[defecto]).unique().height,
            }
            r = _construye(db, list(archivos))
            if r.returncode:
                # Que un defecto tumbe el pipeline también es un resultado.
                corrida["segundos"] = round(time.perf_counter() - t)
                filas.append(corrida | meta | {"tipo": "error", "medida": "dbt_run", "valor": 1})
                print(f"{defecto} {nivel}: dbt run falló\n{r.stdout[-1500:]}")
                continue
            cifras, identidades, violaciones = _medidas(db)
            corrida["detectados"] = corrida["casos"] - sin_reportar(llaves, violaciones, defecto)
            corrida["segundos"] = round(time.perf_counter() - t)
            filas += _filas(corrida | meta, cifras, identidades, violaciones)
            mueve = ", ".join(
                f"{k} sin valor" if v is None else f"{k} {100 * (v / limpias[k] - 1):+.2f}%"
                for k, v in cifras.items()
            )
            print(
                f"{defecto} {nivel}: {corrida['casos']} casos, {corrida['detectados']} "
                f"detectados, {corrida['segundos']} s, {mueve}"
            )
            pl.DataFrame(filas, schema=COLUMNAS).write_csv(DIR / "impacto_parcial.csv")

    df = pl.DataFrame(filas, schema=COLUMNAS)
    salida.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(salida, float_precision=2)
    print(f"{salida}: {df.height} filas, {round(time.perf_counter() - t0)} s")
    return df


def main(argv: list[str] | None = None) -> None:
    from rpi.__main__ import build_config

    p = argparse.ArgumentParser(prog="python -m rpi.calidad", description=__doc__.split("\n")[1])
    p.add_argument("--defectos", default="todos", help="'todos' o IDs separados por coma.")
    p.add_argument("--niveles", default="tasa,techo", help="tasa, techo o los dos.")
    p.add_argument("--limpio", default="data/raw", help="Dataset limpio ya generado.")
    p.add_argument("--salida", default=str(SALIDA))
    p.add_argument("--months", type=int, default=None)
    p.add_argument("--plants", type=int, default=None)
    p.add_argument("--country", default=None, choices=["MX", "US", "NI"])
    p.add_argument("--seed", type=int, default=None)
    a = p.parse_args(argv)
    cfg = build_config(
        argparse.Namespace(
            months=a.months,
            plants=a.plants,
            country=a.country,
            loss_rate=None,
            seed=a.seed,
            defectos=None,
        )
    )
    defectos = list(DEFECTOS) if a.defectos == "todos" else a.defectos.upper().split(",")
    corre(defectos, a.niveles.split(","), Path(a.limpio), Path(a.salida), cfg)


if __name__ == "__main__":
    main()
