#!/usr/bin/env python
"""
Condition 2 (Null Gate v1) -- the decisive diagnostic.

QUESTION. Under Environment D (regime-switching volatility, zero return signal),
RAC-HRP beat ERC by +0.10 Sharpe (a FAIL) but did NOT beat static HRP (-0.006, a
PASS). The interpretation on the table is: the +0.10 is an HRP-vs-ERC *allocator-
family* difference under vol clustering, NOT anything the re-clustering trigger
does. That interpretation makes a falsifiable prediction:

    If the edge is allocator-family mechanics, then STATIC HRP -- which has no
    trigger at all -- should beat ERC under Environment D by about the SAME
    +0.10 as RAC-HRP does.

This script computes that direct paired contrast. It is decisive either way:

    static_HRP - ERC  ~= +0.10   -> interpretation CONFIRMED. The edge exists
                                    with no trigger present; it is allocator
                                    mechanics. The trigger is exonerated.

    static_HRP - ERC  ~= 0       -> interpretation REFUTED. Only the TRIGGERED
                                    variant beats ERC, which would implicate the
                                    trigger after all. Stop and rethink.

METHOD. Uses the SAME environment draws (same seeds) as Null Gate v1, so every
statistic is a true paired contrast on identical synthetic panels -- not a fresh
simulation that would introduce its own Monte Carlo noise. RAC-HRP is carried
along only as a cross-check that these numbers reproduce v1's D-row exactly.

    python scripts/diagnostic_static_vs_erc.py --raw data/raw --reps 100 \\
        --universe crsp_largecap --out outputs/n100_reps100

Reads nothing it should not: development region only, test region untouched.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import Config, select_cov_window, SAMPLE_START, DEV_END
from rac_hrp.data import mock, panel
from rac_hrp.data.universe import UniverseBuilder, realized_n_report
from rac_hrp.backtest.folds import FoldGenerator
from rac_hrp.backtest.engine import WalkForward, Strategy
from rac_hrp.backtest.metrics import sharpe
from rac_hrp.data.panel import Panels
from rac_hrp.nulls.environments import draw

ENV = "D_regime_switch_vol"


def paired_contrast(panels: Panels, cfg: Config, eval_pos: np.ndarray,
                    n_reps: int) -> pd.DataFrame:
    """Per-replication Sharpes for the three strategies, on identical D draws."""
    strategies = [
        Strategy("HRP_static", allocator="hrp", recluster="never"),
        Strategy("ERC", allocator="erc"),
        Strategy("RAC_HRP", allocator="hrp", recluster="ar_trigger"),  # cross-check
    ]
    # env index in the canonical ordering, so the seed matches Null Gate v1 exactly
    from rac_hrp.nulls.environments import ENVIRONMENTS
    env_idx = list(ENVIRONMENTS.keys()).index(ENV)

    rows = []
    for m in range(n_reps):
        rng = np.random.default_rng(cfg.seed + 1000 * env_idx + m)   # == gate seed
        perf, signal = draw(ENV, panels.returns, rng)
        np_ = Panels(returns=perf, mcap=panels.mcap,
                     membership=panels.membership, rf=panels.rf,
                     delist_audit=panels.delist_audit)
        wf = WalkForward(np_, cfg, signal_returns=signal)
        res = wf.run(strategies, eval_pos)
        rows.append({k: sharpe(v.returns, panels.rf) for k, v in res.items()})
        print(f"  rep {m + 1:3d}/{n_reps}  "
              f"HRP_static={rows[-1]['HRP_static']:+.3f}  "
              f"ERC={rows[-1]['ERC']:+.3f}  "
              f"static-ERC={rows[-1]['HRP_static'] - rows[-1]['ERC']:+.3f}")
    return pd.DataFrame(rows)


def _ci(d: np.ndarray):
    d = d[np.isfinite(d)]
    mean = float(np.mean(d))
    se = float(np.std(d, ddof=1) / np.sqrt(len(d)))
    return mean, mean - 1.96 * se, mean + 1.96 * se, se


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--universe", default="crsp_largecap",
                    choices=["sp500", "crsp_largecap"])
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--reps", type=int, default=100)
    ap.add_argument("--out", default="outputs")
    a = ap.parse_args()

    raw = a.raw
    if a.mock:
        raw = "data/mock_%s" % a.universe
        if not os.path.exists(os.path.join(raw, "dsf.parquet")):
            mock.generate(raw, universe=a.universe)
    if raw is None:
        ap.error("supply --raw <dir> or --mock")
    os.makedirs(a.out, exist_ok=True)

    P = panel.build_panels(raw)
    cfg0 = Config(n_assets=a.n)
    ub = UniverseBuilder(P, cfg0)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    W = select_cov_window(float(realized_n_report(ub.snapshots(probe))
                                .n_selected.median()))
    cfg = Config(n_assets=a.n, cov_window=W, null_replications=a.reps)

    fg = FoldGenerator(cal, cfg)
    eval_pos = fg.dev_folds()[-1].test_pos   # same window Null Gate v1 used

    print("=" * 74)
    print("  CONDITION 2 -- static HRP vs ERC under Environment D (paired)")
    print("=" * 74)
    print(f"  {a.reps} replications on identical D draws (seeds match Null Gate v1)\n")

    df = paired_contrast(P, cfg, eval_pos, a.reps)
    df.to_csv(os.path.join(a.out, "diagnostic_static_vs_erc_raw.csv"), index=False)

    contrasts = {
        "static_HRP - ERC": (df["HRP_static"] - df["ERC"]).values,
        "RAC_HRP - ERC  (v1 cross-check)": (df["RAC_HRP"] - df["ERC"]).values,
        "RAC_HRP - static_HRP  (v1 cross-check)": (df["RAC_HRP"] - df["HRP_static"]).values,
    }

    print("\n" + "=" * 74)
    print("  RESULT")
    print("=" * 74)
    out_rows = []
    for name, d in contrasts.items():
        mean, lo, hi, se = _ci(d)
        out_rows.append({"contrast": name, "mean_dSharpe": round(mean, 4),
                         "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                         "se": round(se, 4)})
        print(f"  {name:42s}  mean {mean:+.4f}  CI [{lo:+.3f}, {hi:+.3f}]")
    pd.DataFrame(out_rows).to_csv(
        os.path.join(a.out, "diagnostic_static_vs_erc_summary.csv"), index=False)

    sm, slo, shi, _ = _ci(contrasts["static_HRP - ERC"])
    print("\n" + "-" * 74)
    print("  VERDICT")
    print("-" * 74)
    if slo > 0.05:
        print(f"  static HRP beats ERC by {sm:+.3f} under Environment D, with NO")
        print("  trigger present. The +0.10 RAC-vs-ERC result is an ALLOCATOR-FAMILY")
        print("  effect, not a trigger effect. Interpretation CONFIRMED.")
        print("  -> The Env-D FAIL is a cross-allocator diagnostic, not evidence")
        print("     that the trigger manufactures signal. Proceed to Null Gate v2.")
    elif abs(sm) <= 0.05:
        print(f"  static HRP vs ERC is {sm:+.3f} -- near zero. The edge over ERC")
        print("  appears ONLY with the trigger active. Interpretation REFUTED.")
        print("  -> STOP. The trigger may be implicated. Do not design v2 around")
        print("     the allocator-family explanation until this is understood.")
    else:
        print(f"  static HRP vs ERC is {sm:+.3f}, CI [{slo:+.3f}, {shi:+.3f}] --")
        print("  ambiguous at this replication count. Increase --reps and repeat")
        print("  before drawing a conclusion.")
    print(f"\n  artifacts: {a.out}/diagnostic_static_vs_erc_*.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
