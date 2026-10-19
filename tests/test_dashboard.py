"""
El dashboard corre completo sobre la base de RPI_DB (ADR-031, punto 8).

Con los defectos encendidos las secciones bloqueadas cambian por un aviso y la
pestaña de calidad muestra las reglas; ninguna celda puede tronar. En 4b.1 la
tabla de exceso de saldo tronaba sin cierres válidos y tumbaba la pestaña.
"""

import html
import os
import re
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
        plantas, meses, corte = c.execute(
            """
            SELECT COUNT(DISTINCT planta), COUNT(DISTINCT strftime(fecha_contab, '%Y-%m')),
                   (SELECT MAX(corte) FROM int_calendario_necesidad)
            FROM stg_mb51
            WHERE fecha_contab <= (SELECT MAX(corte) FROM int_calendario_necesidad)
            """
        ).fetchone()
        c.close()
    except Exception:
        pytest.skip("Sin base con los marts: corre dbt antes.")
    salida = tmp_path / "dashboard.html"
    # Sin el código: el HTML con código trae el texto del encabezado aunque no se
    # haya ejecutado.
    r = subprocess.run(
        [sys.executable, "-m", "marimo", "export", "html", "notebooks/02_dashboard.py"]
        + ["--no-include-code", "-o", str(salida)],
        cwd=RAIZ,
        env=os.environ | {"RPI_DB": DB},
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]

    # El encabezado decía 14 plantas y 18 meses fijos; el reducido, la ventana
    # recortada y un extracto real tienen otros.
    texto = html.unescape(salida.read_text(encoding="utf-8")).replace("\\u00b7", "·")
    encabezado = re.search(
        r"Flota multi-planta · (\d+) meses · (\d+) plantas · extracto al ([\d.]+)", texto
    )
    assert encabezado, "el encabezado no salió en el HTML"
    assert encabezado.groups() == (str(meses), str(plantas), f"{corte:%d.%m.%Y}")
