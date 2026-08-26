"""
Tests for Table 5 and Figure 6 reproduction wrappers.

Verifies that each wrapper module:
- Exposes a `run()` callable
- Defines the correct constants (DROP set, CSV paths, GENERATOR path)
- Does NOT require executing the generators (smoke test only)
"""

import pytest
from release.reproduce import table5_ratings, fig6_reliance


class TestTable5Ratings:
    """Table 5 (post-block trust/reliance ratings) wrapper."""

    def test_exposes_run(self):
        """Table5 wrapper exposes run() function."""
        assert callable(table5_ratings.run)

    def test_drop_constant(self):
        """Table5 wrapper defines DROP set with {18, 39}."""
        assert hasattr(table5_ratings, "DROP")
        assert table5_ratings.DROP == {18, 39}

    def test_us2_csv_constant(self):
        """Table5 wrapper defines US2_CSV pointing to set3."""
        assert hasattr(table5_ratings, "US2_CSV")
        assert table5_ratings.US2_CSV == "analysis/repro/new/us2_blockStats_set3.csv"
        assert "set3" in table5_ratings.US2_CSV

    def test_us3_csv_constant(self):
        """Table5 wrapper defines US3_CSV pointing to set3."""
        assert hasattr(table5_ratings, "US3_CSV")
        assert table5_ratings.US3_CSV == "analysis/repro/new/us3_blockStats_set3.csv"
        assert "set3" in table5_ratings.US3_CSV

    def test_ratings_constant(self):
        """Table5 wrapper defines RATINGS columns for the three questions."""
        assert hasattr(table5_ratings, "RATINGS")
        assert set(table5_ratings.RATINGS) == {"q_trust", "q_rely_look", "q_rely_shoot"}


class TestFig6Reliance:
    """Figure 6 (within-session reliance growth) wrapper."""

    def test_exposes_run(self):
        """Fig6 wrapper exposes run() function."""
        assert callable(fig6_reliance.run)

    def test_generator_constant(self):
        """Fig6 wrapper defines GENERATOR pointing to fig_reliance_growth.py."""
        assert hasattr(fig6_reliance, "GENERATOR")
        assert fig6_reliance.GENERATOR == "analysis/fig_reliance_growth.py"
