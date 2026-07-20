"""
rac_hrp.nulls.gate_v2_stats
===========================
The exact statistical rules from the signed protocol, isolated so they can be
unit-tested against hand-computed values independent of the simulation.

Every formula here is quoted from the amendments. Nothing is improvised.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
from scipy import stats


# --------------------------------------------------------------------------
# [A-2] one-sided paired-t bounds
# --------------------------------------------------------------------------
@dataclass
class TVerdict:
    mean: float
    upper: float          # U = d_bar + t(0.95,n-1) * s/sqrt(n)
    lower: float          # L = d_bar - t(0.95,n-1) * s/sqrt(n)
    n: int
    verdict: str          # PASS | FAIL | INCONCLUSIVE


def paired_t_bounds(d: np.ndarray, margin: float = 0.10,
                    conf: float = 0.95) -> TVerdict:
    """One-sided paired-t bounds and classification.

    PASS          if U <= margin
    FAIL          if L >  margin
    INCONCLUSIVE  otherwise

    U and L use the ONE-SIDED critical value t(conf, n-1) -- e.g. t(0.95, n-1),
    NOT t(0.975). Both bounds share that same half-width; they are the two
    one-sided 95% bounds, reported together.
    """
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 2:
        return TVerdict(np.nan, np.nan, np.nan, n, "INCONCLUSIVE")
    dbar = float(np.mean(d))
    s = float(np.std(d, ddof=1))
    tcrit = float(stats.t.ppf(conf, n - 1))
    half = tcrit * s / np.sqrt(n)
    U, L = dbar + half, dbar - half
    if U <= margin:
        v = "PASS"
    elif L > margin:
        v = "FAIL"
    else:
        v = "INCONCLUSIVE"
    return TVerdict(dbar, U, L, n, v)


# --------------------------------------------------------------------------
# [control-construction ruling] deterministic location-shift controls
# --------------------------------------------------------------------------
def location_shift(d: np.ndarray, delta: float) -> np.ndarray:
    """d_control_r = (d_r - mean(d)) + delta.

    Preserves n, sample variance, shape, skew, outliers; sets the sample mean
    exactly to delta. Deterministic -- no seed.
    """
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    return (d - d.mean()) + delta


def control_verdicts(d: np.ndarray, null_delta: float, pos_delta: float,
                     margin: float, conf: float) -> Tuple[TVerdict, TVerdict]:
    """Return (null_control_verdict, positive_control_verdict) for one cell."""
    null_v = paired_t_bounds(location_shift(d, null_delta), margin, conf)
    pos_v = paired_t_bounds(location_shift(d, pos_delta), margin, conf)
    return null_v, pos_v


# --------------------------------------------------------------------------
# [A-4] paired percentile bootstrap (diagnostic only)
# --------------------------------------------------------------------------
def paired_bootstrap(d: np.ndarray, seed: int, n_resamples: int = 10_000,
                     conf: float = 0.95) -> Tuple[float, float]:
    """One-sided 95% percentile bounds from paired resampling of the
    replication-level differences, with replacement, across complete
    replications. Returns (lower_pctl, upper_pctl).

    Diagnostic only: never replaces the paired-t verdict.
    """
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = np.empty(n_resamples)
    for b in range(n_resamples):
        idx = rng.integers(0, n, n)
        means[b] = d[idx].mean()
    lower = float(np.percentile(means, 100 * (1 - conf)))   # 5th pctl
    upper = float(np.percentile(means, 100 * conf))         # 95th pctl
    return (lower, upper)


# --------------------------------------------------------------------------
# [A-3] trigger-activation requirement
# --------------------------------------------------------------------------
@dataclass
class ActivationResult:
    median_firing_rate: float
    frac_reps_active: float          # fraction of reps with >= min_events
    sufficient: bool
    reason: str


def trigger_activation(firing_rates: np.ndarray, event_counts: np.ndarray,
                       min_median_rate: float, min_events: int,
                       min_frac_active: float) -> ActivationResult:
    """An environment is sufficiently informative iff:
      - median firing rate across replications >= min_median_rate, AND
      - >= min_frac_active of replications have >= min_events trigger events.
    Denominator for firing rate = eligible trigger-evaluation opportunities.
    """
    fr = np.asarray(firing_rates, dtype=float)
    ec = np.asarray(event_counts, dtype=float)
    med = float(np.median(fr)) if len(fr) else 0.0
    frac_active = float(np.mean(ec >= min_events)) if len(ec) else 0.0
    ok_rate = med >= min_median_rate
    ok_events = frac_active >= min_frac_active
    if ok_rate and ok_events:
        reason = "sufficient trigger activation"
    elif not ok_rate and not ok_events:
        reason = (f"median firing {med:.1%} < {min_median_rate:.0%} AND only "
                  f"{frac_active:.0%} of reps have >={min_events} events")
    elif not ok_rate:
        reason = f"median firing rate {med:.1%} < {min_median_rate:.0%}"
    else:
        reason = (f"only {frac_active:.0%} of reps have >={min_events} events "
                  f"(< {min_frac_active:.0%})")
    return ActivationResult(med, frac_active, ok_rate and ok_events, reason)
