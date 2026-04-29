"""Tests for ``rsd.config.load_config`` and the schema models."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from rsd.config import load_config
from rsd.schemas import (
    AssetHierarchy,
    FaultScenario,
    LabTest,
    PipelineConfig,
    TagDefinition,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "default.yaml"


def test_load_default_config_returns_pipeline_config() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    assert isinstance(cfg, PipelineConfig)


def test_pipeline_settings_have_expected_values() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    assert cfg.seed == 42
    assert cfg.simulation_freq == "5min"
    assert cfg.pi_output_freq == "1min"
    assert cfg.lims_report_delay_hours == 4


def test_base_operation_is_populated() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    assert cfg.base_operation.feed_rate_kg_h.mean == 400000
    assert cfg.base_operation.feed_rate_kg_h.std == 8000
    assert cfg.base_operation.feed_temp_c.diurnal_amplitude_c == 3
    assert cfg.base_operation.feed_temp_c.diurnal_peak_hour == 14
    assert cfg.base_operation.furnace_target_c == 360


def test_asset_hierarchy_loaded() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    assert isinstance(cfg.asset_hierarchy, AssetHierarchy)
    assert "SITE01" in cfg.asset_hierarchy.sites
    cdu1 = cfg.asset_hierarchy.sites["SITE01"].units["CDU1"]
    e101 = next(e for e in cdu1.equipment if e.tag == "E-101")
    assert e101.functional_location == "SITE01.CDU1.E-101"


def test_tags_loaded_with_expected_count_and_types() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    assert len(cfg.tags) == 18
    assert all(isinstance(t, TagDefinition) for t in cfg.tags)
    fi_101 = next(t for t in cfg.tags if t.name == "FI_101.PV")
    assert fi_101.physics_output == "feed_rate_kg_h"
    assert fi_101.span == (0.0, 600000.0)


def test_lab_panel_loaded() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    assert len(cfg.lab_panel) == 4
    assert all(isinstance(t, LabTest) for t in cfg.lab_panel)
    methods = {t.method for t in cfg.lab_panel}
    assert {"ASTM_D86", "ASTM_D4294", "ASTM_D4052"} <= methods


def test_scenarios_loaded() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    assert len(cfg.scenarios) == 1
    s = cfg.scenarios[0]
    assert isinstance(s, FaultScenario)
    assert s.id == "FOUL_001"
    assert s.type == "exchanger_fouling"
    assert s.profile == "linear"
    assert s.severity_final == 0.4


def test_negative_noise_pct_rejected(tmp_path: Path) -> None:
    bad = {
        "name": "BAD.PV",
        "physics_output": "feed_rate_kg_h",
        "functional_location": "X",
        "units": "kg/h",
        "span": [0, 100],
        "noise_pct": -1.0,
        "lag_seconds": 30,
        "drift_per_day": 0,
        "compression_deadband_pct": 0.1,
    }
    with pytest.raises(ValidationError) as excinfo:
        TagDefinition.model_validate(bad)
    assert "noise_pct" in str(excinfo.value)


def test_invalid_span_rejected() -> None:
    bad = {
        "name": "BAD.PV",
        "physics_output": "feed_rate_kg_h",
        "functional_location": "X",
        "units": "kg/h",
        "span": [100, 100],
        "noise_pct": 0.5,
        "lag_seconds": 30,
        "drift_per_day": 0,
        "compression_deadband_pct": 0.1,
    }
    with pytest.raises(ValidationError) as excinfo:
        TagDefinition.model_validate(bad)
    assert "span" in str(excinfo.value)


def test_unknown_field_rejected(tmp_path: Path) -> None:
    """``extra='forbid'`` catches typos in YAML."""

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # copy defaults but inject an unknown key
    src_dir = REPO_ROOT / "config"
    for sibling in ("asset_hierarchy.yaml", "tags.yaml", "lab_panel.yaml", "scenarios.yaml"):
        (config_dir / sibling).write_text((src_dir / sibling).read_text())
    raw = yaml.safe_load((src_dir / "default.yaml").read_text())
    raw["bogus_field"] = "oops"
    (config_dir / "default.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(ValidationError) as excinfo:
        load_config(config_dir / "default.yaml")
    assert "bogus_field" in str(excinfo.value)


def test_unknown_fault_type_rejected() -> None:
    bad = {
        "id": "X",
        "type": "novel_fault",
        "target": "SITE01.CDU1.E-101",
        "start": "2025-04-15T00:00:00",
        "duration_days": 60,
        "profile": "linear",
        "severity_final": 0.4,
    }
    with pytest.raises(ValidationError):
        FaultScenario.model_validate(bad)
