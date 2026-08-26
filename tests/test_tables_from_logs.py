"""
Test that table reproduction wrappers expose correct interfaces.

Tests:
  - table2_us2.run() exists and is callable
  - table6_us3.run() exists and is callable
  - table6_us3.DEFAULT_DROP == {52, 54, 55, 63}
"""

from release.reproduce import table2_us2, table6_us3


def test_table2_us2_run_exists():
    """Test that table2_us2 exposes run()."""
    assert hasattr(table2_us2, "run")
    assert callable(table2_us2.run)


def test_table6_us3_run_exists():
    """Test that table6_us3 exposes run()."""
    assert hasattr(table6_us3, "run")
    assert callable(table6_us3.run)


def test_us3_default_drop():
    """Test that DEFAULT_DROP is correctly set to {52, 54, 55, 63} (Table 6's
    own disclosed cohort, decoupled from release.common.cohort.US3_DROP)."""
    assert hasattr(table6_us3, "DEFAULT_DROP")
    assert table6_us3.DEFAULT_DROP == {52, 54, 55, 63}
    assert hasattr(table6_us3, "TABLE6_DROP")
    assert table6_us3.TABLE6_DROP == {52, 54, 55, 63}


def test_table2_us2_generator_reference():
    """Test that table2_us2 references the correct generator script."""
    assert hasattr(table2_us2, "GENERATOR")
    assert "us2_vs_us1_convergence" in table2_us2.GENERATOR
