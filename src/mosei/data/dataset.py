"""Aligned train/valid adapter. Official test and special sets are not accepted."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np

from .data_contract import AlignedBatch, FEATURE_DIMS, validate_label_contract
from .masks import AlignedMaskSet, aligned_mask_set, support_from_text_bert

ALLOWED_SPLITS = {"train", "valid"}


@dataclass(frozen=True)
class AlignedDataset:
    split: str
    text: np.ndarray
    audio: np.ndarray
    vision: np.ndarray
    masks: AlignedMaskSet
    classification_target: np.ndarray
    regression_target: np.ndarray

    def __len__(self) -> int:
        return len(self.classification_target)

    def batch(self, indices: np.ndarray | list[int]) -> AlignedBatch:
        selected = np.asarray(indices)
        if selected.ndim != 1 or not np.issubdtype(selected.dtype, np.integer) or np.any((selected < 0) | (selected >= len(self))):
            raise ValueError("Batch indices must be valid integer positions")
        masks = AlignedMaskSet(*(getattr(self.masks, name)[selected] for name in AlignedMaskSet.__dataclass_fields__))
        return AlignedBatch.from_arrays(self.text[selected], self.audio[selected], self.vision[selected],
                                        masks, self.classification_target[selected], self.regression_target[selected])

    def iter_batches(self, batch_size: int, *, shuffle: bool = False, seed: int | None = None) -> Iterator[AlignedBatch]:
        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be positive")
        if shuffle and self.split != "train":
            raise ValueError("Only train may be shuffled for training loaders")
        order = np.arange(len(self))
        if shuffle:
            if seed is None:
                raise ValueError("Shuffled batching requires an explicit seed")
            order = np.random.default_rng(seed).permutation(order)
        for start in range(0, len(order), batch_size):
            yield self.batch(order[start:start + batch_size])


def create_aligned_dataset(source: dict, split: str) -> AlignedDataset:
    """Select allowlisted fields only; reject test before indexing the source."""
    if split not in ALLOWED_SPLITS:
        raise ValueError("S00D adapter permits only train and valid; test is quarantined")
    item = source[split]
    text = np.asarray(item["text"])
    audio = np.asarray(item["audio"])
    vision = np.asarray(item["vision"])
    n = text.shape[0] if text.ndim == 3 else -1
    for name, values in (("text", text), ("audio", audio), ("vision", vision)):
        if values.shape != (n, 50, FEATURE_DIMS[name]) or not np.issubdtype(values.dtype, np.number) or not np.all(np.isfinite(values)):
            raise ValueError(f"Invalid aligned {name} shape, dtype or finite values")
    support = support_from_text_bert(np.asarray(item["text_bert"]))
    if support.shape[0] != n:
        raise ValueError("Support sample count mismatch")
    masks = aligned_mask_set(support, audio, vision)
    classes, regression = validate_label_contract(item["classification_labels"], item["regression_labels"])
    if len(classes) != n:
        raise ValueError("Target sample count mismatch")
    return AlignedDataset(split, text, audio, vision, masks, classes, regression)


def training_batches(dataset: AlignedDataset, batch_size: int, *, seed: int) -> Iterator[AlignedBatch]:
    if dataset.split != "train":
        raise ValueError("Training loader accepts train split only")
    return dataset.iter_batches(batch_size, shuffle=True, seed=seed)
