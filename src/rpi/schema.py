"""
Schema Pandera del dataset MB51 sintetico.

Define el contrato de las 22 columnas (16 core + 6 opcionales) que produce
el generador y que consume el resto del pipeline.

Referencias:
- PROYECTO.md seccion 4 (diccionario de datos y parametros del generador)
- SAP MB51 estandar
"""

from datetime import datetime

import pandera.polars as pa
from pandera.typing.polars import Series

# Codigos de clase de movimiento MB51 que emite el generador.
# Coincide con el mix realista descrito en PROYECTO.md seccion 4.
BWART_VALIDOS = [
    "101",  # Recepcion de mercancia contra PO
    "102",  # Reversa de 101
    "261",  # Consumo a orden
    "309",  # Traslado con cambio de material
    "311",  # Traslado entre almacenes en un mismo centro
    "411",  # Traslado entre stocks especiales
    "501",  # Recepcion sin referencia a PO
    "502",  # Reversa de 501
    "601",  # Salida a cliente
    "602",  # Reversa de 601 (retorno de cliente)
]

# Unidades de medida validas en el dominio de empaques.
MEINS_VALIDAS = ["PC", "EA", "KG"]


class MB51Schema(pa.DataFrameModel):
    """
    Schema de un movimiento MB51 sintetico.

    Convencion de nombres: se respetan los nombres SAP (Werks, Matnr, Bwart, etc.)
    aunque Python prefiera snake_case. Son campos del dominio, no variables locales.
    """

    # ---------- Columnas core (16) ----------

    Werks: Series[str] = pa.Field(
        str_length={"min_value": 4, "max_value": 4},
        description="Centro (planta). SAP siempre 4 caracteres.",
    )
    Lgort: Series[str] = pa.Field(
        str_length={"min_value": 4, "max_value": 4},
        description="Almacen. SAP siempre 4 caracteres.",
    )
    Matnr: Series[str] = pa.Field(
        str_length={"min_value": 1, "max_value": 18},
        description="Codigo de material (empaque).",
    )
    Maktx: Series[str] = pa.Field(
        str_length={"min_value": 1, "max_value": 40},
        description="Texto breve del material.",
    )
    Bwart: Series[str] = pa.Field(
        isin=BWART_VALIDOS,
        description="Clase de movimiento SAP.",
    )
    Mjahr: Series[int] = pa.Field(
        ge=2024,
        le=2027,
        description="Ano contable. Horizonte del dataset: 18 meses ~ 2 anos calendario.",
    )
    Budat: Series[datetime] = pa.Field(
        description="Fecha de contabilizacion.",
    )
    Cpudt: Series[datetime] = pa.Field(
        description="Fecha de registro en sistema. Comparar vs Budat mide disciplina operativa.",
    )
    Cputm: Series[str] = pa.Field(
        str_length={"min_value": 6, "max_value": 6},
        description="Hora de registro en formato HHMMSS (convencion SAP).",
    )
    Menge: Series[float] = pa.Field(
        gt=0,
        description="Cantidad. Positiva por construccion en el generador.",
    )
    Meins: Series[str] = pa.Field(
        isin=MEINS_VALIDAS,
        description="Unidad de medida base.",
    )
    Mblnr: Series[str] = pa.Field(
        str_length={"min_value": 10, "max_value": 10},
        description="Numero de documento material. SAP: 10 caracteres.",
    )
    Zeile: Series[int] = pa.Field(
        ge=1,
        le=999,
        description="Numero de posicion dentro del documento.",
    )
    Lifnr: Series[str] = pa.Field(
        str_length={"min_value": 10, "max_value": 10},
        nullable=True,
        description=(
            "Proveedor. Nullable: solo aplica en movimientos "
            "101/102/461/462/501/502 con socio."
        ),
    )
    Kunnr: Series[str] = pa.Field(
        str_length={"min_value": 10, "max_value": 10},
        nullable=True,
        description="Cliente / consignatario. Nullable: solo aplica en 601/602/631/632.",
    )
    Xblnr: Series[str] = pa.Field(
        str_length={"min_value": 1, "max_value": 16},
        nullable=True,
        description="Referencia externa (embarque, delivery, folio fisico).",
    )

    # ---------- Columnas opcionales (6) ----------

    Ebeln: Series[str] = pa.Field(
        str_length={"min_value": 10, "max_value": 10},
        nullable=True,
        description="Orden de compra. Aplica en movimientos con referencia a PO.",
    )
    Ebelp: Series[int] = pa.Field(
        ge=1,
        le=99999,
        nullable=True,
        description="Posicion de la orden de compra.",
    )
    Sgtxt: Series[str] = pa.Field(
        str_length={"min_value": 1, "max_value": 50},
        nullable=True,
        description="Texto de posicion (placas, folios, comentarios).",
    )
    Umwrk: Series[str] = pa.Field(
        str_length={"min_value": 4, "max_value": 4},
        nullable=True,
        description="Centro destino en traslados 301/311.",
    )
    Umlgo: Series[str] = pa.Field(
        str_length={"min_value": 4, "max_value": 4},
        nullable=True,
        description="Almacen destino en traslados 301/311.",
    )
    Usnam: Series[str] = pa.Field(
        str_length={"min_value": 1, "max_value": 12},
        nullable=True,
        description="Usuario que registro el movimiento.",
    )

    class Config:
        strict = True  # Rechaza columnas extra no declaradas.
        coerce = False  # No convierte tipos silenciosamente; error si no coincide.
