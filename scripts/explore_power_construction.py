"""
EXPLORATORY -- 2E-POWER base-path construction, under development.

NOT FROZEN. NOT A RESULT. Produces nothing that goes in the paper.

Purpose: find a null-path construction that actually behaves like a null, before
freezing it. Verified on SYNTHETIC data with known properties, never on the real
base path, so nothing here can be tuned to a real outcome.

WHY THIS EXISTS
    rev.7 specified: take the observed VI series, median-centre it, plant delta.
    Two errors, both mine.

    1. Median-centring subtracts a scalar from every value. It cannot change the
       DIFFERENCE between the fired and non-fired medians. The "null" base path
       still carried the full observed effect: base D_VI was +0.033/+0.022/
       +0.080/+0.096, i.e. exactly the gate's Table 4 values.

    2. A fixed base path has no sampling variation. Across replications only the
       bootstrap seed changed, so the statistic was constant and the test either
       cleared or did not. Power came out as a step function: 0.000 -> 1.000
       between adjacent grid points.

    Together with Holm across four candidates that all carried the effect, the
    delta=0 cell gave exactly 0.0000 rejections in 2000 replications, which is
    what surfaced the bug.

WHAT A CORRECT CONSTRUCTION NEEDS
    (a) genuine null: no association between the path and the fired mask
    (b) preserved serial dependence: the real series has lag-1 autocorrelation
        ~0.469 and Politis-White selects block length 13; an i.i.d. path would
        make every power number an optimistic upper bound
    (c) replication-level variation: a new realisation each replication, or there
        is no sampling distribution to speak of

CANDIDATE A -- circular block resample of the path
    Draw each replication's path by circular-block-resampling the observed VI
    series with the observed block length. Pair it with the FROZEN fired masks.
    Resampling scrambles which VI values land at fired positions, so (a) holds by
    construction; blocks preserve within-block dependence, so (b) holds
    approximately; a fresh draw per replication gives (c).

CANDIDATE B -- block permutation of the fired mask
    Keep the observed path; permute the fired mask in blocks. Preserves the path
    exactly, but the mask's own burst structure is what condition R needs to
    preserve, so permuting it defeats the placement comparison.

    A is the one to test. B is recorded because it was considered.

TESTS
    1. size on a synthetic null with matched dependence: should be ~0.05
    2. size on the real base path AFTER construction: should be ~0.05
       (the construction is what makes it null; if it is not, A is wrong)
    3. power on synthetic data with a planted effect: should rise SMOOTHLY
    4. recovery: a planted effect of known size should be detected at a rate
       consistent with its magnitude
    5. dependence check: block length selected on constructed paths should be
       close to that selected on the observed series
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.phase2.stats import (circular_block_bootstrap_p, d_vi,  # noqa: E402
                                  holm_adjust, politis_white_block_length)

GAMMAS = (0.5, 1.0, 1.5, 2.0)
ALPHA = 0.05


# --------------------------------------------------------------------------
# Candidate A
# --------------------------------------------------------------------------
def block_resample(x: np.ndarray, L: int, rng: np.random.Generator) -> np.ndarray:
    """Circular block resample of x with block length L, same length out."""
    n = len(x)
    n_blocks = int(np.ceil(n / L))
    starts = rng.integers(0, n, size=n_blocks)
    idx = ((starts[:, None] + np.arange(L)[None, :]) % n).ravel()[:n]
    return x[idx]


def make_null_path(observed: np.ndarray, L: int, rng: np.random.Generator) -> np.ndarray:
    """One replication's null realisation: dependence preserved, association broken."""
    return block_resample(observed, L, rng)


# --------------------------------------------------------------------------
# One replication of the sparse-alternative experiment
# --------------------------------------------------------------------------
def one_rep(observed: np.ndarray, masks: dict, L: int, target: float,
            delta: float, condition: str, seed: int):
    rng = np.random.default_rng(seed)
    path = make_null_path(observed, L, rng)

    if condition == "R":
        plant = masks[target]
    else:
        E = len(path)
        plant = np.zeros(E, dtype=bool)
        plant[rng.choice(E, size=int(masks[target].sum()), replace=False)] = True

    path = path.copy()
    path[plant] += delta

    raw, blk = {}, -1
    for g in GAMMAS:
        b = circular_block_bootstrap_p(path, masks[g],
                                       seed=int(rng.integers(1, 2**31 - 1)),
                                       replicates=2000)
        raw[g] = b.p_value
        if g == target:
            blk = int(b.block_length)
    if not np.isfinite(raw[target]):
        return False, blk, np.nan
    return bool(holm_adjust(raw)[target] < ALPHA), blk, d_vi(path, masks[target])


