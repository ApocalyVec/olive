"""
US2 skill moderation analysis wrapper.

Reproduces Table 4 (US2 baseline shooting skill moderation of throughput delta) from logged posteriors in ~/wingman.
Wraps analysis/repro/tables_us2.py via subprocess.

Usage:
    from release.reproduce import table4_us2
    table4_us2.run()
"""

import os
import subprocess
import sys
from pathlib import Path

# Script that generates Table 4 cells (US2 skill moderation)
GENERATOR = "analysis/repro/tables_us2.py"

# Cohort CSV for Table 4 (US2 baseline skill moderation)
COHORT_CSV = "analysis/repro/new/us2_blockStats_set3.csv"


def run():
    """
    Run US2 skill moderation analysis.

    Invokes analysis/repro/tables_us2.py which:
    - Loads US2 explicit_keys.jsonl from ~/wingman/P{pid}/us2/ (kills/120s)
    - Loads US2 blockStats from the provided CSV (baseline hit_rate)
    - Computes early (first 3 SS blocks) vs late (last 3 blocks) throughput per participant
    - Computes per-condition Pearson correlation between baseline skill and throughput delta
    - Prints per-condition correlation and regression slope (baseline=hit_mean)

    Returns:
        Subprocess return code (0 on success).

    Raises:
        FileNotFoundError: If the generator script or cohort CSV not found.
        subprocess.CalledProcessError: If subprocess exits with non-zero status.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / GENERATOR
    csv_path = repo_root / COHORT_CSV

    if not script_path.exists():
        raise FileNotFoundError(
            f"Required generator script not found: {script_path}\n\n"
            "This wrapper reproduces Table 4 by invoking an analysis script from "
            f"the main OLIVE research repo ({GENERATOR}), which is not part of "
            "this self-contained release and must be present separately on disk "
            "at that path relative to the repo root (it is not vendored here; "
            "see release/README.md's Requirements section and release/REPRODUCE.md "
            "§ 'US2 Skill Moderation (Table 4) Reproduction')."
        )

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Required cohort CSV not found: {csv_path}\n\n"
            "This file must be present at that path relative to the repo root "
            "(it is not vendored here)."
        )

    # Set up environment
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    # Run subprocess
    result = subprocess.run(
        [sys.executable, str(script_path), str(csv_path), "table4"],
        env=env,
        cwd=repo_root,
    )

    return result.returncode


if __name__ == "__main__":
    sys.exit(run())
