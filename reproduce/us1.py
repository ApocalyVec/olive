"""
US1 simulation reproduction wrapper.

Provides thin wrapper around scripts/generate_us1_csvs.py to expose
reproducible argv construction and main() entry point.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def build_argv(
    participants: List[int],
    steps: int,
    num_trials: int,
    addr: str,
    out: str,
) -> List[str]:
    """
    Build argv list for generate_us1_csvs.py.

    Args:
        participants: List of participant IDs (e.g., [5, 20])
        steps: Number of seconds per block (default: 90)
        num_trials: Number of trials per participant × variant
        addr: gRPC server address (e.g., "localhost:50055")
        out: Output directory for CSVs

    Returns:
        List of strings representing argv for generate_us1_csvs.py
    """
    argv = [
        "--addr", addr,
        "--participants",
    ]
    # Append participant IDs as separate arguments
    argv.extend(str(p) for p in participants)

    argv.extend([
        "--num-trials", str(num_trials),
        "--steps", str(steps),
        "--output-dir", out,
    ])

    return argv


def main() -> None:
    """
    Run US1 simulation via generate_us1_csvs.py.

    Parses command-line flags and runs the generator via subprocess:
      python -m release.reproduce.us1 --participants 5 20 --steps 90 \
        --num-trials 5 --addr localhost:50055 --output-dir outputs/us1_master_csvs

    - Ensures save_files/ directory exists in repo root
    - Shells out to generate_us1_csvs.py with built argv
    - Uses PYTHONPATH=. for imports
    """
    repo_root = Path(__file__).parent.parent.parent  # rlpf/

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Run US1 simulation via generate_us1_csvs.py"
    )
    parser.add_argument(
        "--participants",
        type=int,
        nargs="*",
        default=None,
        help="Participant IDs to run (e.g., 5 20)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=90,
        help="Number of seconds per block (default: 90)",
    )
    parser.add_argument(
        "--num-trials",
        type=int,
        default=5,
        help="Number of trials per participant × variant (default: 5)",
    )
    parser.add_argument(
        "--addr",
        default="localhost:50055",
        help="gRPC server address (default: localhost:50055)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/us1_master_csvs",
        help="Output directory for CSVs (default: outputs/us1_master_csvs)",
    )
    args = parser.parse_args()

    # Ensure save_files/ directory exists
    save_files_dir = repo_root / "save_files"
    save_files_dir.mkdir(parents=True, exist_ok=True)

    # Build argv for generate_us1_csvs.py
    argv = build_argv(
        participants=args.participants or [],
        steps=args.steps,
        num_trials=args.num_trials,
        addr=args.addr,
        out=args.output_dir,
    )

    # Run the generator via subprocess
    cmd = [sys.executable, str(repo_root / "scripts" / "generate_us1_csvs.py")] + argv

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    subprocess.run(cmd, env=env, check=True)


if __name__ == "__main__":
    main()
