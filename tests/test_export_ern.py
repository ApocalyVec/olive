"""
Test for `release/dataset/ern/export_ern.py`.

Scoped to one subject/study (P5/us1) with a small `limit`, matching
`release/tests/test_extract_ern.py`'s scoping rationale: loading a real
`.p` recording is slow (~1-2GB for P5), so this stays a single-session,
small-limit smoke test rather than exercising the full published cohort.
"""

from release.dataset.ern.export_ern import build_ern_examples


def test_build_ern_examples_schema():
    ex = build_ern_examples(subjects=[5], studies=["us1"], limit=10)

    assert len(ex) > 0

    for row in ex:
        for k in ["subject_id", "study", "eeg", "label", "shot_time"]:
            assert k in row
        assert row["subject_id"] == 5
        assert row["study"] == "us1"
        assert row["label"] in (0, 1)
        assert row["eeg"].shape == (20, 205)


def test_build_ern_examples_respects_global_limit():
    ex = build_ern_examples(subjects=[5], studies=["us1"], limit=10)
    assert len(ex) == 10
