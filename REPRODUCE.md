# OLIVE Reproduction Guide

This document describes how to reproduce key results from the OLIVE paper using the released code and data.

## Reference Values

**US1 Canonical Simulation (participants 5, 20; steps=90, num-trials=5)**

| Model Variant | Metric | Rate | Time (s) | 
|---|---|---|---|
| IE | Belief convergence | 0.79 | 37 | 
| IE | Guidance convergence | 0.97 | 28 | 
| E | Belief convergence | 0.71 | 53 | 
| E | Guidance convergence | 0.79 | 37 | 

## US1 Simulation + Convergence Reproduction

### Overview

The US1 reproduction involves two main steps:

1. **US1 Simulation** (`release/reproduce/us1.py`): Run the OLIVE wingman simulation across participants and model variants, generating per-second and per-block metrics.
2. **Convergence Analysis** (`release/reproduce/us1_convergence.py`): Compute per-variant belief/guidance convergence rates and times from the simulation output.

### Prerequisites

Ensure the OLIVE server is running:
```bash
python -m release.olive.server --port 50055
```

### Step 1: US1 Simulation

```bash
python -m release.reproduce.us1 \
    --participants 5 20 \
    --steps 90 \
    --num-trials 5 \
    --addr localhost:50055 \
    --output-dir outputs/us1_master_csvs
```

**Output:**
- `outputs/us1_master_csvs/secondStats.csv`: Per-second metrics with EMA smoothing
- `outputs/us1_master_csvs/blockStats.csv`: Per-block aggregate metrics

**Flags:**
- `--participants`: List of participant IDs to run (space-separated)
- `--steps`: Duration in seconds per block (default: 90)
- `--num-trials`: Number of trials per participant × variant (default: 5)
- `--addr`: gRPC server address (default: localhost:50055)
- `--output-dir`: Output directory for CSVs (default: outputs/us1_master_csvs)

### Step 2: Convergence Analysis

```bash
python -m release.reproduce.us1_convergence \
    outputs/us1_master_csvs/secondStats.csv \
    --output-csv release/reproduce/out/us1_convergence.csv
```

**Output:**
- `release/reproduce/out/us1_convergence.csv`: Convergence rate and time statistics per variant

**Expected output** (should match or exceed reference rates):
```
Variant  Metric                Rate    Time (s)
IE       Belief convergence   0.79    37
IE       Guidance convergence 0.97    28
E        Belief convergence   0.71    53
E        Guidance convergence 0.79    37
```

---

## US2 Live-Deployment Convergence (Table 2) Reproduction

This reproduces the US2 convergence column from logged posteriors in `~/wingman`.

```bash
python -m release.reproduce.table2_us2
```

**Note:** unlike the US1 reproduction above, this invokes an analysis script
from the main OLIVE research repo (`analysis/repro/new_run/us2_vs_us1_convergence.py`),
which is not vendored in this release and must be present on disk at that
path relative to the repo root. See the Requirements section of
`release/README.md`.

**What it does:**
- Loads `wingman_infer_frames_*.jsonl` from `~/wingman/P{pid}/us2/` (IE: 14 nominal; E: 13 nominal)
- Computes per-block convergence times (belief and guidance) via score_std and top4_stability criteria
- Computes per-condition convergence rates and mean times
- Compares US2 results to US1 reference values
- Prints per-condition convergence rate/time comparison table
- Saves block-level and summary CSVs, and camera-ready SVG figure

**Results:** Reproduces the camera-ready Table 2 US2 convergence cells; running it end-to-end should match the published Table 2 values.

---

## US3 Silent-Switch Reconvergence (Table 6) Reproduction

This reproduces the US3 post-switch reconvergence from logged posteriors in `~/wingman`.

```bash
python -m release.reproduce.table6_us3
```

**Note:** like the Table 2 reproduction above, this invokes an analysis
script from the main OLIVE research repo (`analysis/repro/table5_reconv_drop.py`),
which is not vendored in this release and must be present on disk at that
path relative to the repo root. See the Requirements section of
`release/README.md`.

**What it does:**
- Loads `wingman_infer_frames*.jsonl` from `~/wingman/P{pid}/us3/` (E: 13 nominal; IE: 14 nominal)
- Drops participants P18, P39 by default (`DEFAULT_DROP` in `table6_us3.py`, single-sourced from `release.common.cohort.US3_DROP`)
- Computes per-block post-switch reconvergence times (guidance and belief)
- Computes reconvergence rates and mean times by condition
- Prints condition (E vs IE) Welch t-tests
- Saves block-level and summary CSVs

**Results:** Reproduces the camera-ready Table 6 US3 reconvergence cells; running it end-to-end should match the published Table 6 values.

---

## Partial-Cohort Live OLIVE Re-run (Validation)

This runs a partial-cohort, best-effort validation of OLIVE live replay across a subset of usable subjects (14/15 subjects depending on study; see `USABLE_US2`/`USABLE_US3` in `rerun_live_subset.py`). This is an optional validation step, not required to reproduce any paper table; full live validation requires the complete wingman data infrastructure and a running OLIVE gRPC server.

```bash
python release/reproduce/rerun_live_subset.py --study us2 --wingman-addr 127.0.0.1:50055
python release/reproduce/rerun_live_subset.py --study us3 --wingman-addr 127.0.0.1:50055
```

**What it does:**
For each subject in the allowlist:
- Loads the subject's EEG decoder quality (AUC) from `eeg_priors/{pid}/us1/eeg_pred_beta.json`
- Runs partial-cohort validation with that subject's decoder quality
- Demonstrates how per-subject decoder quality differences manifest in replay convergence behavior

**Results:** This has not been run as part of this release's validation and no output is recorded here. It is best-effort, partial-cohort validation (NOT bit-exact reproduction), and running the full allowlist may be slow / long-running.

---

## Technical Notes

### Convergence Criteria

Convergence is defined as meeting **both** conditions for ≥10 consecutive seconds:
- **Belief**: AUC > 0.90 AND top4_stability ≥ 0.75
- **Guidance**: precision@4 ≥ 1.0 AND top4_stability ≥ 0.75

### EEG Priors

- EEG priors are auto-detected from `eeg_priors/{pid}/us1/eeg_pred_beta.json` (one prior per subject)
- For the E (Explicit-only) variant, EEG priors are not required

### Server Requirements

- The US1 simulation requires a running gRPC server at the specified address
- US2/US3 reproduction runs against already-logged posteriors in `~/wingman` (no OLIVE server needed)

### Hyperparameter Tuning

To tune OLIVE's EM hyperparameters for faster/higher convergence:
1. Modify prompt learning rate, prevalence anchor, or EMA coefficient in `release/olive/server.py`
2. Re-run US1 simulation (Step 1 above)
3. Re-run convergence analysis (Step 2 above)
4. Compare new rates/times to reference values above