def cell(observed, masks, L, target, delta, condition, n_rep, base_seed):
    hits, blocks, stats = 0, [], []
    for r in range(n_rep):
        rej, blk, dv = one_rep(observed, masks, L, target, delta, condition,
                               base_seed + r)
        hits += int(rej)
        blocks.append(blk)
        stats.append(dv)
    p = hits / n_rep
    return dict(power=p, se=float(np.sqrt(p * (1 - p) / n_rep)),
                block=int(np.median(blocks)),
                mean_stat=float(np.nanmean(stats)),
                sd_stat=float(np.nanstd(stats, ddof=1)))


# --------------------------------------------------------------------------
# Synthetic data with known properties
# --------------------------------------------------------------------------
def synth_ar1(n: int, rho: float, sd: float, rng: np.random.Generator) -> np.ndarray:
    """AR(1) path, matched roughly to the observed VI dependence and scale."""
    x = np.zeros(n)
    e = rng.standard_normal(n) * sd * np.sqrt(1 - rho ** 2)
    for i in range(1, n):
        x[i] = rho * x[i - 1] + e[i]
    return x


def synth_bursty_mask(n: int, n_events: int, burst: int,
                      rng: np.random.Generator) -> np.ndarray:
    """Clustered mask: n_events positions arranged in runs of ~burst."""
    m = np.zeros(n, dtype=bool)
    placed = 0
    while placed < n_events:
        run = min(burst, n_events - placed)
        s = int(rng.integers(0, n - run))
        m[s:s + run] = True
        placed = int(m.sum())
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description="EXPLORATORY base-path construction tests")
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--seed", type=int, default=12345)
    a = ap.parse_args()

    print("=" * 74)
    print("  EXPLORATORY -- 2E-POWER base-path construction")
    print("  NOT FROZEN. NOT A RESULT. Synthetic data only.")
    print("=" * 74)

    rng = np.random.default_rng(a.seed)
    E = 233

    # synthetic series matched to the observed: rho ~ 0.47, sd ~ 0.228
    obs = synth_ar1(E, 0.47, 0.228, rng) + 0.58
    L = politis_white_block_length(obs)
    counts = {0.5: 149, 1.0: 111, 1.5: 81, 2.0: 58}
    masks = {g: synth_bursty_mask(E, counts[g], 4, rng) for g in GAMMAS}

    print(f"\n  synthetic series: n={E}, lag-1 acf "
          f"{np.corrcoef(obs[:-1], obs[1:])[0,1]:.3f}, sd {obs.std(ddof=1):.3f}")
    print(f"  Politis-White block length: {L}")
    print(f"  base D_VI on the raw synthetic series (should be ~0):")
    for g in GAMMAS:
        print(f"    g={g}: {d_vi(obs, masks[g]):+.4f}")

    print("\n  TEST 1 -- size under candidate A (delta = 0), target g=2.0")
    c = cell(obs, masks, L, 2.0, 0.0, "R", a.reps, a.seed + 1000)
    print(f"    size {c['power']:.4f} (SE {c['se']:.4f})  block {c['block']}  "
          f"stat mean {c['mean_stat']:+.4f} sd {c['sd_stat']:.4f}")
    print("    PASS" if abs(c["power"] - 0.05) < 0.04 else "    FAIL -- not ~0.05")

    print("\n  TEST 2 -- power rises smoothly, target g=2.0, condition R")
    for d in (0.02, 0.05, 0.08, 0.12, 0.16, 0.20, 0.30):
        c = cell(obs, masks, L, 2.0, d, "R", a.reps, a.seed + 2000)
        print(f"    delta {d:5.2f}  power {c['power']:.3f} (SE {c['se']:.3f})  "
              f"block {c['block']}  stat {c['mean_stat']:+.4f}")

    print("\n  TEST 3 -- condition U at the same deltas")
    for d in (0.02, 0.08, 0.16, 0.30):
        c = cell(obs, masks, L, 2.0, d, "U", a.reps, a.seed + 3000)
        print(f"    delta {d:5.2f}  power {c['power']:.3f} (SE {c['se']:.3f})  "
              f"block {c['block']}  stat {c['mean_stat']:+.4f}")

    print("\n  What to look for:")
    print("    * TEST 1 size near 0.05, not 0.000 and not 1.000")
    print("    * TEST 2 a smooth rise, not a 0 -> 1 step")
    print("    * stat sd > 0 everywhere: there must be sampling variation")
    print("    * TEST 3 lower than TEST 2 at matched delta, but not pinned at 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
