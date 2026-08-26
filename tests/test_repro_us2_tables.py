"""
Tests for US2 Table 3 and Table 4 reproduction wrappers.

Verifies that each wrapper module:
- Exposes a `run()` callable
- Defines GENERATOR and COHORT_CSV constants with correct paths
- Does NOT require executing the generators (smoke test only)
"""

import pytest
from release.reproduce import table3_us2, table4_us2


class TestTable3US2:
    """Table 3 (US2 within-session throughput delta) wrapper."""

    def test_exposes_run(self):
        """Table3 wrapper exposes run() function."""
        assert callable(table3_us2.run)

    def test_generator_constant(self):
        """Table3 wrapper defines GENERATOR pointing to within_session_delta.py."""
        assert hasattr(table3_us2, "GENERATOR")
        assert table3_us2.GENERATOR == "analysis/repro/within_session_delta.py"

    def test_us2_cohort_csv_constant(self):
        """Table3 wrapper defines US2_COHORT_CSV pointing to set4."""
        assert hasattr(table3_us2, "US2_COHORT_CSV")
        assert table3_us2.US2_COHORT_CSV == "analysis/repro/new/us2_blockStats_set4.csv"
        # Verify that set4 (not set3) is used for Table 3
        assert "set4" in table3_us2.US2_COHORT_CSV

    def test_us3_cohort_csv_constant(self):
        """Table3 wrapper defines US3_COHORT_CSV pointing to set3."""
        assert hasattr(table3_us2, "US3_COHORT_CSV")
        assert table3_us2.US3_COHORT_CSV == "analysis/repro/new/us3_blockStats_set3.csv"


class TestTable4US2:
    """Table 4 (US2 skill moderation) wrapper."""

    def test_exposes_run(self):
        """Table4 wrapper exposes run() function."""
        assert callable(table4_us2.run)

    def test_generator_constant(self):
        """Table4 wrapper defines GENERATOR pointing to tables_us2.py."""
        assert hasattr(table4_us2, "GENERATOR")
        assert table4_us2.GENERATOR == "analysis/repro/tables_us2.py"

    def test_cohort_csv_constant(self):
        """Table4 wrapper defines COHORT_CSV pointing to set3."""
        assert hasattr(table4_us2, "COHORT_CSV")
        assert table4_us2.COHORT_CSV == "analysis/repro/new/us2_blockStats_set3.csv"
        # Verify that set3 (not set4) is used for Table 4
        assert "set3" in table4_us2.COHORT_CSV
