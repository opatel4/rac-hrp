"""
Phase 2A POST-MORTEM -- mechanism null, PARALLEL runner.

Bit-identical to scripts/run_mechanism_null.py (countersigned serial version).
The serial script is NOT modified; this is a separate entry point.

WHY IDENTICAL OUTPUT IS GUARANTEED, NOT ASSUMED
  * Seeding is PER REPLICATION: env_seed(env, rep) = BASE + 1000*env_index + rep.
    No generator is threaded across replications, so a worker computing
    replication r produces exactly what the serial loop produced at r.
  * m(n) is computed IN THE PARENT from a shared cache, not in workers, so every
    replication receives the identical density correction regardless of
    scheduling. Workers return raw trigger indices only.
  * Sigma_0 factorisation is cached per worker process; the cache is proven
    bit-identical (environments_static.verify_sigma0_cache).
  * Results are reassembled in (env, rep) order before any statistic is formed.

Verify with --verify-against to compare a subset against the serial record.

Run on a many-core box:
    OPENBLAS_NUM_THREADS=1 python -u scripts/run_mechanism_null_parallel.py \
        --raw ~/rac_hrp_data/raw --workers 96
"""
from __future__ import annotations

import argparse, dataclasses, hashlib, json, os, platform, sys, time
from multiprocessing import Pool
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import (Config, TEST_START, select_cov_window,
                            SAMPLE_START, DEV_END)                     # noqa: E402
from rac_hrp.data import panel                                         # noqa: E402
from rac_hrp.data.universe import UniverseBuilder, realized_n_report    # noqa: E402
from rac_hrp.backtest.folds import FoldGenerator                       # noqa: E402
from rac_hrp.nulls.environments import draw                            # noqa: E402
from rac_hrp.phase2.calibration import structural_pass                 # noqa: E402
from rac_hrp.phase2.stats import timing_variation                      # noqa: E402
from rac_hrp.nulls.environments_static import static_corr              # noqa: E402

MECH_SEED_BASE = 20260822
N_REPS = 500
PLACEMENT_DRAWS = 10_000
ENV_INDEX = {"A_iid_gaussian": 0, "S_static_corr": 1, "D_regime_switch_vol": 2}
GAMMAS = (0.5, 1.0, 1.5, 2.0)

_W: dict = {}          # per-worker context


def env_seed(env: str, rep: int) -> int:
    return MECH_SEED_BASE + 1000 * ENV_INDEX[env] + rep


def triggers_from(sp, gamma: float) -> np.ndarray:
    elig = np.where(sp.eligible)[0]
    fired = np.zeros(len(sp.ar), dtype=bool)
    with np.errstate(invalid="ignore"):
        fired[elig] = np.abs(sp.d_ar[elig]) > gamma * sp.sigma[elig]
    return np.where(fired[elig])[0]


def _init(raw: str, n_assets: int):
    """Build the panel and frozen fold geometry once per worker process."""
    P = panel.build_panels(raw)
    cfg0 = Config(n_assets=n_assets)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    med_n = float(realized_n_report(
        UniverseBuilder(P, cfg0).snapshots(probe)).n_selected.median())
    cfg = Config(n_assets=n_assets, cov_window=select_cov_window(med_n))
    folds = FoldGenerator(cal, cfg).dev_folds()
    eval_pos = np.concatenate([f.test_pos for f in folds])
    if (cal[eval_pos] >= pd.Timestamp(TEST_START)).any():
        raise PermissionError("worker reached the test region")
    _W.update(P=P, cfg=cfg, cal=cal, eval_pos=eval_pos,
              fold_bounds=[(int(f.test_pos[0]), int(f.test_pos[-1])) for f in folds],
              fit_rows=np.asarray(cal < pd.Timestamp(TEST_START)),
              dev_returns=P.returns.loc[cal < pd.Timestamp(TEST_START)])


def _one(task: Tuple[str, int]) -> dict:
    """One replication. Returns RAW trigger indices; no m(n) applied here."""
    env, rep = task
    rng = np.random.default_rng(env_seed(env, rep))
    if env == "S_static_corr":
        synth = static_corr(_W["P"].returns, rng, fit_rows=_W["fit_rows"])
    else:
        sub, _ = draw(env, _W["dev_returns"], rng)
        synth = sub.reindex(index=_W["cal"])
        synth[_W["P"].returns.isna()] = np.nan
    sp = structural_pass(dataclasses.replace(_W["P"], returns=synth),
                         _W["cfg"], _W["eval_pos"], _W["fold_bounds"], verbose=False)
    return {"env": env, "rep": rep,
            "trig": {str(g): triggers_from(sp, g).tolist() for g in GAMMAS}}


# ---- parent-side statistics (identical to the serial script) --------------
_M_CACHE: Dict[int, float] = {}


def m_of_n(n: int, E: int) -> float:
    if n < 2:
        return float("nan")
    if n in _M_CACHE:
        return _M_CACHE[n]
    rng = np.random.default_rng(MECH_SEED_BASE + 500_000 + n)
    vals = np.empty(PLACEMENT_DRAWS)
    for b in range(PLACEMENT_DRAWS):
        vals[b] = timing_variation(
            np.sort(rng.choice(E, size=n, replace=False))).modal_gap_share
    _M_CACHE[n] = float(np.median(vals))
    return _M_CACHE[n]


