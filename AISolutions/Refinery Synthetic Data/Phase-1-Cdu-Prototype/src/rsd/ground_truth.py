"""Ground truth writer.

Writes the noise-free labels (active fault, fault-state columns) and the
clean physics signals to Parquet, indexed by the same timestamp axis as the
noisy outputs so downstream evaluation can join PI/LIMS records to the truth
on a single key.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_LABEL_COLUMNS: tuple[str, ...] = ("active_fault", "fouling_E101")


@dataclass(frozen=True)
class GroundTruthWriter:
    """Build and persist ground-truth artifacts derived from scenario+physics."""

    def build_labels(self, scenario_df: pd.DataFrame) -> pd.DataFrame:
        """Return a DataFrame of fault labels indexed by timestamp.

        Columns: ``active_fault`` plus every fault-state column present in
        ``scenario_df`` (currently :data:`_LABEL_COLUMNS`).
        """

        missing = [c for c in _LABEL_COLUMNS if c not in scenario_df.columns]
        if missing:
            raise KeyError(f"scenario_df missing label columns: {missing}")
        out = scenario_df[list(_LABEL_COLUMNS)].copy()
        out.index.name = "timestamp"
        return out

    def build_true_values(self, clean_df: pd.DataFrame) -> pd.DataFrame:
        """Return the clean physics DataFrame, ready to be joined on timestamp."""

        out = clean_df.copy()
        out.index.name = "timestamp"
        return out

    def write(
        self,
        scenario_df: pd.DataFrame,
        clean_df: pd.DataFrame,
        out_dir: Path | str,
    ) -> tuple[Path, Path]:
        """Materialize ``labels.parquet`` and ``true_values.parquet``.

        Parameters
        ----------
        scenario_df
            Scenario DataFrame from :class:`rsd.scenario.ScenarioGenerator`.
        clean_df
            Clean physics DataFrame from :func:`rsd.physics.simulate_batch`.
        out_dir
            Directory to write into. Created if missing.

        Returns
        -------
        tuple[pathlib.Path, pathlib.Path]
            Paths of the two Parquet files (labels, true_values).
        """

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        labels = self.build_labels(scenario_df)
        true_values = self.build_true_values(clean_df)
        labels_path = out_dir / "labels.parquet"
        true_path = out_dir / "true_values.parquet"
        labels.to_parquet(labels_path)
        true_values.to_parquet(true_path)
        return labels_path, true_path
