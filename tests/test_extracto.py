"""
Adaptador de extracto real (ADR-035). El dataset sintético escrito como lo daría
SAP tiene que regresar idéntico al contrato: si la ida y vuelta no cuadra, el
adaptador cambia datos y no solo formato.
"""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from rpi.db import fallas_de_schema
from rpi.extracto import lee_unidades, main, mb51
from rpi.schema import MEINS_VALIDAS


def _con_miles(expr: pl.Expr, decimales: int, decimal: str) -> pl.Expr:
    # 1234.5 -> "1.234,50" o "1,234.50", como lo exporta SAP según la notación.
    miles = "." if decimal == "," else ","
    texto = expr.round(decimales).cast(pl.Decimal(18, decimales)).cast(pl.String)
    entero = texto.str.split(".").list.first()
    con_miles = entero.str.reverse().str.replace_all(r"(\d{3})(\d)", f"$1{miles}$2")
    con_miles = con_miles.str.reverse()
    if decimales == 0:
        return con_miles
    return con_miles + decimal + texto.str.split(".").list.get(1)


def a_sap(
    df: pl.DataFrame,
    decimal: str = ",",
    fecha: str = "%d.%m.%Y",
    signo_atras: bool = False,
    hora_con_puntos: bool = False,
) -> pl.DataFrame:
    """Un MB51 del contrato con los campos técnicos de MSEG y MKPF."""
    cantidad = _con_miles(pl.col("Menge").abs(), 0, decimal)
    if signo_atras:
        menge = pl.when(pl.col("Menge") < 0).then(cantidad + "-").otherwise(cantidad)
    else:
        menge = cantidad
    hora = pl.col("Cputm") if hora_con_puntos else pl.col("Cputm").str.replace_all(":", "")
    columnas = [
        pl.col("Mblnr").alias("MBLNR"),
        pl.col("Mjahr").cast(pl.String).alias("MJAHR"),
        pl.col("Zeile").alias("ZEILE"),
        pl.col("Bwart").alias("BWART"),
        pl.col("Matnr").alias("MATNR"),
        pl.col("Maktx").alias("MAKTX"),
        pl.col("Werks").alias("WERKS"),
        pl.col("Lgort").alias("LGORT"),
        menge.alias("MENGE"),
        pl.when(pl.col("Meins") == "PC").then(pl.lit("ST")).otherwise("Meins").alias("MEINS"),
        _con_miles(pl.col("Costo_usd") * pl.col("Menge").abs(), 2, decimal).alias("DMBTR"),
        pl.lit("USD").alias("WAERS"),
        pl.col("Budat").dt.strftime(fecha).alias("BUDAT"),
        pl.col("Cpudt").dt.strftime(fecha).alias("CPUDT"),
        hora.alias("CPUTM"),
        pl.col("Kunnr").alias("KUNNR"),
        pl.col("Lifnr").alias("LIFNR"),
        pl.col("Xblnr").alias("XBLNR"),
    ]
    if not signo_atras:
        columnas.append(
            pl.when(pl.col("Menge") < 0).then(pl.lit("H")).otherwise(pl.lit("S")).alias("SHKZG")
        )
    return df.select(columnas)


@pytest.fixture(scope="module")
def limpio(raw_ci: Path) -> dict[str, pl.DataFrame]:
    return {f.name: pl.read_parquet(f) for f in sorted(raw_ci.glob("mb51_*.parquet"))}


def _extracto(limpio: dict[str, pl.DataFrame], tmp: Path, sep: str = ";", **kw) -> Path:
    # Barajado: un extracto real no llega en el orden en que escribe el generador.
    archivo = tmp / "MB51.csv"
    sap = pl.concat([a_sap(df, **kw) for df in limpio.values()])
    sap.sample(fraction=1.0, shuffle=True, seed=7).write_csv(archivo, separator=sep)
    return archivo


def _igual_al_limpio(limpio: dict[str, pl.DataFrame], salida: Path) -> None:
    escritos = sorted(f.name for f in salida.glob("mb51_*.parquet"))
    assert escritos == sorted(limpio)
    for nombre, df in limpio.items():
        assert pl.read_parquet(salida / nombre).equals(df), nombre


def test_ida_y_vuelta(limpio, tmp_path):
    archivo = _extracto(limpio, tmp_path)
    mb51(archivo, tmp_path / "raw")
    _igual_al_limpio(limpio, tmp_path / "raw")


def test_otra_notacion_fecha_y_separador(limpio, tmp_path):
    archivo = _extracto(limpio, tmp_path, sep=",", decimal=".", fecha="%m/%d/%Y")
    mb51(archivo, tmp_path / "raw", separador=",", decimal=".", fecha="%m/%d/%Y")
    _igual_al_limpio(limpio, tmp_path / "raw")


def test_signo_en_la_cantidad_y_hora_con_puntos(limpio, tmp_path):
    # Como lo exporta el ALV de MB51: sin SHKZG y con el menos atrás.
    archivo = _extracto(limpio, tmp_path, signo_atras=True, hora_con_puntos=True)
    assert "SHKZG" not in pl.read_csv(archivo, separator=";", n_rows=1, infer_schema=False).columns
    mb51(archivo, tmp_path / "raw")
    _igual_al_limpio(limpio, tmp_path / "raw")


