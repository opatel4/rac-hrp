"""
Phase 2 -- STRUCTURAL CALIBRATION GATE  (DEVELOPMENT REGION ONLY).

Executes steps 1-3 of the procedure frozen in the frozen pre-registration
    "PHASE 2 - PRE-REGISTRATION & CALIBRATION GATE (rev.5)"

    Step 1  structural diagnostics only, for every gamma candidate
    Step 2  apply the deterministic selection rule automatically, in code
    Step 3  write the selected gamma and full diagnostics to a hashed record

Steps 4-5 are NOT run here and must not be run until this gate selects:
    Step 4  Null Gate v2 at the selected gamma. The existing verdict applies
            only to gamma = 1.0 and is NOT inherited.
    Step 5  only on a pass, generate performance output.

PERFORMANCE IS NOT COMPUTED. This script never calls the backtest engine's
return path and never touches the risk-free series. Selection cannot be
influenced by a performance number because no performance number exists here.

TWO STRUCTURAL GUARDS
  * the test region is unreachable -- an evaluation position on or after
    TEST_START raises PermissionError;
  * the D4 covariance-window rule is applied BEFORE folds are built. Skipping it
    silently shifts every fold by a year (the Phase 1 bug) and would make the
    calibration incomparable to Phase 0.5 and Phase 1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import (Config, TEST_START, select_cov_window,   # noqa: E402
                            SAMPLE_START, DEV_END)
from rac_hrp.data import panel                                       # noqa: E402
from rac_hrp.data.universe import UniverseBuilder, realized_n_report  # noqa: E402
from rac_hrp.backtest.folds import FoldGenerator                     # noqa: E402
from rac_hrp.phase2.config import Phase2Config                       # noqa: E402
from rac_hrp.phase2.calibration import run_calibration               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Phase 2 structural calibration gate (development region only)")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--outdir", default="outputs/phase2")
    ap.add_argument("--quick", action="store_true",
                    help="reduced Monte Carlo/bootstrap counts; SMOKE TEST ONLY, "
                         "results are NOT the frozen specification and must not "
                         "be reported")
    a = ap.parse_args()
    # A --quick run must be structurally distinguishable from a frozen run
    # AFTER the fact, not just by a warning that scrolled past.
    if a.quick and not a.outdir.rstrip('/').endswith('_QUICK'):
        a.outdir = a.outdir.rstrip('/') + '_QUICK'
    os.makedirs(a.outdir, exist_ok=True)

    print("=" * 78)
    print("  PHASE 2 -- STRUCTURAL CALIBRATION GATE   (DEVELOPMENT REGION ONLY)")
    print("=" * 78)
    print("  Frozen specification: PHASE 2 PRE-REGISTRATION rev.5 (frozen)")
    print("  Performance is NOT computed at this stage.")
    print("  Test-region evaluation is structurally blocked.")
    print()

    # ---- panel ---------------------------------------------------------
    P = panel.build_panels(a.raw)
    print(f"  panel            : {P.returns.shape[0]:,} days x "
          f"{P.returns.shape[1]:,} permnos")

    # ---- D4 rule BEFORE folds (Phase 1 lesson) --------------------------
    cfg0 = Config(n_assets=a.n)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    med_n = float(realized_n_report(
        UniverseBuilder(P, cfg0).snapshots(probe)).n_selected.median())
    W = select_cov_window(med_n)
    cfg = Config(n_assets=a.n, cov_window=W)
    print(f"  D4 window        : W = {W}  (median realized N = {med_n:.0f})")

    # ---- development folds ---------------------------------------------
    folds = FoldGenerator(P.returns.index, cfg).dev_folds()
    eval_pos = np.concatenate([f.test_pos for f in folds])
    fold_bounds = [(int(f.test_pos[0]), int(f.test_pos[-1])) for f in folds]

    dates = P.returns.index[eval_pos]
    if (dates >= pd.Timestamp(TEST_START)).any():
        raise PermissionError(
            f"Phase 2 attempted to evaluate on/after the test start {TEST_START}. "
            "Test-region work is not authorized.")
    print(f"  dev span         : {dates[0].date()} -> {dates[-1].date()} "
          f"({len(eval_pos):,} days, {len(folds)} folds)")
    print(f"  universe         : N = {cfg.n_assets}")
    print()

    # ---- frozen Phase 2 parameters -------------------------------------
    p2 = Phase2Config()
    if a.quick:
        import dataclasses
        p2 = dataclasses.replace(p2, placebo_draws=3_000,
                                 bootstrap_replicates=800)
        print("  *** --quick: reduced Monte Carlo counts. SMOKE TEST ONLY.")
        print("  *** These are NOT the frozen counts and MUST NOT be reported.")
        print()
    print(f"  gamma candidates : {list(p2.gamma_candidates)}")
    print(f"  placebo          : seed {p2.placebo_seed}, B = {p2.placebo_draws:,}, "
          f"{p2.placebo_percentile:.0f}th pct, q in "
          f"{p2.separation_periods[0]}..{p2.separation_periods[-1]}")
    print(f"  bootstrap        : {p2.bootstrap_kind}, B = "
          f"{p2.bootstrap_replicates:,}, Holm alpha = {p2.holm_alpha}")
    print(f"  sigma            : rolling({p2.ar_sigma_rebalances}, "
          f"min_periods=6).std(ddof={p2.ar_sigma_ddof}).shift(1)")
    print()
    print("-" * 78)

    out = run_calibration(P, cfg, eval_pos, fold_bounds=fold_bounds,
                          cfg2=p2, outdir=a.outdir, verbose=True)

    # ---- report ---------------------------------------------------------
    print()
    print("-" * 78)
    print("  CALIBRATION TABLE   (structural evidence only)")
    print("-" * 78)
    t = out["table"]
    show = ["gamma", "n_events", "firing_rate", "min_events_per_fold",
            "cv_gap", "modal_gap_share", "J_star", "J_threshold",
            "D_VI", "p_holm", "turnover_annual_DIAGNOSTIC", "PASSES_ALL"]
    show = [c for c in show if c in t.columns]
    print(t[show].to_string(index=False))
    print()
    print("  turnover_annual_DIAGNOSTIC is REPORTED ONLY -- it cannot pass or")
    print("  fail a candidate (the 1.5x multiplier was asserted, not derived).")
    print()

    m = out["manifest"]
    sel = out["selected"]
    print("-" * 78)
    if sel is not None:
        print(f"  => SELECTED gamma = {sel}")
        print()
        print("  NEXT (do not skip, do not reorder):")
        print("    4. Run Null Gate v2 at this gamma. The existing v2 verdict")
        print("       applies only to gamma = 1.0 and is NOT inherited.")
        print("    5. ONLY on a pass, generate performance output.")
        print("    If the null gate fails, PHASE 2 STOPS. No fall-through.")
    else:
        print("  => NO CANDIDATE PASSES. PHASE 2 STOPS.")
        print()
        for g, fails in m.get("failed_criteria_by_gamma", {}).items():
            print(f"     gamma={g}: failed {', '.join(fails)}")
        print()
        print("  The 'least bad' candidate is NOT selected. Per the frozen rule,")
        print("  the recorded conclusion is that the current trigger specification")
        print("  is not sufficiently informative on the development region.")
        print("  That is a reportable finding, not a failure of the pipeline.")
    print()
    print(f"  frozen record : {a.outdir}/calibration_manifest.json")
    print(f"  table         : {a.outdir}/calibration_table.csv")
    print(f"  block lengths : {m.get('politis_white_block_lengths')}")
    print(f"  degenerate    : {m.get('degenerate_bootstrap_replicates')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
