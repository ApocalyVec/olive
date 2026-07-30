"""
US3 reconvergence analysis wrapper.

Reproduces Table 6 (US3 post-switch reconvergence) from logged posteriors in ~/wingman.
Wraps analysis/repro/table5_reconv_drop.py via subprocess with configurable drop set.

Usage:
    from release.reproduce import table6_us3
    table6_us3.run()  # Uses DEFAULT_DROP = release.common.cohort.US3_DROP ({18, 39})
    table6_us3.run(drop={18, 39, 50})  # Custom drop set
"""

import os
import subprocess
import sys
from pathlib import Path

from release.common.cohort import US3_DROP

# Script that generates Table 6 cells (US3 post-switch reconvergence)
GENERATOR = "analysis/repro/table5_reconv_drop.py"

# Default drop set (matches REPRODUCE.md camera-ready table); single-sourced
# from release.common.cohort.US3_DROP so this and release/common/cohort.py
# can't silently drift apart.
DEFAULT_DROP = US3_DROP


def run(drop=None):
    """
    Run US3 reconvergence analysis with configurable drop set.

    Invokes analysis/repro/table5_reconv_drop.py as subprocess with:
    - US3_DROP env var set to comma-separated drop set
    - PYTHONPATH=. so the script can import us3_convergence

    The script computes:
    - Per-block post-switch reconvergence times (guidance and belief)
    - Reconvergence rates and timing summary by condition (E vs IE)
    - IE vs E Welch t-tests

    Args:
        drop: Set of participant IDs to exclude (default: {18, 39}).
              If None, uses DEFAULT_DROP.

    Returns:
        Subprocess return code (0 on success).

    Raises:
        FileNotFoundError: If analysis/repro/table5_reconv_drop.py not found.
        subprocess.CalledProcessError: If subprocess exits with non-zero status.
    """
    if drop is None:
        drop = DEFAULT_DROP

    # Convert set to comma-separated string for US3_DROP env var
    drop_str = ",".join(str(p) for p in sorted(drop))

    # Resolve script path
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / GENERATOR

    if not script_path.exists():
        raise FileNotFoundError(
            f"Required generator script not found: {script_path}\n\n"
            "This wrapper reproduces Table 6 by invoking an analysis script from "
            f"the main OLIVE research repo ({GENERATOR}), which is not part of "
            "this self-contained release and must be present separately on disk "
            "at that path relative to the repo root (it is not vendored here -- "
            "see release/README.md's Requirements section and release/REPRODUCE.md "
            "§ 'US3 Silent-Switch Reconvergence (Table 6) Reproduction')."
        )

    # Set up environment
    env = os.environ.copy()
    env["US3_DROP"] = drop_str
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
