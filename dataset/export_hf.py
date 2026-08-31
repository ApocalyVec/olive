"""
Assemble per-example FRP (fixation-related potential) dataset records and
export them as a HuggingFace `datasets.Dataset` + coverage matrix + card.

This module is the final assembly step of the release pipeline: it wires
together Tasks 2.1-2.4 (already-committed, reused as-is, never
reimplemented here):

    - `release.dataset.extract_epochs.iter_epochs`: raw FRP epochs
    - `release.dataset.regen_p_target.p_target_for_epoch`: per-fixation
      implicit-evidence target probability regeneration
    - `release.dataset.derive_saccades.{load_p_streams,incoming_saccade}`:
      incoming-saccade kinematics from the raw `.p` eye-tracking recording
    - `release.dataset.attach_metadata.{condition_for,ra_condition_for,
      block_meta}`: condition/block metadata
    - `release.common.cohort.RELEASE_SUBJECTS`: the 27-subject release
      cohort
    - `release.common.cohort.PUBLISHED_SUBJECTS`: the 25-subject published
      cohort (excludes subjects 61 and 63 with zero epochs)

Saccade join (best-effort, OFF by default: see `with_saccades`)
-------------------------------------------------------------------
Each epoch from `iter_epochs` carries `item_id` and `fix_time_s`, a
TFRecord-clock fixation-onset timestamp. The raw incoming-saccade
kinematics live in a session's `.p` recording and must be looked up by
`t_onset` from that session's `long_gaze.jsonl` fixation records, which is
an LSL-clock timestamp. **These two clocks are not guaranteed to share an
origin** (`fix_time_s` is TFRecord-pipeline time, `t_onset` is LSL time),
so the join below matches by `item_id` first, then picks the
`long_gaze.jsonl` fixation event whose `t_onset` is numerically closest to
`fix_time_s`, and only accepts the match if that gap is within
`saccade_tolerance_s`. When the pipeline's clocks do not happen to share an
origin for a given session, this tolerance check will reject every
candidate and the saccade fields degrade gracefully to NaN; this is
expected, not a bug, and is why the join is documented as best-effort and
kept behind a flag defaulting to `False`.

A second, session-topology caveat: for the common case (one recording
session per study directory) the `.p` file and every `long_gaze.jsonl`
block file live directly under that one study directory (or, when
`iter_epochs`-style numbered session subdirectories exist AND that numbered
subdirectory itself contains its own `.p` file, under that subdirectory).
For the rare case observed on disk (e.g. subject 5 / us1) where a study
directory has multiple numbered subdirectories that each look like a
session (containing their own block-numbered `long_gaze.jsonl` trees) but
only *one* physical `.p` recording exists at the study-directory root, the
join falls back to that shared root `.p` for every session under that
study directory. In that situation fixation events from more than one
"session" may be pooled against a single raw recording; this is a known,
accepted imprecision of the best-effort join (again defaulting to `nan`
rather than fabricating a wrong-but-confident answer), not silently
swallowed. See `_resolve_session_root` below.

Loading a session's `.p` file is expensive (up to ~1-3GB per file), so this
module never touches the filesystem for saccades unless `with_saccades=True`
is explicitly passed, and caches each loaded session's parsed streams +
`long_gaze.jsonl` index for the duration of one `build_examples` call so a
session already paid for is not reloaded per-epoch.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from release.common.cohort import PUBLISHED_SUBJECTS
from release.dataset.attach_metadata import block_meta, condition_for, ra_condition_for
from release.dataset.derive_saccades import incoming_saccade, load_p_streams
from release.dataset.extract_epochs import iter_epochs
from release.dataset.regen_p_target import p_target_for_epoch

WINGMAN_ROOT = Path.home() / "wingman"

STUDIES = ("us1", "us2", "us3")

# Default acceptance window (seconds) for matching a fixation's TFRecord-clock
# `fix_time_s` against a `long_gaze.jsonl` fixation event's LSL-clock
# `t_onset`. This is deliberately generous (not a physically meaningful
# fixation-duration bound); it exists only to reject grossly-mismatched
# candidates when the two clocks happen not to share an origin for a given
# session; see the module docstring's clock-alignment caveat.
DEFAULT_SACCADE_TOLERANCE_S = 1.0

_NAN_SACCADE_ROW = {
    "fixation_duration": float("nan"),
    "amplitude": float("nan"),
    "angle": float("nan"),
    "peak_velocity": float("nan"),
    "mean_velocity": float("nan"),
    "dx": float("nan"),
    "dy": float("nan"),
}

EXAMPLE_KEYS = [
    "subject_id",
    "user_study",
    "session",
    "eeg",
    "pupil",
    "y",
    "p_target",
    "p_target_quality",
    "item_id",
    "run",
    "fixation_duration",
    "saccade_amplitude",
    "saccade_angle",
    "saccade_peak_velocity",
    "saccade_mean_velocity",
    "saccade_dx",
    "saccade_dy",
    "condition",
    "condition_ra",
    "block_idx",
    "difficulty",
    "task",
]


def _resolve_session_root(subject_id: int, study: str, session: int) -> Optional[Path]:
    """Best-effort resolution of the directory to search for a session's raw
    `.p` recording and `long_gaze.jsonl` fixation records.

    Handles the common single-session-per-study-dir layout (the study dir
    itself holds the one `.p` file plus block-numbered subdirectories with
    `long_gaze.jsonl`) by returning the first matching study dir. For the
    subjects observed with multiple numbered session subdirectories under a
    study dir (e.g. subject 5, 7 / us1), if a numbered subdirectory matching
    `session` itself contains a `.p` file, that subdirectory is returned
    instead so the session's own recording and fixations are used together.
    See the module docstring for the fallback caveat when no numbered
    subdirectory has its own `.p`.
    """
    subj_dir = WINGMAN_ROOT / str(subject_id)
    if not subj_dir.is_dir():
        return None
    study_dirs = sorted(p for p in subj_dir.glob(f"{study}*") if p.is_dir())
    if not study_dirs:
        return None
    for study_dir in study_dirs:
        nested = study_dir / str(session)
        if nested.is_dir() and next(nested.rglob("*.p"), None) is not None:
            return nested
    return study_dirs[0]


def _load_session_saccade_index(subject_id: int, study: str, session: int) -> Optional[dict]:
    """Load one session's `.p` streams + a `{item_id: [(t_onset, duration)]}`
    index built from every `long_gaze.jsonl` under the resolved session
    root. Returns `None` if no `.p` recording or no usable eye-tracking
    stream is found; never raises."""
    root = _resolve_session_root(subject_id, study, session)
    if root is None:
        return None

    p_paths = sorted(root.rglob("*.p"))
    if not p_paths:
        return None

    try:
        streams = load_p_streams(p_paths[0])
    except Exception:  # broad: a .p file can fail to unpickle in many ways
        warnings.warn(
            f"export_hf: failed to load .p recording {p_paths[0]} for "
            f"subject {subject_id}/{study}/session {session}; saccades will be nan",
            RuntimeWarning,
        )
        return None

    varjo = streams.get("Unity.VarjoEyeTrackingComplete")
    head = streams.get("Unity.HeadTracker")
    if varjo is None or head is None:
        return None

    gaze_by_item: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for long_gaze_path in sorted(root.rglob("long_gaze.jsonl")):
        try:
            for line in long_gaze_path.read_text().splitlines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                for g in obj.get("gaze_events", []):
                    gaze_by_item[int(g["item_id"])].append(
                        (float(g["t_onset"]), float(g.get("duration", float("nan"))))
                    )
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            continue  # one malformed/unreadable long_gaze.jsonl must not kill the whole session

    for events in gaze_by_item.values():
        events.sort()

    return {"varjo": varjo, "head": head, "gaze_by_item": gaze_by_item}


def _saccade_for_epoch(
    subject_id: int,
    study: str,
    epoch: dict,
    session_cache: dict,
    tolerance_s: float,
) -> dict:
    """Look up (fixation_duration, incoming-saccade kinematics) for one
    epoch, using/populating `session_cache` (keyed by (subject, study,
    session)) so a session's `.p` file is loaded at most once per
    `build_examples` call. All-nan on any lookup/tolerance miss."""
    key = (subject_id, study, epoch["session"])
    if key not in session_cache:
        session_cache[key] = _load_session_saccade_index(subject_id, study, epoch["session"])
    index = session_cache[key]
    if index is None:
        return dict(_NAN_SACCADE_ROW)

    events = index["gaze_by_item"].get(int(epoch["item_id"]))
    if not events:
        return dict(_NAN_SACCADE_ROW)

    fix_time_s = epoch["fix_time_s"]
    t_onset, duration = min(events, key=lambda e: abs(e[0] - fix_time_s))
    if abs(t_onset - fix_time_s) > tolerance_s:
        return dict(_NAN_SACCADE_ROW)

    sac = incoming_saccade(index["varjo"], index["head"], t_onset)
    return {
        "fixation_duration": duration,
        "amplitude": sac["amplitude"],
        "angle": sac["angle"],
        "peak_velocity": sac["peak_velocity"],
        "mean_velocity": sac["mean_velocity"],
        "dx": sac["dx"],
        "dy": sac["dy"],
    }


def _block_idx_for_epoch(epoch: dict) -> int:
    """Derive the block index from the epoch's `run` field.

    `run` is not literally a block index in `iter_epochs`'s output, but was
    verified empirically against on-disk `meta.jsonl`/block-directory
    structure for multiple subjects across us1/us2/us3: `run` counts
    fixations' originating block starting at 1, one-to-one with the
    0-indexed `<block_idx>/meta.jsonl` directories `block_meta` reads from
    (i.e. `block_idx == run - 1`). Falls back to -1 (matches `block_meta`'s
    own "not found" sentinel) if `run` is not a positive int.
    """
    run = epoch.get("run")
    if isinstance(run, int) and run >= 1:
        return run - 1
    return -1


def build_examples(
    subjects: Iterable[int],
    studies: Iterable[str],
    limit: Optional[int] = None,
    with_saccades: bool = False,
    saccade_tolerance_s: float = DEFAULT_SACCADE_TOLERANCE_S,
) -> list[dict]:
    """Assemble per-example FRP dataset records for `subjects` x `studies`.

    For each (subject, study), enumerates `iter_epochs(subject, study)`;
    `idx` (the epoch's 0-based position within that subject/study's own
    enumeration) seeds the deterministic `p_target_for_epoch` regeneration.
    Attaches condition/RA-condition metadata, best-effort block
    index/difficulty, and (only when `with_saccades=True`) incoming-saccade
    kinematics + fixation duration, all-nan otherwise, by design (see
    module docstring).

    `limit`, if given, caps the *total* number of examples returned across
    the whole (subjects x studies) sweep (not per subject/study); meant
    for fast/small smoke builds, e.g. tests.

    Never raises for a subject/study with no data: `iter_epochs` already
    yields nothing in that case, so the sweep simply contributes zero
    examples for that pair.
    """
    examples: list[dict] = []
    session_cache: dict = {}

    for study in studies:
        for subject_id in subjects:
            condition = condition_for(subject_id)
            condition_ra = ra_condition_for(subject_id)

            for idx, epoch in enumerate(iter_epochs(subject_id, study)):
                if limit is not None and len(examples) >= limit:
                    return examples

                if study == "us1":
                    p_target = float("nan")
                    p_target_quality = float("nan")
                else:
                    item_dtn = 2 if epoch["y"] == 1 else 1
                    p_target, p_target_quality = p_target_for_epoch(subject_id, item_dtn, idx)

                block_idx = _block_idx_for_epoch(epoch)
                meta = block_meta(subject_id, study, block_idx)
                difficulty = meta["difficulty"]
                task = "visual_search" if difficulty == -1 else "spaceshooter"

                if with_saccades:
                    sac = _saccade_for_epoch(subject_id, study, epoch, session_cache, saccade_tolerance_s)
                else:
                    sac = dict(_NAN_SACCADE_ROW)

                examples.append(
                    {
                        "subject_id": epoch["subject_id"],
                        "user_study": epoch["user_study"],
                        "session": epoch["session"],
                        "eeg": epoch["eeg"],
                        "pupil": epoch["pupil"],
                        "y": epoch["y"],
                        "p_target": p_target,
                        "p_target_quality": p_target_quality,
                        "item_id": epoch["item_id"],
                        "run": epoch["run"],
                        "fixation_duration": sac["fixation_duration"],
                        "saccade_amplitude": sac["amplitude"],
                        "saccade_angle": sac["angle"],
                        "saccade_peak_velocity": sac["peak_velocity"],
                        "saccade_mean_velocity": sac["mean_velocity"],
                        "saccade_dx": sac["dx"],
                        "saccade_dy": sac["dy"],
                        "condition": condition,
                        "condition_ra": condition_ra,
                        "block_idx": block_idx,
                        "difficulty": difficulty,
                        "task": task,
                    }
                )

            # Free this (subject, study)'s loaded .p session streams before
            # moving on: each can be up to ~1-3GB and is never needed again
            # once every epoch for this pair has been assembled.
            if with_saccades:
                for key in [k for k in session_cache if k[0] == subject_id and k[1] == study]:
                    del session_cache[key]

    return examples


def _coverage_rows(subjects: Iterable[int], studies: Iterable[str], examples: list[dict]) -> list[dict]:
    counts: dict[tuple[int, str], int] = defaultdict(int)
    for ex in examples:
        counts[(ex["subject_id"], ex["user_study"])] += 1
    rows = []
    for subject_id in subjects:
        row = {"subject_id": subject_id}
        for study in studies:
            row[study] = counts.get((subject_id, study), 0)
        row["total"] = sum(row[study] for study in studies)
        rows.append(row)
    return rows


def write_coverage_csv(subjects: Iterable[int], studies: Iterable[str], examples: list[dict], out_path: Path) -> None:
    studies = list(studies)
    rows = _coverage_rows(subjects, studies, examples)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["subject_id", *studies, "total"])
        writer.writeheader()
        writer.writerows(rows)


def _example_for_arrow(ex: dict) -> dict:
    """Convert one example dict's numpy arrays to plain nested lists so it
    round-trips cleanly through `datasets`/pyarrow regardless of which
    array feature type gets inferred."""
    out = dict(ex)
    out["eeg"] = ex["eeg"].tolist()
    out["pupil"] = ex["pupil"].tolist()
    return out


def write_dataset(examples: list[dict], out_dir: Path) -> str:
    """Write `examples` as a HuggingFace dataset under `out_dir`.

    Tries `datasets.Dataset` first (`.to_parquet`, giving a single Parquet
    file with subject/study/session columns, per the brief's acceptable
    layout); falls back to a plain pandas/pyarrow Parquet write if
    `datasets` is not importable in this environment. Returns the path
    written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [_example_for_arrow(ex) for ex in examples]
    parquet_path = out_dir / "frp_dataset.parquet"

    try:
        from datasets import Dataset

        ds = Dataset.from_list(rows) if rows else Dataset.from_dict({k: [] for k in EXAMPLE_KEYS})
        ds.to_parquet(str(parquet_path))
        ds.save_to_disk(str(out_dir / "hf_dataset"))
        return str(parquet_path)
    except ImportError:
        warnings.warn(
            "export_hf: `datasets` not importable; falling back to a plain "
            "pandas/pyarrow Parquet write (no `datasets`-native save_to_disk directory).",
            RuntimeWarning,
        )
        import pandas as pd

        df = pd.DataFrame(rows if rows else {k: [] for k in EXAMPLE_KEYS})
        df.to_parquet(parquet_path)
        return str(parquet_path)


