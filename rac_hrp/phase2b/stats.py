"""
rac_hrp.phase2b.stats
=====================
Phase 2B -- statistical core and observed-series loader.

Specification: PHASE2B_SPEC.md

CONTENTS
--------
Two halves, merged. The statistical core -- Spearman, circular block bootstrap,
and the section 2 size / power / falsification harnesses -- was written and
tested first; it is recovered verbatim from commit 1a3787c except for the block
length change recorded immediately below. The loader wires it to the repo.

BLOCK LENGTH -- SUBSTITUTED, AND NOT NUMERICALLY NEUTRAL
--------------------------------------------------------
The recovered core carried its own Politis-White so it could be tested with no
repo dependency, and its docstring said to prefer the repo's. Done: the local
implementation is deleted and `phase2.stats.politis_white_block_length` is
imported in its place, reaching every call site through the `block_length=None`
branch. Spec section 1 carries the mechanism over unchanged, and the repo's is
the implementation that produced the block lengths recorded in the Phase 2A
gate (19) and the 2E horizon artefact (13).

The interfaces are compatible -- the repo's is `(x: np.ndarray) -> int`, and no
call site here passed the local `k_max` -- but the two are NOT the same
function. They differ in the m_hat search (different rho indexing and stopping
rule), in the d-hat constant (`2*d**2` on correlations vs `(4/3)*G0**2` on
autocovariances), in the maximum-b clip (`n//2` vs `ceil(min(3*sqrt(n), n/3))`)
and in NaN handling: the repo's filters non-finite input, the local one
propagated it. The swap can therefore change block lengths, and through them
p-values. It is deliberate, it is reported, and it is not silent.

WHAT `load_series` IS
---------------------
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
from scipy import stats

from ..config import Config, TEST_START
from ..data.panel import Panels
from ..phase2.calibration import StructuralPass, structural_pass
from ..phase2.horizon import (LabelledPass, _vi_pair, assert_equivalent_to_gate,
                              labelled_pass, vi_at_lag)
# THE validated Politis-White. Replaces the recovered core's self-contained
# copy; see the module docstring for how the two differ.
from ..phase2.stats import politis_white_block_length

__all__ = [
    "spearman_rho",
    "politis_white_block_length",
    "circular_block_indices",
    "bootstrap_test",
    "size_check",
    "power_curve",
    "falsification_check",
    # merged in from the loader half
    "load_series",
    "format_load_report",
    "ObservedSeries",
    "HorizonSeries",
    "HoldoutReached",
]
# NOTE: `mde80` was already absent from the recovered file's __all__. Left as
# found rather than quietly corrected -- flagged instead.

# Spec section 1: h = 5 is the fixed gating horizon; h = 1 is computed and
# reported, non-gating. Ordering is load-bearing only for readability.
HORIZONS: Tuple[int, ...] = (5, 1)

# Phase 2A's eligible set. Asserted, not assumed -- see `load_series`.
EXPECTED_ELIGIBLE = 233

# Read off `_vi_pair` rather than restated, so this can never drift from the
# guard it is attributing NaNs to.
MIN_COMMON: int = int(
    inspect.signature(_vi_pair).parameters["min_common"].default)


# ==========================================================================
# STATISTICAL CORE -- recovered from 1a3787c
#
# Operates on two aligned 1-D arrays and knows nothing about covariance
# estimation, clustering or the trigger. The only change from the recovered
# file is that `politis_white_block_length` is now the repo's, imported above.
# ==========================================================================

def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation. Ties handled by average ranks."""
    return float(stats.spearmanr(x, y).statistic)


def circular_block_indices(n: int, b: int, rng: np.random.Generator) -> np.ndarray:
    """Index vector of length n drawn as circular blocks of length b."""
    b = max(1, min(b, n))
    n_blocks = int(np.ceil(n / b))
    starts = rng.integers(0, n, size=n_blocks)
    idx = (starts[:, None] + np.arange(b)[None, :]).ravel() % n
    return idx[:n]


