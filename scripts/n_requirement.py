"""
Phase 2B design analysis — what n would the Stage A test need?

NOT a Phase 2B result. Computes nothing from the observed series. Runs the
same power harness on synthetic data at several sample sizes to measure how
MDE80 scales with n, then inverts that to a data-configuration requirement.

Anchored on the real measurement: MDE80 = 0.2304 at n = 233, block length 13.
The synthetic generator is calibrated to comparable persistence; what is being
measured here is the SCALING EXPONENT, not the level. The level is taken from
the real run.
"""
from __future__ import annotations
import numpy as np, sys, json, time
sys.path.insert(0, ".")
import phase2b_stats as P

REAL_MDE80 = 0.2304      # measured, n=233, b=13, alpha=0.05
REAL_N     = 233
REAL_B     = 13


def ar1(n, phi, rng):
    e = rng.standard_normal(n)
    x = np.empty(n); x[0] = e[0]
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


def synth(n, rng):
    """Stand-ins with persistence and tail comparable to the observed series."""
    s = np.abs(ar1(n, 0.55, rng)) / np.abs(rng.standard_t(6, n) * 0.4 + 1.2)
    vi = 0.75 + 0.06 * ar1(n, 0.65, rng)
    return s, vi


def block_for(n):
    """Politis-White scales as n^(1/3); anchor on the real b=13 at n=233."""
    return max(1, int(round(REAL_B * (n / REAL_N) ** (1 / 3))))


def mde_at(n, *, seed, c_grid, reps, replicates):
    rng = np.random.default_rng(seed)
    s, vi = synth(n, rng)
    b = block_for(n)
    t0 = time.time()
    curve = P.power_curve(s, vi, seed=seed, c_grid=c_grid, reps=reps,
                          replicates=replicates, block_length=b)
    return {
        "n": n, "block_length": b,
        "curve": curve,
        "mde80": P.mde80(curve),
        "secs": round(time.time() - t0, 1),
    }


if __name__ == "__main__":
    n = int(sys.argv[1])
    grid = tuple(float(x) for x in sys.argv[2].split(","))
    reps = int(sys.argv[3]); reps_b = int(sys.argv[4])
    out = mde_at(n, seed=20260901, c_grid=grid, reps=reps, replicates=reps_b)
    for r in out["curve"]:
        print(f"  c={r['c']:<6} rho={r['achieved_rho']:+.4f}  power={r['power']:.3f}")
    print(f"n={out['n']}  b={out['block_length']}  "
          f"MDE80={out['mde80'] if out['mde80'] is None else round(out['mde80'],4)}  "
          f"[{out['secs']}s]")
    json.dump(out, open(f"mde_n{n}.json", "w"))
