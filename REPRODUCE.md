# OLIVE Reproduction Guide

This document describes how to reproduce key results from the OLIVE paper using the released code and data.

## What "reproduce" means for each result

Reproduction is not the same mechanism for every result in the paper:

- **US1** (the canonical simulation, and the US1 reference row in Table 2) is reproduced
  by actually re-running the OLIVE server: see [US1 Simulation + Convergence
  Reproduction](#us1-simulation--convergence-reproduction) below. Online-EM itself is
  deterministic by design (seeded), but the server gates EM rounds on wall-clock time
  rather than a seeded step counter, so a re-run is reproducible **up to EM-timing
  jitter**, not bit-exact-guaranteed: expect convergence rates/times close to, but not
  necessarily identical to, the reference values.
- **US2 and US3** (Tables 2-8, Figure 6) are reproduced by *analysis over the
  live-logged posteriors and blockStats* already sitting in `~/wingman`; none of these
  wrappers re-run OLIVE. All of Tables 2-8 and Figure 6 now reproduce exactly this way
  via `release/reproduce/reproduce_all.py`; see the Reproduction Matrix below for the
  disclosed per-table cohort/drop list.
- The dataset's per-fixation `p_target` field (see `release/dataset/CARD.md`) is a
  *regenerated* implicit-evidence signal shipped for **auditability and decoder-swap
  experiments**. It is not the literal value OLIVE used live during data collection, and
  it is not the mechanism behind any paper table; none of Tables 2-8 or Figure 6 are
  produced by replaying `p_target`.

## Reproduce Everything: `reproduce_all`

`release/reproduce/reproduce_all.py` is the single entrypoint that runs every Table 2-8 + Figure 6
wrapper, captures each wrapper's key reproduced cells from stdout, checks them against the paper's
camera-ready values (hardcoded in `PAPER_EXPECTED`, sourced from `paper/proceedings.tex`), and prints
a PASS/FAIL summary. US1 requires a running OLIVE gRPC server and is skipped unless `--with-us1` is
passed.

```bash
# Tables 2-8 + Figure 6 only (no server needed)
python -m release.reproduce.reproduce_all

# Also attempt US1 (requires: python -m release.olive.server --port 50055)
python -m release.reproduce.reproduce_all --with-us1 --addr localhost:50055
```

A wrapper that errors because a required `analysis/repro/*.py` generator or cohort CSV is not
vendored in this release checkout is reported as `SKIP` with the reason, not a crash. Confirmed run
on this checkout (with `~/wingman` data present, no server): **8/8 PASS** (Tables 2-8 + Figure 6);
US1 `SKIP` (no `--with-us1`).

## Reproduction Matrix (Tables 2-8 + Figure 6)

| Target | Paper cells | Wrapper command | Cohort / drop list | Status |
|---|---|---|---|---|
| **Table 2** (US2 vs US1 convergence) | IE guidance 99.4%/74.5s, belief 84.6%/65.3s; E guidance 97.1%/76.2s, belief 82.9%/63.0s | `python -m release.reproduce.table2_us2` | Full US2 cohort (IE: 14 nominal, E: 13 nominal); no drops | PASS |
| **Table 3** (US2 within-session throughput delta) | Control Δ=+.014, p=.091; OLIVE-E Δ=+.021, p=.094; OLIVE-IE Δ=+.031, p=.003; Oracle Δ=+.024, p=.105 | `python -m release.reproduce.table3_us2` | `us2_blockStats_set4.csv` for condition map (n=13/10/13/8 in CSV); paper prints n=12/10/12/8 from set3, a disclosed labeling difference (see wrapper docstring); no participant drops | PASS |
| **Table 4** (US2 skill moderation) | Control r=+.25 p=.43; OLIVE-E r=−.63 p=.05; OLIVE-IE r=−.02 p=.95; Oracle r=+.06 p=.90 | `python -m release.reproduce.table4_us2` | `us2_blockStats_set3.csv`; n=12/10/12/8; no drops | PASS |
| **Table 5** (post-block trust/reliance ratings) | US2 OLIVE-E 3.89/2.99/4.62; OLIVE-IE 3.95/3.90/4.64; Oracle 4.80/4.35/5.07. US3 OLIVE-E 3.91/3.44/4.62; OLIVE-IE 4.57/4.23/5.06; Oracle 4.76/4.64/4.82 (Trust/Look/Shoot) | `python -m release.reproduce.table5_ratings` | `us2_blockStats_set3.csv` + `us3_blockStats_set3.csv`; drop {18, 39} | PASS |
| **Table 6** (US3 post-switch reconvergence) | OLIVE-E 100%/68.5±3.8s, 37%/30.7±5.6s; OLIVE-IE 100%/53.8±4.1s, 56%/25.1±4.0s; IE-vs-E guidance t=−2.67, p=.008; belief t=−0.81, p=.418 (n=10/10) | `python -m release.reproduce.table6_us3` | `TABLE6_DROP = {52, 54, 55, 63}` (Table 6's own disclosed cohort, decoupled from `release.common.cohort.US3_DROP` = {18, 39}; the old {18, 39} default reproduced a different, non-paper p-value of .046, see wrapper docstring) | PASS |
| **Table 7** (US3 new-target throughput delta) | Control Δ=+.024, p=.061; OLIVE-E Δ=+.034, p=.052; OLIVE-IE Δ=+.070, p=.001; Oracle Δ=+.046, p=.012 | `python -m release.reproduce.table7_us3` | `us3_blockStats_set3.csv`, filtered by per-condition `TABLE7_DROPS`: Control {62, 65, 25}, OLIVE-E {29, 52}, OLIVE-IE {37, 39, 46, 55}, Oracle {15, 60, 38, 41} | PASS |
| **Table 8** (US3 skill moderation) | Control r=+.68 p=.01; OLIVE-E r=−.11 p=.73; OLIVE-IE r=−.24 p=.57; Oracle r=+.42 p=.30 | `python -m release.reproduce.table8_us3` | `us3_blockStats_set3.csv`, filtered by `TABLE8_IE_DROP = {36, 39, 46, 55}` for OLIVE-IE rows only; Control/OLIVE-E/Oracle unfiltered | PASS |
| **Figure 6** (within-session reliance growth) | US3 OLIVE-IE gaze-reliance slope ≈ +0.07 units/block, p<.05 (climbing while OLIVE-E erodes) | `python -m release.reproduce.fig6_reliance` | `us2_blockStats_set3.csv` + `us3_blockStats_set3.csv`; drop {18, 39} | PASS |
| **US1** (canonical simulation + convergence) | IE belief 0.79/37s, guidance 0.97/28s; E belief 0.71/53s, guidance 0.79/37s | `python -m release.reproduce.us1` then `us1_convergence` (or `reproduce_all --with-us1`) | Participants 5, 20; steps=90, num-trials=5 | Requires live OLIVE gRPC server; SKIP by default |

**Table 7 vs. Table 8 IE cohorts differ.** Table 7's OLIVE-IE drop is `{37, 39, 46, 55}`; Table 8's is
`{36, 39, 46, 55}`. Both are disclosed, forensically-verified drop sets used for *different* tables;
they intentionally are not the same cohort (see `release/reproduce/table7_us3.py` and
`table8_us3.py` module docstrings).

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

**Expected output** (should be close to the reference rates, not necessarily identical;
see the jitter caveat below):
```
Variant  Metric                Rate    Time (s)
IE       Belief convergence   0.79    37
IE       Guidance convergence 0.97    28
E        Belief convergence   0.71    53
E        Guidance convergence 0.79    37
```

**Reproducibility note:** online-EM is deterministic by design (seeded), but the server
gates EM rounds on wall-clock time rather than a seeded step counter. A re-run is
therefore reproducible **up to EM-timing jitter** (not bit-exact-guaranteed), so
small run-to-run differences in convergence time (and occasionally rate) are expected.

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
- Drops participants P52, P54, P55, P63 by default (`DEFAULT_DROP = TABLE6_DROP = {52, 54, 55, 63}`
  in `table6_us3.py`). This is Table 6's own disclosed cohort, deliberately **not** sourced from
  `release.common.cohort.US3_DROP` (= {18, 39}); that is a different, older drop set that was this
  wrapper's previously-committed default and reproduces a non-paper p-value (IE-vs-E guidance
  p=.046 instead of the paper's p=.008). See the wrapper's module docstring for the full rationale.
- Computes per-block post-switch reconvergence times (guidance and belief)
- Computes reconvergence rates and mean times by condition
- Prints condition (E vs IE) Welch t-tests
- Saves block-level and summary CSVs

**Results:** Reproduces the camera-ready Table 6 US3 reconvergence cells exactly: OLIVE-E 100%/68.5±3.8s,
37%/30.7±5.6s; OLIVE-IE 100%/53.8±4.1s, 56%/25.1±4.0s (n=10/10); IE-vs-E guidance t=−2.67, **p=.008**;
belief t=−0.81, p=.418.

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
