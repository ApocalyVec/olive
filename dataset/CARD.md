---
pretty_name: OLIVE FRP Dataset
license: cc-by-4.0
tags:
- eeg
- fixation-related-potentials
- pupillometry
- eye-tracking
- xr
- bci
- attention
size_categories:
- 10K<n<100K
configs:
- config_name: default
  data_files:
  - split: train
    path: data/frp_dataset.parquet
- config_name: ern
  data_files:
  - split: train
    path: data/ern.parquet
---

# OLIVE FRP Dataset

## What this is

Per-fixation, fixation-related-potential (FRP) examples from the OLIVE
Wingman / SpaceShooter user studies (US1 offline simulation, US2 live deployment,
US3 silent target-switch), for the release cohort of 25 participants.
Each example pairs a fixation-locked EEG epoch and pupil epoch with its target label,
incoming-saccade metadata, per-fixation implicit-evidence probability, and
condition and block information.

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

Built from subjects=[4, 5, 12, 18, 20, 28, 29, 31, 33, 34, 35, 36, 37, 39, 40, 46, 47, 48, 49, 51, 52, 53, 54, 55, 59], studies=['us1', 'us2', 'us3'],
with_saccades=False.

- Total examples: 58184
- Target-label rate (`y==1`): 0.4035 (23478 target / 34706 non-target)
- `p_target` valid (non-NaN): 18246 rows, mean=0.5059; NaN: 39938 rows
- `p_target_quality` (valid rows): mean=0.7669, range=[0.5375, 0.8851]
- Subjects with zero examples across all studies: 0 ([])
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

All participants in the published cohort provided informed consent under the study's
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

## ERN variant

A second HuggingFace config (`ern`), loadable via
`load_dataset("ApocalyVec/olive-frp", "ern")`, of per-shot response-locked
ERN (error-related negativity) epochs -- distinct from the fixation-locked
FRP epochs in the `default` config above.

### What this is

One row per in-game shot event (enemy hit = correct, friendly-fire hit =
error) from the OLIVE Wingman / SpaceShooter user studies (US1, US2, US3),
for the release cohort of 25 participants. Each row
is a single-trial, response-locked EEG epoch around the shot event, labeled
correct/error.

### Fields (one row per shot event)

| field | type | description |
|---|---|---|
| `subject_id` | int | participant id |
| `study` | str | `us1` / `us2` / `us3` |
| `session` | str | recording-session `.p` file stem |
| `eeg` | float32[20, 205] | response-locked EEG epoch, uV, see window below |
| `label` | int (0/1) | `0` = correct (enemy hit), `1` = error (friendly-fire hit) |
| `shot_time` | float | LSL timestamp of the shot event |
| `montage` | list[str] | B-Alert channel names, in `eeg` row order |
| `condition` | str | primary, as-published condition label (`IE` / `E`), same as the `default` config's `condition` field -- **use this for any published-table-facing analysis** |

### Epoch window and filtering

- **EEG**: 20-channel B-Alert X24 subset (same montage as the FRP
  config), sampled at 256 Hz.
- **Window**: response-locked (shot-event-locked) `[-200, 600]` ms →
  205 samples/channel.
- **Filter**: continuous zero-phase 4th-order Butterworth bandpass,
  0.5-30.0 Hz, applied to the full continuous recording *before*
  epoching (per-epoch filtering of an ~800 ms window is invalid for a
  0.5 Hz high-pass, which needs several seconds of settling).
- **Baseline window**: `[-200, 0]` ms (pre-response) is the
  conventional ERN baseline period included in the epoch; the exported `eeg`
  array is the filtered epoch as-is and is **not baseline-corrected** --
  apply baseline correction (subtract the `[-200, 0]` ms mean per
  channel) yourself if your analysis requires it.
- **Label convention**: shot events come from `Unity.ReNa.EventMarkers` row
  2 (DTN-coded); DTN==1 (friendly fire) → `label=1` (error), DTN==2 (enemy)
  → `label=0` (correct). Verified identical across US1/US2/US3 (see
  `release/dataset/ern/extract_ern.py`'s module docstring for the
  per-subject verification counts).

### Availability

Available for all three studies: US1 (offline simulation), US2 (live
deployment), US3 (silent target-switch). Coverage varies by
subject/study -- some subjects have zero epochs in a given study (no
session recorded, or no `.p` file with usable shot events); see the
coverage table below and `ern_coverage.csv` (same directory as this
card) for exact per-subject counts.

### Coverage

Built from subjects=[4, 5, 12, 18, 20, 28, 29, 31, 33, 34, 35, 36, 37, 39, 40, 46, 47, 48, 49, 51, 52, 53, 54, 55, 59], studies=['us1', 'us2', 'us3'].

- Total examples: 29178
- Error rate (`label==1`): 0.2352 (6864 error / 22314 correct)
- Subjects with zero examples across all studies: 1 ([47])
- Subjects with >0 examples in at least one study: 24 ([4, 5, 12, 18, 20, 28, 29, 31, 33, 34, 35, 36, 37, 39, 40, 46, 48, 49, 51, 52, 53, 54, 55, 59])

Full per-subject x per-study correct/error counts: see `ern_coverage.csv`.
Table (subject_id x study, `total` = row sum):

| subject_id | us1_correct | us1_error | us2_correct | us2_error | us3_correct | us3_error | total |
|---|---|---|---|---|---|---|---|
| 4 | 218 | 100 | 404 | 141 | 483 | 118 | 1464 |
| 5 | 224 | 120 | 0 | 0 | 0 | 0 | 344 |
| 12 | 158 | 80 | 0 | 0 | 0 | 0 | 238 |
| 18 | 190 | 85 | 327 | 199 | 0 | 0 | 801 |
| 20 | 162 | 81 | 388 | 190 | 412 | 117 | 1350 |
| 28 | 258 | 103 | 416 | 149 | 502 | 137 | 1565 |
| 29 | 291 | 143 | 544 | 215 | 651 | 148 | 1992 |
| 31 | 300 | 137 | 0 | 0 | 0 | 0 | 437 |
| 33 | 246 | 109 | 613 | 123 | 513 | 106 | 1710 |
| 34 | 362 | 89 | 683 | 111 | 573 | 115 | 1933 |
| 35 | 300 | 113 | 377 | 57 | 226 | 31 | 1104 |
| 36 | 427 | 95 | 697 | 120 | 687 | 85 | 2111 |
| 37 | 381 | 89 | 714 | 152 | 684 | 109 | 2129 |
| 39 | 273 | 123 | 651 | 232 | 566 | 210 | 2055 |
| 40 | 264 | 66 | 0 | 0 | 540 | 105 | 975 |
| 46 | 316 | 134 | 0 | 0 | 566 | 213 | 1229 |
| 47 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 48 | 305 | 109 | 627 | 228 | 605 | 165 | 2039 |
| 49 | 92 | 43 | 563 | 247 | 573 | 193 | 1711 |
| 51 | 229 | 84 | 438 | 142 | 392 | 140 | 1425 |
| 52 | 182 | 65 | 0 | 0 | 0 | 0 | 247 |
| 53 | 279 | 81 | 676 | 198 | 0 | 0 | 1234 |
| 54 | 313 | 114 | 0 | 0 | 0 | 0 | 427 |
| 55 | 240 | 119 | 0 | 0 | 0 | 0 | 359 |
| 59 | 213 | 86 | 0 | 0 | 0 | 0 | 299 |
