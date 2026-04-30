"""Tests for ``rsd.ground_truth.GroundTruthWriter``."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from rsd.config import load_config
from rsd.ground_truth import GroundTruthWriter
from rsd.physics import simulate_batch
from rsd.realism import RealismLayer
from rsd.scenario import ScenarioGenerator

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


@pytest.fixture
def small_pipeline_state() -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = load_config(CONFIG_PATH)
    scen = ScenarioGenerator(
        base_operation=cfg.base_operation,
        scenarios=tuple(cfg.scenarios),
        seed=cfg.seed,
    ).generate("2025-04-10", "2025-04-20", freq=cfg.simulation_freq)
    clean = simulate_batch(scen)
    return scen, clean


def test_build_labels_has_expected_columns(
    small_pipeline_state: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    scen, _ = small_pipeline_state
    labels = GroundTruthWriter().build_labels(scen)
    assert set(labels.columns) == {"active_fault", "fouling_E101"}
    assert labels.index.name == "timestamp"


def test_build_true_values_includes_all_physics_columns(
    small_pipeline_state: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    _, clean = small_pipeline_state
    true_values = GroundTruthWriter().build_true_values(clean)
    assert set(true_values.columns) == set(clean.columns)
    assert true_values.index.name == "timestamp"


def test_write_produces_both_parquets(
    small_pipeline_state: tuple[pd.DataFrame, pd.DataFrame], tmp_path: Path
) -> None:
    scen, clean = small_pipeline_state
    labels_path, true_path = GroundTruthWriter().write(scen, clean, tmp_path)
    assert labels_path.exists()
    assert true_path.exists()
    assert labels_path.name == "labels.parquet"
    assert true_path.name == "true_values.parquet"


def test_round_trip_parquet_preserves_data(
    small_pipeline_state: tuple[pd.DataFrame, pd.DataFrame], tmp_path: Path
) -> None:
    scen, clean = small_pipeline_state
    writer = GroundTruthWriter()
    writer.write(scen, clean, tmp_path)
    loaded_labels = pd.read_parquet(tmp_path / "labels.parquet")
    loaded_true = pd.read_parquet(tmp_path / "true_values.parquet")
    expected_labels = writer.build_labels(scen)
    expected_true = writer.build_true_values(clean)
    # Parquet round-trip drops DatetimeIndex.freq metadata; values must match.
    pd.testing.assert_frame_equal(loaded_labels, expected_labels, check_freq=False)
    pd.testing.assert_frame_equal(loaded_true, expected_true, check_freq=False)


def test_labels_active_fault_marks_fouling_window(
    small_pipeline_state: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    scen, _ = small_pipeline_state
    labels = GroundTruthWriter().build_labels(scen)
    fault_window = (labels.index >= pd.Timestamp("2025-04-15")) & (
        labels.index < pd.Timestamp("2025-04-15") + pd.Timedelta(days=60)
    )
    assert (labels.loc[fault_window, "active_fault"] == "FOUL_001").all()
    assert (labels.loc[~fault_window, "active_fault"] == "NONE").all()


def test_joinable_to_noisy_pi_on_timestamp(
    small_pipeline_state: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """PI noisy output (1-min) should join cleanly against ground truth (5-min)."""

    scen, clean = small_pipeline_state
    cfg = load_config(CONFIG_PATH)
    layer = RealismLayer(tags=tuple(cfg.tags), seed=cfg.seed)
    pi_df = layer.apply(clean, target_freq=cfg.pi_output_freq)
    labels = GroundTruthWriter().build_labels(scen)
    # Inner-join on timestamp by reindexing labels onto pi_df at 1-min cadence.
    aligned = labels.reindex(pi_df.index, method="ffill")
    assert aligned.index.equals(pi_df.index)
    assert aligned["active_fault"].notna().all()


def test_missing_label_column_raises() -> None:
    df = pd.DataFrame({"feed_rate_kg_h": [1.0]}, index=pd.date_range("2025-01-01", periods=1))
    with pytest.raises(KeyError) as ei:
        GroundTruthWriter().build_labels(df)
    assert "fouling_E101" in str(ei.value) or "active_fault" in str(ei.value)
