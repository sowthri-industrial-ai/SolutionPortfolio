# RSD User Manual

Phase 1 of the Refinery Synthetic Data generator. This manual covers installation, dataset generation, and the three primary usage patterns.

## Prerequisites

- macOS or Linux
- Python 3.11 or later
- About 2 GB of free disk space (a year of synthetic data is ~1.5 GB compressed Parquet)

## Installation

```bash
cd <repo-root>
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verify the install:

```bash
pytest tests/         # 74 tests should pass
ruff check src/ tests/
mypy src/
```

All three should exit clean.

## Usage 1 — Generate a synthetic dataset

The primary use case. One command produces a full year of synthetic refinery data.

```bash
python -m rsd.generate \
    --config config/default.yaml \
    --start 2025-01-01 \
    --end 2025-12-31 \
    --output ./output \
    --seed 42
```

### CLI options

| Flag | Required | Description |
|---|---|---|
| `--config` | yes | Path to the top-level YAML config (typically `config/default.yaml`) |
| `--start` | yes | First day to generate, ISO format (e.g., `2025-01-01`) |
| `--end` | yes | Last day to generate, exclusive ISO format (e.g., `2025-12-31`) |
| `--output` | yes | Directory to write outputs into (created if missing) |
| `--seed` | no | Random seed; overrides the seed in `config/default.yaml` |

### Output structure

```
output/
├── pi/year=YYYY/month=MM/data.parquet    # 1-min PI tags, partitioned by month
├── lims/lab_records.parquet              # sparse LIMS samples
├── ground_truth/labels.parquet           # noise-free fault labels
├── ground_truth/true_values.parquet      # noise-free physics values
└── metadata/run_info.json                # provenance metadata
```

### Reproducibility

Same `--config` plus same `--seed` produces byte-identical output every run. This is enforced by an acceptance test.

### Performance

A full year (105,120 scenario rows × 18 PI tags × 1-minute resolution) generates in approximately 3 seconds on a developer laptop.

### Customizing the dataset

All tunable parameters live in `config/`. Common edits:

- **Different fault timing or severity:** edit `config/scenarios.yaml`, change `start`, `duration_days`, or `severity_final`.
- **Different feed conditions:** edit `config/default.yaml`, change `base_operation.feed_rate_kg_h.mean` or `feed_temp_c.mean`.
- **Different tag noise/lag:** edit `config/tags.yaml`, change `noise_pct`, `lag_seconds`, or `compression_deadband_pct` per tag.
- **Different lab cadence:** edit `config/lab_panel.yaml`, change `frequency_hours` per test.

No code changes required for any of these.

## Usage 2 — Read and analyze the data in Python

Output is standard Parquet. Anything that reads Parquet works (pandas, Polars, DuckDB, Spark).

### Read PI data (all months)

```python
import pandas as pd

# Reads every monthly partition under output/pi/ in one call.
pi = pd.read_parquet("output/pi/")
print(pi.shape)        # (525596, 18) for a full year
print(pi.columns)      # 18 PI tag names
```

### Read LIMS data

```python
lims = pd.read_parquet("output/lims/lab_records.parquet")
print(lims.head())
# Columns: sample_id, functional_location, stream, test_method,
# property, value, units, sample_time, report_time, true_value
```

### Read ground truth

```python
labels = pd.read_parquet("output/ground_truth/labels.parquet")
truth = pd.read_parquet("output/ground_truth/true_values.parquet")

# Where is the fault active?
print(labels["active_fault"].value_counts())

# The injected fouling severity over time
print(labels[labels["fouling_E101"] > 0]["fouling_E101"].describe())
```

### Join noisy data to ground truth

The ground truth lives at the 5-minute physics cadence; PI lives at 1-minute. Use forward-fill alignment:

```python
aligned = labels.reindex(pi.index, method="ffill")
evaluation = pd.concat([pi, aligned], axis=1)
# Now you can train a model on PI columns and evaluate against
# active_fault as the supervised label.
```

### Read run metadata

```python
import json
with open("output/metadata/run_info.json") as f:
    meta = json.load(f)
print(meta)  # config_version, code_version, seed, runtime_seconds, row counts
```

## Usage 3 — Run the example fault detector

A standalone consumer script that demonstrates the dataset is genuinely useful: it recovers the injected fouling event from noisy data using a simple rolling-mean detector.

```bash
python examples/detect_fault.py ./output
```

Expected output:

```
Detected fault window:
  start    : 2025-04-14 14:53:00
  end      : 2025-06-17 10:05:00
  ...
```

Compare against the configured fault in `config/scenarios.yaml` (default: 2025-04-15 to 2025-06-14). Start should be within ±2 days; end is within ±9 days due to rolling-window edge smearing (see README.md "Detector limitations" for explanation).

## Common workflows

### Generate multiple datasets for cross-validation

Loop over seeds:

```bash
for seed in 1 2 3 4 5; do
    python -m rsd.generate \
        --config config/default.yaml \
        --start 2025-01-01 --end 2025-12-31 \
        --output ./output_seed_${seed} \
        --seed ${seed}
done
```

Each output directory contains a complete, deterministic dataset variant.

### Generate a short dataset for fast iteration

```bash
python -m rsd.generate \
    --config config/default.yaml \
    --start 2025-04-01 --end 2025-05-01 \
    --output ./output_short --seed 42
```

One month, generates in well under a second.

### Train a fault classifier (sketch)

```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

pi = pd.read_parquet("output/pi/")
labels = pd.read_parquet("output/ground_truth/labels.parquet")
y = labels["active_fault"].reindex(pi.index, method="ffill") != "NONE"

X_train, X_test, y_train, y_test = train_test_split(
    pi.fillna(method="ffill"), y, test_size=0.2, shuffle=False
)

clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train, y_train)
print(f"Test accuracy: {clf.score(X_test, y_test):.3f}")
```

## Troubleshooting

**Pipeline runs but produces empty output:** check that `--start` is before `--end`. The pipeline silently writes nothing for a zero-length range.

**Determinism check fails:** confirm both runs used identical `--config` content and `--seed`. Parquet binary metadata may differ across runs; the data values do not.

**Out-of-memory on a long range:** generate month-by-month or quarter-by-quarter, then concatenate with `pd.read_parquet("output/pi/")`.

**`ModuleNotFoundError: No module named 'rsd'`:** the venv isn't active or `pip install -e .` wasn't run. Run `source .venv/bin/activate && pip install -e ".[dev]"`.

**Want a different fault but only fouling is implemented:** correct — Phase 1 only supports `exchanger_fouling`. Adding pump degradation or off-spec feed is Phase 2 work.

## Where to learn more

- `README.md` — project overview and quickstart
- `ARCHITECTURE.md` — design principles and module map
- `ABOUT_FILES.md` — guide to every file and folder in the repository
- `config/*.yaml` — every tunable parameter, with comments
- `tests/` — examples of how every module is exercised
