"""
Assemble per-shot ERN (error-related negativity) dataset records and export
them as a second HuggingFace config (`ern`) alongside the FRP dataset
(`release/dataset/export_hf.py`).

This module is the final assembly step for the ERN variant: it wires
together the already-committed extractor (`release/dataset/ern/extract_ern.py`
task 4.1/4.2, reused as-is, never reimplemented here) with the same
condition-metadata helper the FRP export uses, for consistency between the
two dataset variants:

    - `release.dataset.ern.extract_ern.iter_ern_epochs` -- response-locked
      ERN epochs, per (subject, study)
    - `release.dataset.attach_metadata.condition_for` -- primary,
      as-published condition label (`IE` / `E`)
    - `release.common.cohort.PUBLISHED_SUBJECTS` -- the 25-subject published
      cohort

Kept deliberately simple relative to `export_hf.py`: no saccade join, no
`p_target` regeneration, no block/difficulty metadata -- ERN examples are
per-shot-event (not per-fixation), and `iter_ern_epochs` already yields a
self-contained record (subject/study/session/eeg/label/shot_time/montage).

`main()` runs the full (`PUBLISHED_SUBJECTS` x us1/us2/us3) build, which
loads every published subject's `.p` recording per study (each up to
~1-3GB) -- this is slow and is meant to be invoked deliberately (e.g. by a
release-build controller), not as a side effect of importing this module.
`--subjects`/`--studies`/`--limit` let a caller run a smaller/faster build
(e.g. for a smoke test).
"""

from __future__ import annotations

import argparse
import csv
import re
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from release.common.cohort import PUBLISHED_SUBJECTS
from release.dataset.attach_metadata import condition_for
from release.dataset.ern.extract_ern import iter_ern_epochs

STUDIES = ("us1", "us2", "us3")

EXAMPLE_KEYS = [
    "subject_id",
    "study",
    "session",
    "eeg",
    "label",
    "shot_time",
    "montage",
    "condition",
]

# Response-locked ERN epoch parameters (from
# `analysis/repro/new_run/ern_utils.py`, reused unchanged by `iter_ern_epochs`).
ERN_T_PRE_MS = -200
ERN_T_POST_MS = 600
ERN_FS_HZ = 256
ERN_N_SAMP = 205
ERN_N_CH = 20
ERN_FILTER_LO_HZ = 0.5
ERN_FILTER_HI_HZ = 30.0
ERN_BASELINE_MS = (-200, 0)


def build_ern_examples(
    subjects: Iterable[int],
    studies: Iterable[str],
    limit: Optional[int] = None,
) -> list[dict]:
    """Assemble per-shot ERN dataset records for `subjects` x `studies`.

    For each (study, subject), enumerates `iter_ern_epochs(subject, study)`
    and attaches the primary, as-published `condition` label (`IE` / `E`,
    via `condition_for`) for consistency with the FRP dataset's `condition`
    field.

    `limit`, if given, caps the *total* number of examples returned across
    the whole (subjects x studies) sweep (not per subject/study) -- meant
    for fast/small builds, e.g. tests.

    Never raises for a subject/study with no data: `iter_ern_epochs` already
    yields nothing in that case, so the sweep simply contributes zero
    examples for that pair.
    """
    examples: list[dict] = []

    for study in studies:
        for subject_id in subjects:
            condition = condition_for(subject_id)
            for epoch in iter_ern_epochs(subject_id, study):
                if limit is not None and len(examples) >= limit:
                    return examples
                examples.append(
                    {
                        "subject_id": epoch["subject_id"],
                        "study": epoch["study"],
                        "session": epoch["session"],
                        "eeg": epoch["eeg"],
                        "label": epoch["label"],
                        "shot_time": epoch["shot_time"],
                        "montage": epoch["montage"],
                        "condition": condition,
                    }
                )

    return examples


