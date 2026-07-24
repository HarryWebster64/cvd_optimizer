"""Pydantic models for the CVD Optimizer parameter specification (params.yaml).

Mirrors the "Parameter Specification (YAML)" layout in ARCHITECTURE.md:
chamber, feedstock_gas, microwave_source, openfoam, warpx, xolotl.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Annotated, Any

import pint
import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    field_validator,
)
from pydantic_core import core_schema

ureg = pint.UnitRegistry()
Quantity = ureg.Quantity


class _PintQuantityAnnotation:
    """Core-schema glue letting pydantic parse/validate `pint.Quantity` fields.

    Accepts strings like "30 cm", validates the result is dimensionally
    compatible with `reference_unit` (e.g. "meter"), and serializes back
    to a string.
    """

    def __init__(self, reference_unit: str) -> None:
        self.reference_unit = reference_unit

    def __get_pydantic_core_schema__(
        self, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate(value: Any) -> Quantity:
            if isinstance(value, Quantity):
                qty = value
            elif isinstance(value, str):
                try:
                    qty = ureg.Quantity(value)
                except pint.PintError as exc:
                    raise ValueError(f"could not parse {value!r} as a quantity: {exc}") from exc
            else:
                raise TypeError(f"expected a string or pint.Quantity, got {value!r}")

            if not qty.check(self.reference_unit):
                raise ValueError(
                    f"{value!r} has dimensionality {qty.dimensionality}, "
                    f"expected dimensionality compatible with {self.reference_unit!r}"
                )
            return qty

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )


def PintField(reference_unit: str) -> type:
    """Build an Annotated pint.Quantity type constrained to `reference_unit`'s dimensionality."""
    return Annotated[Quantity, _PintQuantityAnnotation(reference_unit)]


Length = PintField("meter")
Temperature = PintField("kelvin")
Pressure = PintField("pascal")
Velocity = PintField("meter/second")
Frequency = PintField("hertz")
Power = PintField("watt")
Duration = PintField("second")


class _QuantityModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ChamberConfig(_QuantityModel):
    type: str
    diameter: Length
    height: Length
    substrate_temperature: Temperature


class FeedstockGasConfig(_QuantityModel):
    pressure: Pressure
    inlet_velocity: Velocity
    mass_fractions: dict[str, float]

    @field_validator("mass_fractions")
    @classmethod
    def _mass_fractions_sum_to_one(cls, value: dict[str, float]) -> dict[str, float]:
        total = sum(value.values())
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(f"mass_fractions must sum to 1.0, got {total}")
        return value


class MicrowaveSourceConfig(_QuantityModel):
    frequency: Frequency
    power: Power


class OpenFOAMMeshConfig(_QuantityModel):
    cell_target: Length


class OpenFOAMConfig(BaseModel):
    version: str
    solver: str
    n_procs: int = Field(ge=1)
    mesh: OpenFOAMMeshConfig


class WarpXScoringMeshConfig(BaseModel):
    n_bins_xyz: tuple[int, int, int]


class WarpXConfig(BaseModel):
    n_steps: int = Field(gt=0)
    scoring_mesh: WarpXScoringMeshConfig


class XolotlConfig(_QuantityModel):
    dimensions: int = Field(ge=1, le=3)
    runtime: Duration
    interstitial_traps: bool


class CVDParameters(BaseModel):
    """Top-level params.yaml document."""

    chamber: ChamberConfig
    feedstock_gas: FeedstockGasConfig
    microwave_source: MicrowaveSourceConfig
    openfoam: OpenFOAMConfig
    warpx: WarpXConfig
    xolotl: XolotlConfig

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CVDParameters":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
