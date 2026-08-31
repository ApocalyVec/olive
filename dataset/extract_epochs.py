"""
Robust FRP (fixation-related potential) epoch extraction from the Wingman
study TFRecords.

Reuses the `tfrecord_loader` reading pattern from
`main_check_eeg_pupil_tfrecords.py` (`_load_signal_xy`), but is deliberately
defensive: real study data on disk includes shards that are zero bytes and
`.idx` sidecar files that are size-0 or otherwise stale/unreliable. This
module never trusts `.idx` files (always reads with `index_path=None`) and
wraps every shard read in try/except so a single bad/empty shard cannot
crash extraction for a subject/study. It also excludes legacy pre-fix
backup shards (see `_BACKUP_PREFIXES`) so old, buggy `y_raw_encoded` labels
cannot re-enter the extracted data.

Directory layout on disk: `~/wingman/<sid>/<study>[_<condsuffix>]/...`, e.g.
`~/wingman/12/us2_e/...`. TFRecord shards for a given subject/study can live
directly under the study dir, under a "wingman" subdir, or under numbered
session subdirs (observed for some us1 subjects who were recorded across
more than one session, e.g. `us1/0/*.tfrecord`, `us1/1/*.tfrecord`).
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Iterator

import numpy as np
from tfrecord.reader import tfrecord_loader

# ---------------------------
# Config (matches main_check_eeg_pupil_tfrecords.py)
# ---------------------------
EEG_N_CH = 20
EEG_N_T_DEFAULT = 230  # (-0.1, 0.8) s @ 256 Hz

PUPIL_N_CH = 2
PUPIL_N_T_DEFAULT = 80  # (-1.0, 3.0) s @ 20 Hz

WINGMAN_ROOT = Path.home() / "wingman"

# Legacy pre-fix backup shards must never be ingested: they carry the old,
# buggy y_raw_encoded labels (and duplicate (session, item_id, run) keys
# against the corrected shards). Mirrors BACKUP_YRAW_PREFIX /
# BACKUP_ENCODER_PREFIX in scripts/check_fix_tfrecords.py, which renames
# pre-fix shards with these prefixes before writing the corrected replacement.
_BACKUP_PREFIXES = ("_before_y_raw_encoded_fix_", "_before_y_encoder_fix_")

# Minimal description: only parse what we need (avoids unknown dtype issues).
_DESCRIPTION = {
    "eeg": "float",
    "eeg.shape": "int",
    "pupil_size": "float",
    "pupil_size.shape": "int",
    "y_raw": "int",
    "y_raw_encoded": "int",
    "run": "int",
    "item_id": "int",
    "fix_time_s": "float",
}

# Some legacy shards (observed for subjects 4, 5, 12 / us1) serialize
# `y_raw_encoded` as a float feature instead of an int64 feature. `_DESCRIPTION`
# declaring it "int" makes `tfrecord_loader` raise a TypeError on the very
# first record of such a shard, which previously aborted (and silently
# dropped) the *entire* shard. This alternate description is used as a retry
# for exactly that case; see `_iter_shard_records`.
_DESCRIPTION_FLOAT_YRAW = {**_DESCRIPTION, "y_raw_encoded": "float"}


def _as_scalar_int(v) -> int:
    # round() before int() so a float-serialized label (e.g. 1.0, or
    # 0.9999999 from float round-tripping) never truncates to the wrong
    # class; a no-op for already-integer values.
    return int(round(float(np.asarray(v).reshape(-1)[0])))


def _decode_y(arr) -> int:
    # Decode y_raw_encoded one-hot (column order: [y_raw==1, y_raw==2]).
    # y_raw=1 (non-target) -> [1,0]; y_raw=2 (target) -> [0,1].
    # Correct decode uses argmax: argmax([1,0])=0, argmax([0,1])=1.
    return int(np.argmax(np.asarray(arr).reshape(-1)))


def _as_scalar_float(v) -> float:
    return float(np.asarray(v).reshape(-1)[0])


def _reshape_signal(flat_v, shape_v, n_ch_default: int, n_t_default: int) -> np.ndarray:
    """Reshape a flattened signal using its recorded `.shape` field, falling
    back to the default (n_ch_default, n_t_default) if the shape field is
    missing or inconsistent with the flattened payload size."""
    flat = np.asarray(flat_v, dtype=np.float32).reshape(-1)
    if shape_v is not None:
        shp = tuple(np.asarray(shape_v, dtype=np.int64).reshape(-1).tolist())
        if len(shp) == 2 and shp[0] * shp[1] == flat.size:
            return flat.reshape(shp)
    return flat.reshape(n_ch_default, n_t_default)


def _resolve_study_dirs(subject_id: int, study: str) -> list[Path]:
    """Resolve all session dirs for a subject+study, e.g. globbing
    `us2*` under `~/wingman/<sid>/` matches `us2`, `us2_e`, `us2_ie`, etc.
    Returns an empty list (never raises) if the subject has no such dirs."""
    subj_dir = WINGMAN_ROOT / str(subject_id)
    if not subj_dir.is_dir():
        return []
    return sorted(p for p in subj_dir.glob(f"{study}*") if p.is_dir())


def _wingman_canonical_name(name: str) -> str:
    """Strip the `wingman_` filename prefix used by shards living under a
    `wingman/` subdir, so they can be compared against same-content shards
    that live directly under the study dir (e.g. `wingman_00001.tfrecord` ->
    `00001.tfrecord`). Names without the prefix are returned unchanged."""
    prefix = "wingman_"
    return name[len(prefix):] if name.startswith(prefix) else name


def _dedup_wingman_source_shards(all_shards: list[Path]) -> list[Path]:
    """Drop `wingman/`-parented shards that are byte-identical duplicates of
    a shard already present outside `wingman/` in the same study dir.

    Bug this fixes (subject 18 / us1): some study dirs have shards both
    directly under the study dir (e.g. `00001.tfrecord`) *and*, byte-for-byte
    identical, under a `wingman/` subdir (`wingman/wingman_00001.tfrecord`).
    Both copies are int-encoded, so neither triggers the `y_raw_encoded`
    float-retry TypeError that the sole other `wingman/`-duplicate guard
    (`has_sibling_source` in `iter_epochs`) is built around; a plain
    recursive glob ingests both, doubling every extracted epoch for that
    subject/study.

    This is deliberately a *source-directory* dedup, not a
    (session, item_id, run)-key dedup: several subjects legitimately have a
    handful of repeated keys from genuine re-fixations within a *single*
    source directory, and those must survive untouched. A `wingman/` shard
    is dropped here only when a non-`wingman/` shard in the same study dir
    shares both its basename (modulo the `wingman_` prefix) and its exact,
    non-zero file size: i.e. only when it is provably the same file
    ingested twice. If `wingman/` is the *only* source in the study dir
    (subject 4/us1: no sibling shard at all), nothing is dropped; that is
    exactly the case the float-retry exists to recover.
    """
    primary = [p for p in all_shards if p.parent.name != "wingman"]
    wingman = [p for p in all_shards if p.parent.name == "wingman"]
    if not primary or not wingman:
        return all_shards  # wingman/ is the sole source, or there's nothing to dedup against

    primary_sizes: dict[tuple[str, int], Path] = {}
    for p in primary:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > 0:
            primary_sizes[(p.name, size)] = p

    kept = list(primary)
    for p in wingman:
        try:
            size = p.stat().st_size
        except OSError:
            kept.append(p)
            continue
        is_duplicate = size > 0 and (_wingman_canonical_name(p.name), size) in primary_sizes
        if not is_duplicate:
            kept.append(p)
    return sorted(kept)


def _session_from_shard(shard_path: Path) -> int:
    """Session is derived from the shard's immediate parent directory name
    when that name is a plain integer (observed for subjects recorded across
    multiple sessions); otherwise defaults to 0."""
    name = shard_path.parent.name
    return int(name) if name.isdigit() else 0


def _iter_shard_records(shard_path: Path, allow_float_yraw_retry: bool = True):
    """Yield decoded records from one shard, tolerating empty, truncated, or
    otherwise unreadable shards. Never relies on a `.idx` sidecar file since
    many are size-0 or stale in the study data.

    `tfrecord_loader` returns a single generator frame: once it raises, that
    frame is dead and cannot be resumed mid-shard (true per-record recovery
    would require re-driving the lower-level `tfrecord_iterator` byte reader
    ourselves). So an exception here always ends this shard's contribution;
    we warn (with the shard path and how many records were already yielded)
    so a genuinely truncated/corrupt shard is visible rather than silently
    dropped, instead of only relying on the empty-shard case being silent.

    One exception is retried rather than treated as terminal: some legacy
    shards serialize `y_raw_encoded` as a float feature while `_DESCRIPTION`
    declares it "int", which makes `tfrecord_loader` raise a TypeError before
    yielding anything. If that happens on the very first record of a fresh
    attempt (and `allow_float_yraw_retry` is True, see `iter_epochs`), we
    retry the whole shard once with `_DESCRIPTION_FLOAT_YRAW` (`y_raw_encoded`
    declared "float"); `_as_scalar_int` rounds it back to an int downstream.
    If records were already yielded before the failure (a genuinely
    mixed/corrupt shard, not this dtype mismatch), we do not retry (that
    would re-yield already-emitted records) and fall back to the
    warn-and-stop behavior.
    """
    description = _DESCRIPTION
    retried = False
    while True:
        n_yielded = 0
        try:
            for rec in tfrecord_loader(
                data_path=str(shard_path),
                index_path=None,  # never trust .idx: many are size-0/stale
                description=description,
            ):
                n_yielded += 1
                yield rec
            return
        except TypeError as exc:
            if (
                allow_float_yraw_retry
                and not retried
                and n_yielded == 0
                and "y_raw_encoded" in str(exc)
            ):
                description = _DESCRIPTION_FLOAT_YRAW
                retried = True
                continue
            warnings.warn(
                f"iter_epochs: shard read aborted after {n_yielded} record(s) "
                f"in {shard_path}: {exc!r}",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        except Exception as exc:
            warnings.warn(
                f"iter_epochs: shard read aborted after {n_yielded} record(s) "
                f"in {shard_path}: {exc!r}",
                RuntimeWarning,
                stacklevel=2,
            )
            return


def iter_epochs(subject_id: int, study: str) -> Iterator[dict]:
    """Yield one dict per stored FRP epoch across all TFRecord shards for a
    subject/study.

    Yields dicts with keys: subject_id, user_study, session, eeg
    (np.float32 [20, T]), pupil (np.float32 [2, T]), y (int 0/1), item_id
    (int), run (int), fix_time_s (float).

    Robust by construction: a subject/study with zero matching dirs, zero
    shards, or only empty/corrupt shards yields nothing rather than raising.

    Guard against a legacy-duplicate-directory trap uncovered by the
    `y_raw_encoded` float/int retry (see `_iter_shard_records`): for a couple
    of subjects (observed for 5 and 12 / us1), a `wingman/` subdirectory
    holds a *second*, float-`y_raw_encoded` copy of the exact same fixations
    already present (as working int-`y_raw_encoded` shards) directly under
    the study dir or under numbered session subdirs. Before the retry
    existed, that `wingman/` copy always failed to parse and was silently
    (and, in this specific case, harmlessly) dropped; blindly extending the
    retry to it would double-count every affected subject. So the retry is
    only allowed for a `wingman/`-parented shard when `wingman/` is this
    subject/study's *only* shard source (e.g. subject 4 / us1, which has no
    sibling directory at all): i.e. exactly the case the retry is meant to
    fix.

    Subjects whose `wingman/` and sibling copies were *both* already
    readable pre-retry (e.g. subject 18 / us1) never hit that TypeError
    (and hence never hit the retry-decision guard above), so a plain
    recursive glob ingested both int-encoded copies of every shard, doubling
    every extracted epoch. `_dedup_wingman_source_shards` removes that
    duplicate source (see its docstring) before shards are read, independent
    of the float-retry guard.
    """
    for study_dir in _resolve_study_dirs(subject_id, study):
        all_shards = _dedup_wingman_source_shards(sorted(study_dir.rglob("*.tfrecord")))
        has_sibling_source = any(
            p.parent.name != "wingman"
            and not p.name.startswith(_BACKUP_PREFIXES)
            and p.stat().st_size > 0
            for p in all_shards
        )

        for shard_path in all_shards:
            if shard_path.name.startswith(_BACKUP_PREFIXES):
                continue  # pre-fix backup shard: stale/buggy labels, never ingest
            if shard_path.stat().st_size == 0:
                continue  # fast path for the common empty-shard case

            session = _session_from_shard(shard_path)
            allow_float_yraw_retry = not (
                shard_path.parent.name == "wingman" and has_sibling_source
            )

            for rec in _iter_shard_records(shard_path, allow_float_yraw_retry):
                try:
                    eeg = _reshape_signal(
                        rec["eeg"], rec.get("eeg.shape"), EEG_N_CH, EEG_N_T_DEFAULT
                    ).astype(np.float32, copy=False)
                    pupil = _reshape_signal(
                        rec["pupil_size"], rec.get("pupil_size.shape"), PUPIL_N_CH, PUPIL_N_T_DEFAULT
                    ).astype(np.float32, copy=False)
                    y = _decode_y(rec["y_raw_encoded"])
                    item_id = _as_scalar_int(rec["item_id"])
                    run = _as_scalar_int(rec["run"])
                    fix_time_s = _as_scalar_float(rec["fix_time_s"])
                except (KeyError, ValueError, IndexError):
                    # Malformed individual record: skip it, keep the shard going.
                    continue

                yield {
                    "subject_id": subject_id,
                    "user_study": study,
                    "session": session,
                    "eeg": eeg,
                    "pupil": pupil,
                    "y": y,
                    "item_id": item_id,
                    "run": run,
                    "fix_time_s": fix_time_s,
                }
