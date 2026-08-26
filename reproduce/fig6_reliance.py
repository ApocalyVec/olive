"""
Within-session reliance growth rate figure wrapper.

Reproduces Figure 6 (within-session reliance growth slopes, US2 & US3) by invoking
the figure generator script. Computes per-participant slopes of post-block ratings
(Trust, Rely-look, Rely-shoot) vs block index, averaged per condition with P18 & P39
dropped.

Usage:
    from release.reproduce import fig6_reliance
    fig6_reliance.run()
"""

import os
import subprocess
import sys
from pathlib import Path

# Script that generates Figure 6 (within-session reliance growth)
GENERATOR = "analysis/fig_reliance_growth.py"


def run():
    """
    Run within-session reliance growth analysis and generate Figure 6.

    Invokes analysis/fig_reliance_growth.py as subprocess which:
    - Loads US2 and US3 set3 blockStats (with P18 & P39 dropped)
    - Computes per-participant slope of each rating vs block index
    - Averages slopes per condition with one-sample t-tests
    - Saves Figure 6 SVG/PNG (paper/figures/reliance_growth.svg)
    - Prints per-condition slope table (mean ± SE, units/block)

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
            "This wrapper reproduces Figure 6 by invoking an analysis script from "
            f"the main OLIVE research repo ({GENERATOR}), which is not part of "
            "this self-contained release and must be present separately on disk "
            "at that path relative to the repo root (it is not vendored here -- "
            "see release/README.md's Requirements section and release/REPRODUCE.md "
            "§ 'Figure 6 — Within-session Reliance Growth Rates Reproduction')."
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