def _label_balance(examples: list[dict]) -> dict:
    n = len(examples)
    n_pos = sum(1 for e in examples if e["y"] == 1)
    return {"n": n, "n_target": n_pos, "n_nontarget": n - n_pos, "target_rate": (n_pos / n) if n else float("nan")}


def _p_target_summary(examples: list[dict]) -> dict:
    vals = [e["p_target"] for e in examples if not math.isnan(e["p_target"])]
    qualities = [e["p_target_quality"] for e in examples if not math.isnan(e["p_target_quality"])]
    n_nan = sum(1 for e in examples if math.isnan(e["p_target"]))
    return {
        "n_valid": len(vals),
        "n_nan": n_nan,
        "p_target_mean": (sum(vals) / len(vals)) if vals else float("nan"),
        "quality_mean": (sum(qualities) / len(qualities)) if qualities else float("nan"),
        "quality_min": min(qualities) if qualities else float("nan"),
        "quality_max": max(qualities) if qualities else float("nan"),
    }


def write_card(
    examples: list[dict],
    subjects: list[int],
    studies: list[str],
    coverage_csv_path: Path,
    card_path: Path,
    with_saccades: bool,
) -> None:
    balance = _label_balance(examples)
    ptarget = _p_target_summary(examples)
    coverage_rows = _coverage_rows(subjects, studies, examples)
    n_absent = sum(1 for r in coverage_rows if r["total"] == 0)
    absent_subjects = sorted(r["subject_id"] for r in coverage_rows if r["total"] == 0)
    present_subjects = sorted(r["subject_id"] for r in coverage_rows if r["total"] > 0)

    coverage_lines = ["| subject_id | " + " | ".join(studies) + " | total |", "|---" * (len(studies) + 2) + "|"]
    for row in coverage_rows:
        coverage_lines.append(
            "| " + " | ".join(str(row[c]) for c in ["subject_id", *studies, "total"]) + " |"
        )

    card = f"""---
pretty_name: OLIVE FRP Dataset
license: cc-by-4.0
tags:
- eeg
- fixation-related-potentials
- pupillometry
- eye-tracking
- xr
- bci
- attention
size_categories:
- 10K<n<100K
configs:
- config_name: default
  data_files:
  - split: train
    path: data/frp_dataset.parquet
---

# OLIVE FRP Dataset

## What this is

Per-fixation, fixation-related-potential (FRP) examples from the OLIVE
Wingman / SpaceShooter user studies (US1 offline simulation, US2 live deployment,
US3 silent target-switch), for the release cohort of {len(PUBLISHED_SUBJECTS)} participants.
Each example pairs a fixation-locked EEG epoch and pupil epoch with its target label,
incoming-saccade metadata, per-fixation implicit-evidence probability, and
condition and block information.

## Fields (one row per fixation-locked epoch)

| field | type | description |
|---|---|---|
| `subject_id` | int | participant id |
| `user_study` | str | `us1` / `us2` / `us3` |
| `session` | int | recording-session index within (subject, study); usually `0` |
| `eeg` | float32[20, 230] | fixation-locked EEG epoch, see montage/window below |
| `pupil` | float32[2, 80] | fixation-locked pupil-diameter epoch (left/right), see window below |
| `y` | int (0/1) | ground-truth fixated-item label (1 = target) |
| `p_target` | float in [0,1] or NaN | per-fixation implicit-evidence target probability (in [0,1]); NaN where per-subject EEG-evidence parameters are unavailable |
| `p_target_quality` | float in [0.4,1.0] or NaN | per-subject decoder quality (AUC), or NaN |
| `item_id` | int | fixated item id within its block |
| `run` | int | 1-indexed fixation-generating-block counter from the TFRecord (`block_idx = run - 1`, see caveat below) |
| `fixation_duration` | float seconds or NaN | fixation duration from `long_gaze.jsonl`; NaN unless `with_saccades=True` and the join matched |
| `saccade_amplitude` | float degrees or NaN | incoming-saccade amplitude; NaN unless `with_saccades=True` and derivable |
| `saccade_angle` | float radians or NaN | incoming-saccade direction (`atan2(dy, dx)`) |
| `saccade_peak_velocity` | float deg/s or NaN | incoming-saccade peak velocity |
| `saccade_mean_velocity` | float deg/s or NaN | incoming-saccade mean velocity |
| `saccade_dx`, `saccade_dy` | float or NaN | gaze-forward-vector delta components across the incoming saccade |
| `condition` | str | primary, as-published condition label (`IE` / `E`); **use this for any published-table-facing analysis** |
| `condition_ra` | str or None | secondary RA-proposed overlay label; **UNRESOLVED, does not match published tables**, transparency/audit only |
| `block_idx` | int | 0-indexed block within (subject, study, session); `-1` if not derivable (see caveat) |
| `difficulty` | int | adaptive difficulty level for `block_idx`, from `meta.jsonl`; `-1` if not found |
| `task` | str | `visual_search` (calibration blocks, difficulty==-1) or `spaceshooter` (gameplay blocks, difficulty>=0); a per-BLOCK label, not per-study |

`block_idx` caveat: `iter_epochs` does not carry a literal block index field. `run`
was verified empirically (against on-disk `meta.jsonl`/block-directory counts for
multiple subjects across us1/us2/us3) to be a 1-indexed running block counter, so
`block_idx = run - 1` is used. This has not been verified for every subject/session;
treat `block_idx`/`difficulty` as best-effort, not a guaranteed-exact join. `task` is
derived from `difficulty` (`difficulty == -1` => `visual_search`, else `spaceshooter`)
and therefore inherits the same best-effort/fallback behavior: a failed metadata
lookup falls back to `difficulty = -1` => `task = visual_search`.

## EEG montage and epoch windows

- **EEG**: 20-channel B-Alert X24 subset, standard 10-20 layout, sampled at 256 Hz.
  Epoch window is fixation-onset-locked `[-0.1, 0.8]` s → 230 samples/channel.
- **Pupil**: 2-channel (left/right) pupil diameter, sampled at 20 Hz. Epoch window is
  fixation-onset-locked `[-1.0, 3.0]` s → 80 samples/channel.
- Both windows match `release/dataset/extract_epochs.py`'s `EEG_N_T_DEFAULT` /
  `PUPIL_N_T_DEFAULT` constants (reused, not redefined, here).

## Condition legend

- `condition` (primary, as-published): `IE` = Implicit+Explicit (EEG + shot events),
  `E` = Explicit-only (shot events, no EEG). This is the label used throughout the
  paper's published tables and figures.
- `condition_ra`: a secondary v1 RA-proposed relabeling overlay (adds `Oracle` /
  `Control` labels for a handful of subjects) that is **UNRESOLVED against the
  published cohort and does not match the paper's tables** (see
  `release/dataset/attach_metadata.py`'s module docstring and `_RA_OVERRIDES`).
  Included for transparency/auditing only; always prefer `condition` for anything
  that should agree with the paper.

## `p_target` generation

`p_target` is the per-fixation implicit-evidence target probability produced by the default decoder in `release/olive/decode.py` (`DefaultDecoder`), which reads per-subject parameters under `eeg_priors/`. It is `NaN` for subjects/rows without available parameters. Replace the decoder with your own; see the repository README.

## Coverage

Built from subjects={sorted(subjects)}, studies={list(studies)},
with_saccades={with_saccades}.

- Total examples: {balance['n']}
- Target-label rate (`y==1`): {balance['target_rate']:.4f} ({balance['n_target']} target / {balance['n_nontarget']} non-target)
- `p_target` valid (non-NaN): {ptarget['n_valid']} rows, mean={ptarget['p_target_mean']:.4f}; NaN: {ptarget['n_nan']} rows
- `p_target_quality` (valid rows): mean={ptarget['quality_mean']:.4f}, range=[{ptarget['quality_min']:.4f}, {ptarget['quality_max']:.4f}]
- Subjects with zero examples across all studies: {n_absent} ({absent_subjects})
- Subjects with >0 examples in at least one study: {len(present_subjects)} ({present_subjects})

Full per-subject x per-study counts: see `{coverage_csv_path.name}` (same directory as
this card). Table (subject_id x study, `total` = row sum):

{chr(10).join(coverage_lines)}

## Saccade fields caveat (`with_saccades`)

`saccade_*` and `fixation_duration` are **all-NaN by default**
(`with_saccades=False`). Deriving them requires loading a session's raw `.p`
eye-tracking recording (up to ~1-3GB) and joining each epoch's TFRecord-clock
`fix_time_s` against `long_gaze.jsonl`'s LSL-clock `t_onset` by nearest-match within
`item_id`, subject to a tolerance (default {DEFAULT_SACCADE_TOLERANCE_S}s);
**these two clocks are not guaranteed to share an origin**, so even with
`with_saccades=True`, a session whose clocks do not align will legitimately yield
all-NaN saccade fields for every epoch in that session; this is a documented
limitation of the join, not a bug. A second caveat: for the small number of subjects
with multiple numbered "session" subdirectories under one study directory but only
one physical `.p` file at the study-directory root (observed for subject 5 / us1),
the join falls back to that one shared `.p` for every session under that study
directory, which can pool fixation events across sessions. See
`release/dataset/export_hf.py`'s module docstring for full detail.

## Consent

All participants in the published cohort provided informed consent under the study's
IRB protocol for their de-identified physiological (EEG, pupil), behavioral, and
gaze data to be included in a public research dataset release. No directly
identifying information (name, contact info, raw video) is included in this export;
`subject_id` is a study-internal integer id, not a real-world identifier.

## License

**TBD**: placeholder, CC-BY-4.0 (pending final confirmation from the study PI /
IRB before public release).

## Citation

**Placeholder**: update with the final paper citation before public release:

```
@inproceedings{{olive-physio-2026,
  title     = {{OLIVE: [paper title TBD]}},
  author    = {{[authors TBD]}},
  booktitle = {{[venue TBD]}},
  year      = {{2026}},
}}
```
"""

    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(card)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the OLIVE release FRP dataset.")
    parser.add_argument("--out", default=str(Path(__file__).parent / "out"), help="output directory")
    parser.add_argument(
        "--with-saccades",
        action="store_true",
        default=False,
        help="join incoming-saccade kinematics from raw .p recordings (slow, best-effort; default off)",
    )
    parser.add_argument("--limit", type=int, default=None, help="cap total examples (for a fast smoke build)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    subjects = PUBLISHED_SUBJECTS
    studies = list(STUDIES)

    examples = build_examples(subjects, studies, limit=args.limit, with_saccades=args.with_saccades)

    dataset_path = write_dataset(examples, out_dir)
    coverage_csv_path = out_dir / "coverage.csv"
    write_coverage_csv(subjects, studies, examples, coverage_csv_path)
    card_path = Path(__file__).parent / "CARD.md"
    write_card(examples, subjects, studies, coverage_csv_path, card_path, args.with_saccades)

    print(f"Wrote {len(examples)} examples -> {dataset_path}")
    print(f"Wrote coverage matrix -> {coverage_csv_path}")
    print(f"Wrote dataset card -> {card_path}")


if __name__ == "__main__":
    main()
