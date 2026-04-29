# Refinery Synthetic Data Generator (RSD) — Builder Brief

**Version:** 1.0  
**Target builder:** Claude Code (or equivalent agentic coding assistant)  
**Estimated effort:** 2–4 days of focused work for a single developer  
**Prerequisite reading:** This document in full, plus all files in `config/`.

---

## 1. Project charter

### 1.1 What we are building

A Python package, `rsd`, that generates synthetic time-series and lab data for a single Crude Distillation Unit (CDU) of a refinery. The output is a labeled dataset suitable for training and evaluating ML models for anomaly detection, soft sensors, and fault classification.

The pipeline runs end-to-end from a single CLI command and produces:

- **PI historian-equivalent data** — 1-minute resolution time-series for ~25 process tags, written as Parquet files partitioned by month.
- **LIMS-equivalent data** — sparse lab samples (every 8 hours) with realistic sample-time vs. report-time delays, written as Parquet.
- **Ground truth** — noise-free physics values, active fault flags, and scenario metadata, written as Parquet alongside the noisy outputs.

### 1.2 Why

Real refinery data is confidential, sparse on labeled faults, and biased toward normal operation. Synthetic data with known ground truth enables rigorous ML model development and evaluation. This prototype establishes the architecture; the physics layer is mocked here but designed for later replacement with DWSIM/IDAES without changing other components.

### 1.3 Success criteria

The build is complete when **all** of the following are true:

1. Running `python -m rsd.generate --config config/default.yaml --start 2025-01-01 --end 2025-12-31 --output ./output` produces a complete year of synthetic data in under 10 minutes on a modern laptop.
2. Output structure matches the layout specified in §6.
3. Acceptance tests in `tests/acceptance/` all pass.
4. The injected fault scenario is recoverable from the data — a simple downstream analysis script (provided as `examples/detect_fault.py`) successfully identifies the fault window with reasonable precision.
5. Code passes `ruff check`, `ruff format --check`, and `mypy src/`.
6. README contains accurate setup, usage, and architecture overview.

### 1.4 Explicit non-goals

These are out of scope for this prototype. Do **not** implement them. Do **not** add scaffolding for them unless explicitly listed in the module spec.

- DWSIM or IDAES integration (deliberately deferred — the mock physics layer is a stable interface for later swap-in).
- Multiple refinery units (CDU only).
- Data sources beyond PI and LIMS (no alarms, CMMS, logbook, vibration, CEMS, etc.).
- Multiple fault scenarios (one fouling scenario only).
- Cloud deployment, Docker, or orchestration tooling.
- A web UI or visualization layer.
- Real-time streaming output (batch generation only).
- Statistical sophistication beyond what's specified (no GARCH noise, no copula-based correlation, no rare-event simulation).

If you find yourself building any of the above, stop and re-read the brief.

---

## 2. Architectural principles

These principles are non-negotiable and apply across every module.

**Separation of physics from realism.** The mock physics module produces clean, deterministic outputs given inputs. The realism module adds all sensor artifacts. They never share responsibilities. When the physics is later replaced with DWSIM, the realism module must continue to work unchanged.

**Single event timeline.** All data sources subscribe to one canonical timeline produced by the scenario generator. Cross-source consistency (e.g., a fault visible in both PI and LIMS) emerges from this shared source of truth, not from per-source coordination.

**Asset hierarchy as join key.** Every record carries a functional location string (e.g., `SITE01.CDU1.E-101`). Joins across sources happen on this key. The asset hierarchy is loaded from YAML at startup and is read-only at runtime.

**Ground truth alongside noisy data.** For every noisy output, the corresponding noise-free physics value and active fault flags are written to a separate `ground_truth/` directory. This is what makes the dataset evaluable.

**Configuration over code.** Tag definitions, lab panels, fault scenarios, and asset hierarchy live in YAML files. Adding a new tag should not require code changes. The code reads config and acts on it generically.

**Determinism via seeded RNG.** Every stochastic component takes a seed. Running the pipeline twice with the same config and seed produces identical output. This is mandatory for reproducible experiments.

**Pure functions where possible.** Generators take inputs, return outputs, no hidden state. Side effects (file I/O) are confined to the orchestrator.

---

## 3. Module map and data flow

