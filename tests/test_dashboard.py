"""
El dashboard corre completo sobre la base de RPI_DB (ADR-031, punto 8).

Con los defectos encendidos las secciones bloqueadas cambian por un aviso y la
pestaña de calidad muestra las reglas; ninguna celda puede tronar. En 4b.1 la
tabla de exceso de saldo tronaba sin cierres válidos y tumbaba la pestaña.
"""

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

RAIZ = Path(__file__).resolve().parents[1]
DB = os.environ.get("RPI_DB", "data/rpi.duckdb")


def test_dashboard_corre_sin_errores(tmp_path):
    try:
        c = duckdb.connect(str(RAIZ / DB), read_only=True)
        c.execute("SELECT 1 FROM mart_impacto_defectos LIMIT 1")
        c.close()
    except Exception:
        pytest.skip("Sin base con los marts: corre dbt antes.")
    r = subprocess.run(
        [sys.executable, "-m", "marimo", "export", "html", "notebooks/02_dashboard.py"]
        + ["-o", str(tmp_path / "dashboard.html")],
        cwd=RAIZ,
        env=os.environ | {"RPI_DB": DB},
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
