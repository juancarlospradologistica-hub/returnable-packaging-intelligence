"""
Dibujos de la pestaña "Red RPL" del dashboard (ADR-039).

Funciones puras que reciben cifras y devuelven SVG como texto. No leen la base
ni dependen de marimo: el dashboard les pasa lo que sale de los marts y aquí
solo se decide la geometría.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from xml.sax.saxutils import escape

# Orden del ciclo y etiqueta de cada estado.
ESTADOS = {
    "vacios": "Vacíos",
    "linea": "Línea",
    "llenos": "Llenos",
    "cliente": "Cliente",
    "sucios": "Sucios",
    "reparacion": "Reparación",
    "scrap": "Scrap",
}
# Salidas definitivas de la flota: no tienen nodo, se dibujan como flecha afuera.
SALIDAS = {"faltante": "Faltante 702", "baja": "Baja 555"}

GRIS, BORDE, TEXTO = "#ecf0f1", "#7f8c8d", "#2c3e50"
ALERTA, ALERTA_FONDO = "#c0392b", "#fadbd8"
FLUJO = "#2c7fb8"

ANCHO_MIN, ANCHO_MAX = 1.0, 16.0


def grosor(valor: float, escala: float) -> float:
    """Grosor de un tramo: proporcional a su flujo contra la escala, con piso."""
    if escala <= 0 or valor <= 0:
        return ANCHO_MIN
    return ANCHO_MIN + (ANCHO_MAX - ANCHO_MIN) * min(valor / escala, 1.0)


def cobertura(vacios: float, salidas_semana: float) -> float | None:
    """Días de salidas a cliente que cubre lo que hay en vacíos."""
    return vacios / (salidas_semana / 7) if salidas_semana else None


def en_alerta(
    vacios: float, salidas_semana: float, desechable_semana: float, politica_dias: float
) -> bool:
    """
    Vacíos en rojo: en la semana algún material salió en desechable, o lo que
    queda cubre menos días que la política de parametros_flota. El total de la
    planta puede cubrir semanas y aun así un material quedarse sin vacíos.
    """
    if desechable_semana > 0:
        return True
    dias = cobertura(vacios, salidas_semana)
    return dias is not None and dias < politica_dias


def _num(v: float | None) -> str:
    return "—" if v is None else f"{v:,.0f}"


# Posición de cada estado. Los cinco del ciclo van sobre el círculo; reparación
# y scrap adentro, entre sucios y vacíos, porque son el desvío de lo dañado.
_CX, _CY, _R = 360.0, 240.0, 165.0


def _sobre_circulo(grados: float) -> tuple[float, float]:
    a = math.radians(grados)
    return _CX + _R * math.cos(a), _CY + _R * math.sin(a)


POSICION = {
    "vacios": _sobre_circulo(-90),
    "linea": _sobre_circulo(-18),
    "llenos": _sobre_circulo(54),
    "cliente": _sobre_circulo(126),
    "sucios": _sobre_circulo(198),
    "reparacion": (_CX - 40.0, _CY - 20.0),
    "scrap": (_CX + 45.0, _CY + 40.0),
}
_RADIO_NODO = 38.0


def _tramo(o: tuple[float, float], d: tuple[float, float], ancho: float, color: str) -> str:
    # Se recorta en el borde de cada nodo para que la flecha no quede tapada.
    dx, dy = d[0] - o[0], d[1] - o[1]
    largo = math.hypot(dx, dy) or 1.0
    ux, uy = dx / largo, dy / largo
    x1, y1 = o[0] + ux * _RADIO_NODO, o[1] + uy * _RADIO_NODO
    x2, y2 = d[0] - ux * (_RADIO_NODO + 6), d[1] - uy * (_RADIO_NODO + 6)
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-opacity="0.55" stroke-width="{ancho:.1f}" '
        f'marker-end="url(#punta)" data-ancho="{ancho:.2f}"/>'
    )


def anillo(
    stock: Mapping[str, float],
    flujos: Mapping[tuple[str, str], float],
    *,
    escala: float | None = None,
    alerta: bool = False,
    notas: Mapping[str, str] | None = None,
    titulo: str = "",
) -> str:
    """
    El ciclo del empaque de una planta en una semana.

    stock: contenedores por estado al cierre. flujos: (origen, destino) →
    contenedores en la semana; origen o destino pueden ser faltante o baja.
    escala: flujo que llena el grosor máximo; fija entre semanas para que una
    animación no cambie de escala. alerta pinta vacíos en rojo. notas agrega
    una línea bajo el número de un estado.
    """
    notas = notas or {}
    escala = escala if escala is not None else max(flujos.values(), default=0.0)
    partes = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 480" '
        'width="100%" style="max-width:720px" role="img" class="rpi-anillo">',
        # Punta de tamaño fijo: con markerUnits por default crece con el grosor.
        "<defs><marker id='punta' viewBox='0 0 10 10' refX='8' refY='5' "
        "markerUnits='userSpaceOnUse' markerWidth='11' markerHeight='11' "
        f"orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 z' fill='{FLUJO}'/>"
        "</marker></defs>",
    ]
    if titulo:
        partes.append(
            f'<text x="{_CX:.0f}" y="22" text-anchor="middle" font-size="15" '
            f'fill="{TEXTO}">{escape(titulo)}</text>'
        )

    for (o, d), v in sorted(flujos.items()):
        if o in POSICION and d in POSICION:
            partes.append(_tramo(POSICION[o], POSICION[d], grosor(v, escala), FLUJO))
    salidas_y = {"faltante": 462.0, "baja": 462.0}
    for (o, d), v in sorted(flujos.items()):
        if o in POSICION and d in SALIDAS and v > 0:
            x, y = POSICION[o]
            fin = (x + (-60 if d == "faltante" else 60), salidas_y[d])
            partes.append(_tramo((x, y), fin, grosor(v, escala), ALERTA))
            partes.append(
                f'<text x="{fin[0]:.1f}" y="{fin[1] + 12:.1f}" text-anchor="middle" '
                f'font-size="11" fill="{ALERTA}">{SALIDAS[d]}: {_num(v)}</text>'
            )

    for estado, etiqueta in ESTADOS.items():
        x, y = POSICION[estado]
        rojo = alerta and estado == "vacios"
        fondo, borde = (ALERTA_FONDO, ALERTA) if rojo else (GRIS, BORDE)
        clase = "estado alerta" if rojo else "estado"
        partes.append(
            f'<g class="{clase}" data-estado="{estado}">'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{_RADIO_NODO}" fill="{fondo}" '
            f'stroke="{borde}" stroke-width="{2.5 if rojo else 1.2}"/>'
            f'<text x="{x:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="12" '
            f'fill="{TEXTO}">{etiqueta}</text>'
            f'<text x="{x:.1f}" y="{y + 11:.1f}" text-anchor="middle" font-size="13" '
            f'font-weight="bold" fill="{ALERTA if rojo else TEXTO}">'
            f"{_num(stock.get(estado))}</text>"
        )
        if estado in notas:
            # La nota va hacia afuera del anillo, donde no pasa ningún tramo.
            # Arriba queda el título: la nota de vacíos va a su derecha. Los
            # estados de adentro llevan la nota abajo, lejos de los tramos.
            dx, dy = x - _CX, y - _CY
            if estado in ("reparacion", "scrap"):
                nx, ny, ancla = x, y + _RADIO_NODO + 14, "middle"
            elif abs(dx) < 40 and dy < 0:
                nx, ny, ancla = x + _RADIO_NODO + 8, y + 4, "start"
            else:
                largo = math.hypot(dx, dy) or 1.0
                nx = x + dx / largo * (_RADIO_NODO + 16)
                ny = y + dy / largo * (_RADIO_NODO + 16) + 4
                ancla = "middle" if abs(dx) < 40 else ("start" if dx > 0 else "end")
            partes.append(
                f'<text x="{nx:.1f}" y="{ny:.1f}" text-anchor="{ancla}" font-size="11" '
                f'fill="{ALERTA if rojo else BORDE}">{escape(notas[estado])}</text>'
            )
        partes.append("</g>")
    partes.append("</svg>")
    return "".join(partes)


def red(
    plantas: Sequence[tuple[str, str, bool]],
    clientes: Sequence[str],
    rutas: Sequence[tuple[str, str, float]],
    *,
    escala: float | None = None,
    resalta: str | None = None,
    titulo: str = "",
) -> str:
    """
    Plantas a la izquierda, agrupadas por país, y clientes a la derecha.

    plantas: (planta, país, alerta). rutas: (planta, cliente, contenedores).
    El grosor de cada ruta es su flujo contra la escala; alerta pinta la planta
    en rojo. resalta deja en azul las rutas de una planta y las demás en gris.
    """
    escala = escala if escala is not None else max((r[2] for r in rutas), default=0.0)
    paso = 22.0
    alto_p = 60 + paso * (len(plantas) + len({p[1] for p in plantas}))
    alto_c = 60 + paso * len(clientes)
    alto = max(alto_p, alto_c, 120)
    x_p, x_c = 150.0, 560.0

    y_planta, filas, y = {}, [], 50.0
    pais_actual = None
    for planta, pais, alerta in sorted(plantas, key=lambda p: (p[1], p[0])):
        if pais != pais_actual:
            filas.append(
                f'<text x="20" y="{y + 4:.1f}" font-size="11" fill="{BORDE}">{escape(pais)}</text>'
            )
            pais_actual = pais
            y += paso
        y_planta[planta] = y
        fondo, borde = (ALERTA_FONDO, ALERTA) if alerta else (GRIS, BORDE)
        clase = "planta alerta" if alerta else "planta"
        filas.append(
            f'<g class="{clase}" data-planta="{escape(planta)}">'
            f'<rect x="{x_p - 105:.1f}" y="{y - 9:.1f}" width="110" height="18" rx="4" '
            f'fill="{fondo}" stroke="{borde}"/>'
            f'<text x="{x_p - 50:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-size="11" '
            f'fill="{ALERTA if alerta else TEXTO}">{escape(planta)}</text></g>'
        )
        y += paso

    y_cliente = {}
    for i, cliente in enumerate(sorted(c for c in clientes if c is not None)):
        yc = 50.0 + paso * i
        y_cliente[cliente] = yc
        filas.append(
            f'<text x="{x_c + 8:.1f}" y="{yc + 4:.1f}" font-size="11" '
            f'fill="{TEXTO}">{escape(cliente)}</text>'
        )

    lineas = []
    # Una ruta sin planta o sin cliente (un 621 sin cliente) no tiene dónde ir.
    for planta, cliente, v in sorted(r for r in rutas if r[0] is not None and r[1] is not None):
        if planta not in y_planta or cliente not in y_cliente or v <= 0:
            continue
        y1, y2 = y_planta[planta], y_cliente[cliente]
        medio = (x_p + x_c) / 2
        propia = resalta is None or planta == resalta
        color, opacidad = (FLUJO, 0.5) if propia else (BORDE, 0.15)
        lineas.append(
            f'<path d="M{x_p + 6:.1f},{y1:.1f} C{medio:.1f},{y1:.1f} {medio:.1f},{y2:.1f} '
            f'{x_c:.1f},{y2:.1f}" fill="none" stroke="{color}" stroke-opacity="{opacidad}" '
            f'stroke-width="{grosor(v, escala):.1f}" data-ancho="{grosor(v, escala):.2f}" '
            f'data-planta="{escape(planta)}"/>'
        )

    cabeza = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 {alto:.0f}" '
        'width="100%" style="max-width:680px" role="img" class="rpi-red">'
    )
    if titulo:
        cabeza += (
            f'<text x="340" y="22" text-anchor="middle" font-size="15" '
            f'fill="{TEXTO}">{escape(titulo)}</text>'
        )
    # Las rutas van debajo de los nodos y la resaltada encima de las demás.
    lineas.sort(key=lambda ruta: resalta is not None and f'data-planta="{escape(resalta)}"' in ruta)
    return cabeza + "".join(lineas) + "".join(filas) + "</svg>"
