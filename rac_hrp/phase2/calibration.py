"""
rac_hrp.phase2.calibration
==========================
Phase 2 structural calibration gate — STEPS 1-3 of the frozen procedure.

Implements the signed pre-registration:
    "PHASE 2 — PRE-REGISTRATION & CALIBRATION GATE (rev.5)"  [FROZEN]

PERFORMANCE-BLIND BY CONSTRUCTION
---------------------------------
This module never computes a portfolio return, Sharpe ratio, drawdown, or any
other performance quantity. It cannot: it never calls the backtest engine's
return path and never touches the risk-free series. That is not a convention to
be remembered — the code has no way to produce a performance number, so
selection cannot be influenced by one even accidentally.

WHAT IT DOES
    Step 1  structural diagnostics only, for every gamma candidate
    Step 2  apply the deterministic selection rule automatically
    Step 3  write the selected gamma and full diagnostics to a hashed record

WHAT HAPPENS NEXT (not here)
    Step 4  Null Gate v2 at the selected gamma. The existing verdict applies
            only to gamma = 1.0 and is NOT inherited.
    Step 5  only on a pass, generate performance output.

If no candidate passes, Phase 2 STOPS. The "least bad" candidate is not
selected. If the selected candidate later fails Null Gate v2, Phase 2 STOPS —
there is no fall-through to the next gamma.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import Config
from ..core.clustering import (build_tree, cluster_labels, n_clusters_from_rule,
                               variation_of_information)
from ..core.covariance import estimate
from ..core.pca_mp import spectrum, absorption_ratio
from ..core.allocators import hrp_weights
from ..data.panel import Panels
from ..data.universe import UniverseBuilder
from .config import (Phase2Config, AR_SMOOTH_REBALANCES, AR_SMOOTH_MIN_PERIODS,
                     AR_SIGMA_REBALANCES, AR_SIGMA_MIN_PERIODS, AR_SIGMA_DDOF,
                     AR_SIGMA_SHIFT)
from .stats import (j_star, placebo_threshold, timing_variation, d_vi,
                    circular_block_bootstrap_p, holm_adjust)


@dataclass
class StructuralPass:
    """Everything the gate needs, computed independently of gamma."""
    dates: pd.DatetimeIndex          # rebalance dates, in order
    ar: np.ndarray                   # absorption ratio at each rebalance
    d_ar: np.ndarray                 # smoothed first difference
    sigma: np.ndarray                # trailing scale estimate (shifted)
    eligible: np.ndarray             # bool: sigma defined -> a trigger COULD fire
    vi: np.ndarray                   # counterfactual VI vs the previous clustering
    turnover: np.ndarray             # counterfactual re-cluster turnover
    fold_of: np.ndarray              # development fold index per rebalance
    k_frozen: int


def structural_pass(P: Panels, cfg: Config, eval_pos: np.ndarray,
                    fold_bounds: Optional[List[Tuple[int, int]]] = None,
                    verbose: bool = False) -> StructuralPass:
    """Compute AR, dAR, sigma, and the COUNTERFACTUAL clustering diagnostics.

    The counterfactual is essential: hypothetical clusters are recomputed at
    EVERY eligible rebalance, including those where a live strategy would not
    re-cluster. Only then are triggered and non-triggered structural change
    directly comparable.

    k is frozen at the first eligible rebalance (mp_k_mode = fixed_per_run) and
    held for the whole run. No look-ahead: it comes from the trailing window
    ending at that first date.
    """
    ub = UniverseBuilder(P, cfg)
    cal = P.returns.index
    rebal = eval_pos[::cfg.rebalance_freq]

    dates, ars, vis, turns, folds = [], [], [], [], []
    k_frozen: Optional[int] = None
    prev_labels: Optional[np.ndarray] = None
    prev_permnos: Optional[np.ndarray] = None
    prev_Z = prev_order = None

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
            k_frozen = int(spec.k)              # inception-calibrated, held for the run

        ar = absorption_ratio(spec, k=k_frozen)
        nc = n_clusters_from_rule(spec, cfg.n_clusters_rule,
                                  cfg.n_clusters_min, cfg.n_clusters_max)
        Z, order, _ = build_tree(cov, spec, space=cfg.cluster_space,
                                 k=k_frozen, canonical_order=True)
        labels = cluster_labels(Z, nc)

        # ---- counterfactual structural change vs the PREVIOUS clustering ----
        vi_t, turn_t = np.nan, np.nan
        if prev_labels is not None:
            common = np.intersect1d(permnos, prev_permnos)
            if len(common) >= 10:
                cur_map = {p: l for p, l in zip(permnos, labels)}
                pre_map = {p: l for p, l in zip(prev_permnos, prev_labels)}
                a = np.array([pre_map[p] for p in common])
                b = np.array([cur_map[p] for p in common])
                vi_t = variation_of_information(a, b)

                # attributable turnover: same date, same covariance, same
                # universe, same allocator -- only the TREE differs.
                try:
                    w_new = pd.Series(hrp_weights(cov, order), index=permnos)
                    pos_prev = np.array([list(permnos).index(p) for p in common])
                    sub = cov[np.ix_(pos_prev, pos_prev)]
                    prev_rank = {p: i for i, p in enumerate(prev_permnos)}
                    old_order_full = [p for p in prev_permnos if p in set(common)]
                    idx_old = np.array([list(common).index(p) for p in old_order_full])
                    w_old = pd.Series(hrp_weights(sub, idx_old), index=common)
                    wn = w_new.reindex(common).fillna(0.0)
                    wn = wn / wn.sum() if wn.sum() > 0 else wn
                    turn_t = 0.5 * float(np.abs(wn.values - w_old.values).sum())
                except Exception:
                    turn_t = np.nan

        dates.append(cal[t]); ars.append(ar); vis.append(vi_t); turns.append(turn_t)
        if fold_bounds:
            f = next((i for i, (a0, b0) in enumerate(fold_bounds) if a0 <= t <= b0), -1)
        else:
            f = 0
        folds.append(f)
        prev_labels, prev_permnos, prev_Z, prev_order = labels, permnos, Z, order

    idx = pd.DatetimeIndex(dates)
    s = pd.Series(ars, index=idx)

    # ---- trigger inputs, exactly as frozen (section 1) -------------------
    s_sm = s.rolling(AR_SMOOTH_REBALANCES, min_periods=AR_SMOOTH_MIN_PERIODS).mean()
    d = s_sm.diff()
    sig = d.rolling(AR_SIGMA_REBALANCES,
                    min_periods=AR_SIGMA_MIN_PERIODS).std(ddof=AR_SIGMA_DDOF)
    sig = sig.shift(AR_SIGMA_SHIFT)
    eligible = sig.notna().values

    if verbose:
        print(f"    rebalances {len(idx)}, eligible {int(eligible.sum())}, "
              f"k frozen = {k_frozen}")

    return StructuralPass(idx, s.values, d.values, sig.values, eligible,
                          np.array(vis), np.array(turns),
                          np.array(folds), int(k_frozen or 0))


# ==========================================================================
# Step 1b -- evaluate one gamma candidate against the hard-gate table
# ==========================================================================
@dataclass
class CandidateResult:
    gamma: float
    n_events: int
    n_eligible: int
    firing_rate: float
    events_per_fold: Dict[int, int]
    cv_gap: float
    modal_gap_share: float
    j_star: float
    j_star_arg: Tuple[int, int]
    j_threshold: float
    d_vi: float
    p_raw: float
    p_holm: float = np.nan
    block_length: int = 0
    n_degenerate: int = 0
    turnover_annual: float = np.nan     # DIAGNOSTIC ONLY -- never gates
    passes: Dict[str, bool] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.passes.values())


def evaluate_candidate(sp: StructuralPass, gamma: float, cfg2: Phase2Config,
                       verbose: bool = False) -> CandidateResult:
    """All five hard criteria plus the turnover diagnostic, for one gamma."""
    elig_pos = np.where(sp.eligible)[0]
    E = len(elig_pos)
    fired_full = np.zeros(len(sp.ar), dtype=bool)
    with np.errstate(invalid="ignore"):
        fired_full[elig_pos] = (np.abs(sp.d_ar[elig_pos])
                                > gamma * sp.sigma[elig_pos])

    trig_local = np.where(fired_full[elig_pos])[0]     # indices INTO the eligible set
    n_events = len(trig_local)
    f = n_events / E if E else 0.0

    # 1. informativeness
    ok_fire = (cfg2.firing_min <= f <= cfg2.firing_max)

    # 2. event sufficiency, per development fold
    per_fold: Dict[int, int] = {}
    for fold in sorted(set(sp.fold_of[elig_pos].tolist())):
        m = sp.fold_of[elig_pos] == fold
        per_fold[int(fold)] = int(fired_full[elig_pos][m].sum())
    ok_events = bool(per_fold) and all(v >= cfg2.min_events_per_fold
                                       for v in per_fold.values())

    # 3. timing variation
    ts = timing_variation(trig_local)
    ok_timing = (np.isfinite(ts.cv_gap) and ts.cv_gap >= cfg2.cv_gap_min
                 and np.isfinite(ts.modal_gap_share)
                 and ts.modal_gap_share <= cfg2.modal_gap_share_max)

    # 4. separation -- threshold RECOMPUTED at this candidate's own event count
    js, arg = j_star(trig_local, E, cfg2.separation_periods)
    thr = placebo_threshold(E, n_events, cfg2.separation_periods,
                            cfg2.placebo_seed, cfg2.placebo_draws,
                            cfg2.placebo_percentile)
    ok_sep = js <= thr                                  # WEAK inequality

    # 5. cluster informativeness
    vi_e = sp.vi[elig_pos]
    fired_e = fired_full[elig_pos]
    m = np.isfinite(vi_e)
    boot = circular_block_bootstrap_p(vi_e[m], fired_e[m],
                                      seed=cfg2.bootstrap_seed_for(gamma),
                                      replicates=cfg2.bootstrap_replicates)

    # turnover -- DIAGNOSTIC, never gates
    tvals = sp.turnover[elig_pos][fired_e]
    tvals = tvals[np.isfinite(tvals)]
    span_years = max(len(elig_pos) / 12.0, 1e-9)
    turn = float(tvals.sum() / span_years) if len(tvals) else np.nan

    r = CandidateResult(
        gamma=gamma, n_events=n_events, n_eligible=E, firing_rate=f,
        events_per_fold=per_fold, cv_gap=ts.cv_gap,
        modal_gap_share=ts.modal_gap_share, j_star=js, j_star_arg=arg,
        j_threshold=thr, d_vi=boot.d_hat, p_raw=boot.p_value,
        block_length=boot.block_length, n_degenerate=boot.n_degenerate,
        turnover_annual=turn)
    r.passes = {"informativeness": ok_fire, "event_sufficiency": ok_events,
                "timing_variation": ok_timing, "separation": ok_sep,
                "cluster_informativeness": False}   # filled after Holm
    if verbose:
        print(f"    gamma={gamma}: events={n_events}/{E} ({f:.1%}), "
              f"J*={js:.4f} vs {thr:.4f}, D_VI={boot.d_hat:+.4f} p={boot.p_value:.4f}")
    return r


# ==========================================================================
# Step 2 -- deterministic selection
# ==========================================================================
def select_gamma(results: List[CandidateResult],
                 cfg2: Phase2Config) -> Optional[float]:
    """Closest to the inherited gamma among those passing EVERY hard criterion;
    ties broken toward the LARGER gamma (fewer interventions, lower turnover).

    Returns None if no candidate passes — Phase 2 then STOPS. The "least bad"
    candidate is never selected.
    """
    ok = [r for r in results if r.passed]
    if not ok:
        return None
    ok.sort(key=lambda r: (abs(r.gamma - cfg2.gamma_inherited), -r.gamma))
    return ok[0].gamma


# ==========================================================================
# Orchestration
# ==========================================================================
def run_calibration(P: Panels, cfg: Config, eval_pos: np.ndarray,
                    fold_bounds: Optional[List[Tuple[int, int]]] = None,
                    cfg2: Optional[Phase2Config] = None,
                    outdir: str = "outputs/phase2_calibration",
                    verbose: bool = True) -> dict:
    cfg2 = cfg2 or Phase2Config()
    os.makedirs(outdir, exist_ok=True)

    if verbose:
        print("  [1/3] structural pass (AR, dAR, sigma, counterfactual VI)")
    sp = structural_pass(P, cfg, eval_pos, fold_bounds, verbose=verbose)

    if verbose:
        print("  [2/3] evaluating candidates (NO performance computed)")
    results = [evaluate_candidate(sp, g, cfg2, verbose=verbose)
               for g in cfg2.gamma_candidates]

    # Holm across the four candidates, then finalise the inferential criterion
    holm = holm_adjust({r.gamma: r.p_raw for r in results})
    for r in results:
        r.p_holm = holm.get(r.gamma, np.nan)
        r.passes["cluster_informativeness"] = bool(
            np.isfinite(r.d_vi) and r.d_vi > 0
            and np.isfinite(r.p_holm) and r.p_holm < cfg2.holm_alpha)

    selected = select_gamma(results, cfg2)

    if verbose:
        print("  [3/3] writing frozen record")
    table = pd.DataFrame([{
        "gamma": r.gamma, "n_events": r.n_events, "n_eligible": r.n_eligible,
        "firing_rate": round(r.firing_rate, 4),
        "min_events_per_fold": min(r.events_per_fold.values()) if r.events_per_fold else 0,
        "cv_gap": round(r.cv_gap, 4) if np.isfinite(r.cv_gap) else np.nan,
        "modal_gap_share": round(r.modal_gap_share, 4) if np.isfinite(r.modal_gap_share) else np.nan,
        "J_star": round(r.j_star, 4), "J_threshold": round(r.j_threshold, 4),
        "D_VI": round(r.d_vi, 4) if np.isfinite(r.d_vi) else np.nan,
        "p_raw": round(r.p_raw, 5) if np.isfinite(r.p_raw) else np.nan,
        "p_holm": round(r.p_holm, 5) if np.isfinite(r.p_holm) else np.nan,
        "block_length": r.block_length, "n_degenerate": r.n_degenerate,
        "turnover_annual_DIAGNOSTIC": round(r.turnover_annual, 4) if np.isfinite(r.turnover_annual) else np.nan,
        **{f"pass_{k}": v for k, v in r.passes.items()},
        "PASSES_ALL": r.passed,
    } for r in results])
    table.to_csv(os.path.join(outdir, "calibration_table.csv"), index=False)

    stop_reason = None
    if selected is None:
        failing = sorted({k for r in results for k, v in r.passes.items() if not v})
        stop_reason = (
            "No candidate satisfied every hard structural criterion. Per the "
            "frozen selection rule, the 'least bad' candidate is NOT selected and "
            "Phase 2 STOPS. The recorded conclusion is that the current trigger "
            "specification is not sufficiently informative on the development "
            "region. Criteria failed by at least one candidate: "
            + ", ".join(failing) + ".")

    manifest = {
        "specification": "PHASE 2 PRE-REGISTRATION rev.5 (FROZEN, countersigned)",
        "selected_gamma": selected,
        "phase2_stops": selected is None,
        "stop_reason": stop_reason,
        "failed_criteria_by_gamma": {
            str(r.gamma): sorted([k for k, v in r.passes.items() if not v])
            for r in results},
        "k_frozen": sp.k_frozen,
        "n_rebalances": int(len(sp.ar)),
        "n_eligible": int(sp.eligible.sum()),
        "config": json.loads(cfg2.to_json()),
        "politis_white_block_lengths": {str(r.gamma): r.block_length for r in results},
        "degenerate_bootstrap_replicates": {str(r.gamma): r.n_degenerate for r in results},
        "bootstrap_implementation": "in-repo circular block bootstrap (rac_hrp.phase2.stats)",
        "code_sha256": {},
    }
    here = os.path.dirname(os.path.abspath(__file__))
    for f in ["config.py", "stats.py", "calibration.py"]:
        p = os.path.join(here, f)
        if os.path.exists(p):
            manifest["code_sha256"][f] = hashlib.sha256(
                open(p, "rb").read()).hexdigest()
    with open(os.path.join(outdir, "calibration_manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, default=str)

    if verbose:
        if selected is not None:
            print(f"\n  => SELECTED gamma = {selected}")
            print("     Next: Null Gate v2 at this gamma. On failure, Phase 2 STOPS.")
        else:
            print("\n  => NO CANDIDATE PASSES. PHASE 2 STOPS.")
            print("     " + (stop_reason or ""))

    return {"table": table, "results": results, "selected": selected,
            "selected_gamma": selected, "stop_reason": stop_reason,
            "manifest": manifest, "structural": sp}
