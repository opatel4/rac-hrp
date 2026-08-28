"""
Phase 2G -- ROBUSTNESS DIAGNOSTICS.

Frozen specification: RAC_HRP_Phase2G_PreSpec_rev1.md
SHA-256: c431974eb7bd611b27533d7d52abbe1ac00f385d2f2eb4573b3563d279794fd2

Three non-gating diagnostics:

  2G-K        sensitivity of the gate result to the retained-component count k
  2G-RANK     Spearman correlation between VI and continuous trigger strength
  2G-HORIZON  D_VI across horizons h in {1..8}

NON-GATING (spec section 0.1). Nothing here can render any gamma admissible or
reopen Phase 2A.

THE BINDING CLAUSE (spec section 0.3). The frozen specification is NOT revised in
light of any result here. If 2G-K is more favourable at some k != 15, if 2G-RANK
resolves an effect the gate could not, or if 2G-HORIZON peaks at some h != 5, none
of those becomes the reported analysis. The confirmatory results remain k = 15,
difference-of-medians, h = 1 for the gate and h = 5 for the horizon-matched
diagnostic. These describe sensitivity; they do not re-select.

ABORT CONDITIONS. Each diagnostic contains a cell that must reproduce a frozen
result exactly. 2G-K at k = 15 must reproduce the gate's event counts and D_VI;
2G-HORIZON at h = 1 must reproduce the gate's D_VI and at h = 5 the horizon-matched
values. A mismatch means the implementation differs from the frozen one and the run
aborts before anything is reported.

PERFORMANCE IS NOT COMPUTED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import rankdata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import (Config, TEST_START, select_cov_window,       # noqa: E402
                            SAMPLE_START, DEV_END)
from rac_hrp.core.clustering import (build_tree, cluster_labels,          # noqa: E402
                                     n_clusters_from_rule,
                                     variation_of_information)
from rac_hrp.core.covariance import estimate                              # noqa: E402
from rac_hrp.core.pca_mp import spectrum, absorption_ratio                # noqa: E402
from rac_hrp.data import panel                                            # noqa: E402
from rac_hrp.data.universe import UniverseBuilder, realized_n_report       # noqa: E402
from rac_hrp.backtest.folds import FoldGenerator                          # noqa: E402
from rac_hrp.phase2.calibration import structural_pass                    # noqa: E402
from rac_hrp.phase2.stats import (circular_block_bootstrap_p, d_vi,       # noqa: E402
                                  holm_adjust, politis_white_block_length)
from rac_hrp.phase2.horizon import labelled_pass, vi_at_lag               # noqa: E402
from rac_hrp.phase2 import horizon as HZ                                  # noqa: E402

SPEC_FILE = "RAC_HRP_Phase2G_PreSpec_rev1.md"
SPEC_SHA = "c431974eb7bd611b27533d7d52abbe1ac00f385d2f2eb4573b3563d279794fd2"

SEED_K = 131276444
SEED_RANK = 115262612
SEED_HORIZON = 560119915

GAMMAS: Tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
K_GRID: Tuple[int, ...] = (10, 15, 20, 25)
H_GRID: Tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8)
BOOT = 10_000
ALPHA = 0.05

FROZEN_EVENTS = {0.5: 149, 1.0: 111, 1.5: 81, 2.0: 58}
FROZEN_DVI = {0.5: 0.033, 1.0: 0.022, 1.5: 0.080, 2.0: 0.096}
FROZEN_DVI_H5 = {0.5: 0.0662, 1.0: 0.0600, 1.5: 0.0814, 2.0: 0.1038}
TOL = 5e-3


class AbortRun(RuntimeError):
    """A frozen reproduction check failed."""


def sha256(path: str) -> Optional[str]:
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except Exception:
        return None


def fired_masks(sp) -> Dict[float, np.ndarray]:
    elig = np.where(sp.eligible)[0]
    out = {}
    for g in GAMMAS:
        with np.errstate(invalid="ignore"):
            out[g] = np.abs(sp.d_ar[elig]) > g * sp.sigma[elig]
    return out


# ==========================================================================
# 2G-K -- structural pass at an arbitrary fixed k
# ==========================================================================
def structural_pass_fixed_k(P, cfg, eval_pos, k_fixed: int):
    """The frozen loop with k supplied rather than derived.

    Mirrors calibration.structural_pass call for call. The single difference is
    that k is the supplied value instead of the Marchenko-Pastur count at the
    first eligible rebalance. The turnover branch is omitted; VI does not depend
    on it and this diagnostic never reads it.
    """
    ub = UniverseBuilder(P, cfg)
    cal = P.returns.index
    rebal = eval_pos[::cfg.rebalance_freq]

    dates, ars, vis = [], [], []
    prev_labels = prev_permnos = None

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
        ar = absorption_ratio(spec, k=k_fixed)
        nc = n_clusters_from_rule(spec, cfg.n_clusters_rule,
                                  cfg.n_clusters_min, cfg.n_clusters_max)
        Z, order, _ = build_tree(cov, spec, space=cfg.cluster_space,
                                 k=k_fixed, canonical_order=True)
        labels = cluster_labels(Z, nc)

        vi_t = np.nan
        if prev_labels is not None:
            common = np.intersect1d(permnos, prev_permnos)
            if len(common) >= 10:
                cur = {p: l for p, l in zip(permnos, labels)}
                pre = {p: l for p, l in zip(prev_permnos, prev_labels)}
                vi_t = variation_of_information(
                    np.array([pre[p] for p in common]),
                    np.array([cur[p] for p in common]))

        dates.append(cal[t]); ars.append(ar); vis.append(vi_t)
        prev_labels, prev_permnos = labels, permnos

    idx = pd.DatetimeIndex(dates)
    s = pd.Series(ars, index=idx)
    s_sm = s.rolling(5, min_periods=1).mean()
    d = s_sm.diff()
    sig = d.rolling(12, min_periods=6).std(ddof=1).shift(1)

    return {"dates": idx, "ar": s.values, "d_ar": d.values,
            "sigma": sig.values, "eligible": sig.notna().values,
            "vi": np.array(vis)}


def run_k_sweep(P, cfg, eval_pos, fold_bounds, verbose=True) -> List[dict]:
    rows = []
    for ki, k in enumerate(K_GRID):
        if verbose:
            print(f"    k = {k} ...", flush=True)
        sp = structural_pass_fixed_k(P, cfg, eval_pos, k)
        elig = np.where(sp["eligible"])[0]
        E = len(elig)
        vi_e = sp["vi"][elig]
        raw = {}
        cells = []
        for gi, g in enumerate(GAMMAS):
            with np.errstate(invalid="ignore"):
                fired = np.abs(sp["d_ar"][elig]) > g * sp["sigma"][elig]
            n = int(fired.sum())
            dv = d_vi(vi_e, fired)
            b = circular_block_bootstrap_p(vi_e, fired,
                                           seed=SEED_K + 1000 * ki + gi,
                                           replicates=BOOT)
            raw[g] = b.p_value
            cells.append({"gamma": g, "n_events": n, "d_vi": dv,
                          "p_raw": b.p_value, "block_length": int(b.block_length)})
        adj = holm_adjust(raw)
        for c in cells:
            c["p_holm"] = adj[c["gamma"]]
        rows.append({"k": k, "E": E,
                     "ar_min": float(np.nanmin(sp["ar"])),
                     "ar_max": float(np.nanmax(sp["ar"])),
                     "cells": cells})

        if k == 15:
            for c in cells:
                g = c["gamma"]
                if c["n_events"] != FROZEN_EVENTS[g]:
                    raise AbortRun(
                        f"2G-K at k=15, gamma={g}: {c['n_events']} events, "
                        f"frozen gate reports {FROZEN_EVENTS[g]}")
                if abs(c["d_vi"] - FROZEN_DVI[g]) > TOL:
                    raise AbortRun(
                        f"2G-K at k=15, gamma={g}: D_VI {c['d_vi']:+.4f}, "
                        f"frozen gate reports {FROZEN_DVI[g]:+.4f}")
            if verbose:
                print("      k = 15 reproduces the frozen gate", flush=True)
    return rows


# ==========================================================================
# 2G-RANK -- Spearman on continuous trigger strength
# ==========================================================================
def spearman(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 4:
        return float("nan")
    return float(np.corrcoef(rankdata(x[ok]), rankdata(y[ok]))[0, 1])


def run_rank(sp, verbose=True) -> dict:
    elig = np.where(sp.eligible)[0]
    vi = np.asarray(sp.vi, dtype=float)[elig]
    with np.errstate(invalid="ignore"):
        z = np.abs(sp.d_ar[elig]) / sp.sigma[elig]

    rho = spearman(z, vi)
    L = int(politis_white_block_length(vi[np.isfinite(vi)]))
    n = len(vi)
    n_blocks = int(np.ceil(n / L))
    rng = np.random.default_rng(SEED_RANK)
    exceed = kept = 0
    for _ in range(BOOT):
        starts = rng.integers(0, n, size=n_blocks)
        idx = ((starts[:, None] + np.arange(L)[None, :]) % n).ravel()[:n]
        r_b = spearman(z[idx], vi[idx])
        if not np.isfinite(r_b):
            continue
        kept += 1
        if (r_b - rho) >= rho:
            exceed += 1
    p = (1.0 + exceed) / (kept + 1.0) if kept else float("nan")
    if verbose:
        print(f"    rho = {rho:+.4f},  one-sided p = {p:.4f},  block = {L}", flush=True)
    return {"rho": rho, "p_one_sided": float(p), "block_length": L,
            "n": int(n), "kept_replicates": kept,
            "note": ("single test, no multiplicity adjustment; NOT comparable to the "
                     "gate's Holm-adjusted values and does not replace the frozen "
                     "criterion (spec 0.3)")}


# ==========================================================================
# 2G-HORIZON -- D_VI across h
# ==========================================================================
def run_horizon_sweep(lp, sp, verbose=True) -> List[dict]:
    elig = np.where(sp.eligible)[0]
    masks = fired_masks(sp)
    rows = []
    for h in H_GRID:
        vi_h = vi_at_lag(lp, h)[elig]
        raw, cells = {}, []
        for gi, g in enumerate(GAMMAS):
            dv = d_vi(vi_h, masks[g])
            b = circular_block_bootstrap_p(vi_h, masks[g],
                                           seed=SEED_HORIZON + 1000 * h + gi,
                                           replicates=BOOT)
            raw[g] = b.p_value
            cells.append({"gamma": g, "d_vi": dv, "p_raw": b.p_value,
                          "block_length": int(b.block_length)})
        adj = holm_adjust(raw)
        for c in cells:
            c["p_holm"] = adj[c["gamma"]]
        rows.append({"h": h, "cells": cells})
        if verbose:
            print("    h=%d  " % h + "  ".join(
                "g%.1f:%+.4f(p%.3f)" % (c["gamma"], c["d_vi"], c["p_holm"])
                for c in cells), flush=True)

        if h == 1:
            for c in cells:
                if abs(c["d_vi"] - FROZEN_DVI[c["gamma"]]) > TOL:
                    raise AbortRun(
                        f"2G-HORIZON at h=1, gamma={c['gamma']}: D_VI "
                        f"{c['d_vi']:+.4f}, frozen gate reports "
                        f"{FROZEN_DVI[c['gamma']]:+.4f}")
        if h == 5:
            for c in cells:
                if abs(c["d_vi"] - FROZEN_DVI_H5[c["gamma"]]) > TOL:
                    raise AbortRun(
                        f"2G-HORIZON at h=5, gamma={c['gamma']}: D_VI "
                        f"{c['d_vi']:+.4f}, 2E-HORIZON reports "
                        f"{FROZEN_DVI_H5[c['gamma']]:+.4f}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 2G robustness diagnostics")
    ap.add_argument("--raw", default=os.path.expanduser("~/rac_hrp_data/raw"))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--outdir", default="outputs/phase2g")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 78)
    print("  PHASE 2G -- ROBUSTNESS DIAGNOSTICS")
    print("=" * 78)
    got = sha256(os.path.join(root, SPEC_FILE))
    print(f"  spec SHA-256         : {got}")
    if got != SPEC_SHA:
        print(f"  *** SPEC HASH MISMATCH -- expected {SPEC_SHA}")
        return 2
    print("  spec hash            : verified")
    print("  NON-GATING. Phase 2A is CLOSED. The frozen specification is NOT")
    print("  revised in light of any result here (spec section 0.3).")
    print()

    P = panel.build_panels(a.raw)
    cfg0 = Config(n_assets=a.n)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    med_n = float(realized_n_report(
        UniverseBuilder(P, cfg0).snapshots(probe)).n_selected.median())
    W = select_cov_window(med_n)
    cfg = Config(n_assets=a.n, cov_window=W)
    folds = FoldGenerator(P.returns.index, cfg).dev_folds()
    eval_pos = np.concatenate([f.test_pos for f in folds])
    fold_bounds = [(int(f.test_pos[0]), int(f.test_pos[-1])) for f in folds]
    if (P.returns.index[eval_pos] >= pd.Timestamp(TEST_START)).any():
        raise PermissionError("Phase 2G reached the test region")
    print(f"  D4 window            : W = {W}")
    print()

    t0 = time.time()
    try:
        print("  [2G-K] sensitivity to the retained-component count")
        k_rows = run_k_sweep(P, cfg, eval_pos, fold_bounds)
        print()

        print("  [2G-RANK] Spearman on continuous trigger strength")
        sp = structural_pass(P, cfg, eval_pos, fold_bounds, verbose=False)
        rank = run_rank(sp)
        print()

        print("  [2G-HORIZON] D_VI across horizons")
        lp = labelled_pass(P, cfg, eval_pos, verbose=False)
        HZ.assert_equivalent_to_gate(lp, sp)
        h_rows = run_horizon_sweep(lp, sp)
    except AbortRun as e:
        print(f"\n  *** ABORTED -- {e}")
        return 3

    print()
    print("-" * 78)
    print("  2G-K")
    print("  k    E    AR range        " + "  ".join(f"g{g}" for g in GAMMAS))
    for r in k_rows:
        ev = " ".join("%3d" % c["n_events"] for c in r["cells"])
        dv = " ".join("%+.3f" % c["d_vi"] for c in r["cells"])
        ph = " ".join("%.3f" % c["p_holm"] for c in r["cells"])
        mark = "  <- frozen" if r["k"] == 15 else ""
        print(f"  {r['k']:<4} {r['E']:<4} [{r['ar_min']:.3f},{r['ar_max']:.3f}]"
              f"   n={ev}  D={dv}  p={ph}{mark}")
    print()
    print("  2G-RANK")
    print(f"  rho = {rank['rho']:+.4f}   one-sided p = {rank['p_one_sided']:.4f}"
          f"   block = {rank['block_length']}   n = {rank['n']}")
    print("  Single test; not comparable to Holm-adjusted gate values.")
    print()
    print("  2G-HORIZON")
    for r in h_rows:
        mark = "  <- frozen gate" if r["h"] == 1 else (
            "  <- 2E-HORIZON claim" if r["h"] == 5 else "")
        print("  h=%d  " % r["h"] + "  ".join(
            "%+.4f(%.3f)" % (c["d_vi"], c["p_holm"]) for c in r["cells"]) + mark)
    print("-" * 78)
    print("  h = 5 remains the inferential claim. The sweep is robustness and does")
    print("  not re-select (spec section 0.3).")
    print(f"  elapsed              : {(time.time()-t0)/60:.1f} min")

    record = {
        "diagnostic": "Phase 2G robustness diagnostics",
        "specification": f"{SPEC_FILE} (frozen, hashed)",
        "spec_sha256": SPEC_SHA, "gating": False,
        "phase2a_verdict_unchanged": "NO ADMISSIBLE GAMMA",
        "frozen_analysis_not_reselected": True,
        "seeds": {"k": SEED_K, "rank": SEED_RANK, "horizon": SEED_HORIZON},
        "bootstrap_replicates": BOOT, "alpha": ALPHA, "W": int(W),
        "k_sweep": k_rows, "rank": rank, "horizon_sweep": h_rows,
        "elapsed_min": round((time.time() - t0) / 60.0, 2),
        "environment": {"numpy": np.__version__, "pandas": pd.__version__,
                        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS", "unset")},
        "code_sha256": {
            "run_phase2g.py": sha256(os.path.abspath(__file__)),
            "calibration.py": sha256(os.path.join(root, "rac_hrp/phase2/calibration.py")),
            "horizon.py": sha256(os.path.join(root, "rac_hrp/phase2/horizon.py")),
            "stats.py": sha256(os.path.join(root, "rac_hrp/phase2/stats.py")),
        },
    }
    out = os.path.join(a.outdir, "phase2g_result.json")
    with open(out, "w") as f:
        json.dump(record, f, indent=2)
    print(f"  record written       : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
