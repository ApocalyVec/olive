from release.dataset.export_hf import build_examples


def test_build_examples_schema():
    ex = build_examples(subjects=[5], studies=["us1"], limit=5)
    assert len(ex) > 0
    e = ex[0]
    for k in ["subject_id", "user_study", "eeg", "pupil", "y", "p_target", "p_target_quality", "condition"]:
        assert k in e


def test_build_examples_respects_global_limit():
    ex = build_examples(subjects=[5], studies=["us1"], limit=3)
    assert len(ex) == 3


def test_build_examples_saccades_default_off_are_nan():
    import math

    ex = build_examples(subjects=[5], studies=["us1"], limit=5)
    for row in ex:
        assert math.isnan(row["saccade_amplitude"])
        assert math.isnan(row["fixation_duration"])


def test_build_examples_task_field():
    """Built examples should include 'task' field with valid values."""
    ex = build_examples(subjects=[5], studies=["us1"], limit=10)
    assert len(ex) > 0
    for row in ex:
        assert "task" in row
        assert row["task"] in {"visual_search", "spaceshooter"}


def test_us1_ptarget_nan():
    """US1 examples should have NaN p_target and p_target_quality."""
    import math

    ex = build_examples(subjects=[5], studies=["us1"], limit=5)
    assert len(ex) > 0
    for row in ex:
        assert math.isnan(row["p_target"]), f"Expected NaN but got {row['p_target']}"
        assert math.isnan(row["p_target_quality"]), f"Expected NaN but got {row['p_target_quality']}"


def test_us2_ptarget_numeric():
    """US2 examples should have numeric p_target (not NaN)."""
    import math

    ex = build_examples(subjects=[20], studies=["us2"], limit=5)
    if len(ex) > 0:
        # If we got examples, at least some should have valid p_target values
        # (US2 may not have p_target for all subjects, so we just check if any are numeric)
        has_numeric = any(not math.isnan(row["p_target"]) for row in ex)
        assert has_numeric, "Expected at least one numeric p_target value in US2 examples"
