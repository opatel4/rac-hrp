#!/usr/bin/env python
"""
Phase 0.5 -- Data Engineering & Staged Build.  ORCHESTRATOR.

Runs the five Phase 0.5 tasks in order and enforces the two gates that decide
whether Phase 1 is allowed to start:

  T1  CRSP point-in-time universe   (panel build + delisting splice)
  T2  Eligibility screen            (realized-N + universe-turnover report)
  T3  RECONSTRUCTION VALIDATION     <-- GATE. Survivorship re-enters here or nowhere.
  T4  Stage-1 N-invariant machinery (fold generator + full pipeline, parameterised by N)
  T5  NULL GATE v1, three nulls     <-- GATE. Trigger-timing null is the one that
                                        can kill the paper's thesis.

Usage
-----
    # offline, on synthetic data -- proves the machinery before WRDS
    python scripts/run_phase05.py --mock --n 100 --reps 20

    # the real thing, after `python -m rac_hrp.data.wrds_pull --outdir data/raw`
    python scripts/run_phase05.py --raw data/raw --n 100 --reps 50

Phase 0.5 NEVER touches the test region (2023-2025). The fold generator raises
if anything tries.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import Config, select_cov_window, SAMPLE_START, DEV_END
from rac_hrp.data import mock, panel, validation
from rac_hrp.data import validation_crsp
from rac_hrp.data.universe import UniverseBuilder, realized_n_report
from rac_hrp.backtest.folds import FoldGenerator
from rac_hrp.backtest.engine import WalkForward, default_strategies
from rac_hrp.backtest.metrics import summary_table
from rac_hrp.nulls.gate import run_gate, power_check


def rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None, help="dir with the 5 CRSP parquet files")
    ap.add_argument("--mock", action="store_true", help="generate + use synthetic data")
    ap.add_argument("--n", type=int, default=100, help="universe size (staged: 100/200/full)")
    ap.add_argument("--reps", type=int, default=20, help="null replications")
    ap.add_argument("--outdir", default="outputs")
    ap.add_argument("--skip-nulls", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="short eval window + few reps; smoke test only")
    ap.add_argument("--gate", default="v1", choices=["v1","v2"],
                    help="v2 = frozen two-tier gate (frozen protocol rev.2)")
    ap.add_argument("--universe", default="crsp_largecap",
                    choices=["sp500", "crsp_largecap"],
                    help="which T3 validation gate to apply (D1)")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    t0 = time.time()

    # ---- data source ------------------------------------------------------
    if a.mock:
        raw = "data/mock_%s" % a.universe
        if not os.path.exists(os.path.join(raw, "dsf.parquet")):
            mock.generate(raw, universe=a.universe)
    elif a.raw:
        raw = a.raw
    else:
        ap.error("supply --raw <dir> or --mock")

    if mock.is_mock(raw):
        print("\n" + "!" * 78)
        print("!!  SYNTHETIC DATA. Every number below is a machinery check, not a")
        print("!!  finding. Nothing here may be reported. Re-run with --raw once the")
        print("!!  WRDS pull is done.")
        print("!" * 78)

    # ======================================================================
    rule("T1  POINT-IN-TIME PANEL + DELISTING SPLICE")
    P = panel.build_panels(raw)
    print(f"  returns panel   {P.returns.shape[0]:,} days x {P.returns.shape[1]:,} permnos")
    print(f"  calendar        {P.returns.index[0].date()} -> {P.returns.index[-1].date()}")
    print(f"  membership      {len(P.membership):,} spells")
    if len(P.delist_audit):
        vc = P.delist_audit.source.value_counts().to_dict()
        print(f"  delisting splice {len(P.delist_audit):,} events  {vc}")
    else:
        print("  delisting splice 0 events (CIZ vintage, or MISSING -- check!)")

    # ======================================================================
    rule("T2  ELIGIBILITY SCREEN + REALIZED-N")
    cfg = Config(n_assets=a.n)
    ub = UniverseBuilder(P, cfg)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg.rebalance_freq]
    rep_n = realized_n_report(ub.snapshots(probe))
    rep_n.to_csv(os.path.join(a.outdir, "realized_n.csv"))

    med_n = float(rep_n.n_selected.median())
    print(f"  target N            {a.n}")
    print(f"  realized N          median {med_n:.0f}  min {rep_n.n_selected.min()}  "
          f"max {rep_n.n_selected.max()}")
    print(f"  dropped (seasoning) median {rep_n.n_dropped_history.median():.0f} names/rebal")
    print(f"  universe turnover   mean {rep_n.universe_turnover.mean():.1%} per rebalance")

    # ---- D4: deterministic covariance window -----------------------------
    W = select_cov_window(med_n)
    cfg = Config(n_assets=a.n, cov_window=W, null_replications=a.reps)
    print(f"\n  D4 covariance window -> W = {W}  (median N/W = {med_n / W:.3f} <= 0.67)")
    print("     (a RULE, consuming only the realized universe size -- not a tuned knob)")

    # ======================================================================
    rule("T3  RECONSTRUCTION VALIDATION   [GATE]")
    names = None
    npath = os.path.join(raw, "names.parquet")
    if os.path.exists(npath):
        names = pd.read_parquet(npath)
    if a.universe == "crsp_largecap":
        vrep = validation_crsp.validate_crsp_largecap(P, names=names, n_assets=a.n)
    else:
        vrep = validation.validate(P, names=names)
    print(vrep)
    for c in vrep.checks:
        if c.evidence is not None and len(c.evidence):
            c.evidence.to_csv(os.path.join(
                a.outdir, f"validation_{c.name.replace(' ', '_')}.csv"))
    if not vrep.passed:
        print("STOPPING. The universe is not what you think it is. Fix it before "
              "anything else -- every downstream number depends on this.")
        return 1

    # ======================================================================
    rule("T4  STAGE-1 PIPELINE (N-invariant)")
    fg = FoldGenerator(cal, cfg)
    folds = fg.dev_folds()
    for f in folds:
        print("  " + f.describe(cal))
    audit = fg.leakage_audit(folds)
    print("\n  purge/embargo audit:")
    print("  " + audit.to_string(index=False).replace("\n", "\n  "))
    audit.to_csv(os.path.join(a.outdir, "fold_leakage_audit.csv"), index=False)
    if not audit["ok"].all():
        print("STOPPING: a fold leaks. The purge/embargo did not open the gap it claims.")
        return 1

    eval_pos = folds[-1].test_pos if a.quick else np.concatenate(
        [f.test_pos for f in folds])
    print(f"\n  running the full pipeline on {len(eval_pos):,} development days "
          f"(N={a.n}, W={W}, estimator={cfg.cov_estimator})")

    wf = WalkForward(P, cfg)
    res = wf.run(default_strategies(cfg), eval_pos, verbose=True)
    tbl = summary_table(res, P.rf)
    print("\n  DEVELOPMENT-REGION PERFORMANCE  (diagnostic only -- D10: dev folds")
    print("  have NO model-selection role. These numbers select NOTHING.)\n")
    print("  " + tbl.round(3).to_string().replace("\n", "\n  "))
    tbl.to_csv(os.path.join(a.outdir, "phase05_dev_performance.csv"))

    rac = res["RAC_HRP"]
    if len(rac.diagnostics):
        rac.diagnostics.to_csv(os.path.join(a.outdir, "rac_diagnostics.csv"))
        d = rac.diagnostics
        print(f"\n  absorption ratio: mean {d.ar.mean():.4f}  sd {d.ar.std():.4f}")
        print(f"  MP components k : median {d.mp_k.median():.0f}  "
              f"(k used for AR: {d.k_used.iloc[0]:.0f}, frozen per fold)")
        print(f"  AR trigger fired: {rac.n_reclusters} times over "
              f"{len(d)} rebalances ({rac.n_reclusters / max(len(d), 1):.1%})")

    # ======================================================================
    if a.skip_nulls:
        print("\n  --skip-nulls set. THE GATE HAS NOT BEEN RUN. Phase 1 is not cleared.")
        return 0

    rule("T5  NULL GATE v1  (three nulls + Env-B)   [GATE]")
    gate_eval = folds[-1].test_pos
    reps = 3 if a.quick else a.reps
    print(f"  {reps} replications x 4 environments on the last development fold")
    print("  (equivalence test: the ENTIRE CI must fall inside the margin)\n")

    if a.gate == "v2":
        from rac_hrp.nulls.gate_v2 import run_gate_v2
        print("\n  NULL GATE v2 (frozen; frozen protocol rev.2)")
        v2rep = run_gate_v2(P, cfg, gate_eval, outdir=os.path.join(a.outdir,"null_gate_v2"), verbose=True)
        print(v2rep)
        print("\n  freeze manifest written to", os.path.join(a.outdir,"null_gate_v2","freeze_manifest.json"))
        return 0 if v2rep.overall=="PASS" else 1

    grep = run_gate(P, cfg, gate_eval, n_reps=reps, verbose=False)
    print(grep)
    grep.table().to_csv(os.path.join(a.outdir, "null_gate_v1.csv"), index=False)

    rule("GATE POWER (positive control)")
    pw = power_check(P, cfg, gate_eval, n_reps=max(3, reps // 4), verbose=False)
    print(pw.to_string(index=False))
    pw.to_csv(os.path.join(a.outdir, "gate_power.csv"), index=False)
    print("\n  Read this as the gate's minimum detectable effect. A PASS above is")
    print("  only worth what this table says it is worth.")

    # ======================================================================
    with open(os.path.join(a.outdir, "phase05_config.json"), "w") as fh:
        fh.write(cfg.to_json())

    rule("PHASE 0.5 SUMMARY")
    print(f"  reconstruction gate : {'PASS' if vrep.passed else 'FAIL'}")
    print(f"  null gate v1        : {'PASS' if grep.passed else ('FAIL' if grep.any_fail else 'INCONCLUSIVE')}")
    print(f"  elapsed             : {time.time() - t0:.0f}s")
    print(f"  artifacts           : {a.outdir}/")

    if vrep.passed and grep.passed:
        print("\n  => PHASE 1 IS CLEARED.")
        return 0
    print("\n  => PHASE 1 IS NOT CLEARED. Do not proceed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
