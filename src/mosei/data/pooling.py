"""Model-agnostic masked temporal reductions that exclude padding."""
from __future__ import annotations

import numpy as np


def _validated(values, support_mask, *, torch_tensor=False):
    if values.ndim != 3 or support_mask.ndim != 2 or values.shape[:2] != support_mask.shape:
        raise ValueError("Expected values (B,T,D) and mask (B,T)")
    if (str(support_mask.dtype) != "torch.bool" if torch_tensor else support_mask.dtype != np.bool_):
        raise ValueError("Temporal mask must be boolean")


def masked_sum(values, support_mask):
    """Sum only explicitly supported positions; supports NumPy and optional torch tensors."""
    if type(values).__module__.startswith("torch"):
        _validated(values, support_mask, torch_tensor=True)
        return (values * support_mask.unsqueeze(-1).to(values.dtype)).sum(dim=1)
    array = np.asarray(values)
    mask = np.asarray(support_mask)
    _validated(array, mask)
    return np.sum(np.where(mask[..., None], array, 0), axis=1)


def masked_mean(values, support_mask):
    """Return zero for an all-false mask; never divide by zero."""
    summed = masked_sum(values, support_mask)
    if type(values).__module__.startswith("torch"):
        count = support_mask.sum(dim=1).clamp(min=1).unsqueeze(-1)
        return summed / count
    count = np.maximum(np.asarray(support_mask).sum(axis=1), 1)[:, None]
    return summed / count
