"""
Test for `release/dataset/ern/extract_ern.py`.

Loads real subjects' `.p` recordings (bandpass-filtered continuous EEG,
~1-4 GB on disk) via `iter_ern_epochs`, so these tests are intentionally
scoped to ONE subject per study to keep runtime reasonable.

- Subject 5/us1 is the feasibility reference from the ERN check (~120 error
  / 224 correct shot events) and loads in ~1s on this machine (SSD + OS
  page cache); if it's slow/unavailable in another environment, prefer the
  smallest `.p` on disk under `~/wingman` (subject 8/us1, ~1.0 GB, at last
  check) over subject 7 (no us1 data).
- Subject 35/us2 and subject 35/us3 (task 4.2, US2/US3 ERN extension) are
  the smallest full US2/US3 `.p` recordings on disk with real gameplay
  (~3.3 GB / ~2.5 GB), chosen via `release/dataset/out/coverage.csv`
  (us2=1023, us3=1217 epoch counts) to keep runtime reasonable; both load
  in ~1s each on this machine and yield clean row-2 shot events with both
  DTN labels (us2: 57 error / 377 correct; us3: 31 error / 226 correct),
  confirming the `Unity.ReNa.EventMarkers` row-2 shot-event convention
  extends unchanged from US1 to US2/US3.
"""

from collections import Counter

from release.dataset.ern.extract_ern import iter_ern_epochs


def test_iter_ern_epochs_subject5_us1():
    rows = list(iter_ern_epochs(5, "us1"))

    assert len(rows) > 0

    labels = Counter(r["label"] for r in rows)
    assert set(labels.keys()) == {0, 1}
    # Ample counts, per the ERN feasibility check for P5 (~120 err/224 corr).
    assert labels[1] > 10
    assert labels[0] > 10

    for r in rows:
        assert r["subject_id"] == 5
        assert r["study"] == "us1"
        assert r["eeg"].shape[0] == 20
        assert 200 <= r["eeg"].shape[1] <= 210
        assert r["label"] in (0, 1)
        assert isinstance(r["shot_time"], float)
        assert len(r["montage"]) == 20


def test_iter_ern_epochs_subject35_us2():
    rows = list(iter_ern_epochs(35, "us2"))

    assert len(rows) > 0

    labels = Counter(r["label"] for r in rows)
    assert set(labels.keys()) == {0, 1}
    assert labels[1] > 10
    assert labels[0] > 10

    for r in rows:
        assert r["subject_id"] == 35
        assert r["study"] == "us2"
        assert r["eeg"].shape[0] == 20
        assert 200 <= r["eeg"].shape[1] <= 210
        assert r["label"] in (0, 1)
        assert isinstance(r["shot_time"], float)
        assert len(r["montage"]) == 20


def test_iter_ern_epochs_subject35_us3():
    rows = list(iter_ern_epochs(35, "us3"))

    assert len(rows) > 0

    labels = Counter(r["label"] for r in rows)
    assert set(labels.keys()) == {0, 1}
    assert labels[1] > 10
    assert labels[0] > 10

    for r in rows:
        assert r["subject_id"] == 35
        assert r["study"] == "us3"
        assert r["eeg"].shape[0] == 20
        assert 200 <= r["eeg"].shape[1] <= 210
        assert r["label"] in (0, 1)
        assert isinstance(r["shot_time"], float)
        assert len(r["montage"]) == 20


def test_iter_ern_epochs_missing_subject_yields_nothing():
    # No crash, no data: a subject/study with no session on disk.
    rows = list(iter_ern_epochs(999999, "us1"))
    assert rows == []
