"""LIMS writer.

Generates sparse lab-record samples from the clean physics DataFrame. Each
lab test fires on its own cadence; samples occasionally fail to materialize
(missed bottle, rejected sample); measured values carry test-specific
reproducibility noise; report_time lags sample_time by the configured delay.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from rsd.schemas import LabTest

_MISS_RATE: float = 0.02


@dataclass(frozen=True)
class LIMSWriter:
    """Generate long-format LIMS records from clean physics.

    Parameters
    ----------
    lab_tests
        Test definitions (method, property, stream, frequency, uncertainty).
    report_delay_hours
        Lag between ``sample_time`` and ``report_time``.
    seed
        Master seed for both miss-sample draws and measurement noise.
    """

    lab_tests: tuple[LabTest, ...]
    report_delay_hours: float
    seed: int

    def generate(self, clean_df: pd.DataFrame) -> pd.DataFrame:
        """Return one long-format DataFrame with all lab records.

        Parameters
        ----------
        clean_df
            Physics DataFrame whose columns include every ``physics_output``
            referenced by ``self.lab_tests``.

        Returns
        -------
        pandas.DataFrame
            Columns: ``sample_id``, ``functional_location``, ``stream``,
            ``test_method``, ``property``, ``value``, ``units``,
            ``sample_time``, ``report_time``, ``true_value``. Sorted by
            ``sample_time`` then ``test_method``/``property``.
        """

        missing = [
            t.physics_output for t in self.lab_tests if t.physics_output not in clean_df.columns
        ]
        if missing:
            raise KeyError(
                f"clean_df missing physics_output columns required by lab tests: "
                f"{sorted(set(missing))}"
            )

        rng = np.random.default_rng(self.seed)
        report_delta = pd.Timedelta(hours=self.report_delay_hours)
        records: list[dict[str, object]] = []

        start = clean_df.index[0]
        end = clean_df.index[-1]

        for test_idx, test in enumerate(self.lab_tests):
            sample_times = pd.date_range(
                start=start, end=end, freq=pd.Timedelta(hours=test.frequency_hours)
            )
            n = len(sample_times)
            if n == 0:
                continue

            true_series = clean_df[test.physics_output].reindex(sample_times, method="nearest")
            true_values = true_series.to_numpy(dtype=float)

            kept = rng.random(n) >= _MISS_RATE
            noise = rng.normal(0.0, test.uncertainty_std, size=n)

            for seq, ts in enumerate(sample_times):
                if not kept[seq]:
                    continue
                true_v = float(true_values[seq])
                measured = true_v + float(noise[seq])
                records.append(
                    {
                        "sample_id": f"LIMS-{test_idx:02d}-{seq:06d}",
                        "functional_location": test.stream,
                        "stream": test.stream,
                        "test_method": test.method,
                        "property": test.property,
                        "value": measured,
                        "units": test.units,
                        "sample_time": ts,
                        "report_time": ts + report_delta,
                        "true_value": true_v,
                    }
                )

        df = pd.DataFrame.from_records(records)
        if df.empty:
            return df
        df = df.sort_values(
            ["sample_time", "test_method", "property", "stream"], kind="stable"
        ).reset_index(drop=True)
        df["sample_time"] = pd.to_datetime(df["sample_time"])
        df["report_time"] = pd.to_datetime(df["report_time"])
        return df
