"""
US1 convergence analysis wrapper.

Clean-room copy of analysis/us1_convergence.py's pure convergence functions.
Kept separate because the analysis module isn't importable (runs matplotlib
+ hardcoded paths on import).

Convergence definitions (verbatim from analysis/us1_convergence.py):
  Belief convergence:   AUC > 0.90  AND top4_stability >= 0.75  for ≥10 consecutive seconds
  Guidance convergence: precision@4 >= 1.0 AND top4_stability >= 0.75 for ≥10 consecutive seconds

For single-OLIVE reproduction (generate_us1_csvs.py output), model_type is injected
as "olive" since the single-model secondStats.csv has no model_type column
(that column only exists in the merged 5-model CSV built by merge_us1_csvs.py).
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Configuration (matching analysis/us1_convergence.py)
BELIEF_AUC_THRESH = 0.90
BELIEF_STAB_THRESH = 0.75
GUIDANCE_PREC_THRESH = 1.0
GUIDANCE_STAB_THRESH = 0.75
MIN_DURATION = 10  # consecutive seconds

EEG_AUC = {
    12: 0.6352137020741672,
    13: 0.6350627183232773,
    14: 0.6646679631230192,
    15: 0.7957516339869280,
    16: 0.7793748845067447,
    17: 0.8157271168080882,
    18: 0.5375171382275956,
    19: 0.7786353778568649,
    20: 0.8135451969553865,
    21: 0.7730644355644356,
    22: 0.7205204662510165,
    23: 0.8939228995901640,
    25: 0.7692909918285464,
    26: 0.8239113827349122,
    27: 0.8256019984314638,
    28: 0.8850508474576271,
    29: 0.8028024606971976,
    30: 0.7224858757062147,
    31: 0.9017754868270331,
    32: 0.7517761219892566,
    33: 0.7005303109077674,
    34: 0.7248504790877673,
    35: 0.7822598134894817,
    36: 0.7897993311036787,
    4: 0.7565922920892494,
    5: 0.6363636363636364,
    6: 0.7777758440654368,
    8: 0.7543355490029487,
}

EEG_BIN_EDGES = [0.0, 0.70, 1.01]
EEG_BIN_LABELS = ["Low EEG (<0.70)", "High EEG (≥0.70)"]

RENAME_MODELS = {"supervised": "olive-base"}
INCLUDE_MODEL_TYPES = ["olive", "olive-base", "tpt", "tda"]


def add_eeg_cols(df):
    """Add EEG AUC and binning columns to DataFrame."""
    df = df.copy()
    df["eeg_auc"] = df["participant_id"].map(EEG_AUC)
    df["eeg_bin"] = pd.cut(
        df["eeg_auc"], bins=EEG_BIN_EDGES, labels=EEG_BIN_LABELS, right=False
    ).astype(str)
    return df


def convergence_time(block_df, criteria_col):
    """
    Given a single block's DataFrame (sorted by seconds_elapsed) and a boolean
    criteria column, return the first second at which criteria is met for
    MIN_DURATION consecutive seconds, or NaN.
    """
    sdf = block_df.sort_values("seconds_elapsed").reset_index(drop=True)
    meets = sdf[criteria_col].astype(int).fillna(0)

    # Rolling sum over MIN_DURATION rows; == MIN_DURATION means all were True
    roll = meets.rolling(MIN_DURATION, min_periods=MIN_DURATION).sum()
    end_idxs = roll[roll == MIN_DURATION].index
    if len(end_idxs) == 0:
        return np.nan
    # Convergence defined as start of the stable window
    start_idx = end_idxs[0] - MIN_DURATION + 1
    return float(sdf.loc[start_idx, "seconds_elapsed"])


def compute_convergence(df):
    """Return a DataFrame with one row per block and convergence times."""
    df = df.copy()
    df["belief_meets"] = (
        (df["auc"] > BELIEF_AUC_THRESH) & (df["top4_stability"] >= BELIEF_STAB_THRESH)
    )
    df["guidance_meets"] = (
        (df["precision_at_4"] >= GUIDANCE_PREC_THRESH)
        & (df["top4_stability"] >= GUIDANCE_STAB_THRESH)
    )

    group_keys = [
        "participant_id",
        "model_type",
        "model_variant",
        "block_idx",
        "trial_seed",
        "eeg_bin",
    ]
    records = []
    for keys, gdf in df.groupby(group_keys):
        bt = convergence_time(gdf, "belief_meets")
        gt = convergence_time(gdf, "guidance_meets")
        records.append(
            dict(
                zip(group_keys, keys),
                belief_conv=bt,
                guidance_conv=gt,
            )
        )

    return pd.DataFrame(records)


def compute_convergence_summary(
    second_stats_csv: str,
    ema_mode: str = "raw",
    output_csv: Optional[str] = None,
) -> pd.DataFrame:
    """
    Compute per-variant belief/guidance convergence rate and time statistics.

    Args:
        second_stats_csv: Path to secondStats.csv file
        ema_mode: EMA mode to filter on (default: "raw")
        output_csv: Optional path to write convergence summary CSV

    Returns:
        DataFrame with convergence summary rows
    """
    # Load and filter data
    second_df = pd.read_csv(second_stats_csv)
    second_df = second_df.query("ema_mode == @ema_mode")

    # Add EEG columns
    second_df = add_eeg_cols(second_df)

    # Inject model_type if missing (single-OLIVE reproduction path from generate_us1_csvs.py)
    # Full multi-model reproduction uses merge_us1_csvs.py which includes the model_type column
    if "model_type" not in second_df.columns:
        second_df["model_type"] = "olive"

    # Rename model types
    second_df["model_type"] = second_df["model_type"].replace(RENAME_MODELS)

    # Filter to included models
    second_df = second_df[second_df["model_type"].isin(INCLUDE_MODEL_TYPES)]

    # Compute convergence
    conv_df = compute_convergence(second_df)

    # Compute summary statistics
    summary_rows = []
    for conv_col, conv_label in [("belief_conv", "belief"), ("guidance_conv", "guidance")]:
        for (mtype, variant), gdf in conv_df.groupby(["model_type", "model_variant"]):
            times = gdf[conv_col].values
            n_total = len(times)
            conv_times = times[~np.isnan(times)]
            n_converged = len(conv_times)
            conv_rate = n_converged / n_total if n_total > 0 else np.nan
            mean_t = float(np.mean(conv_times)) if n_converged > 0 else np.nan
            median_t = float(np.median(conv_times)) if n_converged > 0 else np.nan
            se_t = (
                float(np.std(conv_times, ddof=1) / np.sqrt(n_converged))
                if n_converged > 1
                else np.nan
            )
            summary_rows.append(
                dict(
                    model_type=mtype,
                    model_variant=variant,
                    convergence_type=conv_label,
                    n_total=n_total,
                    n_converged=n_converged,
                    conv_rate=round(conv_rate, 4),
                    mean_time=round(mean_t, 2) if not np.isnan(mean_t) else np.nan,
                    median_time=round(median_t, 2) if not np.isnan(median_t) else np.nan,
                    se_time=round(se_t, 2) if not np.isnan(se_t) else np.nan,
                )
            )

    summary_df = pd.DataFrame(summary_rows)

    # Write to CSV if output path provided
    if output_csv:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(output_csv, index=False)
        print(f"Saved convergence summary CSV: {output_csv}")

    return summary_df


_CONV_LABELS = {"belief": "Belief convergence", "guidance": "Guidance convergence"}


def build_arg_parser() -> argparse.ArgumentParser:
    """
    Build the argparse parser for the US1 convergence CLI.

    Usage (see release/README.md Step 4 and release/REPRODUCE.md § US1 Step 2):
        python -m release.reproduce.us1_convergence \
            outputs/us1/secondStats.csv \
            --output-csv release/reproduce/out/us1_convergence.csv
    """
    parser = argparse.ArgumentParser(
        description="Compute per-variant belief/guidance convergence rate and time "
        "statistics from a US1 secondStats.csv."
    )
    parser.add_argument(
        "second_stats_csv",
        help="Path to secondStats.csv produced by release.reproduce.us1 (US1 simulation)",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Path to write the convergence summary CSV "
        "(default: release/reproduce/out/us1_convergence.csv)",
    )
    parser.add_argument(
        "--ema-mode",
        default="raw",
        help="ema_mode value to filter the input on (default: raw)",
    )
    return parser


def print_convergence_table(summary_df: pd.DataFrame) -> None:
    """Print the per-variant belief/guidance rate + time table (matches the
    'Expected output' block in release/REPRODUCE.md)."""
    header = f"{'Variant':<8} {'Metric':<21} {'Rate':<7} {'Time (s)':<8}"
    print(header)
    for _, row in summary_df.iterrows():
        metric = _CONV_LABELS.get(row["convergence_type"], row["convergence_type"])
        rate = "" if pd.isna(row["conv_rate"]) else f"{row['conv_rate']:.2f}"
        time_s = "" if pd.isna(row["mean_time"]) else f"{row['mean_time']:.0f}"
        print(f"{row['model_variant']:<8} {metric:<21} {rate:<7} {time_s:<8}")


def main(argv: Optional[list] = None) -> None:
    """
    Entry point for convergence analysis.

    Parses `second_stats_csv` (+ optional `--output-csv`, `--ema-mode`),
    calls `compute_convergence_summary`, prints the per-variant belief/
    guidance rate + time table, and (if `--output-csv` is set, or by default)
    writes the summary CSV to release/reproduce/out/us1_convergence.csv.
    """
    repo_root = Path(__file__).parent.parent.parent  # rlpf/
    default_output_csv = repo_root / "release" / "reproduce" / "out" / "us1_convergence.csv"

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    output_csv = args.output_csv or str(default_output_csv)

    summary_df = compute_convergence_summary(
        args.second_stats_csv,
        ema_mode=args.ema_mode,
        output_csv=output_csv,
    )

    print_convergence_table(summary_df)


if __name__ == "__main__":
    main(sys.argv[1:])
