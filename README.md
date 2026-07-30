# OLIVE: Online Latent Inference from Variable Evidence

OLIVE is an online Bayesian inference system that fuses explicit behavioral signals (task performance, user actions) with implicit physiological signals (EEG, pupil diameter) into a frozen CLIP vision-language model via virtual prompt tuning. At its core, OLIVE uses an expectation-maximization algorithm to maintain a continuously-updated posterior belief over hidden user intent, enabling real-time adaptation in interactive systems like visual search assistants.

## Repository Layout

- **`olive/`**: Core OLIVE server and inference engine
  - `server.py`: gRPC server that runs the OLIVE wingman (decoder-free; run with `python -m release.olive.server --port 50055`)
  - `decode.py`: The decoder seam — ships with a default per-fixation implicit-evidence decoder, replaceable with your own EEG decoder

- **`reproduce/`**: Reproduction scripts for key results from the paper
  - `us1.py`: US1 offline simulation (Wingman on simulated participants)
  - `us1_convergence.py`: Convergence analysis from US1 simulation output
  - `table2_us2.py`: Table 2 reproduction (US2 live-deployment convergence)
  - `table6_us3.py`: Table 6 reproduction (US3 silent-switch reconvergence)
  - `rerun_live_subset.py`: Partial-cohort live OLIVE validation

- **`dataset/`**: FRP epoch extraction, processing, and export
  - `extract_epochs.py`: Fixation-locked EEG/pupil epoch extraction
  - `regen_p_target.py`: Per-fixation target-probability regeneration
  - `derive_saccades.py`: Incoming-saccade feature derivation
  - `attach_metadata.py`: Condition/block metadata attachment
  - `export_hf.py`: Hugging Face dataset export
  - `CARD.md`: Full dataset documentation
  - `out/coverage.csv`: Per-subject, per-study epoch counts

- **`common/`**: Shared utilities
  - `cohort.py`: Release cohort definition (`RELEASE_SUBJECTS`)

## Setup

1. Python 3.10+, in a virtualenv or conda env of your choice.
2. Install dependencies:
   ```bash
   pip install -r release/requirements.txt
   ```
   `release/requirements.txt` covers the dataset-export path only (`datasets`, `pyarrow`); the OLIVE server and reproduction scripts additionally need the parent repo's own dependencies (see the top-level `requirements.txt` at the repo root), so run this release from inside a checkout of the full repo rather than as a standalone package.
3. Create the working directories the scripts expect:
   ```bash
   mkdir -p save_files outputs/us1
   ```

## Quickstart

### Step 1: Boot the OLIVE gRPC server

In one terminal, from the repo root:
```bash
python -m release.olive.server --port 50055
```

### Step 2: Run the US1 offline simulation

In another terminal:
```bash
python -m release.reproduce.us1 \
    --participants 5 20 \
    --steps 90 \
    --num-trials 5 \
    --addr localhost:50055 \
    --output-dir outputs/us1
```

This generates per-second and per-block metrics across two participants (IDs 5, 20) in both IE (Implicit+Explicit) and E (Explicit-only) conditions, writing `outputs/us1/secondStats.csv` and `outputs/us1/blockStats.csv`.

### Step 3: Analyze US1 convergence

```bash
python -m release.reproduce.us1_convergence \
    outputs/us1/secondStats.csv \
    --output-csv release/reproduce/out/us1_convergence.csv
```

This computes per-variant belief/guidance convergence rates and times; compare the output to the reference table in `release/REPRODUCE.md`.

### Step 4: Reproduce Table 2 / Table 6 (optional)

These two wrappers reproduce the camera-ready US2 and US3 convergence tables from already-logged posteriors in `~/wingman`. They invoke analysis scripts from the main OLIVE research repo (`analysis/repro/...`), which are **not vendored in this release** and must be present on disk at the repo root alongside `release/` for these commands to run (see Requirements below):

```bash
python -m release.reproduce.table2_us2   # Table 2: US2 live-deployment convergence
python -m release.reproduce.table6_us3   # Table 6: US3 silent-switch reconvergence
```

### Step 5: Build the FRP dataset (optional)

```bash
python -m release.dataset.export_hf
```

This assembles the per-fixation FRP dataset for the release cohort, writing a Parquet/HF dataset, a coverage matrix, and `release/dataset/CARD.md` under `release/dataset/out/`. See `release/dataset/CARD.md` for the full field-by-field description of the exported dataset.

## Extending OLIVE

### Extension Point 1: Replace the Decoder

The decoder interface is defined in `release/olive/decode.py` as a simple `Decoder` protocol:

```python
def decode(item_dtn: int, *, seed: Optional[int] = None) -> tuple[float, float]:
    """Return (p_target, quality)"""
```

By default, OLIVE ships with `DefaultDecoder`, which reads recorded per-subject EEG-evidence parameters. To integrate your own physiological decoder:

1. Implement a class conforming to the `Decoder` protocol
2. Modify `release/olive/decode.py`'s `load_default_decoder()` to return your decoder instead
3. The shipped per-fixation `p_target` provides a baseline implicit-evidence signal; verify your decoder's behavior against it and against the dataset export's `p_target_quality` field

### Extension Point 2: Tune EM Hyperparameters

OLIVE's online-EM convergence speed and final accuracy are controlled by:
- **Prompt learning rate**: How fast the virtual prompt adapts to new evidence
- **Prevalence anchor**: Prior strength that stabilizes target/non-target rate estimates
- **EMA coefficient**: Temporal smoothing of the posterior belief

These hyperparameters are tuned in the server code (see `release/olive/server.py`). To measure convergence under new settings:

1. Update the hyperparameters in `server.py`
2. Re-run the US1 simulation (Step 2 above)
3. Re-run the convergence analysis (Step 3 above) and compare belief/guidance convergence rates and times to the reference values in `release/REPRODUCE.md`

## Requirements

See `release/requirements.txt` for the dataset-export Python dependencies. The OLIVE code (`olive/`) and dataset builder (`dataset/`) are self-contained and require no external OLIVE source tree beyond the repo root's own `requirements.txt`. The Table 2 / Table 6 reproduction wrappers (`reproduce/table2_us2.py`, `reproduce/table6_us3.py`) are the exception: they invoke analysis scripts from the main OLIVE research repo (`analysis/repro/...`), which must be present on disk alongside this release for those two wrappers to run.
