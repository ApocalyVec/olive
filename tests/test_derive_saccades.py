import json
import math
from pathlib import Path

import numpy as np
import pytest

from release.dataset.derive_saccades import (
    _DEFAULT_PRE_WINDOW_S,
    _OFFSET_TOL_S,
    _detect_saccades,
    _resolve_gaze_forward_rows,
    _select_incoming_saccade,
    incoming_saccade,
    load_p_streams,
)


def _a_small_us1_p_path() -> str:
    """Resolve one small us1 `.p` recording under `~/wingman`.

    Subject 7's numbered session dirs (`us1/0`, `us1/1`, `us1/2`) are the
    smallest known `Exp_wingman_us1` recordings on disk (tens of MB, vs. up
    to ~3GB for other subjects), so restrict the search to subject 7 and
    take the smallest match to keep this test fast and light on memory.
    """
    root = Path.home() / "wingman" / "7" / "us1"
    candidates = list(root.rglob("*Exp_wingman_us1*.p"))
    if not candidates:
        pytest.skip("no local ~/wingman/7/us1 .p recordings found")
    return str(min(candidates, key=lambda p: p.stat().st_size))


def _real_t_onsets_for_small_p() -> list[float]:
    """Every `gaze_events[].t_onset` from the `long_gaze.jsonl` blocks that
    belong to the same session (`~/wingman/7/us1/1`) as `_a_small_us1_p_path`.
    """
    session_dir = Path.home() / "wingman" / "7" / "us1" / "1"
    t_onsets: list[float] = []
    for long_gaze_path in session_dir.glob("*/long_gaze.jsonl"):
        for line in long_gaze_path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            for g in obj.get("gaze_events", []):
                t_onsets.append(g["t_onset"])
    if not t_onsets:
        pytest.skip("no local long_gaze.jsonl fixation onsets found for ~/wingman/7/us1/1")
    return t_onsets


def test_p_has_gaze_and_head():
    s = load_p_streams(_a_small_us1_p_path())
    assert "Unity.VarjoEyeTrackingComplete" in s and "Unity.HeadTracker" in s
    varjo, ts = s["Unity.VarjoEyeTrackingComplete"]
    assert varjo.shape[0] in (34, 35) and varjo.shape[1] == ts.shape[0]


