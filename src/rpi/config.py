# src/rpi/config.py
"""
Configuración parametrizada del generador sintético MB51.
Todos los valores reflejan los parámetros definidos en PROYECTO.md §4.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator


class Country(str, Enum):
    MX = "MX"
    US = "US"
    NI = "NI"


class MaterialType(str, Enum):
    KLT = "KLT"
    RACK = "RACK"
    CARTON = "CARTON"


class PlantConfig(BaseModel):
    """Un centro (Werks) con sus atributos de generación."""

    werks: str = Field(
        ...,
        pattern=r"^PLNT_(MX|US|NI)\d{2}$",
        description="Código de planta sintético. Ejemplo: PLNT_MX01.",
    )
    country: Country
    matnr_count: int = Field(default=480, ge=50, le=500)
    monthly_movements_min: int = Field(default=40_000, ge=100)
    monthly_movements_max: int = Field(default=80_000, ge=100)

    @model_validator(mode="after")
    def max_mayor_que_min(self) -> "PlantConfig":
        if self.monthly_movements_max <= self.monthly_movements_min:
            raise ValueError(
                "monthly_movements_max debe ser mayor que monthly_movements_min"
            )
        return self


class MaterialMix(BaseModel):
    """
    Proporción de cada tipo de material.
    Los tres valores deben sumar 1.0.
    """

    klt: Annotated[float, Field(gt=0.0, lt=1.0)] = 0.60
    rack: Annotated[float, Field(gt=0.0, lt=1.0)] = 0.30
    carton: Annotated[float, Field(gt=0.0, lt=1.0)] = 0.10

    @model_validator(mode="after")
    def suma_uno(self) -> "MaterialMix":
        total = round(self.klt + self.rack + self.carton, 10)
        if total != 1.0:
            raise ValueError(
                f"klt + rack + carton debe sumar 1.0, obtenido {total}"
            )
        return self


class CycleConfig(BaseModel):
    """
    Distribución log-normal del ciclo 601 → 602.
    Media 25 días, cola larga hasta ~90 días.
    """

    mean_days: float = Field(default=25.0, gt=0.0)
    sigma: float = Field(
        default=0.6,
        gt=0.0,
        description="Desviación estándar en escala log. 0.6 genera cola hasta ~90 días.",
    )
    cap_days: int = Field(default=180, ge=30)


class CpudtLagConfig(BaseModel):
    """
    Lag entre Budat (fecha contabilización) y Cpudt (fecha registro sistema).
    Los tres valores deben sumar 1.0.
    """

    same_day: Annotated[float, Field(ge=0.0, le=1.0)] = 0.92
    one_to_two_days: Annotated[float, Field(ge=0.0, le=1.0)] = 0.06
    over_48h: Annotated[float, Field(ge=0.0, le=1.0)] = 0.02

    @model_validator(mode="after")
    def suma_uno(self) -> "CpudtLagConfig":
        total = round(self.same_day + self.one_to_two_days + self.over_48h, 10)
        if total != 1.0:
            raise ValueError(
                f"same_day + one_to_two_days + over_48h debe sumar 1.0, "
                f"obtenido {total}"
            )
        return self


def _default_plants() -> list[PlantConfig]:
    """
    Lista canónica de 14 plantas sintéticas.
    Orden: MX01-06, US01-06, NI01-02.
    """
    plants: list[PlantConfig] = []
    for i in range(1, 7):
        plants.append(PlantConfig(werks=f"PLNT_MX{i:02d}", country=Country.MX))
    for i in range(1, 7):
        plants.append(PlantConfig(werks=f"PLNT_US{i:02d}", country=Country.US))
    for i in range(1, 3):
        plants.append(PlantConfig(werks=f"PLNT_NI{i:02d}", country=Country.NI))
    return plants


class GeneratorConfig(BaseModel):
    """
    Configuración completa del generador sintético MB51.
    Instanciar con defaults reproduce los parámetros de PROYECTO.md §4.
    """

    plants: list[PlantConfig] = Field(default_factory=_default_plants)
    horizon_months: int = Field(default=18, ge=1, le=60)
    global_matnr_pool: int = Field(
    default=1_200,
    ge=100,
    description=(
        "Total de Matnr únicos en el universo. "
        "El 40% circula en todas las plantas (~480 Matnr compartidos)."
    ),
)
    material_mix: MaterialMix = Field(default_factory=MaterialMix)
    loss_rate: float = Field(default=0.02, ge=0.0, le=0.5)
    cycle: CycleConfig = Field(default_factory=CycleConfig)
    cpudt_lag: CpudtLagConfig = Field(default_factory=CpudtLagConfig)
    random_seed: int | None = Field(
        default=42,
        description="Semilla para reproducibilidad. None = no fijar.",
    )

    @model_validator(mode="after")
    def plantas_no_vacias(self) -> "GeneratorConfig":
        if not self.plants:
            raise ValueError("La lista de plantas no puede estar vacía.")
        return self