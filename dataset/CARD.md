# OLIVE Release FRP Dataset — Card

## What this is

Per-fixation, fixation-related-potential (FRP) examples assembled from the OLIVE
Wingman / SpaceShooter user studies (US1 offline simulation, US2 live deployment,
US3 silent target-switch), for the release cohort of 27
participants (`release.common.cohort.RELEASE_SUBJECTS`). Assembled by
`release/dataset/export_hf.py::build_examples`, which composes the already-committed
Tasks 2.1-2.4 modules (epoch extraction, p_target regeneration, saccade derivation,
condition/block metadata) without reimplementing any of their logic.

## Fields (one row per fixation-locked epoch)

| field | type | description |
|---|---|---|
| `subject_id` | int | participant id |
| `user_study` | str | `us1` / `us2` / `us3` |
| `session` | int | recording-session index within (subject, study); usually `0` |
| `eeg` | float32[20, 230] | fixation-locked EEG epoch, see montage/window below |
| `pupil` | float32[2, 80] | fixation-locked pupil-diameter epoch (left/right), see window below |
| `y` | int (0/1) | ground-truth fixated-item label (1 = target) |
| `p_target` | float in [0,1] or NaN | per-fixation implicit-evidence target probability (in [0,1]); NaN where per-subject EEG-evidence parameters are unavailable |
| `p_target_quality` | float in [0.4,1.0] or NaN | per-subject decoder quality (AUC), or NaN |
| `item_id` | int | fixated item id within its block |
| `run` | int | 1-indexed fixation-generating-block counter from the TFRecord (`block_idx = run - 1`, see caveat below) |
| `fixation_duration` | float seconds or NaN | fixation duration from `long_gaze.jsonl`; NaN unless `with_saccades=True` and the join matched |
| `saccade_amplitude` | float degrees or NaN | incoming-saccade amplitude; NaN unless `with_saccades=True` and derivable |
| `saccade_angle` | float radians or NaN | incoming-saccade direction (`atan2(dy, dx)`) |
| `saccade_peak_velocity` | float deg/s or NaN | incoming-saccade peak velocity |
| `saccade_mean_velocity` | float deg/s or NaN | incoming-saccade mean velocity |
| `saccade_dx`, `saccade_dy` | float or NaN | gaze-forward-vector delta components across the incoming saccade |
| `condition` | str | primary, as-published condition label (`IE` / `E`) -- **use this for any published-table-facing analysis** |
| `condition_ra` | str or None | secondary RA-proposed overlay label; **UNRESOLVED, does not match published tables**, transparency/audit only |
| `block_idx` | int | 0-indexed block within (subject, study, session); `-1` if not derivable (see caveat) |
| `difficulty` | int | adaptive difficulty level for `block_idx`, from `meta.jsonl`; `-1` if not found |

`block_idx` caveat: `iter_epochs` does not carry a literal block index field. `run`
was verified empirically (against on-disk `meta.jsonl`/block-directory counts for
multiple subjects across us1/us2/us3) to be a 1-indexed running block counter, so
`block_idx = run - 1` is used. This has not been verified for every subject/session;
treat `block_idx`/`difficulty` as best-effort, not a guaranteed-exact join.

## EEG montage and epoch windows

- **EEG**: 20-channel B-Alert X24 subset, standard 10-20 layout, sampled at 256 Hz.
  Epoch window is fixation-onset-locked `[-0.1, 0.8]` s → 230 samples/channel.
- **Pupil**: 2-channel (left/right) pupil diameter, sampled at 20 Hz. Epoch window is
  fixation-onset-locked `[-1.0, 3.0]` s → 80 samples/channel.
- Both windows match `release/dataset/extract_epochs.py`'s `EEG_N_T_DEFAULT` /
  `PUPIL_N_T_DEFAULT` constants (reused, not redefined, here).

## Condition legend

- `condition` (primary, as-published): `IE` = Implicit+Explicit (EEG + shot events),
  `E` = Explicit-only (shot events, no EEG). This is the label used throughout the
  paper's published tables and figures.
- `condition_ra`: a secondary v1 RA-proposed relabeling overlay (adds `Oracle` /
  `Control` labels for a handful of subjects) that is **UNRESOLVED against the
  published cohort and does not match the paper's tables** (see
  `release/dataset/attach_metadata.py`'s module docstring and `_RA_OVERRIDES`).
  Included for transparency/auditing only -- always prefer `condition` for anything
  that should agree with the paper.

## `p_target` generation

`p_target` is the per-fixation implicit-evidence target probability produced by the default decoder in `release/olive/decode.py` (`DefaultDecoder`), which reads per-subject parameters under `eeg_priors/`. It is `NaN` for subjects/rows without available parameters. Replace the decoder with your own — see the repository README.

