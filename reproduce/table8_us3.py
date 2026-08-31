"""
US3 skill moderation wrapper (baseline hit rate vs. new-target throughput delta).

Reproduces Table 8 (US3 skill moderation: correlation between baseline hit rate
and within-session new-target throughput delta) from
analysis/repro/new/us3_blockStats_set3.csv, with an ad-hoc OLIVE-IE drop
cohort, via analysis/repro/us3_skill_mod.py.

us3_skill_mod.py has NO --drop flag: it consumes the full blockStats CSV as
given. To apply the Table 8 drop cohort, this wrapper writes a FILTERED COPY
of the set3 US3 CSV (with the dropped OLIVE-IE participant rows removed) to a
temp file, then invokes the existing generator against that filtered copy. It
does NOT reimplement the correlation / regression statistics; those live
entirely in us3_skill_mod.py.

Drop cohort, forensically verified against the published paper cells:
    OLIVE-IE {36, 39, 46, 55}  (keeps IE participants 20, 28, 33, 35, 37, 47, 54, 61)
Control, OLIVE-E, and Oracle are UNCHANGED (full set3 cohort for those
conditions).

Note this differs from Table 7's OLIVE-IE drop ({37, 39, 46, 55}); both are
disclosed drop sets used for different tables; they are NOT the same cohort.
Confirmed against paper commit 24f904d.

Usage:
    from release.reproduce import table8_us3
    table8_us3.run()
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

# Script that generates Table 8 cells (US3 skill moderation)
GENERATOR = "analysis/repro/us3_skill_mod.py"

# Cohort CSV for Table 8 (US3 set3 blockStats, filtered below)
US3_COHORT_CSV = "analysis/repro/new/us3_blockStats_set3.csv"

# The `condition` column value for OLIVE-IE rows in
# analysis/repro/new/us3_blockStats_set3.csv (inspected directly: {'E', 'C',
# 'O', 'IE'}).
IE_CONDITION_CSV_LABEL = "IE"

# Table 8 OLIVE-IE drop cohort. See module docstring for provenance.
TABLE8_IE_DROP = {36, 39, 46, 55}


def _write_filtered_us3_csv(us3_path, out_path):
    """Write a copy of the US3 set3 CSV with TABLE8_IE_DROP OLIVE-IE rows removed."""
    df = pd.read_csv(us3_path)
    mask = (df["condition"] == IE_CONDITION_CSV_LABEL) & (
        df["participant_id"].isin(TABLE8_IE_DROP)
    )
    filtered = df[~mask]
    filtered.to_csv(out_path, index=False)
    return filtered


def run():
    """
    Run US3 skill moderation analysis (Table 8).

    Writes a filtered copy of the US3 set3 blockStats CSV (TABLE8_IE_DROP
    OLIVE-IE rows removed; Control/E/Oracle rows unchanged) to a temp file,
    then invokes analysis/repro/us3_skill_mod.py as a subprocess against that
    filtered CSV, which:
    - Computes per-block hit_rate = target_shot / (target_shot + nontarget_shot)
    - Computes per-participant baseline hit rate (mean over blocks)
    - Computes per-participant delta new-target throughput (last 3 - first 3
      SS blocks, same metric as Table 7)
    - Computes the Pearson correlation and OLS slope of baseline hit rate vs.
      delta, per condition
    - Prints the per-condition skill-moderation table.

    Returns:
        Subprocess return code (0 on success).

    Raises:
        FileNotFoundError: If the generator script or cohort CSV not found.
        subprocess.CalledProcessError: If subprocess exits with non-zero status.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / GENERATOR
    us3_csv_path = repo_root / US3_COHORT_CSV

    if not script_path.exists():
        raise FileNotFoundError(
            f"Required generator script not found: {script_path}\n\n"
            "This wrapper reproduces Table 8 by invoking an analysis script from "
            f"the main OLIVE research repo ({GENERATOR}), which is not part of "
            "this self-contained release and must be present separately on disk "
            "at that path relative to the repo root (it is not vendored here; "
            "see release/README.md's Requirements section and release/REPRODUCE.md "
            "§ 'US3 Skill Moderation (Table 8) Reproduction')."
        )

    if not us3_csv_path.exists():
        raise FileNotFoundError(
            f"Required cohort CSV not found: {us3_csv_path}\n\n"
            "This file must be present at that path relative to the repo root "
            "(it is not vendored here)."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        filtered_us3_path = Path(tmpdir) / "us3_blockStats_set3_table8_filtered.csv"
        _write_filtered_us3_csv(us3_csv_path, filtered_us3_path)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root)

        result = subprocess.run(
            [sys.executable, str(script_path), str(filtered_us3_path), "table8"],
            env=env,
            cwd=repo_root,
        )

    return result.returncode


if __name__ == "__main__":
    sys.exit(run())
