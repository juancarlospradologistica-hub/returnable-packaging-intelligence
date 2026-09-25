# src/rpi/config.py
"""
Configuración parametrizada del generador sintético MB51.
Los valores por defecto reproducen PROYECTO.md §4 (ADR-011).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator


class Country(StrEnum):
    MX = "MX"
    US = "US"
    NI = "NI"


class MaterialType(StrEnum):
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
    monthly_movements_min: int = Field(default=40_000, ge=100)
    monthly_movements_max: int = Field(default=80_000, ge=100)

    @model_validator(mode="after")
    def max_mayor_que_min(self) -> PlantConfig:
        if self.monthly_movements_max <= self.monthly_movements_min:
            raise ValueError(
                "monthly_movements_max debe ser mayor que monthly_movements_min"
            )
        return self


class MaterialMix(BaseModel):
    """Proporción de Matnr por tipo. Debe sumar 1.0."""

    klt: Annotated[float, Field(gt=0.0, lt=1.0)] = 0.60
    rack: Annotated[float, Field(gt=0.0, lt=1.0)] = 0.30
    carton: Annotated[float, Field(gt=0.0, lt=1.0)] = 0.10

    @model_validator(mode="after")
    def suma_uno(self) -> MaterialMix:
        total = round(self.klt + self.rack + self.carton, 10)
        if total != 1.0:
            raise ValueError(
                f"klt + rack + carton debe sumar 1.0, obtenido {total}"
            )
        return self


class CycleConfig(BaseModel):
    """Ciclo 621 → 622 log-normal. Media 25 días, cola larga."""

    mean_days: float = Field(default=25.0, gt=0.0)
    sigma: float = Field(
        default=0.6,
        gt=0.0,
        description="Desviación estándar en escala log. 0.6 genera cola hasta ~90 días.",
    )
    cap_days: int = Field(default=180, ge=30)


class CpudtLagConfig(BaseModel):
    """Lag Budat → Cpudt. Debe sumar 1.0."""

    same_day: Annotated[float, Field(ge=0.0, le=1.0)] = 0.92
    one_to_two_days: Annotated[float, Field(ge=0.0, le=1.0)] = 0.06
    over_48h: Annotated[float, Field(ge=0.0, le=1.0)] = 0.02

    @model_validator(mode="after")
    def suma_uno(self) -> CpudtLagConfig:
        total = round(self.same_day + self.one_to_two_days + self.over_48h, 10)
        if total != 1.0:
            raise ValueError(
                f"same_day + one_to_two_days + over_48h debe sumar 1.0, "
                f"obtenido {total}"
            )
        return self


class CustomerConfig(BaseModel):
    """
    Cuentas cliente (plantas OEM). Supuesto ADR-011: 40 globales,
    de 3 a 8 por planta.
    """

    global_count: int = Field(default=40, ge=1)
    per_plant_min: int = Field(default=3, ge=1)
    per_plant_max: int = Field(default=8, ge=1)

    @model_validator(mode="after")
    def rango_valido(self) -> CustomerConfig:
        if self.per_plant_min > self.per_plant_max:
            raise ValueError("per_plant_min no puede ser mayor que per_plant_max")
        if self.per_plant_max > self.global_count:
            raise ValueError("per_plant_max no puede superar global_count")
        return self


class LossConfig(BaseModel):
    """
    Merma por viaje, heterogénea por cuenta (ADR-011).

    Dos segmentos: las cuentas problema (problem_account_share) concentran
    problem_loss_share de la merma. Con los defaults: 20% de las cuentas
    generan 70% de la merma y la media ponderada es rate_mean.
    """

    rate_mean: float = Field(default=0.005, gt=0.0, le=0.5)
    problem_account_share: float = Field(default=0.20, gt=0.0, lt=1.0)
    problem_loss_share: float = Field(default=0.70, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def concentracion_valida(self) -> LossConfig:
        if self.problem_loss_share <= self.problem_account_share:
            raise ValueError(
                "problem_loss_share debe ser mayor que problem_account_share; "
                "si no, las cuentas problema pierden menos que el promedio"
            )
        if self.rate_high > 0.5:
            raise ValueError(f"rate_high = {self.rate_high:.4f} supera 0.5")
        return self

    @property
    def rate_high(self) -> float:
        return self.rate_mean * self.problem_loss_share / self.problem_account_share

    @property
    def rate_low(self) -> float:
        return (
            self.rate_mean
            * (1 - self.problem_loss_share)
            / (1 - self.problem_account_share)
        )


class MengeRange(BaseModel):
    min: int = Field(ge=1)
    max: int = Field(ge=1)

    @model_validator(mode="after")
    def min_menor_max(self) -> MengeRange:
        if self.min > self.max:
            raise ValueError("min no puede ser mayor que max")
        return self


class MengeConfig(BaseModel):
    """
    Contenedores por línea de salida, por tipo. Supuesto temporal de
    ADR-011; ADR-012 lo reemplaza con la explosión del plan.
    """

    klt: MengeRange = Field(default_factory=lambda: MengeRange(min=1, max=12))
    rack: MengeRange = Field(default_factory=lambda: MengeRange(min=1, max=4))
    carton: MengeRange = Field(default_factory=lambda: MengeRange(min=1, max=6))

    def for_type(self, mat_type: MaterialType) -> MengeRange:
        return {
            MaterialType.KLT: self.klt,
            MaterialType.RACK: self.rack,
            MaterialType.CARTON: self.carton,
        }[mat_type]


def _default_plants() -> list[PlantConfig]:
    """14 plantas canónicas: MX01-06, US01-06, NI01-02."""
    plants: list[PlantConfig] = []
    for i in range(1, 7):
        plants.append(PlantConfig(werks=f"PLNT_MX{i:02d}", country=Country.MX))
    for i in range(1, 7):
        plants.append(PlantConfig(werks=f"PLNT_US{i:02d}", country=Country.US))
    for i in range(1, 3):
        plants.append(PlantConfig(werks=f"PLNT_NI{i:02d}", country=Country.NI))
    return plants


class MaterialCost(BaseModel):
    """Costo unitario en USD por tipo de material."""

    klt: float = Field(default=25.0, gt=0, description="KLT plástico")
    rack: float = Field(default=180.0, gt=0, description="Rack metálico")
    carton: float = Field(default=8.0, gt=0, description="Cartón + tarima madera")


class GeneratorConfig(BaseModel):
    """Configuración completa del generador sintético MB51."""

    plants: list[PlantConfig] = Field(default_factory=_default_plants)
    reference_date: date = Field(
        default=date(2026, 6, 30),
        description="Fecha de corte. Ningún movimiento se emite después.",
    )
    horizon_months: int = Field(default=18, ge=1, le=60)
    global_matnr_pool: int = Field(default=1_200, ge=100)
    global_matnr_share: float = Field(
        default=0.40,
        gt=0.0,
        le=1.0,
        description=(
            "Fracción del pool presente en todas las plantas (ADR-007). "
            "El resto se reparte sin repetir entre plantas."
        ),
    )
    reconciliation_months: int = Field(
        default=3,
        ge=1,
        le=12,
        description="Periodicidad de la conciliación de saldo en cliente.",
    )
    material_mix: MaterialMix = Field(default_factory=MaterialMix)
    customers: CustomerConfig = Field(default_factory=CustomerConfig)
    loss: LossConfig = Field(default_factory=LossConfig)
    menge: MengeConfig = Field(default_factory=MengeConfig)
    cycle: CycleConfig = Field(default_factory=CycleConfig)
    cpudt_lag: CpudtLagConfig = Field(default_factory=CpudtLagConfig)
    cost: MaterialCost = Field(default_factory=MaterialCost)
    random_seed: int | None = Field(
        default=42,
        description="Semilla para reproducibilidad. None = no fijar.",
    )

    @model_validator(mode="after")
    def plantas_no_vacias(self) -> GeneratorConfig:
        if not self.plants:
            raise ValueError("La lista de plantas no puede estar vacía.")
        return self
