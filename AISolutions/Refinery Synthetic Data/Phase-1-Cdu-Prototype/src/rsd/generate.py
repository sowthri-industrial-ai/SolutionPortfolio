"""Pipeline orchestrator and CLI entrypoint.

Glues together :mod:`rsd.scenario`, :mod:`rsd.physics`, :mod:`rsd.realism`,
:mod:`rsd.lims`, and :mod:`rsd.ground_truth` into a single command. Side
effects — directory creation, Parquet writes, JSON snapshot — are confined
to this module; everything below it is a pure function or a side-effect-free
DataFrame transform.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import click
import pandas as pd

from rsd import __version__
from rsd.config import load_config
from rsd.ground_truth import GroundTruthWriter
from rsd.lims import LIMSWriter
from rsd.physics import simulate_batch
from rsd.realism import RealismLayer
from rsd.scenario import ScenarioGenerator
from rsd.schemas import PipelineConfig


@click.command()
@click.option(
    "--config",
    "config_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the top-level pipeline YAML.",
)
@click.option(
    "--start",
    required=True,
    type=str,
    help="Inclusive start date (YYYY-MM-DD).",
)
@click.option(
    "--end",
    required=True,
    type=str,
    help="Inclusive end date (YYYY-MM-DD). The full day is included.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory. Existing partitions are overwritten.",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Override the config seed (useful for sweeps).",
)
def main(
    config_path: Path,
    start: str,
    end: str,
    output_path: Path,
    seed: int | None,
) -> None:
    """Generate synthetic CDU data for the given date range."""

    run_pipeline(
        config_path=config_path,
        start=start,
        end=end,
        output_path=output_path,
        seed_override=seed,
    )


def run_pipeline(
    *,
    config_path: Path,
    start: str,
    end: str,
    output_path: Path,
    seed_override: int | None = None,
) -> dict[str, object]:
    """Run the full pipeline and persist outputs.

    Returns
    -------
    dict
        Run-info dictionary (also written to ``metadata/run_info.json``).
    """

    t0 = time.perf_counter()
    cfg = load_config(config_path)
    effective_seed = seed_override if seed_override is not None else cfg.seed

    start_dt = pd.Timestamp(start)
    end_exclusive = pd.Timestamp(end) + pd.Timedelta(days=1)
    click.echo(
        f"[rsd] {start} -> {end} (exclusive {end_exclusive.date()}), "
        f"output={output_path}, seed={effective_seed}"
    )

    scen = ScenarioGenerator(
        base_operation=cfg.base_operation,
        scenarios=tuple(cfg.scenarios),
        seed=effective_seed,
    ).generate(start_dt, end_exclusive, freq=cfg.simulation_freq)
    click.echo(f"[rsd] scenario: {len(scen):,} rows at {cfg.simulation_freq}")

    clean = simulate_batch(scen)
    click.echo(f"[rsd] physics: {len(clean):,} rows")

    pi = RealismLayer(tags=tuple(cfg.tags), seed=effective_seed).apply(
        clean, target_freq=cfg.pi_output_freq
    )
    click.echo(f"[rsd] PI: {len(pi):,} rows x {len(pi.columns)} tags at {cfg.pi_output_freq}")

    lims = LIMSWriter(
        lab_tests=tuple(cfg.lab_panel),
        report_delay_hours=cfg.lims_report_delay_hours,
        seed=effective_seed,
    ).generate(clean)
    click.echo(f"[rsd] LIMS: {len(lims):,} records")

    output_path = Path(output_path)
    _write_pi_partitioned(pi, output_path / "pi")
    _write_lims(lims, output_path / "lims")
    GroundTruthWriter().write(scen, clean, output_path / "ground_truth")

    runtime_s = time.perf_counter() - t0
    info = _write_metadata(
        path=output_path / "metadata" / "run_info.json",
        cfg=cfg,
        effective_seed=effective_seed,
        start=start,
        end=end,
        runtime_s=runtime_s,
        config_path=config_path,
    )
    click.echo(f"[rsd] done in {runtime_s:.2f}s -> {output_path}")
    return info


def _write_pi_partitioned(pi: pd.DataFrame, root: Path) -> None:
    """Write PI tags to ``root/year=YYYY/month=MM/data.parquet`` partitions."""

    if root.exists():
        shutil.rmtree(root)
    if pi.empty:
        return
    idx = pd.DatetimeIndex(pi.index)
    grouped = pi.groupby([idx.year, idx.month])
    for key, df_month in grouped:
        year_month = cast(tuple[int, int], key)
        year, month = year_month
        path = root / f"year={year}" / f"month={month:02d}" / "data.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df_month.to_parquet(path)
        click.echo(f"[rsd] wrote PI {year}-{month:02d}: {len(df_month):,} rows")


def _write_lims(lims: pd.DataFrame, root: Path) -> None:
    """Write all LIMS records as a single sparse Parquet file."""

    root.mkdir(parents=True, exist_ok=True)
    lims.to_parquet(root / "lab_records.parquet", index=False)


def _write_metadata(
    *,
    path: Path,
    cfg: PipelineConfig,
    effective_seed: int,
    start: str,
    end: str,
    runtime_s: float,
    config_path: Path,
) -> dict[str, object]:
    """Write ``run_info.json`` and return the dict."""

    path.parent.mkdir(parents=True, exist_ok=True)
    info: dict[str, object] = {
        "rsd_version": __version__,
        "config_path": str(config_path.resolve()),
        "start": start,
        "end": end,
        "effective_seed": effective_seed,
        "config_seed": cfg.seed,
        "runtime_seconds": round(runtime_s, 3),
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "config_snapshot": json.loads(cfg.model_dump_json()),
    }
    path.write_text(json.dumps(info, indent=2, sort_keys=True))
    return info


def _git_sha() -> str | None:
    """Return the current HEAD SHA, or ``None`` if not in a git repo."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


if __name__ == "__main__":
    main()
