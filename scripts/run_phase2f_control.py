"""
Phase 2F -- W-CALIBRATED POSITIVE CONTROL.

Frozen specification: RAC_HRP_Phase2F_PreSpec_rev2.md
SHA-256: 1adee84e80e10eed0beda46dcfc155bc66240833db2ba17e6d2ec8665709417f

STANDALONE MODULE. `rac_hrp/nulls/environments.py` is hashed in
outputs/phase2_mechanism/mechanism_null.json and is NOT modified. The slow variant
is dispatched directly here, exactly as environments_static.py does for environment
S, and for the same reason: registering it in ENVIRONMENTS would shift the ordering
that list(ENVIRONMENTS.keys()).index(ENV) uses for seed derivation.

WHY THIS RUN EXISTS
    Environment D was the positive control in the frozen mechanism null. Real-data
    excess burstiness exceeded its 97.5th percentile at every gamma, so D did not
    bracket the observed values and the experiment's sensitivity was never shown.
    D's states persist ~100 and ~34 daily observations against W = 504, so a single
    covariance window spans about four complete cycles and averages the designed
    structure away.

    The Markov sampling itself was verified correct: 200,000-step simulation of the
    frozen state machine returns P(0->1) = 0.0100 and P(1->0) = 0.0293 against
    intended 0.01 and 0.03. The mismatch is durations against W, nothing else.

WHAT CHANGES
    p_stay (0.99, 0.97) -> (0.999, 0.9985): mean runs 100/34 days -> 1000/667 days,
    both longer than W = 504. n_factors, vol_ratio and corr_shift are unchanged.

WHAT DOES NOT CHANGE
    Statistic, placement correction, trigger rule, gamma grid and ordering, NaN
    mask, membership path, market caps, rebalance dates, W, k, smoothing, sigma-hat.
    The m(n) density cache is LOADED from the frozen manifest rather than
    recomputed, so the density correction is bit-identical to the frozen arms.

SEEDS
    Environment draws use the Phase 2F base 102633858. The placement cache carries
    the frozen base 20260822 by construction, since it is loaded not regenerated.

NON-GATING. Nothing here can reopen Phase 2A. No performance quantity is computed.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import (Config, TEST_START, select_cov_window,      # noqa: E402
                            SAMPLE_START, DEV_END)
from rac_hrp.data import panel                                          # noqa: E402
from rac_hrp.data.universe import UniverseBuilder, realized_n_report     # noqa: E402
from rac_hrp.backtest.folds import FoldGenerator                        # noqa: E402
from rac_hrp.phase2.calibration import structural_pass                  # noqa: E402
from rac_hrp.phase2.stats import timing_variation                       # noqa: E402

SPEC_FILE = "RAC_HRP_Phase2F_PreSpec_rev2.md"
SPEC_SHA = "1adee84e80e10eed0beda46dcfc155bc66240833db2ba17e6d2ec8665709417f"
FROZEN_MANIFEST = "outputs/phase2_mechanism/mechanism_null.json"

BASE_SEED = 102633858                 # Phase 2F, section 3
N_REPS = 500
GAMMAS: Tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)

P_STAY_SLOW = (0.999, 0.9985)         # mean runs 1000 and 667 days
N_FACTORS = 3
VOL_RATIO = 2.5
CORR_SHIFT = 1.4


def rep_seed(rep: int) -> int:
    return BASE_SEED + rep


# --------------------------------------------------------------------------
# Slow-regime environment: frozen regime_switch_vol with longer persistence
# --------------------------------------------------------------------------
def _mask(real: pd.DataFrame) -> np.ndarray:
    return real.notna().values


def slow_regime_switch(real: pd.DataFrame, rng: np.random.Generator,
                       p_stay: Tuple[float, float] = P_STAY_SLOW
                       ) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Line-for-line the frozen regime_switch_vol, with p_stay lengthened.

    Returns the synthetic panel and the realised regime statistics, so the run
    can verify the durations came out as specified (PreSpec section 5).
    """
    M = _mask(real)
    T, N = real.shape
    ps_lo, ps_hi = p_stay

    state = np.zeros(T, dtype=int)
    for t in range(1, T):
        u = rng.random()
        state[t] = (0 if u < ps_lo else 1) if state[t - 1] == 0 \
            else (1 if u < ps_hi else 0)

    sd = real.std(axis=0, skipna=True).values
    sd = np.where(np.isfinite(sd) & (sd > 0), sd, np.nanmedian(sd))
    B = rng.normal(0.0, 1.0, size=(N, N_FACTORS))
    scale = np.where(state == 0, 1.0, VOL_RATIO)[:, None]
    load = np.where(state == 0, 1.0, CORR_SHIFT)[:, None]
    F = rng.standard_normal((T, N_FACTORS)) * scale
    E = rng.standard_normal((T, N)) * scale
    X = (F @ B.T) * load * 0.35 + E
    X = X * sd[None, :] / np.nanstd(X, axis=0, keepdims=True)
    X = X - X.mean(axis=0, keepdims=True)
    X[~M] = np.nan

    sw = np.diff(state)
    n01 = int((sw == 1).sum())
    n10 = int((sw == -1).sum())
    lo_steps = int((state[:-1] == 0).sum())
    hi_steps = int((state[:-1] == 1).sum())
    stats = {
        "frac_high": float(state.mean()),
        "mean_run_low": lo_steps / n01 if n01 else float("nan"),
        "mean_run_high": hi_steps / n10 if n10 else float("nan"),
        "n_transitions": n01 + n10,
    }
    return pd.DataFrame(X, index=real.index, columns=real.columns), stats


