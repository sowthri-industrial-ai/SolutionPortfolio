"""Scenario generator.

Produces a single canonical timeline that all downstream data sources
subscribe to. Cross-source consistency (a fault visible in both PI and LIMS)
emerges from this shared source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from rsd.schemas import BaseOperation, FaultScenario

_FAULT_STATE_COLUMN: dict[str, str] = {
    "exchanger_fouling": "fouling_E101",
}

_NO_FAULT = "NONE"


@dataclass(frozen=True)
class ScenarioGenerator:
    """Builds the timeline DataFrame consumed by physics and downstream layers.

    Parameters
    ----------
    base_operation
        Steady-state operating envelope.
    scenarios
        Fault scenarios to inject. Empty list means a fault-free run.
    seed
        Master seed for all stochastic draws.
    """

    base_operation: BaseOperation
    scenarios: tuple[FaultScenario, ...]
    seed: int

    def generate(
        self,
        start: datetime | str,
        end: datetime | str,
        freq: str = "5min",
    ) -> pd.DataFrame:
        """Return a DataFrame indexed by ``freq`` timestamps in ``[start, end)``.

        Columns: ``feed_rate_kg_h``, ``feed_temp_c``, ``furnace_target_c``,
        every fault-state column declared in :data:`_FAULT_STATE_COLUMN` (zero
        outside fault windows), ``api_delta``, ``active_fault``.
        """

        ts = pd.date_range(start=start, end=end, freq=freq, inclusive="left")
        n = len(ts)
        rng = np.random.default_rng(self.seed)

        feed = self.base_operation.feed_rate_kg_h
        temp = self.base_operation.feed_temp_c

        feed_rate = rng.normal(feed.mean, feed.std, size=n)

        hours = ts.hour.to_numpy(dtype=float) + ts.minute.to_numpy(dtype=float) / 60.0
        diurnal = temp.diurnal_amplitude_c * np.cos(
            (hours - temp.diurnal_peak_hour) * 2.0 * np.pi / 24.0
        )
        feed_temp = rng.normal(temp.mean, temp.std, size=n) + diurnal

        df = pd.DataFrame(
            {
                "feed_rate_kg_h": feed_rate,
                "feed_temp_c": feed_temp,
                "furnace_target_c": np.full(n, float(self.base_operation.furnace_target_c)),
            },
            index=ts,
        )
        df.index.name = "timestamp"

        # Every fault-state column exists, zero-valued by default.
        for col in sorted(set(_FAULT_STATE_COLUMN.values())):
            df[col] = 0.0

        df["api_delta"] = 0.0
        active_fault = np.full(n, _NO_FAULT, dtype=object)

        for scen in self.scenarios:
            col = _FAULT_STATE_COLUMN[scen.type]
            duration = pd.Timedelta(days=scen.duration_days)
            start_t = pd.Timestamp(scen.start)
            end_t = start_t + duration
            mask = (ts >= start_t) & (ts < end_t)
            if not mask.any():
                continue
            elapsed_s = (ts[mask] - start_t).total_seconds().to_numpy(dtype=float)
            fraction = elapsed_s / duration.total_seconds()
            df.loc[mask, col] = fraction * scen.severity_final
            active_fault[mask] = scen.id

        df["active_fault"] = active_fault
        return df
