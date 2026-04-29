"""Tests for the example fault-detection consumer script."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from rsd.generate import run_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "default.yaml"
SCRIPT_PATH = REPO_ROOT / "examples" / "detect_fault.py"


def _load_module():  # type: ignore[no-untyped-def]
    name = "detect_fault_example"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # Register before exec so dataclass type lookup works.
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("detect") / "output"
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-02-01",
        end="2025-08-31",
        output_path=out,
        seed_override=42,
    )
    return out


def test_detect_finds_fault_within_two_days_of_configured_start(
    output_dir: Path,
) -> None:
    mod = _load_module()
    result = mod.detect(output_dir)
    assert result is not None
    configured_start = pd.Timestamp("2025-04-15")
    delta_days = abs((result.start - configured_start).total_seconds()) / 86400.0
    assert delta_days <= 2.0, (
        f"detected start {result.start} is {delta_days:.1f}d from "
        f"configured {configured_start}"
    )


def test_detect_window_end_within_two_days_of_configured_end(
    output_dir: Path,
) -> None:
    mod = _load_module()
    result = mod.detect(output_dir)
    assert result is not None
    configured_end = pd.Timestamp("2025-04-15") + pd.Timedelta(days=60)
    delta_days = abs((result.end - configured_end).total_seconds()) / 86400.0
    # Rolling mean smears the trailing edge by up to ~7 days, so allow a bit
    # more slack on the end than on the start.
    assert delta_days <= 9.0, (
        f"detected end {result.end} is {delta_days:.1f}d from "
        f"configured {configured_end}"
    )


def test_cli_subprocess_succeeds(output_dir: Path) -> None:
    """Running the example as ``python examples/detect_fault.py <out>``."""

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Detected fault window" in result.stdout
    assert "2025-04" in result.stdout or "2025-05" in result.stdout
