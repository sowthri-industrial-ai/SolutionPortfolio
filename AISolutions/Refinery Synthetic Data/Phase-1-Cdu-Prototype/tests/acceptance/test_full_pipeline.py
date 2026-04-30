"""End-to-end smoke test: 1-month pipeline produces every expected artifact."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from rsd.generate import run_pipeline

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


def test_one_month_pipeline_produces_all_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "output"
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-01-01",
        end="2025-01-31",
        output_path=out,
        seed_override=42,
    )

    pi_partition = out / "pi" / "year=2025" / "month=01" / "data.parquet"
    lims_path = out / "lims" / "lab_records.parquet"
    labels_path = out / "ground_truth" / "labels.parquet"
    true_path = out / "ground_truth" / "true_values.parquet"
    meta_path = out / "metadata" / "run_info.json"

    for p in (pi_partition, lims_path, labels_path, true_path, meta_path):
        assert p.exists(), f"missing artifact: {p}"

    pi = pd.read_parquet(pi_partition)
    lims = pd.read_parquet(lims_path)
    labels = pd.read_parquet(labels_path)
    truth = pd.read_parquet(true_path)

    assert len(pi) > 0
    assert len(lims) > 0
    assert len(labels) > 0
    assert len(truth) > 0

    # 1-min cadence over Jan 1 .. Jan 31 inclusive: 31 * 24 * 60 = 44,640 rows
    # (last 5-min tick at 23:55 -> 1-min resample ends at 23:55 -> 44,636).
    assert 44_000 < len(pi) <= 44_640
    assert pi.shape[1] == 18
