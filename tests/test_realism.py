"""Tests for ``rsd.realism.RealismLayer``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rsd.config import load_config
from rsd.physics import simulate_batch
from rsd.realism import RealismLayer
from rsd.scenario import ScenarioGenerator
from rsd.schemas import TagDefinition

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


def _build_layer(tags: tuple[TagDefinition, ...], seed: int = 1) -> RealismLayer:
    return RealismLayer(tags=tags, seed=seed)


def _flat_clean(value: float, n_steps: int = 5000) -> pd.DataFrame:
    """A 5-min cadence DataFrame with a single constant column."""

    idx = pd.date_range("2025-01-01", periods=n_steps, freq="5min")
    return pd.DataFrame({"feed_rate_kg_h": np.full(n_steps, value)}, index=idx)


def _ramp_clean(start_v: float, end_v: float, n_steps: int = 1000) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=n_steps, freq="5min")
    return pd.DataFrame(
        {"feed_rate_kg_h": np.linspace(start_v, end_v, n_steps)}, index=idx
    )


def _make_tag(
    *,
    noise_pct: float = 0.0,
    lag_seconds: float = 0.0,
    drift_per_day: float = 0.0,
    deadband_pct: float = 0.0,
    span: tuple[float, float] = (0.0, 600000.0),
) -> TagDefinition:
    return TagDefinition(
        name="TEST.PV",
        physics_output="feed_rate_kg_h",
        functional_location="X",
        units="kg/h",
        span=span,
        noise_pct=noise_pct,
        lag_seconds=lag_seconds,
        drift_per_day=drift_per_day,
        compression_deadband_pct=deadband_pct,
    )


def test_noise_std_matches_configured() -> None:
    tag = _make_tag(noise_pct=0.5, span=(0, 600000))
    expected_sigma = 0.005 * 600000  # 3000
    layer = _build_layer((tag,))
    out = layer.apply(_flat_clean(400000, 5000), target_freq="1min")
    samples = out["TEST.PV"].dropna().to_numpy()
    # Quantization adds a tiny rounding component; tolerance is generous.
    assert abs(samples.std(ddof=0) - expected_sigma) / expected_sigma < 0.05


def test_lag_introduces_phase_delay_for_step_input() -> None:
    """Step input plus a long lag should ramp slowly toward the new value."""

    n = 200
    idx = pd.date_range("2025-01-01", periods=n, freq="5min")
    sig = np.where(np.arange(n) < n // 2, 0.0, 100.0)
    clean = pd.DataFrame({"feed_rate_kg_h": sig}, index=idx)
    tag = _make_tag(lag_seconds=600, span=(0, 200))
    layer = _build_layer((tag,))
    out = layer.apply(clean, target_freq="1min")
    sliced = out["TEST.PV"].to_numpy()
    # Just after the step, the lagged signal should be well below the new setpoint.
    step_idx = (n // 2) * 5
    assert sliced[step_idx + 1] < 50.0
    # Far past the step, it should be close to the new setpoint.
    assert sliced[-1] == pytest.approx(100.0, abs=2.0)


def test_gap_rate_in_expected_range() -> None:
    tag = _make_tag()
    layer = _build_layer((tag,), seed=7)
    out = layer.apply(_flat_clean(400000, 20000), target_freq="1min")
    nan_fraction = out["TEST.PV"].isna().mean()
    # Expected: 1e-4 per sample x ~17.5 min mean gap ~ 0.00175 NaN fraction.
    assert 0.0005 < nan_fraction < 0.005


def test_compression_reduces_unique_values_with_low_deadband() -> None:
    """A wide deadband should collapse many quantization levels into one."""

    tag_no_compress = _make_tag(noise_pct=0.5, span=(0, 600000), deadband_pct=0.0)
    tag_compress = _make_tag(noise_pct=0.5, span=(0, 600000), deadband_pct=2.0)
    layer1 = _build_layer((tag_no_compress,), seed=11)
    layer2 = _build_layer((tag_compress,), seed=11)
    out1 = layer1.apply(_flat_clean(400000, 5000), target_freq="1min")
    out2 = layer2.apply(_flat_clean(400000, 5000), target_freq="1min")
    assert out2["TEST.PV"].nunique() < out1["TEST.PV"].nunique()


def test_quantization_resolution() -> None:
    tag = _make_tag(span=(0, 600000), noise_pct=0.0)
    layer = _build_layer((tag,))
    out = layer.apply(_flat_clean(400000, 100), target_freq="1min")
    resolution = 600000 / 4096
    diffs = out["TEST.PV"].dropna().to_numpy() / resolution
    assert np.allclose(diffs, np.round(diffs), atol=1e-9)


def test_determinism_same_seed() -> None:
    tag = _make_tag(noise_pct=0.5, drift_per_day=10.0, deadband_pct=0.5)
    l1 = _build_layer((tag,), seed=99)
    l2 = _build_layer((tag,), seed=99)
    o1 = l1.apply(_flat_clean(400000, 2000), target_freq="1min")
    o2 = l2.apply(_flat_clean(400000, 2000), target_freq="1min")
    pd.testing.assert_frame_equal(o1, o2)


def test_different_seed_changes_output() -> None:
    tag = _make_tag(noise_pct=0.5)
    o1 = _build_layer((tag,), seed=1).apply(_flat_clean(400000, 1000), "1min")
    o2 = _build_layer((tag,), seed=2).apply(_flat_clean(400000, 1000), "1min")
    assert not np.array_equal(
        o1["TEST.PV"].dropna().to_numpy(), o2["TEST.PV"].dropna().to_numpy()
    )


def test_missing_physics_output_raises() -> None:
    tag = TagDefinition(
        name="X.PV",
        physics_output="nonexistent_column",
        functional_location="X",
        units="kg/h",
        span=(0, 1),
        noise_pct=0,
        lag_seconds=0,
        drift_per_day=0,
        compression_deadband_pct=0,
    )
    layer = _build_layer((tag,))
    with pytest.raises(KeyError) as ei:
        layer.apply(_flat_clean(400000, 100))
    assert "nonexistent_column" in str(ei.value)


def test_resampling_and_full_pipeline_with_real_config() -> None:
    cfg = load_config(CONFIG_PATH)
    scen = ScenarioGenerator(
        base_operation=cfg.base_operation,
        scenarios=tuple(cfg.scenarios),
        seed=cfg.seed,
    ).generate("2025-01-01", "2025-01-02", freq=cfg.simulation_freq)
    clean = simulate_batch(scen)
    layer = RealismLayer(tags=tuple(cfg.tags), seed=cfg.seed)
    out = layer.apply(clean, target_freq=cfg.pi_output_freq)
    assert len(out.columns) == len(cfg.tags)
    # Scenario uses [start, end) at 5-min, so last clean tick is 23:55.
    # Realism resamples to 1-min from 00:00 through 23:55 inclusive: 1436 rows.
    assert len(out) == 1436
    assert {t.name for t in cfg.tags} == set(out.columns)
