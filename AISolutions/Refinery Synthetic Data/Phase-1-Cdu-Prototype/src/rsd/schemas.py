"""Pydantic schemas for the RSD pipeline.

Every config file, the physics seam, and the orchestrator's data contracts are
defined here. All models are frozen and forbid extra keys: typos in YAML files
fail fast with a useful error.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Frozen(BaseModel):
    """Base for all schema models: immutable, strict about unknown keys."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------- asset hierarchy ----------


class Equipment(_Frozen):
    """One piece of equipment (exchanger, furnace, column, pump)."""

    tag: str
    type: str
    service: str
    criticality: str
    functional_location: str


class Stream(_Frozen):
    """A named process stream and its functional location."""

    id: str
    functional_location: str


class Unit(_Frozen):
    """A process unit containing equipment and streams."""

    name: str
    equipment: list[Equipment]
    streams: list[Stream]


class Site(_Frozen):
    """A refinery site containing one or more units."""

    name: str
    timezone: str
    units: dict[str, Unit]


class AssetHierarchy(_Frozen):
    """The top-level asset hierarchy parsed from ``asset_hierarchy.yaml``."""

    sites: dict[str, Site]


# ---------- tags ----------


class TagDefinition(_Frozen):
    """One PI tag definition.

    The ``physics_output`` field names the column produced by ``rsd.physics``
    that this tag observes. It is the seam between the physics layer and the
    realism layer.
    """

    name: str
    description: str = ""
    physics_output: str
    functional_location: str
    units: str
    span: tuple[float, float]
    noise_pct: float = Field(ge=0)
    lag_seconds: float = Field(ge=0)
    drift_per_day: float = Field(ge=0)
    compression_deadband_pct: float = Field(ge=0)

    @field_validator("span")
    @classmethod
    def _span_ordered(cls, v: tuple[float, float]) -> tuple[float, float]:
        if v[1] <= v[0]:
            raise ValueError(f"span must be (min, max) with max > min, got {v}")
        return v


# ---------- lab tests ----------


class LabTest(_Frozen):
    """One LIMS test definition."""

    method: str
    property: str
    stream: str
    physics_output: str
    units: str
    uncertainty_std: float = Field(ge=0)
    frequency_hours: float = Field(gt=0)


# ---------- fault scenarios ----------


class FaultScenario(_Frozen):
    """A single fault scenario. v1 supports ``exchanger_fouling`` only."""

    id: str
    type: Literal["exchanger_fouling"]
    target: str
    start: datetime
    duration_days: float = Field(gt=0)
    profile: Literal["linear"]
    severity_final: float = Field(ge=0, le=1)
    description: str = ""


# ---------- base operation ----------


class NormalParams(_Frozen):
    """Mean/std parameters for a normal distribution."""

    distribution: Literal["normal"]
    mean: float
    std: float = Field(ge=0)


class FeedTempParams(NormalParams):
    """Normal distribution plus a diurnal sinusoid for ambient temperature."""

    diurnal_amplitude_c: float = Field(ge=0)
    diurnal_peak_hour: float = Field(ge=0, lt=24)


class BaseOperation(_Frozen):
    """Steady-state operating envelope from which the scenario draws inputs."""

    feed_rate_kg_h: NormalParams
    feed_temp_c: FeedTempParams
    furnace_target_c: float


# ---------- pipeline config ----------


class PipelineConfig(_Frozen):
    """Fully-loaded pipeline configuration with all sub-files materialized."""

    seed: int
    simulation_freq: str
    pi_output_freq: str
    lims_report_delay_hours: float = Field(ge=0)
    base_operation: BaseOperation
    asset_hierarchy: AssetHierarchy
    tags: list[TagDefinition]
    lab_panel: list[LabTest]
    scenarios: list[FaultScenario]


class RawPipelineConfig(_Frozen):
    """The on-disk shape of ``default.yaml`` before sibling files are loaded."""

    asset_hierarchy_path: str
    tags_path: str
    lab_panel_path: str
    scenarios_path: str
    seed: int
    simulation_freq: str
    pi_output_freq: str
    lims_report_delay_hours: float = Field(ge=0)
    base_operation: BaseOperation


# ---------- physics seam ----------


class PhysicsInputs(_Frozen):
    """Per-timestep inputs to the mock physics layer.

    This is the stable interface where DWSIM/IDAES will later be plugged in.
    """

    feed_rate_kg_h: float = Field(gt=0)
    feed_temp_c: float
    furnace_target_c: float
    fouling_E101: float = Field(ge=0, le=1)
    api_delta: float = 0.0
    api_delta_sulfur: float = 0.0


class PhysicsOutputs(_Frozen):
    """Per-timestep outputs of the mock physics layer.

    Field names match the ``physics_output`` strings declared in
    ``tags.yaml`` and ``lab_panel.yaml``.
    """

    feed_rate_kg_h: float
    feed_temp_c: float

    T_cold_out_c: float
    P_E101_in_barg: float

    T_furnace_c: float
    Q_furnace_W: float
    fuel_gas_flow_kg_s: float

    T_top_c: float
    T_kero_c: float
    T_diesel_c: float
    T_AGO_c: float
    T_residue_c: float
    P_tower_top_barg: float

    y_naphtha: float
    y_kero: float
    y_diesel: float
    y_AGO: float
    y_residue: float

    F_naphtha_kg_h: float
    F_kero_kg_h: float
    F_diesel_kg_h: float
    F_AGO_kg_h: float
    F_residue_kg_h: float

    diesel_T95_c: float
    diesel_sulfur_pct: float
    kero_T95_c: float
    naphtha_density: float