def bootstrap_test(
    s: np.ndarray,
    vi: np.ndarray,
    *,
    seed: int,
    replicates: int = 10_000,
    block_length: int | None = None,
) -> dict:
    """
    One-sided block-bootstrap test of H0: rho_s <= 0.

    The pair (s_t, vi_t) is resampled jointly in circular blocks, preserving both
    serial dependence and the cross-series pairing. The resulting distribution is
    centred on the observed statistic, giving

        p = (1 + #{rho* - rho_hat >= rho_hat}) / (B_kept + 1)

    which is the Phase 2A convention.

    P SATURATES AT ITS FLOOR ONCE rho_hat > 0.5 -- READ RHO, NOT P
    ---------------------------------------------------------------
    The exceedance condition rearranges to rho* >= 2 * rho_hat. Spearman is
    bounded above by 1, so the centred statistic rho* - rho_hat cannot exceed
    1 - rho_hat, and an exceedance is possible at all only when

        1 - rho_hat >= rho_hat,  i.e.  rho_hat <= 0.5.

    For any rho_hat > 0.5 the count is exactly zero by arithmetic, and

        p == p_floor == 1 / (B_kept + 1)

    identically. This is not evidence accumulating until it exhausts the
    resolution B provides -- it is the statistic running out of room. Raising B
    lowers p_floor and adds no information whatsoever. A p of 1e-4 at B = 10,000
    means "rho_hat > 0.5" and nothing more precise, and it would read the same
    at rho_hat = 0.51 and rho_hat = 0.99.

    The implication is asymmetric, and the weaker direction is the one that
    matters in practice:

        rho_hat > 0.5   ==>  p == p_floor          (guaranteed, by the bound)
        p == p_floor    =/=> rho_hat > 0.5         (it can also just mean that
                                                    no replicate happened to
                                                    reach 2 * rho_hat)

    Empirically, at B = 1,000 on n = 150 the floor is already reached by
    rho_hat ~ 0.30, well below the guaranteed point. So p == p_floor cannot be
    inverted into any statement about rho_hat at all. Report rho alongside p
    whenever p sits on its floor; the p-value alone is uninformative there.

    The centring convention is frozen (spec section 1, Phase 2A inheritance) and
    is NOT changed here. This is documentation of a property, not a repair.
    """
    s = np.asarray(s, dtype=float)
    vi = np.asarray(vi, dtype=float)
    if s.shape != vi.shape:
        raise ValueError(f"length mismatch: s={s.shape}, vi={vi.shape}")
    n = s.size

    if block_length is None:
        b_s = politis_white_block_length(s)
        b_v = politis_white_block_length(vi)
        block_length = max(b_s, b_v)

    rho_hat = spearman_rho(s, vi)
    rng = np.random.default_rng(seed)

    reps = np.empty(replicates)
    reps.fill(np.nan)
    for i in range(replicates):
        idx = circular_block_indices(n, block_length, rng)
        ss, vv = s[idx], vi[idx]
        if np.all(ss == ss[0]) or np.all(vv == vv[0]):
            continue  # degenerate
        reps[i] = spearman_rho(ss, vv)

    kept = reps[np.isfinite(reps)]
    b_kept = kept.size
    if b_kept == 0:
        raise RuntimeError("all bootstrap replicates degenerate")

    centred = kept - rho_hat
    p = (1 + int(np.sum(centred >= rho_hat))) / (b_kept + 1)

    return {
        "rho": rho_hat,
        "p": p,
        "n": n,
        "block_length": int(block_length),
        "replicates_kept": b_kept,
        "replicates_requested": replicates,
        "p_floor": 1.0 / (b_kept + 1),
        "seed": seed,
    }


# ==========================================================================
# Section 2 checks -- NOT YET RUN
# ==========================================================================

def size_check(
    s: np.ndarray,
    vi: np.ndarray,
    *,
    seed: int,
    reps: int = 2_000,
    replicates: int = 2_000,
    block_length: int | None = None,
    alpha: float = 0.05,
) -> dict:
    """
    Empirical size under a true null.

    Each replication resamples s and vi in circular blocks with INDEPENDENT index
    vectors. That preserves each series' own serial dependence while destroying any
    association between them, so H0 holds by construction.

    Spec §2 fails this check if empirical size exceeds 0.10.
    """
    s = np.asarray(s, dtype=float)
    vi = np.asarray(vi, dtype=float)
    n = s.size

    if block_length is None:
        block_length = max(
            politis_white_block_length(s), politis_white_block_length(vi)
        )

    rng = np.random.default_rng(seed)
    rejects = 0
    for r in range(reps):
        s_star = s[circular_block_indices(n, block_length, rng)]
        v_star = vi[circular_block_indices(n, block_length, rng)]
        out = bootstrap_test(
            s_star, v_star,
            seed=int(rng.integers(0, 2**31 - 1)),
            replicates=replicates,
            block_length=block_length,
        )
        rejects += int(out["p"] < alpha)

    size = rejects / reps
    return {
        "empirical_size": size,
        "mc_se": float(np.sqrt(size * (1 - size) / reps)),
        "nominal": alpha,
        "reps": reps,
        "block_length": int(block_length),
        "pass": size <= 0.10,
    }


def _plant(s: np.ndarray, vi: np.ndarray, c: float) -> np.ndarray:
    """Add a monotone signal of strength c, scaled to vi's own spread."""
    z = stats.rankdata(s)
    z = (z - z.mean()) / z.std(ddof=0)
    return vi + c * np.std(vi, ddof=1) * z


