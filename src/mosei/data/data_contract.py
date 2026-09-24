"""Typed, leak-resistant aligned batch contract for the controlled baseline."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .masks import AlignedMaskSet, CorruptionMask, TIME, structural_zero_mask

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
    with np.errstate(over="ignore", under="ignore"):
        converted = values.astype(np.float32, copy=True)
    if not np.all(np.isfinite(converted)):
        raise ValueError("Regression target became non-finite after float32 conversion")
    converted_expected = np.where(converted < 0, 0, np.where(converted == 0, 1, 2))
    if not np.array_equal(converted_expected, expected):
        raise ValueError("float32 conversion changed the strict-zero target class")
    return classes.astype(np.int64, copy=True), converted


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
            with np.errstate(over="ignore", under="ignore"):
                converted = array.astype(np.float32, copy=True)
            if not np.all(np.isfinite(converted)):
                raise ValueError(f"Aligned {name} became non-finite after float32 conversion")
            if name in ("audio", "vision") and not np.array_equal(
                    structural_zero_mask(array), structural_zero_mask(converted)):
                raise ValueError(f"Aligned {name} structural-zero status changed during conversion")
            features[name] = converted
        mask_names = AlignedMaskSet.__dataclass_fields__
        for mask_name in mask_names:
            mask = getattr(masks, mask_name)
            if not isinstance(mask, np.ndarray) or mask.shape != (n, TIME) or mask.dtype != np.bool_:
                raise ValueError(f"Invalid {mask_name} shape/dtype")
        support = masks.text_support_mask
        if n < 1 or np.any(~support[:, :-1] & support[:, 1:]) or np.any(~support.any(axis=1)):
            raise ValueError("Aligned support must be a nonempty continuous prefix")
        if not np.array_equal(masks.padding_mask, ~support):
            raise ValueError("Padding mask must be the complement of support")
        if not np.array_equal(masks.text_observed_mask, support):
            raise ValueError("Text observed mask must equal support")
        if not np.array_equal(masks.audio_support_mask, masks.text_support_mask) or not np.array_equal(masks.vision_support_mask, masks.text_support_mask):
            raise ValueError("Aligned modalities must share support")
        for name in ("audio", "vision"):
            zero = getattr(masks, f"{name}_structural_zero_mask")
            if not np.array_equal(zero, structural_zero_mask({"audio": audio, "vision": vision}[name])):
                raise ValueError(f"{name} structural-zero mask disagrees with source values")
            if not np.array_equal(getattr(masks, f"{name}_observed_mask"),
                                  masks.text_support_mask & ~zero):
                raise ValueError(f"{name} observed mask disagrees with support and structural zero")
        corruption = CorruptionMask.empty(masks)
        corruption.validate_against(masks)
        return cls(features["text"], features["audio"], features["vision"],
                   masks.text_support_mask.copy(), masks.audio_support_mask.copy(), masks.vision_support_mask.copy(),
                   masks.text_observed_mask.copy(), masks.audio_observed_mask.copy(), masks.vision_observed_mask.copy(),
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
        # from_numpy shares storage. Give every tensor private storage, including masks and targets.
        return {"model_inputs": {key: torch.from_numpy(np.array(value, copy=True)) for key, value in self.model_inputs.items()},
                "targets": {key: torch.from_numpy(np.array(value, copy=True)) for key, value in self.targets.items()}}
