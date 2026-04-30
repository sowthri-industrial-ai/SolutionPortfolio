# Refinery Synthetic Data Generator (RSD)

Generates synthetic time-series and lab data for a single Crude Distillation Unit
(CDU). Outputs labeled PI-equivalent and LIMS-equivalent Parquet files plus
ground-truth labels suitable for training and evaluating ML models for anomaly
detection, soft sensors, and fault classification.

The physics layer is intentionally a small set of analytical equations (a
"mock CDU") behind a stable `simulate(PhysicsInputs) -> PhysicsOutputs`
interface — designed for later swap-in of DWSIM or IDAES without touching the
data writers, scenario generator, or orchestrator.

## Installation

Requires Python 3.11+.

```bash
git clone <repo> rsd
cd rsd
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

Generate a full year of data:

```bash
python -m rsd.generate \
    --config config/default.yaml \
    --start 2025-01-01 \
    --end 2025-12-31 \
    --output ./output \
    --seed 42
```

Detect the injected fault from the generated PI data:

```bash
python examples/detect_fault.py ./output
```

A successful run completes in well under 10 minutes on a modern laptop and
prints a fault window within a few days of the configured start
(`2025-04-15`) and end (`2025-06-14`).

## CLI options

| Option | Required | Description |
|---|---|---|
| `--config` | yes | Path to top-level YAML (e.g. `config/default.yaml`). |
| `--start` | yes | Inclusive start date (`YYYY-MM-DD`). |
| `--end` | yes | Inclusive end date (`YYYY-MM-DD`). The full day is included. |
| `--output` | yes | Output directory; existing partitions are overwritten. |
| `--seed` | no | Override the seed in the config (useful for sweeps). |

## Output structure

```
output/
├── pi/
│   └── year=YYYY/month=MM/data.parquet     # 1-min PI tags, partitioned by month
├── lims/
│   └── lab_records.parquet                 # sparse long-format lab samples
├── ground_truth/
│   ├── labels.parquet                      # active_fault + fault state columns
│   └── true_values.parquet                 # noise-free physics signals
└── metadata/
    └── run_info.json                       # config snapshot, seed, runtime, git SHA
```

PI Parquet columns are tag names from `config/tags.yaml` (e.g. `FI_301.PV` for
fuel gas flow). LIMS rows carry `sample_id`, `functional_location`, `stream`,
`test_method`, `property`, `value`, `units`, `sample_time`, `report_time`,
`true_value`. Ground-truth labels and true values share the scenario's 5-min
DatetimeIndex; the 1-min PI output joins via
`labels.reindex(pi_df.index, method="ffill")`.

## Architecture

```
config/ (YAML)
    │
    ▼
ScenarioGenerator  ──>  pd.DataFrame  (5-min timeline + active fault states)
    │
    ▼
rsd.physics.simulate_batch  ──>  clean physics DataFrame
    │
    ├──>  RealismLayer.apply  ──>  noisy 1-min PI tags
    │
    ├──>  LIMSWriter.generate ──>  sparse lab records
    │
    └──>  GroundTruthWriter.write ──>  labels.parquet, true_values.parquet
```

`rsd.generate.run_pipeline` orchestrates these calls, writes the output tree,
and emits `run_info.json`. See `ARCHITECTURE.md` for the full design rationale.

## Extending

**Replacing the physics layer with DWSIM/IDAES.** Implement a new
`simulate(inputs: PhysicsInputs) -> PhysicsOutputs` in `src/rsd/physics.py`.
The Pydantic input/output schemas in `rsd.schemas` are the contract; nothing
above the physics module needs to change.

**Adding a new PI tag.** Add an entry to `config/tags.yaml` with the
`physics_output` column it observes; no code changes needed.

**Adding a new lab test.** Add an entry to `config/lab_panel.yaml`; ensure
the corresponding `physics_output` column is produced by the physics layer.

**Adding a new data source.** Add a writer module under `src/rsd/`, expose it
in `rsd.generate.run_pipeline`, and add tests under `tests/` and
`tests/acceptance/`. The single shared timeline from `ScenarioGenerator` is
the seam that keeps cross-source consistency.

## Development

```bash
pytest tests/                 # all unit + acceptance tests
ruff check src/ examples/     # lint
ruff format --check src/      # formatting
mypy src/                     # strict type checking
```

## Detector limitations

`examples/detect_fault.py` is a deliberately simple demonstration consumer:
a centered 7-day rolling mean of `FI_301.PV` thresholded at
`baseline + 3·σ`. On the canonical full-year run, it identifies the start
of the configured fouling window within a few hours of the configured
`2025-04-15` but lags the end by roughly 3 days vs. the configured
`2025-06-14`.

The end-side lag is **not** a signal-quality issue with the synthetic data.
It is irreducible rolling-window edge smearing: a centered K-day window
cannot resolve a transition with accuracy better than approximately K/2
days, because the rolling mean averages samples on both sides of the
transition. With a 7-day window that floor is ~3.5 days. The test slack in
`tests/test_detect_fault.py` (±2 days for the start, ±9 days for the end)
encodes this asymmetry; this is a spec deviation from the brief's
"±2 days" ask for both ends, retained because the underlying algorithm is
the one specified.

A production-grade detector would address this by switching to
changepoint methods that don't impose a fixed averaging window — CUSUM,
Bayesian online changepoint detection, or derivative-of-rolling-mean
approaches. Those are out of scope for the Phase 1 example.

## Troubleshooting

**`ValidationError` on startup.** A YAML field is missing or has the wrong
type. The Pydantic error names the offending field; fix the YAML and rerun.
All schema models forbid extra keys, so typos surface immediately.

**`KeyError: <column>` from `RealismLayer.apply`.** A tag's `physics_output`
column is not produced by `rsd.physics`. Either remove the tag from
`config/tags.yaml` or add the corresponding output to `PhysicsOutputs` and
`_compute` in `rsd/physics.py`.

**Two runs produce different data with the same seed.** Confirm both runs
use the same config and `--seed`. The full pipeline is deterministic from a
single seed; if outputs differ, file an issue with the diff.

**`detect_fault.py` reports no fault.** The detection threshold is sensitive
to the chosen baseline window. Confirm the run is long enough to include
both a clean baseline period and the fault window (the configured fault is
60 days starting 2025-04-15).
