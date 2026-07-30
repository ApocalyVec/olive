"""Tests for partial-cohort allowlist validation."""

from release.reproduce.rerun_live_subset import USABLE_US2, USABLE_US3


def test_usable_lists():
    """Assert allowlist subjects match specification."""
    assert USABLE_US2 == [4, 18, 20, 28, 29, 33, 34, 35, 36, 37, 39, 40, 48, 49]
    assert USABLE_US3 == [4, 12, 20, 28, 29, 33, 34, 35, 36, 37, 39, 40, 46, 48, 49]
