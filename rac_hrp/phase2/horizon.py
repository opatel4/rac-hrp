"""
rac_hrp.phase2.horizon
======================
2E-HORIZON: horizon-matched cluster informativeness.

Frozen specification: RAC_HRP_Phase2E_PreSpec_rev5.md
SHA-256: 6153831fa0da7a52673a48bd24cc208fabd857715d7e3a2e5c61c0162ef88b46

WHAT THIS IS
------------
The frozen gate measures variation of information between clusterings at
CONSECUTIVE rebalances. The trigger statistic is algebraically a FIVE-rebalance
change in the absorption ratio (PreSpec section 1). The two are sampled at
different horizons. This module recomputes D_VI with VI taken between the
clustering at t and the clustering at t-5, changing the horizon and nothing else.

NON-GATING. No result here can render any gamma admissible or alter any frozen
value. The Phase 2A verdict stands regardless of what this returns.

WHY A PARALLEL LOOP
-------------------
`calibration.structural_pass` holds cluster labels only in a rolling `prev_labels`
variable and discards them; `StructuralPass` exposes the VI series but not the
per-date labels. A five-lag pairing needs labels at every date.

`calibration.py` is hashed in outputs/phase2/calibration_manifest.json and MUST
NOT be modified. So this module duplicates the loop and retains the labels.

Duplication is a silent-divergence risk -- the exact failure mode this project has
hit before. It is converted into a checked invariant: `assert_equivalent_to_gate`
recomputes the ONE-STEP VI series from the retained labels and requires bitwise
equality with the frozen `StructuralPass.vi`. If the duplicate has drifted
anywhere, the run aborts before any statistic is computed. Calling the diagnostic
without that check is a programming error and is enforced below.

DELIBERATE OMISSION
-------------------
The gate loop also computes counterfactual re-cluster turnover. That branch is
excluded here: it is expensive, this diagnostic never reads it, and VI does not
depend on it. The equivalence assertion covers VI, which is the only quantity used.

INFERENCE
---------
`d_vi`, `circular_block_bootstrap_p` and `holm_adjust` are imported from
`phase2.stats` and called unchanged. The Politis-White block length is selected
from the series actually being resampled, so it may differ from the gate's; both
are reported (PreSpec section 3.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import Config
from ..core.clustering import (build_tree, cluster_labels, n_clusters_from_rule,
                               variation_of_information)
from ..core.covariance import estimate
from ..core.pca_mp import spectrum, absorption_ratio
from ..data.panel import Panels
from ..data.universe import UniverseBuilder
from .calibration import StructuralPass, structural_pass
from .stats import circular_block_bootstrap_p, d_vi, holm_adjust

HORIZON = 5
BOOTSTRAP_SEED_BASE = 100756712          # PreSpec rev.5 section 3.3, OS entropy
BOOTSTRAP_REPLICATES = 10_000
ALPHA = 0.05
GAMMA_CANDIDATES: Tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
EXPECTED_EVENT_COUNTS: Dict[float, int] = {0.5: 149, 1.0: 111, 1.5: 81, 2.0: 58}
EXPECTED_ELIGIBLE = 233


def bootstrap_seed_for(gamma: float) -> int:
    """Same derivation rule as the frozen gate; gamma ordering is load-bearing."""
    return BOOTSTRAP_SEED_BASE + GAMMA_CANDIDATES.index(gamma)


# --------------------------------------------------------------------------
# Labelled pass
# --------------------------------------------------------------------------
@dataclass
class LabelledPass:
    """Per-rebalance cluster labels, retained so any horizon can be paired."""
    dates: pd.DatetimeIndex
    permnos: List[np.ndarray] = field(default_factory=list)
    labels: List[np.ndarray] = field(default_factory=list)
    ar: np.ndarray = field(default_factory=lambda: np.array([]))
    k_frozen: int = 0

    def __len__(self) -> int:
        return len(self.dates)


def labelled_pass(P: Panels, cfg: Config, eval_pos: np.ndarray,
                  verbose: bool = False) -> LabelledPass:
    """Duplicate of the gate's structural loop, retaining labels at every date.

    Every call inside this loop mirrors `calibration.structural_pass` exactly,
    in the same order, with the same arguments. The only differences are that
    labels are retained rather than discarded, and the turnover branch is
    omitted (see module docstring).
    """
    ub = UniverseBuilder(P, cfg)
    cal = P.returns.index
    rebal = eval_pos[::cfg.rebalance_freq]

    dates: List[pd.Timestamp] = []
    permnos_all: List[np.ndarray] = []
    labels_all: List[np.ndarray] = []
    ars: List[float] = []
    k_frozen: Optional[int] = None

    for t in rebal:
        snap = ub.snapshot(cal[t])
        if len(snap.permnos) < 10:
            continue
        lo = t - cfg.cov_window + 1
        if lo < 0:
            continue
        X = P.returns.iloc[lo:t + 1][snap.permnos]
        ok = X.notna().mean() >= (1.0 - cfg.max_missing_frac)
        permnos = snap.permnos[ok.values]
        if len(permnos) < 10:
            continue
        X = X[permnos].fillna(0.0)

        cov = estimate(X.values, cfg.cov_estimator)
        spec = spectrum(cov, cfg.cov_window, min_components=cfg.ar_min_components)
        if k_frozen is None:
            k_frozen = int(spec.k)

        ar = absorption_ratio(spec, k=k_frozen)
        nc = n_clusters_from_rule(spec, cfg.n_clusters_rule,
                                  cfg.n_clusters_min, cfg.n_clusters_max)
        Z, order, _ = build_tree(cov, spec, space=cfg.cluster_space,
                                 k=k_frozen, canonical_order=True)
        labels = cluster_labels(Z, nc)

        dates.append(cal[t])
        permnos_all.append(np.asarray(permnos))
        labels_all.append(np.asarray(labels))
        ars.append(ar)

    if verbose:
        print(f"    labelled pass: {len(dates)} rebalances, k frozen = {k_frozen}")

    return LabelledPass(pd.DatetimeIndex(dates), permnos_all, labels_all,
                        np.asarray(ars), int(k_frozen or 0))


# --------------------------------------------------------------------------
# VI at an arbitrary lag
# --------------------------------------------------------------------------
def _vi_pair(permnos_a: np.ndarray, labels_a: np.ndarray,
             permnos_b: np.ndarray, labels_b: np.ndarray,
             min_common: int = 10) -> float:
    """VI on the intersection of two universes. Mirrors the gate's construction."""
    common = np.intersect1d(permnos_b, permnos_a)
    if len(common) < min_common:
        return np.nan
    map_a = {p: l for p, l in zip(permnos_a, labels_a)}
    map_b = {p: l for p, l in zip(permnos_b, labels_b)}
    a = np.array([map_b[p] for p in common])          # earlier date
    b = np.array([map_a[p] for p in common])          # later date
    return variation_of_information(a, b)


