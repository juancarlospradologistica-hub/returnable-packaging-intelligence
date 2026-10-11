"""
Cada defecto inyectado lo reporta la regla de su defecto (ADR-028, punto 12).

Corre sobre la base que apunta RPI_DB después de dbt run con los defectos
encendidos; en una base limpia, sin bitácora, revisa que no haya violaciones.
"""

import os

import duckdb
import polars as pl
import pytest

DB_PATH = os.environ.get("RPI_DB", "data/rpi.duckdb")

# Llave con la que la bitácora y las violaciones se encuentran, por defecto.
LINEA = ["planta", "anio_contable", "doc_material", "posicion"]
MATERIAL = ["planta", "material"]
PARTE = ["planta", "parte"]
LLAVE = {
    **dict.fromkeys(["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08"], LINEA),
    **dict.fromkeys(["D09", "D13", "D14", "D15", "D16", "D17", "D18"], MATERIAL),
    **dict.fromkeys(["D10", "D11", "D12"], PARTE),
}


@pytest.fixture(scope="module")
def con():
    try:
        c = duckdb.connect(DB_PATH, read_only=True)
        c.execute("SELECT 1 FROM int_calidad_violaciones LIMIT 1")
    except Exception:
        pytest.skip("Sin base con int_calidad_violaciones: corre dbt antes.")
    yield c
    c.close()


def _tablas(con) -> set[str]:
    return {r[0] for r in con.execute("SHOW TABLES").fetchall()}


@pytest.fixture(scope="module")
def bitacora(con) -> pl.DataFrame:
    if "raw_bitacora_defectos" not in _tablas(con):
        pytest.skip("Base sin defectos inyectados.")
    return con.execute(
        """
        SELECT defecto, Werks AS planta, Matnr AS material, Mjahr AS anio_contable,
               Mblnr AS doc_material, CAST(Zeile AS INTEGER) AS posicion, Parte AS parte
        FROM raw_bitacora_defectos
        """
    ).pl()


@pytest.fixture(scope="module")
def violaciones(con) -> pl.DataFrame:
    return con.execute("SELECT * FROM int_calidad_violaciones").pl()


def test_cada_defecto_lo_reporta_su_regla(bitacora, violaciones):
    faltan = []
    for defecto, llave in sorted(LLAVE.items()):
        inyectado = bitacora.filter(pl.col("defecto") == defecto).select(llave).unique()
        if inyectado.is_empty():
            faltan.append(f"{defecto}: sin casos en la bitácora")
            continue
        reportado = violaciones.filter(pl.col("defecto") == defecto).select(llave).unique()
        sin_regla = inyectado.join(reportado, on=llave, how="anti", nulls_equal=True)
        if not sin_regla.is_empty():
            faltan.append(f"{defecto}: {sin_regla.height} de {inyectado.height} sin reportar")
    assert not faltan, "\n".join(faltan)


def test_falsas_alarmas(bitacora, violaciones):
    """Violaciones de una regla fuera de los registros de su defecto. Se reportan, no fallan."""
    resumen = []
    for defecto, llave in sorted(LLAVE.items()):
        reportado = violaciones.filter(pl.col("defecto") == defecto).select(llave).unique()
        inyectado = bitacora.filter(pl.col("defecto") == defecto).select(llave).unique()
        extra = reportado.join(inyectado, on=llave, how="anti", nulls_equal=True).height
        resumen.append(f"{defecto}: {extra}")
    print("falsas alarmas por defecto: " + ", ".join(resumen))


def test_limpio_sin_violaciones(con, violaciones):
    if "raw_bitacora_defectos" in _tablas(con):
        pytest.skip("Base con defectos inyectados.")
    assert violaciones.is_empty(), violaciones.group_by("regla").len()
