"""
Phase 1 -- static baseline rebuild (DEVELOPMENT REGION ONLY).

AUTHORIZATION BOUNDARY
----------------------
Phase 1 development-region implementation is authorized. Test-region strategy
comparison, model selection, threshold adjustment, and performance inspection are
NOT authorized until the test-region endpoint is formally resolved and recorded
(the CRSP vintage ends 2024-12-31; the pre-registered endpoint is 2025-11-28).

This script therefore refuses to touch the test region. The refusal is structural,
not advisory: it asserts on the fold boundary before doing any work.

WHAT THIS BUILDS
----------------
  1. Static baselines (EW, ERC, HRP_static, min-variance) on the development
     region only.
  2. An ESTIMATOR COMPARISON across {sample, lw_linear, nls}. This is a
     DIAGNOSTIC, not a selection: D10 gives development folds no model-selection
     role. The estimator used downstream is whatever the frozen config says; this
     table exists to document sensitivity, not to pick a winner.
  3. An ACCOUNTING RECONCILIATION -- independently recomputes the portfolio
     return series from weights and asset returns and checks it against the
     engine's own output. If the engine's accounting is wrong, every number in
     the paper is wrong, and no performance table would reveal it.
  4. Turnover diagnostics per strategy.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import (Config, TEST_START, select_cov_window,
                            SAMPLE_START, DEV_END)
from rac_hrp.data import panel
from rac_hrp.data.universe import UniverseBuilder, realized_n_report
from rac_hrp.backtest.folds import FoldGenerator
from rac_hrp.backtest.engine import WalkForward, Strategy
from rac_hrp.backtest import metrics as M


BASELINES = [
    Strategy("EW", allocator="ew"),
    Strategy("ERC", allocator="erc"),
    Strategy("HRP_static", allocator="hrp", recluster="never"),
    Strategy("MHRP_EV", allocator="hrp_equalvol", recluster="never"),
    Strategy("MinVar", allocator="minvar"),
]


def _dev_eval_positions(P, cfg) -> np.ndarray:
    """Concatenated development-fold evaluation positions. Never test region."""
    fg = FoldGenerator(P.returns.index, cfg)
    folds = fg.dev_folds()
    pos = np.concatenate([f.test_pos for f in folds])

    # STRUCTURAL GUARD: nothing here may reach the pre-registered test region.
    test_start = pd.Timestamp(TEST_START)
    dates = P.returns.index[pos]
    if (dates >= test_start).any():
        raise PermissionError(
            f"Phase 1 attempted to evaluate on/after the test start {TEST_START}. "
            "Test-region work is not authorized until the endpoint is resolved.")
    return pos


def accounting_reconciliation(P, res, name: str) -> dict:
    """Independently recompute the return series from weights; compare to engine.

    The engine grows weights intra-rebalance and books turnover costs. Here we
    recompute the gross portfolio return from the stored weight path and the
    realised asset returns, without reusing the engine's arithmetic, and compare.
    A mismatch means the accounting is broken.
    """
    W = getattr(res, "weights", None)
    if not W:
        return {"strategy": name, "n_days_checked": 0,
                "median_abs_diff": np.nan, "max_abs_diff": np.nan,
                "status": "no weight path stored"}

    rets = P.returns
    recomputed = []
    for d, w in W.items():          # weights is Dict[Timestamp, Series]
        if d not in rets.index:
            continue
        row = rets.loc[d].reindex(w.index)
        r = float(np.nansum(w.values * np.nan_to_num(row.values, nan=0.0)))
        recomputed.append((d, r))
    if not recomputed:
        return {"strategy": name, "status": "no overlapping dates", "max_abs_diff": np.nan}

    rec = pd.Series(dict(recomputed)).sort_index()
    # Compare against GROSS returns: net books turnover cost on rebalance days,
    # so net would differ by construction and the check would be meaningless.
    eng = res.gross_returns.reindex(rec.index)
    diff = (rec - eng).abs()
    med = float(np.nanmedian(diff))
    mx = float(np.nanmax(diff))
    ok = med < 1e-10
    return {"strategy": name,
            "n_days_checked": int(len(rec)),
            "median_abs_diff": round(med, 12),
            "max_abs_diff": round(mx, 10),
            "status": "OK" if ok else "REVIEW -- gross return does not reconcile"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 1 static baselines (dev region)")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--outdir", default="outputs/phase1")
    ap.add_argument("--estimators", default="sample,lw_linear,nls",
                    help="diagnostic sensitivity sweep; selects nothing (D10)")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    print("=" * 78)
    print("  PHASE 1 -- STATIC BASELINE REBUILD   (DEVELOPMENT REGION ONLY)")
    print("=" * 78)
    print("  Test-region evaluation is NOT authorized and is structurally blocked.")
    print()

    P = panel.build_panels(a.raw)

    # ---- D4: deterministic covariance window (PRE-REGISTERED RULE) -------
    # Phase 0.5 applies this BEFORE building folds; the fold geometry depends on
    # min_train = cov_window + min_history_days. Skipping it silently shifts every
    # fold by a year and makes Phase 1 baselines incomparable to Phase 0.5.
    cfg0 = Config(n_assets=a.n)
    ub = UniverseBuilder(P, cfg0)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    med_n = float(realized_n_report(ub.snapshots(probe)).n_selected.median())
    W = select_cov_window(med_n)
    cfg = Config(n_assets=a.n, cov_window=W, store_weights=True)
    print(f"  D4 covariance window: W = {W}  (median realized N = {med_n:.0f})")


    eval_pos = _dev_eval_positions(P, cfg)
    dates = P.returns.index[eval_pos]
    print(f"  dev evaluation span : {dates[0].date()} -> {dates[-1].date()} "
          f"({len(eval_pos):,} days)")
    print(f"  universe            : N = {cfg.n_assets}")
    print()

    # ---- 1. baselines under the frozen estimator ------------------------
    print("-" * 78)
    print(f"  BASELINES  (frozen estimator = {cfg.cov_estimator})")
    print("-" * 78)
    wf = WalkForward(P, cfg)
    res = wf.run(BASELINES, eval_pos)

    perf = M.summary_table(res, P.rf)
    print(perf.round(3).to_string())
    perf.to_csv(os.path.join(a.outdir, "phase1_baselines.csv"))

    # ---- 2. estimator sensitivity (DIAGNOSTIC ONLY) ---------------------
    print()
    print("-" * 78)
    print("  ESTIMATOR SENSITIVITY  (diagnostic -- D10: selects NOTHING)")
    print("-" * 78)
    sweep = []
    for est in [e.strip() for e in a.estimators.split(",") if e.strip()]:
        c2 = Config(n_assets=a.n, cov_window=W, cov_estimator=est)
        r2 = WalkForward(P, c2).run(BASELINES, eval_pos)
        for name, rr in r2.items():
            sweep.append({"estimator": est, "strategy": name,
                          "sharpe": M.sharpe(rr.returns, P.rf)})
    sw = pd.DataFrame(sweep).pivot(index="strategy", columns="estimator", values="sharpe")
    print(sw.round(3).to_string())
    sw.to_csv(os.path.join(a.outdir, "phase1_estimator_sensitivity.csv"))
    print()
    print("  These numbers document sensitivity. They do not choose the estimator;")
    print("  the estimator is fixed by the frozen pre-analysis plan.")

    # ---- 3. accounting reconciliation -----------------------------------
    print()
    print("-" * 78)
    print("  ACCOUNTING RECONCILIATION  [correctness gate]")
    print("-" * 78)
    acc = pd.DataFrame([accounting_reconciliation(P, r, n) for n, r in res.items()])
    print(acc.to_string(index=False))
    acc.to_csv(os.path.join(a.outdir, "phase1_accounting.csv"), index=False)

    st = acc["status"].astype(str)
    bad = acc[st.str.startswith("REVIEW")]
    unver = acc[~st.str.startswith("REVIEW") & (st != "OK")]
    print()
    if len(bad):
        print("  => ACCOUNTING REVIEW REQUIRED. Do not report performance until resolved.")
        return 1
    if len(unver):
        # A gate that cannot run must not report success. This is the vacuous-pass
        # failure mode the null gate was built to avoid; the same rule applies here.
        print("  => UNVERIFIED: no weight path was recorded, so the accounting check")
        print("     did not actually run. This is NOT a pass. Enable store_weights.")
        return 1
    print("  => accounting reconciles (recomputed gross == engine gross).")
    print()
    print(f"  artifacts: {a.outdir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
