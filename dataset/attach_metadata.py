"""
Attach condition and block difficulty metadata to FRP epochs.

Interfaces:
  - condition_for(subject_id) -> str: Primary published condition label.
  - ra_condition_for(subject_id) -> str | None: Secondary RA-proposed overlay (UNRESOLVED).
  - block_meta(subject_id, study, block_idx) -> dict: Block metadata (difficulty, etc).

RA overlay (v1) is UNRESOLVED and does NOT match published tables. These corrections
are included for transparency, but reconciliation with co-authors is still pending.
The column should be used for analysis/auditing only — always prefer condition_for()
for published tables.
"""

from __future__ import annotations

import json
from pathlib import Path

from release.common.cohort import AS_PUBLISHED_COND

# ─────────────────────────────────────────────────────────────────────────────
# RA v1 condition overrides — FLAGGED UNRESOLVED, do not use for published tables
# ─────────────────────────────────────────────────────────────────────────────
_RA_OVERRIDES = {
    4: "Oracle",    # Published: E
    5: "Control",   # Published: IE
    12: "Control",  # Published: E
    59: "Control",  # Published: E
    27: "IE",       # Published: IE
    56: "IE",       # Published: IE
    58: "Oracle",   # Published: E
}

WINGMAN_ROOT = Path.home() / "wingman"


def condition_for(subject_id: int) -> str:
    """Return the primary (as-published) condition label for a subject.

    Returns:
        'IE' or 'E' if subject_id is in the published cohort, else 'unknown'.
    """
    return AS_PUBLISHED_COND.get(subject_id, "unknown")


def ra_condition_for(subject_id: int) -> str | None:
    """Return the secondary RA-proposed condition label, or None.

    IMPORTANT: These RA corrections are UNRESOLVED and do NOT match the published
    paper tables. Reconciliation with co-authors is pending. Use this column only
    for transparency/auditing; always prefer condition_for() for published results.

    Logic:
      1. If subject_id in _RA_OVERRIDES, return the override.
      2. Else if subject_id in AS_PUBLISHED_COND, return that label.
      3. Else return None.

    Returns:
        str (RA override or as-published label), or None if subject unknown.
    """
    if subject_id in _RA_OVERRIDES:
        return _RA_OVERRIDES[subject_id]
    if subject_id in AS_PUBLISHED_COND:
        return AS_PUBLISHED_COND[subject_id]
    return None


def block_meta(subject_id: int, study: str, block_idx: int) -> dict:
    """Read block metadata (difficulty, block_marker) from meta.jsonl.

    Paths checked:
      - ~/wingman/<sid>/<study>/<block_idx>/meta.jsonl (common layout)
      - ~/wingman/<sid>/<study>*/<session>/<block_idx>/meta.jsonl (session-subdir layout)

    Args:
        subject_id: Participant ID (e.g., 4).
        study: Study name (e.g., 'us2', 'us3', 'us1').
        block_idx: Block index (e.g., 0, 1, 2, ...).

    Returns:
        dict with 'difficulty' (int, default -1) and 'block_marker' (int, default -1).
        Returns {'difficulty': -1, 'block_marker': -1} if file not found or parsing fails.
    """
    # Try to find the block directory under a matching study dir.
    # Study dirs may have suffixes, e.g., 'us2', 'us2_e', 'us2_ie', etc.
    subj_dir = WINGMAN_ROOT / str(subject_id)

    # If subject dir doesn't exist, return default.
    if not subj_dir.is_dir():
        return {"difficulty": -1, "block_marker": -1}

    # Find all matching study directories (e.g., us2*, us3*).
    study_dirs = sorted(
        p for p in subj_dir.glob(f"{study}*") if p.is_dir()
    )

    # Iterate through matching study dirs and look for block_idx.
    # First, try direct path: study_dir / block_idx / meta.jsonl
    for study_dir in study_dirs:
        block_dir = study_dir / str(block_idx)
        meta_file = block_dir / "meta.jsonl"

        if meta_file.is_file():
            try:
                with meta_file.open() as f:
                    line = f.readline().strip()
                    if line:
                        data = json.loads(line)
                        difficulty = data.get("difficulty", -1)
                        block_marker = data.get("block_marker", -1)
                        return {"difficulty": int(difficulty), "block_marker": int(block_marker)}
            except (OSError, json.JSONDecodeError, ValueError):
                # File read or JSON parse error; continue to next study dir.
                pass

    # Second, try session-subdir path: study_dir / <session> / block_idx / meta.jsonl
    for study_dir in study_dirs:
        # Iterate through potential session subdirectories (numeric directories)
        for session_dir in sorted(study_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            # Try to parse as session number; skip if not numeric
            try:
                int(session_dir.name)
            except ValueError:
                continue

            block_dir = session_dir / str(block_idx)
            meta_file = block_dir / "meta.jsonl"

            if meta_file.is_file():
                try:
                    with meta_file.open() as f:
                        line = f.readline().strip()
                        if line:
                            data = json.loads(line)
                            difficulty = data.get("difficulty", -1)
                            block_marker = data.get("block_marker", -1)
                            return {"difficulty": int(difficulty), "block_marker": int(block_marker)}
                except (OSError, json.JSONDecodeError, ValueError):
                    # File read or JSON parse error; continue to next session.
                    pass

    # Not found or error reading all candidate dirs.
    return {"difficulty": -1, "block_marker": -1}
