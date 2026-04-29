"""Two runs with the same seed must produce hash-equal DataFrame contents."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from rsd.generate import run_pipeline

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


def _read_pi(out: Path) -> pd.DataFrame:
    files = sorted((out / "pi").rglob("data.parquet"))
    return pd.concat([pd.read_parquet(p) for p in files]).sort_index()


def test_two_runs_with_same_seed_are_data_equal(tmp_path: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    for out in (out_a, out_b):
        run_pipeline(
            config_path=CONFIG_PATH,
            start="2025-01-01",
            end="2025-01-31",
            output_path=out,
            seed_override=42,
        )

    pi_a = _read_pi(out_a)
    pi_b = _read_pi(out_b)
    pd.testing.assert_frame_equal(pi_a, pi_b, check_freq=False)

    lims_a = pd.read_parquet(out_a / "lims" / "lab_records.parquet")
    lims_b = pd.read_parquet(out_b / "lims" / "lab_records.parquet")
    pd.testing.assert_frame_equal(lims_a, lims_b)

    labels_a = pd.read_parquet(out_a / "ground_truth" / "labels.parquet")
    labels_b = pd.read_parquet(out_b / "ground_truth" / "labels.parquet")
    pd.testing.assert_frame_equal(labels_a, labels_b, check_freq=False)

    truth_a = pd.read_parquet(out_a / "ground_truth" / "true_values.parquet")
    truth_b = pd.read_parquet(out_b / "ground_truth" / "true_values.parquet")
    pd.testing.assert_frame_equal(truth_a, truth_b, check_freq=False)
