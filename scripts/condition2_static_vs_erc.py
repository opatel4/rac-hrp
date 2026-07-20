#!/usr/bin/env python
"""
CONDITION 2 (advisor ruling) -- paired static-HRP vs ERC contrast under Env-D.

FROZEN ANALYSIS. This script defines the contrast and the statistics BEFORE it is
run, per the ruling ("do not rerun or modify the simulation until the contrast
definition and analysis code are frozen"). It changes nothing about the null-gate
simulation: it re-executes Null Gate v1 from its FROZEN SEEDS to recover the exact
per-replication Sharpe ratios v1 produced, then computes one additional paired
contrast that v1 recorded internally but never wrote to disk.

WHY THIS IS RECOVERY, NOT RERUNNING. Every replication's RNG seed is a
deterministic function of the frozen config seed (gate.run_gate, line ~229:
seed + 1000*env_index + m). Re-executing reproduces v1's Sharpes bit-for-bit --
identical noise, identical strategies, identical numbers. No new randomness is
drawn and no simulation parameter is touched. The only thing added is the
static-vs-ERC subtraction, which is algebra on numbers v1 already computed.

WHAT IS BEING TESTED. Sharpe differences are additive within a replication, so
    (S_static - S_ERC) = (S_RAC - S_ERC) - (S_RAC - S_static)
is pinned near +0.108 in the MEAN by v1's reported cells (+0.102 and -0.006).
The point estimate therefore carries no new information. The NEW information is
the PAIRED confidence interval, whose width depends on the within-replication
covariance of the two strategies -- which v1 never surfaced.

INTERPRETATION RULE (fixed ex ante, per the ruling):
  STRONG SUPPORT      static-ERC ~ +0.10, CI excludes zero, RAC ~ static.
                      Pattern RAC ~ Static HRP > ERC. The Env-D difference
                      originates in the HRP ALLOCATOR FAMILY, not the trigger.
  PARTIAL SUPPORT     mean ~ +0.10 but CI includes zero. Pattern consistent,
                      simulation insufficiently precise.
  CONTRADICTION       static-ERC materially smaller than RAC-ERC. The trigger or
                      its interaction may contribute; current explanation dropped.

WORDING CONSTRAINT (per the ruling): a STRONG result supports the
"allocator-family explanation" ONLY. It does NOT license the more specific
mechanism ("HRP reweights newly-calm assets faster"), which needs weight-path or
regime-transition diagnostics not performed here.

Usage:
    python scripts/condition2_static_vs_erc.py --raw data/raw \\
        --reps 100 --outdir outputs/condition2
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import Config, select_cov_window, SAMPLE_START, DEV_END
from rac_hrp.data import panel
from rac_hrp.data.universe import UniverseBuilder, realized_n_report
from rac_hrp.backtest.folds import FoldGenerator
from rac_hrp.backtest.metrics import sharpe
from rac_hrp.nulls.gate import gate_strategies, _run_replication, FOCAL
from rac_hrp.nulls.environments import ENVIRONMENTS

ENV = "D_regime_switch_vol"
A, B = "HRP_static", "ERC"


def _boot_ci(d: np.ndarray, n_boot: int = 10000, seed: int = 0):
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(d, size=len(d), replace=True).mean()
                      for _ in range(n_boot)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--reps", type=int, default=100)
    ap.add_argument("--outdir", default="outputs/condition2")
    ap.add_argument("--universe", default="crsp_largecap")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    P = panel.build_panels(a.raw)
    cfg0 = Config(n_assets=100)
    ub = UniverseBuilder(P, cfg0)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    W = select_cov_window(float(realized_n_report(ub.snapshots(probe)).n_selected.median()))

    # EXACT config Null Gate v1 used -- so seeds reproduce v1's replications.
    cfg = Config(n_assets=100, cov_window=W, null_replications=a.reps)
    fg = FoldGenerator(cal, cfg)
    eval_pos = fg.dev_folds()[-1].test_pos

    print(f"Recovering Env-D per-replication Sharpes from frozen seeds "
          f"(seed={cfg.seed}, reps={a.reps}, W={W})")
    print("This reproduces Null Gate v1's numbers; it does not draw new noise.\n")

    # env index MUST match run_gate's ordering so the seed arithmetic matches v1.
    env_index = list(ENVIRONMENTS.keys()).index(ENV)
    rows = []
    for m in range(a.reps):
        rng = np.random.default_rng(cfg.seed + 1000 * env_index + m)
        srs, _ = _run_replication(P, cfg, eval_pos, ENV, rng)
        rows.append(srs)
        print(f"  rep {m+1:3d}/{a.reps}  "
              f"S_static={srs[A]:+.3f}  S_ERC={srs[B]:+.3f}  "
              f"d={srs[A]-srs[B]:+.3f}")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.outdir, "env_d_per_replication_sharpes.csv"), index=False)

    # ---- the paired contrast --------------------------------------------
    d = (df[A] - df[B]).dropna().values
    n = len(d)
    mean = float(np.mean(d))
    sd = float(np.std(d, ddof=1))
    se = sd / np.sqrt(n)                       # Monte Carlo standard error
    ci_lo, ci_hi = mean - 1.96 * se, mean + 1.96 * se
    q1, med, q3 = np.percentile(d, [25, 50, 75])
    frac_pos = float(np.mean(d > 0))
    b_lo, b_hi = _boot_ci(d, seed=cfg.seed)

    # cross-check against v1's algebra
    rac_erc = float((df[FOCAL] - df[B]).mean())
    rac_static = float((df[FOCAL] - df[A]).mean())
    implied = rac_erc - rac_static

    # ---- verdict ---------------------------------------------------------
    excludes_zero = not (ci_lo <= 0 <= ci_hi)
    near_10 = abs(mean - 0.10) < 0.05
    if excludes_zero and near_10:
        verdict = "STRONG SUPPORT for the allocator-family explanation"
    elif near_10 and not excludes_zero:
        verdict = "PARTIAL SUPPORT: pattern consistent, simulation imprecise"
    elif mean < rac_erc - 0.03:
        verdict = "CONTRADICTION: static-ERC materially < RAC-ERC; trigger may contribute"
    else:
        verdict = "AMBIGUOUS: does not fit the pre-specified cases; report descriptively"

    out = {
        "environment": ENV,
        "contrast": f"{A} - {B}",
        "n_replications": n,
        "mean": round(mean, 4),
        "monte_carlo_se": round(se, 4),
        "ci95_normal": [round(ci_lo, 4), round(ci_hi, 4)],
        "ci95_bootstrap": [round(b_lo, 4), round(b_hi, 4)],
        "median": round(float(med), 4),
        "iqr": [round(float(q1), 4), round(float(q3), 4)],
        "frac_positive": round(frac_pos, 3),
        "cross_check_implied_from_v1": round(implied, 4),
        "cross_check_rac_minus_erc": round(rac_erc, 4),
        "cross_check_rac_minus_static": round(rac_static, 4),
        "verdict": verdict,
        "wording_constraint": ("Supports 'allocator-family explanation' only. Does "
                               "NOT license the 'reweights newly-calm assets faster' "
                               "mechanism, which requires weight-path / regime-"
                               "transition diagnostics not performed here."),
        "provenance": ("Recovered from Null Gate v1 frozen seeds "
                       f"(seed={cfg.seed}); identical to v1's per-rep Sharpes. "
                       "No simulation parameter modified."),
    }
    with open(os.path.join(a.outdir, "condition2_result.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    print("\n" + "=" * 70)
    print(f"  CONDITION 2 -- {A} vs {B} under {ENV}")
    print("=" * 70)
    print(f"  mean paired ΔSharpe      {mean:+.4f}")
    print(f"  Monte Carlo SE           {se:.4f}")
    print(f"  95% CI (normal)          [{ci_lo:+.4f}, {ci_hi:+.4f}]")
    print(f"  95% CI (bootstrap)       [{b_lo:+.4f}, {b_hi:+.4f}]")
    print(f"  median [IQR]             {med:+.4f}  [{q1:+.4f}, {q3:+.4f}]")
    print(f"  P(d > 0)                 {frac_pos:.3f}")
    print(f"  algebra cross-check      implied {implied:+.4f}  vs computed {mean:+.4f}")
    print(f"\n  => {verdict}")
    print(f"\n  {out['wording_constraint']}")
    print(f"\n  artifacts: {a.outdir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
