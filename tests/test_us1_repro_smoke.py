import pandas as pd

from release.reproduce.us1 import build_argv
from release.reproduce.us1_convergence import build_arg_parser, compute_convergence_summary


def test_build_argv():
    a = build_argv(
        participants=[5, 20], steps=90, num_trials=5, addr="localhost:50055", out="x"
    )
    # Assert flag/value pairing (e.g. --steps immediately followed by "90")
    assert "--addr" in a
    addr_idx = a.index("--addr")
    assert a[addr_idx + 1] == "localhost:50055"

    assert "--participants" in a
    participants_idx = a.index("--participants")
    # Participants should be 5 and 20 after the flag
    assert a[participants_idx + 1] == "5"
    assert a[participants_idx + 2] == "20"

    assert "--steps" in a
    steps_idx = a.index("--steps")
    assert a[steps_idx + 1] == "90"

    assert "--num-trials" in a
    num_trials_idx = a.index("--num-trials")
    assert a[num_trials_idx + 1] == "5"

    assert "--output-dir" in a
    output_idx = a.index("--output-dir")
    assert a[output_idx + 1] == "x"


def test_us1_convergence_arg_parser():
    """CLI wiring (Finding 1): positional second_stats_csv + optional
    --output-csv / --ema-mode, matching README Step 4 / REPRODUCE.md § US1
    Step 2: `python -m release.reproduce.us1_convergence
    outputs/us1/secondStats.csv --output-csv release/reproduce/out/us1_convergence.csv`.
    """
    parser = build_arg_parser()

    args = parser.parse_args(["outputs/us1/secondStats.csv"])
    assert args.second_stats_csv == "outputs/us1/secondStats.csv"
    assert args.output_csv is None  # main() fills in the default path
    assert args.ema_mode == "raw"

    args = parser.parse_args(
        [
            "outputs/us1/secondStats.csv",
            "--output-csv",
            "release/reproduce/out/us1_convergence.csv",
            "--ema-mode",
            "raw",
        ]
    )
    assert args.output_csv == "release/reproduce/out/us1_convergence.csv"


def _synthetic_second_stats() -> pd.DataFrame:
    """Tiny synthetic secondStats-shaped DataFrame: one converging variant
    (IE, belief+guidance criteria held for >=10 consecutive seconds) and one
    non-converging variant (E, criteria never held), across the columns
    `compute_convergence_summary` reads from a real secondStats.csv."""
    rows = []
    n_seconds = 15
    for variant, converges in [("IE", True), ("E", False)]:
        for t in range(n_seconds):
            if converges:
                auc, prec4, stab = 0.95, 1.0, 0.9
            else:
                auc, prec4, stab = 0.5, 0.0, 0.2
            rows.append(
                dict(
                    participant_id=12,  # present in EEG_AUC
                    model_variant=variant,
                    ema_mode="raw",
                    block_idx=0,
                    trial_seed=1,
                    seconds_elapsed=t,
                    auc=auc,
                    precision_at_4=prec4,
                    top4_stability=stab,
                    mean_mu_pos=0.0,
                    mean_mu_neg=0.0,
                )
            )
    return pd.DataFrame(rows)


def test_compute_convergence_summary_returns_per_variant_frame(tmp_path):
    """Finding 1 smoke test: build a synthetic secondStats.csv (no real US1
    run needed) and assert compute_convergence_summary returns a per-variant
    belief/guidance summary frame."""
    csv_path = tmp_path / "secondStats.csv"
    _synthetic_second_stats().to_csv(csv_path, index=False)

    summary_df = compute_convergence_summary(str(csv_path))

    assert not summary_df.empty
    assert set(summary_df["model_variant"]) == {"IE", "E"}
    assert set(summary_df["convergence_type"]) == {"belief", "guidance"}

    ie_belief = summary_df.query("model_variant == 'IE' and convergence_type == 'belief'").iloc[0]
    assert ie_belief["n_converged"] >= 1
    assert ie_belief["conv_rate"] > 0

    e_belief = summary_df.query("model_variant == 'E' and convergence_type == 'belief'").iloc[0]
    assert e_belief["n_converged"] == 0
    assert e_belief["conv_rate"] == 0
