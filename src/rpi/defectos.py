"""
Catálogo de defectos inyectables (ADR-028, ADR-029).

Cada defecto corre sobre las tablas limpias de una planta con su propio
generador aleatorio, default_rng([seed, indice_planta, 3, k]): encender uno no
mueve ningún sorteo del dataset limpio ni de otro defecto. Dentro de la planta
los objetivos no se repiten: un documento, un material o una parte que tocó un
defecto queda fuera de los siguientes, así con todos encendidos ninguno tapa la
regla de otro. Cada cambio queda en la bitácora; nada cambia fuera de ella.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import polars as pl

from rpi.config import DefectosConfig, PlantConfig

BITACORA = "bitacora_defectos.parquet"

ESQUEMA_BITACORA = {
    "defecto": pl.String,
    "objeto": pl.String,
    "Werks": pl.String,
    "Matnr": pl.String,
    "Mjahr": pl.Int64,
    "Mblnr": pl.String,
    "Zeile": pl.String,
    "Parte": pl.String,
    "campo": pl.String,
    "valor_original": pl.String,
    "valor_inyectado": pl.String,
}

_DOC = ["Mjahr", "Mblnr"]


@dataclass
class Planta:
    """Tablas de una planta y lo que ya tocó algún defecto."""

    tablas: dict[str, pl.DataFrame]
    planta: PlantConfig
    primera_del_pais: bool
    corte: date
    docs: pl.DataFrame = field(
        default_factory=lambda: pl.DataFrame(schema={"Mjahr": pl.Int64, "Mblnr": pl.String})
    )
    materiales: set[str] = field(default_factory=set)
    partes: set[str] = field(default_factory=set)
    bitacora: list[pl.DataFrame] = field(default_factory=list)

    @property
    def werks(self) -> str:
        return self.planta.werks

    def moneda_local(self, cfg: DefectosConfig) -> bool:
        """La planta recibe D18: su maestro queda en moneda local."""
        return (
            "D18" in cfg.activos and self.primera_del_pais and self.planta.country in cfg.d18_moneda
        )

    def marca_docs(self, df: pl.DataFrame) -> None:
        self.docs = pl.concat([self.docs, df.select(_DOC)]).unique()

    def registra(self, df: pl.DataFrame, defecto: str, objeto: str) -> None:
        """df trae la llave del objeto, campo, valor_original y valor_inyectado."""
        fila = df.with_columns(
            pl.lit(defecto).alias("defecto"),
            pl.lit(objeto).alias("objeto"),
            pl.lit(self.werks).alias("Werks"),
        )
        self.bitacora.append(
            fila.select(
                pl.col(c).cast(t) if c in fila.columns else pl.lit(None, dtype=t).alias(c)
                for c, t in ESQUEMA_BITACORA.items()
            )
        )


def _cuantos(tasa: float, universo: int, candidatos: int) -> int:
    """Al menos uno por planta si el defecto aplica; nunca más que los candidatos."""
    if tasa <= 0 or candidatos == 0:
        return 0
    return min(candidatos, max(1, round(tasa * universo)))


def _elige(df: pl.DataFrame, n: int, rng: np.random.Generator) -> pl.DataFrame:
    if n == 0:
        return df.head(0)
    return df[np.sort(rng.choice(df.height, size=n, replace=False))]


def _texto(col: str) -> pl.Expr:
    return pl.col(col).cast(pl.String)


# ---------------------------------------------------------------------------
# MB51
# ---------------------------------------------------------------------------


def _lineas_libres(p: Planta, df: pl.DataFrame) -> pl.DataFrame:
    return df.join(p.docs, on=_DOC, how="anti").filter(~pl.col("Matnr").is_in(sorted(p.materiales)))


def _cambia_lineas(
    mb51: pl.DataFrame, sel: pl.DataFrame, campo: str, nuevo: pl.Expr
) -> pl.DataFrame:
    """Aplica nuevo en campo a las filas de sel (por _i) y deja el resto igual."""
    cambio = sel.select("_i", nuevo.alias("_nuevo"), pl.lit(True).alias("_marca"))
    return (
        mb51.join(cambio, on="_i", how="left")
        .sort("_i")
        .with_columns(
            pl.when(pl.col("_marca")).then(pl.col("_nuevo")).otherwise(pl.col(campo)).alias(campo)
        )
        .drop("_nuevo", "_marca")
    )


def _defecto_linea(
    p: Planta,
    defecto: str,
    rng: np.random.Generator,
    universo: pl.Expr,
    tasa: float,
    campo: str,
    nuevo: pl.Expr,
) -> None:
    mb51 = p.tablas["mb51"].with_row_index("_i")
    base = mb51.filter(universo)
    candidatos = _lineas_libres(p, base)
    sel = _elige(candidatos, _cuantos(tasa, base.height, candidatos.height), rng)
    p.tablas["mb51"] = _cambia_lineas(mb51, sel, campo, nuevo).drop("_i")
    p.registra(
        sel.with_columns(
            pl.lit(campo).alias("campo"),
            _texto(campo).alias("valor_original"),
            nuevo.cast(pl.String).alias("valor_inyectado"),
        ),
        defecto,
        "mb51",
    )
    p.marca_docs(sel)


def d01_duplicado(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """Un día completo de la planta entra dos veces, con la misma llave."""
    mb51 = p.tablas["mb51"]
    dias = mb51["Budat"].unique().sort()
    n = min(cfg.d01_dias, dias.len())
    if n == 0:
        return
    elegidos = dias.gather(np.sort(rng.choice(dias.len(), size=n, replace=False)))
    dup = mb51.filter(pl.col("Budat").is_in(elegidos.implode()))
    p.tablas["mb51"] = pl.concat([mb51, dup])
    p.registra(
        dup.with_columns(
            pl.lit("linea").alias("campo"),
            pl.lit(None, dtype=pl.String).alias("valor_original"),
            pl.lit("duplicada").alias("valor_inyectado"),
        ),
        "D01",
        "mb51",
    )
    p.marca_docs(dup)


def d02_bwart(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    universo = pl.col("Bwart") == "621"
    _defecto_linea(p, "D02", rng, universo, cfg.d02_tasa, "Bwart", pl.lit(cfg.d02_bwart))


def d03_lgort(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    universo = (
        (pl.col("Bwart") == "311") & (pl.col("Zeile") == "0002") & (pl.col("Lgort") == "VACI")
    )
    _defecto_linea(p, "D03", rng, universo, cfg.d03_tasa, "Lgort", pl.lit(cfg.d03_lgort))


def d04_sin_cliente(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    universo = pl.col("Bwart") == "621"
    _defecto_linea(p, "D04", rng, universo, cfg.d04_tasa, "Kunnr", pl.lit(None, dtype=pl.String))


def d05_signo(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    _defecto_linea(p, "D05", rng, pl.lit(True), cfg.d05_tasa, "Menge", -pl.col("Menge"))


def d06_piezas(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    Desde una fecha, los 621 de un material se capturan con las piezas de la
    parte en lugar de contenedores. La fecha sale de los 621 del propio
    material, así cada material elegido tiene al menos una línea afectada.
    """
    mb51 = p.tablas["mb51"].with_row_index("_i")
    piezas = p.tablas["instruccion"].group_by("Matnr").agg(pl.col("Piezas").min())
    s621 = _lineas_libres(p, mb51.filter(pl.col("Bwart") == "621")).join(piezas, on="Matnr")
    candidatos = s621.select("Matnr").unique().sort("Matnr")
    sel = _elige(candidatos, _cuantos(cfg.d06_tasa, piezas.height, candidatos.height), rng)
    desde = []
    for m in sel["Matnr"]:
        fechas = s621.filter(pl.col("Matnr") == m)["Budat"].unique().sort()
        desde.append(fechas[int(rng.integers(0, fechas.len()))])
    sel = sel.with_columns(pl.Series("desde", desde, dtype=pl.Date))
    lineas = s621.join(sel, on="Matnr").filter(pl.col("Budat") >= pl.col("desde"))
    nuevo = pl.col("Menge") * pl.col("Piezas")
    p.tablas["mb51"] = _cambia_lineas(mb51, lineas, "Menge", nuevo).drop("_i")
    p.registra(
        lineas.with_columns(
            pl.lit("Menge").alias("campo"),
            _texto("Menge").alias("valor_original"),
            nuevo.cast(pl.String).alias("valor_inyectado"),
        ),
        "D06",
        "mb51",
    )
    p.materiales |= set(sel["Matnr"])


