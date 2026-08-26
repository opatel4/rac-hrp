"""
Phase 2A POST-MORTEM -- pipeline-level structureless null (mechanism diagnostic).

Executes the countersigned pre-specification
    RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md (rev.4)

BINDING CONSTRAINT (pre-spec section 0)
    This experiment diagnoses the mechanism behind the already-observed Phase 2A
    failure. No outcome can reopen Phase 2A, change a frozen threshold, select a
    new gamma, or authorize performance evaluation.

NO PERFORMANCE IS COMPUTED. The engine's return path and the risk-free series are
never touched. Only timing-side statistics are produced.

IMPLEMENTATION-SAFETY DEVIATION FROM THE PRE-SPEC (no statistic changes)
    The pre-spec said environment S would be registered in
    rac_hrp.nulls.environments.ENVIRONMENTS. It is NOT, and must not be:
      * gate.py:220  ->  envs = environments or list(ENVIRONMENTS.keys())
                         (a fifth key silently enrols S in the frozen Phase 0.5 gate)
      * condition2_static_vs_erc.py:102 and diagnostic_static_vs_erc.py:69
                     ->  list(ENVIRONMENTS.keys()).index(ENV)
                         (seed derivation by dict position)
      * gate_v2_config.py:89 ENVIRONMENT_ORDER is a parallel tuple that must agree
    S is therefore dispatched DIRECTLY here; A and D go through the unmodified
    draw(). Nothing in rac_hrp/nulls/ is edited. Likewise fit_rows is applied by
    restricting the returns handed to each generator, not by adding a kwarg to the
    shared draw().

Run:
    OPENBLAS_NUM_THREADS=1 python scripts/run_mechanism_null.py --raw ~/rac_hrp_data/raw
"""
from __future__ import annotations

import argparse, dataclasses, hashlib, json, os, platform, sys, time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import (Config, TEST_START, select_cov_window,
                            SAMPLE_START, DEV_END)                    # noqa: E402
from rac_hrp.data import panel                                        # noqa: E402
from rac_hrp.data.universe import UniverseBuilder, realized_n_report   # noqa: E402
from rac_hrp.backtest.folds import FoldGenerator                      # noqa: E402
from rac_hrp.nulls.environments import draw                           # noqa: E402  (UNMODIFIED)
from rac_hrp.phase2.calibration import structural_pass                # noqa: E402  (UNMODIFIED)
from rac_hrp.phase2.config import Phase2Config                        # noqa: E402
from rac_hrp.phase2.stats import timing_variation                     # noqa: E402  (FROZEN)
from rac_hrp.nulls.environments_static import static_corr             # noqa: E402  (S, separate module)

# ---- frozen pre-spec parameters -------------------------------------------
MECH_SEED_BASE = 20260822
N_REPS = 500
PLACEMENT_DRAWS = 10_000
ENV_INDEX = {"A_iid_gaussian": 0, "S_static_corr": 1, "D_regime_switch_vol": 2}
GAMMAS = (0.5, 1.0, 1.5, 2.0)


def env_seed(env: str, rep: int) -> int:
    return MECH_SEED_BASE + 1000 * ENV_INDEX[env] + rep


# ---- deterministic density lookup m(n) ------------------------------------
_M_CACHE: Dict[int, float] = {}


def m_of_n(n: int, E: int) -> float:
    """median( modal_gap_share | n events among E ), deterministic and cached.

    Keyed on n alone: two replications with the same event count receive the
    IDENTICAL density correction, and the real data uses this same lookup.
    """
    if n < 2:
        return float("nan")
    if n in _M_CACHE:
        return _M_CACHE[n]
    rng = np.random.default_rng(MECH_SEED_BASE + 500_000 + n)
    vals = np.empty(PLACEMENT_DRAWS)
    for b in range(PLACEMENT_DRAWS):
        idx = np.sort(rng.choice(E, size=n, replace=False))
        vals[b] = timing_variation(idx).modal_gap_share
    _M_CACHE[n] = float(np.median(vals))
    return _M_CACHE[n]