def test_incoming_saccade_on_real_recording_returns_well_formed_floats():
    s = load_p_streams(_a_small_us1_p_path())
    varjo = s["Unity.VarjoEyeTrackingComplete"]
    head = s["Unity.HeadTracker"]
    _, ts = varjo

    # A t_onset squarely inside the recording (away from both edges) should
    # have enough pre-onset samples to attempt saccade detection -- the
    # result may still legitimately be all-NaN if no saccade is found in
    # the window, but every key must be present and every value a float.
    t_onset = float(ts[len(ts) // 2])
    result = incoming_saccade(varjo, head, t_onset)

    assert set(result.keys()) == {"amplitude", "angle", "peak_velocity", "mean_velocity", "dx", "dy"}
    for v in result.values():
        assert isinstance(v, float)


def test_incoming_saccade_never_selects_a_saccade_after_t_onset():
    """
    Fix-round-1 regression test for the "incoming saccade selected an
    outgoing saccade" bug: on real fixation onsets, re-derive the same
    candidate `incoming_saccade` would pick (via the private helpers it
    calls internally) and assert its offset_time never lands after
    `t_onset + _OFFSET_TOL_S`. Also cross-checks that `incoming_saccade`'s
    public result is non-NaN exactly when a qualifying candidate exists.
    """
    p_path = _a_small_us1_p_path()
    s = load_p_streams(p_path)
    varjo = s["Unity.VarjoEyeTrackingComplete"]
    head = s["Unity.HeadTracker"]
    data, ts = varjo

    t_onsets = _real_t_onsets_for_small_p()
    assert len(t_onsets) > 10  # sanity: the fixture actually exercises many onsets

    gaze_rows = _resolve_gaze_forward_rows(data)
    assert gaze_rows is not None

    checked_non_nan = 0
    for t_onset in t_onsets:
        result = incoming_saccade(varjo, head, t_onset)
        is_nan_result = math.isnan(result["amplitude"])

        mask = (ts >= t_onset - _DEFAULT_PRE_WINDOW_S) & (ts <= t_onset)
        sub_ts = ts[mask]
        sub_xyz = data[gaze_rows][:, mask]
        order = np.argsort(sub_ts, kind="stable")
        sub_ts, sub_xyz = sub_ts[order], sub_xyz[:, order]
        keep = np.concatenate([[True], np.diff(sub_ts) > 0])
        sub_ts, sub_xyz = sub_ts[keep], sub_xyz[:, keep]

        saccades = _detect_saccades(sub_xyz, sub_ts) if sub_ts.shape[0] >= 8 else []
        candidate = _select_incoming_saccade(saccades, t_onset)

        # The core fix: whenever incoming_saccade derived a real (non-NaN)
        # result, the saccade it selected must not land after t_onset.
        assert is_nan_result == (candidate is None)
        if candidate is not None:
            assert candidate.offset_time <= t_onset + _OFFSET_TOL_S
            checked_non_nan += 1

    assert checked_non_nan > 0  # the fixture must exercise at least one real derivation


def test_incoming_saccade_missing_window_is_all_nan():
    s = load_p_streams(_a_small_us1_p_path())
    varjo = s["Unity.VarjoEyeTrackingComplete"]
    head = s["Unity.HeadTracker"]
    _, ts = varjo

    # t_onset far before the recording starts -> no pre-onset samples at all.
    result = incoming_saccade(varjo, head, float(ts.min()) - 1000.0)
    assert all(math.isnan(v) for v in result.values())


def _make_synthetic_varjo(fs=200.0, n=400, fix_a_end=150, saccade_samples=10):
    """
    Build a synthetic 35-channel Varjo stream: a unit gaze-forward vector
    that holds still (fixation A), slerps to a new direction over
    `saccade_samples` samples (the incoming saccade), then holds still
    again (fixation B). Channels other than gaze_forward_x/y/z (rows 7,8,9,
    matching rlpf.params.params.varjoEyetracking_chs) and status (row 5)
    are left at zero -- they are not read by `incoming_saccade`.
    """
    ts = np.arange(n) / fs

    def unit(v):
        v = np.asarray(v, dtype=float)
        return v / np.linalg.norm(v)

    a = unit([0.0, 0.0, 1.0])
    b = unit([0.4, 0.2, 1.0])  # ~24 deg away from `a`
    sac_end = fix_a_end + saccade_samples

    gaze = np.zeros((3, n))
    gaze[:, :fix_a_end] = a[:, None]
    omega = np.arccos(np.clip(np.dot(a, b), -1.0, 1.0))
    for i in range(fix_a_end, sac_end):
        t = (i - fix_a_end) / saccade_samples
        gaze[:, i] = (np.sin((1 - t) * omega) * a + np.sin(t * omega) * b) / np.sin(omega)
    gaze[:, sac_end:] = b[:, None]

    data = np.zeros((35, n))
    data[7], data[8], data[9] = gaze[0], gaze[1], gaze[2]
    data[5] = 2.0  # valid status
    return (data, ts), sac_end


def test_incoming_saccade_synthetic_gaze_jump_is_derived():
    varjo, sac_end = _make_synthetic_varjo()
    _, ts = varjo
    head = (np.zeros((9, ts.shape[0])), ts)

    t_onset = float(ts[sac_end])
    result = incoming_saccade(varjo, head, t_onset)

    for v in result.values():
        assert not math.isnan(v)
    assert result["amplitude"] > 0.0
    assert result["peak_velocity"] > 0.0
    assert result["mean_velocity"] > 0.0
    # the synthetic jump moves toward +x/+y, so both components should be positive.
    assert result["dx"] > 0.0
    assert result["dy"] > 0.0
    assert result["angle"] == pytest.approx(math.atan2(result["dy"], result["dx"]))


def test_incoming_saccade_malformed_varjo_is_all_nan():
    head = (np.zeros((9, 3)), np.array([0.0, 1.0, 2.0]))
    result = incoming_saccade((np.zeros((3, 3)), np.array([0.0, 1.0, 2.0])), head, 1.0)
    assert all(math.isnan(v) for v in result.values())
