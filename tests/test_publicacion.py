"""
Bloqueo de publicación (ADR-031, punto 8).

Las pruebas de lógica corren sobre una base en memoria con las dos tablas que
lee el módulo. La última corre sobre la base de RPI_DB: limpia, nada bloqueado;
con los defectos encendidos, las nueve cifras bloqueadas.
"""

import os

import duckdb
import pytest

from rpi.publicacion import CifraBloqueadaError, bloqueadas, exige

CIFRAS = [
    "perdida",
    "tco",
    "brecha",
    "ocioso",
    "ciclo",
    "necesidad",
    "flota",
    "saldo_cliente",
    "serie_mensual",
]


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("CREATE TABLE cifras (cifra VARCHAR)")
    c.executemany("INSERT INTO cifras VALUES (?)", [(x,) for x in CIFRAS])
    c.execute(
        """
        CREATE TABLE mart_calidad_datos (
            regla VARCHAR, severidad VARCHAR, cifra_afectada VARCHAR, violaciones BIGINT
        )
        """
    )
    yield c
    c.close()


def viola(con, regla: str, severidad: str, cifra_afectada: str | None, n: int = 1) -> None:
    con.execute(
        "INSERT INTO mart_calidad_datos VALUES (?, ?, ?, ?)",
        [regla, severidad, cifra_afectada, n],
    )


def test_limpio_sin_bloqueo(con):
    assert bloqueadas(con) == {}
    exige(con, CIFRAS)


def test_bloquea_solo_sus_cifras(con):
    viola(con, "cantidad_en_piezas", "bloquea", "tco ciclo", 3)
    viola(con, "cantidad_en_piezas", "bloquea", "tco ciclo", 2)
    assert bloqueadas(con) == {
        "tco": ["cantidad_en_piezas (5)"],
        "ciclo": ["cantidad_en_piezas (5)"],
    }
    exige(con, ["perdida", "brecha"])
    with pytest.raises(CifraBloqueadaError, match=r"ciclo: cantidad_en_piezas \(5\)"):
        exige(con, ["perdida", "ciclo"])


def test_todas_bloquea_las_nueve(con):
    viola(con, "llave_duplicada", "bloquea", "todas")
    assert sorted(bloqueadas(con)) == sorted(CIFRAS)


def test_alerta_y_ninguna_no_bloquean(con):
    viola(con, "registro_despues_del_cierre", "alerta", "serie_mensual")
    viola(con, "regla_sin_cifra", "bloquea", None)
    assert bloqueadas(con) == {}


def test_cifra_desconocida(con):
    with pytest.raises(ValueError, match="perdidas"):
        exige(con, ["perdidas"])


def test_base_actual():
    """Limpia: nada bloqueado. Con bitácora de defectos: las nueve bloqueadas."""
    try:
        c = duckdb.connect(os.environ.get("RPI_DB", "data/rpi.duckdb"), read_only=True)
        c.execute("SELECT 1 FROM mart_calidad_datos LIMIT 1")
    except Exception:
        pytest.skip("Sin base con mart_calidad_datos: corre dbt antes.")
    try:
        sucia = c.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'raw_bitacora_defectos'"
        ).fetchone()[0]
        esperado = sorted(CIFRAS) if sucia else []
        assert sorted(bloqueadas(c)) == esperado
    finally:
        c.close()