def timing_row(trig_local: np.ndarray, E: int) -> dict:
    """f, CV, M, B for one (replication, gamma). NA when n < 2 (pre-spec FIX 5)."""
    n = len(trig_local)
    f = n / E if E else 0.0
    if n < 2:
        return {"n_events": n, "f": f, "timing_defined": False,
                "cv_gap": None, "modal_gap_share": None, "B": None}
    ts = timing_variation(trig_local)
    M = float(ts.modal_gap_share)
    return {"n_events": n, "f": f, "timing_defined": True,
            "cv_gap": float(ts.cv_gap), "modal_gap_share": M,
            "B": M - m_of_n(n, E)}


def triggers_from(sp, gamma: float) -> np.ndarray:
    """Identical trigger rule to calibration.evaluate_candidate (line 212)."""
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--reps", type=int, default=N_REPS)
    ap.add_argument("--outdir", default="outputs/phase2_mechanism")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    print("=" * 78)
    print("  PHASE 2A POST-MORTEM -- PIPELINE-LEVEL STRUCTURELESS NULL")
    print("=" * 78)
    print("  Phase 2A is CLOSED. No outcome here can reopen it.")
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
    dates = P.returns.index[eval_pos]
    if (dates >= pd.Timestamp(TEST_START)).any():
        raise PermissionError("mechanism diagnostic reached the test region")

    # Development-region row mask: every environment fits on these rows ONLY.
    fit_rows = np.asarray(cal < pd.Timestamp(TEST_START))
    print(f"  D4 window W={W}   dev span {len(eval_pos):,}d, {len(folds)} folds")
    print(f"  fit rows (dev only): {int(fit_rows.sum()):,} / {len(cal):,}")

    # ---- real-data reference (frozen gate trigger sets) --------------------
    sp_real = structural_pass(P, cfg, eval_pos, fold_bounds, verbose=False)
    E = int(np.sum(sp_real.eligible))
    real = {g: timing_row(triggers_from(sp_real, g), E) for g in GAMMAS}
    print(f"  real: E={E}, " + ", ".join(
        f"g{g}:n={real[g]['n_events']} B={real[g]['B']:+.4f}" for g in GAMMAS))
    print()

    # ---- null replications -------------------------------------------------
    dev_returns = P.returns.loc[cal < pd.Timestamp(TEST_START)]
    results: Dict[str, List[dict]] = {e: [] for e in ENV_INDEX}
    t_start = time.time()
    for env in ENV_INDEX:
        for rep in range(a.reps):
            rng = np.random.default_rng(env_seed(env, rep))
            if env == "S_static_corr":
                synth = static_corr(P.returns, rng, fit_rows=fit_rows)
            else:
                # A and D fit their vol targets on dev rows; emit full length by
                # generating on the dev slice then reindexing onto the calendar.
                sub, _ = draw(env, dev_returns, rng)
                synth = sub.reindex(index=cal)
                synth[P.returns.isna()] = np.nan
            sp = structural_pass(dataclasses.replace(P, returns=synth),
                                 cfg, eval_pos, fold_bounds, verbose=False)
            row = {"rep": rep, "gammas": {
                str(g): timing_row(triggers_from(sp, g), E) for g in GAMMAS}}
            results[env].append(row)
            if (rep + 1) % 50 == 0:
                el = time.time() - t_start
                print(f"    {env:<22} {rep+1:4d}/{a.reps}   {el/60:5.1f} min")
    print()

    # ---- decision rule, applied mechanically -------------------------------
    def q(env: str, g: float, p: float) -> float:
        v = [r["gammas"][str(g)]["B"] for r in results[env]
             if r["gammas"][str(g)]["timing_defined"]]
        return float(np.percentile(v, p, method="linear")) if v else float("nan")

    def pr_undef(env: str, g: float) -> float:
        n = len(results[env])
        u = sum(1 for r in results[env] if not r["gammas"][str(g)]["timing_defined"])
        return u / n if n else float("nan")

    table = []
    for g in GAMMAS:
        row = {"gamma": g, "real_B": real[g]["B"], "real_n": real[g]["n_events"]}
        for env in ENV_INDEX:
            row[f"{env}_q2.5"] = q(env, g, 2.5)
            row[f"{env}_q97.5"] = q(env, g, 97.5)
            row[f"{env}_pr_undefined"] = pr_undef(env, g)
        table.append(row)

    S, A_, D_ = "S_static_corr", "A_iid_gaussian", "D_regime_switch_vol"
    o1 = all(q(S, g, 2.5) <= real[g]["B"] <= q(S, g, 97.5) for g in GAMMAS)
    o1_strong = o1 and all(q(A_, g, 2.5) <= real[g]["B"] <= q(A_, g, 97.5)
                           for g in GAMMAS)
    o2 = all(real[g]["B"] > q(A_, g, 97.5) and real[g]["B"] > q(S, g, 97.5)
             for g in GAMMAS)
    o2_d = o2 and all(q(D_, g, 2.5) <= real[g]["B"] <= q(D_, g, 97.5)
                      for g in GAMMAS)
    outcome = ("1_architectural" if o1 else
               "2_beyond_regime_free_mechanics" if o2 else "3_mixed")

    print("-" * 78)
    print("  FOUR-GAMMA TABLE (reported regardless of classification)")
    print("-" * 78)
    print(pd.DataFrame(table).to_string(index=False))
    print()
    print(f"  => OUTCOME {outcome}")
    if outcome == "1_architectural":
        print("     Comparable burstiness does not REQUIRE regime changes and")
        print("     cannot be uniquely attributed to them.")
        if o1_strong:
            print("     STRENGTHENED: arises even without cross-asset correlation.")
    elif outcome == "2_beyond_regime_free_mechanics":
        print("     Observed burstiness exceeds regime-free pipeline mechanics")
        print("     under both A and S at all four gamma.")
        if o2_d:
            print("     D overlaps: CONSISTENT WITH designed nonstationarity")
            print("     (consistent with, not proof of, real regimes).")
    else:
        print("     No uniform mechanism classification across the four frozen")
        print("     gamma values. Pattern reported; no proportion is implied.")
    print()
    print("  PHASE 2A REMAINS CLOSED under every outcome (D_VI failed independently).")

    manifest = {
        "prespec": "RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md rev.4 (countersigned)",
        "phase2a_status": "CLOSED - no outcome here can reopen it",
        "seed_base": MECH_SEED_BASE, "reps_per_env": a.reps,
        "placement_draws": PLACEMENT_DRAWS, "E": E, "gammas": list(GAMMAS),
        "env_index": ENV_INDEX,
        "quantile_method": "numpy.percentile method='linear', timing_defined only",
        "fit_sample": "development-region rows only (dates < TEST_START)",
        "d_nanstd_scope": "FULL generated panel (registered implementation; "
                          "vol TARGET is dev-region fitted)",
        "s_registration": "NOT registered in ENVIRONMENTS; dispatched directly. "
                          "Registration would perturb gate.py:220 env list and "
                          "the .index()-based seed derivations in "
                          "condition2/diagnostic_static_vs_erc.py",
        "active_universe_note": "Sigma_0 is time-invariant over the FULL universe; "
                                "the allocator sees a submatrix at each date because "
                                "the real NaN/membership mask is preserved. S is a "
                                "time-invariant full-universe covariance process with "
                                "the real point-in-time availability path preserved.",
        "code_hashes": {f: sha256(f) for f in [
            "rac_hrp/phase2/calibration.py", "rac_hrp/phase2/stats.py",
            "rac_hrp/nulls/environments.py", "rac_hrp/nulls/environments_static.py",
            "scripts/run_mechanism_null.py"]},
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__,
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        "m_of_n_cache": {str(k): v for k, v in sorted(_M_CACHE.items())},
        "real": {str(g): real[g] for g in GAMMAS},
        "table": table, "outcome": outcome,
        "outcome_1_strengthened": bool(o1_strong),
        "outcome_2_d_overlap": bool(o2_d),
        "runtime_min": round((time.time() - t_start) / 60, 1),
    }
    out = os.path.join(a.outdir, "mechanism_null.json")
    with open(out, "w") as fh:
        json.dump({"manifest": manifest, "replications": results}, fh, indent=2)
    print(f"\n  record : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
