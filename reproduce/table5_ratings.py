"""
Post-block operator trust and reliance ratings wrapper.

Reproduces Table 5 (post-block trust/reliance ratings, US2 & US3) from blockStats CSVs.
Computes per-condition mean ratings (q_trust, q_rely_look, q_rely_shoot) for OLIVE-E,
OLIVE-IE, and Oracle, with P18 & P39 dropped.

Usage:
    from release.reproduce import table5_ratings
    table5_ratings.run()
"""

import sys
from pathlib import Path

import pandas as pd

# Cohort CSVs for Table 5 (US2 & US3 set3 blockStats)
US2_CSV = "analysis/repro/new/us2_blockStats_set3.csv"
US3_CSV = "analysis/repro/new/us3_blockStats_set3.csv"

# Participants to drop (per REPRODUCE.md Table 5 revision)
DROP = {18, 39}

# Rating columns to compute
RATINGS = ["q_trust", "q_rely_look", "q_rely_shoot"]


def run():
    """
    Compute Table 5 per-condition mean ratings from set3 blockStats.

    Loads the two set3 blockStats CSVs, groups by (participant_id, condition),
    drops P18 & P39, and computes per-condition means for Trust, Rely(look),
    and Rely(shoot). Prints a table matching the paper's Table 5 format.

    Returns:
        0 on success.

    Raises:
        FileNotFoundError: If either CSV not found.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    us2_path = repo_root / US2_CSV
    us3_path = repo_root / US3_CSV

    if not us2_path.exists():
        raise FileNotFoundError(
            f"Required cohort CSV not found: {us2_path}\n\n"
            "This file must be present at that path relative to the repo root "
            "(it is not vendored here). See release/README.md's Requirements section."
        )

    if not us3_path.exists():
        raise FileNotFoundError(
            f"Required cohort CSV not found: {us3_path}\n\n"
            "This file must be present at that path relative to the repo root "
            "(it is not vendored here). See release/README.md's Requirements section."
        )

    # Condition mappings: folder-suffix encoding for each study
    cond_map_us2 = {"E": "E", "IE": "IE", "Oracle": "oracle"}
    cond_map_us3 = {"E": "E", "IE": "IE", "Oracle": "O"}

    print("\nTable 5 — Post-block Trust and Reliance Ratings (US2 & US3)")
    print("=" * 80)

    def per_cond(csv_path, study, cond_map):
        """Load CSV, drop participants, compute per-condition means."""
        df = pd.read_csv(csv_path)
        # Group by (participant, condition), compute rating means
        pm = df.groupby(["participant_id", "condition"])[RATINGS].mean().reset_index()
        # Drop P18 & P39
        pm = pm[~pm.participant_id.isin(DROP)]

        for label, cond_code in [("OLIVE-E", "E"), ("OLIVE-IE", "IE"), ("Oracle", "Oracle")]:
            sub = pm[pm.condition == cond_map[cond_code]]
            n = len(sub.dropna(subset=RATINGS))
            trust_mean = sub.q_trust.mean()
            look_mean = sub.q_rely_look.mean()
            shoot_mean = sub.q_rely_shoot.mean()
            print(
                f"{study} {label:9s} n={n:2d}  "
                f"Trust {trust_mean:5.2f}  Look {look_mean:5.2f}  Shoot {shoot_mean:5.2f}"
            )

    per_cond(us2_path, "US2", cond_map_us2)
    per_cond(us3_path, "US3", cond_map_us3)

    return 0


if __name__ == "__main__":
    sys.exit(run())
