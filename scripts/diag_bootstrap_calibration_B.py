"""
ONE-OFF DIAGNOSTIC -- bootstrap null-calibration as a function of B.

NOT a test. Not part of any suite. Produces no result that gates anything.

MOTIVATION
    The Phase 2 stats self-test runs the null calibration at B_boot = 600 (a
    tractable count for a suite) while the FROZEN PRODUCTION spec uses
    B_boot = 10,000. At 2,000 null datasets the measured rejection rate was

        P(p <= 0.05) = 0.066,  MC SE 0.0055,  ~95% CI [0.055, 0.077]

    i.e. mildly anti-conservative and now statistically distinguishable from the
    nominal 0.05 (at 200 datasets it was not). The open question is whether this
    is a finite-B artefact that shrinks at the production replicate count.

DESIGN
    Sweep B_boot over {600, 2000, 10000} holding EVERYTHING else identical to the
    self-test: same null-dataset seeds (default_rng(1000 + s)), same fixed
    bootstrap seed, same firing rate, same E. Only B changes, so any trend is
    attributable to B alone.

    Secondary arm: at the largest B, repeat with a PER-DATASET bootstrap seed
    (20260817 + 2000 + s) instead of the fixed one. The self-test holds the
    bootstrap seed constant across datasets, so resampled indices are identical
    while data varies; the p-values are therefore not fully independent draws and
    the binomial MC SE may understate true uncertainty. This arm quantifies that.

INTERPRETATION IS DEFERRED. No tolerance is changed on the basis of this run;
the self-test tolerance stays at +/- 0.02 pending review.
"""
from __future__ import annotations

import argparse, json, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rac_hrp.phase2.stats import circular_block_bootstrap_p      # noqa: E402

FIRING = 0.48          # matches the self-test
BOOT_SEED = 20260817 + 2000


def calibrate(n_datasets: int, replicates: int, E: int,
              vary_seed: bool = False) -> dict:
    ps = []
    for s in range(n_datasets):
        rng = np.random.default_rng(1000 + s)          # identical to self-test
        vi = rng.standard_normal(E)
        fired = rng.random(E) < FIRING
        seed = BOOT_SEED + s if vary_seed else BOOT_SEED
        r = circular_block_bootstrap_p(vi, fired, seed=seed, replicates=replicates)
        if np.isfinite(r.p_value):
            ps.append(r.p_value)
    ps = np.array(ps)
    n = len(ps)
    rate = float(np.mean(ps <= 0.05))
    se = float(np.sqrt(rate * (1 - rate) / n)) if n else float("nan")
    return {"replicates": replicates, "n_datasets": n_datasets,
            "n_finite": n, "vary_seed": vary_seed,
            "rate": round(rate, 5), "mc_se": round(se, 5),
            "ci95": [round(rate - 1.96 * se, 5), round(rate + 1.96 * se, 5)],
            "excludes_nominal_0.05": not (rate - 1.96 * se <= 0.05 <= rate + 1.96 * se),
            "rate_at_0.10": round(float(np.mean(ps <= 0.10)), 5),
            "rate_at_0.01": round(float(np.mean(ps <= 0.01)), 5),
            "median_p": round(float(np.median(ps)), 5)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", type=int, default=2000)
    ap.add_argument("--E", type=int, default=233,
                    help="MUST match the E used in tests/test_phase2_stats.py")
    ap.add_argument("--B", default="600,2000,10000")
    ap.add_argument("--outdir", default="outputs/phase2_diagnostics")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    Bs = [int(x) for x in a.B.split(",")]

    print("=" * 74)
    print("  BOOTSTRAP NULL CALIBRATION vs B_boot  (one-off diagnostic)")
    print("=" * 74)
    print(f"  datasets={a.datasets}  E={a.E}  firing={FIRING}  "
          f"boot seed={BOOT_SEED} (fixed)")
    print(f"  nominal level 0.05; production B_boot = 10,000")
    print()

    rows = []
    t0 = time.time()
    for B in Bs:
        t = time.time()
        r = calibrate(a.datasets, B, a.E)
        r["secs"] = round(time.time() - t, 1)
        rows.append(r)
        flag = "  <-- excludes 0.05" if r["excludes_nominal_0.05"] else ""
        print(f"  B={B:>6}  rate={r['rate']:.4f}  SE={r['mc_se']:.4f}  "
              f"CI95=[{r['ci95'][0]:.4f},{r['ci95'][1]:.4f}]  "
              f"({r['secs']:.0f}s){flag}", flush=True)

    print()
    print("  secondary arm: per-dataset bootstrap seed at largest B")
    rv = calibrate(a.datasets, max(Bs), a.E, vary_seed=True)
    rv["secs"] = None
    print(f"  B={max(Bs):>6}  rate={rv['rate']:.4f}  SE={rv['mc_se']:.4f}  "
          f"CI95=[{rv['ci95'][0]:.4f},{rv['ci95'][1]:.4f}]  (varying seed)")
    print()
    fixed_max = [r for r in rows if r["replicates"] == max(Bs)][0]
    print(f"  fixed-seed vs varying-seed at B={max(Bs)}: "
          f"{fixed_max['rate']:.4f} vs {rv['rate']:.4f} "
          f"(diff {rv['rate'] - fixed_max['rate']:+.4f})")
    print()
    print("  NOTE: interpretation deferred. No tolerance changed on this basis.")

    rec = {"purpose": "one-off; diagnoses B-dependence of bootstrap null calibration",
           "gates_nothing": True, "nominal": 0.05, "E": a.E, "firing": FIRING,
           "boot_seed_fixed": BOOT_SEED, "datasets": a.datasets,
           "sweep": rows, "varying_seed_arm": rv,
           "total_min": round((time.time() - t0) / 60, 1)}
    out = os.path.join(a.outdir, "bootstrap_calibration_vs_B.json")
    with open(out, "w") as fh:
        json.dump(rec, fh, indent=2)
    print(f"\n  record : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
