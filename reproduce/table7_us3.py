"""
US3 new-target throughput within-session delta wrapper (early vs. late).

Reproduces Table 7 (US3 new-target throughput early-vs-late delta) from
analysis/repro/new/us3_blockStats_set3.csv, filtered by ad-hoc per-condition
drop cohorts, via analysis/repro/within_session_delta.py.

within_session_delta.py has NO --drop flag: it consumes the full blockStats
CSV as given. To apply the Table 7 drop cohorts, this wrapper writes a
FILTERED COPY of the set3 US3 CSV (with the dropped (condition, participant_id)
rows removed) to a temp file, then invokes the existing generator against that
filtered copy alongside the (unfiltered) US2 set3 CSV. It does NOT reimplement
the delta / t-test statistics -- those live entirely in within_session_delta.py.

Drop cohorts (participant_ids dropped from EACH condition's rows), forensically
verified against the published paper cells:
    Control {62, 65, 25}
    OLIVE-E {29, 52}
    OLIVE-IE {37, 39, 46, 55}
    Oracle  {15, 60, 38, 41}

Note this differs from Table 8's OLIVE-IE drop ({36, 39, 46, 55}) -- both are
disclosed drop sets used for different tables; they are NOT the same cohort.

Usage:
    from release.reproduce import table7_us3
    table7_us3.run()
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

# Script that generates Table 7 cells (US3 new-target throughput delta)
GENERATOR = "analysis/repro/within_session_delta.py"

# Cohort CSVs for Table 7 (US2 set3 paired with US3 set3, filtered below)
US2_COHORT_CSV = "analysis/repro/new/us2_blockStats_set3.csv"
US3_COHORT_CSV = "analysis/repro/new/us3_blockStats_set3.csv"

# Table 7 per-condition drop cohorts, keyed by the human-readable condition
# name used in the paper. See module docstring for provenance.
TABLE7_DROPS = {
    "Control": {62, 65, 25},
    "E": {29, 52},
    "IE": {37, 39, 46, 55},
    "Oracle": {15, 60, 38, 41},
}

# Maps the paper's condition names to the `condition` column values found in
# analysis/repro/new/us3_blockStats_set3.csv (inspected directly: {'E', 'C',
# 'O', 'IE'}).
CONDITION_CSV_LABELS = {
    "Control": "C",
    "E": "E",
    "IE": "IE",
    "Oracle": "O",
}


def _write_filtered_us3_csv(us3_path, out_path):
    """Write a copy of the US3 set3 CSV with TABLE7_DROPS rows removed."""
    df = pd.read_csv(us3_path)
    mask = pd.Series(False, index=df.index)
    for cond_name, pids in TABLE7_DROPS.items():
        csv_label = CONDITION_CSV_LABELS[cond_name]
        mask |= (df["condition"] == csv_label) & (df["participant_id"].isin(pids))
    filtered = df[~mask]
    filtered.to_csv(out_path, index=False)
    return filtered


def run():
    """
    Run US3 new-target throughput within-session delta analysis (Table 7).

    Writes a filtered copy of the US3 set3 blockStats CSV (TABLE7_DROPS rows
    removed) to a temp file, then invokes analysis/repro/within_session_delta.py
    as a subprocess against that filtered CSV (paired with the unfiltered US2
    set3 CSV) which:
    - Loads US2 explicit_keys.jsonl from ~/wingman/P{pid}/us2/ (kills/120s)
    - Loads the filtered US3 blockStats CSV
    - Computes early (first 3 SS blocks) vs late (last 3 blocks) new-target
      throughput per participant
    - Performs one-sample t-test of per-participant delta vs 0, per condition
    - Prints both the US2 and US3 delta comparison tables; Table 7 is the
      "US3 new-target throughput delta" block of the output.

    Returns:
        Subprocess return code (0 on success).

    Raises:
        FileNotFoundError: If the generator script or cohort CSV not found.
        subprocess.CalledProcessError: If subprocess exits with non-zero status.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / GENERATOR
    us2_csv_path = repo_root / US2_COHORT_CSV
    us3_csv_path = repo_root / US3_COHORT_CSV

    if not script_path.exists():
        raise FileNotFoundError(
            f"Required generator script not found: {script_path}\n\n"
            "This wrapper reproduces Table 7 by invoking an analysis script from "
            f"the main OLIVE research repo ({GENERATOR}), which is not part of "
            "this self-contained release and must be present separately on disk "
            "at that path relative to the repo root (it is not vendored here -- "
            "see release/README.md's Requirements section and release/REPRODUCE.md "
            "§ 'US3 New-Target Throughput Delta (Table 7) Reproduction')."
        )

    if not us2_csv_path.exists():
        raise FileNotFoundError(
            f"Required cohort CSV not found: {us2_csv_path}\n\n"
            "This file must be present at that path relative to the repo root "
            "(it is not vendored here)."
        )

    if not us3_csv_path.exists():
        raise FileNotFoundError(
            f"Required cohort CSV not found: {us3_csv_path}\n\n"
            "This file must be present at that path relative to the repo root "
            "(it is not vendored here)."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        filtered_us3_path = Path(tmpdir) / "us3_blockStats_set3_table7_filtered.csv"
        _write_filtered_us3_csv(us3_csv_path, filtered_us3_path)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root)

        result = subprocess.run(
            [sys.executable, str(script_path), str(us2_csv_path), str(filtered_us3_path), "table7"],
            env=env,
            cwd=repo_root,
        )

    return result.returncode


if __name__ == "__main__":
    sys.exit(run())
