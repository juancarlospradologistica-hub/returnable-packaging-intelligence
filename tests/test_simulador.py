"""Núcleo del gemelo de la red RPL (ADR-038): cola con capacidad y vacíos."""

import datetime as dt

import numpy as np
import polars as pl
import pytest

from rpi.simulador import (
    Estacion,
    capacidad_diaria,
    correr,
    dias_de_paro,
    liberar,
    simular,
    vacios,
)

# Dos semanas que arrancan en lunes.
HABIL = np.array([True] * 5 + [False] * 2 + [True] * 5 + [False] * 2)


def _traza(seed: int = 7, filas: int = 6) -> np.ndarray:
    rng = np.random.default_rng(seed)
    listo = rng.integers(0, 30, (filas, len(HABIL))).astype(float)
    listo[:, ~HABIL] = 0
    return listo


def test_sin_limite_es_la_traza():
    listo = _traza()
    lib = liberar(listo, np.full(len(HABIL), np.inf))
    np.testing.assert_allclose(lib, listo)


def test_respeta_la_capacidad_y_el_dia_inhabil():
    listo = _traza()
    cap = capacidad_diaria(HABIL, 40.0)
    lib = liberar(listo, cap)
    assert (lib.sum(axis=0) <= cap + 1e-9).all()
    assert (lib[:, ~HABIL] == 0).all()


def test_nunca_sale_antes_de_estar_listo():
    listo = _traza()
    lib = liberar(listo, capacidad_diaria(HABIL, 40.0))
    assert (lib.cumsum(axis=1) <= listo.cumsum(axis=1) + 1e-9).all()


def test_no_deja_capacidad_ociosa_con_cola():
    listo = _traza()
    cap = capacidad_diaria(HABIL, 40.0)
    lib = liberar(listo, cap)
    cola = (listo - lib).sum(axis=0).cumsum()
    con_cola = cola > 1e-9
    np.testing.assert_allclose(lib.sum(axis=0)[con_cola], cap[con_cola])


def test_cola_fifo_por_dia_listo():
    listo = np.zeros((2, 4))
    listo[1, 0] = 5  # el lote más viejo está en la segunda fila
    listo[0, 1] = 5
    lib = liberar(listo, np.full(4, 4.0))
    np.testing.assert_allclose(lib[1], [4, 1, 0, 0])
    np.testing.assert_allclose(lib[0], [0, 3, 2, 0])


def test_lo_que_no_sale_antes_del_corte_se_queda_en_cola():
    listo = np.zeros((1, 3))
    listo[0, 2] = 10
    lib = liberar(listo, np.full(3, 4.0))
    np.testing.assert_allclose(lib[0], [0, 0, 4])


def test_capacidad_mal_formada():
    with pytest.raises(ValueError):
        liberar(np.ones((1, 3)), np.ones(2))
    with pytest.raises(ValueError):
        liberar(-np.ones((1, 3)), np.ones(3))


def test_vacios_con_piso_en_cero():
    saldo, falta = vacios(np.array([[5.0, -3.0, -4.0, 2.0]]))
    np.testing.assert_allclose(saldo[0], [5, 2, 0, 2])
    np.testing.assert_allclose(falta[0], [0, 0, 2, 0])


def test_dias_de_paro_solo_cuenta_habiles():
    paro = dias_de_paro(HABIL, 3, 4)
    assert np.nonzero(paro)[0].tolist() == [3, 4, 7, 8]


def _planta():
    """Un material con flota de 50 y un lavado que regresa todo a vacíos."""
    dias = len(HABIL)
    listo = np.zeros((2, dias))
    listo[0, HABIL] = 20  # sucios que regresan a vacíos
    listo[1, HABIL] = 2  # sucios que pasan a reparación
    salidas = np.where(HABIL, -20.0, 0.0)
    delta = (listo[0] + salidas)[None, :].copy()
    delta[0, 0] += 50  # apertura
    est = Estacion(listo, np.array([0, 0]), np.array([True, False]))
    return delta, {"lavado": est}


