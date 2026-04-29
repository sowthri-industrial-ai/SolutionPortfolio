# Refinery Synthetic Data Generator (RSD)

Generates synthetic time-series and lab data for a single Crude Distillation
Unit (CDU). Outputs labeled PI-equivalent and LIMS-equivalent Parquet files
plus ground-truth labels for ML model development.

## Status

Prototype scaffold. See `RSD_BRIEF.md` for the full specification.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
python -m rsd.generate \
    --config config/default.yaml \
    --start 2025-01-01 \
    --end 2025-12-31 \
    --output ./output \
    --seed 42
```

## Architecture

See `ARCHITECTURE.md` (forthcoming).
