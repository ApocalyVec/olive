"""
Response-locked ERN (error-related negativity) epoch extractor for
US1/US2/US3.

Reuses the signal-processing core (continuous 0.5-30 Hz bandpass BEFORE
epoching, response-locked windowing, shot-event parsing) from
`analysis/repro/new_run/ern_utils.py::load_session` /
`ern_utils.py::extract_epochs`, imported directly rather than reimplemented.

Deviations from `ern_utils.load_session`, all path/interface generalizations
only (no signal-processing changes):
  - `BASE = '/media/nvme3/wingman'` (and the `/home/leo`-style paths some
    other repro scripts hardcode) is replaced with `Path.home() / "wingman"`,
    matching the layout used by `release/dataset/extract_epochs.py`.
  - The session directory is resolved as `<sid>/<study>*` (glob) instead of
    a hardcoded `'us1'` literal, so the same loader works for any study
    passed in.
  - `ern_utils.load_session` is a research-script loader: it prints
    diagnostics and returns None only when the `.p` file is missing. Here,
    `_load_session` is silent and additionally treats a missing/malformed
    `BAlert` or `Unity.ReNa.EventMarkers` stream, or a corrupt/unreadable
    pickle, as "no data" (returns None) rather than raising, per the
    "handle missing .p/streams gracefully" requirement for this extractor.

The epoching math itself (window, baseline convention, bandpass corners,
shot-event row/DTN semantics) is untouched: it is imported from
`ern_utils` (`_bandpass_continuous`) or reproduced verbatim inline
(`iter_ern_epochs`'s epoch-slicing loop mirrors `ern_utils.extract_epochs`).

US2/US3 support (task 4.2): `ern_utils.load_session` and the paper's US1
feasibility analysis only ever looked at US1 `.p` recordings. For v2 we
checked whether the same `Unity.ReNa.EventMarkers` row-2 shot-event /
DTN-in-{1,2} convention holds for US2 and US3 `.p` recordings too, by
loading full (non-truncated) US2/US3 sessions for subjects 4, 20, 28, 35
(chosen via `release/dataset/out/coverage.csv` for nonzero us2/us3 epoch
counts) directly with `pickle`/`numpy` (no code changes, read-only
inspection). Result: every one of those 8 US2/US3 `.p` files has a
`Unity.ReNa.EventMarkers` stream whose row 2 carries hundreds of nonzero
DTN-coded shot events (DTN==1 friendly fire / error, DTN==2 enemy /
correct), with the exact same semantics as US1 -- e.g. subject 4 us2: 141
DTN==1 + 404 DTN==2 (row2 nonzero count 545); subject 4 us3: 118 DTN==1 +
483 DTN==2 (601); subject 20 us2: 190/388; subject 20 us3: 117/412;
subject 28 us2: 149/416; subject 28 us3: 137/502; subject 35 us2: 57/377;
subject 35 us3: 31/226. So the epoching logic below (already
study-agnostic, since it only depends on `BAlert` + row-2 shot events
loaded via `<sid>/<study>*` glob) needed no signal-processing changes to
support `study in {"us1", "us2", "us3"}` -- only the docstring/type hints
were updated to state the extended scope explicitly.
"""

from __future__ import annotations

import pickle
import sys
import warnings
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

warnings.filterwarnings("ignore")

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analysis.repro.new_run.ern_utils import (  # noqa: E402
    BALERT_CHANNELS,
    EEG_N_CH,
    FS,
    N_SAMP,
    T_PRE,
    _bandpass_continuous,
)

WINGMAN_ROOT = Path.home() / "wingman"

# Shot events: Unity.ReNa.EventMarkers row index 2, nonzero = shot.
# DTN == 1 -> friendly fire (error, label 1); DTN == 2 -> enemy (correct, label 0).
_DTN_ERROR = 1
_DTN_CORRECT = 2