def test_con_capacidad_sin_limite_reproduce_vacios():
    delta, est = _planta()
    r = simular(delta, est, {"lavado": np.full(len(HABIL), np.inf)})
    np.testing.assert_allclose(r.saldo, delta.cumsum(axis=1))
    assert r.faltante.sum() == 0
    assert r.flota_min[0] == delta.cumsum(axis=1).min()


def test_capacidad_corta_baja_vacios_y_saca_desechable():
    delta, est = _planta()
    cap = capacidad_diaria(HABIL, 18.0)
    r = simular(delta, est, {"lavado": cap})
    # Salen 18 al día de 22 listos: la cola crece 4 al día hábil y la parte
    # a vacíos llega tarde. Lo que va a reparación no toca vacíos.
    assert r.liberado["lavado"][HABIL].tolist() == [18.0] * HABIL.sum()
    assert r.flota_min[0] < delta.cumsum(axis=1).min()
    assert (r.saldo >= 0).all()
    np.testing.assert_allclose(
        r.saldo[0, -1] - r.faltante.sum(),
        delta.sum() - (est["lavado"].listo[0] - _a_vacios(est, cap)).sum(),
    )


def test_flota_que_falta_es_el_desechable_acumulado():
    # Sin piso, lo más bajo de vacíos dice cuánta flota faltó; con Lindley, la
    # misma cantidad sale en desechable.
    delta, est = _planta()
    r = simular(delta, est, {"lavado": capacidad_diaria(HABIL, 10.0)})
    assert r.flota_min[0] < 0
    np.testing.assert_allclose(-r.flota_min[0], r.faltante.sum())


def _a_vacios(est, cap):
    return liberar(est["lavado"].listo, cap)[0]


# ---------------------------------------------------------------------------
# Escenarios sobre tablas como las de dbt
# ---------------------------------------------------------------------------


def _tablas():
    fechas = [dt.date(2025, 1, 6) + dt.timedelta(days=i) for i in range(21)]
    habil = [f.weekday() < 5 for f in fechas]
    cal = pl.DataFrame(
        {
            "fecha": fechas,
            "habil": habil,
            "estable": [True] * 21,
            "inicio_paro": [f.weekday() == 0 and i < 14 for i, f in enumerate(fechas)],
        }
    )
    lotes, vac = [], []
    for planta, n in (("P1", 1), ("P2", 2)):
        for i, f in enumerate(fechas):
            if not habil[i]:
                continue
            for mat, q in (("A", 20 * n), ("B", 10 * n)):
                lotes.append((planta, "KLT", mat, "lavado", True, f, q))
                vac.append((planta, "KLT", mat, f, q - q))  # regresa lo que sale
            lotes.append((planta, "KLT", "A", "lavado", False, f, 2))
            lotes.append((planta, "KLT", "A", "reparacion", True, f, 1))
            vac.append((planta, "KLT", "A", f, 1 - 3))
        for mat, q in (("A", 60 * n), ("B", 25 * n)):
            vac.append((planta, "KLT", mat, fechas[0], q))
    lotes = pl.DataFrame(
        lotes,
        schema=["planta", "tipo_material", "material", "estacion", "a_vacios", "fecha", "cantidad"],
        orient="row",
    )
    vac = pl.DataFrame(
        vac, schema=["planta", "tipo_material", "material", "fecha", "delta"], orient="row"
    )
    costos = pl.DataFrame(
        {
            "planta": ["P1", "P1", "P2", "P2"],
            "material": ["A", "B", "A", "B"],
            "costo_unitario_usd": [25.0, 25.0, 25.0, 25.0],
        }
    )
    return cal, lotes, vac, costos