def vi_at_lag(lp: LabelledPass, lag: int) -> np.ndarray:
    """VI between the clustering at t and at t-lag, for every rebalance."""
    n = len(lp)
    out = np.full(n, np.nan)
    for i in range(lag, n):
        out[i] = _vi_pair(lp.permnos[i], lp.labels[i],
                          lp.permnos[i - lag], lp.labels[i - lag])
    return out


# --------------------------------------------------------------------------
# Equivalence precondition -- MANDATORY
# --------------------------------------------------------------------------
class GateDivergence(RuntimeError):
    """The duplicated loop does not reproduce the frozen gate's VI series."""


def assert_equivalent_to_gate(lp: LabelledPass, sp: StructuralPass) -> None:
    """Require that the retained labels reproduce the frozen one-step VI series.

    This is the guard that makes the duplicated loop safe. Same inputs, same
    call sequence, so bitwise equality is the correct bar. Any divergence means
    the duplicate has drifted and nothing downstream is meaningful.
    """
    if len(lp) != len(sp.dates):
        raise GateDivergence(
            f"rebalance count differs: labelled {len(lp)}, gate {len(sp.dates)}")
    if not lp.dates.equals(sp.dates):
        raise GateDivergence("rebalance dates differ")
    if lp.k_frozen != sp.k_frozen:
        raise GateDivergence(
            f"k differs: labelled {lp.k_frozen}, gate {sp.k_frozen}")

    recomputed = vi_at_lag(lp, 1)
    gate = np.asarray(sp.vi, dtype=float)

    nan_mismatch = np.isnan(recomputed) != np.isnan(gate)
    if nan_mismatch.any():
        bad = np.where(nan_mismatch)[0]
        raise GateDivergence(
            f"NaN pattern differs at {len(bad)} rebalance(s), first at index {bad[0]}")

    both = ~np.isnan(gate)
    if not np.array_equal(recomputed[both], gate[both]):
        diff = np.abs(recomputed[both] - gate[both])
        j = int(np.argmax(diff))
        raise GateDivergence(
            f"one-step VI differs from the frozen gate; max |diff| = {diff.max():.3e} "
            f"at eligible-array position {j}")


# --------------------------------------------------------------------------
# The diagnostic
# --------------------------------------------------------------------------
@dataclass
class HorizonCell:
    gamma: float
    n_events: int
    d_vi_h: float
    p_raw: float
    p_holm: float
    block_length: int
    degenerate: int
    median_vi_fired: float
    median_vi_not: float


@dataclass
class HorizonResult:
    horizon: int
    n_eligible: int
    cells: List[HorizonCell]
    gate_block_lengths: Dict[float, int]
    outcome: str
    spec_sha256: str = "6153831fa0da7a52673a48bd24cc208fabd857715d7e3a2e5c61c0162ef88b46"


