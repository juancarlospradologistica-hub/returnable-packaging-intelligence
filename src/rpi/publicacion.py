"""
Bloqueo de publicación (ADR-028, punto 4; ADR-031, punto 8).

Un notebook o el dashboard no presentan una cifra si una regla que bloquea
tiene violaciones sobre ella. Las cifras de cada regla salen de cifra_afectada
del seed reglas_calidad, que mart_calidad_datos ya trae en cada fila.
"""

from __future__ import annotations

import duckdb

TODAS = "todas"


class CifraBloqueadaError(RuntimeError):
    """Una cifra que se iba a publicar tiene una regla que bloquea sobre ella."""


def cifras(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [c for (c,) in con.execute("SELECT cifra FROM cifras ORDER BY cifra").fetchall()]


def bloqueadas(con: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Cifra → reglas que bloquean con violaciones, con su conteo. Vacío si no hay."""
    todas = cifras(con)
    filas = con.execute(
        """
        SELECT regla, ANY_VALUE(cifra_afectada), SUM(violaciones)::BIGINT
        FROM mart_calidad_datos
        WHERE severidad = 'bloquea'
        GROUP BY regla
        ORDER BY regla
        """
    ).fetchall()
    out: dict[str, list[str]] = {}
    for regla, afectada, n in filas:
        claves = (afectada or "").split()
        for c in todas if TODAS in claves else claves:
            out.setdefault(c, []).append(f"{regla} ({n:,})")
    return out


def exige(con: duckdb.DuckDBPyConnection, publica: list[str]) -> None:
    """Detiene la publicación si alguna de las cifras está bloqueada."""
    desconocidas = sorted(set(publica) - set(cifras(con)))
    if desconocidas:
        raise ValueError(f"Cifras fuera del seed cifras: {desconocidas}")
    bloqueo = bloqueadas(con)
    hay = {c: bloqueo[c] for c in publica if c in bloqueo}
    if hay:
        detalle = "; ".join(f"{c}: {', '.join(r)}" for c, r in hay.items())
        raise CifraBloqueadaError(f"No se publica. Reglas que bloquean: {detalle}")
