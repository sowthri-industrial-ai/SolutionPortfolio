# About the files in this repository

This document is a guide to every file and folder in the `phase1-cdu-prototype` repository. New contributors should read it after the README to understand the layout before diving into code.

## Top-level documentation

| File | Purpose |
|---|---|
| `README.md` | Front door of the project. Overview, install, quickstart, output structure, troubleshooting. The first thing anyone reads. Rendered automatically on the GitHub project page. |
| `USER_MANUAL.md` | Comprehensive how-to for end users. Covers the three primary usage patterns (generate datasets, read data into Python, run the example detector), CLI options, common workflows, and troubleshooting. Written for technical users who know Python and the terminal. |
| `ARCHITECTURE.md` | Design principles and layer-by-layer module map. Read this if you intend to extend or modify the system. Captures the architectural choices that the brief locked in. |
| `ABOUT_FILES.md` | This document. Repository orientation. |

## Project configuration files

| File | Purpose |
|---|---|
| `pyproject.toml` | Python project metadata. Declares the package name, dependencies (numpy, pandas, pyarrow, pydantic, pyyaml, scipy, click), dev dependencies (pytest, ruff, mypy, hypothesis), and tool configuration for ruff, mypy, and pytest. The single source of truth for "what does this project depend on." |
| `.gitignore` | Tells git which files to ignore. Excludes build artifacts (`output/`), virtual environments (`.venv/`), Python caches (`__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`), and Claude Code local settings (`.claude/settings.local.json`). |

## Configuration as data — the `config/` directory

Every tunable parameter of the synthetic data pipeline lives here as YAML. Code is generic and reads behavior from these files. Adding a new tag, lab test, or fault scenario is a config change, not a code change.

| File | Purpose |
|---|---|
| `config/default.yaml` | Top-level pipeline configuration. Sets the default seed, simulation frequency, PI output frequency, LIMS report delay, and base operating conditions (feed rate, feed temp, furnace target). References the four sibling YAML files below. |
| `config/asset_hierarchy.yaml` | Defines the simulated refinery's physical structure: site, units, equipment, and streams, with functional locations like `SITE01.CDU1.E-101`. Every record in every output references this hierarchy as the join key. |
| `config/tags.yaml` | Defines the 18 PI tags. Each tag specifies its physics output (which physics column it maps to), its functional location, units, span, noise percentage, lag time constant, drift rate, and compression deadband. |
| `config/lab_panel.yaml` | Defines the LIMS test panel: which ASTM tests run on which streams, at what frequency, with what measurement uncertainty. Currently four tests covering diesel T95, diesel sulfur, kero T95, and naphtha density. |
| `config/scenarios.yaml` | Defines the fault scenarios injected into the dataset. Phase 1 has one: a linear exchanger fouling event on E-101 from 2025-04-15 to 2025-06-14, ramping to 40% UA reduction. |

## Source code — the `src/rsd/` directory

The Python package itself. Each file is one of the layers from `ARCHITECTURE.md`.

| File | Purpose |
|---|---|
| `src/rsd/__init__.py` | Package marker. Empty by design; exists so Python recognizes `src/rsd/` as an importable package. |
| `src/rsd/schemas.py` | Pydantic v2 models for every configuration object: `AssetHierarchy`, `TagDefinition`, `LabTest`, `FaultScenario`, `BaseOperation`, `PipelineConfig`. Also defines `PhysicsInputs` and `PhysicsOutputs` — the seam through which DWSIM/IDAES will plug in later. All models are frozen with `extra="forbid"` so a typo in YAML fails fast. |
| `src/rsd/config.py` | Configuration loader. Single function `load_config(path)` reads the top-level YAML, follows references to sibling YAML files, validates the combined structure via Pydantic, and returns a single typed `PipelineConfig`. Resolves sibling paths relative to the loaded YAML's parent directory so the CLI works from any working directory. |
| `src/rsd/scenario.py` | Scenario timeline generator. `ScenarioGenerator` produces a 5-minute-indexed DataFrame of inputs over the requested date range: feed rate, feed temperature with diurnal variation, furnace setpoint, and per-fault state columns. Linear ramp from zero to severity over each fault window. Seeded for determinism. |
| `src/rsd/physics.py` | Mock CDU physics. `simulate(PhysicsInputs) -> PhysicsOutputs` is the stable interface for later DWSIM/IDAES replacement. Implements the equations from the brief's §4.2: NTU effectiveness for the preheat exchanger, energy balance for the furnace, parametric yield model for the tower, plus product-property correlations (diesel T95, sulfur, kero T95, naphtha density). Vectorized batch version processes 100k rows in well under a second. |
| `src/rsd/realism.py` | The PI realism layer. `RealismLayer.apply(clean_df, target_freq)` takes 5-minute clean physics output and produces 1-minute realistic PI tag streams. Per tag, applies in order: cubic interpolation, first-order sensor lag (scipy.signal.lfilter), random-walk drift, Gaussian noise, 12-bit DCS quantization, NaN gap injection, and swinging-door deadband compression. Deterministic given seed. |
| `src/rsd/lims.py` | The LIMS writer. `LIMSWriter.generate(clean_df)` walks each lab test at its configured frequency, looks up the true value via nearest-neighbor reindex, drops 2% as missed samples, adds Normal(0, uncertainty_std) measurement noise, and emits long-format records with both `sample_time` and `report_time` (sample_time plus the configured report delay). |
| `src/rsd/ground_truth.py` | The ground truth writer. `GroundTruthWriter` exposes pure builders (`build_labels`, `build_true_values`) and a side-effecting `write` that emits `labels.parquet` (active fault and fault-state columns) and `true_values.parquet` (the noise-free physics signals). Joinable to noisy outputs on timestamp. |
| `src/rsd/generate.py` | The CLI entry point and end-to-end orchestrator. Reads config, builds the scenario timeline, runs physics in batch, calls the realism layer (PI), the LIMS writer, the ground truth writer, partitions the PI output by month, writes the run metadata JSON. Side effects (directory creation, Parquet writes, JSON snapshot) are confined to this module. |

