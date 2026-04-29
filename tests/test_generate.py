"""Module-level tests for the orchestrator. End-to-end acceptance is in
``tests/acceptance/`` (Module 9)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from rsd.generate import main, run_pipeline

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


def test_cli_runs_short_range(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "output"
    result = runner.invoke(
        main,
        [
            "--config",
            str(CONFIG_PATH),
            "--start",
            "2025-01-01",
            "--end",
            "2025-01-02",
            "--output",
            str(out),
            "--seed",
            "42",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "pi" / "year=2025" / "month=01" / "data.parquet").exists()
    assert (out / "lims" / "lab_records.parquet").exists()
    assert (out / "ground_truth" / "labels.parquet").exists()
    assert (out / "ground_truth" / "true_values.parquet").exists()
    assert (out / "metadata" / "run_info.json").exists()


def test_run_info_json_has_expected_fields(tmp_path: Path) -> None:
    out = tmp_path / "output"
    info = run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-01-01",
        end="2025-01-02",
        output_path=out,
        seed_override=42,
    )
    expected_fields = {
        "rsd_version",
        "config_path",
        "start",
        "end",
        "effective_seed",
        "config_seed",
        "runtime_seconds",
        "generated_at",
        "git_sha",
        "config_snapshot",
    }
    assert expected_fields <= set(info.keys())
    on_disk = json.loads((out / "metadata" / "run_info.json").read_text())
    assert on_disk["effective_seed"] == 42


def test_seed_override_takes_effect(tmp_path: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-01-01",
        end="2025-01-02",
        output_path=out_a,
        seed_override=1,
    )
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-01-01",
        end="2025-01-02",
        output_path=out_b,
        seed_override=2,
    )
    pi_a = pd.read_parquet(out_a / "pi" / "year=2025" / "month=01" / "data.parquet")
    pi_b = pd.read_parquet(out_b / "pi" / "year=2025" / "month=01" / "data.parquet")
    # Different seeds → different noise realizations.
    assert not pi_a.equals(pi_b)


def test_partitioning_splits_across_months(tmp_path: Path) -> None:
    out = tmp_path / "output"
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-01-30",
        end="2025-02-02",
        output_path=out,
        seed_override=42,
    )
    jan = out / "pi" / "year=2025" / "month=01" / "data.parquet"
    feb = out / "pi" / "year=2025" / "month=02" / "data.parquet"
    assert jan.exists()
    assert feb.exists()


def test_idempotent_overwrite_clears_stale_partitions(tmp_path: Path) -> None:
    out = tmp_path / "output"
    # First run covers Jan-Feb.
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-01-30",
        end="2025-02-02",
        output_path=out,
        seed_override=42,
    )
    assert (out / "pi" / "year=2025" / "month=02" / "data.parquet").exists()
    # Second run covers Jan only — Feb partition must be removed.
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-01-15",
        end="2025-01-20",
        output_path=out,
        seed_override=42,
    )
    assert not (out / "pi" / "year=2025" / "month=02").exists()
