"""
rac_hrp.phase2b.stats
=====================
Phase 2B -- observed-series loader.

Specification: PHASE2B_SPEC.md

WHAT THIS IS
------------
`load_series` builds the two observed series the Phase 2B statistic is defined
on (spec section 1):

    s_t  = |dAR_t| / sigma_hat_t        the trigger's standardised statistic
    VI_t = VI(t, t-h)                   h = 5 gating, h = 1 reported

It computes NO statistic. There is no Spearman correlation, no bootstrap and no
p-value in this module. It returns arrays.

WHY THIS IS SECTION 2 INFRASTRUCTURE, NOT SECTION 1 CODE
--------------------------------------------------------
Spec section 2 must pass before any section 1 analysis runs. Both of the
section 2 checks that use real data need these series first: `size_check`
resamples the observed series against an independently resampled partner, and
`power_curve` plants a known association on them. Neither can be written
without a loader, so the loader precedes them.

The ordering protection is therefore NOT that this file is unwritten. It is
that `bootstrap_test` is never called on the unresampled real pair until size,
power and falsification have passed. This module makes that protection
checkable rather than nominal: it hands back inputs, and the thing that would
turn them into a result lives elsewhere.

REUSE, NOT REIMPLEMENTATION
---------------------------
Clustering and VI are imported, never rewritten:

    structural_pass          phase2.calibration   frozen gate pass
    labelled_pass            phase2.horizon       per-date labels retained
    assert_equivalent_to_gate phase2.horizon      mandatory anti-drift guard
    vi_at_lag                phase2.horizon       VI at an arbitrary lag

`rac_hrp/phase2/` is hash-frozen and is not touched. This module lives in a
separate package and only reads from it.

The equivalence guard is not optional here either. `labelled_pass` duplicates
the gate's structural loop, and duplication is the silent-divergence failure
mode this project has already hit twice. `assert_equivalent_to_gate` requires
the retained labels to reproduce the frozen one-step VI series bitwise, and is
called before any series is returned.

COUNTERFACTUAL BY CONSTRUCTION
------------------------------
VI is recomputed at every eligible rebalance, including those where a live
strategy would not re-cluster. That is inherited, not added: it is the stated
contract of `structural_pass` (calibration.py, "EVERY eligible rebalance,
including those where a live strategy would not re-cluster"), and `vi_at_lag`
runs across the whole labelled-pass array before the eligible subset is taken.
Conditioning the sample on the strategy's own firing would make fired and
non-fired dates incomparable, which is the comparison the statistic is.

NaN ACCOUNTING -- NOTHING IS MASKED
-----------------------------------
`vi_at_lag` yields NaN from two unrelated causes, and they are reported
separately because they mean different things:

  boundary   array position i < h, so there is no t-h partner at all. A
             structural consequence of the horizon.
  floor      `_vi_pair` found fewer than `min_common` permnos shared between
             the universes at t and t-h and declined to compute VI. A property
             of universe turnover in the data, not of the horizon.

The returned VI arrays keep their NaNs. Callers decide what to do about them;
this module refuses to make that decision silently.

On the arithmetic, the two causes cannot collide. Eligibility requires
sigma_hat, which is `rolling(12, min_periods=6).std().shift(1)` of dAR, and dAR
is itself a first difference. The first eligible array position is therefore 7,
while the boundary band for h = 5 is positions 0-4. 7 > 4, so no eligible
position is ever a boundary NaN and the expected n is the full eligible set at
both horizons. That is a derivation, not a measurement: the counts are still
computed and returned, and a nonzero boundary count means the derivation is
wrong and must be reported, not absorbed.

PERFORMANCE-BLIND
-----------------
Nothing here imports or reaches a return, Sharpe ratio, drawdown or risk-free
series. The imports are clustering, covariance, PCA, panel and config. Note
that `eval_pos` is a parameter rather than something this module builds, so
`rac_hrp.backtest` is never imported at all.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..config import Config, TEST_START
from ..data.panel import Panels
from ..phase2.calibration import StructuralPass, structural_pass
from ..phase2.horizon import (LabelledPass, _vi_pair, assert_equivalent_to_gate,
                              labelled_pass, vi_at_lag)

# Spec section 1: h = 5 is the fixed gating horizon; h = 1 is computed and
# reported, non-gating. Ordering is load-bearing only for readability.
HORIZONS: Tuple[int, ...] = (5, 1)

# Phase 2A's eligible set. Asserted, not assumed -- see `load_series`.
EXPECTED_ELIGIBLE = 233

# Read off `_vi_pair` rather than restated, so this can never drift from the
# guard it is attributing NaNs to.
MIN_COMMON: int = int(
    inspect.signature(_vi_pair).parameters["min_common"].default)


class HoldoutReached(PermissionError):
    """A rebalance on or after the holdout start entered the evaluation set."""


@dataclass
class HorizonSeries:
    """VI at one horizon over the eligible set, with its NaNs accounted for."""
    horizon: int
    vi: np.ndarray                  # length n_eligible, NaNs RETAINED
    n_expected: int                 # eligible positions
    n_boundary_nan: int             # no t-h partner exists
    n_floor_nan: int                # < MIN_COMMON shared permnos
    n_used: int                     # finite VI actually available
    floor_positions: List[int] = field(default_factory=list)
    floor_dates: List[pd.Timestamp] = field(default_factory=list)
    floor_common: List[int] = field(default_factory=list)

    @property
    def matches_expected(self) -> bool:
        return self.n_used == self.n_expected


@dataclass
class ObservedSeries:
    """The Phase 2B input pair. No statistic has been computed on it."""
    dates: pd.DatetimeIndex         # eligible rebalance dates
    s: np.ndarray                   # |dAR| / sigma_hat on the eligible set
    horizons: Dict[int, HorizonSeries]
    n_rebalances: int               # full labelled pass
    n_eligible: int
    k_frozen: int
    n_s_nonfinite: int = 0
    s_nonfinite_dates: List[pd.Timestamp] = field(default_factory=list)

    def pair(self, horizon: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """(s, VI) at one horizon, NaNs intact. Alignment is positional."""
        return self.s, self.horizons[horizon].vi


def _classify_nans(lp: LabelledPass, elig_pos: np.ndarray, vi_e: np.ndarray,
                   horizon: int) -> HorizonSeries:
    """Split the NaNs in `vi_e` into boundary and floor, and attribute each.

    `vi_e` is VI already computed by `vi_at_lag`; nothing is recomputed here
    except the intersection SIZE for floor positions, which exists only so the
    report can say how short of MIN_COMMON the overlap fell. VI itself is never
    recomputed.
    """
    boundary: List[int] = []
    floor_positions: List[int] = []
    floor_dates: List[pd.Timestamp] = []
    floor_common: List[int] = []

    for j, i in enumerate(elig_pos):
        if i < horizon:
            boundary.append(j)
            continue
        if np.isnan(vi_e[j]):
            floor_positions.append(j)
            floor_dates.append(lp.dates[i])
            common = np.intersect1d(lp.permnos[i], lp.permnos[i - horizon])
            floor_common.append(int(len(common)))

    n_expected = len(elig_pos)
    n_used = int(np.count_nonzero(~np.isnan(vi_e)))

    return HorizonSeries(
        horizon=horizon,
        vi=vi_e,
        n_expected=n_expected,
        n_boundary_nan=len(boundary),
        n_floor_nan=len(floor_positions),
        n_used=n_used,
        floor_positions=floor_positions,
        floor_dates=floor_dates,
        floor_common=floor_common,
    )


def load_series(P: Panels, cfg: Config, eval_pos: np.ndarray,
                fold_bounds: Optional[List[Tuple[int, int]]] = None,
                horizons: Sequence[int] = HORIZONS,
                verbose: bool = True) -> ObservedSeries:
    """Build the observed (s, VI) pair for Phase 2B. Computes no statistic.

    Setup is mirrored, not reconstructed: `P`, `cfg`, `eval_pos` and
    `fold_bounds` are built by the caller with the identical sequence used in
    `scripts/run_phase2.py` and `scripts/run_phase2e_horizon.py`. Rebuilding
    them here would be an unrecorded divergence from the gate, and the
    equivalence check below would be measuring the wrong thing.

    Aborts rather than returning a degraded result if the labelled pass has
    drifted from the frozen gate, or if the eligible set is not the frozen 233.
    """
    if verbose:
        print("  [2B] frozen gate pass ...")
    sp: StructuralPass = structural_pass(P, cfg, eval_pos, fold_bounds,
                                         verbose=verbose)

    if verbose:
        print("  [2B] labelled pass ...")
    lp: LabelledPass = labelled_pass(P, cfg, eval_pos, verbose=verbose)

    if verbose:
        print("  [2B] equivalence check against the frozen gate ...")
    assert_equivalent_to_gate(lp, sp)
    if verbose:
        print("       OK -- one-step VI reproduces the gate bitwise")

    elig_pos = np.where(sp.eligible)[0]
    n_eligible = int(len(elig_pos))
    if n_eligible != EXPECTED_ELIGIBLE:
        raise ValueError(
            f"eligible set is {n_eligible}, frozen gate reports "
            f"{EXPECTED_ELIGIBLE}; the trigger series has changed and nothing "
            "downstream is comparable to Phase 2A")

    dates = lp.dates[elig_pos]
    if (dates >= pd.Timestamp(TEST_START)).any():
        raise HoldoutReached(
            f"a rebalance on or after the holdout start {TEST_START} entered "
            "the Phase 2B evaluation set; the holdout is single-use and no "
            "unlock is recorded")

    # ---- s_t = |dAR_t| / sigma_hat_t, spec section 1 ---------------------
    # Identical to the gate's firing quantity: it fires when s_t > gamma.
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.abs(sp.d_ar[elig_pos]) / sp.sigma[elig_pos]

    s_bad = ~np.isfinite(s)
    n_s_nonfinite = int(np.count_nonzero(s_bad))
    s_nonfinite_dates = list(dates[s_bad])

    # ---- VI at each horizon, NaNs retained and attributed ----------------
    out: Dict[int, HorizonSeries] = {}
    for h in horizons:
        vi_full = vi_at_lag(lp, h)
        out[int(h)] = _classify_nans(lp, elig_pos, vi_full[elig_pos], int(h))

    series = ObservedSeries(
        dates=dates,
        s=s,
        horizons=out,
        n_rebalances=len(lp),
        n_eligible=n_eligible,
        k_frozen=lp.k_frozen,
        n_s_nonfinite=n_s_nonfinite,
        s_nonfinite_dates=s_nonfinite_dates,
    )

    if verbose:
        print(format_load_report(series))
    return series


def format_load_report(obs: ObservedSeries) -> str:
    """Observation accounting. Expected vs actual, and every NaN attributed."""
    L: List[str] = []
    L.append("  [2B] observed series -- no statistic computed")
    L.append(f"       rebalances {obs.n_rebalances}, eligible {obs.n_eligible} "
             f"(expected {EXPECTED_ELIGIBLE}), k frozen {obs.k_frozen}")
    L.append(f"       s_t finite {obs.n_eligible - obs.n_s_nonfinite} / "
             f"{obs.n_eligible}")
    if obs.n_s_nonfinite:
        L.append(f"       *** {obs.n_s_nonfinite} non-finite s_t "
                 f"(sigma_hat == 0); first {obs.s_nonfinite_dates[0].date()}")
    L.append("")
    L.append("       h   n used   expected   boundary NaN   floor NaN")
    for h in sorted(obs.horizons, reverse=True):
        hs = obs.horizons[h]
        flag = "" if hs.matches_expected else "   <-- SHORT"
        L.append(f"       {hs.horizon:<3d} {hs.n_used:6d}   {hs.n_expected:8d}   "
                 f"{hs.n_boundary_nan:12d}   {hs.n_floor_nan:9d}{flag}")

    for h in sorted(obs.horizons, reverse=True):
        hs = obs.horizons[h]
        if hs.n_boundary_nan:
            L.append("")
            L.append(f"       *** h={h}: {hs.n_boundary_nan} boundary NaN inside "
                     "the eligible set. Expected 0 -- eligibility begins at")
            L.append("       *** position 7 and the boundary band is 0..h-1. "
                     "Investigate before use.")
        if hs.n_floor_nan:
            L.append("")
            L.append(f"       h={h}: {hs.n_floor_nan} floor NaN "
                     f"(< {MIN_COMMON} shared permnos across {h} rebalances)")
            for j, d, c in zip(hs.floor_positions, hs.floor_dates,
                               hs.floor_common):
                L.append(f"         eligible position {j:3d}  {d.date()}  "
                         f"common = {c}")
    return "\n".join(L)
