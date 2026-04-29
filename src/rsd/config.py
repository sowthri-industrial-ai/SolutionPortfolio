"""Configuration loader.

``load_config`` reads the top-level pipeline YAML, follows the sibling
references to load asset hierarchy, tags, lab panel, and scenarios, and
returns a fully-validated :class:`PipelineConfig`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from rsd.schemas import (
    AssetHierarchy,
    FaultScenario,
    LabTest,
    PipelineConfig,
    RawPipelineConfig,
    TagDefinition,
)


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _resolve(base: Path, ref: str) -> Path:
    """Resolve a path string from a YAML against the directory of that YAML."""

    p = Path(ref)
    return p if p.is_absolute() else (base / p).resolve()


def load_config(path: Path | str) -> PipelineConfig:
    """Load and validate the full pipeline configuration tree.

    Parameters
    ----------
    path
        Path to the top-level YAML (e.g. ``config/default.yaml``).

    Returns
    -------
    PipelineConfig
        The validated configuration with all sibling files materialized.

    Raises
    ------
    pydantic.ValidationError
        If any file fails schema validation.
    FileNotFoundError
        If a sibling file referenced by the top-level YAML is missing.
    """

    root_path = Path(path).resolve()
    raw = RawPipelineConfig.model_validate(_read_yaml(root_path))
    base_dir = root_path.parent

    asset_doc = _read_yaml(_resolve(base_dir, raw.asset_hierarchy_path))
    asset_hierarchy = AssetHierarchy.model_validate(asset_doc)

    tags_doc = _read_yaml(_resolve(base_dir, raw.tags_path))
    tags = [TagDefinition.model_validate(t) for t in cast(list[Any], tags_doc["tags"])]

    lab_doc = _read_yaml(_resolve(base_dir, raw.lab_panel_path))
    lab_panel = [LabTest.model_validate(t) for t in cast(list[Any], lab_doc["tests"])]

    scen_doc = _read_yaml(_resolve(base_dir, raw.scenarios_path))
    scenarios = [
        FaultScenario.model_validate(s) for s in cast(list[Any], scen_doc["fault_scenarios"])
    ]

    return PipelineConfig(
        seed=raw.seed,
        simulation_freq=raw.simulation_freq,
        pi_output_freq=raw.pi_output_freq,
        lims_report_delay_hours=raw.lims_report_delay_hours,
        base_operation=raw.base_operation,
        asset_hierarchy=asset_hierarchy,
        tags=tags,
        lab_panel=lab_panel,
        scenarios=scenarios,
    )
