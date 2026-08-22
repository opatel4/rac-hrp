"""
Modal-gap-share NULL CALIBRATION -- diagnostic for the Phase 2 timing_variation
criterion.

PURPOSE
    Determine whether `modal_gap_share`, as computed by the FROZEN
    `timing_variation`, can distinguish a temporally structured trigger from
    random placement at the observed firing rates. Motivated by the frozen
    Phase 2 result: modal_gap_share sat at 0.76-0.82 across every gamma, was
    nearly flat while cv_gap climbed monotonically, and matched the range seen
    earlier on STRUCTURELESS mock data. A statistic that returns the same value
    on noise and on real data may be measuring event density, not trigger
    quality.

WHAT THIS DOES NOT DO
    It does not alter any Phase 2 result. The gate has already stopped and that
    conclusion is frozen. This only characterises WHY it stopped, and it reuses
    the frozen statistic rather than reimplementing it.

DECISION RULE  (fixed in writing BEFORE execution; see advisor memo)
    For each candidate with n events over E eligible rebalances, draw B random
    size-n subsets of {0..E-1}, feed each (sorted) to the frozen
    `timing_variation`, and collect the null distribution of modal_gap_share.
    Let mu0 be its mean and [q2.5, q97.5] its central 95%.
      (A) mu0 > MODAL_CEILING (0.50)
          => the ceiling is UNREACHABLE at this firing rate. No trigger,
             structured or not, can satisfy the criterion. The failure is a
             specification artefact of event density, not evidence about the
             trigger.
      (B) m_obs within [q2.5, q97.5]
          => the criterion does not discriminate the real trigger from random
             placement at this rate. Uninformative here.
      (C) m_obs > q97.5
          => the real trigger is MORE temporally clustered than random.
             modal_gap_share is detecting genuine burstiness; the failure is
             evidence about the trigger.
    All three outcomes are reportable. The verdict does not depend on the sign
    of the Phase 2 result.

PRE-REGISTERED PARAMETERS
    MODAL_NULL_SEED = 20260821   (new, documented here; local Generator only)
    MODAL_NULL_B    = 10_000     (null placements per candidate)
    MODAL_CEILING   = 0.50       (= config MODAL_GAP_SHARE_MAX)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# CONFIRM THIS IMPORT PATH before trusting a real run:
#     grep -rn "def timing_variation" rac_hrp/phase2/
# The statistic MUST be the frozen one; do not reimplement it here.
from rac_hrp.phase2.stats import timing_variation           # noqa: E402

MODAL_NULL_SEED = 20260821
MODAL_NULL_B = 10_000
MODAL_CEILING = 0.50


def null_modal_gap_shares(n_events: int, E: int, B: int,
                          rng: np.random.Generator) -> np.ndarray:
    """B random size-n subsets of {0..E-1}, each scored by the frozen statistic."""
    out = np.empty(B, dtype=float)
    for b in range(B):
        idx = np.sort(rng.choice(E, size=n_events, replace=False))
        out[b] = timing_variation(idx).modal_gap_share
    return out


def classify(m_obs: float, null: np.ndarray) -> dict:
    mu0 = float(np.mean(null))
    q2_5, q50, q97_5 = (float(np.percentile(null, p)) for p in (2.5, 50, 97.5))
    ceiling_unreachable = mu0 > MODAL_CEILING
    placement = float(np.mean(null >= m_obs))     # one-sided upper tail
    if ceiling_unreachable:
        verdict = "A: ceiling unreachable at this firing rate (spec artefact)"
    elif m_obs > q97_5:
        verdict = "C: observed more bursty than random (criterion is informative)"
    elif m_obs < q2_5:
        verdict = "observed LESS bursty than random (unexpected; investigate)"
    else:
        verdict = "B: indistinguishable from random (uninformative at this rate)"
    return {"null_mean": round(mu0, 4), "null_p2.5": round(q2_5, 4),
            "null_p50": round(q50, 4), "null_p97.5": round(q97_5, 4),
            "m_obs": round(float(m_obs), 4),
            "obs_upper_tail_placement": round(placement, 4),
            "ceiling_unreachable": ceiling_unreachable, "verdict": verdict}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Null calibration of the Phase 2 modal_gap_share criterion")
    ap.add_argument("--table", default="outputs/phase2/calibration_table.csv",
                    help="the FROZEN calibration table (source of n, E, m_obs)")
    ap.add_argument("--outdir", default="outputs/phase2_diagnostics")
    ap.add_argument("--B", type=int, default=MODAL_NULL_B)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    t = pd.read_csv(a.table)
    for col in ("gamma", "n_events", "n_eligible", "modal_gap_share"):
        if col not in t.columns:
            raise SystemExit(f"frozen table is missing column '{col}'")

    rng = np.random.default_rng(MODAL_NULL_SEED)
    print("=" * 78)
    print("  MODAL-GAP-SHARE NULL CALIBRATION  (diagnostic; Phase 2 result unchanged)")
    print("=" * 78)
    print(f"  frozen table : {a.table}")
    print(f"  seed         : {MODAL_NULL_SEED}   B = {a.B:,}   ceiling = {MODAL_CEILING}")
    print(f"  statistic    : rac_hrp.phase2.stats.timing_variation (frozen)")
    print()

    rows = []
    for _, r in t.iterrows():
        n, E, m_obs = int(r.n_events), int(r.n_eligible), float(r.modal_gap_share)
        null = null_modal_gap_shares(n, E, a.B, rng)
        c = classify(m_obs, null)
        c = {"gamma": float(r.gamma), "n_events": n, "n_eligible": E, **c}
        rows.append(c)
        print(f"  gamma={c['gamma']:<4} n={n:>3}/{E}  m_obs={c['m_obs']:.4f}  "
              f"null mean={c['null_mean']:.4f} "
              f"[{c['null_p2.5']:.4f}, {c['null_p97.5']:.4f}]")
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