def run_horizon(P: Panels, cfg: Config, eval_pos: np.ndarray,
                fold_bounds=None, verbose: bool = True) -> HorizonResult:
    """2E-HORIZON, end to end. Aborts unless the gate equivalence check passes."""
    if verbose:
        print("  [2E-HORIZON] frozen gate pass ...")
    sp = structural_pass(P, cfg, eval_pos, fold_bounds, verbose=verbose)

    if verbose:
        print("  [2E-HORIZON] labelled pass ...")
    lp = labelled_pass(P, cfg, eval_pos, verbose=verbose)

    if verbose:
        print("  [2E-HORIZON] equivalence check against the frozen gate ...")
    assert_equivalent_to_gate(lp, sp)
    if verbose:
        print("            OK -- one-step VI reproduces the gate bitwise")

    vi_h = vi_at_lag(lp, HORIZON)

    elig_pos = np.where(sp.eligible)[0]
    E = len(elig_pos)
    if E != EXPECTED_ELIGIBLE:
        raise GateDivergence(f"eligible set is {E}, expected {EXPECTED_ELIGIBLE}")

    vi_h_e = vi_h[elig_pos]
    cells: List[HorizonCell] = []
    raw: Dict[float, float] = {}

    for gamma in GAMMA_CANDIDATES:
        fired_full = np.zeros(len(sp.ar), dtype=bool)
        with np.errstate(invalid="ignore"):
            fired_full[elig_pos] = (np.abs(sp.d_ar[elig_pos])
                                    > gamma * sp.sigma[elig_pos])
        fired_e = fired_full[elig_pos]
        n_events = int(fired_e.sum())

        expected = EXPECTED_EVENT_COUNTS[gamma]
        if n_events != expected:
            raise GateDivergence(
                f"gamma={gamma}: {n_events} events, frozen gate reports {expected}")

        boot = circular_block_bootstrap_p(vi_h_e, fired_e,
                                          seed=bootstrap_seed_for(gamma),
                                          replicates=BOOTSTRAP_REPLICATES)
        raw[gamma] = boot.p_value
        finite = ~np.isnan(vi_h_e)
        cells.append(HorizonCell(
            gamma=gamma,
            n_events=n_events,
            d_vi_h=d_vi(vi_h_e, fired_e),
            p_raw=boot.p_value,
            p_holm=np.nan,
            block_length=int(boot.block_length),
            degenerate=int(boot.n_degenerate),
            median_vi_fired=float(np.nanmedian(vi_h_e[fired_e & finite])),
            median_vi_not=float(np.nanmedian(vi_h_e[(~fired_e) & finite])),
        ))

    adj = holm_adjust(raw)
    for c in cells:
        c.p_holm = adj[c.gamma]

    resolved = [c for c in cells if c.p_holm < ALPHA and c.d_vi_h > 0]
    signs = {np.sign(c.d_vi_h) for c in cells if np.isfinite(c.d_vi_h)}
    if resolved:
        outcome = "H"
    elif len(signs) > 1:
        outcome = "U"
    else:
        outcome = "T"

    return HorizonResult(horizon=HORIZON, n_eligible=E, cells=cells,
                         gate_block_lengths={}, outcome=outcome)


def format_report(res: HorizonResult) -> str:
    L: List[str] = []
    L.append("2E-HORIZON -- horizon-matched cluster informativeness")
    L.append(f"  spec SHA-256 {res.spec_sha256}")
    L.append(f"  horizon {res.horizon} rebalances, eligible set {res.n_eligible}")
    L.append("")
    L.append("  gamma  events   D_VI(5)   p raw   p Holm   block   med fired   med not")
    for c in res.cells:
        L.append(f"  {c.gamma:5.1f}  {c.n_events:6d}  {c.d_vi_h:+8.4f}  "
                 f"{c.p_raw:6.3f}  {c.p_holm:7.3f}  {c.block_length:5d}  "
                 f"{c.median_vi_fired:9.4f}  {c.median_vi_not:8.4f}")
    L.append("")
    verdicts = {
        "H": "OUTCOME H -- the effect is statistically resolved at the matched horizon. "
             "This confers NO admissibility; the Phase 2A verdict stands.",
        "T": "OUTCOME T -- horizon alignment does not recover statistically detectable "
             "cluster informativeness. The topology account remains compatible but is NOT "
             "identified: non-rejection may equally reflect limited power. Report with 2E-POWER.",
        "U": "OUTCOME U -- unresolved. Sign reversal or non-monotonicity the decision rule "
             "does not anticipate. Report the anomaly; assert no interpretation.",
    }
    L.append("  " + verdicts[res.outcome])
    return "\n".join(L)