```
┌─────────────────────────────────────────────────────────────┐
│  config/ (YAML)                                              │
│  asset_hierarchy.yaml, tags.yaml, lab_panel.yaml,            │
│  scenarios.yaml, default.yaml                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ load
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  rsd.scenario.ScenarioGenerator                              │
│  → DataFrame: timeline of inputs + active fault states       │
└──────────────────────┬──────────────────────────────────────┘
                       │ inputs at 5-min cadence
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  rsd.physics.MockCDU                                         │
│  → DataFrame: clean physics outputs at 5-min cadence         │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐
│ rsd.realism.PIWriter │  │ rsd.lims.LIMSWriter  │
│ → 1-min PI Parquet   │  │ → sparse LIMS Parquet│
└──────────┬───────────┘  └──────────┬───────────┘
           │                         │
           └────────────┬────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  rsd.ground_truth.GroundTruthWriter                          │
│  → labels.parquet, true_values.parquet                       │
└─────────────────────────────────────────────────────────────┘
                        ▲
                        │ orchestrated by
                        │
┌─────────────────────────────────────────────────────────────┐
│  rsd.generate (CLI entrypoint)                               │
│  - Loads config, instantiates components, runs pipeline      │
│  - Writes output partitioned by month                        │
└─────────────────────────────────────────────────────────────┘
```

**Data flow contract:** Each module's output is the next module's input. Schemas are defined in §5 and enforced by Pydantic models in `rsd.schemas`.

---

## 4. The mock physics layer

The mock CDU is **not** a real flowsheet simulation. It is a small set of analytical equations that capture the *qualitative* behavior of a crude distillation unit well enough to make downstream realism and ML use cases meaningful. The equations are below; implement them exactly as specified.

### 4.1 Inputs

At each timestep the physics layer receives:

| Variable | Symbol | Units | Typical value |
|---|---|---|---|
| Crude charge mass flow | F_in | kg/h | 400,000 |
| Feed temperature | T_in | °C | 25 (with diurnal swing) |
| Furnace outlet target | T_furnace | °C | 360 |
| E-101 fouling factor | f_foul | dimensionless 0–1 | 0 (clean) → 0.4 (fouled) |
| API gravity offset | ΔAPI | dimensionless | 0 (base crude) |

### 4.2 Equations

Use these exact forms. Constants are tunable but defaults below produce realistic numbers.

**Preheat exchanger E-101** (crude side cold inlet → cold outlet):
```
UA_clean = 8e5  W/K            # base heat transfer
UA = UA_clean * (1 - f_foul)
T_hot_in = 320  # °C, fixed (residue side)
T_cold_in = T_in
ΔT_lm ≈ ((T_hot_in - T_cold_out) - (T_hot_out - T_cold_in)) / ln(...)
# Simplified: assume Q = UA * (T_hot_in - T_cold_in) * effectiveness
effectiveness = 1 - exp(-UA / (F_in/3600 * 2100))   # NTU method, Cp=2100 J/kg·K
T_cold_out = T_cold_in + effectiveness * (T_hot_in - T_cold_in)
```

**Furnace F-101** (boost from preheat to flash zone temperature):
```
Q_furnace = F_in/3600 * 2300 * (T_furnace - T_cold_out)   # W, Cp=2300 J/kg·K liquid+vapor
fuel_gas_flow = Q_furnace / (50e6 * 0.85)                  # kg/s, LHV 50 MJ/kg, η=0.85
```
Note: `Q_furnace` rises when E-101 is fouled (T_cold_out drops). This is the diagnostic signature of fouling.

**Atmospheric tower T-101** (yields and key temperatures):

Use a simple parametric yield model. Base yields (mass fractions of feed):
```
y_naphtha = 0.18
y_kero    = 0.13
y_diesel  = 0.22
y_AGO     = 0.12
y_residue = 0.35
```

Adjust for ΔAPI (heavier crude → lower light yields):
```
y_naphtha = 0.18 + 0.005 * ΔAPI    # API offset of -3 → -0.015
y_kero    = 0.13 + 0.003 * ΔAPI
y_residue = 1 - (y_naphtha + y_kero + y_diesel + y_AGO)
```

Tower temperatures (simple correlations):
```
T_top      = 130 + 0.05 * (T_furnace - 360)        # °C, naphtha overhead
T_kero     = 200 + 0.04 * (T_furnace - 360)
T_diesel   = 280 + 0.04 * (T_furnace - 360)
T_AGO      = 320 + 0.03 * (T_furnace - 360)
T_residue  = T_furnace - 5
```

Pressures (small variation around setpoint):
```
P_tower_top = 1.5 + 0.001 * (F_in - 400000)/1000   # barg
P_E101_in   = 8.0 + 0.002 * (F_in - 400000)/1000   # barg
```

Product property — diesel T95 (used for LIMS):
```
diesel_T95 = 355 + 0.15 * (T_diesel - 280) - 5 * ΔAPI    # °C
```
Diesel sulfur:
```
diesel_sulfur_pct = 0.04 + 0.02 * max(0, ΔAPI_sulfur)    # wt%
# where ΔAPI_sulfur is the sulfur perturbation, default 0
```

