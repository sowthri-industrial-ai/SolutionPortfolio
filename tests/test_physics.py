"""Tests for ``rsd.physics``."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from rsd.physics import simulate, simulate_batch
from rsd.schemas import PhysicsInputs


def _hand_cold_out(t_in: float, f_in: float, f_foul: float) -> float:
    ua_clean = 8e5
    cp = 2100.0
    ua = ua_clean * (1.0 - f_foul)
    mass_kg_s = f_in / 3600.0
    eff = 1.0 - math.exp(-ua / (mass_kg_s * cp))
    return t_in + eff * (320.0 - t_in)


def test_normal_operation_matches_hand_calc() -> None:
    inp = PhysicsInputs(
        feed_rate_kg_h=400000,
        feed_temp_c=25.0,
        furnace_target_c=360.0,
        fouling_E101=0.0,
        api_delta=0.0,
        api_delta_sulfur=0.0,
    )
    out = simulate(inp)
    expected_cold_out = _hand_cold_out(25.0, 400000, 0.0)
    assert out.T_cold_out_c == pytest.approx(expected_cold_out, rel=1e-9)
    expected_q = (400000 / 3600) * 2300 * (360.0 - expected_cold_out)
    assert out.Q_furnace_W == pytest.approx(expected_q, rel=1e-9)
    assert out.fuel_gas_flow_kg_s == pytest.approx(expected_q / (50e6 * 0.85), rel=1e-9)


def test_yields_sum_to_one() -> None:
    inp = PhysicsInputs(
        feed_rate_kg_h=400000,
        feed_temp_c=25.0,
        furnace_target_c=360.0,
        fouling_E101=0.0,
        api_delta=0.0,
    )
    out = simulate(inp)
    assert out.y_naphtha + out.y_kero + out.y_diesel + out.y_AGO + out.y_residue == pytest.approx(
        1.0, abs=1e-9
    )


def test_fouled_operation_drops_cold_out_and_raises_q() -> None:
    clean = simulate(
        PhysicsInputs(
            feed_rate_kg_h=400000,
            feed_temp_c=25.0,
            furnace_target_c=360.0,
            fouling_E101=0.0,
        )
    )
    fouled = simulate(
        PhysicsInputs(
            feed_rate_kg_h=400000,
            feed_temp_c=25.0,
            furnace_target_c=360.0,
            fouling_E101=0.4,
        )
    )
    assert fouled.T_cold_out_c < clean.T_cold_out_c
    assert fouled.Q_furnace_W > clean.Q_furnace_W
    assert fouled.fuel_gas_flow_kg_s > clean.fuel_gas_flow_kg_s


def test_off_spec_feed_shifts_yields_and_t95() -> None:
    base = simulate(
        PhysicsInputs(
            feed_rate_kg_h=400000,
            feed_temp_c=25.0,
            furnace_target_c=360.0,
            fouling_E101=0.0,
            api_delta=0.0,
        )
    )
    heavy = simulate(
        PhysicsInputs(
            feed_rate_kg_h=400000,
            feed_temp_c=25.0,
            furnace_target_c=360.0,
            fouling_E101=0.0,
            api_delta=-3.0,
        )
    )
    # Heavier crude (negative ΔAPI) -> less light product, more residue.
    assert heavy.y_naphtha < base.y_naphtha
    assert heavy.y_kero < base.y_kero
    assert heavy.y_residue > base.y_residue
    # diesel_T95 should be HIGHER with negative ΔAPI (per spec: -5 * ΔAPI).
    assert heavy.diesel_T95_c > base.diesel_T95_c


def test_t_furnace_passthrough() -> None:
    inp = PhysicsInputs(
        feed_rate_kg_h=400000,
        feed_temp_c=25.0,
        furnace_target_c=362.5,
        fouling_E101=0.0,
    )
    out = simulate(inp)
    assert out.T_furnace_c == 362.5


def test_simulate_batch_matches_simulate_one_by_one() -> None:
    n = 50
    df = pd.DataFrame(
        {
            "feed_rate_kg_h": np.linspace(380000, 420000, n),
            "feed_temp_c": np.linspace(20, 30, n),
            "furnace_target_c": np.full(n, 360.0),
            "fouling_E101": np.linspace(0.0, 0.4, n),
            "api_delta": np.linspace(-2, 2, n),
        },
        index=pd.date_range("2025-01-01", periods=n, freq="5min"),
    )
    batch = simulate_batch(df)
    rows = []
    for _, row in df.iterrows():
        out = simulate(
            PhysicsInputs(
                feed_rate_kg_h=row["feed_rate_kg_h"],
                feed_temp_c=row["feed_temp_c"],
                furnace_target_c=row["furnace_target_c"],
                fouling_E101=row["fouling_E101"],
                api_delta=row["api_delta"],
            )
        )
        rows.append(out.model_dump())
    expected = pd.DataFrame(rows, index=df.index)
    pd.testing.assert_frame_equal(
        batch[expected.columns], expected, check_dtype=False, atol=1e-12, rtol=1e-12
    )


def test_fouling_monotonically_raises_fuel_gas_flow() -> None:
    df = pd.DataFrame(
        {
            "feed_rate_kg_h": np.full(20, 400000.0),
            "feed_temp_c": np.full(20, 25.0),
            "furnace_target_c": np.full(20, 360.0),
            "fouling_E101": np.linspace(0.0, 0.4, 20),
            "api_delta": np.zeros(20),
        }
    )
    out = simulate_batch(df)
    fuel = out["fuel_gas_flow_kg_s"].to_numpy()
    assert np.all(np.diff(fuel) > 0)


def test_simulate_batch_rejects_missing_columns() -> None:
    df = pd.DataFrame({"feed_rate_kg_h": [400000.0]})
    with pytest.raises(KeyError) as excinfo:
        simulate_batch(df)
    assert "feed_temp_c" in str(excinfo.value)


def test_diesel_sulfur_floor_at_zero_api_sulfur() -> None:
    out = simulate(
        PhysicsInputs(
            feed_rate_kg_h=400000,
            feed_temp_c=25.0,
            furnace_target_c=360.0,
            fouling_E101=0.0,
            api_delta_sulfur=-1.0,
        )
    )
    assert out.diesel_sulfur_pct == pytest.approx(0.04, abs=1e-12)


def test_simulate_batch_performance_under_a_second() -> None:
    """Vectorized batch of ~100k rows should run in well under a second."""

    import time

    n = 100_000
    df = pd.DataFrame(
        {
            "feed_rate_kg_h": np.full(n, 400000.0),
            "feed_temp_c": np.full(n, 25.0),
            "furnace_target_c": np.full(n, 360.0),
            "fouling_E101": np.zeros(n),
            "api_delta": np.zeros(n),
        }
    )
    t0 = time.perf_counter()
    simulate_batch(df)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"simulate_batch took {elapsed:.3f}s for {n} rows"
