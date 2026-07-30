"""
Incoming-saccade kinematics derived from the raw `.p` eye-tracking recordings.

Each Wingman session is dumped as a pickled dict of
`{stream_name: (data[channels, samples], timestamps[samples])}` (protocol-4
pickle written by the ReNa recorder, NOT the RNStream `.dats` container --
`rlpf.utils.RNStream` does not parse these files and should not be used
here).

For every fixation onset (`gaze_events[].t_onset` in `long_gaze.jsonl`,
already in the same LSL clock as the Varjo stream timestamps) we want the
kinematics of the saccade that *produced* that fixation, i.e. the saccade
immediately preceding `t_onset`. This module locates that saccade in the raw
`Unity.VarjoEyeTrackingComplete` stream and reports its amplitude/velocity
(via `rlpf.eye.eyetracking`'s I-VT/I-DT + `Saccade` machinery -- the
amplitude/velocity physics is not reimplemented here) together with
`dx`/`dy`/`angle`, which are derived directly from the change in the
gaze-forward unit vector across the saccade (the `Saccade` class does not
carry these fields).

Channel layout caveat: `rlpf.params.params.varjoEyetracking_chs` is meant to
name every channel in the `Unity.VarjoEyeTrackingComplete` stream, but real
recordings have been observed with a channel count that does not exactly
match `len(varjoEyetracking_chs)`. Rather than trust the list index blindly,
`_resolve_gaze_forward_rows` searches a small range of index shifts and picks
the one whose 3 candidate rows form a unit-norm vector (as a unit gaze
direction must).
"""

from __future__ import annotations

import math
import pickle
import warnings
from typing import Optional

import numpy as np

from rlpf.eye.eyetracking import fixation_detection_i_dt, fixation_detection_i_vt
from rlpf.params.params import varjoEyetracking_chs

_GAZE_FORWARD_NAMES = ("gaze_forward_x", "gaze_forward_y", "gaze_forward_z")

# How far (in index positions) the real channel layout is allowed to drift
# from rlpf.params.params.varjoEyetracking_chs before we give up on it.
_MAX_INDEX_SHIFT = 2

# A candidate gaze-forward triplet must have a median |norm - 1| below this
# to be accepted as the real gaze-forward vector.
_UNIT_NORM_TOLERANCE = 0.05

# Default window (seconds) of samples looked at *before* a fixation onset
# when hunting for its incoming saccade. The window ends AT t_onset (no
# look-ahead) -- the brief's hard constraint is "samples BEFORE t_onset",
# and a look-ahead window let the detector occasionally pick an outgoing
# saccade (one that starts at/after t_onset) as if it were incoming.
_DEFAULT_PRE_WINDOW_S = 0.5
_MIN_WINDOW_SAMPLES = 8

# A detected saccade's offset (landing) time is allowed to exceed t_onset by
# at most this much and still be considered "incoming" -- this only absorbs
# floating-point/index-to-time rounding noise from the detector, since the
# analysis window itself never contains samples after t_onset.
_OFFSET_TOL_S = 0.005

_NAN_RESULT = {
    "amplitude": float("nan"),
    "angle": float("nan"),
    "peak_velocity": float("nan"),
    "mean_velocity": float("nan"),
    "dx": float("nan"),
    "dy": float("nan"),
}


def load_p_streams(p_path) -> dict:
    """
    Load a session's `.p` recording.

    The file is a protocol-4 pickle of `{stream_name: (data, timestamps)}`.
    Returns the dict unmodified -- callers index into it by stream name
    (e.g. 'Unity.VarjoEyeTrackingComplete', 'Unity.HeadTracker').
    """
    with open(p_path, "rb") as f:
        return pickle.load(f)


def _resolve_gaze_forward_rows(data: np.ndarray) -> Optional[np.ndarray]:
    """
    Find the row indices of gaze_forward_x/y/z in `data`.

    Starts from the index implied by `varjoEyetracking_chs` and tries small
    shifts around it, accepting the shift whose 3 rows have the smallest
    median deviation from unit norm (computed over samples where the row
    triplet is not all-zero/NaN, i.e. valid gaze samples).
    """
    n_ch = data.shape[0]
    base = [varjoEyetracking_chs.index(name) for name in _GAZE_FORWARD_NAMES]

    best_idx = None
    best_score = np.inf
    for shift in range(-_MAX_INDEX_SHIFT, _MAX_INDEX_SHIFT + 1):
        idx = [b + shift for b in base]
        if min(idx) < 0 or max(idx) >= n_ch:
            continue
        rows = data[idx, :]
        norm = np.linalg.norm(rows, axis=0)
        valid = norm[np.isfinite(norm) & (norm > 1e-6)]
        if valid.size == 0:
            continue
        score = float(np.median(np.abs(valid - 1.0)))
        if score < best_score:
            best_score = score
            best_idx = idx

    if best_idx is None or best_score > _UNIT_NORM_TOLERANCE:
        return None
    return np.array(best_idx)


