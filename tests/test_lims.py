"""Tests for ``rsd.lims.LIMSWriter``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rsd.config import load_config
from rsd.lims import LIMSWriter
from rsd.physics import simulate_batch
from rsd.scenario import ScenarioGenerator
from rsd.schemas import LabTest

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


def _diesel_t95_test(freq_hours: float = 8.0, uncertainty: float = 1.5) -> LabTest:
    return LabTest(
        method="ASTM_D86",
        property="T95",
        stream="SITE01.CDU1.STREAM.diesel_product",
        physics_output="diesel_T95_c",
        units="degC",
        uncertainty_std=uncertainty,
        frequency_hours=freq_hours,
    )


def _flat_clean(n_steps: int = 30 * 288) -> pd.DataFrame:
    """30 days at 5-min cadence, constant true value of 350.0."""

    idx = pd.date_range("2025-01-01", periods=n_steps, freq="5min")
    return pd.DataFrame({"diesel_T95_c": np.full(n_steps, 350.0)}, index=idx)


def test_record_count_matches_frequency_minus_misses() -> None:
    clean = _flat_clean()
    test = _diesel_t95_test(freq_hours=8.0)
    writer = LIMSWriter(lab_tests=(test,), report_delay_hours=4.0, seed=42)
    df = writer.generate(clean)
    expected_total = (clean.index[-1] - clean.index[0]) / pd.Timedelta(hours=8) + 1
    expected_kept = expected_total * 0.98
    # Within statistical tolerance for ~90 expected records.
    assert abs(len(df) - expected_kept) < 6


def test_sample_times_aligned_to_frequency() -> None:
    clean = _flat_clean(n_steps=288)  # 1 day
    test = _diesel_t95_test(freq_hours=8.0)
    writer = LIMSWriter(lab_tests=(test,), report_delay_hours=4.0, seed=0)
    df = writer.generate(clean)
    # All sample_times are 8h-aligned offsets from start.
    deltas = (df["sample_time"] - clean.index[0]) / pd.Timedelta(hours=8)
    assert np.allclose(deltas.to_numpy(), np.round(deltas.to_numpy()))


def test_report_time_is_sample_time_plus_delay() -> None:
    clean = _flat_clean()
    test = _diesel_t95_test()
    writer = LIMSWriter(lab_tests=(test,), report_delay_hours=4.0, seed=1)
    df = writer.generate(clean)
    delta = (df["report_time"] - df["sample_time"]) / pd.Timedelta(hours=1)
    assert (delta == 4.0).all()
    assert (df["report_time"] > df["sample_time"]).all()


def test_measurement_noise_distribution_matches_uncertainty() -> None:
    clean = _flat_clean(n_steps=365 * 288)  # 1 year
    test = _diesel_t95_test(freq_hours=8.0, uncertainty=1.5)
    writer = LIMSWriter(lab_tests=(test,), report_delay_hours=4.0, seed=42)
    df = writer.generate(clean)
    errors = df["value"] - df["true_value"]
    assert abs(errors.mean()) < 0.15
    assert abs(errors.std(ddof=0) - 1.5) / 1.5 < 0.1


def test_missing_physics_output_raises() -> None:
    test = LabTest(
        method="X",
        property="Y",
        stream="S",
        physics_output="nonexistent",
        units="u",
        uncertainty_std=1.0,
        frequency_hours=8.0,
    )
    writer = LIMSWriter(lab_tests=(test,), report_delay_hours=4.0, seed=0)
    with pytest.raises(KeyError) as ei:
        writer.generate(_flat_clean(100))
    assert "nonexistent" in str(ei.value)


def test_record_schema_complete() -> None:
    clean = _flat_clean(288)
    test = _diesel_t95_test()
    writer = LIMSWriter(lab_tests=(test,), report_delay_hours=4.0, seed=2)
    df = writer.generate(clean)
    expected = {
        "sample_id",
        "functional_location",
        "stream",
        "test_method",
        "property",
        "value",
        "units",
        "sample_time",
        "report_time",
        "true_value",
    }
    assert expected == set(df.columns)
    assert df["sample_id"].is_unique


def test_determinism_same_seed() -> None:
    clean = _flat_clean()
    tests = (_diesel_t95_test(), _diesel_t95_test(freq_hours=24.0))
    a = LIMSWriter(lab_tests=tests, report_delay_hours=4.0, seed=7).generate(clean)
    b = LIMSWriter(lab_tests=tests, report_delay_hours=4.0, seed=7).generate(clean)
    pd.testing.assert_frame_equal(a, b)


def test_two_percent_miss_rate() -> None:
    clean = _flat_clean(n_steps=365 * 288)
    test = _diesel_t95_test(freq_hours=8.0)
    expected_total = (clean.index[-1] - clean.index[0]) / pd.Timedelta(hours=8) + 1
    writer = LIMSWriter(lab_tests=(test,), report_delay_hours=4.0, seed=12345)
    df = writer.generate(clean)
    miss_fraction = 1.0 - len(df) / expected_total
    assert 0.01 < miss_fraction < 0.03


def test_full_pipeline_with_real_config() -> None:
    cfg = load_config(CONFIG_PATH)
    scen = ScenarioGenerator(
        base_operation=cfg.base_operation,
        scenarios=tuple(cfg.scenarios),
        seed=cfg.seed,
    ).generate("2025-01-01", "2025-02-01", freq=cfg.simulation_freq)
    clean = simulate_batch(scen)
    writer = LIMSWriter(
        lab_tests=tuple(cfg.lab_panel),
        report_delay_hours=cfg.lims_report_delay_hours,
        seed=cfg.seed,
    )
    df = writer.generate(clean)
    assert len(df) > 0
    methods = set(df["test_method"].unique())
    assert {"ASTM_D86", "ASTM_D4294", "ASTM_D4052"} <= methods
    assert (df["report_time"] > df["sample_time"]).all()