# --------------------------------------------------------------------------
# Frozen statistic, with the density cache loaded rather than recomputed
# --------------------------------------------------------------------------
def load_m_cache(root: str) -> Dict[int, float]:
    with open(os.path.join(root, FROZEN_MANIFEST)) as f:
        m = json.load(f)["manifest"]
    return {int(k): float(v) for k, v in m["m_of_n_cache"].items()}


def timing_row(trig_local: np.ndarray, E: int, mcache: Dict[int, float]) -> dict:
    """Identical to the frozen runner; m(n) comes from the frozen cache."""
    n = len(trig_local)
    f = n / E if E else 0.0
    if n < 2:
        return {"n_events": n, "f": f, "timing_defined": False,
                "cv_gap": None, "modal_gap_share": None, "B": None}
    ts = timing_variation(trig_local)
    M = float(ts.modal_gap_share)
    if n not in mcache:
        return {"n_events": n, "f": f, "timing_defined": False,
                "cv_gap": float(ts.cv_gap), "modal_gap_share": M, "B": None,
                "reason": "event count absent from the frozen m(n) cache"}
    return {"n_events": n, "f": f, "timing_defined": True,
            "cv_gap": float(ts.cv_gap), "modal_gap_share": M,
            "B": M - mcache[n]}


def triggers_from(sp, gamma: float) -> np.ndarray:
    elig = np.where(sp.eligible)[0]
    fired = np.zeros(len(sp.ar), dtype=bool)
    with np.errstate(invalid="ignore"):
        fired[elig] = np.abs(sp.d_ar[elig]) > gamma * sp.sigma[elig]
    return np.where(fired[elig])[0]