def incoming_saccade(
    varjo,
    head,
    t_onset: float,
    pre_window_s: float = _DEFAULT_PRE_WINDOW_S,
) -> dict:
    """
    Kinematics of the saccade landing on the fixation that starts at `t_onset`.

    @param varjo: `(data[channels, samples], timestamps[samples])` for the
        'Unity.VarjoEyeTrackingComplete' stream, in the same clock as
        `t_onset`.
    @param head: `(data[channels, samples], timestamps[samples])` for the
        'Unity.HeadTracker' stream. Accepted for interface symmetry with the
        session's stream dict; head-rotation compensation is not applied in
        this derivation (kept out to avoid brittle resampling over the short
        pre-onset windows used here) -- amplitude/velocity are computed on
        raw (non-head-corrected) gaze angles, matching
        `fixation_detection_i_vt`/`_i_dt`'s default (`head_rotation_xy_degree=None`).
    @param t_onset: fixation onset timestamp, LSL clock (same clock as
        `varjo`'s timestamps -- NOT the `long_gaze.jsonl` record wrapper's
        unix-epoch `timestamp` field). The analysis window is
        `[t_onset - pre_window_s, t_onset]` -- strictly samples BEFORE (or
        at) `t_onset`, never after, so an outgoing saccade of the same
        fixation cannot be mistaken for the incoming one.
    @return: dict with float keys amplitude, angle, peak_velocity,
        mean_velocity, dx, dy. Any/all are `nan` when the incoming saccade
        cannot be derived (missing/too-short window, no channel layout
        match, no saccade detected before `t_onset`, non-finite gaze samples
        at the saccade boundary).
    """
    del head  # accepted for interface symmetry; see docstring.

    try:
        data, ts = varjo
        data = np.asarray(data, dtype=float)
        ts = np.asarray(ts, dtype=float)
    except (TypeError, ValueError):
        return dict(_NAN_RESULT)

    if data.ndim != 2 or ts.ndim != 1 or data.shape[1] != ts.shape[0] or ts.shape[0] == 0:
        return dict(_NAN_RESULT)

    gaze_rows = _resolve_gaze_forward_rows(data)
    if gaze_rows is None:
        return dict(_NAN_RESULT)

    # No look-ahead: the window never contains samples after t_onset, so any
    # saccade detected inside it necessarily precedes (or lands at) t_onset.
    mask = (ts >= t_onset - pre_window_s) & (ts <= t_onset)
    if int(np.count_nonzero(mask)) < _MIN_WINDOW_SAMPLES:
        return dict(_NAN_RESULT)

    sub_ts = ts[mask]
    sub_xyz = data[gaze_rows][:, mask]

    # fixation_detection_i_vt/i_dt require strictly increasing timestamps.
    order = np.argsort(sub_ts, kind="stable")
    sub_ts = sub_ts[order]
    sub_xyz = sub_xyz[:, order]
    keep = np.concatenate([[True], np.diff(sub_ts) > 0])
    sub_ts = sub_ts[keep]
    sub_xyz = sub_xyz[:, keep]
    if sub_ts.shape[0] < _MIN_WINDOW_SAMPLES:
        return dict(_NAN_RESULT)

    saccades = _detect_saccades(sub_xyz, sub_ts)
    candidate = _select_incoming_saccade(saccades, t_onset)
    if candidate is None:
        return dict(_NAN_RESULT)

    onset_i, offset_i = candidate.onset, candidate.offset
    n_samples = sub_xyz.shape[1]
    if not (0 <= onset_i < n_samples and 0 <= offset_i < n_samples):
        return dict(_NAN_RESULT)

    v_onset = sub_xyz[:, onset_i]
    v_offset = sub_xyz[:, offset_i]
    if not (np.all(np.isfinite(v_onset)) and np.all(np.isfinite(v_offset))):
        dx = dy = angle = float("nan")
    else:
        delta = v_offset - v_onset
        dx = float(delta[0])
        dy = float(delta[1])
        angle = float(math.atan2(dy, dx))

    return {
        "amplitude": float(candidate.amplitude),
        "angle": angle,
        "peak_velocity": float(candidate.peak_velocity),
        "mean_velocity": float(candidate.average_velocity),
        "dx": dx,
        "dy": dy,
    }


def _select_incoming_saccade(saccades, t_onset: float, tol: float = _OFFSET_TOL_S):
    """
    Pick the incoming saccade for a fixation starting at `t_onset` out of a
    list of detected `Saccade` objects.

    Only candidates that land at or before `t_onset` (within `tol`, to
    absorb detector index-to-time rounding noise) qualify -- a saccade whose
    offset is after `t_onset` is an outgoing saccade of some other fixation,
    not the one that produced this one. Among qualifying candidates, the one
    with the latest `offset_time` is the saccade immediately into this
    fixation. Returns `None` if no candidate qualifies.

    Exposed at module level (rather than inlined in `incoming_saccade`) so
    tests can independently verify the "offset_time <= t_onset + tol"
    invariant against real detected saccades.
    """
    qualifying = [s for s in saccades if s.offset_time <= t_onset + tol]
    if not qualifying:
        return None
    return max(qualifying, key=lambda s: s.offset_time)


def _detect_saccades(sub_xyz: np.ndarray, sub_ts: np.ndarray):
    """Try I-VT first, fall back to I-DT; both return `Saccade` objects."""
    saccades = []
    try:
        _, _, saccades, _ = fixation_detection_i_vt(sub_xyz, sub_ts)
    except Exception as exc:
        warnings.warn(
            f"incoming_saccade: fixation_detection_i_vt failed on a "
            f"{sub_xyz.shape[1]}-sample window ({exc!r}); falling back to I-DT",
            RuntimeWarning,
        )
    if saccades:
        return saccades
    try:
        _, _, saccades, _ = fixation_detection_i_dt(sub_xyz, sub_ts)
    except Exception as exc:
        warnings.warn(
            f"incoming_saccade: fixation_detection_i_dt failed on a "
            f"{sub_xyz.shape[1]}-sample window ({exc!r}); returning no saccades",
            RuntimeWarning,
        )
        saccades = []
    return saccades
