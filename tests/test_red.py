"""Dibujos de la pestaña "Red RPL" (ADR-039)."""

import re
import xml.etree.ElementTree as ET

from rpi.red import ANCHO_MAX, ANCHO_MIN, ESTADOS, anillo, cobertura, en_alerta, grosor, red

NS = "{http://www.w3.org/2000/svg}"

STOCK = {
    "vacios": 900,
    "linea": 120,
    "llenos": 110,
    "cliente": 2500,
    "sucios": 300,
    "reparacion": 20,
    "scrap": 3,
}
FLUJOS = {
    ("vacios", "linea"): 1000,
    ("linea", "llenos"): 1000,
    ("llenos", "cliente"): 1000,
    ("cliente", "sucios"): 950,
    ("sucios", "vacios"): 930,
    ("sucios", "reparacion"): 20,
    ("reparacion", "vacios"): 18,
    ("reparacion", "scrap"): 2,
    ("cliente", "faltante"): 5,
    ("scrap", "baja"): 2,
}


def _anchos(svg: str) -> list[float]:
    return [float(x) for x in re.findall(r'data-ancho="([\d.]+)"', svg)]


def test_svg_valido_con_todos_los_estados():
    raiz = ET.fromstring(anillo(STOCK, FLUJOS, titulo="PLNT_MX01 · KLT"))
    estados = [g.get("data-estado") for g in raiz.iter(f"{NS}g")]
    assert estados == list(ESTADOS)
    textos = "".join(t.text or "" for t in raiz.iter(f"{NS}text"))
    assert "2,500" in textos and "Faltante 702: 5" in textos and "Baja 555: 2" in textos


def test_grosor_proporcional_con_piso_y_tope():
    assert grosor(0, 100) == ANCHO_MIN
    assert grosor(100, 100) == ANCHO_MAX
    assert grosor(500, 100) == ANCHO_MAX
    assert grosor(10, 100) < grosor(50, 100) < grosor(90, 100)
    assert grosor(10, 0) == ANCHO_MIN


def test_escala_fija_entre_semanas():
    # Con la escala de toda la ventana, una semana con la mitad del flujo
    # dibuja tramos más delgados; sin escala, cada semana llenaría el máximo.
    lleno = _anchos(anillo(STOCK, FLUJOS, escala=2000))
    mitad = _anchos(anillo(STOCK, {k: v / 2 for k, v in FLUJOS.items()}, escala=2000))
    assert max(mitad) < max(lleno)
    sola = _anchos(anillo(STOCK, {k: v / 2 for k, v in FLUJOS.items()}))
    assert max(sola) == ANCHO_MAX


def test_vacios_en_rojo_con_alerta():
    sin = ET.fromstring(anillo(STOCK, FLUJOS))
    con = ET.fromstring(anillo(STOCK, FLUJOS, alerta=True, notas={"vacios": "3.1 días"}))
    assert not [g for g in sin.iter(f"{NS}g") if "alerta" in g.get("class", "")]
    rojos = [g.get("data-estado") for g in con.iter(f"{NS}g") if "alerta" in g.get("class", "")]
    assert rojos == ["vacios"]
    assert "3.1 días" in "".join(t.text or "" for t in con.iter(f"{NS}text"))


def test_estado_sin_dato_y_texto_escapado():
    svg = anillo({}, {}, titulo="<planta & tipo>")
    raiz = ET.fromstring(svg)
    assert "—" in "".join(t.text or "" for t in raiz.iter(f"{NS}text"))
    assert "&lt;planta &amp; tipo&gt;" in svg


def test_red_con_plantas_por_pais_y_rutas():
    plantas = [("PLNT_US01", "US", False), ("PLNT_MX01", "MX", True), ("PLNT_MX02", "MX", False)]
    clientes = ["CUST-0002", "CUST-0001"]
    rutas = [
        ("PLNT_MX01", "CUST-0001", 400),
        ("PLNT_MX02", "CUST-0001", 100),
        ("PLNT_US01", "CUST-0002", 0),
        ("PLNT_XX99", "CUST-0001", 50),  # planta fuera de la lista: no se dibuja
        ("PLNT_MX01", None, 30),  # 621 sin cliente
    ]
    raiz = ET.fromstring(red(plantas, [*clientes, None], rutas))
    nodos = [(g.get("data-planta"), g.get("class")) for g in raiz.iter(f"{NS}g")]
    assert nodos == [
        ("PLNT_MX01", "planta alerta"),
        ("PLNT_MX02", "planta"),
        ("PLNT_US01", "planta"),
    ]
    anchos = [float(p.get("data-ancho")) for p in raiz.iter(f"{NS}path")]
    assert len(anchos) == 2
    assert sorted(anchos) == [grosor(100, 400), ANCHO_MAX]


def test_alerta_por_desechable_o_por_cobertura():
    # 700 salidas en la semana son 100 por día: 250 vacíos cubren 2.5 días.
    assert cobertura(250, 700) == 2.5
    assert cobertura(250, 0) is None
    assert en_alerta(250, 700, 0, 3)
    assert not en_alerta(400, 700, 0, 3)
    # Con vacíos de sobra en el total, un material que salió en desechable
    # pone la planta en rojo.
    assert en_alerta(40_000, 700, 12, 3)
    assert not en_alerta(0, 0, 0, 3)


def test_resalta_las_rutas_de_una_planta():
    plantas = [("PLNT_MX01", "MX", False), ("PLNT_MX02", "MX", False)]
    rutas = [("PLNT_MX01", "CUST-0001", 100), ("PLNT_MX02", "CUST-0001", 100)]
    raiz = ET.fromstring(red(plantas, ["CUST-0001"], rutas, resalta="PLNT_MX01"))
    trazos = [(p.get("data-planta"), p.get("stroke")) for p in raiz.iter(f"{NS}path")]
    # La resaltada va al final, encima de las demás, y en otro color.
    assert [t[0] for t in trazos] == ["PLNT_MX02", "PLNT_MX01"]
    assert trazos[0][1] != trazos[1][1]
