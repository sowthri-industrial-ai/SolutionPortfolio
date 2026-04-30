"""Tests for ``rsd.scenario.ScenarioGenerator``."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rsd.config import load_config
from rsd.scenario import ScenarioGenerator
from rsd.schemas import (
    BaseOperation,
    FaultScenario,
    FeedTempParams,
    NormalParams,
)

CONFIG_PATH = (
    __import__("pathlib").Path(__file__).resolve().parent.parent / "config" / "default.yaml"
)


@pytest.fixture
def base_operation() -> BaseOperation:
    return BaseOperation(
        feed_rate_kg_h=NormalParams(distribution="normal", mean=400000.0, std=8000.0),
        feed_temp_c=FeedTempParams(
            distribution="normal",
            mean=25.0,
            std=5.0,
            diurnal_amplitude_c=3.0,
            diurnal_peak_hour=14.0,
        ),
        furnace_target_c=360.0,
    )


@pytest.fixture
def fouling_scenario() -> FaultScenario:
    return FaultScenario(
        id="FOUL_001",
        type="exchanger_fouling",
        target="SITE01.CDU1.E-101",
        start=datetime(2025, 4, 15),
        duration_days=60,
        profile="linear",
        severity_final=0.4,
    )


def test_row_count_matches_freq(base_operation: BaseOperation) -> None:
    gen = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=42)
    df = gen.generate("2025-01-01", "2025-01-02", freq="5min")
    # 24h * 60min / 5min = 288 rows, end-exclusive
    assert len(df) == 288


def test_columns_present_even_without_faults(base_operation: BaseOperation) -> None:
    gen = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=42)
    df = gen.generate("2025-01-01", "2025-01-02")
    expected = {
        "feed_rate_kg_h",
        "feed_temp_c",
        "furnace_target_c",
        "fouling_E101",
        "api_delta",
        "active_fault",
    }
    assert expected <= set(df.columns)
    assert (df["fouling_E101"] == 0).all()
    assert (df["active_fault"] == "NONE").all()


def test_feed_rate_distribution_matches_config(base_operation: BaseOperation) -> None:
    gen = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=42)
    df = gen.generate("2025-01-01", "2025-02-01")
    assert abs(df["feed_rate_kg_h"].mean() - 400000) < 200
    assert abs(df["feed_rate_kg_h"].std() - 8000) < 200


def test_feed_temp_diurnal_peaks_at_14(base_operation: BaseOperation) -> None:
    gen = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=42)
    df = gen.generate("2025-01-01", "2025-02-01")
    by_hour = df.groupby(df.index.hour)["feed_temp_c"].mean()
    assert by_hour.idxmax() == 14


def test_furnace_target_constant(base_operation: BaseOperation) -> None:
    gen = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=42)
    df = gen.generate("2025-01-01", "2025-01-02")
    assert (df["furnace_target_c"] == 360.0).all()


def test_fault_window_marks_active_fault(
    base_operation: BaseOperation, fouling_scenario: FaultScenario
) -> None:
    gen = ScenarioGenerator(
        base_operation=base_operation, scenarios=(fouling_scenario,), seed=42
    )
    df = gen.generate("2025-04-01", "2025-07-01")
    in_window = (df.index >= pd.Timestamp("2025-04-15")) & (
        df.index < pd.Timestamp("2025-04-15") + pd.Timedelta(days=60)
    )
    assert (df.loc[in_window, "active_fault"] == "FOUL_001").all()
    assert (df.loc[~in_window, "active_fault"] == "NONE").all()


def test_fault_ramps_linearly(
    base_operation: BaseOperation, fouling_scenario: FaultScenario
) -> None:
    gen = ScenarioGenerator(
        base_operation=base_operation, scenarios=(fouling_scenario,), seed=42
    )
    df = gen.generate("2025-04-01", "2025-07-01")
    start = pd.Timestamp("2025-04-15")
    in_window = (df.index >= start) & (df.index < start + pd.Timedelta(days=60))
    fouling = df.loc[in_window, "fouling_E101"]
    assert fouling.iloc[0] == pytest.approx(0.0, abs=1e-6)
    # Last 5-min tick is one step short of severity_final (window is half-open).
    assert fouling.iloc[-1] < 0.4
    assert fouling.iloc[-1] == pytest.approx(0.4 * (1 - 5 / (60 * 24 * 60)), rel=1e-9)
    diffs = np.diff(fouling.to_numpy())
    assert np.allclose(diffs, diffs[0], rtol=1e-9)


def test_determinism_with_same_seed(base_operation: BaseOperation) -> None:
    g1 = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=7)
    g2 = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=7)
    df1 = g1.generate("2025-01-01", "2025-01-05")
    df2 = g2.generate("2025-01-01", "2025-01-05")
    pd.testing.assert_frame_equal(df1, df2)


def test_different_seed_changes_output(base_operation: BaseOperation) -> None:
    g1 = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=1)
    g2 = ScenarioGenerator(base_operation=base_operation, scenarios=(), seed=2)
    df1 = g1.generate("2025-01-01", "2025-01-02")
    df2 = g2.generate("2025-01-01", "2025-01-02")
    assert not (df1["feed_rate_kg_h"].to_numpy() == df2["feed_rate_kg_h"].to_numpy()).all()


def test_loads_with_real_config() -> None:
    cfg = load_config(CONFIG_PATH)
    gen = ScenarioGenerator(
        base_operation=cfg.base_operation,
        scenarios=tuple(cfg.scenarios),
        seed=cfg.seed,
    )
    df = gen.generate("2025-01-01", "2025-02-01", freq=cfg.simulation_freq)
    assert len(df) > 0
    assert "active_fault" in df.columns


@given(
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    days=st.integers(min_value=1, max_value=10),
)
@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_no_nan_and_monotonic(seed: int, days: int) -> None:
    base = BaseOperation(
        feed_rate_kg_h=NormalParams(distribution="normal", mean=400000.0, std=8000.0),
        feed_temp_c=FeedTempParams(
            distribution="normal",
            mean=25.0,
            std=5.0,
            diurnal_amplitude_c=3.0,
            diurnal_peak_hour=14.0,
        ),
        furnace_target_c=360.0,
    )
    gen = ScenarioGenerator(base_operation=base, scenarios=(), seed=seed)
    start = datetime(2025, 6, 1)
    df = gen.generate(start, start + timedelta(days=days))
    numeric = df.select_dtypes(include=[np.number])
    assert not numeric.isna().any().any()
    assert df.index.is_monotonic_increasing
    assert df.index.is_unique