def power_curve(
    s: np.ndarray,
    vi: np.ndarray,
    *,
    seed: int,
    c_grid=(0.0, 0.09, 0.15, 0.18, 0.21, 0.24, 0.30, 0.45),
    reps: int = 400,
    replicates: int = 1_000,
    block_length: int | None = None,
    alpha: float = 0.05,
) -> list[dict]:
    """
    Power against planted monotone association.

    Each replication block-resamples vi and s independently (true null), then adds a
    signal proportional to the standardised ranks of s. Reports achieved Spearman
    rho alongside power so MDE can be read on the rho scale, which is what the spec
    thresholds on (MDE80 <= 0.20).
    """
    s = np.asarray(s, dtype=float)
    vi = np.asarray(vi, dtype=float)
    n = s.size

    if block_length is None:
        block_length = max(
            politis_white_block_length(s), politis_white_block_length(vi)
        )

    rng = np.random.default_rng(seed)
    rows = []
    for c in c_grid:
        rejects, rhos = 0, []
        for _ in range(reps):
            s_star = s[circular_block_indices(n, block_length, rng)]
            v_star = vi[circular_block_indices(n, block_length, rng)]
            v_star = _plant(s_star, v_star, c)
            out = bootstrap_test(
                s_star, v_star,
                seed=int(rng.integers(0, 2**31 - 1)),
                replicates=replicates,
                block_length=block_length,
            )
            rejects += int(out["p"] < alpha)
            rhos.append(out["rho"])
        rows.append({
            "c": c,
            "achieved_rho": float(np.mean(rhos)),
            "power": rejects / reps,
            "reps": reps,
        })
    return rows


def mde80(curve: list[dict]) -> float | None:
    """
    Smallest achieved rho at which power reaches 0.80, by linear interpolation.

    Sensitive to grid resolution: a coarse grid straddling 0.80 interpolates across
    a convex stretch of the power curve and overestimates. Verified on synthetic
    data, where a five-point grid gave 0.216 and a refined grid gave 0.183 for the
    same setup. Keep the grid dense near the crossing.
    """
    pts = sorted(((r["achieved_rho"], r["power"]) for r in curve))
    for (r0, p0), (r1, p1) in zip(pts, pts[1:]):
        if p0 < 0.80 <= p1:
            if p1 == p0:
                return r1
            return r0 + (0.80 - p0) * (r1 - r0) / (p1 - p0)
    return None if pts[-1][1] < 0.80 else pts[0][0]


def falsification_check(
    environments: list[tuple[np.ndarray, np.ndarray]],
    *,
    seed: int,
    replicates: int = 2_000,
    alpha: float = 0.05,
) -> dict:
    """
    Run the test end to end on the Phase 2D structureless null environments.

    `environments` is a list of (s, vi) pairs produced by the existing structureless
    generators. Spec §2 fails if the test is significant in more than 10% of them.
    """
    rng = np.random.default_rng(seed)
    results = []
    for s_env, vi_env in environments:
        out = bootstrap_test(
            s_env, vi_env,
            seed=int(rng.integers(0, 2**31 - 1)),
            replicates=replicates,
        )
        results.append(out)
    rate = float(np.mean([r["p"] < alpha for r in results]))
    return {
        "rejection_rate": rate,
        "n_environments": len(results),
        "alpha": alpha,
        "pass": rate <= 0.10,
        "detail": results,
    }


# ==========================================================================
# REPO WIRING
# ==========================================================================

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
    gate_vi: np.ndarray             # frozen gate's one-step VI, eligible subset
    horizons: Dict[int, HorizonSeries]
    n_rebalances: int               # full labelled pass
    n_eligible: int
    k_frozen: int
    n_s_nonfinite: int = 0
    s_nonfinite_dates: List[pd.Timestamp] = field(default_factory=list)

    def pair(self, horizon: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """(s, VI) at one horizon, NaNs intact. Alignment is positional."""
        return self.s, self.horizons[horizon].vi

    def crosscheck_h1(self) -> Tuple[int, int, bool]:
        """Floor NaNs at h=1 vs NaNs in the frozen gate's own VI series.

        `assert_equivalent_to_gate` already forces the h=1 series to match
        `sp.vi` bitwise over the FULL labelled-pass array. This checks the
        eligible-subset NaN ACCOUNTING in `_classify_nans`, which is separate
        code and can be wrong independently of that guarantee.

        Returns (floor NaN at h=1, NaN in gate VI, agree).
        """
        mine = self.horizons[1].n_floor_nan
        gate = int(np.count_nonzero(np.isnan(self.gate_vi)))
        return mine, gate, mine == gate


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
        gate_vi=np.asarray(sp.vi, dtype=float)[elig_pos],
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

    if 1 in obs.horizons:
        mine, gate, agree = obs.crosscheck_h1()
        L.append("")
        L.append(f"       h=1 cross-check: floor NaN {mine} vs gate VI NaN "
                 f"{gate} -- {'agree' if agree else '*** DISAGREE ***'}")

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
