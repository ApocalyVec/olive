# Working with agents: OLIVE code repository

This file orients an AI coding agent (Claude Code, Cursor, etc.) working in this
repository. It is a companion to `README.md` (human quickstart) and `REPRODUCE.md`
(paper reproduction).

## What this repo is

OLIVE (Online Latent Inference from Variable Evidence): an online-EM system that fuses
explicit behavioral evidence and implicit physiological (fixation-locked EEG) evidence
into a frozen CLIP VLM via virtual-prompt tuning. This repo is the **release**: the
algorithm, a reproduction of the paper's tables/figures, and builders for the released
datasets.

## Layout

| Path | Purpose |
|---|---|
| `olive/server.py` | decoder-free OLIVE gRPC server (EM + CLIP scorer) |
| `olive/decode.py` | the pluggable `decode()` seam: `DefaultDecoder` is the default per-fixation implicit-evidence decoder |
| `reproduce/` | one wrapper per paper table/figure + `reproduce_all.py` |
| `dataset/` | FRP dataset builder (`export_hf.py`) + `dataset/ern/` (ERN variant) |
| `examples/` | example notebooks (ERP, subject-transfer) |
| `common/cohort.py` | cohort constants |
| `tests/` | pytest suite |

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # plus the parent repo's requirements
mkdir -p save_files                       # cache dir for the US1 simulation
```
Run everything as `PYTHONPATH=. python …` from the repo root.

## Key commands

- **Tests:** `PYTHONPATH=. python -m pytest tests -q`
- **Reproduce all paper tables/figures:** `PYTHONPATH=. python -m reproduce.reproduce_all`
  (Tables 2 to 8 + Fig 6; US1 needs the server, add `--with-us1`).
- **OLIVE server:** `PYTHONPATH=. python -m olive.server --port 50055` (CLIP ViT-B/16; CPU/MPS/CUDA).
- **Build the FRP dataset:** `PYTHONPATH=. python -m dataset.export_hf`
- **Build the ERN variant:** `PYTHONPATH=. python -m dataset.ern.export_ern`

## Conventions an agent MUST respect

- **Label convention: `y == 1` is the target**, `y == 0` non-target (one-hot `y_raw_encoded`
  is argmax-decoded; `y_raw == 2` == target). Do not reintroduce first-element decoding.
- **Cohort:** `PUBLISHED_SUBJECTS` (25) is what the dataset ships; `RELEASE_SUBJECTS` (27)
  is the nominal IE+E cohort. Reproduction wrappers use their own `set3`/`set4` cohorts.
- **`p_target`** is a per-fixation implicit-evidence probability for **auditability and
  decoder-swap experiments**, present for US2/US3 only (NaN for US1). It is **not** the
  literal value used in the live studies and is not the mechanism behind any paper table.
- **Reproduction is analysis-of-logs**, not OLIVE re-runs, for US2/US3 (US1 is a seeded
  simulation, reproducible up to EM-timing jitter). Each table has a documented cohort/drop
  set in `REPRODUCE.md`; do not silently change them.
- **Never commit** large artifacts: `dataset/out/*.parquet`, `dataset/out/hf_dataset/`,
  `__pycache__/`. Commit changed files by explicit path.
- The Table 2/6 reproduction wrappers call analysis scripts under `analysis/repro/…` in the
  parent OLIVE research repo (not vendored here); the dataset builders read `~/wingman/`.

## Extending

- Swap in your own EEG decoder: implement the `Decoder` protocol in `olive/decode.py`; the
  shipped `p_target` gives a baseline to compare against.
- Tune the EM (prompt lr, prevalence anchor, EMA) and measure with `reproduce/us1_convergence.py`.

## Data availability / provenance

The paper describes the studies and the implicit-evidence channel; this repo does not
duplicate that. See the paper and the HuggingFace dataset card (`ApocalyVec/olive-physio`).
