"""
rac_hrp.nulls.gate_v2
=====================
Null Gate v2 -- the frozen, two-tier gate authorized by the signed protocol (rev.2).

Structure:
  * PRIMARY GATE (gating): RAC-HRP vs same-policy comparators {HRP_static,
    HRP_periodic_3}. One-sided paired-t, margin +0.10. This tier blocks Phase 1.
  * DIAGNOSTIC PANEL (non-gating): RAC-HRP and HRP_static vs {EW, ERC}. Reported,
    never gates.
  * CONTROLS (gating precondition): deterministic location-shift null/positive
    controls per primary cell; misclassification -> whole-gate INCONCLUSIVE.
  * TRIGGER ACTIVATION (gating precondition): per-environment sufficiency;
    failure -> that environment's primary cells are INCONCLUSIVE.
  * BOOTSTRAP (diagnostic): paired percentile bounds, seeded per protocol.

Every replication-level Sharpe is persisted so all statistics are reproducible
without re-execution. A freeze manifest hashes the frozen inputs.

v1 is untouched and remains the immutable historical record.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import Config
from ..backtest.engine import WalkForward, Strategy
from ..backtest.metrics import sharpe
from ..data.panel import Panels
from .environments import ENVIRONMENTS, draw
from .gate_v2_config import (GateV2Config, ENV_INDEX, DIAGNOSTIC_COMPARATORS,
                             ENVIRONMENT_ORDER)
from .gate_v2_stats import (paired_t_bounds, control_verdicts, paired_bootstrap,
                            trigger_activation, TVerdict)

FOCAL = "RAC_HRP"


def v2_strategies() -> List[Strategy]:
    """RAC-HRP + the two same-policy primaries + the two diagnostic allocators."""
    return [
        Strategy(FOCAL, allocator="hrp", recluster="ar_trigger"),
        Strategy("HRP_static", allocator="hrp", recluster="never"),
        Strategy("HRP_periodic_3", allocator="hrp", recluster="periodic:3"),
        Strategy("EW", allocator="ew"),
        Strategy("ERC", allocator="erc"),
    ]


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
@dataclass
class PrimaryCell:
    env: str
    comparator: str
    t: TVerdict
    boot_lower: float
    boot_upper: float
    null_ctrl: str
    pos_ctrl: str
    activation_ok: bool
    verdict: str          # PASS | FAIL | INCONCLUSIVE | INCONCLUSIVE - LOW TRIGGER ACTIVATION


@dataclass
class DiagnosticCell:
    env: str
    focal: str            # RAC_HRP or HRP_static
    comparator: str       # EW or ERC
    mean: float
    upper: float
    lower: float


@dataclass
class V2Report:
    primary: List[PrimaryCell] = field(default_factory=list)
    diagnostic: List[DiagnosticCell] = field(default_factory=list)
    activation: Dict[str, dict] = field(default_factory=dict)
    control_validation_ok: bool = True
    control_failures: List[str] = field(default_factory=list)
    sharpe_matrix_path: str = ""
    manifest: dict = field(default_factory=dict)

    @property
    def overall(self) -> str:
        if not self.control_validation_ok:
            return "INCONCLUSIVE - CONTROL VALIDATION REQUIREMENT NOT MET"
        verdicts = [c.verdict for c in self.primary]
        if any(v == "FAIL" for v in verdicts):
            return "FAIL"
        if any("INCONCLUSIVE" in v for v in verdicts):
            return "INCONCLUSIVE"
        return "PASS"

    def primary_table(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "environment": c.env, "vs": c.comparator,
            "mean_dSharpe": round(c.t.mean, 4),
            "one_sided_U": round(c.t.upper, 4),
            "one_sided_L": round(c.t.lower, 4),
            "boot_[L,U]": f"[{c.boot_lower:+.3f}, {c.boot_upper:+.3f}]",
            "null_ctrl": c.null_ctrl, "pos_ctrl": c.pos_ctrl,
            "verdict": c.verdict,
        } for c in self.primary])

    def diagnostic_table(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "environment": c.env, "focal": c.focal, "vs": c.comparator,
            "mean_dSharpe": round(c.mean, 4),
            "one_sided_[L,U]": f"[{c.lower:+.3f}, {c.upper:+.3f}]",
        } for c in self.diagnostic])

    def __str__(self) -> str:
        L = ["NULL GATE v2  (frozen; signed protocol rev.2)",
             "=" * 60, "",
             "PRIMARY GATE (same-policy; gating):",
             self.primary_table().to_string(index=False), "",
             "DIAGNOSTIC PANEL (cross-allocator; NON-gating):",
             self.diagnostic_table().to_string(index=False) if self.diagnostic
             else "  (none)", ""]
        L.append("TRIGGER ACTIVATION (per environment):")
        for e, a in self.activation.items():
            L.append(f"    {e:22s} median firing {a['median_firing_rate']:.1%}  "
                     f"reps>=3 events {a['frac_reps_active']:.0%}  "
                     f"{'OK' if a['sufficient'] else 'INSUFFICIENT'}")
        L.append("")
        if not self.control_validation_ok:
            L.append("CONTROL VALIDATION: FAILED")
            for f in self.control_failures:
                L.append(f"    {f}")
        else:
            L.append("CONTROL VALIDATION: all null controls PASS, all positive controls FAIL")
        L += ["", f"=> OVERALL: {self.overall}"]
        return "\n".join(L)


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
def _run_env(panels: Panels, cfg: Config, v2: GateV2Config,
             eval_pos: np.ndarray, env: str, n_reps: int,
             verbose: bool) -> tuple:
    """Return (sharpe_df, firing_rates, event_counts) for one environment.

    sharpe_df: one row per replication, columns = strategy names.
    """
    rows, firing_rates, event_counts = [], [], []
    strategies = v2_strategies()
    for r in range(n_reps):
        rng = np.random.default_rng(v2.seed_for(env, r))
        perf, signal = draw(env, panels.returns, rng)
        np_ = Panels(returns=perf, mcap=panels.mcap, membership=panels.membership,
                     rf=panels.rf, delist_audit=panels.delist_audit)
        wf = WalkForward(np_, cfg, signal_returns=signal)
        res = wf.run(strategies, eval_pos)

        row = {k: sharpe(v.returns, panels.rf) for k, v in res.items()}
        rows.append(row)

        rac = res[FOCAL]
        n_events = rac.n_reclusters
        n_opps = len(rac.diagnostics) if len(rac.diagnostics) else 1
        event_counts.append(n_events)
        firing_rates.append(n_events / n_opps)
        if verbose:
            print(f"    {env} rep {r+1:3d}/{n_reps}  triggers={n_events}")
    return pd.DataFrame(rows), np.array(firing_rates), np.array(event_counts)


def run_gate_v2(panels: Panels, cfg: Config, eval_pos: np.ndarray,
                v2: Optional[GateV2Config] = None,
                outdir: str = "outputs/null_gate_v2",
                verbose: bool = False) -> V2Report:
    v2 = v2 or GateV2Config()
    os.makedirs(outdir, exist_ok=True)
    rep = V2Report()
    margin, conf = v2.materiality_margin, v2.confidence

    all_matrices = {}
    for env in ENVIRONMENT_ORDER:
        n = v2.replications[env]
        if verbose:
            print(f"\n  [{env}] {ENVIRONMENTS[env]}  ({n} reps)")
        sdf, fr, ec = _run_env(panels, cfg, v2, eval_pos, env, n, verbose)
        all_matrices[env] = sdf

        # ---- trigger activation [A-3] --------------------------------
        act = trigger_activation(fr, ec, v2.min_median_firing_rate,
                                 v2.min_events_per_rep, v2.min_frac_reps_active)
        rep.activation[env] = asdict(act)

        # ---- primary cells -------------------------------------------
        for c in v2.primary_comparators:
            d = (sdf[FOCAL] - sdf[c]).values
            d = d[np.isfinite(d)]
            tv = paired_t_bounds(d, margin, conf)

            bseed = v2.bootstrap_seed_for(env, c)
            bl, bu = paired_bootstrap(d, bseed, v2.bootstrap_resamples, conf)

            nv, pv = control_verdicts(d, v2.null_delta, v2.positive_delta,
                                      margin, conf)
            if nv.verdict != "PASS":
                rep.control_validation_ok = False
                rep.control_failures.append(
                    f"{env} vs {c}: null control -> {nv.verdict} (must PASS)")
            if pv.verdict != "FAIL":
                rep.control_validation_ok = False
                rep.control_failures.append(
                    f"{env} vs {c}: positive control -> {pv.verdict} (must FAIL)")

            if not act.sufficient:
                verdict = "INCONCLUSIVE - LOW TRIGGER ACTIVATION"
            else:
                verdict = tv.verdict

            rep.primary.append(PrimaryCell(
                env=env, comparator=c, t=tv, boot_lower=bl, boot_upper=bu,
                null_ctrl=nv.verdict, pos_ctrl=pv.verdict,
                activation_ok=act.sufficient, verdict=verdict))

        # ---- diagnostic panel [P2.2] ---------------------------------
        for foc in (FOCAL, "HRP_static"):
            for c in DIAGNOSTIC_COMPARATORS[env]:
                d = (sdf[foc] - sdf[c]).values
                tv = paired_t_bounds(d[np.isfinite(d)], margin, conf)
                rep.diagnostic.append(DiagnosticCell(
                    env=env, focal=foc, comparator=c,
                    mean=tv.mean, upper=tv.upper, lower=tv.lower))

    # ---- persist replication-level Sharpe matrix [A-5] ---------------
    long = []
    for env, sdf in all_matrices.items():
        s = sdf.copy()
        s.insert(0, "replication", range(len(s)))
        s.insert(0, "environment", env)
        long.append(s)
    matrix = pd.concat(long, ignore_index=True)
    mpath = os.path.join(outdir, "replication_sharpe_matrix.csv")
    matrix.to_csv(mpath, index=False)
    rep.sharpe_matrix_path = mpath

    rep.primary_table().to_csv(os.path.join(outdir, "primary_gate.csv"), index=False)
    if rep.diagnostic:
        rep.diagnostic_table().to_csv(os.path.join(outdir, "diagnostic_panel.csv"), index=False)

    # ---- freeze manifest [P§8] ---------------------------------------
    rep.manifest = freeze_manifest(v2, outdir)
    with open(os.path.join(outdir, "freeze_manifest.json"), "w") as fh:
        json.dump(rep.manifest, fh, indent=2)

    return rep


# --------------------------------------------------------------------------
# Freeze manifest [P§8] -- makes "frozen and unaltered" verifiable
# --------------------------------------------------------------------------
def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def freeze_manifest(v2: GateV2Config, outdir: str) -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    frozen_files = ["gate_v2_config.py", "gate_v2_stats.py", "gate_v2.py",
                    "environments.py"]
    hashes = {}
    for f in frozen_files:
        p = os.path.join(here, f)
        if os.path.exists(p):
            hashes[f] = _hash_file(p)
    return {
        "base_seed": v2.base_seed,
        "replications": v2.replications,
        "materiality_margin": v2.materiality_margin,
        "primary_comparators": list(v2.primary_comparators),
        "null_delta": v2.null_delta,
        "positive_delta": v2.positive_delta,
        "code_sha256": hashes,
        "config_json": v2.to_json(),
    }
