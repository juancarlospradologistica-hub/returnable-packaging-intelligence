"""
Adaptador de extracto real (ADR-035, ADR-037): MB51, maestro de materiales y
foto de stock bajados de SAP al contrato de entrada del pipeline, el mismo que
escribe el generador.

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
    uv run python -m rpi.extracto maestro data/extracto/maestro.csv
    uv run python -m rpi.extracto foto 30.06.2026 --almacen MARD.csv --cliente MSKU.csv
"""

from __future__ import annotations

import argparse
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl

from rpi.generator import MAESTRO, STOCK_INICIAL

SALIDA = Path("data/extracto/raw")
SEEDS = Path("seeds")
UNIDADES = SEEDS / "unidades_extracto.csv"

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
    t = pl.col(campo).str.replace_all(miles, "", literal=True)
    if decimal == ",":
        t = t.str.replace(",", ".", literal=True)
    valor = t.str.strip_suffix("-").cast(pl.Float64)
    return pl.when(t.str.ends_with("-")).then(-valor).otherwise(valor)


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

    # Cada campo se limpia una vez y los derivados salen de la columna limpia.
    lf = crudo.select(_texto(c).alias(c) for c in [*OBLIGATORIOS, *OPCIONALES]).with_columns(
        _numero("MENGE", decimal).alias("_cantidad"),
        _numero("DMBTR", decimal).alias("_importe"),
        pl.col("BUDAT").str.to_date(fecha).alias("_budat"),
    )
    # Con SHKZG la cantidad viene sin signo: H (haber) es salida. Sin SHKZG, el
    # signo viene en la cantidad, como en el ALV de MB51.
    menge = (
        pl.when(pl.col("SHKZG") == "H")
        .then(-pl.col("_cantidad").abs())
        .when(pl.col("SHKZG") == "S")
        .then(pl.col("_cantidad").abs())
        .otherwise(pl.col("_cantidad"))
    )
    # HHMMSS, como lo guarda SAP, o HH:MM:SS: el contrato guarda HH:MM:SS.
    hora = (
        pl.col("CPUTM")
        .str.replace_all(":", "", literal=True)
        .str.zfill(6)
        .str.replace(r"^(\d{2})(\d{2})(\d{2})$", "$1:$2:$3")
    )
    # Precio del documento solo si viene en USD; un LEIH estándar no lleva
    # importe y el contrato lo deja nulo (ADR-028).
    costo = (
        pl.when((pl.col("WAERS") == "USD") & (pl.col("_importe") > 0))
        .then((pl.col("_importe") / pl.col("_cantidad").abs()).round(2))
        .otherwise(None)
    )
    return lf.select(
        pl.col("WERKS").alias("Werks"),
        pl.col("LGORT").alias("Lgort"),
        pl.col("MATNR").alias("Matnr"),
        pl.col("MAKTX").alias("Maktx"),
        pl.col("BWART").alias("Bwart"),
        pl.coalesce(
            pl.col("MJAHR").cast(pl.Int64), pl.col("_budat").dt.year().cast(pl.Int64)
        ).alias("Mjahr"),
        pl.col("_budat").alias("Budat"),
        pl.col("CPUDT").str.to_date(fecha).alias("Cpudt"),
        hora.alias("Cputm"),
        menge.cast(pl.Int64).alias("Menge"),
        # Una unidad fuera del seed pasa como viene y la marca el schema.
        pl.col("MEINS").replace(unidades).alias("Meins"),
        pl.col("MBLNR").alias("Mblnr"),
        pl.col("ZEILE").str.zfill(4).alias("Zeile"),
        pl.col("LIFNR").alias("Lifnr"),
        pl.col("KUNNR").alias("Kunnr"),
        pl.col("XBLNR").alias("Xblnr"),
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

    El CSV pasa en streaming, como texto, a un Parquet temporal; de ahí cada
    planta se convierte y se escribe sola. La memoria la pone la planta más
    grande, no el extracto: convertir los 21M de líneas del completo en un
    solo plan pasaba de 6 GB (ADR-035).
    """
    mapeo = lee_columnas(columnas)
    tabla_unidades = lee_unidades(unidades)
    salida.mkdir(parents=True, exist_ok=True)
    for viejo in salida.glob("mb51_*.parquet"):
        viejo.unlink()
    escritos = []
    with tempfile.TemporaryDirectory() as tmp:
        texto = Path(tmp) / "mb51_texto.parquet"
        crudo = pl.scan_csv(archivo, separator=separador, infer_schema=False)
        crudo.rename(mapeo, strict=False).sink_parquet(texto)
        crudo = pl.scan_parquet(texto)
        contrato_mb51(crudo, tabla_unidades, decimal, fecha)  # falla antes si faltan campos
        werks = _texto("WERKS")
        plantas = crudo.select(werks.unique()).collect().to_series().sort()
        if plantas.has_nulls():
            # Sin centro no hay archivo de planta donde ponerla, y tirarla
            # sería corregir el extracto.
            n = crudo.filter(werks.is_null()).select(pl.len()).collect().item()
            raise ValueError(f"{n:,} líneas del extracto sin WERKS")
        for planta in plantas:
            destino = salida / f"mb51_{planta}.parquet"
            una = crudo.filter(werks == planta)
            contrato_mb51(una, tabla_unidades, decimal, fecha).sort(
                "Budat", "Mblnr", "Zeile"
            ).collect().write_parquet(destino)
            escritos.append(destino)
    return escritos


def _crudo(archivo: Path, separador: str, columnas: Path | None) -> pl.LazyFrame:
    crudo = pl.scan_csv(archivo, separator=separador, infer_schema=False)
    return crudo.rename(lee_columnas(columnas), strict=False)


def _exige(campos: set[str], obligatorios: list[str], que: str) -> None:
    faltan = [c for c in obligatorios if c not in campos]
    if faltan:
        raise ValueError(f"Faltan campos obligatorios en {que}: {', '.join(faltan)}")


# --- Maestro de materiales ---

MAESTRO_OBLIGATORIOS = ["WERKS", "MATNR", "MAKTX", "MTART", "MATKL", "MEINS", "PEINH"]


def maestro(
    archivo: Path,
    salida: Path = SALIDA,
    separador: str = ";",
    decimal: str = ",",
    columnas: Path | None = None,
    unidades: Path = UNIDADES,
    moneda: str | None = None,
) -> Path:
    """
    MARA, MARC, MAKT y MBEW de cada material asignado a la planta, a
    maestro_materiales.parquet. El precio es VERPR o STPRS según el control de
    precio VPRSV (V precio medio variable, S estándar); un LEIH sin valorar
    trae el del registro info (EINE.NETPR), que se mapea a VERPR con
    --columnas. WAERS es de la sociedad y no está en MBEW: sin la columna,
    --moneda la da para todo el archivo.
    """
    crudo = _crudo(archivo, separador, columnas)
    campos = set(crudo.collect_schema().names())
    _exige(campos, MAESTRO_OBLIGATORIOS, "el maestro")
    if not {"VERPR", "STPRS"} & campos:
        raise ValueError("El maestro no trae precio: falta VERPR o STPRS")
    if "WAERS" not in campos and moneda is None:
        raise ValueError("El maestro no trae WAERS: pasa la moneda con --moneda")
    opcionales = {"VERPR", "STPRS", "VPRSV", "WAERS"}
    crudo = crudo.with_columns(pl.lit(None, dtype=pl.String).alias(c) for c in opcionales - campos)
    lf = crudo.select(_texto(c).alias(c) for c in [*MAESTRO_OBLIGATORIOS, *sorted(opcionales)])
    precio = (
        pl.when(pl.col("VPRSV") == "S")
        .then(_numero("STPRS", decimal))
        .otherwise(pl.coalesce(_numero("VERPR", decimal), _numero("STPRS", decimal)))
    )
    tabla = lf.select(
        pl.col("WERKS").alias("Werks"),
        pl.col("MATNR").alias("Matnr"),
        pl.col("MAKTX").alias("Maktx"),
        pl.col("MTART").alias("Mtart"),
        pl.col("MATKL").alias("Matkl"),
        pl.col("MEINS").replace(lee_unidades(unidades)).alias("Meins"),
        precio.alias("Verpr"),
        pl.col("PEINH").cast(pl.Int64).alias("Peinh"),
        pl.coalesce(pl.col("WAERS"), pl.lit(moneda, dtype=pl.String)).alias("Waers"),
    ).sort("Werks", "Matnr")
    salida.mkdir(parents=True, exist_ok=True)
    destino = salida / MAESTRO
    tabla.collect().write_parquet(destino)
    return destino


# --- Foto de stock ---

# Columnas de stock de MARD y MSKU: la foto es la suma de las que vengan.
STOCK_ALMACEN = ["LABST", "UMLME", "INSME", "EINME", "SPEME", "RETME"]
STOCK_CLIENTE = ["KULAB", "KUINS", "KUEIN"]


def _stock(crudo: pl.LazyFrame, llave: list[str], stock: list[str], decimal: str, que: str):
    campos = set(crudo.collect_schema().names())
    _exige(campos, ["WERKS", "MATNR", *llave], que)
    cantidades = [c for c in [*stock, "MENGE"] if c in campos]
    if not cantidades:
        raise ValueError(f"{que} no trae cantidad: {', '.join(stock)} o MENGE")
    if "SOBKZ" in campos:
        # MSKU guarda también el stock en consignación (W); aquí solo va el V.
        crudo = crudo.filter(_texto("SOBKZ") == "V")
    return crudo.select(
        _texto("WERKS").alias("Werks"),
        *[_texto(c).alias(c.capitalize()) for c in llave],
        _texto("MATNR").alias("Matnr"),
        pl.sum_horizontal(_numero(c, decimal).fill_null(0) for c in cantidades)
        .cast(pl.Int64)
        .alias("Menge"),
    )


def _regresa(cierre: pl.DataFrame, mb51: pl.LazyFrame, apertura, seeds: Path) -> pl.DataFrame:
    """
    Foto al cierre menos lo que se movió en la ventana: la foto del día antes
    del primer movimiento. Se regresan los almacenes del ciclo (seed
    almacenes) y los que traiga la foto; un almacén vacío al cierre no aparece
    en MARD y su stock de apertura sale solo de los movimientos. Con MSKU, cada
    cuenta V de las plantas que trae.
    """
    almacenes = pl.read_csv(seeds / "almacenes.csv", infer_schema=False)
    ciclo = almacenes.filter(pl.col("estado") != "fuera_ciclo")["lgort"]
    clases = pl.read_csv(seeds / "clases_movimiento.csv", infer_schema=False)
    salida = clases.filter(pl.col("evento") == "salida_cliente")["bwart"]
    cuenta = clases.filter(
        pl.col("evento").is_in(["salida_cliente", "recogida_cliente", "faltante_cliente"])
    )["bwart"]

    en_foto = cierre.filter(pl.col("Lgort").is_not_null()).select("Lgort").unique()["Lgort"]
    alcance = pl.concat([ciclo, en_foto]).unique()
    llave = ["Werks", "Lgort", "Matnr", "Kunnr"]
    almacen = mb51.filter(pl.col("Lgort").is_in(alcance.implode())).select(
        "Werks", "Lgort", "Matnr", pl.lit(None, dtype=pl.String).alias("Kunnr"), "Menge"
    )
    plantas_v = cierre.filter(pl.col("Kunnr").is_not_null())["Werks"].unique()
    cliente = mb51.filter(
        pl.col("Bwart").is_in(cuenta.implode()) & pl.col("Werks").is_in(plantas_v.implode())
    ).select(
        "Werks",
        pl.lit(None, dtype=pl.String).alias("Lgort"),
        "Matnr",
        "Kunnr",
        pl.when(pl.col("Bwart").is_in(salida.implode()))
        .then(pl.col("Menge").abs())
        .otherwise(-pl.col("Menge").abs())
        .alias("Menge"),
    )
    movido = pl.concat([almacen, cliente]).group_by(llave).agg(pl.col("Menge").sum())
    return (
        pl.concat(
            [
                cierre.lazy().select(*llave, "Menge"),
                movido.with_columns(-pl.col("Menge")),
            ]
        )
        .group_by(llave)
        .agg(pl.col("Menge").sum())
        .filter(pl.col("Menge") != 0)
        .with_columns(pl.lit(apertura).alias("Fecha"))
        .collect()
    )


def foto(
    al: date,
    almacen: Path,
    salida: Path = SALIDA,
    cliente: Path | None = None,
    mb51: Path | None = None,
    separador: str = ";",
    decimal: str = ",",
    columnas: Path | None = None,
    seeds: Path = SEEDS,
) -> Path:
    """
    Stock por almacén (MARD o MB5B) y stock V en cliente (MSKU) a
    stock_inicial.parquet, la foto del día anterior a la ventana (ADR-036).

    Con la foto de ese día se escribe como viene. Con la del día del extracto,
    que es la que cualquiera baja de MMBE o SE16N, se regresa con el MB51 ya
    convertido: foto al cierre menos lo que se movió en la ventana. Una fecha
    a la mitad de la ventana no sirve para ninguna de las dos.
    """
    mb51 = mb51 or salida
    movimientos = pl.scan_parquet(mb51 / "mb51_*.parquet")
    inicio, fin = (
        movimientos.select(
            pl.col("Budat").min().alias("inicio"), pl.col("Budat").max().alias("fin")
        )
        .collect()
        .row(0)
    )
    llave = ["Werks", "Lgort", "Matnr", "Kunnr"]
    partes = [
        _stock(_crudo(almacen, separador, columnas), ["LGORT"], STOCK_ALMACEN, decimal, "MARD")
        .with_columns(pl.lit(None, dtype=pl.String).alias("Kunnr"))
        .select(*llave, "Menge")
    ]
    if cliente is not None:
        partes.append(
            _stock(_crudo(cliente, separador, columnas), ["KUNNR"], STOCK_CLIENTE, decimal, "MSKU")
            .with_columns(pl.lit(None, dtype=pl.String).alias("Lgort"))
            .select(*llave, "Menge")
        )
    cierre = pl.concat(partes).filter(pl.col("Menge") != 0).collect()

    if al < inicio:
        tabla = cierre.with_columns(pl.lit(al).alias("Fecha"))
    elif al >= fin:
        tabla = _regresa(cierre, movimientos, inicio - timedelta(days=1), seeds)
    else:
        raise ValueError(
            f"Foto al {al}: dentro de la ventana del MB51 ({inicio} a {fin}). Tiene que ser "
            "del día anterior al primer movimiento o del día del extracto."
        )
    salida.mkdir(parents=True, exist_ok=True)
    destino = salida / STOCK_INICIAL
    tabla.sort(llave, nulls_last=True).write_parquet(destino)
    return destino


def _filas(archivo: Path) -> str:
    return f"{archivo}: {pl.scan_parquet(archivo).select(pl.len()).collect().item():,} filas"


def main(argv: list[str] | None = None) -> None:
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--salida", type=Path, default=SALIDA)
    comun.add_argument("--separador", default=";")
    comun.add_argument("--decimal", default=",", choices=[",", "."])
    comun.add_argument("--columnas", type=Path, help="CSV columna,campo para otros encabezados.")

    p = argparse.ArgumentParser(
        prog="python -m rpi.extracto", description="Extracto de SAP al contrato."
    )
    sub = p.add_subparsers(dest="tabla", required=True)
    m = sub.add_parser("mb51", parents=[comun], help="MB51 con los campos de MSEG y MKPF.")
    m.add_argument("archivo", type=Path)
    m.add_argument("--fecha", default="%d.%m.%Y", help="Formato de fecha (strftime).")
    ma = sub.add_parser("maestro", parents=[comun], help="MARA, MARC, MAKT y MBEW.")
    ma.add_argument("archivo", type=Path)
    ma.add_argument("--moneda", help="WAERS para todo el archivo si no trae la columna.")
    fo = sub.add_parser("foto", parents=[comun], help="Stock por almacén y en cliente.")
    fo.add_argument("al", help="Día de la foto, con el formato de --fecha.")
    fo.add_argument("--almacen", type=Path, required=True, help="MARD o MB5B.")
    fo.add_argument("--cliente", type=Path, help="MSKU: stock especial V en cliente.")
    fo.add_argument("--mb51", type=Path, help="MB51 ya convertido; default, --salida.")
    fo.add_argument("--fecha", default="%d.%m.%Y", help="Formato de fecha (strftime).")
    a = p.parse_args(argv)

    if a.tabla == "mb51":
        for f in mb51(a.archivo, a.salida, a.separador, a.decimal, a.fecha, a.columnas):
            print(_filas(f))
    elif a.tabla == "maestro":
        print(
            _filas(
                maestro(a.archivo, a.salida, a.separador, a.decimal, a.columnas, moneda=a.moneda)
            )
        )
    else:
        al = datetime.strptime(a.al, a.fecha).date()
        destino = foto(
            al, a.almacen, a.salida, a.cliente, a.mb51, a.separador, a.decimal, a.columnas
        )
        print(_filas(destino))


if __name__ == "__main__":
    main()
