"""Each output Parquet must conform to its expected schema."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from rsd.config import load_config
from rsd.generate import run_pipeline

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("schemas") / "output"
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-04-01",
        end="2025-04-30",
        output_path=out,
        seed_override=42,
    )
    return out


def test_pi_schema(output_dir: Path) -> None:
    cfg = load_config(CONFIG_PATH)
    pi = pd.read_parquet(output_dir / "pi" / "year=2025" / "month=04" / "data.parquet")
    expected_columns = {t.name for t in cfg.tags}
    assert expected_columns == set(pi.columns)
    for col in pi.columns:
        assert pd.api.types.is_float_dtype(pi[col]), f"{col} must be float dtype"
    assert isinstance(pi.index, pd.DatetimeIndex)


def test_lims_schema(output_dir: Path) -> None:
    lims = pd.read_parquet(output_dir / "lims" / "lab_records.parquet")
    expected_columns = {
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
    assert expected_columns == set(lims.columns)
    assert pd.api.types.is_datetime64_any_dtype(lims["sample_time"])
    assert pd.api.types.is_datetime64_any_dtype(lims["report_time"])
    assert pd.api.types.is_float_dtype(lims["value"])
    assert pd.api.types.is_float_dtype(lims["true_value"])
    assert lims["sample_id"].is_unique
    assert (lims["report_time"] > lims["sample_time"]).all()


def test_labels_schema(output_dir: Path) -> None:
    labels = pd.read_parquet(output_dir / "ground_truth" / "labels.parquet")
    assert set(labels.columns) == {"active_fault", "fouling_E101"}
    assert pd.api.types.is_string_dtype(labels["active_fault"])
    assert pd.api.types.is_float_dtype(labels["fouling_E101"])
    assert isinstance(labels.index, pd.DatetimeIndex)
    # Active fault values are exactly {"NONE", "FOUL_001"} for the v1 scenario.
    assert set(labels["active_fault"].unique()) <= {"NONE", "FOUL_001"}


def test_true_values_schema(output_dir: Path) -> None:
    truth = pd.read_parquet(output_dir / "ground_truth" / "true_values.parquet")
    expected = {
        "feed_rate_kg_h",
        "feed_temp_c",
        "T_cold_out_c",
        "P_E101_in_barg",
        "T_furnace_c",
        "Q_furnace_W",
        "fuel_gas_flow_kg_s",
        "T_top_c",
        "T_kero_c",
        "T_diesel_c",
        "T_AGO_c",
        "T_residue_c",
        "P_tower_top_barg",
        "y_naphtha",
        "y_kero",
        "y_diesel",
        "y_AGO",
        "y_residue",
        "F_naphtha_kg_h",
        "F_kero_kg_h",
        "F_diesel_kg_h",
        "F_AGO_kg_h",
        "F_residue_kg_h",
        "diesel_T95_c",
        "diesel_sulfur_pct",
        "kero_T95_c",
        "naphtha_density",
    }
    assert expected == set(truth.columns)
    assert isinstance(truth.index, pd.DatetimeIndex)


def test_run_info_schema(output_dir: Path) -> None:
    import json

    info = json.loads((output_dir / "metadata" / "run_info.json").read_text())
    expected = {
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
    assert expected <= set(info.keys())
    assert isinstance(info["config_snapshot"], dict)
    assert isinstance(info["effective_seed"], int)
    assert info["runtime_seconds"] >= 0