def _escenarios(*filas):
    return pl.DataFrame(
        list(filas),
        schema={
            "escenario": pl.String,
            "estacion": pl.String,
            "tipo_material": pl.String,
            "planta": pl.String,
            "utilizacion": pl.Float64,
            "contenedores_dia": pl.Float64,
            "paro_dias": pl.Int32,
        },
        orient="row",
    )


def test_replay_reproduce_la_traza():
    cal, lotes, vac, costos = _tablas()
    esc = _escenarios(("replay", "lavado", None, None, None, None, 0))
    r = correr(cal, lotes, vac, costos, esc)
    assert r["faltante"].sum() == 0
    assert r["cola_lavado_max"].max() == 0
    assert r["capacidad_lavado"].is_null().all()
    # Lo más bajo de vacíos en la traza: A arranca con 60 y pierde 2 por día hábil.
    p1 = r.filter(r["planta"] == "P1").row(0, named=True)
    assert p1["flota_sobra"] == (60 - 2 * 15) + 25
    assert p1["flota_sobra_usd"] == p1["flota_sobra"] * 25


def test_capacidad_por_utilizacion_y_por_planta():
    cal, lotes, vac, costos = _tablas()
    esc = _escenarios(
        ("x", "lavado", None, None, 0.8, None, 0),
        ("x", "lavado", "KLT", "P2", None, 50.0, 0),
    )
    r = correr(cal, lotes, vac, costos, esc).sort("planta")
    # P1 sale 32 por día hábil: 32 / 0.8. P2 usa su fila propia.
    assert r["capacidad_lavado"].to_list() == [pytest.approx(40.0), 50.0]
    assert r["capacidad_reparacion"].is_null().all()


def test_paro_corre_cada_lunes_posible():
    cal, lotes, vac, costos = _tablas()
    esc = _escenarios(
        ("paro", "lavado", None, None, 0.8, None, 3),
        ("paro", "reparacion", None, None, 0.8, None, 0),
    )
    r = correr(cal, lotes, vac, costos, esc)
    assert r.height == 2 * 2  # dos plantas, dos lunes
    assert r["inicio_paro"].n_unique() == 2
    assert (r["paro_dias"] == 3).all()
    assert (r["cola_lavado_max"] > 0).all()


def test_menos_capacidad_nunca_mejora():
    cal, lotes, vac, costos = _tablas()
    utilizaciones = [0.5, 0.8, 0.95, 1.0, 1.3]
    esc = _escenarios(*[(f"u{u}", "lavado", None, None, u, None, 0) for u in utilizaciones])
    r = correr(cal, lotes, vac, costos, esc)
    for planta in ("P1", "P2"):
        filas = r.filter(r["planta"] == planta).sort("capacidad_lavado", descending=True)
        assert filas["faltante"].is_sorted()
        assert filas["flota_sobra"].is_sorted(descending=True)
        assert filas["cola_lavado_media"].is_sorted()
    assert r["faltante"].max() > 0


def test_serie_diaria_del_inicio_elegido():
    cal, lotes, vac, costos = _tablas()
    esc = _escenarios(("paro", "lavado", None, None, 0.8, None, 3))
    resumen = correr(cal, lotes, vac, costos, esc)
    peor = resumen.sort("faltante", descending=True).group_by("planta").first()
    d = correr(cal, lotes, vac, costos, esc, peor=peor)
    assert d.height == 2 * cal.height
    for fila in peor.iter_rows(named=True):
        serie = d.filter(pl.col("planta") == fila["planta"])
        assert serie["faltante"].sum() == pytest.approx(fila["faltante"])
        assert serie["cola_lavado"].max() == pytest.approx(fila["cola_lavado_max"])
    # La cola es lo listo menos lo liberado, acumulado.
    p1 = d.filter(pl.col("planta") == "P1")
    np.testing.assert_allclose(
        p1["cola_lavado"], (p1["listo_lavado"] - p1["liberado_lavado"]).cum_sum()
    )
