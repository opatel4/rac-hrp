"""
rac_hrp.phase2.stats
====================
The exact statistical rules from the signed Phase 2 pre-registration (rev.5),
isolated so they can be unit-tested independently of the simulation.

Nothing here is improvised. Section references are to the signed document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from .config import (SEPARATION_PERIODS, PLACEBO_SEED, PLACEBO_DRAWS,
                     PLACEBO_PERCENTILE, BOOTSTRAP_REPLICATES, HOLM_ALPHA)


# ==========================================================================
# Section 3 -- phase-adjusted separation from periodic schedules
# ==========================================================================
def periodic_set(E: int, q: int, r: int) -> np.ndarray:
    """P(q, r) = { e_j in E : j mod q == r } as a boolean mask of length E."""
    m = np.zeros(E, dtype=bool)
    m[r::q] = True
    return m


def j_star(trigger_idx: Sequence[int], E: int,
           periods: Sequence[int] = SEPARATION_PERIODS
           ) -> Tuple[float, Tuple[int, int]]:
    """Phase-adjusted maximum Jaccard overlap with any periodic schedule.

        J*_g = max over q, r of |T ∩ P(q,r)| / |T ∪ P(q,r)|

    PHASE MATTERS. Maximising over q alone (implicitly r = 0) is degenerate: a
    trigger firing exactly every second rebalance on the ODD dates scores 0.252
    against an even-anchored grid -- i.e. it passes as well separated while being
    literally a calendar rule. With phase it scores 1.000.

    q = 1 is deliberately EXCLUDED from the frozen period set: P(1,0) is every
    eligible date, a superset of any trigger set, so J(g,1) = f_g identically and
    the statistic would merely restate the firing rate.
    """
    T = np.zeros(E, dtype=bool)
    T[np.asarray(trigger_idx, dtype=int)] = True
    nT = int(T.sum())
    if nT == 0:
        return 0.0, (0, 0)
    best, arg = 0.0, (0, 0)
    for q in periods:
        for r in range(q):
            P = periodic_set(E, q, r)
            inter = int(np.count_nonzero(T & P))
            union = nT + int(P.sum()) - inter
            j = inter / union if union else 0.0
            if j > best:
                best, arg = j, (q, r)
    return float(best), arg


def placebo_threshold(E: int, n_events: int,
                      periods: Sequence[int] = SEPARATION_PERIODS,
                      seed: int = PLACEBO_SEED,
                      draws: int = PLACEBO_DRAWS,
                      pct: float = PLACEBO_PERCENTILE) -> float:
    """Frozen placebo critical value for J* at a GIVEN event count.

    RECOMPUTED PER CANDIDATE. The threshold depends strongly on |T|: the 95th
    percentile is 0.171 at |T| = 12 and 0.382 at |T| = 112, and at low event
    counts q = 2 does not even attain the maximum. Reusing one cutoff across
    candidates would be wrong.

    RNG numpy PCG64; percentile by numpy linear interpolation.
    """
    if n_events <= 0:
        return 0.0
    rng = np.random.default_rng(seed)
    masks = [(q, r, periodic_set(E, q, r)) for q in periods for r in range(q)]
    sizes = {(q, r): int(P.sum()) for q, r, P in masks}
    M = np.stack([P for _, _, P in masks]).astype(np.uint8)      # (K, E)
    szs = np.array([sizes[(q, r)] for q, r, _ in masks], dtype=float)

    T = np.zeros((draws, E), dtype=np.uint8)
    for i in range(draws):
        T[i, rng.choice(E, size=n_events, replace=False)] = 1

    inter = T @ M.T                                              # (draws, K)
    union = n_events + szs[None, :] - inter
    best = (inter / union).max(axis=1)
    return float(np.percentile(best, pct))


# ==========================================================================
# Section 2 -- timing variation
# ==========================================================================
@dataclass
class TimingStats:
    cv_gap: float
    modal_gap_share: float
    n_gaps: int


def timing_variation(trigger_idx: Sequence[int]) -> TimingStats:
    """CV of inter-trigger gaps, and the share of gaps at the modal interval.

    A trigger whose gaps are almost always the same length is calendar-like even
    if its dates do not align with any anchored grid, which is why the modal
    share is gated alongside the coefficient of variation.
    """
    t = np.sort(np.asarray(trigger_idx, dtype=int))
    if len(t) < 3:
        return TimingStats(np.nan, np.nan, max(0, len(t) - 1))
    g = np.diff(t)
    mean = float(g.mean())
    cv = float(g.std(ddof=1) / mean) if mean > 0 else np.nan
    vals, counts = np.unique(g, return_counts=True)
    return TimingStats(cv, float(counts.max() / len(g)), len(g))


# ==========================================================================
# Section 4 -- D_VI and its circular block bootstrap
# ==========================================================================
def d_vi(vi: np.ndarray, fired: np.ndarray) -> float:
    """D_VI = median(VI_t | I_t = 1) - median(VI_t | I_t = 0)."""
    vi = np.asarray(vi, dtype=float)
    fired = np.asarray(fired).astype(bool)
    a, b = vi[fired], vi[~fired]
    if len(a) == 0 or len(b) == 0:
        return np.nan
    return float(np.median(a) - np.median(b))


def politis_white_block_length(x: np.ndarray) -> int:
    """Politis-White (2004) automatic block length, integer, >= 1.

    Implemented in-repo (no third-party dependency) so the value is reproducible
    and can be recorded in the run manifest, as the advisor requires.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 8:
        return 1
    xc = x - x.mean()
    denom = float(xc @ xc)
    if denom <= 0:
        return 1
    kn = max(5, int(np.ceil(np.sqrt(np.log10(n)))))
    mmax = int(np.ceil(np.sqrt(n))) + kn
    rho = np.array([float(xc[:n - k] @ xc[k:]) / denom
                    for k in range(1, min(mmax, n - 1) + 1)])
    crit = 2.0 * np.sqrt(np.log10(n) / n)
    m = 0
    for k in range(len(rho) - kn):
        if np.all(np.abs(rho[k:k + kn]) < crit):
            m = k + 1
            break
    if m == 0:
        m = len(rho)
    M = min(2 * m, len(rho))
    lags = np.arange(1, M + 1)
    lam = np.where(np.abs(lags / M) <= 0.5, 1.0,
                   np.maximum(0.0, 2.0 * (1.0 - np.abs(lags / M))))
    g = float(np.sum(lam * lags * rho[:M])) * 2.0
    d = float(np.sum(lam * rho[:M])) * 2.0 + 1.0
    dsc = 2.0 * d ** 2
    if dsc <= 0:
        return 1
    b = ((2.0 * g ** 2) / dsc) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return int(np.clip(round(b), 1, max(1, n // 2)))


@dataclass
class BootstrapResult:
    d_hat: float
    p_value: float
    block_length: int
    replicates: int
    n_degenerate: int          # replicates with only one I class (see manifest note)


def circular_block_bootstrap_p(vi: np.ndarray, fired: np.ndarray, seed: int,
                               replicates: int = BOOTSTRAP_REPLICATES
                               ) -> BootstrapResult:
    """One-sided centred circular block bootstrap for H0: D_VI <= 0.

    Frozen mechanics (rev.5 section 4):
      * circular block bootstrap -- edge observations are not under-weighted
      * Politis-White automatic block length
      * the PAIR (VI_t, I_t) is resampled JOINTLY in blocks, preserving alignment
      * B = 10,000 replicates, numpy PCG64, deterministic candidate-specific seed
      * replicates centred by subtracting the observed D_hat
      * p = (1 + #{ b : D*_b - D_hat >= D_hat }) / (B + 1)

    Degenerate replicates (all-fired or none-fired, so one class is empty) cannot
    produce a difference of medians. They are DISCARDED from the numerator and
    denominator and their count is returned for the run manifest. This is
    expected to be vanishingly rare at the observed firing rates.
    """
    vi = np.asarray(vi, dtype=float)
    fired = np.asarray(fired).astype(bool)
    n = len(vi)
    d_hat = d_vi(vi, fired)
    if not np.isfinite(d_hat) or n < 4:
        return BootstrapResult(d_hat, np.nan, 1, 0, 0)

    L = politis_white_block_length(vi)
    n_blocks = int(np.ceil(n / L))
    rng = np.random.default_rng(seed)

    kept, exceed, degenerate = 0, 0, 0
    for _ in range(replicates):
        starts = rng.integers(0, n, size=n_blocks)
        idx = ((starts[:, None] + np.arange(L)[None, :]) % n).ravel()[:n]
        d_b = d_vi(vi[idx], fired[idx])
        if not np.isfinite(d_b):
            degenerate += 1
            continue
        kept += 1
        if (d_b - d_hat) >= d_hat:
            exceed += 1

    p = (1.0 + exceed) / (kept + 1.0) if kept else np.nan
    return BootstrapResult(d_hat, float(p), L, kept, degenerate)


# ==========================================================================
# Section 4 -- Holm step-down multiplicity control
# ==========================================================================
def holm_adjust(p: Dict[float, float]) -> Dict[float, float]:
    """Holm step-down adjusted p-values, keyed by gamma.

    Holm rather than Bonferroni because the trigger sets are highly dependent
    across gamma and Bonferroni would be needlessly conservative.
    """
    items = [(g, v) for g, v in p.items() if np.isfinite(v)]
    items.sort(key=lambda kv: kv[1])
    m = len(items)
    out: Dict[float, float] = {g: np.nan for g in p}
    running = 0.0
    for i, (g, v) in enumerate(items):
        adj = min(1.0, (m - i) * v)
        running = max(running, adj)          # enforce monotonicity
        out[g] = running
    return out
