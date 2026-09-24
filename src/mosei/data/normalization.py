"""Identity and train-only observed-vector z-score infrastructure."""
from __future__ import annotations

import numpy as np

from .data_contract import AlignedBatch, FEATURE_DIMS
from .dataset import AlignedDataset

CONFIG_VERSION = "s00d-data-contract-v1"
MODALITIES = ("text", "audio", "vision")


def _require_train(dataset: AlignedDataset) -> None:
    if not isinstance(dataset, AlignedDataset) or dataset.split != "train":
        raise ValueError("Normalizer fit accepts train dataset only")


class IdentityNormalizer:
    method = "none"

    def __init__(self) -> None:
        self.fit_split: str | None = None

    def fit(self, dataset: AlignedDataset) -> "IdentityNormalizer":
        _require_train(dataset)
        self.fit_split = "train"
        return self

    def transform(self, batch: AlignedBatch) -> AlignedBatch:
        if self.fit_split != "train":
            raise ValueError("Identity normalizer must be initialized on train")
        return batch

    def state_dict(self) -> dict:
        return {"method": self.method, "config_version": CONFIG_VERSION, "fit_split": self.fit_split,
                "feature_dimensions": FEATURE_DIMS}


class TrainOnlyZScoreNormalizer:
    method = "train_only_z_score"

    def __init__(self) -> None:
        self.fit_split: str | None = None
        self.stats: dict[str, dict] = {}

    def fit(self, dataset: AlignedDataset, *, batch_size: int = 32) -> "TrainOnlyZScoreNormalizer":
        _require_train(dataset)
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        totals = {name: {"count": 0, "sum": np.zeros(dim, dtype=np.float64),
                         "sumsq": np.zeros(dim, dtype=np.float64)} for name, dim in FEATURE_DIMS.items()}
        for batch in dataset.iter_batches(batch_size):
            for name in MODALITIES:
                values = getattr(batch, name)
                observed = getattr(batch, f"{name}_observed_mask")
                selected = values[observed].astype(np.float64, copy=False)
                totals[name]["count"] += int(len(selected))
                totals[name]["sum"] += selected.sum(axis=0)
                totals[name]["sumsq"] += np.square(selected).sum(axis=0)
        stats = {}
        for name, aggregate in totals.items():
            count = aggregate["count"]
            if count < 1:
                raise ValueError(f"No observed train vectors for {name}")
            mean = aggregate["sum"] / count
            variance = np.maximum(aggregate["sumsq"] / count - mean * mean, 0.0)
            std = np.sqrt(variance)
            if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(std)):
                raise ValueError("Normalizer statistics must be finite")
            stats[name] = {"count": count, "feature_dimensions": FEATURE_DIMS[name],
                           "mean": mean.tolist(), "std": std.tolist(),
                           "zero_std_feature_count": int(np.count_nonzero(std == 0))}
        self.stats = stats
        self.fit_split = "train"
        return self

    def transform(self, batch: AlignedBatch) -> AlignedBatch:
        if self.fit_split != "train" or set(self.stats) != set(MODALITIES):
            raise ValueError("Z-score normalizer must be fit on train")
        features = {}
        for name in MODALITIES:
            original = getattr(batch, name)
            observed = getattr(batch, f"{name}_observed_mask")
            mean = np.asarray(self.stats[name]["mean"], dtype=np.float64)
            std = np.asarray(self.stats[name]["std"], dtype=np.float64)
            if mean.shape != (FEATURE_DIMS[name],) or std.shape != mean.shape:
                raise ValueError("Normalizer state dimension mismatch")
            scale = np.where(std == 0, 1.0, std)
            changed = original.copy()
            changed[observed] = ((original[observed].astype(np.float64) - mean) / scale).astype(np.float32)
            if not np.all(np.isfinite(changed)):
                raise ValueError("Normalized features must be finite")
            features[name] = changed
        return AlignedBatch(features["text"], features["audio"], features["vision"],
                            batch.text_support_mask, batch.audio_support_mask, batch.vision_support_mask,
                            batch.text_observed_mask, batch.audio_observed_mask, batch.vision_observed_mask,
                            batch.classification_target, batch.regression_target, batch.corruption)

    def state_dict(self) -> dict:
        if self.fit_split != "train":
            raise ValueError("Unfit normalizer has no serializable statistics")
        return {"method": self.method, "config_version": CONFIG_VERSION,
                "fit_split": self.fit_split, "feature_dimensions": FEATURE_DIMS,
                "mask_rule": "text:support; audio/vision:support AND NOT structural_zero",
                "statistics": self.stats}

    @classmethod
    def from_state_dict(cls, state: dict) -> "TrainOnlyZScoreNormalizer":
        if (state.get("method") != cls.method or state.get("config_version") != CONFIG_VERSION or
                state.get("fit_split") != "train" or state.get("feature_dimensions") != FEATURE_DIMS):
            raise ValueError("Invalid train-only normalizer state")
        stats = state.get("statistics")
        if not isinstance(stats, dict) or set(stats) != set(MODALITIES):
            raise ValueError("Incomplete normalizer statistics")
        for name in MODALITIES:
            item = stats[name]
            for key in ("mean", "std"):
                values = np.asarray(item[key], dtype=np.float64)
                if (values.shape != (FEATURE_DIMS[name],) or not np.all(np.isfinite(values)) or
                        (key == "std" and np.any(values < 0))):
                    raise ValueError("Invalid normalizer statistic shape/value")
            if item["count"] < 1 or item["feature_dimensions"] != FEATURE_DIMS[name]:
                raise ValueError("Invalid normalizer count/dimension")
        result = cls()
        result.fit_split = "train"
        result.stats = stats
        return result