def d07_622_sin_saldo(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    Un 622 se contabiliza a un cliente de la planta que nunca recibió ese
    material: la cuenta no tiene saldo que recoger.
    """
    mb51 = p.tablas["mb51"].with_row_index("_i")
    s621 = mb51.filter((pl.col("Bwart") == "621") & pl.col("Kunnr").is_not_null())
    clientes = sorted(s621["Kunnr"].unique())
    historia = {
        m: set(g["Kunnr"]) for (m,), g in s621.select("Matnr", "Kunnr").unique().group_by("Matnr")
    }
    base = mb51.filter(pl.col("Bwart") == "622")
    con_libre = [m for m, ks in historia.items() if len(ks) < len(clientes)]
    candidatos = _lineas_libres(p, base).filter(pl.col("Matnr").is_in(con_libre))
    sel = _elige(candidatos, _cuantos(cfg.d07_tasa, base.height, candidatos.height), rng)
    nuevos = []
    for m in sel["Matnr"]:
        libres = sorted(set(clientes) - historia[m])
        nuevos.append(libres[int(rng.integers(0, len(libres)))])
    sel = sel.with_columns(pl.Series("_kunnr", nuevos, dtype=pl.String))
    p.tablas["mb51"] = _cambia_lineas(mb51, sel, "Kunnr", pl.col("_kunnr")).drop("_i")
    p.registra(
        sel.with_columns(
            pl.lit("Kunnr").alias("campo"),
            _texto("Kunnr").alias("valor_original"),
            pl.col("_kunnr").alias("valor_inyectado"),
        ),
        "D07",
        "mb51",
    )
    p.marca_docs(sel)


def d08_cpudt_cerrado(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    Documentos registrados entre d08_dias_min y d08_dias_max días después del
    fin de mes de su Budat, sin pasar del corte. Todas las posiciones del
    documento comparten el registro.
    """
    mb51 = p.tablas["mb51"].with_row_index("_i")
    todos = mb51.select(_DOC).unique()
    con_material_tocado = mb51.filter(pl.col("Matnr").is_in(sorted(p.materiales))).select(_DOC)
    candidatos = (
        mb51.group_by(_DOC)
        .agg(pl.col("Budat").first())
        .join(p.docs, on=_DOC, how="anti")
        .join(con_material_tocado, on=_DOC, how="anti")
        .filter(
            pl.col("Budat").dt.month_end() + pl.duration(days=cfg.d08_dias_min) <= pl.lit(p.corte)
        )
        .sort(_DOC)
    )
    sel = _elige(candidatos, _cuantos(cfg.d08_tasa, todos.height, candidatos.height), rng)
    extra = rng.integers(cfg.d08_dias_min, cfg.d08_dias_max + 1, sel.height)
    sel = sel.with_columns(pl.Series("_extra", extra, dtype=pl.Int64)).select(
        *_DOC,
        pl.min_horizontal(
            pl.col("Budat").dt.month_end() + pl.duration(days=pl.col("_extra")),
            pl.lit(p.corte),
        ).alias("_cpudt"),
    )
    lineas = mb51.join(sel, on=_DOC)
    p.tablas["mb51"] = _cambia_lineas(mb51, lineas, "Cpudt", pl.col("_cpudt")).drop("_i")
    p.registra(
        lineas.with_columns(
            pl.lit("Cpudt").alias("campo"),
            _texto("Cpudt").alias("valor_original"),
            _texto("_cpudt").alias("valor_inyectado"),
        ),
        "D08",
        "mb51",
    )
    p.marca_docs(sel)


def d16_precio_documento(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    El documento de un material lleva un precio anterior a una revaluación:
    entre d16_desvio_min y d16_desvio_max arriba o abajo del maestro. No cae en
    la planta de D18: con el maestro en otra moneda no hay precio con el cual
    comparar el documento (ADR-030).
    """
    if p.moneda_local(cfg):
        return
    mb51 = p.tablas["mb51"].with_row_index("_i")
    universo = mb51.select("Matnr").unique()
    candidatos = universo.filter(~pl.col("Matnr").is_in(sorted(p.materiales))).sort("Matnr")
    sel = _elige(candidatos, _cuantos(cfg.d16_tasa, universo.height, candidatos.height), rng)
    signo = rng.choice([-1.0, 1.0], size=sel.height)
    desvio = rng.uniform(cfg.d16_desvio_min, cfg.d16_desvio_max, sel.height)
    sel = sel.with_columns(pl.Series("_factor", 1 + signo * desvio))
    lineas = mb51.join(p.docs, on=_DOC, how="anti").join(sel, on="Matnr")
    nuevo = (pl.col("Costo_usd") * pl.col("_factor")).round(2)
    p.tablas["mb51"] = _cambia_lineas(mb51, lineas, "Costo_usd", nuevo).drop("_i")
    por_material = lineas.group_by("Matnr").agg(
        pl.col("Costo_usd").first().cast(pl.String).alias("valor_original"),
        nuevo.first().cast(pl.String).alias("valor_inyectado"),
    )
    p.registra(por_material.with_columns(pl.lit("Costo_usd").alias("campo")), "D16", "mb51")
    p.materiales |= set(sel["Matnr"])


# ---------------------------------------------------------------------------
# Foto de stock inicial
# ---------------------------------------------------------------------------


def d09_sin_foto(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """La foto inicial deja fuera todas las filas de un material."""
    stock = p.tablas["stock"]
    universo = stock.select("Matnr").unique()
    candidatos = universo.filter(~pl.col("Matnr").is_in(sorted(p.materiales))).sort("Matnr")
    sel = _elige(candidatos, _cuantos(cfg.d09_tasa, universo.height, candidatos.height), rng)
    quitadas = stock.join(sel, on="Matnr")
    p.tablas["stock"] = stock.join(sel, on="Matnr", how="anti")
    p.registra(
        quitadas.group_by("Matnr").agg(
            pl.lit("Menge").alias("campo"),
            pl.col("Menge").sum().cast(pl.String).alias("valor_original"),
            pl.lit(None, dtype=pl.String).alias("valor_inyectado"),
        ),
        "D09",
        "stock_inicial",
    )
    p.materiales |= set(sel["Matnr"])


# ---------------------------------------------------------------------------
# Instrucción de empaque
# ---------------------------------------------------------------------------


def _partes_candidatas(p: Planta) -> pl.DataFrame:
    return (
        p.tablas["instruccion"]
        .filter(
            ~pl.col("Matnr").is_in(sorted(p.materiales)) & ~pl.col("Parte").is_in(sorted(p.partes))
        )
        .sort("Parte")
    )


def _elige_partes(p: Planta, tasa: float, rng: np.random.Generator) -> pl.DataFrame:
    instruccion = p.tablas["instruccion"]
    candidatos = _partes_candidatas(p)
    sel = _elige(candidatos, _cuantos(tasa, instruccion.height, candidatos.height), rng)
    p.partes |= set(sel["Parte"])
    return sel


def d10_sin_instruccion(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    sel = _elige_partes(p, cfg.d10_tasa, rng)
    p.tablas["instruccion"] = p.tablas["instruccion"].join(sel, on="Parte", how="anti")
    p.registra(
        sel.with_columns(
            pl.lit("fila").alias("campo"),
            _texto("Matnr").alias("valor_original"),
            pl.lit(None, dtype=pl.String).alias("valor_inyectado"),
        ),
        "D10",
        "instruccion_empaque",
    )


def _cambia_partes(p: Planta, sel: pl.DataFrame, campo: str) -> None:
    p.tablas["instruccion"] = (
        p.tablas["instruccion"]
        .join(sel.select("Parte", "_nuevo"), on="Parte", how="left")
        .with_columns(pl.coalesce("_nuevo", campo).alias(campo))
        .drop("_nuevo")
    )


def d11_piezas_cero(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    sel = _elige_partes(p, cfg.d11_tasa, rng).with_columns(
        pl.lit(0, dtype=pl.Int64).alias("_nuevo")
    )
    _cambia_partes(p, sel, "Piezas")
    p.registra(
        sel.with_columns(
            pl.lit("Piezas").alias("campo"),
            _texto("Piezas").alias("valor_original"),
            _texto("_nuevo").alias("valor_inyectado"),
        ),
        "D11",
        "instruccion_empaque",
    )


def d12_instruccion_carton(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """La instrucción de la parte apunta a un cartón de la planta."""
    cartones = sorted(p.tablas["maestro"].filter(pl.col("Mtart") == "VERP")["Matnr"])
    if not cartones:
        return
    sel = _elige_partes(p, cfg.d12_tasa, rng)
    nuevos = [cartones[int(i)] for i in rng.integers(0, len(cartones), sel.height)]
    sel = sel.with_columns(pl.Series("_nuevo", nuevos, dtype=pl.String))
    _cambia_partes(p, sel, "Matnr")
    # El cartón al que apunta queda tocado: si un defecto de maestro le quitara
    # el tipo, la instrucción ya no se vería como desechable.
    p.materiales |= set(nuevos)
    p.registra(
        sel.with_columns(
            pl.lit("Matnr").alias("campo"),
            _texto("Matnr").alias("valor_original"),
            pl.col("_nuevo").alias("valor_inyectado"),
        ),
        "D12",
        "instruccion_empaque",
    )


# ---------------------------------------------------------------------------
# Maestro de materiales
# ---------------------------------------------------------------------------


def _elige_maestro(
    p: Planta, tasa: float, rng: np.random.Generator, filtro: pl.Expr | None = None
) -> pl.DataFrame:
    """Materiales del maestro que se mueven en la planta y que nadie tocó."""
    movidos = p.tablas["mb51"]["Matnr"].unique()
    universo = p.tablas["maestro"].filter(pl.col("Matnr").is_in(movidos.implode()))
    if filtro is not None:
        universo = universo.filter(filtro)
    candidatos = universo.filter(~pl.col("Matnr").is_in(sorted(p.materiales))).sort("Matnr")
    sel = _elige(candidatos, _cuantos(tasa, universo.height, candidatos.height), rng)
    p.materiales |= set(sel["Matnr"])
    return sel


def _cambia_maestro(p: Planta, sel: pl.DataFrame, campo: str) -> None:
    p.tablas["maestro"] = (
        p.tablas["maestro"]
        .join(sel.select("Matnr", "_nuevo"), on="Matnr", how="left")
        .with_columns(pl.coalesce("_nuevo", campo).alias(campo))
        .drop("_nuevo")
    )


def _registra_maestro(p: Planta, sel: pl.DataFrame, defecto: str, campo: str) -> None:
    p.registra(
        sel.with_columns(
            pl.lit(campo).alias("campo"),
            _texto(campo).alias("valor_original"),
            _texto("_nuevo").alias("valor_inyectado"),
        ),
        defecto,
        "maestro",
    )


def d13_unidad_precio(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """Precio por pieza con la unidad de precio heredada de otra alta: 10 o 100."""
    sel = _elige_maestro(p, cfg.d13_tasa, rng)
    unidades = rng.choice(cfg.d13_unidades, size=sel.height)
    sel = sel.with_columns(pl.Series("_nuevo", unidades, dtype=pl.Int64))
    _cambia_maestro(p, sel, "Peinh")
    _registra_maestro(p, sel, "D13", "Peinh")


def d14_alta_por_referencia(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    Un retornable dado de alta copiando un material de la otra familia: arrastra
    su grupo de artículos y su precio.
    """
    maestro = p.tablas["maestro"]
    sel = _elige_maestro(p, cfg.d14_tasa, rng, pl.col("Mtart") == "LEIH")
    grupo, precio = [], []
    for g in sel["Matkl"]:
        otros = maestro.filter((pl.col("Mtart") == "LEIH") & (pl.col("Matkl") != g)).sort("Matnr")
        ref = otros.row(int(rng.integers(0, otros.height)), named=True)
        grupo.append(ref["Matkl"])
        precio.append(ref["Verpr"])
    sel_grupo = sel.with_columns(pl.Series("_nuevo", grupo, dtype=pl.String))
    sel_precio = sel.with_columns(pl.Series("_nuevo", precio, dtype=pl.Float64))
    _cambia_maestro(p, sel_grupo, "Matkl")
    _cambia_maestro(p, sel_precio, "Verpr")
    _registra_maestro(p, sel_grupo, "D14", "Matkl")
    _registra_maestro(p, sel_precio, "D14", "Verpr")


def d15_sin_maestro(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    sel = _elige_maestro(p, cfg.d15_tasa, rng)
    p.tablas["maestro"] = p.tablas["maestro"].join(sel, on="Matnr", how="anti")
    p.registra(
        sel.with_columns(
            pl.lit("fila").alias("campo"),
            _texto("Matkl").alias("valor_original"),
            pl.lit(None, dtype=pl.String).alias("valor_inyectado"),
        ),
        "D15",
        "maestro",
    )


def d17_grupo_fuera(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    sel = _elige_maestro(p, cfg.d17_tasa, rng).with_columns(pl.lit(cfg.d17_matkl).alias("_nuevo"))
    _cambia_maestro(p, sel, "Matkl")
    _registra_maestro(p, sel, "D17", "Matkl")


def d18_moneda_local(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    La primera planta de un país con moneda propia entrega el maestro en esa
    moneda. No sortea nada; el generador del defecto queda sin uso.
    """
    if not p.moneda_local(cfg):
        return
    moneda, factor = cfg.d18_moneda[p.planta.country]
    maestro = p.tablas["maestro"]
    p.tablas["maestro"] = maestro.with_columns(
        (pl.col("Verpr") * factor).round(2).alias("Verpr"), pl.lit(moneda).alias("Waers")
    )
    p.registra(
        maestro.select(
            "Matnr",
            pl.lit("Waers").alias("campo"),
            pl.col("Waers").alias("valor_original"),
            pl.lit(moneda).alias("valor_inyectado"),
        ),
        "D18",
        "maestro",
    )


# ---------------------------------------------------------------------------
# Ciegos (ADR-033): defectos de un extracto real que ninguna regla nombra al
# medirse por primera vez. La medición se versiona antes de escribir su regla.
# ---------------------------------------------------------------------------


def _desde(mb51: pl.DataFrame, rng: np.random.Generator) -> object:
    """Una fecha en el tercio central de la ventana: el cambio llega a media historia."""
    dias = mb51["Budat"].unique().sort()
    return dias[int(rng.integers(dias.len() // 3, 2 * dias.len() // 3))]


def b01_matnr_formato(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    Desde una fecha, los movimientos de unos retornables llegan con el Matnr
    con ceros a la izquierda: cambió la conversión del extracto y el maestro
    sigue con el formato de antes.
    """
    mb51 = p.tablas["mb51"].with_row_index("_i")
    s621 = mb51.filter(pl.col("Bwart") == "621")
    candidatos = _lineas_libres(p, s621).select("Matnr").unique().sort("Matnr")
    universo = s621["Matnr"].n_unique()
    sel = _elige(candidatos, _cuantos(cfg.b01_tasa, universo, candidatos.height), rng)
    desde = _desde(mb51, rng)
    lineas = _lineas_libres(
        p, mb51.filter(pl.col("Matnr").is_in(sel["Matnr"].implode()) & (pl.col("Budat") >= desde))
    )
    nuevo = pl.lit("0" * cfg.b01_ceros) + pl.col("Matnr")
    p.tablas["mb51"] = _cambia_lineas(mb51, lineas, "Matnr", nuevo).drop("_i")
    p.registra(
        lineas.with_columns(
            pl.lit("Matnr").alias("campo"),
            _texto("Matnr").alias("valor_original"),
            nuevo.alias("valor_inyectado"),
        ),
        "B01",
        "mb51",
    )
    p.materiales |= set(sel["Matnr"])
    p.marca_docs(lineas)


def b02_kunnr_formato(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    Desde una fecha, las recogidas de un cliente llegan con el Kunnr con ceros
    a la izquierda: el sistema del transportista lo manda con otro formato y
    la cuenta queda partida en dos.
    """
    mb51 = p.tablas["mb51"].with_row_index("_i")
    s622 = _lineas_libres(
        p, mb51.filter((pl.col("Bwart") == "622") & pl.col("Kunnr").is_not_null())
    )
    clientes = s622.select("Kunnr").unique().sort("Kunnr")
    n = min(cfg.b02_clientes, clientes.height)
    if n == 0:
        return
    sel = _elige(clientes, n, rng)
    desde = _desde(mb51, rng)
    lineas = s622.filter(pl.col("Kunnr").is_in(sel["Kunnr"].implode()) & (pl.col("Budat") >= desde))
    nuevo = pl.lit("00") + pl.col("Kunnr")
    p.tablas["mb51"] = _cambia_lineas(mb51, lineas, "Kunnr", nuevo).drop("_i")
    p.registra(
        lineas.with_columns(
            pl.lit("Kunnr").alias("campo"),
            _texto("Kunnr").alias("valor_original"),
            nuevo.alias("valor_inyectado"),
        ),
        "B02",
        "mb51",
    )
    p.marca_docs(lineas)


def b03_recontabiliza(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    Un documento 621 se contabiliza otra vez con otro número, al día
    siguiente: la llave no se repite y la salida cuenta doble. El número
    nuevo lleva el prefijo 4999, fuera de la secuencia del generador.
    """
    mb51 = p.tablas["mb51"]
    docs = mb51.filter(pl.col("Bwart") == "621").select(_DOC).unique()
    candidatos = (
        docs.join(p.docs, on=_DOC, how="anti")
        .join(
            mb51.filter(pl.col("Matnr").is_in(sorted(p.materiales))).select(_DOC),
            on=_DOC,
            how="anti",
        )
        .sort(_DOC)
    )
    sel = _elige(candidatos, _cuantos(cfg.b03_tasa, docs.height, candidatos.height), rng)
    dup = mb51.join(sel, on=_DOC).with_columns(
        ("4999" + pl.col("Mblnr").str.slice(4)).alias("Mblnr"),
        pl.min_horizontal(pl.col("Cpudt") + pl.duration(days=1), pl.lit(p.corte)).alias("Cpudt"),
    )
    p.tablas["mb51"] = pl.concat([mb51, dup])
    p.registra(
        dup.with_columns(
            pl.lit("linea").alias("campo"),
            pl.lit(None, dtype=pl.String).alias("valor_original"),
            pl.lit("recontabilizada").alias("valor_inyectado"),
        ),
        "B03",
        "mb51",
    )
    p.marca_docs(sel)
    p.marca_docs(dup)


def b04_budat_despues_del_corte(p: Planta, cfg: DefectosConfig, rng: np.random.Generator) -> None:
    """
    Salidas de las últimas semanas contabilizadas con fecha del periodo
    siguiente, 1 a 5 días después del corte, y registradas antes de extraer:
    el extracto trae movimientos que todavía no pasan.
    """
    mb51 = p.tablas["mb51"].with_row_index("_i")
    base = mb51.filter(pl.col("Bwart") == "621")
    ventana = base.filter(pl.col("Budat") > pl.lit(p.corte) - pl.duration(days=cfg.b04_dias))
    candidatos = _lineas_libres(p, ventana)
    sel = _elige(candidatos, _cuantos(cfg.b04_tasa, base.height, candidatos.height), rng)
    sel = sel.with_columns(
        pl.Series("_dias", rng.integers(1, 6, sel.height), dtype=pl.Int64)
    ).with_columns((pl.lit(p.corte) + pl.duration(days=pl.col("_dias"))).alias("_budat"))
    p.tablas["mb51"] = _cambia_lineas(mb51, sel, "Budat", pl.col("_budat")).drop("_i")
    p.registra(
        sel.with_columns(
            pl.lit("Budat").alias("campo"),
            _texto("Budat").alias("valor_original"),
            _texto("_budat").alias("valor_inyectado"),
        ),
        "B04",
        "mb51",
    )
    p.marca_docs(sel)


Defecto = Callable[[Planta, DefectosConfig, np.random.Generator], None]

CATALOGO: dict[str, Defecto] = {
    "D01": d01_duplicado,
    "D02": d02_bwart,
    "D03": d03_lgort,
    "D04": d04_sin_cliente,
    "D05": d05_signo,
    "D06": d06_piezas,
    "D07": d07_622_sin_saldo,
    "D08": d08_cpudt_cerrado,
    "D09": d09_sin_foto,
    "D10": d10_sin_instruccion,
    "D11": d11_piezas_cero,
    "D12": d12_instruccion_carton,
    "D13": d13_unidad_precio,
    "D14": d14_alta_por_referencia,
    "D15": d15_sin_maestro,
    "D16": d16_precio_documento,
    "D17": d17_grupo_fuera,
    "D18": d18_moneda_local,
    # Al final del catálogo: sus generadores son k = 19 a 22 y los de D01-D18 no cambian.
    "B01": b01_matnr_formato,
    "B02": b02_kunnr_formato,
    "B03": b03_recontabiliza,
    "B04": b04_budat_despues_del_corte,
}


def inyecta(
    tablas: dict[str, pl.DataFrame],
    cfg: DefectosConfig,
    planta: PlantConfig,
    primera_del_pais: bool,
    corte: date,
    seed: int,
    idx: int,
) -> tuple[dict[str, pl.DataFrame], pl.DataFrame]:
    """
    Aplica los defectos activos a las tablas limpias de una planta, en el orden
    del catálogo. tablas: mb51, stock, partes, instruccion, plan y maestro.
    """
    p = Planta(dict(tablas), planta, primera_del_pais, corte)
    for k, (clave, defecto) in enumerate(CATALOGO.items(), start=1):
        if clave in cfg.activos:
            defecto(p, cfg, np.random.default_rng([seed, idx, 3, k]))
    bitacora = pl.concat(p.bitacora) if p.bitacora else pl.DataFrame(schema=ESQUEMA_BITACORA)
    return p.tablas, bitacora
