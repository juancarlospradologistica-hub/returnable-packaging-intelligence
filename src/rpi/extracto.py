"""
Adaptador de extracto real (ADR-035): un MB51 bajado de SAP al contrato de
entrada del pipeline, el mismo que escribe el generador.

Cambia nombres, formatos y signo; no corrige datos. Un Matnr con ceros a la
izquierda o una fecha después del corte pasan como vienen y los ven sus reglas
(ADR-034): normalizarlos aquí escondería justo lo que Fase 4 detecta.

El extracto es un CSV con los campos técnicos de MSEG y MKPF (MATNR, WERKS,
BWART, SHKZG...), que son iguales en cualquier SAP sin importar el idioma del
usuario. Un archivo con otros encabezados se mapea con --columnas. Los formatos
por default son los de usuario estándar de SAP: fecha DD.MM.AAAA y notación
decimal 1.234.567,89.

Uso:
    uv run python -m rpi.extracto mb51 data/extracto/MB51.csv
    uv run python -m rpi.extracto mb51 MB51.csv --decimal . --fecha %m/%d/%Y --columnas mapeo.csv
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import polars as pl

SALIDA = Path("data/extracto/raw")
UNIDADES = Path("seeds/unidades_extracto.csv")

# Campo técnico SAP → columna del contrato. SHKZG, DMBTR y WAERS no tienen
# columna propia: dan el signo de Menge y el precio del documento.
CONTRATO = {
    "WERKS": "Werks",
    "LGORT": "Lgort",
    "MATNR": "Matnr",
    "MAKTX": "Maktx",
    "BWART": "Bwart",
    "MJAHR": "Mjahr",
    "BUDAT": "Budat",
    "CPUDT": "Cpudt",
    "CPUTM": "Cputm",
    "MENGE": "Menge",
    "MEINS": "Meins",
    "MBLNR": "Mblnr",
    "ZEILE": "Zeile",
    "LIFNR": "Lifnr",
    "KUNNR": "Kunnr",
    "XBLNR": "Xblnr",
}
OBLIGATORIOS = [
    "WERKS", "MATNR", "MAKTX", "BWART", "BUDAT", "CPUDT", "CPUTM",
    "MENGE", "MEINS", "MBLNR", "ZEILE",
]  # fmt: skip
OPCIONALES = ["LGORT", "MJAHR", "LIFNR", "KUNNR", "XBLNR", "SHKZG", "DMBTR", "WAERS"]


def _texto(campo: str) -> pl.Expr:
    # Un campo vacío en el CSV es nulo, no una cadena vacía.
    limpio = pl.col(campo).str.strip_chars()
    return pl.when(limpio == "").then(None).otherwise(limpio)


def _numero(campo: str, decimal: str) -> pl.Expr:
    """'1.234,50' o '1,234.50' según la notación; '5-' con el signo atrás, como en el ALV."""
    miles = "." if decimal == "," else ","
    t = _texto(campo).str.replace_all(miles, "", literal=True)
    if decimal == ",":
        t = t.str.replace(",", ".", literal=True)
    negativo = t.str.ends_with("-")
    valor = t.str.strip_suffix("-").cast(pl.Float64)
    return pl.when(negativo).then(-valor).otherwise(valor)


def lee_columnas(archivo: Path | None) -> dict[str, str]:
    """Encabezado del archivo → campo técnico SAP. Sin archivo, los nombres técnicos."""
    if archivo is None:
        return {}
    mapeo = pl.read_csv(archivo, infer_schema=False)
    return dict(zip(mapeo["columna"], mapeo["campo"].str.to_uppercase(), strict=True))


def lee_unidades(archivo: Path = UNIDADES) -> dict[str, str]:
    unidades = pl.read_csv(archivo, infer_schema=False)
    return dict(zip(unidades["unidad"], unidades["meins"], strict=True))


def contrato_mb51(
    crudo: pl.LazyFrame, unidades: dict[str, str], decimal: str, fecha: str
) -> pl.LazyFrame:
    """Columnas técnicas de SAP, como texto, a las 17 columnas del contrato MB51."""
    campos = set(crudo.collect_schema().names())
    faltan = [c for c in OBLIGATORIOS if c not in campos]
    if faltan:
        raise ValueError(f"Faltan campos obligatorios en el extracto: {', '.join(faltan)}")
    crudo = crudo.with_columns(
        pl.lit(None, dtype=pl.String).alias(c) for c in OPCIONALES if c not in campos
    )

    cantidad = _numero("MENGE", decimal)
    # Con SHKZG la cantidad viene sin signo: H (haber) es salida. Sin SHKZG, el
    # signo viene en la cantidad, como en el ALV de MB51.
    menge = (
        pl.when(_texto("SHKZG") == "H")
        .then(-cantidad.abs())
        .when(_texto("SHKZG") == "S")
        .then(cantidad.abs())
        .otherwise(cantidad)
    )
    # HHMMSS, como lo guarda SAP, o HH:MM:SS: el contrato guarda HH:MM:SS.
    hora = (
        _texto("CPUTM")
        .str.replace_all(":", "", literal=True)
        .str.zfill(6)
        .str.replace(r"^(\d{2})(\d{2})(\d{2})$", "$1:$2:$3")
    )
    budat = _texto("BUDAT").str.to_date(fecha)
    # Precio del documento solo si viene en USD; un LEIH estándar no lleva
    # importe y el contrato lo deja nulo (ADR-028).
    costo = (
        pl.when((_texto("WAERS") == "USD") & (_numero("DMBTR", decimal) > 0))
        .then((_numero("DMBTR", decimal) / cantidad.abs()).round(2))
        .otherwise(None)
    )
    return crudo.select(
        _texto("WERKS").alias("Werks"),
        _texto("LGORT").alias("Lgort"),
        _texto("MATNR").alias("Matnr"),
        _texto("MAKTX").alias("Maktx"),
        _texto("BWART").alias("Bwart"),
        pl.coalesce(_texto("MJAHR").cast(pl.Int64), budat.dt.year().cast(pl.Int64)).alias("Mjahr"),
        budat.alias("Budat"),
        _texto("CPUDT").str.to_date(fecha).alias("Cpudt"),
        hora.alias("Cputm"),
        menge.cast(pl.Int64).alias("Menge"),
        # Una unidad fuera del seed pasa como viene y la marca el schema.
        _texto("MEINS").replace(unidades).alias("Meins"),
        _texto("MBLNR").alias("Mblnr"),
        _texto("ZEILE").str.zfill(4).alias("Zeile"),
        _texto("LIFNR").alias("Lifnr"),
        _texto("KUNNR").alias("Kunnr"),
        _texto("XBLNR").alias("Xblnr"),
        costo.cast(pl.Float64).alias("Costo_usd"),
    )


def mb51(
    archivo: Path,
    salida: Path = SALIDA,
    separador: str = ";",
    decimal: str = ",",
    fecha: str = "%d.%m.%Y",
    columnas: Path | None = None,
    unidades: Path = UNIDADES,
) -> list[Path]:
    """
    Escribe un Parquet por planta (mb51_<Werks>.parquet), como el generador.
    El extracto pasa en streaming a un Parquet temporal y de ahí sale cada
    planta con un filtro: la memoria no depende del tamaño del archivo.
    """
    crudo = pl.scan_csv(archivo, separator=separador, infer_schema=False)
    crudo = crudo.rename(lee_columnas(columnas), strict=False)
    lf = contrato_mb51(crudo, lee_unidades(unidades), decimal, fecha)

    salida.mkdir(parents=True, exist_ok=True)
    for viejo in salida.glob("mb51_*.parquet"):
        viejo.unlink()
    escritos = []
    with tempfile.TemporaryDirectory() as tmp:
        todo = Path(tmp) / "mb51.parquet"
        lf.sink_parquet(todo)
        plantas = pl.scan_parquet(todo).select("Werks").unique().collect()["Werks"]
        for werks in sorted(plantas.drop_nulls()):
            destino = salida / f"mb51_{werks}.parquet"
            (
                pl.scan_parquet(todo)
                .filter(pl.col("Werks") == werks)
                .sort("Budat", "Mblnr", "Zeile")
                .sink_parquet(destino)
            )
            escritos.append(destino)
    return escritos


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m rpi.extracto", description=__doc__.split("\n")[1])
    sub = p.add_subparsers(dest="tabla", required=True)
    m = sub.add_parser("mb51", help="MB51 con los campos técnicos de MSEG y MKPF.")
    m.add_argument("archivo", type=Path)
    m.add_argument("--salida", type=Path, default=SALIDA)
    m.add_argument("--separador", default=";")
    m.add_argument("--decimal", default=",", choices=[",", "."])
    m.add_argument("--fecha", default="%d.%m.%Y", help="Formato de fecha (strftime).")
    m.add_argument("--columnas", type=Path, help="CSV columna,campo para otros encabezados.")
    a = p.parse_args(argv)
    escritos = mb51(a.archivo, a.salida, a.separador, a.decimal, a.fecha, a.columnas)
    for f in escritos:
        print(f"{f}: {pl.scan_parquet(f).select(pl.len()).collect().item():,} filas")


if __name__ == "__main__":
    main()
