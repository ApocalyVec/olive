from collections import Counter

from release.dataset.extract_epochs import _BACKUP_PREFIXES, _resolve_study_dirs, iter_epochs


def test_subject4_us1_yraw_float_dtype_recovered():
    # Regression test: subject 4/us1's shards serialize `y_raw_encoded` as a
    # float feature, while `_DESCRIPTION` declares it "int". Before the
    # dtype-tolerant retry in `_iter_shard_records`, this TypeError aborted
    # every shard on the first record, silently dropping the whole
    # subject/study (0 examples). It must now be non-empty.
    rows = list(iter_epochs(4, "us1"))
    assert len(rows) > 0
    r = rows[0]
    assert r["eeg"].shape[0] == 20 and r["pupil"].shape[0] == 2
    assert r["y"] in (0, 1)


def test_us1_epoch_shapes():
    rows = list(iter_epochs(5, "us1"))
    assert len(rows) > 0
    r = rows[0]
    assert r["eeg"].shape[0] == 20 and r["pupil"].shape[0] == 2
    assert r["y"] in (0, 1) and isinstance(r["item_id"], int)


def test_us1_excludes_backup_shards_and_has_unique_keys():
    # Sanity-check the test fixture itself: subject 5/us1 must actually have
    # pre-fix backup shards on disk, otherwise this test would pass
    # vacuously without exercising the exclusion at all.
    study_dirs = _resolve_study_dirs(5, "us1")
    all_shards = [p for d in study_dirs for p in d.rglob("*.tfrecord")]
    backup_shards = [p for p in all_shards if p.name.startswith(_BACKUP_PREFIXES)]
    assert len(backup_shards) > 0, "expected pre-fix backup shards in the fixture data"

    rows = list(iter_epochs(5, "us1"))

    # No epoch should have come from a backup shard: with backups included
    # subject 5/us1 yields 1182 epochs (591 of which are stale duplicates);
    # with backups excluded it should drop to ~591 (the fixed shards only).
    assert 0 < len(rows) < 1182

    # (session, item_id, run) must be unique once backups (which duplicate
    # these keys against the corrected shards) are excluded.
    keys = [(r["session"], r["item_id"], r["run"]) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate (session,item_id,run) keys: backup contamination"


def test_subject18_us1_no_full_wingman_source_duplication():
    # Regression test for a source-directory duplication bug: subject 18/us1
    # has TFRecord shards both directly under the study dir (e.g.
    # `00001.tfrecord`) *and*, byte-identical, under a `wingman/` subdir
    # (`wingman/wingman_00001.tfrecord`). Both copies are int-encoded (no
    # TypeError), so unlike subjects 5/12 they never triggered the
    # `y_raw_encoded` float-retry guard that already protects against a
    # `wingman/`-duplicate; a plain recursive glob ingested both, doubling
    # every extracted epoch (every (session, item_id, run) key appeared
    # exactly twice: 1592 rows / 796 unique keys before the fix).
    #
    # Sanity-check the fixture itself first: subject 18/us1 must actually
    # have both a top-level and a wingman/ shard set on disk, otherwise this
    # test would pass vacuously without exercising the dedup at all.
    study_dirs = _resolve_study_dirs(18, "us1")
    all_shards = [p for d in study_dirs for p in d.rglob("*.tfrecord")]
    has_wingman_shards = any(p.parent.name == "wingman" for p in all_shards)
    has_primary_shards = any(p.parent.name != "wingman" for p in all_shards)
    assert has_wingman_shards and has_primary_shards, (
        "expected both a wingman/ and a non-wingman/ shard set in the fixture data"
    )

    rows = list(iter_epochs(18, "us1"))
    assert len(rows) > 0

    # Deliberately NOT asserting global (session, item_id, run) uniqueness:
    # several other subjects (e.g. 36, 37, 48) legitimately have a handful of
    # repeated keys from genuine re-fixations within a *single* source
    # directory, and a fix for subject 18's cross-directory bug must not be
    # written in a way that would also force those legitimate repeats away.
    # Instead, assert there is no *full* doubling: no key repeats more than
    # twice, and the vast majority of keys are unique.
    keys = [(r["session"], r["item_id"], r["run"]) for r in rows]
    n, n_unique = len(keys), len(set(keys))
    assert n_unique / n > 0.9, f"subject 18/us1 keys look doubled again: n={n} unique={n_unique}"

    max_repeat = max(Counter(keys).values())
    assert max_repeat <= 2, f"a (session,item_id,run) key repeats {max_repeat} times; expected <=2"


def test_us1_legit_repeat_subject_not_forced_unique():
    # Subject 36/us1 has a small number of legitimate repeated
    # (session, item_id, run) keys from genuine re-fixations within a single
    # source directory -- not the cross-directory duplication fixed above.
    # The subject-18 dedup fix must not collapse these: `n` should be
    # slightly greater than `n_unique` (small legit repeat count preserved),
    # not equal (over-eager dedup) and nowhere near double (bug regression).
    rows = list(iter_epochs(36, "us1"))
    keys = [(r["session"], r["item_id"], r["run"]) for r in rows]
    n, n_unique = len(keys), len(set(keys))
    assert n > n_unique, "expected a small number of legitimate repeated keys to survive"
    assert n_unique / n > 0.9, f"unexpectedly large repeat fraction: n={n} unique={n_unique}"