## Tests — the `tests/` directory

Every module has a paired test file. The acceptance subdirectory holds end-to-end tests that exercise the whole pipeline.

| File | What it tests |
|---|---|
| `tests/test_config.py` | Configuration loading: valid configs load successfully, invalid configs raise Pydantic ValidationErrors with helpful messages. |
| `tests/test_scenario.py` | Scenario generator: row counts, value ranges, diurnal pattern, fault ramp linearity, determinism. Includes a Hypothesis property test. |
| `tests/test_physics.py` | Mock physics: hand-calculated values match the simulator output, batch-vs-single-step equivalence, fouling monotonicity, performance gate. |
| `tests/test_realism.py` | Realism layer: empirical noise std matches configured value, lag introduces expected phase delay, gap rate matches configured rate, compression collapses values. Includes integration through scenario + physics + realism. |
| `tests/test_lims.py` | LIMS writer: record count statistics, sample time alignment, report-after-sample invariant, error distribution, schema completeness, miss rate, determinism. |
| `tests/test_ground_truth.py` | Ground truth writer: schema correctness, write produces both files, Parquet round-trip equality (with `check_freq=False` since DatetimeIndex.freq is dropped by Parquet), joinability with PI output. |
| `tests/test_generate.py` | Module-level orchestrator tests: CLI flag handling, output directory creation, run_info.json content. |
| `tests/test_detect_fault.py` | Tests for the example fault detector: detected start within ±2 days, detected end within ±9 days (rolling-window edge smearing), CLI subprocess executes successfully. |
| `tests/acceptance/test_full_pipeline.py` | End-to-end smoke test: 1-month run produces all expected files with non-zero rows. |
| `tests/acceptance/test_fault_recoverable.py` | The proof point: 3-month run with fouling fault, statistical regression of fuel gas flow recovers the injected fault with 5-sigma confidence. |
| `tests/acceptance/test_determinism.py` | Two runs with the same seed produce content-equal DataFrames. |
| `tests/acceptance/test_schemas.py` | Output Parquet files conform to expected schemas (column sets, dtypes, sample-id uniqueness, sample-time before report-time). |

## Examples — the `examples/` directory

| File | Purpose |
|---|---|
| `examples/detect_fault.py` | Standalone CLI that demonstrates the dataset is genuinely useful: reads every PI partition, computes a centered 7-day rolling mean of fuel gas flow, identifies the fouling event by thresholding the rolling mean against a baseline plus 3-sigma. Print-only output, no plotting libraries. The proof point that justifies the entire Phase 1 build. |

## Runtime artifacts (not in version control)

These appear when you run the pipeline. They are excluded from git via `.gitignore`.

| Path | Purpose |
|---|---|
| `output/` | Generated synthetic data. Recreated each time you run `python -m rsd.generate`. Contains PI Parquet partitions by month, LIMS records, ground truth, and run metadata. Reproducible from config and seed, so safe to delete and regenerate. |
| `.venv/` | Python virtual environment with project dependencies. Created by `python -m venv .venv`. Local to your machine; do not commit. |
| `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | Python tool caches. Speeds up repeat runs. Safe to delete; tools regenerate them. |

## How to navigate when you want to do X

| If you want to... | Read or edit |
|---|---|
| Use the system to generate a dataset | `USER_MANUAL.md` |
| Understand the project at a glance | `README.md` |
| Understand the design and architecture | `ARCHITECTURE.md` |
| Tune feed rate, fault timing, or noise levels | `config/*.yaml` |
| Add a new fault type | `config/scenarios.yaml` plus `src/rsd/physics.py` plus `src/rsd/scenario.py` |
| Add a new PI tag | `config/tags.yaml` (no code change needed if it maps to an existing physics output) |
| Add a new lab test | `config/lab_panel.yaml` (and add the physics output to `src/rsd/physics.py` if needed) |
| Replace mock physics with DWSIM or IDAES | `src/rsd/physics.py` (only the body of `simulate()` changes) |
| See how something is tested | `tests/test_<module>.py` |
| Run the proof point | `python examples/detect_fault.py ./output` |

---

*This document is part of the Phase 1 documentation set. For Phase 2 and beyond, this file should be updated to reflect new modules, new data sources, and new fault scenarios as they are added.*