## Coverage

Built from subjects=[4, 5, 12, 18, 20, 28, 29, 31, 33, 34, 35, 36, 37, 39, 40, 46, 47, 48, 49, 51, 52, 53, 54, 55, 59, 61, 63], studies=['us1', 'us2', 'us3'],
with_saccades=False.

- Total examples: 58184
- Target-label rate (`y==1`): 0.5735 (33371 target / 24813 non-target)
- `p_target` valid (non-NaN): 27445 rows, mean=0.5111; NaN: 30739 rows
- `p_target_quality` (valid rows): mean=0.7615, range=[0.5375, 0.9018]
- Subjects with zero examples across all studies: 2 ([61, 63])
- Subjects with >0 examples in at least one study: 25 ([4, 5, 12, 18, 20, 28, 29, 31, 33, 34, 35, 36, 37, 39, 40, 46, 47, 48, 49, 51, 52, 53, 54, 55, 59])

Full per-subject x per-study counts: see `coverage.csv` (same directory as
this card). Table (subject_id x study, `total` = row sum):

| subject_id | us1 | us2 | us3 | total |
|---|---|---|---|---|
| 4 | 725 | 925 | 1046 | 2696 |
| 5 | 591 | 0 | 0 | 591 |
| 12 | 564 | 0 | 863 | 1427 |
| 18 | 796 | 745 | 0 | 1541 |
| 20 | 1071 | 1407 | 994 | 3472 |
| 28 | 840 | 867 | 863 | 2570 |
| 29 | 633 | 901 | 1025 | 2559 |
| 31 | 520 | 0 | 0 | 520 |
| 33 | 662 | 598 | 560 | 1820 |
| 34 | 997 | 1109 | 1305 | 3411 |
| 35 | 778 | 1023 | 1217 | 3018 |
| 36 | 1022 | 1332 | 1466 | 3820 |
| 37 | 1014 | 932 | 1026 | 2972 |
| 39 | 1226 | 1755 | 1609 | 4590 |
| 40 | 875 | 693 | 795 | 2363 |
| 46 | 783 | 0 | 1217 | 2000 |
| 47 | 612 | 0 | 0 | 612 |
| 48 | 1412 | 2049 | 1593 | 5054 |
| 49 | 759 | 1961 | 1488 | 4208 |
| 51 | 1049 | 1332 | 798 | 3179 |
| 52 | 607 | 0 | 0 | 607 |
| 53 | 1013 | 1473 | 0 | 2486 |
| 54 | 946 | 0 | 0 | 946 |
| 55 | 924 | 0 | 0 | 924 |
| 59 | 798 | 0 | 0 | 798 |
| 61 | 0 | 0 | 0 | 0 |
| 63 | 0 | 0 | 0 | 0 |

## Saccade fields caveat (`with_saccades`)

`saccade_*` and `fixation_duration` are **all-NaN by default**
(`with_saccades=False`). Deriving them requires loading a session's raw `.p`
eye-tracking recording (up to ~1-3GB) and joining each epoch's TFRecord-clock
`fix_time_s` against `long_gaze.jsonl`'s LSL-clock `t_onset` by nearest-match within
`item_id`, subject to a tolerance (default 1.0s) --
**these two clocks are not guaranteed to share an origin**, so even with
`with_saccades=True`, a session whose clocks do not align will legitimately yield
all-NaN saccade fields for every epoch in that session; this is a documented
limitation of the join, not a bug. A second caveat: for the small number of subjects
with multiple numbered "session" subdirectories under one study directory but only
one physical `.p` file at the study-directory root (observed for subject 5 / us1),
the join falls back to that one shared `.p` for every session under that study
directory, which can pool fixation events across sessions. See
`release/dataset/export_hf.py`'s module docstring for full detail.

## Consent

All participants in `RELEASE_SUBJECTS` provided informed consent under the study's
IRB protocol for their de-identified physiological (EEG, pupil), behavioral, and
gaze data to be included in a public research dataset release. No directly
identifying information (name, contact info, raw video) is included in this export;
`subject_id` is a study-internal integer id, not a real-world identifier.

## License

**TBD** -- placeholder: CC-BY-4.0 (pending final confirmation from the study PI /
IRB before public release).

## Citation

**Placeholder** -- update with the final paper citation before public release:

```
@inproceedings{olive-frp-2026,
  title     = {OLIVE: [paper title TBD]},
  author    = {[authors TBD]},
  booktitle = {[venue TBD]},
  year      = {2026},
}
```
