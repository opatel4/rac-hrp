"""
Phase 2E -- 2E-HORIZON: horizon-matched cluster informativeness.
DEVELOPMENT REGION ONLY.

Frozen specification: RAC_HRP_Phase2E_PreSpec_rev5.md
SHA-256: 6153831fa0da7a52673a48bd24cc208fabd857715d7e3a2e5c61c0162ef88b46

NON-GATING. Nothing here can render any gamma admissible, reopen the Phase 2A
calibration gate, or alter any frozen value. The Phase 2A verdict -- NO ADMISSIBLE
GAMMA -- stands regardless of what this returns.

WHAT IT DOES
    The frozen gate measures VI between clusterings at CONSECUTIVE rebalances.
    The trigger statistic is algebraically a FIVE-rebalance change in the
    absorption ratio. This recomputes D_VI with VI taken between the clustering
    at t and at t-5. One thing changes: the horizon.

PERFORMANCE IS NOT COMPUTED. Like the gate, this never calls the backtest
engine's return path and never touches the risk-free series.

SETUP IS MIRRORED, NOT RECONSTRUCTED
    The panel, D4 window rule, folds, eval_pos and fold_bounds are built by the
    identical sequence used in scripts/run_phase2.py. Any divergence would make
    the diagnostic incomparable to the gate, and the equivalence check inside
    rac_hrp.phase2.horizon would fire.

THREE ABORT CONDITIONS
    * the one-step VI series recomputed from retained labels must reproduce the
      frozen gate's VI series bitwise;
    * the eligible set must be exactly 233;
    * event counts must be exactly 149 / 111 / 81 / 58.
    Any failure aborts before a statistic is computed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import (Config, TEST_START, select_cov_window,   # noqa: E402
                            SAMPLE_START, DEV_END)
from rac_hrp.data import panel                                       # noqa: E402
from rac_hrp.data.universe import UniverseBuilder, realized_n_report  # noqa: E402
from rac_hrp.backtest.folds import FoldGenerator                     # noqa: E402
from rac_hrp.phase2 import horizon as H                              # noqa: E402

# 2E-HORIZON was specified and run under rev.5. rev.6 amended only the
# 2E-POWER base path and does not touch this diagnostic; the governing
# revision for this result is therefore rev.5, and the hash below is its.
SPEC_FILE = "RAC_HRP_Phase2E_PreSpec_rev5.md"
SPEC_SHA = "6153831fa0da7a52673a48bd24cc208fabd857715d7e3a2e5c61c0162ef88b46"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="2E-HORIZON (development region only, non-gating)")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--outdir", default="outputs/phase2e_horizon")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    print("=" * 78)
    print("  2E-HORIZON -- horizon-matched cluster informativeness")
    print("=" * 78)
    print(f"  Frozen specification : {SPEC_FILE}")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec_path = os.path.join(root, SPEC_FILE)
    if os.path.exists(spec_path):
        got = _sha256(spec_path)
        print(f"  spec SHA-256         : {got}")
        if got != SPEC_SHA:
            print(f"  *** SPEC HASH MISMATCH -- expected {SPEC_SHA}")
            print("  *** The specification on disk is not the frozen one. Aborting.")
            return 2
        print("  spec hash            : verified")
    else:
        print(f"  *** {SPEC_FILE} not found; cannot verify the freeze. Aborting.")
        return 2

    print("  NON-GATING. The Phase 2A verdict stands regardless of this result.")
    print("  Performance is NOT computed. Test region is structurally blocked.")
    print()

    # ---- panel (mirrors run_phase2.py) ---------------------------------
    P = panel.build_panels(a.raw)
    print(f"  panel                : {P.returns.shape[0]:,} days x "
          f"{P.returns.shape[1]:,} permnos")

    # ---- D4 rule BEFORE folds ------------------------------------------
    cfg0 = Config(n_assets=a.n)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    med_n = float(realized_n_report(
        UniverseBuilder(P, cfg0).snapshots(probe)).n_selected.median())
    W = select_cov_window(med_n)
    cfg = Config(n_assets=a.n, cov_window=W)
    print(f"  D4 window            : W = {W}  (median realized N = {med_n:.0f})")

    # ---- development folds ---------------------------------------------
    folds = FoldGenerator(P.returns.index, cfg).dev_folds()
    eval_pos = np.concatenate([f.test_pos for f in folds])
    fold_bounds = [(int(f.test_pos[0]), int(f.test_pos[-1])) for f in folds]

    dates = P.returns.index[eval_pos]
    if (dates >= pd.Timestamp(TEST_START)).any():
        raise PermissionError(
            f"2E-HORIZON attempted to evaluate on/after the test start {TEST_START}. "
            "Test-region work is not authorized.")
    print(f"  dev span             : {dates[0].date()} -> {dates[-1].date()} "
          f"({len(eval_pos):,} days, {len(folds)} folds)")
    print(f"  horizon              : {H.HORIZON} rebalances")
    print(f"  bootstrap            : circular block, B = {H.BOOTSTRAP_REPLICATES:,}, "
          f"Holm alpha = {H.ALPHA}")
    print(f"  base seed            : {H.BOOTSTRAP_SEED_BASE}")
    print()
    print("-" * 78)

    try:
        res = H.run_horizon(P, cfg, eval_pos, fold_bounds=fold_bounds, verbose=True)
    except H.GateDivergence as e:
        print()
        print("  *** ABORTED -- GATE DIVERGENCE")
        print(f"  *** {e}")
        print("  *** The duplicated loop does not reproduce the frozen gate.")
        print("  *** No statistic was computed. Investigate before re-running.")
        return 3

    print()
    print("-" * 78)
    print(H.format_report(res))
    print("-" * 78)

    # ---- hashed record --------------------------------------------------
    record = {
        "diagnostic": "2E-HORIZON",
        "specification": f"{SPEC_FILE} (frozen, hashed)",
        "spec_sha256": SPEC_SHA,
        "gating": False,
        "phase2a_verdict_unchanged": "NO ADMISSIBLE GAMMA",
        "horizon": res.horizon,
        "n_eligible": res.n_eligible,
        "bootstrap_seed_base": H.BOOTSTRAP_SEED_BASE,
        "bootstrap_replicates": H.BOOTSTRAP_REPLICATES,
        "alpha": H.ALPHA,
        "cov_window": int(W),
        "n_assets": int(cfg.n_assets),
        "dev_span": [str(dates[0].date()), str(dates[-1].date())],
        "outcome": res.outcome,
        "cells": [asdict(c) for c in res.cells],
        "code_sha256": {
            "horizon.py": _sha256(os.path.join(root, "rac_hrp/phase2/horizon.py")),
            "calibration.py": _sha256(os.path.join(root, "rac_hrp/phase2/calibration.py")),
            "stats.py": _sha256(os.path.join(root, "rac_hrp/phase2/stats.py")),
        },
    }
    out = os.path.join(a.outdir, "horizon_result.json")
    with open(out, "w") as f:
        json.dump(record, f, indent=2)
    print(f"  record written       : {out}")
    print()
    print("  REMINDER: this is a post-gate, non-gating diagnostic. It must be")
    print("  reported alongside 2E-POWER, and it confers no admissibility.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
