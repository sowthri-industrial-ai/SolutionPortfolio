"""Mock physics layer for the CDU.

A small set of analytical equations capture the qualitative behavior of a
crude distillation unit well enough to make downstream realism and ML use
cases meaningful. This module is a pure function — no I/O, no global state.
:func:`simulate` is the seam where DWSIM/IDAES will later be plugged in;
:func:`simulate_batch` is a vectorized convenience for whole-DataFrame runs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from rsd.schemas import PhysicsInputs, PhysicsOutputs

# E-101 constants
_UA_CLEAN: float = 8e5  # W/K, clean overall heat-transfer coefficient
_T_HOT_IN: float = 320.0  # °C, fixed residue-side inlet
_CP_CRUDE: float = 2100.0  # J/(kg·K), liquid-side heat capacity

# Furnace constants
_CP_FURNACE: float = 2300.0  # J/(kg·K), liquid+vapor mean
_LHV: float = 50e6  # J/kg, lower heating value of fuel gas
_FURNACE_EFFICIENCY: float = 0.85

# Base yields (mass fractions of feed)
_Y_NAPHTHA_BASE: float = 0.18
_Y_KERO_BASE: float = 0.13
_Y_DIESEL_BASE: float = 0.22
_Y_AGO_BASE: float = 0.12

# Yield sensitivities to API delta
_K_NAPHTHA_API: float = 0.005
_K_KERO_API: float = 0.003

# Tower temperature correlations (deg C) referenced to T_furnace = 360 °C
_T_TOP_BASE: float = 130.0
_K_T_TOP: float = 0.05
_T_KERO_BASE: float = 200.0
_K_T_KERO: float = 0.04
_T_DIESEL_BASE: float = 280.0
_K_T_DIESEL: float = 0.04
_T_AGO_BASE: float = 320.0
_K_T_AGO: float = 0.03

_T_FURNACE_REF: float = 360.0
_F_IN_REF: float = 400000.0  # kg/h

# Pressure correlations (barg)
_P_TOWER_BASE: float = 1.5
_P_TOWER_K: float = 0.001
_P_E101_BASE: float = 8.0
_P_E101_K: float = 0.002

# Product properties
_DIESEL_T95_BASE: float = 355.0
_DIESEL_T95_K_T: float = 0.15
_DIESEL_T95_K_API: float = 5.0

_DIESEL_SULFUR_BASE: float = 0.04
_DIESEL_SULFUR_K: float = 0.02

_KERO_T95_BASE: float = 245.0
_KERO_T95_K_T: float = 0.15
_KERO_T95_K_API: float = 4.0

_NAPHTHA_DENSITY_BASE: float = 720.0
_NAPHTHA_DENSITY_K_T: float = 0.5
_NAPHTHA_DENSITY_K_API: float = 8.0


def _compute(
    feed_rate_kg_h: NDArray[np.float64] | float,
    feed_temp_c: NDArray[np.float64] | float,
    furnace_target_c: NDArray[np.float64] | float,
    fouling_E101: NDArray[np.float64] | float,
    api_delta: NDArray[np.float64] | float,
    api_delta_sulfur: NDArray[np.float64] | float,
) -> dict[str, NDArray[np.float64] | float]:
    """Vectorized core of the physics. Operates on scalars or arrays uniformly."""

    f_in = np.asarray(feed_rate_kg_h, dtype=float)
    t_cold_in = np.asarray(feed_temp_c, dtype=float)
    t_furnace = np.asarray(furnace_target_c, dtype=float)
    f_foul = np.asarray(fouling_E101, dtype=float)
    d_api = np.asarray(api_delta, dtype=float)
    d_api_s = np.asarray(api_delta_sulfur, dtype=float)

    # E-101 NTU effectiveness method
    ua = _UA_CLEAN * (1.0 - f_foul)
    mass_flow_kg_s = f_in / 3600.0
    effectiveness = 1.0 - np.exp(-ua / (mass_flow_kg_s * _CP_CRUDE))
    t_cold_out = t_cold_in + effectiveness * (_T_HOT_IN - t_cold_in)

    # Furnace
    q_furnace = mass_flow_kg_s * _CP_FURNACE * (t_furnace - t_cold_out)
    fuel_gas_flow = q_furnace / (_LHV * _FURNACE_EFFICIENCY)

    # Yields
    y_naphtha = _Y_NAPHTHA_BASE + _K_NAPHTHA_API * d_api
    y_kero = _Y_KERO_BASE + _K_KERO_API * d_api
    y_diesel = np.broadcast_to(np.asarray(_Y_DIESEL_BASE), y_naphtha.shape).astype(float)
    y_ago = np.broadcast_to(np.asarray(_Y_AGO_BASE), y_naphtha.shape).astype(float)
    y_residue = 1.0 - (y_naphtha + y_kero + y_diesel + y_ago)

    # Product flows (kg/h)
    f_naphtha = y_naphtha * f_in
    f_kero = y_kero * f_in
    f_diesel = y_diesel * f_in
    f_ago = y_ago * f_in
    f_residue = y_residue * f_in

    # Tower temperatures
    dt_furnace = t_furnace - _T_FURNACE_REF
    t_top = _T_TOP_BASE + _K_T_TOP * dt_furnace
    t_kero = _T_KERO_BASE + _K_T_KERO * dt_furnace
    t_diesel = _T_DIESEL_BASE + _K_T_DIESEL * dt_furnace
    t_ago = _T_AGO_BASE + _K_T_AGO * dt_furnace
    t_residue = t_furnace - 5.0

    # Pressures
    df_in = (f_in - _F_IN_REF) / 1000.0
    p_tower = _P_TOWER_BASE + _P_TOWER_K * df_in
    p_e101 = _P_E101_BASE + _P_E101_K * df_in

    # Product properties
    diesel_t95 = (
        _DIESEL_T95_BASE + _DIESEL_T95_K_T * (t_diesel - _T_DIESEL_BASE) - _DIESEL_T95_K_API * d_api
    )
    diesel_sulfur = _DIESEL_SULFUR_BASE + _DIESEL_SULFUR_K * np.maximum(0.0, d_api_s)
    kero_t95 = _KERO_T95_BASE + _KERO_T95_K_T * (t_kero - _T_KERO_BASE) - _KERO_T95_K_API * d_api
    naphtha_density = (
        _NAPHTHA_DENSITY_BASE
        + _NAPHTHA_DENSITY_K_T * (t_top - _T_TOP_BASE)
        - _NAPHTHA_DENSITY_K_API * d_api
    )

    return {
        "feed_rate_kg_h": f_in,
        "feed_temp_c": t_cold_in,
        "T_cold_out_c": t_cold_out,
        "P_E101_in_barg": p_e101,
        "T_furnace_c": t_furnace,
        "Q_furnace_W": q_furnace,
        "fuel_gas_flow_kg_s": fuel_gas_flow,
        "T_top_c": t_top,
        "T_kero_c": t_kero,
        "T_diesel_c": t_diesel,
        "T_AGO_c": t_ago,
        "T_residue_c": t_residue,
        "P_tower_top_barg": p_tower,
        "y_naphtha": y_naphtha,
        "y_kero": y_kero,
        "y_diesel": y_diesel,
        "y_AGO": y_ago,
        "y_residue": y_residue,
        "F_naphtha_kg_h": f_naphtha,
        "F_kero_kg_h": f_kero,
        "F_diesel_kg_h": f_diesel,
        "F_AGO_kg_h": f_ago,
        "F_residue_kg_h": f_residue,
        "diesel_T95_c": diesel_t95,
        "diesel_sulfur_pct": diesel_sulfur,
        "kero_T95_c": kero_t95,
        "naphtha_density": naphtha_density,
    }


def simulate(inputs: PhysicsInputs) -> PhysicsOutputs:
    """Run the mock CDU physics for a single timestep.

    Parameters
    ----------
    inputs
        Validated :class:`PhysicsInputs` for one moment in time.

    Returns
    -------
    PhysicsOutputs
        All physics outputs at the same timestep.
    """

    out = _compute(
        inputs.feed_rate_kg_h,
        inputs.feed_temp_c,
        inputs.furnace_target_c,
        inputs.fouling_E101,
        inputs.api_delta,
        inputs.api_delta_sulfur,
    )
    scalar = {k: float(np.asarray(v).item()) for k, v in out.items()}
    return PhysicsOutputs(**scalar)


_SCENARIO_REQUIRED_COLS: tuple[str, ...] = (
    "feed_rate_kg_h",
    "feed_temp_c",
    "furnace_target_c",
    "fouling_E101",
    "api_delta",
)


def simulate_batch(scenario_df: pd.DataFrame) -> pd.DataFrame:
    """Run the mock CDU physics over an entire scenario DataFrame.

    Parameters
    ----------
    scenario_df
        DataFrame produced by :class:`rsd.scenario.ScenarioGenerator`. Must
        contain the columns named in :data:`_SCENARIO_REQUIRED_COLS`. An
        optional ``api_delta_sulfur`` column is honored when present.

    Returns
    -------
    pandas.DataFrame
        Indexed identically to ``scenario_df``; columns are every field of
        :class:`PhysicsOutputs`.
    """

    missing = [c for c in _SCENARIO_REQUIRED_COLS if c not in scenario_df.columns]
    if missing:
        raise KeyError(f"scenario_df missing required columns: {missing}")

    api_sulfur = (
        scenario_df["api_delta_sulfur"].to_numpy(dtype=float)
        if "api_delta_sulfur" in scenario_df.columns
        else np.zeros(len(scenario_df), dtype=float)
    )

    out = _compute(
        scenario_df["feed_rate_kg_h"].to_numpy(dtype=float),
        scenario_df["feed_temp_c"].to_numpy(dtype=float),
        scenario_df["furnace_target_c"].to_numpy(dtype=float),
        scenario_df["fouling_E101"].to_numpy(dtype=float),
        scenario_df["api_delta"].to_numpy(dtype=float),
        api_sulfur,
    )
    return pd.DataFrame(out, index=scenario_df.index)
