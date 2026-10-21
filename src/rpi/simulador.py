"""
Gemelo de la red RPL: lavado de empaques y reparación con capacidad finita
sobre la traza del MB51 (ADR-038).

La traza dice cuándo quedó lista cada salida de una estación: el día en que el
MB51 la saca de sucios o de reparación. Con capacidad por día, lo que no cabe
espera su turno en orden de fecha lista. El simulador solo puede retrasar una
salida, nunca adelantarla: con capacidad sin límite reproduce el MB51.

Vacíos se recalcula por material con la recursión de Lindley: un día en que
falta vacío, la salida va en desechable y el saldo no queda negativo.

Todo es NumPy por planta y tipo de empaque; los modelos de dbt solo arman las
matrices y publican el resultado.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np
import polars as pl


@dataclass(frozen=True)
class Cola:
    """
    Lotes de una estación en orden de espera: por día listo y, dentro del día,
    por fila. Cada lote ocupa el tramo (inicio, fin] de la fila de espera.
    Se arma una vez por estación y sirve para todos los escenarios.
    """

    filas: int
    dias: int
    t: np.ndarray
    f: np.ndarray
    inicio: np.ndarray
    fin: np.ndarray
    listo_acum: np.ndarray

    @classmethod
    def de(cls, listo: np.ndarray) -> Cola:
        if (listo < 0).any():
            raise ValueError("listo no puede ser negativo")
        filas, dias = listo.shape
        t, f = np.nonzero(listo.T)
        q = listo[f, t].astype(float)
        fin = np.cumsum(q)
        return cls(filas, dias, t, f, fin - q, fin, listo.sum(axis=0).cumsum())

    def salidas(self, capacidad: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Lote, día y cantidad de cada salida con esa capacidad por día."""
        if capacidad.shape != (self.dias,):
            raise ValueError("capacidad necesita un valor por día")
        if (capacidad < 0).any():
            raise ValueError("capacidad no puede ser negativa")
        if not self.dias:
            vacio = np.zeros(0, dtype=np.int64)
            return vacio, vacio, np.zeros(0)
        # Total liberado acumulado: x[t] = min(listo_acum[t], x[t-1] + capacidad[t]).
        # Desenrollada es C[t] + min(0, min_{s<=t} listo_acum[s] - C[s]), con C
        # la capacidad acumulada. Sin límite se toma una capacidad que cubre todo.
        tope = self.listo_acum[-1] + 1.0
        cap_acum = np.minimum(capacidad, tope).cumsum()
        holgura = np.minimum.accumulate(np.minimum(self.listo_acum - cap_acum, 0.0))
        # El redondeo quita el ruido de punto flotante de sumar capacidades
        # grandes: sin él, un lote sin límite deja una millonésima para mañana.
        lib = np.round(cap_acum + holgura, 6)

        # Lo que sale de un lote el día t es el traslape de su tramo con lo
        # liberado ese día.
        previo = np.concatenate([[0.0], lib[:-1]])
        t0 = np.searchsorted(lib, self.inicio, side="right")
        t1 = np.minimum(np.searchsorted(lib, self.fin, side="left"), self.dias - 1)
        n = np.maximum(t1 - t0 + 1, 0)
        lote = np.repeat(np.arange(len(self.fin)), n)
        t = t0[lote] + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))
        sale = np.minimum(lib[t], self.fin[lote]) - np.maximum(previo[t], self.inicio[lote])
        return lote, t, np.maximum(sale, 0.0)


def liberar(listo: np.ndarray, capacidad: np.ndarray) -> np.ndarray:
    """
    Lo que sale de una estación cada día con capacidad finita.

    listo: (filas, días), cantidad que quedó lista cada día según la traza.
    capacidad: (días,), contenedores por día; 0 en día inhábil o en paro,
    np.inf sin límite. La cola es FIFO por día listo y, dentro del día, por
    fila. Devuelve una matriz del mismo tamaño que listo.
    """
    cola = Cola.de(listo)
    lote, t, sale = cola.salidas(capacidad)
    idx = cola.f[lote] * cola.dias + t
    return np.bincount(idx, sale, minlength=cola.filas * cola.dias).reshape(cola.filas, cola.dias)


