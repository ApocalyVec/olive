"""Partial-cohort live OLIVE re-run for validation.

Wraps scripts/run_all_participants_olive.py to re-run a subset of subjects
with per-subject EEG decoder quality (AUC) instead of a global --eeg-quality.

This is a best-effort validation run (NOT bit-exact); it demonstrates how per-subject
quality differences manifest in re-run convergence behavior.

Usage:
    python release/reproduce/rerun_live_subset.py --study us2 --wingman-addr 127.0.0.1:50055
    python release/reproduce/rerun_live_subset.py --study us3 --wingman-addr 127.0.0.1:50055
"""

import argparse
import subprocess
import sys
from pathlib import Path

from release.common.cohort import RELEASE_SUBJECTS
from release.olive.decode import load_default_decoder

# Usable subjects for each study (partial cohort, best-effort validation).
# Kept as explicit allowlists (not every release subject has usable live
# replay data for a given study), but tied to the single-source cohort
# definition below via an assertion so they can never silently drift to
# include a subject outside release.common.cohort.RELEASE_SUBJECTS.
USABLE_US2 = [4, 18, 20, 28, 29, 33, 34, 35, 36, 37, 39, 40, 48, 49]
USABLE_US3 = [4, 12, 20, 28, 29, 33, 34, 35, 36, 37, 39, 40, 46, 48, 49]

assert set(USABLE_US2) <= set(RELEASE_SUBJECTS), "USABLE_US2 must be a subset of RELEASE_SUBJECTS"
assert set(USABLE_US3) <= set(RELEASE_SUBJECTS), "USABLE_US3 must be a subset of RELEASE_SUBJECTS"


def main():
    """
    Run partial-cohort live OLIVE re-run with per-subject EEG quality.

    For each subject in the allowlist:
    - Loads their EEG decoder AUC from release.olive.decode.load_default_decoder(sid).quality
    - Runs scripts/run_all_participants_olive.py with --eeg-quality set to that subject's AUC
    - Collects and prints per-subject results

    This is NOT bit-exact reproduction; it demonstrates per-subject quality differences
    in the replay framework.
    """
    parser = argparse.ArgumentParser(
        description="Partial-cohort live OLIVE re-run with per-subject EEG quality"
    )
    parser.add_argument(
        "--study",
        choices=["us2", "us3"],
        required=True,
        help="Study to re-run (us2 or us3)"
    )
    parser.add_argument(
        "--wingman-addr",
        default="127.0.0.1:50055",
        help="Wingman server address (default: 127.0.0.1:50055)"
    )
    args = parser.parse_args()

    # Select allowlist based on study
    if args.study == "us2":
        allowlist = USABLE_US2
    else:
        allowlist = USABLE_US3

    # Get repository root
    repo_root = Path(__file__).resolve().parent.parent.parent

    # Runner script
    runner = repo_root / "scripts" / "run_all_participants_olive.py"
    if not runner.exists():
        raise FileNotFoundError(f"Runner script not found: {runner}")

    print(f"\n{'='*70}")
    print(f"Partial-cohort live OLIVE re-run ({args.study.upper()})")
    print(f"Study: {args.study}")
    print(f"Wingman: {args.wingman_addr}")
    print(f"Usable subjects ({len(allowlist)}): {allowlist}")
    print(f"{'='*70}")
    print("\nNOTE: This is best-effort validation (NOT bit-exact).")
    print("Per-subject EEG decoder quality (AUC) is fetched from per-subject priors.\n")

    results = []

    for sid in allowlist:
        try:
            # Load the subject's EEG decoder quality
            decoder = load_default_decoder(sid)
            quality = decoder.quality

            print(f"\n{'='*70}")
            print(f"P{sid}: Loading decoder quality from eeg_priors/{sid}/us1/eeg_pred_beta.json")
            print(f"P{sid}: AUC (quality) = {quality:.4f}")
            print(f"{'='*70}")

            # Run the replay script for this subject with their decoder quality
            cmd = [
                sys.executable,
                str(runner),
                "--wingman-addr", args.wingman_addr,
                "--participants", str(sid),
                "--eeg-quality", str(quality),
            ]

            print(f"P{sid}: Running: {' '.join(cmd)}\n")

            result = subprocess.run(
                cmd,
                cwd=repo_root,
                env={
                    **dict(__import__("os").environ),
                    "PYTHONPATH": str(repo_root),
                },
            )

            if result.returncode == 0:
                results.append({"participant": sid, "status": "OK", "quality": quality})
            else:
                results.append(
                    {"participant": sid, "status": "FAILED", "quality": quality}
                )

        except Exception as e:
            print(f"\nP{sid}: ERROR loading decoder: {e}")
            results.append({"participant": sid, "status": "ERROR", "error": str(e)})

    # Summary
    print(f"\n\n{'='*70}")
    print("Partial-cohort re-run summary:")
    print(f"{'='*70}")
    print(f"{'Participant':<15} {'Status':<10} {'Quality':<12}")
    print("-" * 37)
    for r in results:
        quality_str = f"{r.get('quality', 'N/A'):.4f}" if isinstance(r.get('quality'), float) else "N/A"
        print(f"P{r['participant']:<14} {r['status']:<10} {quality_str:<12}")

    ok_count = sum(1 for r in results if r["status"] == "OK")
    print(f"\nCompleted: {ok_count}/{len(allowlist)} subjects")
    print(f"\nREPRODUCTION TYPE: Partial-cohort, best-effort validation (NOT bit-exact).")
    print(f"This demonstrates per-subject EEG quality differences in the replay framework.")


if __name__ == "__main__":
    main()
