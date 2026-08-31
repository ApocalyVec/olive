"""
US2 within-session throughput delta analysis wrapper.

Reproduces Table 3 (US2 early-vs-late target throughput delta) from logged posteriors in ~/wingman.
Wraps analysis/repro/within_session_delta.py via subprocess.

NOTE: The cohort CSV is us2_blockStats_set4.csv (n=13/10/13/8), but the paper prints
cohort sizes as n=12/10/12/8 from set3, a disclosed labeling difference documented
in the wrapper to prevent silent drift. See release/REPRODUCE.md § 'US2 Within-Session
Throughput Delta (Table 3) Reproduction'.

Usage:
    from release.reproduce import table3_us2
    table3_us2.run()
"""

import os
import subprocess
import sys
from pathlib import Path

# Script that generates Table 3 cells (US2 within-session throughput delta)
GENERATOR = "analysis/repro/within_session_delta.py"

# Cohort CSVs for Table 3 (US2 throughput delta)
US2_COHORT_CSV = "analysis/repro/new/us2_blockStats_set4.csv"
US3_COHORT_CSV = "analysis/repro/new/us3_blockStats_set3.csv"


def run():
    """
    Run US2 within-session throughput delta analysis.

    Invokes analysis/repro/within_session_delta.py which:
    - Loads US2 explicit_keys.jsonl from ~/wingman/P{pid}/us2/ (kills/120s)
    - Loads US3 blockStats from the provided CSV
    - Computes early (first 3 SS blocks) vs late (last 3 blocks) throughput per participant
    - Performs one-sample t-test of per-participant delta vs 0, per condition
    - Prints per-condition delta comparison table

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
            "This wrapper reproduces Table 3 by invoking an analysis script from "
            f"the main OLIVE research repo ({GENERATOR}), which is not part of "
            "this self-contained release and must be present separately on disk "
            "at that path relative to the repo root (it is not vendored here; "
            "see release/README.md's Requirements section and release/REPRODUCE.md "
            "§ 'US2 Within-Session Throughput Delta (Table 3) Reproduction')."
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

    # Set up environment
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    # Run subprocess
    result = subprocess.run(
        [sys.executable, str(script_path), str(us2_csv_path), str(us3_csv_path), "table3"],
        env=env,
        cwd=repo_root,
    )

    return result.returncode


if __name__ == "__main__":
    sys.exit(run())
