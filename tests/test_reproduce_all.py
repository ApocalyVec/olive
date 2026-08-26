"""
Tests for the reproduce_all entrypoint.

Verifies that release.reproduce.reproduce_all:
- Exposes a `main` callable
- Defines a PAPER_EXPECTED dict with entries for Tables 2-8 + Figure 6

Does NOT execute the wrappers (that requires ~/wingman data and analysis/repro
scripts not vendored in this release checkout) -- smoke test only.
"""

from release.reproduce import reproduce_all


def test_exposes_main():
    """reproduce_all exposes a callable main()."""
    assert hasattr(reproduce_all, "main")
    assert callable(reproduce_all.main)


def test_paper_expected_has_all_tables():
    """PAPER_EXPECTED has non-empty entries for tables 2-8 and fig6."""
    assert hasattr(reproduce_all, "PAPER_EXPECTED")
    expected_keys = {"table2", "table3", "table4", "table5", "table6", "table7", "table8", "fig6"}
    assert expected_keys.issubset(set(reproduce_all.PAPER_EXPECTED.keys()))
    for key in expected_keys:
        assert len(reproduce_all.PAPER_EXPECTED[key]) > 0, f"{key} has no expected cells"


def test_table6_expected_matches_paper():
    """Table 6's hardcoded paper values match the camera-ready cells
    (OLIVE-E 100%/68.5, 37%/30.7; OLIVE-IE 100%/53.8, 56%/25.1; p=.008)."""
    t6 = reproduce_all.PAPER_EXPECTED["table6"]
    assert t6["OLIVE-E guidance time"] == 68.5
    assert t6["OLIVE-IE guidance time"] == 53.8
    assert t6["IE vs E guidance p"] == 0.008


def test_targets_registry_covers_tables_2_through_8_and_fig6():
    """TARGETS registry has exactly one entry per table 2-8 and fig6."""
    assert hasattr(reproduce_all, "TARGETS")
    keys = [t[0] for t in reproduce_all.TARGETS]
    assert keys == ["table2", "table3", "table4", "table5", "table6", "table7", "table8", "fig6"]
