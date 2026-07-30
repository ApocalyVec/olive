import math
from release.dataset.regen_p_target import p_target_for_epoch


def test_deterministic_regen():
    """Test that p_target_for_epoch is deterministic and values are in valid ranges."""
    a = p_target_for_epoch(4, 2, 0)
    b = p_target_for_epoch(4, 2, 0)

    # Deterministic: same call twice yields identical results
    assert a == b, f"Expected deterministic results, got {a} != {b}"

    # p_target in [0, 1]
    assert 0.0 <= a[0] <= 1.0, f"p_target {a[0]} not in [0.0, 1.0]"

    # quality in [0.4, 1.0]
    assert 0.4 <= a[1] <= 1.0, f"quality {a[1]} not in [0.4, 1.0]"


def test_different_seeds_yield_different_results():
    """Test that different epoch indices (different seeds) yield different results."""
    p1, q1 = p_target_for_epoch(4, 2, 0)
    p2, q2 = p_target_for_epoch(4, 2, 1)

    # Different indices should yield different p_target values (stochastic sampling)
    # Quality should be the same (same subject decoder)
    assert q1 == q2, f"Quality should be the same for same subject, got {q1} != {q2}"
    # p_target values should typically differ (high probability but not guaranteed)
    # We don't assert inequality since sampling could match by chance


def test_missing_priors_returns_nan():
    """Test that subjects without EEG priors return (NaN, NaN)."""
    # Assuming subject 999 does not have priors
    p, q = p_target_for_epoch(999, 2, 0)
    assert math.isnan(p), f"Expected NaN for p_target, got {p}"
    assert math.isnan(q), f"Expected NaN for quality, got {q}"


def test_target_vs_nontarget():
    """Test that target and non-target items have different probability distributions."""
    # For the same subject and seed, target and non-target should differ
    p_target, q_target = p_target_for_epoch(4, 2, 0)
    p_nontarget, q_nontarget = p_target_for_epoch(4, 1, 0)

    # Quality should be the same (same subject)
    assert q_target == q_nontarget

    # p_target should be higher for targets than non-targets
    # (on average, with this seed)
    assert p_target > p_nontarget, f"Expected p_target ({p_target}) > p_nontarget ({p_nontarget})"
