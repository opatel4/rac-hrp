"""
Modal-gap-share NULL CHARACTERISATION -- diagnostic for the Phase 2
timing_variation criterion.  (Post-gate; NON-RESCUING; cannot alter the frozen
Phase 2 result.)

Advisor ruling (rev.): APPROVED with a corrected decision rule. The earlier
"null mean > 0.50 => ceiling unreachable" rule was WRONG and has been removed. A
null mean above 0.50 means a randomly placed trigger of that density typically
exceeds 0.50 -- it does NOT mean a modal share <= 0.50 is unreachable. Those are
different claims. Reachability is a COMBINATORIAL question, computed separately.

DECISION RULE  (fixed in writing before execution)
    For each candidate with n events over E eligible rebalances:
      1. NULL: draw B random size-n subsets of {0..E-1}, score each with the
         frozen timing_variation; record the null distribution of modal_gap_share
         (and cv_gap).
         * Case A -- m_obs within null central 95% [q2.5,q97.5]: statistic does
             not distinguish the real trigger from random timing at this density.
         * Case B -- m_obs > null q97.5: real trigger more clustered than random;
             criterion IS informative; failure is evidence about the trigger.
      2. FEASIBILITY (separate, deterministic): minimum modal-gap-1 fraction
         forced by packing n into E is max(0, 2n-E-1)/(n-1).
         * Case C -- floor > 0.50: threshold combinatorially unattainable at this
             n; criterion structurally invalid there. Decided ONLY by the floor,
             never by the null mean.
    All outcomes reportable; verdict independent of the Phase 2 result's sign.

PRE-REGISTERED  (stated before the diagnostic result is known)
    MODAL_NULL_SEED = 20260821   MODAL_NULL_B = 10_000   MODAL_CEILING = 0.50
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Frozen statistic. Confirmed at rac_hrp/phase2/stats.py:106. Do not reimplement.
from rac_hrp.phase2.stats import timing_variation           # noqa: E402

MODAL_NULL_SEED = 20260821
MODAL_NULL_B = 10_000
MODAL_CEILING = 0.50


def feasibility_floor(n: int, E: int) -> float:
    """Min attainable modal-gap-1 fraction: max(0, 2n-E-1) forced gap-1 intervals
    out of (n-1) gaps."""
    if n < 2:
        return float("nan")
    return max(0, 2 * n - E - 1) / (n - 1)


def null_distributions(n: int, E: int, B: int, rng: np.random.Generator):
    modal = np.empty(B); cv = np.empty(B)
    for b in range(B):
        idx = np.sort(rng.choice(E, size=n, replace=False))
        ts = timing_variation(idx)
        modal[b] = ts.modal_gap_share
        cv[b] = ts.cv_gap
    return modal, cv


def classify(m_obs: float, modal_null: np.ndarray, floor: float) -> dict:
    q2_5, q50, q97_5 = (float(np.percentile(modal_null, p)) for p in (2.5, 50, 97.5))
    upper_tail_p = float(np.mean(modal_null >= m_obs))
    infeasible = floor > MODAL_CEILING
    if infeasible:
        verdict = ("C: 0.50 threshold combinatorially unattainable at this n "
                   "(criterion structurally invalid here)")
    elif m_obs > q97_5:
        verdict = ("B: observed more bursty than random "
                   "(criterion informative; failure is evidence)")
    elif m_obs < q2_5:
        verdict = "observed LESS bursty than random (unexpected; investigate)"
    else:
        verdict = ("A: indistinguishable from random at this density "
                   "(uninformative here)")
    return {"null_p2.5": round(q2_5, 4), "null_p50": round(q50, 4),
            "null_p97.5": round(q97_5, 4),
            "null_mean": round(float(np.mean(modal_null)), 4),
            "m_obs": round(float(m_obs), 4),
            "obs_upper_tail_p": round(upper_tail_p, 4),
            "feasibility_floor": round(floor, 4),
            "threshold_attainable": not infeasible, "verdict": verdict}


def audit_one(table: pd.DataFrame, E: int) -> None:
    """Advisor's hand-check: gaps, frequencies, modal gap, hand share vs the
    function output, so the statistic is verified by eye."""
    n = int(table.iloc[-1].n_events)
    rng = np.random.default_rng(MODAL_NULL_SEED)
    idx = np.sort(rng.choice(E, size=n, replace=False))
    gaps = np.diff(idx)
    vals, counts = np.unique(gaps, return_counts=True)
    modal_gap = int(vals[np.argmax(counts)])
    hand = int(counts.max()) / (n - 1)
    ts = timing_variation(idx)
    print("  AUDIT (one random trigger set, sparsest n):")
    print(f"    n={n}, {n-1} gaps")
    print(f"    gap value : count -> {dict(zip(vals.tolist(), counts.tolist()))}")
    print(f"    modal gap = {modal_gap}, count = {int(counts.max())}")
    print(f"    hand modal_gap_share = {hand:.6f}")
    print(f"    timing_variation()   = {ts.modal_gap_share:.6f}   "
          f"(match: {abs(hand - ts.modal_gap_share) < 1e-9})")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Null characterisation of the Phase 2 modal_gap_share criterion")
    ap.add_argument("--table", default="outputs/phase2/calibration_table.csv")
    ap.add_argument("--outdir", default="outputs/phase2_diagnostics")
    ap.add_argument("--B", type=int, default=MODAL_NULL_B)
    ap.add_argument("--audit", action="store_true",
                    help="hand-verify the statistic on one set, then exit")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    t = pd.read_csv(a.table)
    for col in ("gamma", "n_events", "n_eligible", "modal_gap_share"):
        if col not in t.columns:
            raise SystemExit(f"frozen table is missing column '{col}'")
    E = int(t.iloc[0].n_eligible)

    if a.audit:
        audit_one(t, E)
        return 0

    rng = np.random.default_rng(MODAL_NULL_SEED)
    print("=" * 78)
    print("  MODAL-GAP-SHARE NULL CHARACTERISATION  (post-gate; non-rescuing)")
    print("=" * 78)
    print(f"  frozen table : {a.table}")
    print(f"  seed {MODAL_NULL_SEED}  B={a.B:,}  ceiling={MODAL_CEILING}  E={E}")
    print(f"  statistic    : rac_hrp.phase2.stats.timing_variation (frozen)")
    print()

    rows = []
    for _, r in t.iterrows():
        n, m_obs = int(r.n_events), float(r.modal_gap_share)
        floor = feasibility_floor(n, E)
        modal_null, cv_null = null_distributions(n, E, a.B, rng)
        c = {"gamma": float(r.gamma), "n_events": n, "n_eligible": E,
             "cv_null_mean": round(float(np.mean(cv_null)), 4),
             **classify(m_obs, modal_null, floor)}
        rows.append(c)
        print(f"  gamma={c['gamma']:<4} n={n:>3}/{E}  m_obs={c['m_obs']:.4f}  "
              f"null[{c['null_p2.5']:.4f},{c['null_p97.5']:.4f}] "
              f"floor={c['feasibility_floor']:.4f}")
        print(f"         -> {c['verdict']}")
    print()

    manifest = {"seed": MODAL_NULL_SEED, "B": a.B, "ceiling": MODAL_CEILING,
                "statistic": "rac_hrp.phase2.stats.timing_variation",
                "source_table": a.table, "candidates": rows}
    with open(os.path.join(a.outdir, "modal_gap_null.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"  record : {a.outdir}/modal_gap_null.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
