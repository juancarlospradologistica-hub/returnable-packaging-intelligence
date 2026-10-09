"""
Schemas Pandera del dataset sintetico.

MB51Schema define el contrato de las 22 columnas (16 core + 6 opcionales) que
produce el generador y que consume el resto del pipeline. Partes, instruccion de
empaque y plan de produccion son el contrato de entrada de Fase 3b (ADR-022).

Referencias:
- PROYECTO.md seccion 4 (diccionario de datos y parametros del generador)
- SAP MB51 estandar
"""

from datetime import date

import pandera.polars as pa
from pandera.typing.polars import Series

BWART_VALIDOS = [
    "101",
    "102",
    "261",
    "311",
    "325",
    "343",
    "344",
    "555",
    "601",
    "621",
    "622",
    "702",
]

MEINS_VALIDAS = ["PC", "EA", "KG"]


class MB51Schema(pa.DataFrameModel):
    """
    Schema de un movimiento MB51 sintetico.

    Convencion de nombres: se respetan los nombres SAP (Werks, Matnr, Bwart, etc.)
    aunque Python prefiera snake_case. Son campos del dominio, no variables locales.
    """

    # ---------- Columnas core (16) ----------

    Werks: Series[str] = pa.Field(
        str_length={"min_value": 4, "max_value": 12},
        description="Centro (planta). SAP real: 4 caracteres. Sintetico: hasta 12 (prefijo PLNT_).",
    )
    Lgort: Series[str] = pa.Field(
        str_length={"min_value": 4, "max_value": 12},
        nullable=True,
        description="Almacen. Nulo en 702 con stock especial V: MSKU no lleva almacen.",
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
    Budat: Series[date] = pa.Field(
        description="Fecha de contabilizacion.",
    )
    Cpudt: Series[date] = pa.Field(
        description="Fecha de registro en sistema. Comparar vs Budat mide disciplina operativa.",
    )
    Cputm: Series[str] = pa.Field(
        str_length={"min_value": 6, "max_value": 8},
        description="Hora de registro en formato HHMMSS (convencion SAP).",
    )
    Menge: Series[int] = pa.Field(
        description=(
            "Cantidad del movimiento con signo SAP: salidas negativas "
            "(102, 261, 555, 601, 621, 702, 311), entradas positivas. "
            "Traslados 311 en dos posiciones que suman cero."
        ),
    )
    Meins: Series[str] = pa.Field(
        isin=MEINS_VALIDAS,
        description="Unidad de medida base.",
    )
    Mblnr: Series[str] = pa.Field(
        str_length={"min_value": 10, "max_value": 10},
        description="Numero de documento material. SAP: 10 caracteres.",
    )
    Zeile: Series[str] = pa.Field(
        str_length={"min_value": 4, "max_value": 4},
        description="Numero de posicion dentro del documento. Formato SAP: 4 digitos con ceros.",
    )
    Lifnr: Series[str] = pa.Field(
        str_length={"min_value": 1, "max_value": 12},
        nullable=True,
        description=("Proveedor. Nullable: solo aplica en movimientos 101/102 del cartón."),
    )
    Kunnr: Series[str] = pa.Field(
        str_length={"min_value": 1, "max_value": 12},
        nullable=True,
        description="Cliente / cuenta de stock especial V. Solo en 601, 621, 622 y 702.",
    )
    Xblnr: Series[str] = pa.Field(
        str_length={"min_value": 1, "max_value": 16},
        nullable=True,
        description="Referencia externa (embarque, delivery, folio fisico).",
    )
    Costo_usd: Series[float] = pa.Field(
        gt=0.0,
        description="Costo unitario en USD por tipo de material. Derivado del generador.",
    )

    # ---------- Columnas opcionales (6) ----------

    Ebeln: Series[str] | None = pa.Field(
        str_length={"min_value": 10, "max_value": 10},
        nullable=True,
        description="Orden de compra. Aplica en movimientos con referencia a PO.",
    )
    Ebelp: Series[int] | None = pa.Field(
        ge=1,
        le=99999,
        nullable=True,
        description="Posicion de la orden de compra.",
    )
    Sgtxt: Series[str] | None = pa.Field(
        str_length={"min_value": 1, "max_value": 50},
        nullable=True,
        description="Texto de posicion (placas, folios, comentarios).",
    )
    Umwrk: Series[str] | None = pa.Field(
        str_length={"min_value": 4, "max_value": 4},
        nullable=True,
        description="Centro destino en traslados 301/311.",
    )
    Umlgo: Series[str] | None = pa.Field(
        str_length={"min_value": 4, "max_value": 4},
        nullable=True,
        description="Almacen destino en traslados 301/311.",
    )
    Usnam: Series[str] | None = pa.Field(
        str_length={"min_value": 1, "max_value": 12},
        nullable=True,
        description="Usuario que registro el movimiento.",
    )

    class Config:
        strict = False
        coerce = False


ESCENARIOS_VALIDOS = ["estable", "arranque", "fin_serie"]


class PartesSchema(pa.DataFrameModel):
    """Parte terminada por planta y su cliente. Llave: Werks, Parte."""

    Werks: Series[str] = pa.Field(str_length={"min_value": 4, "max_value": 12})
    Parte: Series[str] = pa.Field(str_length={"min_value": 1, "max_value": 18})
    Kunnr: Series[str] = pa.Field(str_length={"min_value": 1, "max_value": 12})
    Escenario: Series[str] = pa.Field(
        isin=ESCENARIOS_VALIDOS,
        nullable=True,
        description=(
            "Solo sintetico: estable, arranque o fin de serie. En un extracto real "
            "sale del calendario del programa (SOP/EOP) o va vacio."
        ),
    )

    class Config:
        strict = True
        unique = ["Werks", "Parte"]


class InstruccionEmpaqueSchema(pa.DataFrameModel):
    """Una parte, un empaque, piezas fijas por contenedor (POP1). Llave: Werks, Parte."""

    Werks: Series[str] = pa.Field(str_length={"min_value": 4, "max_value": 12})
    Parte: Series[str] = pa.Field(str_length={"min_value": 1, "max_value": 18})
    Matnr: Series[str] = pa.Field(str_length={"min_value": 1, "max_value": 18})
    Piezas: Series[int] = pa.Field(gt=0, description="Piezas por contenedor.")

    class Config:
        strict = True
        unique = ["Werks", "Parte"]


class PlanProduccionSchema(pa.DataFrameModel):
    """Plan semanal en piezas (MD61/PBED). Llave: Werks, Parte, Semana (lunes)."""

    Werks: Series[str] = pa.Field(str_length={"min_value": 4, "max_value": 12})
    Parte: Series[str] = pa.Field(str_length={"min_value": 1, "max_value": 18})
    Semana: Series[date] = pa.Field(description="Lunes de la semana del plan.")
    Piezas: Series[int] = pa.Field(ge=0)

    class Config:
        strict = True
        unique = ["Werks", "Parte", "Semana"]