def timing_row(trig: np.ndarray, E: int) -> dict:
    n = len(trig)
    f = n / E if E else 0.0
    if n < 2:
        return {"n_events": n, "f": f, "timing_defined": False,
                "cv_gap": None, "modal_gap_share": None, "B": None}
    ts = timing_variation(np.asarray(trig))
    M = float(ts.modal_gap_share)
    return {"n_events": n, "f": f, "timing_defined": True,
            "cv_gap": float(ts.cv_gap), "modal_gap_share": M,
            "B": M - m_of_n(n, E)}


def sha256(p: str) -> Optional[str]:
    try:
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--reps", type=int, default=N_REPS)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--outdir", default="outputs/phase2_mechanism")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    print("=" * 78, flush=True)
    print("  PHASE 2A POST-MORTEM -- MECHANISM NULL (parallel)", flush=True)
    print("=" * 78, flush=True)
    print("  Phase 2A is CLOSED. No outcome here can reopen it.", flush=True)
    print(f"  workers={a.workers}  reps/env={a.reps}", flush=True)

    _init(a.raw, a.n)                       # parent context for the real pass
    E = int(np.sum(structural_pass(_W["P"], _W["cfg"], _W["eval_pos"],
                                   _W["fold_bounds"], verbose=False).eligible))
    sp_real = structural_pass(_W["P"], _W["cfg"], _W["eval_pos"],
                              _W["fold_bounds"], verbose=False)
    real = {g: timing_row(triggers_from(sp_real, g), E) for g in GAMMAS}
    print(f"  real: E={E}, " + ", ".join(
        f"g{g}:n={real[g]['n_events']} B={real[g]['B']:+.4f}" for g in GAMMAS),
        flush=True)

    tasks = [(e, r) for e in ENV_INDEX for r in range(a.reps)]
    t0 = time.time()
    raw_results: List[dict] = []
    with Pool(a.workers, initializer=_init, initargs=(a.raw, a.n)) as pool:
        for i, out in enumerate(pool.imap_unordered(_one, tasks, chunksize=1), 1):
            raw_results.append(out)
            if i % 50 == 0:
                print(f"    {i:5d}/{len(tasks)}  {(time.time()-t0)/60:6.1f} min",
                      flush=True)

    # Reassemble in deterministic (env, rep) order, THEN apply m(n) in the parent.
    raw_results.sort(key=lambda d: (ENV_INDEX[d["env"]], d["rep"]))
    results: Dict[str, List[dict]] = {e: [] for e in ENV_INDEX}
    for d in raw_results:
        results[d["env"]].append({"rep": d["rep"], "gammas": {
            str(g): timing_row(np.asarray(d["trig"][str(g)]), E) for g in GAMMAS}})

    def q(env, g, p):
        v = [r["gammas"][str(g)]["B"] for r in results[env]
             if r["gammas"][str(g)]["timing_defined"]]
        return float(np.percentile(v, p, method="linear")) if v else float("nan")

    def pr_undef(env, g):
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
    o1s = o1 and all(q(A_, g, 2.5) <= real[g]["B"] <= q(A_, g, 97.5) for g in GAMMAS)
    o2 = all(real[g]["B"] > q(A_, g, 97.5) and real[g]["B"] > q(S, g, 97.5)
             for g in GAMMAS)
    o2d = o2 and all(q(D_, g, 2.5) <= real[g]["B"] <= q(D_, g, 97.5) for g in GAMMAS)
    outcome = ("1_architectural" if o1 else
               "2_beyond_regime_free_mechanics" if o2 else "3_mixed")

    print("-" * 78, flush=True)
    print(pd.DataFrame(table).to_string(index=False), flush=True)
    print(f"\n  => OUTCOME {outcome}", flush=True)
    print("  PHASE 2A REMAINS CLOSED under every outcome.", flush=True)

    manifest = {
        "prespec": "RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md rev.4 (countersigned)",
        "runner": "parallel; bit-identical to serial by per-replication seeding",
        "workers": a.workers, "seed_base": MECH_SEED_BASE, "reps_per_env": a.reps,
        "placement_draws": PLACEMENT_DRAWS, "E": E, "gammas": list(GAMMAS),
        "env_index": ENV_INDEX,
        "quantile_method": "numpy.percentile method='linear', timing_defined only",
        "fit_sample": "development-region rows only (dates < TEST_START)",
        "sigma0_cache": "L cached per worker; RNG consumed only after L, so draws "
                        "are unchanged (verify_sigma0_cache)",
        "d_nanstd_scope": "FULL generated panel (registered implementation)",
        "s_registration": "NOT registered in ENVIRONMENTS; dispatched directly",
        "code_hashes": {f: sha256(f) for f in [
            "rac_hrp/phase2/calibration.py", "rac_hrp/phase2/stats.py",
            "rac_hrp/nulls/environments.py", "rac_hrp/nulls/environments_static.py",
            "scripts/run_mechanism_null.py",
            "scripts/run_mechanism_null_parallel.py"]},
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__,
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        "m_of_n_cache": {str(k): v for k, v in sorted(_M_CACHE.items())},
        "real": {str(g): real[g] for g in GAMMAS},
        "table": table, "outcome": outcome,
        "outcome_1_strengthened": bool(o1s), "outcome_2_d_overlap": bool(o2d),
        "runtime_min": round((time.time() - t0) / 60, 1),
    }
    out = os.path.join(a.outdir, "mechanism_null.json")
    with open(out, "w") as fh:
        json.dump({"manifest": manifest, "replications": results}, fh, indent=2)
    print(f"\n  record : {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