def _load_session(subject_id: int, study: str) -> Optional[dict]:
    """Load continuous bandpass-filtered EEG + shot events for one session.

    Generalized from `ern_utils.load_session`: study-parameterized session
    directory under `~/wingman/<sid>/<study>*/`, and silent (no prints,
    returns None instead of raising) on any missing/malformed data so the
    caller can degrade gracefully.
    """
    subj_dir = WINGMAN_ROOT / str(subject_id)
    study_dirs = sorted(subj_dir.glob(f"{study}*"))
    if not study_dirs:
        return None

    p_files: list[Path] = []
    for d in study_dirs:
        if d.is_dir():
            p_files.extend(sorted(d.glob("*.p")))
    if not p_files:
        return None

    p_path = p_files[0]
    try:
        with open(p_path, "rb") as f:
            data = pickle.load(f)
    except Exception:
        return None

    if "BAlert" not in data or "Unity.ReNa.EventMarkers" not in data:
        return None

    try:
        eeg_raw = data["BAlert"][0][:EEG_N_CH, :]
        eeg_ts = data["BAlert"][1]
        em_data = data["Unity.ReNa.EventMarkers"][0]
        em_ts = data["Unity.ReNa.EventMarkers"][1]
    except (KeyError, IndexError, TypeError):
        return None

    if eeg_raw.shape[0] != EEG_N_CH or eeg_raw.shape[1] == 0:
        return None

    # Continuous bandpass BEFORE epoching (per-epoch filtering of ~800ms
    # windows is invalid for a 0.5 Hz high-pass, which needs ~6s settling).
    eeg_filt = _bandpass_continuous(eeg_raw, lo=0.5, hi=30.0)

    mask = em_data[2] != 0
    shot_ts = em_ts[mask]
    shot_dtn = em_data[2][mask].astype(int)

    return dict(
        session=p_path.stem,
        eeg_filt=eeg_filt,
        eeg_ts=eeg_ts,
        shot_ts=shot_ts,
        shot_dtn=shot_dtn,
    )


def iter_ern_epochs(subject_id: int, study: str = "us1") -> Iterator[dict]:
    """Yield response-locked ERN epochs for one subject/study.

    `study` may be "us1", "us2", or "us3": the shot-event convention
    (`Unity.ReNa.EventMarkers` row 2, DTN==1 friendly-fire/error, DTN==2
    enemy/correct) was verified to hold identically across all three
    studies (see module docstring for the per-subject counts checked), so
    the epoching below is study-agnostic -- it just resolves the session
    directory as `<sid>/<study>*` and epochs whatever row-2 events it
    finds.

    Each yielded dict:
      subject_id : int
      study      : str
      session    : str            -- session .p file stem
      eeg        : np.float32[20, ~205]  -- bandpass-filtered epoch, uV
      label      : int            -- 1 = error (friendly fire), 0 = correct (enemy)
      shot_time  : float          -- LSL timestamp of the shot event
      montage    : list[str]      -- B-Alert channel names, in eeg row order

    Yields nothing (no crash) if the `.p` file or required streams
    (`BAlert`, `Unity.ReNa.EventMarkers`) are missing or malformed.
    """
    session = _load_session(subject_id, study)
    if session is None:
        return

    eeg = session["eeg_filt"]
    eeg_ts = session["eeg_ts"]
    shot_ts = session["shot_ts"]
    shot_dtn = session["shot_dtn"]
    pre_samp = int(round(abs(T_PRE) * FS))

    montage = list(BALERT_CHANNELS)

    for ts, dtn in zip(shot_ts, shot_dtn):
        if dtn not in (_DTN_ERROR, _DTN_CORRECT):
            continue
        idx = int(np.searchsorted(eeg_ts, ts, side="left"))
        start = idx - pre_samp
        end = start + N_SAMP
        if start < 0 or end > eeg.shape[1]:
            continue
        epoch = eeg[:, start:end].astype(np.float32)
        label = 1 if dtn == _DTN_ERROR else 0
        yield dict(
            subject_id=subject_id,
            study=study,
            session=session["session"],
            eeg=epoch,
            label=label,
            shot_time=float(ts),
            montage=montage,
        )
