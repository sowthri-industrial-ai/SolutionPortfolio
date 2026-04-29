"""The injected fouling fault must be statistically recoverable from PI data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from rsd.generate import run_pipeline

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


def test_fuel_gas_flow_slope_rises_inside_fault_window(tmp_path: Path) -> None:
    """3-month run with the configured fouling fault in month 2.

    Outside the fault window the fuel-gas signal is stationary; inside the
    window it ramps because UA falls and the furnace must compensate. Linear
    regression of FI_301.PV against time should therefore have a much larger
    positive slope inside the window than outside.
    """

    out = tmp_path / "output"
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-03-15",
        end="2025-06-14",
        output_path=out,
        seed_override=42,
    )

    months = [
        out / "pi" / "year=2025" / "month=03" / "data.parquet",
        out / "pi" / "year=2025" / "month=04" / "data.parquet",
        out / "pi" / "year=2025" / "month=05" / "data.parquet",
        out / "pi" / "year=2025" / "month=06" / "data.parquet",
    ]
    pi = pd.concat([pd.read_parquet(p) for p in months if p.exists()]).sort_index()

    fault_start = pd.Timestamp("2025-04-15")
    before_window = pi.loc[pi.index < fault_start, "FI_301.PV"].dropna()
    inside_window = pi.loc[pi.index >= fault_start, "FI_301.PV"].dropna()

    assert len(before_window) > 0 and len(inside_window) > 0

    def _slope(series: pd.Series) -> tuple[float, float]:
        x = (series.index.astype("int64") / 1e9 / 86400.0).to_numpy()  # days
        y = series.to_numpy(dtype=float)
        result = stats.linregress(x, y)
        return float(result.slope), float(result.stderr)

    slope_before, stderr_before = _slope(before_window)
    slope_inside, stderr_inside = _slope(inside_window)

    # Inside-window slope must be much larger than outside-window slope.
    assert slope_inside > slope_before + 5 * (stderr_before + stderr_inside)
    # And the slope difference should be at least an order of magnitude.
    assert abs(slope_inside) > 10 * abs(slope_before) + 1e-6


def test_active_fault_label_alignment(tmp_path: Path) -> None:
    """Ground-truth labels should mark the FOUL_001 window correctly."""

    out = tmp_path / "output"
    run_pipeline(
        config_path=CONFIG_PATH,
        start="2025-03-15",
        end="2025-06-14",
        output_path=out,
        seed_override=42,
    )
    labels = pd.read_parquet(out / "ground_truth" / "labels.parquet")
    in_window = (labels.index >= pd.Timestamp("2025-04-15")) & (
        labels.index < pd.Timestamp("2025-04-15") + pd.Timedelta(days=60)
    )
    assert (labels.loc[in_window, "active_fault"] == "FOUL_001").all()
    assert (labels.loc[~in_window, "active_fault"] == "NONE").all()
    assert np.all(np.diff(labels.loc[in_window, "fouling_E101"].to_numpy()) > 0)