def test_encabezados_propios_con_mapeo(limpio, tmp_path):
    otros = {"MATNR": "Material", "WERKS": "Centro", "BWART": "Clase mov.", "BUDAT": "Fe.cont."}
    archivo = tmp_path / "MB51.csv"
    pl.concat([a_sap(df) for df in limpio.values()]).rename(otros).write_csv(archivo, separator=";")
    mapeo = tmp_path / "mapeo.csv"
    pl.DataFrame({"columna": list(otros.values()), "campo": list(otros)}).write_csv(mapeo)
    mb51(archivo, tmp_path / "raw", columnas=mapeo)
    _igual_al_limpio(limpio, tmp_path / "raw")


@pytest.mark.parametrize(
    ("decimal", "menge", "dmbtr"),
    [(",", "1.234", "2.468,00"), (".", "1,234", "2,468.00"), (",", "1.234-", "2.468,00")],
)
def test_numeros_con_miles(limpio, tmp_path, decimal, menge, dmbtr):
    # En el sintético ningún número llega a mil; en un extracto real sí.
    df = next(iter(limpio.values())).head(1)
    sap = a_sap(df).with_columns(pl.lit(menge).alias("MENGE"), pl.lit(dmbtr).alias("DMBTR"))
    # Con el signo atrás no viene SHKZG; sin signo, S (entrada).
    atras = menge.endswith("-")
    sap = sap.drop("SHKZG") if atras else sap.with_columns(pl.lit("S").alias("SHKZG"))
    archivo = tmp_path / "MB51.csv"
    sap.write_csv(archivo, separator=";")
    (escrito,) = mb51(archivo, tmp_path / "raw", decimal=decimal)
    r = pl.read_parquet(escrito).row(0, named=True)
    assert r["Menge"] == (-1234 if atras else 1234)
    assert r["Costo_usd"] == 2.0


def test_campos_obligatorios_que_faltan(limpio, tmp_path):
    archivo = tmp_path / "MB51.csv"
    pl.concat([a_sap(df) for df in limpio.values()]).drop("BWART", "CPUTM").write_csv(
        archivo, separator=";"
    )
    with pytest.raises(ValueError, match="BWART, CPUTM"):
        mb51(archivo, tmp_path / "raw")


def test_sin_importe_el_precio_queda_nulo(limpio, tmp_path):
    # Un LEIH estándar no lleva importe: el contrato acepta el precio nulo.
    archivo = tmp_path / "MB51.csv"
    sap = pl.concat([a_sap(df) for df in limpio.values()])
    sap.with_columns(pl.lit("0,00").alias("DMBTR")).write_csv(archivo, separator=";")
    escritos = mb51(archivo, tmp_path / "raw")
    for f in escritos:
        assert pl.read_parquet(f)["Costo_usd"].is_null().all()
        assert fallas_de_schema("raw_mb51", f).is_empty()


def test_no_corrige_datos(limpio, tmp_path):
    # Un código con ceros y una fecha después del corte pasan como vienen: los
    # ven matnr_con_formato y budat_despues_del_corte (ADR-034).
    nombre, df = next(iter(limpio.items()))
    sucio = df.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then("000" + pl.col("Matnr"))
        .otherwise("Matnr")
        .alias("Matnr"),
        pl.when(pl.int_range(pl.len()) == 1)
        .then(pl.lit(date(2026, 7, 3)))
        .otherwise("Budat")
        .alias("Budat"),
    )
    archivo = _extracto({nombre: sucio}, tmp_path)
    mb51(archivo, tmp_path / "raw")
    vuelta = pl.read_parquet(tmp_path / "raw" / nombre)
    assert vuelta.sort(vuelta.columns).equals(sucio.sort(sucio.columns))


def test_unidad_fuera_del_seed(limpio, tmp_path):
    nombre, df = next(iter(limpio.items()))
    archivo = tmp_path / "MB51.csv"
    sap = a_sap(df).with_columns(
        pl.when(pl.int_range(pl.len()) < 3).then(pl.lit("CAJ")).otherwise("MEINS").alias("MEINS")
    )
    sap.write_csv(archivo, separator=";")
    (escrito,) = mb51(archivo, tmp_path / "raw")
    # Pasa tal cual: ni nulo ni adivinado.
    assert (
        pl.read_parquet(escrito)
        .sort("Budat", "Mblnr", "Zeile")["Meins"]
        .value_counts()
        .filter(pl.col("Meins") == "CAJ")["count"]
        .item()
        == 3
    )
    fallas = fallas_de_schema("raw_mb51", escrito)
    assert set(fallas["columna"]) == {"Meins"}
    assert fallas.height == 3


def test_unidades_del_seed_son_del_contrato():
    assert set(lee_unidades().values()) <= set(MEINS_VALIDAS)


def test_otra_corrida_borra_las_plantas_viejas(limpio, tmp_path):
    vieja = tmp_path / "raw" / "mb51_PLNT_XX99.parquet"
    vieja.parent.mkdir()
    next(iter(limpio.values())).head(1).write_parquet(vieja)
    mb51(_extracto(limpio, tmp_path), tmp_path / "raw")
    assert not vieja.exists()


def test_cli(limpio, tmp_path, capsys):
    archivo = _extracto(limpio, tmp_path)
    main(["mb51", str(archivo), "--salida", str(tmp_path / "raw")])
    _igual_al_limpio(limpio, tmp_path / "raw")
    assert "filas" in capsys.readouterr().out
