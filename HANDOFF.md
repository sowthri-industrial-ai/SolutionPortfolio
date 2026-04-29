# How to hand this off to the Claude builder

This directory contains everything needed for a Claude Code session
(or equivalent) to build the Refinery Synthetic Data generator end-to-end.

## Files

- `RSD_BRIEF.md` — the full builder brief. Read this first.
- `config/default.yaml` — top-level pipeline configuration.
- `config/asset_hierarchy.yaml` — site/unit/equipment/stream definitions.
- `config/tags.yaml` — 18 PI tag definitions for the CDU.
- `config/lab_panel.yaml` — 4 lab tests for the LIMS data source.
- `config/scenarios.yaml` — one fouling fault scenario.

## Suggested handoff prompt for Claude Code

Open Claude Code in the target repository directory, then say:

> Read `RSD_BRIEF.md` and every file under `config/`. Then build the
> project according to the module sequence in section 5. Build one
> module at a time. After each module, run that module's tests, run
> `ruff check src/` and `mypy src/`, then commit before moving on.
> If you finish a module and any test fails, stop and fix it before
> proceeding. If anything in the brief is ambiguous, ask before
> guessing. When all 11 modules are done, run the full acceptance
> test suite from section 9 and report the results.

That's it. The builder will produce a working repository.

## How to verify the build

After the builder reports completion, run from the repo root:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/
ruff check src/ tests/
mypy src/
python -m rsd.generate \
    --config config/default.yaml \
    --start 2025-01-01 \
    --end 2025-12-31 \
    --output ./output \
    --seed 42
python examples/detect_fault.py ./output
```

All commands should exit 0. The fault detection script should report
a window starting within ±2 days of 2025-04-15.

## Extending after the prototype works

The mock physics module (`src/rsd/physics.py`) is the seam for
swapping in DWSIM or IDAES later. The function signature
`simulate(inputs: PhysicsInputs) -> PhysicsOutputs` is stable;
replace its body, leave everything else alone.

Adding a new data source (alarms, CMMS, logbook, etc.) means:
1. Add a writer module under `src/rsd/`.
2. Add its config schema to `src/rsd/schemas.py`.
3. Wire it into `src/rsd/generate.py`.
4. Add tests.

The architecture deliberately makes each new source an additive change.
