"""bootstrap.py - the percentile bootstrap shared by scripts/20_bootstrap.py and the masking experiment.

Only the decision-free part lives here: resample indices, the 95% percentile interval, and a paired
difference of two key-aligned 0/1 arrays. Policy decisions (decide()) stay in the scripts.
Moving this out of 20_bootstrap.py must not change results*/harness/bootstrap.json by a single byte.
"""
from __future__ import annotations

import numpy as np

B, SEED = 10_000, 20261031


def resample_index(n: int, b: int = B, seed: int = SEED) -> np.ndarray:
    """(b, n) indices of receipts drawn with replacement; one row per resample."""
    return np.random.default_rng(seed).integers(0, n, size=(b, n))


def ci95(x: np.ndarray, digits: int = 4) -> list[float]:
    lo, hi = np.nanpercentile(x, [2.5, 97.5])
    return [round(float(lo), digits), round(float(hi), digits)]


def diff_summary(d: np.ndarray, point: float) -> dict:
    """A bootstrapped difference in points: point estimate, 95% interval, share of resamples above 0."""
    return {"point": round(point, 2), "ci95": ci95(d, 2), "share_of_resamples_above_0": round(float(np.mean(d > 0)), 4)}


def paired_ci(a, b, n_boot: int = B, seed: int = SEED) -> dict:
    """Mean of a minus mean of b, in points, for two 0/1 arrays aligned on the same receipts."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    assert a.shape == b.shape and a.ndim == 1 and len(a) > 0, "paired_ci needs two aligned, non-empty 1-D arrays"
    idx = resample_index(len(a), n_boot, seed)
    d = (a[idx].mean(1) - b[idx].mean(1)) * 100
    return {"n": int(len(a)), **diff_summary(d, float((a.mean() - b.mean()) * 100))}
