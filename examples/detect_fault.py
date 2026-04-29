#!/usr/bin/env python3
"""Detect the fouling fault from generated PI data.

Reads every PI partition under ``<output_dir>/pi``, computes a 7-day
rolling mean of ``FI_301.PV`` (fuel gas flow), takes the first
``BASELINE_DAYS`` of the rolling signal as the baseline, and flags any
contiguous run where the rolling mean exceeds
``baseline_mean + SIGMA_MULTIPLE * baseline_std``. Reports the first such
run as the detected fault window. Print-only — no plotting dependencies.

Usage:
    python examples/detect_fault.py ./output
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

TAG_NAME: str = "FI_301.PV"
ROLLING_WINDOW: str = "7D"
# Baseline length should capture enough natural variation (feed-rate drift,
# diurnal coupling) that the resulting std reflects true rolling-mean noise,
# not under-sampled fluctuation. The configured fault starts ~73 days into
# the example run; 60 days of pre-fault baseline keeps the threshold honest.
BASELINE_DAYS: int = 60
SIGMA_MULTIPLE: float = 3.0


@dataclass(frozen=True)
class Detection:
    """The first contiguous run of above-threshold rolling-mean values."""

    start: pd.Timestamp
    end: pd.Timestamp
    threshold: float
    baseline_mean: float
    baseline_std: float


def detect(output_dir: Path) -> Detection | None:
    """Return the first detected fault window, or ``None`` if none found."""

    pi_files = sorted((output_dir / "pi").rglob("data.parquet"))
    if not pi_files:
        raise FileNotFoundError(f"no PI partitions under {output_dir / 'pi'}")
    pi = pd.concat([pd.read_parquet(p) for p in pi_files]).sort_index()
    if TAG_NAME not in pi.columns:
        raise KeyError(f"{TAG_NAME!r} missing from PI data; columns: {list(pi.columns)}")

    fuel = pi[TAG_NAME].dropna()
    if fuel.empty:
        return None
    # Centered rolling mean: at time T, mean of [T - 3.5d, T + 3.5d]. For a
    # linearly ramping signal this aligns the rolling mean's transitions with
    # the actual ramp edges instead of lagging them by half a window.
    rolling = fuel.rolling(ROLLING_WINDOW, center=True).mean()

    # Drop the warm-up at both ends (first and last 3.5 days) where the
    # centered window is partially populated.
    half = pd.Timedelta(days=3.5)
    rolling = rolling.loc[fuel.index[0] + half : fuel.index[-1] - half]
    if rolling.empty:
        return None

    base_start = fuel.index[0] + half
    base_end = fuel.index[0] + pd.Timedelta(days=BASELINE_DAYS)
    baseline = rolling.loc[base_start:base_end].dropna()
    if baseline.empty:
        return None
    baseline_mean = float(baseline.mean())
    baseline_std = float(baseline.std(ddof=0))
    threshold = baseline_mean + SIGMA_MULTIPLE * baseline_std

    above = (rolling > threshold).to_numpy()
    if not above.any():
        return None

    # Find every contiguous run of True; return the longest one. Brief blips
    # from noise are short-lived; a real fault sustains the excursion for days.
    edges = np.diff(above.astype(np.int8), prepend=0, append=0)
    run_starts = np.where(edges == 1)[0]
    run_ends = np.where(edges == -1)[0]  # exclusive
    if len(run_starts) == 0:
        return None
    lengths = run_ends - run_starts
    pick = int(np.argmax(lengths))
    start_idx = int(run_starts[pick])
    end_idx = int(run_ends[pick] - 1)

    return Detection(
        start=rolling.index[start_idx],
        end=rolling.index[end_idx],
        threshold=threshold,
        baseline_mean=baseline_mean,
        baseline_std=baseline_std,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "output_dir",
        type=Path,
        help="The output directory written by `python -m rsd.generate ...`.",
    )
    args = parser.parse_args(argv)

    result = detect(args.output_dir)
    if result is None:
        print("No fault detected.")
        return 1

    duration_days = (result.end - result.start).total_seconds() / 86400.0
    print("Detected fault window:")
    print(f"  start    : {result.start}")
    print(f"  end      : {result.end}")
    print(f"  duration : {duration_days:.1f} days")
    print(f"  baseline : mean={result.baseline_mean:.4f} kg/s, std={result.baseline_std:.4f} kg/s")
    print(f"  threshold: {result.threshold:.4f} kg/s (baseline + {SIGMA_MULTIPLE:g}-sigma)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
