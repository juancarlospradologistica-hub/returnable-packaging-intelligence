import polars as pl

from rpi.schema import MB51Schema


def test_schema_valida_df_ci(df_ci: pl.DataFrame) -> None:
    """El dataset generado en CI pasa el schema MB51 sin errores."""
    MB51Schema.validate(df_ci)


def test_columnas_core_presentes(df_ci: pl.DataFrame) -> None:
    columnas_core = [
        "Werks", "Lgort", "Matnr", "Maktx", "Bwart",
        "Mjahr", "Budat", "Cpudt", "Cputm",
        "Menge", "Meins", "Mblnr", "Zeile",
        "Lifnr", "Kunnr", "Xblnr",
    ]
    faltantes = [c for c in columnas_core if c not in df_ci.columns]
    assert not faltantes, f"Columnas faltantes: {faltantes}"


def test_bwart_solo_valores_validos(df_ci: pl.DataFrame) -> None:
    from rpi.schema import BWART_VALIDOS
    valores_en_df = set(df_ci["Bwart"].unique().to_list())
    invalidos = valores_en_df - set(BWART_VALIDOS)
    assert not invalidos, f"Bwart con valores fuera del enum: {invalidos}"


def test_menge_no_cero(df_ci: pl.DataFrame) -> None:
    ceros = df_ci.filter(pl.col("Menge") == 0).shape[0]
    assert ceros == 0, f"{ceros} filas con Menge == 0 (inválido en MB51)"