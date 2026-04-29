"""Realism layer.

Adds the artifacts that distinguish a real PI tag stream from clean physics:
sensor lag, slow drift, Gaussian noise, DCS quantization, occasional gaps,
and swinging-door deadband compression. Operates on the clean physics
DataFrame produced by :mod:`rsd.physics`; the physics module itself stays
artifact-free so it remains a clean seam for DWSIM/IDAES later.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.signal import lfilter, lfilter_zi

from rsd.schemas import TagDefinition

_GAP_PROB_PER_SAMPLE: float = 1e-4
_GAP_MIN_MIN: int = 5
_GAP_MAX_MIN: int = 30
_DCS_LEVELS: int = 4096  # 12-bit


@dataclass(frozen=True)
class RealismLayer:
    """Apply per-tag sensor artifacts to a clean physics DataFrame."""

    tags: tuple[TagDefinition, ...]
    seed: int

    def apply(self, clean_df: pd.DataFrame, target_freq: str = "1min") -> pd.DataFrame:
        """Resample clean physics to ``target_freq`` and emit per-tag PI columns.

        Parameters
        ----------
        clean_df
            Physics output indexed by simulation-cadence timestamps. All
            ``physics_output`` columns referenced by ``self.tags`` must be
            present.
        target_freq
            Final PI cadence (default 1-minute).

        Returns
        -------
        pandas.DataFrame
            Indexed by ``target_freq`` timestamps; one column per tag, named
            by ``tag.name``.
        """

        missing = [t.physics_output for t in self.tags if t.physics_output not in clean_df.columns]
        if missing:
            raise KeyError(
                f"clean_df missing physics_output columns required by tags: {sorted(set(missing))}"
            )

        new_index = pd.date_range(start=clean_df.index[0], end=clean_df.index[-1], freq=target_freq)
        resampled = clean_df.reindex(new_index).interpolate(method="cubic")
        resampled = resampled.ffill().bfill()

        rng = np.random.default_rng(self.seed)
        dt_s = pd.Timedelta(target_freq).total_seconds()

        out = pd.DataFrame(index=new_index)
        out.index.name = "timestamp"

        for tag in self.tags:
            x = resampled[tag.physics_output].to_numpy(dtype=float)
            x = _apply_lag(x, tag.lag_seconds, dt_s)
            x = _apply_drift(x, tag.drift_per_day, dt_s, rng)
            x = _apply_noise(x, tag.span, tag.noise_pct, rng)
            x = _quantize(x, tag.span)
            x = _inject_gaps(x, dt_s, rng)
            x = _compress(x, tag.span, tag.compression_deadband_pct)
            out[tag.name] = x

        return out


def _apply_lag(x: NDArray[np.float64], tau_s: float, dt_s: float) -> NDArray[np.float64]:
    """First-order discrete lag with time constant ``tau_s``."""

    if tau_s <= 0.0:
        return x.copy()
    alpha = 1.0 - float(np.exp(-dt_s / tau_s))
    b = np.array([alpha])
    a = np.array([1.0, -(1.0 - alpha)])
    zi = lfilter_zi(b, a) * x[0]
    y, _ = lfilter(b, a, x, zi=zi)
    return np.asarray(y, dtype=float)


def _apply_drift(
    x: NDArray[np.float64],
    drift_per_day: float,
    dt_s: float,
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    """Add a random walk whose 1-day cumulative std equals ``drift_per_day``."""

    if drift_per_day <= 0.0:
        return x
    sigma_step = drift_per_day * np.sqrt(dt_s / 86400.0)
    steps = rng.normal(0.0, sigma_step, size=len(x))
    return x + np.cumsum(steps)


def _apply_noise(
    x: NDArray[np.float64],
    span: tuple[float, float],
    noise_pct: float,
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    """Add Gaussian noise with sigma = ``noise_pct/100 * span_range``."""

    if noise_pct <= 0.0:
        return x
    span_range = span[1] - span[0]
    sigma = noise_pct / 100.0 * span_range
    return x + rng.normal(0.0, sigma, size=len(x))


def _quantize(x: NDArray[np.float64], span: tuple[float, float]) -> NDArray[np.float64]:
    """Quantize to 12-bit DCS resolution (4096 levels across the span)."""

    span_range = span[1] - span[0]
    resolution = span_range / _DCS_LEVELS
    return np.round(x / resolution) * resolution


def _inject_gaps(
    x: NDArray[np.float64],
    dt_s: float,
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    """Mark random 5-30 minute gaps as NaN with low per-sample start probability."""

    n = len(x)
    starts = rng.random(n) < _GAP_PROB_PER_SAMPLE
    out = x.copy()
    for i in np.flatnonzero(starts):
        gap_min = int(rng.integers(_GAP_MIN_MIN, _GAP_MAX_MIN + 1))
        gap_samples = max(1, int(np.ceil(gap_min * 60.0 / dt_s)))
        end = min(int(i) + gap_samples, n)
        out[int(i) : end] = np.nan
    return out


def _compress(
    x: NDArray[np.float64],
    span: tuple[float, float],
    deadband_pct: float,
) -> NDArray[np.float64]:
    """Swinging-door deadband: drop samples within deadband of last recorded.

    NaN samples (gaps) are preserved as-is. The output is dense — dropped
    samples are forward-filled from the most recent recorded value, so the
    column has no extra NaN from compression itself.
    """

    if deadband_pct <= 0.0:
        return x
    span_range = span[1] - span[0]
    deadband = deadband_pct / 100.0 * span_range
    return _compress_loop(x, deadband)


def _compress_loop(x: NDArray[np.float64], deadband: float) -> NDArray[np.float64]:
    """Tight Python loop kept separate so it can be replaced by a JIT later."""

    out = x.copy()
    n = len(x)
    last_recorded = 0.0
    initialized = False
    for i in range(n):
        v = out[i]
        if v != v:  # NaN check, faster than np.isnan in a loop
            continue
        if not initialized:
            last_recorded = v
            initialized = True
            continue
        if abs(v - last_recorded) > deadband:
            last_recorded = v
        else:
            out[i] = last_recorded
    return out
