"""Typed, leak-resistant aligned batch contract for the controlled baseline."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .masks import AlignedMaskSet, CorruptionMask, TIME

CLASS_NAMES = {0: "Negative", 1: "Neutral", 2: "Positive"}
FEATURE_DIMS = {"text": 768, "audio": 74, "vision": 35}


def validate_label_contract(classification: np.ndarray, regression: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    classes = np.asarray(classification)
    values = np.asarray(regression)
    if classes.ndim != 1 or values.shape != classes.shape or not np.issubdtype(classes.dtype, np.number):
        raise ValueError("Targets must be matching numeric vectors")
    if not np.all(np.isfinite(classes)) or not np.all(classes == np.floor(classes)) or not np.all(np.isin(classes, [0, 1, 2])):
        raise ValueError("Classification target must use official 0/1/2 mapping")
    if not np.issubdtype(values.dtype, np.number) or not np.all(np.isfinite(values)) or np.any((values < -3) | (values > 3)):
        raise ValueError("Regression target must be finite and in [-3,3]")
    expected = np.where(values < 0, 0, np.where(values == 0, 1, 2))
    if not np.array_equal(classes.astype(np.int64), expected):
        raise ValueError("Classification target disagrees with strict regression sign/zero")
    return classes.astype(np.int64, copy=False), values.astype(np.float32, copy=False)


@dataclass(frozen=True)
class AlignedBatch:
    text: np.ndarray
    audio: np.ndarray
    vision: np.ndarray
    text_support_mask: np.ndarray
    audio_support_mask: np.ndarray
    vision_support_mask: np.ndarray
    text_observed_mask: np.ndarray
    audio_observed_mask: np.ndarray
    vision_observed_mask: np.ndarray
    classification_target: np.ndarray
    regression_target: np.ndarray
    corruption: CorruptionMask

    @classmethod
    def from_arrays(cls, text: np.ndarray, audio: np.ndarray, vision: np.ndarray,
                    masks: AlignedMaskSet, classification: np.ndarray,
                    regression: np.ndarray) -> "AlignedBatch":
        classes, values = validate_label_contract(classification, regression)
        features = {"text": np.asarray(text), "audio": np.asarray(audio), "vision": np.asarray(vision)}
        n = len(classes)
        for name, array in features.items():
            if array.shape != (n, TIME, FEATURE_DIMS[name]) or not np.issubdtype(array.dtype, np.number):
                raise ValueError(f"Aligned {name} must have shape (B,50,{FEATURE_DIMS[name]})")
            if not np.all(np.isfinite(array)):
                raise ValueError(f"Aligned {name} has NaN/Inf")
            features[name] = array.astype(np.float32, copy=False)
        for name in ("text", "audio", "vision"):
            support = getattr(masks, f"{name}_support_mask")
            observed = getattr(masks, f"{name}_observed_mask")
            if support.shape != (n, TIME) or observed.shape != (n, TIME) or support.dtype != np.bool_ or observed.dtype != np.bool_:
                raise ValueError(f"Invalid {name} mask shape/dtype")
            if np.any(observed & ~support):
                raise ValueError(f"Observed {name} positions must lie within support")
        if not np.array_equal(masks.audio_support_mask, masks.text_support_mask) or not np.array_equal(masks.vision_support_mask, masks.text_support_mask):
            raise ValueError("Aligned modalities must share support")
        corruption = CorruptionMask.empty(masks)
        corruption.validate_against(masks)
        return cls(features["text"], features["audio"], features["vision"],
                   masks.text_support_mask, masks.audio_support_mask, masks.vision_support_mask,
                   masks.text_observed_mask, masks.audio_observed_mask, masks.vision_observed_mask,
                   classes, values, corruption)

    @property
    def padding_mask(self) -> np.ndarray:
        return ~self.text_support_mask

    @property
    def model_inputs(self) -> dict[str, np.ndarray]:
        """Only predictor features and named mask metadata; no labels, IDs or split."""
        return {key: getattr(self, key) for key in (
            "text", "audio", "vision", "text_support_mask", "audio_support_mask",
            "vision_support_mask", "text_observed_mask", "audio_observed_mask",
            "vision_observed_mask", "padding_mask")}

    @property
    def targets(self) -> dict[str, np.ndarray]:
        return {"classification_target": self.classification_target,
                "regression_target": self.regression_target}

    def to_torch(self) -> dict[str, dict]:
        """Optional direct PyTorch bridge; keeps targets separate from predictors."""
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("PyTorch runtime unavailable; NumPy batch contract remains valid") from exc
        return {"model_inputs": {key: torch.from_numpy(value) for key, value in self.model_inputs.items()},
                "targets": {key: torch.from_numpy(value) for key, value in self.targets.items()}}
