"""
This module provides the default per-fixation implicit-evidence decoder and a
Decoder Protocol; replace DefaultDecoder with your own decoder (see README).
"""

from typing import Protocol, Optional
import os
import json
import numpy as np


class _ParamPredictor:
    """
    Loads per-subject parameters from eeg_pred_beta.json and returns per-fixation
    target probabilities.
    """
    def __init__(self, dist_json_path: str):
        with open(dist_json_path, "r") as f:
            d = json.load(f)
        self.state_dict = d
        self.target_label = int(d["target_label"])
        self.params = d["beta_params"]
        self.alpha0 = float(self.params["gt0"]["alpha"])
        self.beta0 = float(self.params["gt0"]["beta"])
        self.alpha1 = float(self.params["gt1"]["alpha"])
        self.beta1 = float(self.params["gt1"]["beta"])

    def predict(self, y_raw, n: Optional[int] = None, seed: Optional[int] = None) -> np.ndarray:
        rng = np.random.default_rng(seed)

        if np.isscalar(y_raw):
            y_is_target = int(y_raw) == self.target_label
            k = 1 if n is None else int(n)
            if y_is_target:
                return rng.beta(self.alpha1, self.beta1, size=k)
            else:
                return rng.beta(self.alpha0, self.beta0, size=k)

        y_raw = np.asarray(y_raw)
        y_bin = (y_raw == self.target_label).astype(np.int64)

        out = np.empty_like(y_bin, dtype=np.float64)
        idx0 = np.where(y_bin == 0)[0]
        idx1 = np.where(y_bin == 1)[0]
        if idx0.size:
            out[idx0] = rng.beta(self.alpha0, self.beta0, size=idx0.size)
        if idx1.size:
            out[idx1] = rng.beta(self.alpha1, self.beta1, size=idx1.size)
        return out


class Decoder(Protocol):
    """Protocol for decoders that return (p_target, quality) tuple."""

    def decode(self, item_dtn: int, *, seed: Optional[int] = None) -> tuple[float, float]:
        """
        Decode an item to get target probability and quality measure.

        Args:
            item_dtn: Item DTN (1 for non-target, 2 for target)
            seed: Random seed for deterministic sampling

        Returns:
            Tuple of (p_target, quality) where:
                - p_target: Probability that item is target, in [0.0, 1.0]
                - quality: Quality measure (AUC) in [0.4, 1.0]
        """
        ...


class DefaultDecoder:
    """
    Default per-fixation implicit-evidence decoder. Reads the recorded
    per-subject EEG-evidence parameters and maps item_dtn to a target
    probability and decoder quality (AUC). Replace with your own decoder
    (see README).
    """

    def __init__(self, dist_json_path: str):
        """
        Initialize decoder from an eeg_pred_beta.json file.

        Args:
            dist_json_path: Path to eeg_pred_beta.json containing the
                per-subject EEG-evidence parameters
        """
        self.predictor = _ParamPredictor(dist_json_path)
        quality = self.predictor.state_dict['metrics']['simulator_active_beta']['threshold_0p5']['auc']
        self.quality = float(quality)

    def decode(self, item_dtn: int, *, seed: Optional[int] = None) -> tuple[float, float]:
        """
        Decode an item to get target probability and quality.

        Args:
            item_dtn: Item DTN (1 for non-target, 2 for target)
            seed: Random seed for deterministic sampling

        Returns:
            Tuple of (p_target, quality)
        """
        # Map item_dtn to y_raw: {1:0 (non-target), 2:1 (target)}
        dtn_to_y_raw = {1: 0, 2: 1}
        if item_dtn not in dtn_to_y_raw:
            raise ValueError(f"item_dtn must be 1 or 2, got {item_dtn}")

        y_raw = dtn_to_y_raw[item_dtn]

        # Get sampled prediction; predict returns an array, take [0]
        p_target = float(self.predictor.predict(y_raw, seed=seed)[0])

        return (p_target, self.quality)


def load_default_decoder(subject_id: int, priors_root: str = 'eeg_priors') -> DefaultDecoder:
    """
    Load the default implicit-evidence decoder for a subject.

    Args:
        subject_id: Participant ID
        priors_root: Root directory containing eeg_priors

    Returns:
        DefaultDecoder instance
    """
    path = os.path.join(priors_root, str(subject_id), 'us1', 'eeg_pred_beta.json')
    return DefaultDecoder(path)
