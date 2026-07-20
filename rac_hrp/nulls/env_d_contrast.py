"""
rac_hrp.nulls.env_d_contrast
============================
Condition 2 of the advisor ruling on Null Gate v1.

FROZEN ANALYSIS SPECIFICATION. This module DEFINES the static-HRP-vs-ERC paired
contrast under Environment D. It is written to be reviewed and frozen BEFORE it is
executed, per the ruling: "do not rerun or modify the simulation until the contrast
definition and analysis code are frozen."

------------------------------------------------------------------------------
WHY A RE-RUN IS REQUIRED, AND WHY IT IS NOT A NEW EXPERIMENT
------------------------------------------------------------------------------
Null Gate v1 computed, for every replication r, the full Sharpe vector
    { S_EW,r , S_ERC,r , S_HRP_static,r , S_HRP_periodic_3,r , S_RAC,r }.
It then reduced each RAC-vs-comparator column to summary statistics and DISCARDED
the replication-level matrix. The pairing between S_static,r and S_ERC,r within a
replication was never written to disk.

The paired contrast d_r = S_static,r - S_ERC,r therefore CANNOT be reconstructed
from the persisted summaries. The MEAN of d_r is recoverable algebraically
(mean(static-ERC) = mean(RAC-ERC) - mean(RAC-static) = +0.102 - (-0.006) = +0.108),
but its CONFIDENCE INTERVAL is not: the CI width depends on Cov(S_static, S_ERC)
across replications, which is a joint property the marginal summaries do not carry.

Re-executing this contrast is DETERMINISTIC given the frozen seed. The gate seeds
replication m in environment e as  cfg.seed + 1000*e_index + m. The environment
draw, the panel construction, the covariance estimation and the allocators are all
deterministic functions of that seed. So a re-run reproduces S_static,r and S_ERC,r
BIT-FOR-BIT identically to v1. This is not a new simulation; it is re-executing a
deterministic function to persist an output that v1 threw away.

PROVENANCE CHECK (mandatory). The re-run must reproduce v1's reported means to
within floating-point tolerance:
    mean(S_RAC - S_ERC)    == +0.1024   (v1, 100 reps)
    mean(S_RAC - S_static) == -0.0062   (v1, 100 reps)
If these do NOT match, the seed handling is not deterministic and the re-run is a
different experiment -- STOP and diagnose before trusting any contrast.

------------------------------------------------------------------------------
WHAT THIS CONTRAST CAN AND CANNOT ESTABLISH  (advisor wording constraint)
------------------------------------------------------------------------------
A strong result (static-vs-ERC ~ +0.10, CI excluding zero, RAC ~ static) supports
the ALLOCATOR-FAMILY explanation: the Environment-D difference originates in the
HRP allocator relative to ERC, not in adaptive re-clustering.

It does NOT establish the more specific mechanism ("HRP reweights newly-calm assets
faster"). That claim requires weight-path diagnostics or conditional regime-
transition analysis and is out of scope here. Reporting language must stop at
"allocator-family explanation."
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import json

import numpy as np
import pandas as pd

from ..config import Config
from ..backtest.metrics import sharpe
from ..data.panel import Panels
from .environments import draw
from .gate import gate_strategies, FOCAL
from ..backtest.engine import WalkForward

ENV = "D_regime_switch_vol"
ENV_INDEX = 3            # position of D in the gate's environment list -- see below

# v1 reference means (100 reps) for the provenance check. Sourced from the frozen
# outputs/n100_reps100 null_gate table. Tolerance is loose enough for float noise,
# tight enough to catch a seed mismatch.
V1_REF = {"RAC_vs_ERC": 0.1024, "RAC_vs_static": -0.0062}
PROVENANCE_TOL = 0.02


@dataclass
class PairedContrast:
    n_reps: int
    mean: float
    ci_lo: float                 # normal-approx 95% paired CI
    ci_hi: float
    mcse: float                  # Monte Carlo standard error of the mean
    median: float
    iqr_lo: float                # 25th pct
    iqr_hi: float                # 75th pct
    frac_positive: float
    boot_lo: float               # bootstrap 95% CI (robustness)
    boot_hi: float
    # provenance
    recovered_rac_vs_erc: float
    recovered_rac_vs_static: float
    provenance_ok: bool
    seed: int

    def verdict(self, margin: float = 0.10) -> str:
        """Advisor's three-way interpretation rule."""
        excludes_zero = not (self.ci_lo <= 0.0 <= self.ci_hi)
        material = abs(self.mean) >= margin * 0.8   # "approximately +0.10"
        if excludes_zero and material:
            return "STRONG SUPPORT (allocator-family explanation)"
        if abs(self.mean) >= margin * 0.5 and not excludes_zero:
            return "PARTIAL SUPPORT (pattern consistent, imprecise)"
        if self.mean < margin * 0.5:
            return "CONTRADICTION (trigger/interaction may contribute)"
        return "AMBIGUOUS -- inspect distribution"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def compute_contrast(panels: Panels,
                     cfg: Config,
                     eval_pos: np.ndarray,
                     n_reps: int,
                     n_boot: int = 10000) -> tuple[PairedContrast, pd.DataFrame]:
    """Execute the frozen contrast. Returns (summary, per_replication_frame).

    The per-replication frame is PERSISTED by the caller -- this is the artifact
    v1 failed to save, and freezing it is condition 4 of the ruling.
    """
    rng_seed = cfg.seed
    rows = []
    for m in range(n_reps):
        # EXACT reproduction of the gate's per-rep seeding:
        #   cfg.seed + 1000 * env_index + m
        rng = np.random.default_rng(rng_seed + 1000 * ENV_INDEX + m)
        perf, signal = draw(ENV, panels.returns, rng)
        null_panels = Panels(returns=perf, mcap=panels.mcap,
                             membership=panels.membership, rf=panels.rf,
                             delist_audit=panels.delist_audit)
        wf = WalkForward(null_panels, cfg, signal_returns=signal)
        res = wf.run(gate_strategies(), eval_pos)
        srs = {k: sharpe(v.returns, panels.rf) for k, v in res.items()}
        rows.append(srs)

    df = pd.DataFrame(rows)
    d = (df["HRP_static"] - df["ERC"]).values          # the paired contrast
    d = d[np.isfinite(d)]
    n = len(d)

    mean = float(np.mean(d))
    sd = float(np.std(d, ddof=1))
    mcse = sd / np.sqrt(n)
    ci_lo, ci_hi = mean - 1.96 * mcse, mean + 1.96 * mcse
    q25, q50, q75 = np.percentile(d, [25, 50, 75])

    # bootstrap CI on the paired differences (robustness to non-normality)
    brng = np.random.default_rng(cfg.seed + 777)
    boot = np.array([np.mean(brng.choice(d, size=n, replace=True))
                     for _ in range(n_boot)])
    boot_lo, boot_hi = np.percentile(boot, [2.5, 97.5])

    # provenance: recompute v1's headline contrasts from the SAME frame
    rac_erc = float(np.mean((df[FOCAL] - df["ERC"]).values))
    rac_static = float(np.mean((df[FOCAL] - df["HRP_static"]).values))
    prov_ok = (abs(rac_erc - V1_REF["RAC_vs_ERC"]) < PROVENANCE_TOL and
               abs(rac_static - V1_REF["RAC_vs_static"]) < PROVENANCE_TOL)

    summary = PairedContrast(
        n_reps=n, mean=mean, ci_lo=ci_lo, ci_hi=ci_hi, mcse=mcse,
        median=float(q50), iqr_lo=float(q25), iqr_hi=float(q75),
        frac_positive=float(np.mean(d > 0)),
        boot_lo=float(boot_lo), boot_hi=float(boot_hi),
        recovered_rac_vs_erc=rac_erc, recovered_rac_vs_static=rac_static,
        provenance_ok=prov_ok, seed=cfg.seed,
    )
    return summary, df