def vacios(delta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Saldo de vacíos por material y lo que salió en desechable cada día.

    delta: (materiales, días), cambio neto de vacíos con la apertura en su
    fecha. Recursión de Lindley: saldo = max(saldo anterior + delta, 0); la
    diferencia es el faltante del día. Se resuelve cerrada con el mínimo
    acumulado, sin recorrer los días.
    """
    acum = delta.cumsum(axis=1)
    # Lo que va faltando en total es lo más bajo que ha llegado el acumulado.
    falta_acum = -np.minimum.accumulate(np.minimum(acum, 0.0), axis=1)
    saldo = acum + falta_acum
    faltante = np.diff(falta_acum, axis=1, prepend=0.0)
    return saldo, faltante


@dataclass
class Estacion:
    """
    Una estación de la planta para un tipo de empaque.

    listo: (filas, días) lo que quedó listo por día según el MB51.
    material: (filas,) índice del material de cada fila.
    a_vacios: (filas,) True si la fila regresa a vacíos al salir; las demás
    salen a otra estación (sucios a reparación, reparación a scrap).
    """

    listo: np.ndarray
    material: np.ndarray
    a_vacios: np.ndarray

    @cached_property
    def cola(self) -> Cola:
        return Cola.de(self.listo)

    @cached_property
    def traza_a_vacios(self) -> np.ndarray:
        """Lo que la traza regresó a vacíos, por material y día."""
        materiales = int(self.material.max()) + 1 if self.material.size else 0
        out = np.zeros((materiales, self.listo.shape[1]))
        np.add.at(out, self.material[self.a_vacios], self.listo[self.a_vacios])
        return out


@dataclass(frozen=True)
class Resultado:
    saldo: np.ndarray  # (materiales, días)
    faltante: np.ndarray  # (materiales, días)
    flota_min: np.ndarray  # (materiales,) lo más bajo de vacíos sin piso
    liberado: dict[str, np.ndarray]  # estación → (días,)
    listo: dict[str, np.ndarray]  # estación → (días,)


def simular(
    vacios_delta: np.ndarray,
    estaciones: dict[str, Estacion],
    capacidad: dict[str, np.ndarray],
) -> Resultado:
    """
    Una planta y un tipo de empaque con la capacidad de cada estación.

    vacios_delta es el cambio de vacíos de la traza, que ya trae las salidas de
    las estaciones en su fecha del MB51. Se quita lo que la traza regresó a
    vacíos y se pone lo que la estación deja salir con su capacidad.
    """
    delta = vacios_delta.astype(float).copy()
    materiales, dias = delta.shape
    liberado, listo = {}, {}
    for nombre, est in estaciones.items():
        cola = est.cola
        lote, t, sale = cola.salidas(capacidad[nombre])
        fila = cola.f[lote]
        a_vac = est.a_vacios[fila]
        idx = est.material[fila[a_vac]] * dias + t[a_vac]
        delta += np.bincount(idx, sale[a_vac], minlength=materiales * dias).reshape(
            materiales, dias
        )
        traza = est.traza_a_vacios
        delta[: traza.shape[0]] -= traza
        liberado[nombre] = np.bincount(t, sale, minlength=dias)
        listo[nombre] = est.listo.sum(axis=0)
    saldo, faltante = vacios(delta)
    flota_min = delta.cumsum(axis=1).min(axis=1) if delta.shape[1] else np.zeros(0)
    return Resultado(saldo, faltante, flota_min, liberado, listo)


def capacidad_diaria(
    habil: np.ndarray,
    por_dia: float,
    paro: np.ndarray | None = None,
) -> np.ndarray:
    """Capacidad por día: por_dia en día hábil, cero en inhábil y en paro."""
    cap = np.where(habil, por_dia, 0.0)
    if paro is not None:
        cap = np.where(paro, 0.0, cap)
    return cap


def dias_de_paro(habil: np.ndarray, inicio: int, dias: int) -> np.ndarray:
    """Los primeros `dias` días hábiles desde `inicio`, sin contar inhábiles."""
    paro = np.zeros(len(habil), dtype=bool)
    hab = np.nonzero(habil[inicio:])[0][:dias] + inicio
    paro[hab] = True
    return paro


# ---------------------------------------------------------------------------
# Escenarios sobre las tablas de dbt
# ---------------------------------------------------------------------------

ESTACIONES = ("lavado", "reparacion")


def _regla(esc: pl.DataFrame, estacion: str, planta: str, tipo: str) -> dict | None:
    """
    La fila del escenario que aplica a una estación, planta y tipo: la de
    planta sobre la general, y la de tipo sobre la que aplica a los dos.
    """
    filas = esc.filter(
        (pl.col("estacion") == estacion)
        & (pl.col("planta").is_null() | (pl.col("planta") == planta))
        & (pl.col("tipo_material").is_null() | (pl.col("tipo_material") == tipo))
    )
    if filas.is_empty():
        return None
    return filas.sort(pl.col("planta").is_null(), pl.col("tipo_material").is_null()).row(
        0, named=True
    )


def _matriz(df: pl.DataFrame, filas: pl.DataFrame, llave: list[str], dias: int) -> np.ndarray:
    out = np.zeros((filas.height, dias))
    if df.is_empty():
        return out
    pos = df.join(filas.with_row_index("_f"), on=llave, how="inner", nulls_equal=True).select(
        "_f", "_t", "cantidad"
    )
    np.add.at(out, (pos["_f"].to_numpy(), pos["_t"].to_numpy()), pos["cantidad"].to_numpy())
    return out


@dataclass(frozen=True)
class Planta:
    """Matrices de una planta y un tipo de empaque, listas para simular."""

    materiales: pl.DataFrame
    vacios_delta: np.ndarray
    estaciones: dict[str, Estacion]
    salida_media: dict[str, float]
    costo: np.ndarray


def armar_planta(
    calendario: pl.DataFrame,
    lotes: pl.DataFrame,
    vac: pl.DataFrame,
    costos: pl.DataFrame,
) -> Planta:
    """
    calendario: fecha, habil, estable en orden. lotes: material, estacion,
    a_vacios, fecha, cantidad. vac: material, fecha, delta. costos: material,
    costo_unitario_usd. Todo de una planta y un tipo.
    """
    dias = calendario.height
    t = calendario.select("fecha", pl.int_range(dias).alias("_t"))
    habil_estable = (calendario["habil"] & calendario["estable"]).to_numpy()

    materiales = (
        pl.concat([vac.select("material"), lotes.select("material")])
        .unique()
        .sort("material")
        .join(costos, on="material", how="left")
    )
    idx = materiales.select("material").with_row_index("_m")
    delta = _matriz(
        vac.join(t, on="fecha").rename({"delta": "cantidad"}),
        materiales.select("material"),
        ["material"],
        dias,
    )

    estaciones, media = {}, {}
    for nombre in ESTACIONES:
        lo = lotes.filter(pl.col("estacion") == nombre).join(t, on="fecha")
        filas = lo.select("material", "a_vacios").unique().sort("material", "a_vacios")
        listo = _matriz(lo, filas, ["material", "a_vacios"], dias)
        mat = filas.join(idx, on="material", how="left")["_m"].to_numpy().astype(np.int64)
        estaciones[nombre] = Estacion(listo, mat, filas["a_vacios"].to_numpy().astype(bool))
        n = habil_estable.sum()
        media[nombre] = float(listo[:, habil_estable].sum() / n) if n else 0.0

    costo = materiales["costo_unitario_usd"].fill_null(0.0).to_numpy()
    return Planta(materiales, delta, estaciones, media, costo)


def _capacidades(
    reglas: dict[str, dict | None],
    p: Planta,
    habil: np.ndarray,
    paro: np.ndarray | None,
) -> tuple[dict[str, np.ndarray], dict[str, float | None]]:
    caps, por_dia = {}, {}
    for nombre in ESTACIONES:
        r = reglas[nombre]
        if r is None or (r["utilizacion"] is None and r["contenedores_dia"] is None):
            caps[nombre] = np.full(len(habil), np.inf)
            por_dia[nombre] = None
            continue
        c = r["contenedores_dia"] or p.salida_media[nombre] / r["utilizacion"]
        dias_paro = r["paro_dias"] or 0
        caps[nombre] = capacidad_diaria(habil, c, paro if dias_paro else None)
        por_dia[nombre] = c
    return caps, por_dia


def _paro_dias(reglas: dict[str, dict | None]) -> int:
    return max((r["paro_dias"] or 0 for r in reglas.values() if r is not None), default=0)


def _resumen(r: Resultado, p: Planta, estable: np.ndarray) -> dict:
    out = {
        "faltante": float(r.faltante.sum()),
        "dias_con_faltante": int((r.faltante.sum(axis=0) > 0).sum()),
        "materiales": int(p.materiales.height),
        "materiales_con_faltante": int((r.faltante.sum(axis=1) > 0).sum()),
        "flota_falta": float(np.maximum(-r.flota_min, 0).sum()),
        "flota_falta_usd": float((np.maximum(-r.flota_min, 0) * p.costo).sum()),
        "flota_sobra": float(np.maximum(r.flota_min, 0).sum()),
        "flota_sobra_usd": float((np.maximum(r.flota_min, 0) * p.costo).sum()),
    }
    for nombre in ESTACIONES:
        cola = (r.listo[nombre] - r.liberado[nombre]).cumsum()
        listo = r.listo[nombre][estable].sum()
        out[f"salida_media_{nombre}"] = p.salida_media[nombre]
        out[f"cola_{nombre}_media"] = float(cola[estable].mean()) if estable.any() else 0.0
        out[f"cola_{nombre}_max"] = float(cola.max()) if cola.size else 0.0
        # Ley de Little: días de espera = cola promedio / entrada promedio.
        out[f"espera_{nombre}_dias"] = float(cola[estable].sum() / listo) if listo else 0.0
    return out


def _diario(r: Resultado, p: Planta, fechas: pl.Series) -> pl.DataFrame:
    cols = {
        "fecha": fechas,
        "vacios_replay": p.vacios_delta.cumsum(axis=1).sum(axis=0),
        "vacios": r.saldo.sum(axis=0),
        "faltante": r.faltante.sum(axis=0),
    }
    for nombre in ESTACIONES:
        cols[f"listo_{nombre}"] = r.listo[nombre]
        cols[f"liberado_{nombre}"] = r.liberado[nombre]
        cols[f"cola_{nombre}"] = (r.listo[nombre] - r.liberado[nombre]).cumsum()
    return pl.DataFrame(cols)


def correr(
    calendario: pl.DataFrame,
    lotes: pl.DataFrame,
    vac: pl.DataFrame,
    costos: pl.DataFrame,
    escenarios: pl.DataFrame,
    peor: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """
    Corre cada escenario en cada planta y tipo de empaque.

    Sin `peor`, devuelve una fila por escenario, planta, tipo e inicio de paro
    (int_sim_planta). Con `peor` (escenario, planta, tipo_material,
    inicio_paro), devuelve la serie diaria de ese inicio (int_sim_diario).
    calendario trae fecha, habil, estable e inicio_paro.
    """
    calendario = calendario.sort("fecha")
    fechas = calendario["fecha"]
    habil = calendario["habil"].to_numpy().astype(bool)
    estable = calendario["estable"].to_numpy().astype(bool)
    inicios = np.nonzero(calendario["inicio_paro"].to_numpy().astype(bool))[0]

    # Un material sin tipo (sin maestro) no se puede simular; lo reporta su
    # regla de calidad y la cifra capacidad queda bloqueada.
    lotes = lotes.drop_nulls(["planta", "tipo_material"])
    vac = vac.drop_nulls(["planta", "tipo_material"])
    salida = []
    claves = lotes.select("planta", "tipo_material").vstack(vac.select("planta", "tipo_material"))
    for planta, tipo in claves.unique().sort("planta", "tipo_material").iter_rows():
        p = armar_planta(
            calendario,
            lotes.filter((pl.col("planta") == planta) & (pl.col("tipo_material") == tipo)),
            vac.filter((pl.col("planta") == planta) & (pl.col("tipo_material") == tipo)),
            costos.filter(pl.col("planta") == planta).select("material", "costo_unitario_usd"),
        )
        for escenario in escenarios["escenario"].unique().sort():
            esc = escenarios.filter(pl.col("escenario") == escenario)
            reglas = {n: _regla(esc, n, planta, tipo) for n in ESTACIONES}
            dias_paro = _paro_dias(reglas)
            if peor is not None:
                elegido = peor.filter(
                    (pl.col("escenario") == escenario)
                    & (pl.col("planta") == planta)
                    & (pl.col("tipo_material") == tipo)
                )
                if elegido.is_empty():
                    continue
                fecha = elegido["inicio_paro"][0]
                lista = (
                    [int(np.nonzero((fechas == fecha).to_numpy())[0][0])]
                    if fecha is not None
                    else [None]
                )
            else:
                lista = list(inicios) if dias_paro else [None]
            for i in lista:
                paro = dias_de_paro(habil, int(i), dias_paro) if i is not None else None
                caps, por_dia = _capacidades(reglas, p, habil, paro)
                r = simular(p.vacios_delta, p.estaciones, caps)
                fila = {
                    "escenario": escenario,
                    "planta": planta,
                    "tipo_material": tipo,
                    "inicio_paro": fechas[int(i)] if i is not None else None,
                    "paro_dias": dias_paro,
                    "capacidad_lavado": por_dia["lavado"],
                    "capacidad_reparacion": por_dia["reparacion"],
                }
                if peor is None:
                    salida.append(pl.DataFrame([fila | _resumen(r, p, estable)]))
                else:
                    d = _diario(r, p, fechas)
                    salida.append(
                        d.with_columns(
                            pl.lit(escenario).alias("escenario"),
                            pl.lit(planta).alias("planta"),
                            pl.lit(tipo).alias("tipo_material"),
                        )
                    )
    if not salida:
        return pl.DataFrame()
    return pl.concat(salida, how="diagonal_relaxed")
