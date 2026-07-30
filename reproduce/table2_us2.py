"""
US2 vs US1 convergence comparison wrapper.

Reproduces Table 2 (US2 convergence column) from logged posteriors in ~/wingman.
Wraps analysis/repro/new_run/us2_vs_us1_convergence.py via subprocess.

Usage:
    from release.reproduce import table2_us2
    table2_us2.run()
"""

import os
import subprocess
import sys
from pathlib import Path

# Script that generates Table 2 cells (US2 vs US1 comparison)
GENERATOR = "analysis/repro/new_run/us2_vs_us1_convergence.py"


def run():
    """
    Run US2 vs US1 convergence comparison.

    Invokes analysis/repro/new_run/us2_vs_us1_convergence.py which:
    - Loads wingman_infer_frames_*.jsonl from ~/wingman/P{pid}/us2/
    - Computes convergence rate and mean_time for belief and guidance by condition
    - Compares US2 results to US1 reference values (hardcoded in script)
    - Prints per-condition convergence rate/time comparison table
    - Saves block-level and summary CSVs

    Returns:
        Subprocess return code (0 on success).

    Raises:
        FileNotFoundError: If the generator script not found.
        subprocess.CalledProcessError: If subprocess exits with non-zero status.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / GENERATOR

    if not script_path.exists():
        raise FileNotFoundError(
            f"Required generator script not found: {script_path}\n\n"
            "This wrapper reproduces Table 2 by invoking an analysis script from "
            f"the main OLIVE research repo ({GENERATOR}), which is not part of "
            "this self-contained release and must be present separately on disk "
            "at that path relative to the repo root (it is not vendored here -- "
            "see release/README.md's Requirements section and release/REPRODUCE.md "
            "§ 'US2 Live-Deployment Convergence (Table 2) Reproduction')."
        )

    # Set up environment
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    # Run subprocess
    result = subprocess.run(
        [sys.executable, str(script_path)],
        env=env,
        cwd=repo_root,
    )

    return result.returncode


if __name__ == "__main__":
    sys.exit(run())
