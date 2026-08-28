"""
Phase 2E -- 2E-POWER, PARALLEL RUNNER.

Frozen specification: RAC_HRP_Phase2E_PreSpec_rev8.md
SHA-256: cfdd64cca9a23a1d873695b2de0576b442cf2b80e302602830a0d1502c403674

BIT-IDENTICAL TO THE SERIAL RUNNER BY CONSTRUCTION
    `rac_hrp.phase2.power` is imported UNMODIFIED. This script changes only the
    execution strategy: it distributes the (target, delta, condition, replication)
    tasks across processes instead of looping over them.

    Every replication draws from `default_rng(seed_for(target, delta, condition,
    r))`. That seed depends on nothing but the four coordinates, so a replication
    produces the same result regardless of when, where, or in what order it runs.
    Aggregation is by cell and the per-cell statistics are order-independent
    (a count of rejections and a median of block lengths).

    --verify runs a cell both ways and asserts equality. Run it before trusting
    any parallel result.

WHAT IS NOT PARALLELISED
    The structural pass runs once, serially, in the parent process. It is the same
    call the gate makes.

NOT A SPECIFICATION CHANGE
    rev.7 fixes seeds, counts, grids and decision rules. It says nothing about
    execution strategy, because execution strategy cannot affect a result whose
    randomness is fully determined by frozen seeds. This script is nonetheless
    recorded as an implementation deviation, following the precedent of
    RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md.

ENVIRONMENT
    Set OPENBLAS_NUM_THREADS=1. Each worker is single-threaded; letting BLAS
    oversubscribe across 96 processes degrades throughput badly and, more
    importantly, the project standard fixes it at 1.

    numpy and pandas versions must match the frozen environment (numpy 1.26.4,
    pandas 2.2.2). The script prints them and refuses to run on a mismatch unless
    --allow-env-drift is passed, in which case the drift is recorded in the result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from multiprocessing import Pool, cpu_count

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.phase2 import power as PW                               # noqa: E402
from run_phase2e_power import build_structural, _sha256              # noqa: E402

SPEC_FILE = "RAC_HRP_Phase2E_PreSpec_rev8.md"
SPEC_SHA = "cfdd64cca9a23a1d873695b2de0576b442cf2b80e302602830a0d1502c403674"
FROZEN_NUMPY = "1.26.4"
FROZEN_PANDAS = "2.2.2"

_INP: PW.PowerInputs | None = None


def _init(inp: PW.PowerInputs) -> None:
    global _INP
    _INP = inp


def _task(args):
    """One replication. Identical to the serial path."""
    target, delta, condition, r = args
    rej, L = PW._one_replication(_INP, target, delta, condition, r)
    return (target, delta, condition, int(rej), L)


def _tasks(n_rep: int):
    yield from ((PW.GAMMA_CANDIDATES[0], 0.0, "R", r) for r in range(n_rep))
    for target in PW.GAMMA_CANDIDATES:
        for condition in PW.CONDITIONS:
            for delta in PW.DELTA_GRID:
                for r in range(n_rep):
                    yield (target, delta, condition, r)


def _aggregate(rows, n_rep: int) -> PW.PowerResult:
    from collections import defaultdict
    hits = defaultdict(int)
    blocks = defaultdict(list)
    for target, delta, condition, rej, L in rows:
        hits[(target, delta, condition)] += rej
        blocks[(target, delta, condition)].append(L)

    res = PW.PowerResult(n_replications=n_rep)

    def mk(key) -> PW.PowerCell:
        t, d, c = key
        p = hits[key] / n_rep
        return PW.PowerCell(t, d, c, n_rep, p,
                            float(np.sqrt(p * (1 - p) / n_rep)),
                            int(np.median(blocks[key])))

    size_key = (PW.GAMMA_CANDIDATES[0], 0.0, "R")
    res.size_cell = mk(size_key)

    for target in PW.GAMMA_CANDIDATES:
        for condition in PW.CONDITIONS:
            for delta in PW.DELTA_GRID:
                res.cells.append(mk((target, delta, condition)))

    for target in PW.GAMMA_CANDIDATES:
        for condition in PW.CONDITIONS:
            row = sorted((c for c in res.cells
                          if c.target == target and c.condition == condition),
                         key=lambda c: c.delta)
            hit = next((c for c in row if c.power >= PW.POWER_TARGET), None)
            if hit is None:
                res.mde80[(target, condition)] = f"> {PW.DELTA_GRID[-1]}"
            else:
                i = row.index(hit)
                lo = row[i - 1].delta if i else 0.0
                res.mde80[(target, condition)] = f"({lo}, {hit.delta}]"
    return res


def verify(inp: PW.PowerInputs, n: int, workers: int) -> bool:
    """Run one cell serially and in parallel; require identical results."""
    target, delta, condition = PW.GAMMA_CANDIDATES[-1], PW.DELTA_GRID[3], "R"
    print(f"  verifying g={target} d={delta} {condition} at {n} replications ...")

    serial = [PW._one_replication(inp, target, delta, condition, r)
              for r in range(n)]
    with Pool(workers, initializer=_init, initargs=(inp,)) as pool:
        par = pool.map(_task, [(target, delta, condition, r) for r in range(n)])

    ok = True
    for r, ((s_rej, s_L), (_, _, _, p_rej, p_L)) in enumerate(zip(serial, par)):
        if int(s_rej) != p_rej or s_L != p_L:
            print(f"    MISMATCH at r={r}: serial ({int(s_rej)}, {s_L}) "
                  f"parallel ({p_rej}, {p_L})")
            ok = False
    print("    identical" if ok else "    NOT IDENTICAL -- do not use the parallel runner")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="2E-POWER, parallel (non-gating)")
    ap.add_argument("--raw", default=os.path.expanduser("~/rac_hrp_data/raw"))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--outdir", default="outputs/phase2e_power")
    ap.add_argument("--workers", type=int, default=max(1, cpu_count() - 2))
    ap.add_argument("--chunk", type=int, default=64)
    ap.add_argument("--verify", type=int, default=0, metavar="N",
                    help="run N replications of one cell both ways and exit")
    ap.add_argument("--allow-env-drift", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    print("=" * 78)
    print("  2E-POWER -- planted-effect power curve   [PARALLEL RUNNER]")
    print("=" * 78)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    got = _sha256(os.path.join(root, SPEC_FILE))
    print(f"  spec SHA-256         : {got}")
    if got != SPEC_SHA:
        print(f"  *** SPEC HASH MISMATCH -- expected {SPEC_SHA}")
        return 2
    print("  spec hash            : verified")

    drift = (np.__version__ != FROZEN_NUMPY) or (pd.__version__ != FROZEN_PANDAS)
    print(f"  numpy / pandas       : {np.__version__} / {pd.__version__} "
          f"(frozen: {FROZEN_NUMPY} / {FROZEN_PANDAS})")
    if drift:
        if not a.allow_env_drift:
            print("  *** ENVIRONMENT DRIFT. The frozen gate was run on the versions above.")
            print("  *** Pin them, or re-run with --allow-env-drift to record the drift.")
            return 5
        print("  *** running with recorded environment drift")

    threads = os.environ.get("OPENBLAS_NUM_THREADS", "unset")
    print(f"  threads per worker   : OPENBLAS_NUM_THREADS={threads}")
    if threads != "1":
        print("  *** set OPENBLAS_NUM_THREADS=1; oversubscription across workers")
        print("  *** wastes cores and departs from the project standard. Aborting.")
        return 6
    print(f"  workers              : {a.workers} of {cpu_count()} cores")
    print("  NON-GATING. The Phase 2A verdict stands regardless of this result.")
    print()

    sp, cfg, dates = build_structural(a.raw, a.n)
    try:
        inp = PW.build_inputs(sp)
    except PW.PowerAbort as e:
        print(f"\n  *** ABORTED -- {e}")
        return 3
    print(f"  base path            : E = {inp.E}, VI median {inp.base_median:.4f}, "
          f"block-resampled per replication at L = {inp.block_length}")
    print(f"  event counts         : "
          + ", ".join(f"g={g}:{inp.n_events[g]}" for g in PW.GAMMA_CANDIDATES))
    print()

    if a.verify:
        return 0 if verify(inp, a.verify, a.workers) else 7

    n_rep = PW.N_REPLICATIONS_DEFAULT
    total = n_rep * (len(PW.GAMMA_CANDIDATES) * len(PW.DELTA_GRID)
                     * len(PW.CONDITIONS) + 1)
    print(f"  tasks                : {total:,} replications")
    print("-" * 78)

    t0 = time.time()
    rows = []
    with Pool(a.workers, initializer=_init, initargs=(inp,)) as pool:
        for i, row in enumerate(pool.imap_unordered(_task, _tasks(n_rep),
                                                    chunksize=a.chunk), 1):
            rows.append(row)
            if i % 5000 == 0 or i == total:
                el = time.time() - t0
                print(f"    {i:,}/{total:,}  {el/60:.1f} min elapsed, "
                      f"{(el/i)*(total-i)/60:.1f} min remaining")
    elapsed = time.time() - t0

    res = _aggregate(rows, n_rep)
    res.base_median = inp.base_median

    lo, hi = PW.SIZE_BAND
    if not (lo <= res.size_cell.power <= hi):
        print(f"\n  *** ABORTED -- delta=0 rejection rate {res.size_cell.power:.4f} "
              f"falls outside the frozen pass band [{lo}, {hi}]")
        return 3

    print()
    print("-" * 78)
    print(PW.format_report(res))
    print("-" * 78)
    print(f"  elapsed              : {elapsed/60:.1f} min "
          f"({a.workers} workers)")

    record = {
        "diagnostic": "2E-POWER",
        "runner": "parallel; bit-identical to the serial runner by construction",
        "specification": f"{SPEC_FILE} (frozen, hashed)",
        "spec_sha256": SPEC_SHA,
        "gating": False,
        "phase2a_verdict_unchanged": "NO ADMISSIBLE GAMMA",
        "n_replications": res.n_replications,
        "bootstrap_replicates": PW.BOOTSTRAP_REPLICATES,
        "alpha": PW.ALPHA,
        "base_seed": PW.BASE_SEED,
        "delta_grid": list(PW.DELTA_GRID),
        "base_path": "per-replication circular block resample of the observed one-step VI at the 233 eligible rebalances",
        "base_median": res.base_median,
        "mde_is_conditional_on_observed_dependence_realisation": True,
        "power_r_minus_u_includes_block_length_response": True,
        "empirical_size_on_observed_dependence": asdict(res.size_cell),
        "published_iid_size_not_comparable": 0.0660,
        "cells": [asdict(c) for c in res.cells],
        "mde80": {f"gamma={g}|{c}": v for (g, c), v in res.mde80.items()},
        "elapsed_minutes": round(elapsed / 60.0, 2),
        "workers": a.workers,
        "environment": {"numpy": np.__version__, "pandas": pd.__version__,
                        "frozen_numpy": FROZEN_NUMPY, "frozen_pandas": FROZEN_PANDAS,
                        "drift": bool(drift),
                        "openblas_num_threads": threads},
        "code_sha256": {
            "power.py": _sha256(os.path.join(root, "rac_hrp/phase2/power.py")),
            "calibration.py": _sha256(os.path.join(root, "rac_hrp/phase2/calibration.py")),
            "stats.py": _sha256(os.path.join(root, "rac_hrp/phase2/stats.py")),
        },
    }
    out = os.path.join(a.outdir, "power_result.json")
    with open(out, "w") as f:
        json.dump(record, f, indent=2)
    print(f"  record written       : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
