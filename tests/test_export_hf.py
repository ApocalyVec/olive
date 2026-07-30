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
