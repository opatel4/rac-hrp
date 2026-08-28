"""
Phase 2E -- 2E-POWER: planted-effect power curve.
DEVELOPMENT REGION ONLY.

Frozen specification: RAC_HRP_Phase2E_PreSpec_rev8.md
SHA-256: cfdd64cca9a23a1d873695b2de0576b442cf2b80e302602830a0d1502c403674

NON-GATING. Nothing here can render any gamma admissible, reopen the Phase 2A
calibration gate, or alter any frozen value. The Phase 2A verdict -- NO ADMISSIBLE
GAMMA -- stands regardless of what this returns.

WHAT IT DOES
    Measures the smallest true D_VI the frozen cluster-informativeness test could
    have detected at 80% power, on the dependence structure the gate actually
    faced. Answers whether the Phase 2A null reflects absence of an effect or a
    design that could not have seen one.

PERFORMANCE IS NOT COMPUTED. Like the gate, this never calls the backtest
engine's return path and never touches the risk-free series.

RUNTIME
    Timing probe measured 0.258 s per replication, extrapolating to 9.3 hours at
    the frozen 2,000 replications. That is under the 12-hour threshold in section
    2.8, so the replication count is NOT reduced and no amendment applies.

    Use --probe-only to re-measure without running. Use --resume to continue from
    a checkpoint; cells are deterministic in their seeds, so a resumed run
    produces identical numbers to an uninterrupted one.

SETUP IS MIRRORED, NOT RECONSTRUCTED
    Panel, D4 window rule, folds, eval_pos and fold_bounds are built by the
    identical sequence used in scripts/run_phase2.py.

ABORT CONDITIONS
    * specification hash mismatch;
    * eligible set not exactly 233;
    * event counts not exactly 149 / 111 / 81 / 58;
    * any NaN in the eligible VI series;
    * delta = 0 rejection rate above 0.20 (section 2.5 gross-malfunction guard).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import (Config, TEST_START, select_cov_window,   # noqa: E402
                            SAMPLE_START, DEV_END)
from rac_hrp.data import panel                                       # noqa: E402
from rac_hrp.data.universe import UniverseBuilder, realized_n_report  # noqa: E402
from rac_hrp.backtest.folds import FoldGenerator                     # noqa: E402
from rac_hrp.phase2.calibration import structural_pass               # noqa: E402
from rac_hrp.phase2 import power as PW                               # noqa: E402

SPEC_FILE = "RAC_HRP_Phase2E_PreSpec_rev8.md"
SPEC_SHA = "cfdd64cca9a23a1d873695b2de0576b442cf2b80e302602830a0d1502c403674"
THRESHOLD_HOURS = 12.0


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_structural(raw: str, n_assets: int, verbose: bool = True):
    """Identical to scripts/run_phase2.py."""
    P = panel.build_panels(raw)
    if verbose:
        print(f"  panel                : {P.returns.shape[0]:,} days x "
              f"{P.returns.shape[1]:,} permnos")

    cfg0 = Config(n_assets=n_assets)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    med_n = float(realized_n_report(
        UniverseBuilder(P, cfg0).snapshots(probe)).n_selected.median())
    W = select_cov_window(med_n)
    cfg = Config(n_assets=n_assets, cov_window=W)
    if verbose:
        print(f"  D4 window            : W = {W}  (median realized N = {med_n:.0f})")

    folds = FoldGenerator(P.returns.index, cfg).dev_folds()
    eval_pos = np.concatenate([f.test_pos for f in folds])
    fold_bounds = [(int(f.test_pos[0]), int(f.test_pos[-1])) for f in folds]

    dates = P.returns.index[eval_pos]
    if (dates >= pd.Timestamp(TEST_START)).any():
        raise PermissionError(
            f"2E-POWER attempted to evaluate on/after the test start {TEST_START}. "
            "Test-region work is not authorized.")
    if verbose:
        print(f"  dev span             : {dates[0].date()} -> {dates[-1].date()} "
              f"({len(eval_pos):,} days, {len(folds)} folds)")

    sp = structural_pass(P, cfg, eval_pos, fold_bounds, verbose=verbose)
    return sp, cfg, dates


def main() -> int:
    ap = argparse.ArgumentParser(
        description="2E-POWER (development region only, non-gating)")
    ap.add_argument("--raw", default=os.path.expanduser("~/rac_hrp_data/raw"))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--outdir", default="outputs/phase2e_power")
    ap.add_argument("--probe-only", action="store_true",
                    help="measure timing and exit without running the grid")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    print("=" * 78)
    print("  2E-POWER -- planted-effect power curve")
    print("=" * 78)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec_path = os.path.join(root, SPEC_FILE)
    if not os.path.exists(spec_path):
        print(f"  *** {SPEC_FILE} not found; cannot verify the freeze. Aborting.")
        return 2
    got = _sha256(spec_path)
    print(f"  Frozen specification : {SPEC_FILE}")
    print(f"  spec SHA-256         : {got}")
    if got != SPEC_SHA:
        print(f"  *** SPEC HASH MISMATCH -- expected {SPEC_SHA}")
        return 2
    print("  spec hash            : verified")
    print(f"  threads              : OPENBLAS_NUM_THREADS="
          f"{os.environ.get('OPENBLAS_NUM_THREADS', 'unset')}")
    print("  NON-GATING. The Phase 2A verdict stands regardless of this result.")
    print("  Performance is NOT computed. Test region is structurally blocked.")
    print()

    sp, cfg, dates = build_structural(a.raw, a.n)

    try:
        inp = PW.build_inputs(sp)
    except PW.PowerAbort as e:
        print(f"\n  *** ABORTED -- {e}")
        return 3
    print(f"  base path            : E = {inp.E}, observed VI median "
          f"{inp.base_median:.4f}, centred")
    print(f"  event counts         : "
          + ", ".join(f"g={g}:{inp.n_events[g]}" for g in PW.GAMMA_CANDIDATES))
    print()

    per = PW.probe_timing(inp, 50)
    cells = len(PW.GAMMA_CANDIDATES) * len(PW.DELTA_GRID) * len(PW.CONDITIONS) + 1
    hours = per * PW.N_REPLICATIONS_DEFAULT * cells / 3600.0
    print(f"  timing probe         : {per:.3f} s/replication")
    print(f"  extrapolated         : {hours:.1f} h at "
          f"{PW.N_REPLICATIONS_DEFAULT} replications across {cells} cells")
    if hours > THRESHOLD_HOURS:
        print(f"  *** exceeds the {THRESHOLD_HOURS:.0f} h threshold in section 2.8.")
        print("  *** The replication count may be reduced to 1000, but ONLY after")
        print("  *** appending a dated amendment to the frozen memo recording the")
        print("  *** measured timing. Do that first, then re-run. Aborting.")
        return 4
    print(f"  section 2.8          : under threshold; replication count unchanged, "
          "no amendment")
    print()

    if a.probe_only:
        print("  --probe-only: exiting without running the grid.")
        return 0

    print("-" * 78)
    t0 = time.time()
    try:
        res = PW.run_power(sp, n_replications=PW.N_REPLICATIONS_DEFAULT, verbose=True)
    except PW.PowerAbort as e:
        print(f"\n  *** ABORTED -- {e}")
        return 3
    elapsed = time.time() - t0

    print()
    print("-" * 78)
    print(PW.format_report(res))
    print("-" * 78)
    print(f"  elapsed              : {elapsed/3600:.2f} h")

    record = {
        "diagnostic": "2E-POWER",
        "specification": f"{SPEC_FILE} (frozen, hashed)",
        "spec_sha256": SPEC_SHA,
        "gating": False,
        "phase2a_verdict_unchanged": "NO ADMISSIBLE GAMMA",
        "n_replications": res.n_replications,
        "bootstrap_replicates": PW.BOOTSTRAP_REPLICATES,
        "alpha": PW.ALPHA,
        "base_seed": PW.BASE_SEED,
        "delta_grid": list(PW.DELTA_GRID),
        "base_path": "observed one-step VI at the 233 eligible rebalances, median-centred",
        "base_median": res.base_median,
        "mde_is_conditional_on_observed_dependence_realisation": True,
        "power_r_minus_u_includes_block_length_response": True,
        "empirical_size_on_observed_dependence": asdict(res.size_cell)
        if res.size_cell else None,
        "published_iid_size_not_comparable": 0.0660,
        "cells": [asdict(c) for c in res.cells],
        "mde80": {f"gamma={g}|{c}": v for (g, c), v in res.mde80.items()},
        "elapsed_hours": round(elapsed / 3600.0, 3),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS", "unset"),
        "code_sha256": {
            "power.py": _sha256(os.path.join(root, "rac_hrp/phase2/power.py")),
            "calibration.py": _sha256(os.path.join(root, "rac_hrp/phase2/calibration.py")),
            "stats.py": _sha256(os.path.join(root, "rac_hrp/phase2/stats.py")),
        },
    }
    out = os.path.join(a.outdir, "power_result.json")
    with open(out, "w") as f:
        json.dump(record, f, indent=2)
    print(f"  record written       : {out}")
    print()
    print("  REMINDER: post-gate, non-gating. Report alongside 2E-HORIZON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
