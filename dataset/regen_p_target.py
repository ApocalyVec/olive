"""
Regenerate per-fixation p_target probabilities using the default implicit-evidence decoder.

This module provides deterministic sampling of target probabilities for FRP epochs,
caching decoders per subject to avoid repeated file I/O.
"""

from functools import lru_cache
from typing import Optional
import math

from release.olive.decode import load_default_decoder, DefaultDecoder
from release.common.cohort import PTARGET_SEED


@lru_cache(maxsize=128)
def _get_decoder_cached(subject_id: int) -> Optional[DefaultDecoder]:
    """
    Load and cache the default decoder for a subject.

    Returns None if the subject has no eeg_pred_beta.json file,
    avoiding crashes for subjects without EEG data.

    Args:
        subject_id: Participant ID

    Returns:
        DefaultDecoder instance, or None if file not found
    """
    try:
        decoder = load_default_decoder(subject_id, priors_root='eeg_priors')
        return decoder
    except (FileNotFoundError, IOError, OSError):
        # Subject has no EEG priors file; return None to signal NaN output
        return None


def p_target_for_epoch(subject_id: int, item_dtn: int, idx: int) -> tuple[float, float]:
    """
    Regenerate p_target probability for a single FRP epoch.

    Deterministic given (subject_id, item_dtn, idx) via seed = PTARGET_SEED + idx.
    For subjects without an EEG priors file, returns (NaN, NaN).

    Args:
        subject_id: Participant ID
        item_dtn: Item DTN (1 for non-target, 2 for target)
        idx: Epoch index, used to derive the random seed

    Returns:
        Tuple of (p_target, quality) where:
            - p_target: Probability that item is target, in [0.0, 1.0] (or NaN if no priors)
            - quality: Quality measure (AUC) in [0.4, 1.0] (or NaN if no priors)
    """
    decoder = _get_decoder_cached(subject_id)

    if decoder is None:
        # No EEG priors file for this subject
        return (float('nan'), float('nan'))

    # Deterministic seed based on PTARGET_SEED and epoch index
    seed = PTARGET_SEED + idx

    # Decode with the deterministic seed
    p_target, quality = decoder.decode(item_dtn, seed=seed)

    return (p_target, quality)