def sha256(path: str) -> Optional[str]:
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 2F W-calibrated positive control")
    ap.add_argument("--raw", default=os.path.expanduser("~/rac_hrp_data/raw"))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--reps", type=int, default=N_REPS)
    ap.add_argument("--outdir", default="outputs/phase2f_control")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 78)
    print("  PHASE 2F -- W-CALIBRATED POSITIVE CONTROL")
    print("=" * 78)
    got = sha256(os.path.join(root, SPEC_FILE))
    print(f"  spec                 : {SPEC_FILE}")
    print(f"  spec SHA-256         : {got}")
    if got != SPEC_SHA:
        print(f"  *** SPEC HASH MISMATCH -- expected {SPEC_SHA}")
        return 2
    print("  spec hash            : verified")
    print("  NON-GATING. Phase 2A is CLOSED and no outcome here can reopen it.")
    print("  No performance quantity is computed.")
    print()

    P = panel.build_panels(a.raw)
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
    if (P.returns.index[eval_pos] >= pd.Timestamp(TEST_START)).any():
        raise PermissionError("Phase 2F reached the test region")

    mcache = load_m_cache(root)
    print(f"  D4 window            : W = {W}")
    print(f"  m(n) cache           : {len(mcache)} entries, loaded from the frozen manifest")
    print(f"  regime persistence   : p_stay = {P_STAY_SLOW}  "
          f"(mean runs {1/(1-P_STAY_SLOW[0]):.0f} and {1/(1-P_STAY_SLOW[1]):.0f} days, W = {W})")
    print(f"  base seed            : {BASE_SEED}")
    print()

    sp_real = structural_pass(P, cfg, eval_pos, fold_bounds, verbose=False)
    E = int(np.sum(sp_real.eligible))
    real = {g: timing_row(triggers_from(sp_real, g), E, mcache) for g in GAMMAS}
    print(f"  real: E={E}, " + ", ".join(
        f"g{g}:n={real[g]['n_events']} B={real[g]['B']:+.4f}" for g in GAMMAS))
    print()

    dev_returns = P.returns.loc[cal < pd.Timestamp(TEST_START)]
    rows: List[dict] = []
    regime_stats: List[dict] = []
    t0 = time.time()
    for rep in range(a.reps):
        rng = np.random.default_rng(rep_seed(rep))
        sub, rs = slow_regime_switch(dev_returns, rng)
        synth = sub.reindex(index=cal)
        synth[P.returns.isna()] = np.nan
        sp = structural_pass(dataclasses.replace(P, returns=synth),
                             cfg, eval_pos, fold_bounds, verbose=False)
        rows.append({"rep": rep, "gammas": {
            str(g): timing_row(triggers_from(sp, g), E, mcache) for g in GAMMAS}})
        regime_stats.append(rs)
        if (rep + 1) % 50 == 0:
            el = time.time() - t0
            print(f"    D_slow  {rep+1:4d}/{a.reps}   {el/60:5.1f} min elapsed, "
                  f"{(el/(rep+1))*(a.reps-rep-1)/60:5.1f} min remaining", flush=True)

    def q(g: float, p: float) -> float:
        v = [r["gammas"][str(g)]["B"] for r in rows
             if r["gammas"][str(g)]["timing_defined"]]
        return float(np.percentile(v, p, method="linear")) if v else float("nan")

    def pr_undef(g: float) -> float:
        u = sum(1 for r in rows if not r["gammas"][str(g)]["timing_defined"])
        return u / len(rows) if rows else float("nan")

    inside = {g: (q(g, 2.5) <= real[g]["B"] <= q(g, 97.5)) for g in GAMMAS}
    above = {g: (real[g]["B"] > q(g, 97.5)) for g in GAMMAS}
    n_in, n_above = sum(inside.values()), sum(above.values())

    if n_in >= 3:
        outcome, verdict = "C", (
            "OUTCOME C -- the control resolves and the burstiness claim survives. "
            "Real burstiness is consistent with genuine slow regime structure while "
            "remaining inconsistent with the regime-free environments A and S.")
    elif n_above >= 3:
        outcome, verdict = "X", (
            "OUTCOME X -- the control resolves and the burstiness claim does NOT "
            "survive. Real burstiness exceeds what genuine slow regime switching "
            "produces. The claim that the trigger detects regime structure is "
            "WITHDRAWN; what it detects remains unexplained by any environment tested.")
    else:
        outcome, verdict = "N", (
            "OUTCOME N -- the control still does not resolve. The Phase 2D "
            "interpretation is unavailable in either direction and the burstiness "
            "result is uninterpretable pending a redesigned control.")

    frozen_D = {0.5: (0.0454, 0.1661), 1.0: (0.1400, 0.3056),
                1.5: (0.1633, 0.4068), 2.0: (0.1052, 0.4402)}

    print()
    print("-" * 78)
    print("  gamma   real B    D_slow [2.5, 97.5]        frozen D [2.5, 97.5]    real is")
    for g in GAMMAS:
        lo, hi = q(g, 2.5), q(g, 97.5)
        flo, fhi = frozen_D[g]
        where = "INSIDE" if inside[g] else ("above" if above[g] else "below")
        print(f"  {g:5.1f}  {real[g]['B']:+.4f}   [{lo:+.4f}, {hi:+.4f}]     "
              f"[{flo:+.4f}, {fhi:+.4f}]     {where}")
    print()
    rs_arr = {k: float(np.mean([r[k] for r in regime_stats]))
              for k in ("frac_high", "mean_run_low", "mean_run_high", "n_transitions")}
    print(f"  realised regimes     : {rs_arr['frac_high']:.3f} of time in the high "
          f"state; mean runs {rs_arr['mean_run_low']:.0f} low / "
          f"{rs_arr['mean_run_high']:.0f} high days")
    print()
    print("  " + verdict)
    print("-" * 78)
    print(f"  elapsed              : {(time.time()-t0)/60:.1f} min")

    record = {
        "diagnostic": "Phase 2F W-calibrated positive control",
        "specification": f"{SPEC_FILE} (frozen, hashed)",
        "spec_sha256": SPEC_SHA,
        "gating": False,
        "phase2a_verdict_unchanged": "NO ADMISSIBLE GAMMA",
        "supersedes_frozen_mechanism_null": False,
        "base_seed": BASE_SEED, "reps": a.reps, "E": E,
        "p_stay": list(P_STAY_SLOW), "W": int(W),
        "m_of_n_cache_source": FROZEN_MANIFEST,
        "real": {str(g): real[g] for g in GAMMAS},
        "table": [{"gamma": g, "real_B": real[g]["B"],
                   "D_slow_q2.5": q(g, 2.5), "D_slow_q97.5": q(g, 97.5),
                   "D_slow_pr_undefined": pr_undef(g),
                   "frozen_D_q2.5": frozen_D[g][0], "frozen_D_q97.5": frozen_D[g][1],
                   "real_inside_D_slow": bool(inside[g])} for g in GAMMAS],
        "realised_regime_stats": rs_arr,
        "outcome": outcome, "verdict": verdict,
        "replications": rows,
        "code_sha256": {
            "run_phase2f_control.py": sha256(os.path.abspath(__file__)),
            "calibration.py": sha256(os.path.join(root, "rac_hrp/phase2/calibration.py")),
            "stats.py": sha256(os.path.join(root, "rac_hrp/phase2/stats.py")),
        },
        "environment": {"numpy": np.__version__, "pandas": pd.__version__,
                        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS", "unset")},
    }
    out = os.path.join(a.outdir, "phase2f_control.json")
    with open(out, "w") as f:
        json.dump(record, f, indent=2)
    print(f"  record written       : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
