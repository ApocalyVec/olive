"""
Tests for Table 7 and Table 8 reproduction wrappers (US3 ad-hoc drop cohorts).

Verifies that each wrapper module:
- Exposes a `run()` callable
- Defines the correct drop-cohort constants (exact values, forensically
  verified against the published paper cells)
- Does NOT require executing the generators (smoke test only)
"""

import pytest
from release.reproduce import table7_us3, table8_us3


class TestTable7US3:
    """Table 7 (US3 new-target throughput early-vs-late delta) wrapper."""

    def test_exposes_run(self):
        """Table7 wrapper exposes run() function."""
        assert callable(table7_us3.run)

    def test_generator_constant(self):
        """Table7 wrapper defines GENERATOR pointing to within_session_delta.py."""
        assert hasattr(table7_us3, "GENERATOR")
        assert table7_us3.GENERATOR == "analysis/repro/within_session_delta.py"

    def test_us2_cohort_csv_constant(self):
        """Table7 wrapper defines US2_COHORT_CSV pointing to set3."""
        assert hasattr(table7_us3, "US2_COHORT_CSV")
        assert table7_us3.US2_COHORT_CSV == "analysis/repro/new/us2_blockStats_set3.csv"

    def test_us3_cohort_csv_constant(self):
        """Table7 wrapper defines US3_COHORT_CSV pointing to set3."""
        assert hasattr(table7_us3, "US3_COHORT_CSV")
        assert table7_us3.US3_COHORT_CSV == "analysis/repro/new/us3_blockStats_set3.csv"

    def test_table7_drops_constant(self):
        """Table7 wrapper defines TABLE7_DROPS with the exact forensically-verified cohorts."""
        assert hasattr(table7_us3, "TABLE7_DROPS")
        assert table7_us3.TABLE7_DROPS == {
            "Control": {62, 65, 25},
            "E": {29, 52},
            "IE": {37, 39, 46, 55},
            "Oracle": {15, 60, 38, 41},
        }


class TestTable8US3:
    """Table 8 (US3 skill moderation) wrapper."""

    def test_exposes_run(self):
        """Table8 wrapper exposes run() function."""
        assert callable(table8_us3.run)

    def test_generator_constant(self):
        """Table8 wrapper defines GENERATOR pointing to us3_skill_mod.py."""
        assert hasattr(table8_us3, "GENERATOR")
        assert table8_us3.GENERATOR == "analysis/repro/us3_skill_mod.py"

    def test_us3_cohort_csv_constant(self):
        """Table8 wrapper defines US3_COHORT_CSV pointing to set3."""
        assert hasattr(table8_us3, "US3_COHORT_CSV")
        assert table8_us3.US3_COHORT_CSV == "analysis/repro/new/us3_blockStats_set3.csv"

    def test_table8_ie_drop_constant(self):
        """Table8 wrapper defines TABLE8_IE_DROP with the exact forensically-verified cohort."""
        assert hasattr(table8_us3, "TABLE8_IE_DROP")
        assert table8_us3.TABLE8_IE_DROP == {36, 39, 46, 55}

    def test_table7_table8_ie_drops_differ(self):
        """Table7's IE drop and Table8's IE drop are disclosed as DIFFERENT cohorts."""
        assert table7_us3.TABLE7_DROPS["IE"] != table8_us3.TABLE8_IE_DROP
