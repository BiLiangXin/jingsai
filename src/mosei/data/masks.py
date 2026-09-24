"""Separate aligned sequence support, observed vectors and artificial corruption."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TIME = 50


def structural_zero_mask(values: np.ndarray) -> np.ndarray:
    """Exact stored zero rows; this does not assign missing or padding meaning."""
    array = np.asarray(values)
    if array.ndim not in (2, 3) or array.shape[-1] < 1 or not np.issubdtype(array.dtype, np.number):
        raise ValueError("Expected numeric (T,D) or (B,T,D) feature array")
    return np.all(array == 0, axis=-1)


def support_from_text_bert(text_bert: np.ndarray) -> np.ndarray:
    values = np.asarray(text_bert)
    if values.ndim != 3 or values.shape[0] < 1 or values.shape[1:] != (3, TIME):
        raise ValueError("aligned text_bert must have shape (N,3,50)")
    if not (np.issubdtype(values.dtype, np.integer) or values.dtype == np.bool_):
        raise ValueError("text_bert mask channel must have integer or boolean dtype")
    channel = values[:, 1, :]
    if not np.all((channel == 0) | (channel == 1)):
        raise ValueError("text_bert channel 1 must be binary")
    support = channel == 1
    if np.any(~support[:, :-1] & support[:, 1:]):
        raise ValueError("Each aligned support mask must be a continuous active prefix")
    if np.any(np.sum(support, axis=1) < 1):
        raise ValueError("Every aligned sample requires at least one supported position")
    return support


@dataclass(frozen=True)
class AlignedMaskSet:
    text_support_mask: np.ndarray
    audio_support_mask: np.ndarray
    vision_support_mask: np.ndarray
    text_observed_mask: np.ndarray
    audio_observed_mask: np.ndarray
    vision_observed_mask: np.ndarray
    padding_mask: np.ndarray
    audio_structural_zero_mask: np.ndarray
    vision_structural_zero_mask: np.ndarray


def aligned_mask_set(support: np.ndarray, audio: np.ndarray, vision: np.ndarray) -> AlignedMaskSet:
    support = np.asarray(support)
    audio = np.asarray(audio)
    vision = np.asarray(vision)
    if support.dtype != np.bool_ or support.ndim != 2 or support.shape[1] != TIME:
        raise ValueError("Support must be boolean (N,50)")
    n = support.shape[0]
    if audio.shape != (n, TIME, 74) or vision.shape != (n, TIME, 35):
        raise ValueError("Aligned audio/vision shape mismatch")
    audio_zero = structural_zero_mask(audio)
    vision_zero = structural_zero_mask(vision)
    return AlignedMaskSet(support, support, support, support,
                          support & ~audio_zero, support & ~vision_zero,
                          ~support, audio_zero, vision_zero)


@dataclass(frozen=True)
class CorruptionMask:
    """Explicit future artificial corruption; never inferred from feature values."""

    text_corruption_mask: np.ndarray
    audio_corruption_mask: np.ndarray
    vision_corruption_mask: np.ndarray

    @classmethod
    def empty(cls, observed: AlignedMaskSet) -> "CorruptionMask":
        shape = observed.text_support_mask.shape
        return cls(*(np.zeros(shape, dtype=bool) for _ in range(3)))

    def validate_against(self, observed: AlignedMaskSet) -> None:
        for name, allowed in (("text", observed.text_observed_mask),
                              ("audio", observed.audio_observed_mask),
                              ("vision", observed.vision_observed_mask)):
            mask = np.asarray(getattr(self, f"{name}_corruption_mask"))
            if mask.dtype != np.bool_ or mask.shape != allowed.shape or np.any(mask & ~allowed):
                raise ValueError(f"{name} artificial corruption must be explicit and within observed support")
