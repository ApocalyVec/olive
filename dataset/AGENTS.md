# Working with agents — OLIVE FRP dataset

Orientation for an AI agent using this HuggingFace dataset (`ApocalyVec/olive-frp`).
See `README.md` (the dataset card) for full field docs.

## Load it

```python
from datasets import load_dataset
frp = load_dataset("ApocalyVec/olive-frp", "default")   # fixation-locked FRP epochs
ern = load_dataset("ApocalyVec/olive-frp", "ern")       # response-locked ERN epochs
```

Two configs: **`default`** (`data/frp_dataset.parquet`) and **`ern`** (`data/ern.parquet`).

## Conventions an agent MUST respect

- **`y == 1` is the target**, `y == 0` non-target (default config). Targets are the minority
  class (~40%). Do not assume `1`=non-target.
- **`task`** is a per-EPOCH label (`visual_search` = calibration blocks, `spaceshooter` =
  gameplay blocks). Both occur within every study session — it is **not** a per-study field.
  Filter by `task`, not by `user_study`, to separate the two tasks.
- **`p_target`** (default config) is a per-fixation implicit-evidence probability for
  auditability / decoder-swap comparison; it is present for US2/US3 only (`NaN` for US1) and
  is not the literal value used in the studies.
- **`condition`** (`IE`/`E`) is the as-published label — use it for anything that should agree
  with the paper. `condition_ra` is an unresolved audit overlay; ignore it for paper-facing work.
- **ERN config**: `label` is `0`=correct (enemy hit) / `1`=error (friendly fire); epochs are
  response-locked `[-200, 600] ms` @256 Hz (`[20, 205]`), 0.5–30 Hz filtered.
- `eeg` loads as a nested array; reshape a row via `np.array(row.tolist(), dtype=np.float32)`
  → `[20, 230]` (default) / `[20, 205]` (ern). EEG is 256 Hz; FRP window is `[-0.1, 0.8] s`.
- `saccade_*` / `fixation_duration` are `NaN` by default (a separate opt-in derivation).

## Cohort & provenance

25 subjects (the OLIVE IE+E cohort with data). The paper describes the studies and the
implicit-evidence channel; this card does not duplicate that. Code + reproduction:
https://github.com/ApocalyVec/olive