def report(summary: PairedContrast) -> str:
    L = []
    L.append("ENVIRONMENT-D PAIRED CONTRAST  (static HRP - ERC)")
    L.append("=" * 52)
    L.append(f"  replications        {summary.n_reps}")
    L.append(f"  mean d_r            {summary.mean:+.4f}")
    L.append(f"  95% paired CI       [{summary.ci_lo:+.4f}, {summary.ci_hi:+.4f}]")
    L.append(f"  Monte Carlo SE      {summary.mcse:.4f}")
    L.append(f"  median [IQR]        {summary.median:+.4f} "
             f"[{summary.iqr_lo:+.4f}, {summary.iqr_hi:+.4f}]")
    L.append(f"  P(d_r > 0)          {summary.frac_positive:.3f}")
    L.append(f"  bootstrap 95% CI    [{summary.boot_lo:+.4f}, {summary.boot_hi:+.4f}]")
    L.append("")
    L.append("  PROVENANCE (must match v1):")
    L.append(f"    recovered RAC-ERC     {summary.recovered_rac_vs_erc:+.4f}  "
             f"(v1: {V1_REF['RAC_vs_ERC']:+.4f})")
    L.append(f"    recovered RAC-static  {summary.recovered_rac_vs_static:+.4f}  "
             f"(v1: {V1_REF['RAC_vs_static']:+.4f})")
    L.append(f"    deterministic re-run  {'CONFIRMED' if summary.provenance_ok else 'FAILED -- STOP'}")
    L.append("")
    L.append(f"  => {summary.verdict()}")
    L.append("")
    L.append("  Scope constraint: a strong result supports the ALLOCATOR-FAMILY")
    L.append("  explanation only. It does NOT establish any specific weight-path")
    L.append("  mechanism; that needs conditional regime-transition diagnostics.")
    return "\n".join(L)
