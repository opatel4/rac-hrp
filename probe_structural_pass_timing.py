"""
TIMING PROBE for the §4d mechanism diagnostic. Measures nothing scientific.

Runs ONE structural_pass on ONE synthetic panel and reports wall-clock, so the
replication count in the pre-specification memo is a measured number rather than
a guess. Writes no record, touches no frozen artefact, and produces no statistic
that could enter any result.

Usage:
    python probe_structural_pass_timing.py --raw ~/rac_hrp_data/raw
"""
from __future__ import annotations
import argparse, dataclasses, os, sys, time
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rac_hrp.config import (Config, TEST_START, select_cov_window,
                            SAMPLE_START, DEV_END)
from rac_hrp.data import panel
from rac_hrp.data.universe import UniverseBuilder, realized_n_report
from rac_hrp.backtest.folds import FoldGenerator
from rac_hrp.nulls import environments as ENV
from rac_hrp.phase2.calibration import structural_pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--env", default="A_iid_gaussian")
    a = ap.parse_args()

    t0 = time.time()
    P = panel.build_panels(a.raw)
    print(f"  panel load           : {time.time()-t0:6.1f}s  "
          f"({P.returns.shape[0]:,} x {P.returns.shape[1]:,})")

    # Identical D4 sequence to run_phase2.py -- W before folds.
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
    dates = P.returns.index[eval_pos]
    if (dates >= pd.Timestamp(TEST_START)).any():
        raise PermissionError("probe reached the test region")
    print(f"  D4 window            : W = {W}   dev span {len(eval_pos):,} days")

    # Synthetic returns; everything else from the REAL panel.
    t0 = time.time()
    rng = np.random.default_rng(12345)
    synth, _ = ENV.draw(a.env, P.returns, rng)
    print(f"  draw {a.env:<20}: {time.time()-t0:6.1f}s")

    P_null = dataclasses.replace(P, returns=synth)

    t0 = time.time()
    sp = structural_pass(P_null, cfg, eval_pos, fold_bounds, verbose=False)
    dt = time.time() - t0
    n_elig = int(np.sum(sp.eligible))
    print(f"  structural_pass      : {dt:6.1f}s   ({n_elig} eligible rebalances)")
    print()
    print("  ---- replication budget (structural_pass only, serial) ----")
    for reps in (50, 100, 200):
        for envs in (3,):
            tot = dt * reps * envs / 60.0
            print(f"    {envs} envs x {reps:3d} reps : {tot:7.1f} min "
                  f"({tot/60:.1f} h)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