### 4.3 Implementation requirement

The physics module must expose a **single function** with this signature:

```python
def simulate(inputs: PhysicsInputs) -> PhysicsOutputs: ...
```

Where `PhysicsInputs` and `PhysicsOutputs` are Pydantic models defined in `rsd.schemas`. This is the seam where DWSIM or IDAES will later be swapped in. **Do not allow physics calculations to leak into other modules.**

---

## 5. Module-by-module build sequence

Build modules in this order. After each module, run its acceptance tests before moving on. Do not start module N+1 until module N's tests pass.

### Module 1: Repository scaffold

**Inputs:** None.

**Outputs:**
- Repository structure as in §6.
- `pyproject.toml` with dependencies: `numpy`, `pandas`, `pyarrow`, `pydantic`, `pyyaml`, `scipy`, `click`, plus dev deps `pytest`, `ruff`, `mypy`, `hypothesis`.
- `pyproject.toml` configures `ruff` (line length 100, target Python 3.11+) and `mypy` (strict mode on `src/`).
- `.gitignore` excluding `output/`, `__pycache__/`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`.
- A `README.md` stub with installation and quickstart placeholders.
- All `config/*.yaml` files copied from the brief (provided as starter files).

**Done when:**
- `pip install -e ".[dev]"` succeeds in a fresh venv.
- `pytest` runs and reports zero tests (no failures).
- `ruff check src/` passes.

### Module 2: Schemas and config loading

**Inputs:** Config YAMLs.

**Outputs:** `src/rsd/schemas.py` containing Pydantic models:

- `AssetHierarchy` — site, units, equipment with `functional_location` strings.
- `TagDefinition` — name, dwsim_path (placeholder string for later), units, span (min, max), noise_pct, lag_seconds, drift_per_day, compression_deadband_pct.
- `LabTest` — method, property, stream, units, uncertainty_std, frequency_hours.
- `FaultScenario` — id, type (literal: `exchanger_fouling` only for v1), target, start (datetime), duration_days, profile (literal: `linear`), severity_final.
- `BaseOperation` — feed_rate distribution params, feed_temp distribution params, ambient diurnal amplitude.
- `PipelineConfig` — top-level config that references the others by file path.
- `PhysicsInputs`, `PhysicsOutputs` — see §4.

Plus `src/rsd/config.py` with a single function `load_config(path: Path) -> PipelineConfig` that loads, validates, and returns the full config tree.

**Done when:**
- `tests/test_config.py` loads `config/default.yaml` and asserts all expected fields are present and correctly typed.
- An invalid config (e.g., negative noise_pct) raises a Pydantic ValidationError with a useful message.
- Type checks pass under `mypy --strict`.

### Module 3: Scenario generator

**Inputs:** `BaseOperation`, list of `FaultScenario`, start, end, freq.

**Outputs:** `src/rsd/scenario.py` containing `ScenarioGenerator` class.

**Behavior:**
- Produces a pandas DataFrame indexed by 5-minute timestamps from start to end.
- Columns: `feed_rate_kg_h`, `feed_temp_c`, `furnace_target_c`, `fouling_E101`, `api_delta`, `active_fault` (str), plus all fault-state columns even when zero.
- `feed_rate_kg_h` ~ Normal(400000, 8000), seeded.
- `feed_temp_c` ~ Normal(25, 5) plus diurnal sinusoid of amplitude 3°C peaking at 14:00.
- `furnace_target_c` constant at 360 (operator setpoint).
- For the configured fouling scenario, `fouling_E101` ramps linearly from 0 to `severity_final` over the fault window; `active_fault` set to scenario id during the window, "NONE" otherwise.
- All randomness uses `numpy.random.default_rng(seed)` from config.

**Done when:**
- `tests/test_scenario.py` checks: correct number of rows, value ranges within expected, fault flag set on exactly the right rows, deterministic given seed.
- Property test (Hypothesis) — for any valid date range and seed, output has no NaN and monotonic timestamps.

### Module 4: Mock physics

**Inputs:** `PhysicsInputs` (a single timestep).

**Outputs:** `src/rsd/physics.py` with a `simulate(inputs)` function and a `simulate_batch(df)` convenience function.

**Behavior:**
- Implements equations from §4 exactly.
- Pure function — no I/O, no global state.
- Vectorized batch version for performance (single pass over a DataFrame should handle ~100k rows in well under a second).

**Done when:**
- `tests/test_physics.py` checks numerical correctness against hand-computed values for several specific input combinations (one normal, one fouled, one off-spec feed).
- Batch version produces identical results to looping single-step calls.
- Fouling causes `fuel_gas_flow` to monotonically increase as expected (regression test).

### Module 5: Realism layer (PI writer)

**Inputs:** Clean physics DataFrame at 5-min cadence + `TagDefinition` list.

**Outputs:** `src/rsd/realism.py` containing `RealismLayer` class with `apply(clean_df, target_freq) -> noisy_df`.

**Behavior:**
- Resamples 5-min → target frequency (default 1-min) via cubic interpolation on numeric columns.
- For each tag in the config:
  1. Map physics output column to tag (via `dwsim_path` field, repurposed as physics output name for now).
  2. First-order lag filter using `tag.lag_seconds`.
  3. Slow drift via random walk scaled by `drift_per_day`.
  4. Gaussian noise with σ = `tag.noise_pct/100 * span`.
  5. Quantize to 12-bit DCS resolution: `round(value / (span/4096)) * (span/4096)`.
  6. Inject gaps (NaN) with low probability (~0.0001 per sample, 5–30 minute gap length).
  7. Apply swinging-door compression: drop samples within `compression_deadband_pct` of last recorded value, forward-fill for the dense view.
- Output DataFrame: timestamp index, one column per tag (named by `tag.name`).

**Done when:**
- `tests/test_realism.py`: noise std matches configured value within statistical tolerance, lag introduces expected phase delay, gaps appear at expected rate, compression reduces unique values for low-deadband tags.
- Determinism: same seed → identical output.

### Module 6: LIMS writer

**Inputs:** Clean physics DataFrame + `LabTest` definitions.

**Outputs:** `src/rsd/lims.py` containing `LIMSWriter` class with `generate(clean_df) -> records_df`.

**Behavior:**
- For each lab test, sample at the configured frequency (e.g., every 8 hours).
- 2% chance of missed sample (record skipped entirely).
- Measured value = true value + Normal(0, `test.uncertainty_std`).
- Each record has: `sample_id`, `functional_location`, `stream`, `test_method`, `property`, `value`, `units`, `sample_time`, `report_time` (sample_time + 4h delay), `true_value` (for ground truth alignment).
- Output as long-format DataFrame.

**Done when:**
- `tests/test_lims.py`: correct record count, sample times aligned to frequency, report time always after sample time, measurement error distribution matches configured uncertainty.

### Module 7: Ground truth writer

**Inputs:** Scenario DataFrame, clean physics DataFrame.

**Outputs:** `src/rsd/ground_truth.py` containing `GroundTruthWriter`.

**Behavior:**
- Writes two Parquet files:
  - `labels.parquet` — timestamp, active_fault, fouling_E101, all fault state columns from scenario.
  - `true_values.parquet` — timestamp, all clean physics columns (the noise-free signals corresponding to PI tags).

**Done when:**
- `tests/test_ground_truth.py`: schema matches spec, joinable to noisy outputs on timestamp.

### Module 8: Orchestrator and CLI

**Inputs:** Config path, date range, output path.

**Outputs:** `src/rsd/generate.py` with `click`-based CLI.

**Behavior:**
- Loads config.
- Builds scenario timeline.
- Calls physics in batch.
- Calls realism layer (PI), LIMS writer, ground truth writer.
- Writes Parquet partitioned by month for time-series outputs:
  - `output/pi/year=YYYY/month=MM/data.parquet`
  - `output/lims/lab_records.parquet` (single file, sparse)
  - `output/ground_truth/labels.parquet`
  - `output/ground_truth/true_values.parquet`
  - `output/metadata/run_info.json` — config snapshot, seed, version, runtime stats, git SHA if available.
- Logs progress to stdout (one line per month processed).
- Idempotent — re-running with same config + seed produces identical output (overwrite mode).

**Done when:**
- `python -m rsd.generate --config config/default.yaml --start 2025-01-01 --end 2025-12-31 --output ./output --seed 42` completes successfully.
- Output structure matches §6.
- Re-running produces byte-identical Parquet files (or hash-equal DataFrame contents — Parquet metadata may differ).

### Module 9: Acceptance tests

**Outputs:** `tests/acceptance/` containing end-to-end tests:

- `test_full_pipeline.py` — runs a 1-month pipeline, asserts all expected files exist with non-zero rows.
- `test_fault_recoverable.py` — runs a 3-month pipeline with fouling fault in month 2, fits a simple linear regression of `fuel_gas_flow` vs time within and outside the fault window, asserts the slope difference is significant.
- `test_determinism.py` — runs the pipeline twice with the same seed, asserts data equality.
- `test_schemas.py` — loads each output Parquet, validates against expected Pandera or Pydantic schema.

**Done when:** All acceptance tests pass.

### Module 10: Example consumer script

**Outputs:** `examples/detect_fault.py` — a standalone script that reads the generated PI data, computes a 7-day rolling mean of `fuel_gas_flow`, flags windows where the rolling mean exceeds baseline + 3σ, and reports the detected fault window. Print-only, no plotting libraries required.

**Done when:** Running `python examples/detect_fault.py ./output` correctly identifies the fouling window within ±2 days of the configured fault start/end.

### Module 11: Documentation

**Outputs:**
- `README.md` with: overview, install instructions, quickstart command, output structure, architecture diagram (ASCII art is fine), how to extend (pointing to the physics seam), troubleshooting.
- Docstrings on all public classes and functions following Google or NumPy style.
- `ARCHITECTURE.md` summarizing the design principles from §2 of this brief.

**Done when:** README quickstart works for a new user starting from a fresh clone.

---

## 6. Repository structure

```
rsd/
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
├── .gitignore
├── config/
│   ├── default.yaml              # top-level: references the others
│   ├── asset_hierarchy.yaml
│   ├── tags.yaml
│   ├── lab_panel.yaml
│   └── scenarios.yaml
├── src/
│   └── rsd/
│       ├── __init__.py
│       ├── schemas.py            # Pydantic models
│       ├── config.py             # config loader
│       ├── scenario.py           # Module 3
│       ├── physics.py            # Module 4 (mock CDU)
│       ├── realism.py            # Module 5 (PI realism layer)
│       ├── lims.py               # Module 6
│       ├── ground_truth.py       # Module 7
│       └── generate.py           # Module 8 (CLI entrypoint)
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_scenario.py
│   ├── test_physics.py
│   ├── test_realism.py
│   ├── test_lims.py
│   ├── test_ground_truth.py
│   └── acceptance/
│       ├── __init__.py
│       ├── test_full_pipeline.py
│       ├── test_fault_recoverable.py
│       ├── test_determinism.py
│       └── test_schemas.py
├── examples/
│   └── detect_fault.py
└── output/                       # gitignored
    ├── pi/
    │   └── year=YYYY/month=MM/data.parquet
    ├── lims/
    │   └── lab_records.parquet
    ├── ground_truth/
    │   ├── labels.parquet
    │   └── true_values.parquet
    └── metadata/
        └── run_info.json
```

---

## 7. Coding standards

- **Python 3.11+** features encouraged (type unions with `|`, `match` statements where clearer).
- **Type hints everywhere.** `mypy --strict` must pass on `src/`.
- **Pydantic v2** for all schemas.
- **No bare `except:`** — catch specific exceptions.
- **No global state.** Pass dependencies as arguments.
- **Docstrings on all public functions and classes.** NumPy or Google style, consistent throughout.
- **Function length:** prefer functions under 50 lines. Split when longer.
- **Test names describe behavior:** `test_fouling_increases_fuel_gas_flow`, not `test_physics_1`.
- **One assertion per test** where reasonable — multiple assertions are fine when they all check one logical property.
- **No commented-out code.** Delete or commit; don't leave dead code.

---

## 8. Working agreement (instructions for the builder)

You are building this in modules. After completing each module:

1. **Run the module's tests.** Do not move forward if any test fails.
2. **Run `ruff check` and `ruff format` on the changed files.**
3. **Run `mypy src/`** and resolve any type errors.
4. **Make a commit** with a clear message naming the module (e.g., `feat(scenario): implement scenario generator (module 3)`).
5. **Report progress** in a checkpoint summary: what was built, what was tested, what's next.

If you encounter ambiguity that can't be resolved from this brief and the config files, **stop and ask** rather than guess. The brief is intentionally specific; if it seems vague on a point, that point may need clarification.

If a module's spec turns out to be wrong or unworkable as you build, raise the issue, propose a fix, and wait for confirmation before deviating.

Resist the urge to add features not in the brief. The non-goals list in §1.4 is binding. Architectural elegance matters less than completing the specified scope cleanly.

---

## 9. Definition of done (whole project)

The project is complete when:

```bash
# In a fresh clone:
git clone <repo> rsd
cd rsd
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the pipeline
python -m rsd.generate \
    --config config/default.yaml \
    --start 2025-01-01 \
    --end 2025-12-31 \
    --output ./output \
    --seed 42

# Verify
pytest tests/                 # all green
ruff check src/ tests/        # no issues
mypy src/                     # no issues
python examples/detect_fault.py ./output    # correctly identifies fault window
```

…all complete successfully on a clean machine.
