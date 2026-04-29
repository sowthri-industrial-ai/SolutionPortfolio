# Architecture

This document summarizes the design principles behind RSD. They apply to
every module and are non-negotiable: changes that compromise them should be
rejected even if they make individual modules simpler.

## Separation of physics from realism

The mock physics module (`rsd.physics`) produces clean, deterministic outputs
given inputs — no noise, no quantization, no gaps. The realism layer
(`rsd.realism`) adds every sensor artifact that distinguishes a real PI tag
from clean physics. They never share responsibilities. When the physics is
later replaced with DWSIM or IDAES, the realism module continues to work
unchanged.

The seam is the `simulate(inputs: PhysicsInputs) -> PhysicsOutputs` function
signature defined in `rsd.schemas`. Pydantic validates inputs and outputs at
the boundary; everything above and below the seam can evolve independently.

## Single event timeline

All data sources subscribe to one canonical timeline produced by
`ScenarioGenerator`. Cross-source consistency — e.g. a fouling fault visible
in both PI tags and LIMS lab samples — emerges from this shared source of
truth, not from per-source coordination.

The scenario DataFrame carries process inputs, fault-state columns, and an
`active_fault` string column. Physics consumes the inputs; the realism layer
and LIMS writer consume the resulting clean physics; the ground-truth writer
consumes the scenario directly. None of those modules talk to each other.

## Asset hierarchy as join key

Every record carries a functional location string (e.g.
`SITE01.CDU1.E-101`). Joins across sources happen on this key. The asset
hierarchy is loaded from YAML at startup and is read-only at runtime.

## Ground truth alongside noisy data

For every noisy output, the corresponding noise-free physics value and the
active fault flags are written to a separate `ground_truth/` directory. This
is what makes the dataset evaluable: a model trained on noisy PI data can be
scored against the physics column it was meant to estimate, and a fault
detector can be scored against the ground-truth label.

## Configuration over code

Tag definitions, lab panels, fault scenarios, and the asset hierarchy live in
YAML files under `config/`. Adding a new tag, a new lab test, or a new fault
scenario requires no code changes — the realism, LIMS, and scenario modules
read config and act on it generically.

## Determinism via seeded RNG

Every stochastic component takes a seed. The orchestrator threads a single
`effective_seed` (from `--seed` or `config.seed`) through `ScenarioGenerator`,
`RealismLayer`, and `LIMSWriter`. Each builds one `numpy.random.default_rng`
and consumes draws in a fixed order. Running the pipeline twice with the
same config and seed produces byte-identical content (Parquet metadata such
as creation time may differ; DataFrame contents are equal).

## Pure functions where possible

Generators and the physics layer take inputs and return outputs with no
hidden state. Side effects — directory creation, Parquet writes, JSON
snapshots — are confined to `rsd.generate.run_pipeline`. This keeps the
units cheap to test and easy to recompose.

## Module map

```
rsd.config         -> load_config(path) -> PipelineConfig
rsd.scenario       -> ScenarioGenerator.generate(...) -> DataFrame
rsd.physics        -> simulate(inputs); simulate_batch(df) -> DataFrame
rsd.realism        -> RealismLayer.apply(clean_df, freq) -> DataFrame
rsd.lims           -> LIMSWriter.generate(clean_df) -> DataFrame
rsd.ground_truth   -> GroundTruthWriter.write(scen, clean, dir) -> (Path, Path)
rsd.generate       -> run_pipeline(...) [the only side-effect site]
```

Every module is exercised by a focused test file under `tests/`, and the
end-to-end behavior is locked down by the suite under `tests/acceptance/`.
