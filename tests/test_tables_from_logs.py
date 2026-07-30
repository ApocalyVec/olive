"""
Test that table reproduction wrappers expose correct interfaces.

Tests:
  - table2_us2.run() exists and is callable
  - table6_us3.run() exists and is callable
  - table6_us3.DEFAULT_DROP == {18, 39}
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
    """Test that DEFAULT_DROP is correctly set to {18, 39}."""
    assert hasattr(table6_us3, "DEFAULT_DROP")
    assert table6_us3.DEFAULT_DROP == {18, 39}


def test_table2_us2_generator_reference():
    """Test that table2_us2 references the correct generator script."""
    assert hasattr(table2_us2, "GENERATOR")
    assert "us2_vs_us1_convergence" in table2_us2.GENERATOR
