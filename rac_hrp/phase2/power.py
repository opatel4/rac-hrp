"""
rac_hrp.phase2.power
====================
2E-POWER: planted-effect power curve for the frozen cluster-informativeness test.

Frozen specification: RAC_HRP_Phase2E_PreSpec_rev8.md
SHA-256: cfdd64cca9a23a1d873695b2de0576b442cf2b80e302602830a0d1502c403674

WHAT THIS IS
------------
The Phase 2A gate failed to reject at every gamma. That is consistent with no
effect and equally consistent with a design that could not have detected one.
This module measures the second possibility: the smallest true D_VI the frozen
inference could have detected at 80% power, on the dependence structure the gate
actually faced.

NON-GATING. Nothing here can render any gamma admissible or alter any frozen
value. The Phase 2A verdict stands regardless of what this returns.

BASE PATH (PreSpec rev.7 section 2.2)
-------------------------------------
The observed one-step VI series at the 233 eligible rebalances, median-centred so
the base path carries no clustering-change effect. Dependence and ordering are
preserved exactly. This is NOT a synthetic generator: rev.6 replaced the original
i.i.d. generator because it had no serial dependence and no burst structure, which
made condition R undefined and would have made every power number an upper bound
under conditions strictly easier than the gate's.

Consequence, stated in the reporting: the MDE is conditional on the observed
dependence realisation. It answers what this design could have detected on this
data, not what it would detect on average across a population.

DESIGN (section 2.2)
--------------------
Target-gamma sparse alternative. For a target candidate g, effect delta, placement
condition and replication r: plant delta ONLY at the positions designated for g,
leave the other three candidates null on the same path, compute all four candidate
tests, apply Holm across those four exactly as the gate does, and record whether
the TARGET rejects. This reproduces the decision the gate would have faced had the
effect been real at a single threshold.

PLACEMENT (section 2.3)
-----------------------
  R  delta planted at the frozen trigger sets, preserving the observed bursts
  U  delta planted at |T_g| uniformly drawn positions

Power_R - Power_U reflects the COMBINED effect of clustered placement on the
statistic and on the block length the frozen inference selects. It is not a
decomposition of the two and is not reported as one. Realised block lengths are
reported per cell.

RANDOMNESS
----------
Base seed 292828877 (PreSpec section 2.4, OS entropy). Seeds are replication-level
and distinguish target, delta, condition and replication index.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .calibration import StructuralPass
from .stats import (circular_block_bootstrap_p, d_vi, holm_adjust,
                    politis_white_block_length)

SPEC_SHA = "cfdd64cca9a23a1d873695b2de0576b442cf2b80e302602830a0d1502c403674"

BASE_SEED = 292828877
GAMMA_CANDIDATES: Tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
DELTA_GRID: Tuple[float, ...] = (0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30)
CONDITIONS: Tuple[str, ...] = ("R", "U")
N_REPLICATIONS_DEFAULT = 2000
BOOTSTRAP_REPLICATES = 2000
ALPHA = 0.05
POWER_TARGET = 0.80
SIZE_BAND = (0.02, 0.10)               # section 2.5 pass band, rev.8
EXPECTED_EVENT_COUNTS: Dict[float, int] = {0.5: 149, 1.0: 111, 1.5: 81, 2.0: 58}
EXPECTED_ELIGIBLE = 233


class PowerAbort(RuntimeError):
    """A frozen precondition failed. No power number is meaningful."""


def seed_for(g: float, delta: float, condition: str, r: int) -> int:
    """Replication-level seed, distinguishing all four coordinates (section 2.4)."""
    gi = GAMMA_CANDIDATES.index(g)
    di = DELTA_GRID.index(delta) if delta in DELTA_GRID else len(DELTA_GRID)
    ci = CONDITIONS.index(condition)
    return BASE_SEED + 10_000_000 * gi + 100_000 * di + 10_000 * ci + r


# --------------------------------------------------------------------------
# Base path and trigger sets
# --------------------------------------------------------------------------
@dataclass
class PowerInputs:
    observed: np.ndarray                   # RAW observed VI at eligible dates
    block_length: int                      # Politis-White length on that series
    fired: Dict[float, np.ndarray]         # frozen trigger masks, eligible-local
    n_events: Dict[float, int]
    base_median: float
    E: int


def build_inputs(sp: StructuralPass) -> PowerInputs:
    """Observed VI, its block length, and the frozen masks. Aborts on drift.

    The series is NOT centred. rev.7 centred it on the mistaken view that this
    would null the statistic; subtracting a scalar leaves the difference between
    two subgroup medians unchanged. Nulling happens per replication, by resampling.
    """
    elig = np.where(sp.eligible)[0]
    E = len(elig)
    if E != EXPECTED_ELIGIBLE:
        raise PowerAbort(f"eligible set is {E}, expected {EXPECTED_ELIGIBLE}")

    vi = np.asarray(sp.vi, dtype=float)[elig]
    if np.isnan(vi).any():
        raise PowerAbort(f"{int(np.isnan(vi).sum())} NaN in the eligible VI series; "
                         "the base path must be complete")

    med = float(np.median(vi))
    L = int(politis_white_block_length(vi))

    fired: Dict[float, np.ndarray] = {}
    counts: Dict[float, int] = {}
    for g in GAMMA_CANDIDATES:
        with np.errstate(invalid="ignore"):
            m = np.abs(sp.d_ar[elig]) > g * sp.sigma[elig]
        n = int(m.sum())
        if n != EXPECTED_EVENT_COUNTS[g]:
            raise PowerAbort(
                f"gamma={g}: {n} events, frozen gate reports {EXPECTED_EVENT_COUNTS[g]}")
        fired[g] = m
        counts[g] = n

    return PowerInputs(observed=vi, block_length=L, fired=fired,
                       n_events=counts, base_median=med, E=E)



def block_resample(x: np.ndarray, L: int, rng: np.random.Generator) -> np.ndarray:
    """Circular block resample of x at block length L, same length out.

    Identical in mechanics to the resampling inside the frozen bootstrap, used
    here to generate each replication's null realisation (rev.8 section 2.2).
    """
    n = len(x)
    n_blocks = int(np.ceil(n / L))
    starts = rng.integers(0, n, size=n_blocks)
    idx = ((starts[:, None] + np.arange(L)[None, :]) % n).ravel()[:n]
    return x[idx]


def uniform_mask(E: int, n_events: int, rng: np.random.Generator) -> np.ndarray:
    """|T_g| positions drawn uniformly without replacement (condition U)."""
    m = np.zeros(E, dtype=bool)
    m[rng.choice(E, size=n_events, replace=False)] = True
    return m


# --------------------------------------------------------------------------
# One replication of the sparse-alternative experiment
# --------------------------------------------------------------------------
def _one_replication(inp: PowerInputs, target: float, delta: float,
                     condition: str, r: int) -> Tuple[bool, int]:
    """Returns (target rejected under Holm, realised block length for target)."""
    rng = np.random.default_rng(seed_for(target, delta, condition, r))

    # rev.8 section 2.2: this replication's null realisation. Circular block
    # resampling breaks the association between path and mask, so no subgroup
    # carries an effect; blocks preserve serial dependence; a fresh draw each
    # replication supplies the sampling variation a power curve requires.
    path = block_resample(inp.observed, inp.block_length, rng)

    if condition == "R":
        plant = inp.fired[target]
    else:
        plant = uniform_mask(inp.E, inp.n_events[target], rng)

    path = path.copy()
    path[plant] += delta

    raw: Dict[float, float] = {}
    block_target = -1
    for g in GAMMA_CANDIDATES:
        boot = circular_block_bootstrap_p(
            path, inp.fired[g],
            seed=int(rng.integers(1, 2**31 - 1)),
            replicates=BOOTSTRAP_REPLICATES)
        raw[g] = boot.p_value
        if g == target:
            block_target = int(boot.block_length)

    if not np.isfinite(raw[target]):
        return False, block_target
    adj = holm_adjust(raw)
    return bool(adj[target] < ALPHA), block_target


# --------------------------------------------------------------------------
# Cells and the sweep
# --------------------------------------------------------------------------
@dataclass
class PowerCell:
    target: float
    delta: float
    condition: str
    n_replications: int
    power: float
    mc_se: float
    median_block_length: int


@dataclass
class PowerResult:
    cells: List[PowerCell] = field(default_factory=list)
    size_cell: Optional[PowerCell] = None
    mde80: Dict[Tuple[float, str], str] = field(default_factory=dict)
    n_replications: int = N_REPLICATIONS_DEFAULT
    base_median: float = float("nan")
    spec_sha256: str = SPEC_SHA


def _cell(inp: PowerInputs, target: float, delta: float, condition: str,
          n_rep: int) -> PowerCell:
    hits, blocks = 0, []
    for r in range(n_rep):
        rej, L = _one_replication(inp, target, delta, condition, r)
        hits += int(rej)
        blocks.append(L)
    p = hits / n_rep
    se = float(np.sqrt(p * (1 - p) / n_rep))
    return PowerCell(target, delta, condition, n_rep, p, se,
                     int(np.median(blocks)))


def probe_timing(inp: PowerInputs, n_probe: int = 50) -> float:
    """Section 2.8: wall-clock for one cell, used to decide the replication count."""
    t0 = time.time()
    _cell(inp, GAMMA_CANDIDATES[-1], DELTA_GRID[3], "R", n_probe)
    return (time.time() - t0) / n_probe


def run_power(sp: StructuralPass, n_replications: int = N_REPLICATIONS_DEFAULT,
              verbose: bool = True) -> PowerResult:
    inp = build_inputs(sp)
    res = PowerResult(n_replications=n_replications, base_median=inp.base_median)

    # ---- delta = 0: empirical size on the real dependence structure -----
    if verbose:
        print("  [2E-POWER] delta = 0 (empirical size on the observed dependence) ...")
    size = _cell(inp, GAMMA_CANDIDATES[0], 0.0, "R", n_replications)
    size.delta = 0.0
    res.size_cell = size
    if verbose:
        print(f"            size = {size.power:.4f}  (MC SE {size.mc_se:.4f}, "
              f"median block {size.median_block_length})")
    lo, hi = SIZE_BAND
    if not (lo <= size.power <= hi):
        raise PowerAbort(
            f"delta=0 rejection rate {size.power:.4f} falls outside the frozen "
            f"pass band [{lo}, {hi}]; the procedure is not adequately calibrated on "
            "this dependence structure and a power curve built on it would be "
            "uninterpretable")

    # ---- the grid --------------------------------------------------------
    total = len(GAMMA_CANDIDATES) * len(DELTA_GRID) * len(CONDITIONS)
    done = 0
    for target in GAMMA_CANDIDATES:
        for condition in CONDITIONS:
            for delta in DELTA_GRID:
                c = _cell(inp, target, delta, condition, n_replications)
                res.cells.append(c)
                done += 1
                if verbose:
                    print(f"    [{done:2d}/{total}] g={target:<4} {condition} "
                          f"d={delta:<5} power={c.power:.3f} "
                          f"(SE {c.mc_se:.3f}, block {c.median_block_length})")

    # ---- MDE80, bracketing intervals only (section 2.7) ------------------
    for target in GAMMA_CANDIDATES:
        for condition in CONDITIONS:
            row = sorted((c for c in res.cells
                          if c.target == target and c.condition == condition),
                         key=lambda c: c.delta)
            hit = next((c for c in row if c.power >= POWER_TARGET), None)
            if hit is None:
                res.mde80[(target, condition)] = f"> {DELTA_GRID[-1]}"
            else:
                i = row.index(hit)
                lo = row[i - 1].delta if i else 0.0
                res.mde80[(target, condition)] = f"({lo}, {hit.delta}]"

    return res


def format_report(res: PowerResult) -> str:
    L: List[str] = []
    L.append("2E-POWER -- planted-effect power curve")
    L.append(f"  spec SHA-256 {res.spec_sha256}")
    L.append(f"  replications per cell {res.n_replications}, "
             f"bootstrap B = {BOOTSTRAP_REPLICATES}, alpha = {ALPHA}")
    L.append(f"  base path: per-replication circular block resample of the observed "
             f"one-step VI (median {res.base_median:.4f})")
    L.append("")
    if res.size_cell is not None:
        s = res.size_cell
        L.append(f"  delta = 0 -> empirical size on the observed dependence structure: "
                 f"{s.power:.4f} (MC SE {s.mc_se:.4f})")
        L.append("     Not comparable to the previously published 0.0660, which was")
        L.append("     measured on i.i.d. normal VI with i.i.d. Bernoulli firing.")
        L.append("")
    L.append("  target  cond   delta   power     SE   block")
    for c in res.cells:
        L.append(f"  {c.target:6.1f}  {c.condition:>4}  {c.delta:6.2f}  "
                 f"{c.power:6.3f}  {c.mc_se:5.3f}  {c.median_block_length:5d}")
    L.append("")
    L.append("  MDE80 (bracketing interval; no interpolation)")
    for (g, cond), v in sorted(res.mde80.items()):
        L.append(f"    gamma {g:<4} {cond}:  {v}")
    L.append("")
    L.append("  Power_R - Power_U reflects the combined effect of clustered placement on")
    L.append("  the statistic AND on the selected block length. It is not a decomposition.")
    L.append("  The MDE is conditional on the observed dependence realisation: it answers")
    L.append("  what this design could have detected on this data, not on average across")
    L.append("  resamples of a population.")
    L.append("")
    L.append("  NON-GATING. The Phase 2A verdict -- NO ADMISSIBLE GAMMA -- is unchanged.")
    return "\n".join(L)