def _coverage_rows(subjects: Iterable[int], studies: Iterable[str], examples: list[dict]) -> list[dict]:
    counts: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: {"correct": 0, "error": 0})
    for ex in examples:
        key = (ex["subject_id"], ex["study"])
        if ex["label"] == 1:
            counts[key]["error"] += 1
        else:
            counts[key]["correct"] += 1

    rows = []
    for subject_id in subjects:
        row: dict = {"subject_id": subject_id}
        total = 0
        for study in studies:
            c = counts[(subject_id, study)]
            row[f"{study}_correct"] = c["correct"]
            row[f"{study}_error"] = c["error"]
            total += c["correct"] + c["error"]
        row["total"] = total
        rows.append(row)
    return rows


def write_coverage_csv(subjects: Iterable[int], studies: Iterable[str], examples: list[dict], out_path: Path) -> None:
    studies = list(studies)
    rows = _coverage_rows(subjects, studies, examples)
    fieldnames = ["subject_id"] + [f"{s}_{k}" for s in studies for k in ("correct", "error")] + ["total"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _example_for_arrow(ex: dict) -> dict:
    """Convert one example dict's numpy array to a plain nested list so it
    round-trips cleanly through `datasets`/pyarrow regardless of which
    array feature type gets inferred."""
    out = dict(ex)
    out["eeg"] = ex["eeg"].tolist()
    return out


def write_dataset(examples: list[dict], out_dir: Path) -> str:
    """Write `examples` as a Parquet file (`ern.parquet`) under `out_dir`.

    Tries `datasets.Dataset` first (`.to_parquet`), matching
    `export_hf.write_dataset`'s approach; falls back to a plain
    pandas/pyarrow Parquet write if `datasets` is not importable. Returns
    the path written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [_example_for_arrow(ex) for ex in examples]
    parquet_path = out_dir / "ern.parquet"

    try:
        from datasets import Dataset

        ds = Dataset.from_list(rows) if rows else Dataset.from_dict({k: [] for k in EXAMPLE_KEYS})
        ds.to_parquet(str(parquet_path))
        return str(parquet_path)
    except ImportError:
        warnings.warn(
            "export_ern: `datasets` not importable; falling back to a plain "
            "pandas/pyarrow Parquet write.",
            RuntimeWarning,
        )
        import pandas as pd

        df = pd.DataFrame(rows if rows else {k: [] for k in EXAMPLE_KEYS})
        df.to_parquet(parquet_path)
        return str(parquet_path)


def _label_balance(examples: list[dict]) -> dict:
    n = len(examples)
    n_err = sum(1 for e in examples if e["label"] == 1)
    return {"n": n, "n_error": n_err, "n_correct": n - n_err, "error_rate": (n_err / n) if n else float("nan")}


_CONFIGS_BLOCK_RE = re.compile(
    r"configs:\n- config_name: default\n  data_files:\n  - split: train\n    path: data/frp_dataset\.parquet\n"
)

_ERN_SECTION_HEADER = "## ERN variant"


def _add_ern_config_to_yaml(card_text: str) -> str:
    """Add the `ern` config entry to the card's YAML `configs:` block.

    Idempotent: if an `ern` config entry is already present, returns
    `card_text` unchanged.
    """
    if "config_name: ern" in card_text:
        return card_text

    replacement = (
        "configs:\n"
        "- config_name: default\n"
        "  data_files:\n"
        "  - split: train\n"
        "    path: data/frp_dataset.parquet\n"
        "- config_name: ern\n"
        "  data_files:\n"
        "  - split: train\n"
        "    path: data/ern.parquet\n"
    )
    new_text, n = _CONFIGS_BLOCK_RE.subn(replacement, card_text, count=1)
    if n == 0:
        warnings.warn(
            "export_ern: could not find the expected `configs:` YAML block in "
            "CARD.md to extend with the `ern` config; leaving YAML untouched.",
            RuntimeWarning,
        )
        return card_text
    return new_text


def _ern_section_text(
    examples: list[dict],
    subjects: list[int],
    studies: list[str],
    coverage_csv_path: Path,
) -> str:
    balance = _label_balance(examples)
    coverage_rows = _coverage_rows(subjects, studies, examples)
    n_absent = sum(1 for r in coverage_rows if r["total"] == 0)
    absent_subjects = sorted(r["subject_id"] for r in coverage_rows if r["total"] == 0)
    present_subjects = sorted(r["subject_id"] for r in coverage_rows if r["total"] > 0)

    cov_cols = ["subject_id"] + [f"{s}_{k}" for s in studies for k in ("correct", "error")] + ["total"]
    coverage_lines = ["| " + " | ".join(cov_cols) + " |", "|---" * len(cov_cols) + "|"]
    for row in coverage_rows:
        coverage_lines.append("| " + " | ".join(str(row[c]) for c in cov_cols) + " |")

    return f"""
{_ERN_SECTION_HEADER}

A second HuggingFace config (`ern`), loadable via
`load_dataset("ApocalyVec/olive-frp", "ern")`, of per-shot response-locked
ERN (error-related negativity) epochs -- distinct from the fixation-locked
FRP epochs in the `default` config above.

### What this is

One row per in-game shot event (enemy hit = correct, friendly-fire hit =
error) from the OLIVE Wingman / SpaceShooter user studies (US1, US2, US3),
for the release cohort of {len(PUBLISHED_SUBJECTS)} participants. Each row
is a single-trial, response-locked EEG epoch around the shot event, labeled
correct/error.

### Fields (one row per shot event)

| field | type | description |
|---|---|---|
| `subject_id` | int | participant id |
| `study` | str | `us1` / `us2` / `us3` |
| `session` | str | recording-session `.p` file stem |
| `eeg` | float32[{ERN_N_CH}, {ERN_N_SAMP}] | response-locked EEG epoch, uV, see window below |
| `label` | int (0/1) | `0` = correct (enemy hit), `1` = error (friendly-fire hit) |
| `shot_time` | float | LSL timestamp of the shot event |
| `montage` | list[str] | B-Alert channel names, in `eeg` row order |
| `condition` | str | primary, as-published condition label (`IE` / `E`), same as the `default` config's `condition` field -- **use this for any published-table-facing analysis** |

### Epoch window and filtering

- **EEG**: {ERN_N_CH}-channel B-Alert X24 subset (same montage as the FRP
  config), sampled at {ERN_FS_HZ} Hz.
- **Window**: response-locked (shot-event-locked) `[{ERN_T_PRE_MS}, {ERN_T_POST_MS}]` ms →
  {ERN_N_SAMP} samples/channel.
- **Filter**: continuous zero-phase 4th-order Butterworth bandpass,
  {ERN_FILTER_LO_HZ}-{ERN_FILTER_HI_HZ} Hz, applied to the full continuous recording *before*
  epoching (per-epoch filtering of an ~800 ms window is invalid for a
  {ERN_FILTER_LO_HZ} Hz high-pass, which needs several seconds of settling).
- **Baseline window**: `[{ERN_BASELINE_MS[0]}, {ERN_BASELINE_MS[1]}]` ms (pre-response) is the
  conventional ERN baseline period included in the epoch; the exported `eeg`
  array is the filtered epoch as-is and is **not baseline-corrected** --
  apply baseline correction (subtract the `[{ERN_BASELINE_MS[0]}, {ERN_BASELINE_MS[1]}]` ms mean per
  channel) yourself if your analysis requires it.
- **Label convention**: shot events come from `Unity.ReNa.EventMarkers` row
  2 (DTN-coded); DTN==1 (friendly fire) → `label=1` (error), DTN==2 (enemy)
  → `label=0` (correct). Verified identical across US1/US2/US3 (see
  `release/dataset/ern/extract_ern.py`'s module docstring for the
  per-subject verification counts).

### Availability

Available for all three studies: US1 (offline simulation), US2 (live
deployment), US3 (silent target-switch). Coverage varies by
subject/study -- some subjects have zero epochs in a given study (no
session recorded, or no `.p` file with usable shot events); see the
coverage table below and `{coverage_csv_path.name}` (same directory as this
card) for exact per-subject counts.

### Coverage

Built from subjects={sorted(subjects)}, studies={list(studies)}.

- Total examples: {balance['n']}
- Error rate (`label==1`): {balance['error_rate']:.4f} ({balance['n_error']} error / {balance['n_correct']} correct)
- Subjects with zero examples across all studies: {n_absent} ({absent_subjects})
- Subjects with >0 examples in at least one study: {len(present_subjects)} ({present_subjects})

Full per-subject x per-study correct/error counts: see `{coverage_csv_path.name}`.
Table (subject_id x study, `total` = row sum):

{chr(10).join(coverage_lines)}
"""


def write_ern_card_section(
    examples: list[dict],
    subjects: list[int],
    studies: list[str],
    coverage_csv_path: Path,
    card_path: Path,
) -> None:
    """Add the `ern` HF config to `card_path`'s YAML `configs:` block and
    append an `## ERN variant` section describing this dataset variant.

    Idempotent: re-running with the same `card_path` replaces a previously
    appended `## ERN variant` section (matched up to the next top-level `##`
    heading or end of file) rather than duplicating it, and leaves the YAML
    `configs:` block untouched if it already has an `ern` entry.
    """
    card_text = card_path.read_text() if card_path.exists() else ""
    card_text = _add_ern_config_to_yaml(card_text)

    section = _ern_section_text(examples, subjects, studies, coverage_csv_path)

    if _ERN_SECTION_HEADER in card_text:
        # Replace the existing section (from its header up to the next
        # top-level "## " heading, or end of file) rather than duplicating it.
        start = card_text.index(_ERN_SECTION_HEADER)
        rest = card_text[start + len(_ERN_SECTION_HEADER):]
        next_heading = rest.find("\n## ")
        end = start + len(_ERN_SECTION_HEADER) + (next_heading if next_heading != -1 else len(rest))
        card_text = card_text[:start].rstrip("\n") + "\n\n" + section.strip("\n") + "\n\n" + card_text[end:].lstrip("\n")
    else:
        card_text = card_text.rstrip("\n") + "\n\n" + section.strip("\n") + "\n"

    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(card_text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the OLIVE release ERN dataset (second HF config).")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "out"), help="output directory")
    parser.add_argument(
        "--subjects",
        type=int,
        nargs="+",
        default=None,
        help="subject ids to include (default: PUBLISHED_SUBJECTS, all 25)",
    )
    parser.add_argument(
        "--studies",
        nargs="+",
        default=None,
        help="studies to include (default: us1 us2 us3)",
    )
    parser.add_argument("--limit", type=int, default=None, help="cap total examples (for a fast smoke build)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    subjects = args.subjects if args.subjects is not None else list(PUBLISHED_SUBJECTS)
    studies = args.studies if args.studies is not None else list(STUDIES)

    examples = build_ern_examples(subjects, studies, limit=args.limit)

    dataset_path = write_dataset(examples, out_dir)
    coverage_csv_path = out_dir / "ern_coverage.csv"
    write_coverage_csv(subjects, studies, examples, coverage_csv_path)
    card_path = Path(__file__).resolve().parents[1] / "CARD.md"
    write_ern_card_section(examples, subjects, studies, coverage_csv_path, card_path)

    print(f"Wrote {len(examples)} examples -> {dataset_path}")
    print(f"Wrote coverage matrix -> {coverage_csv_path}")
    print(f"Updated dataset card -> {card_path}")


if __name__ == "__main__":
    main()
