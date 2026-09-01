"""
Phase 2C scoping — does pooling across universes buy effective sample size?

NOT a Phase 2B or 2C result. Runs no test, computes no p-value, and touches
nothing that bears on the Phase 2B stop condition. This is a design screen:
it asks whether k universes give k independent samples or something much less,
and it is meant to be run BEFORE any Phase 2C specification is written.

The logic. Pooling k universes multiplies the nominal observation count by k,
but equity universes share a market factor, so the absorption ratio moves
together across them. If s_t is near-identical everywhere, the trigger fires
on the same dates everywhere and the extra universes add almost nothing. The
standard design effect for k correlated series with mean pairwise correlation
rho_bar is

    DEFF  = 1 + (k - 1) * rho_bar
    n_eff = n * k / DEFF

which collapses to n (no gain at all) when rho_bar = 1, and gives the full
n*k when rho_bar = 0.

WHAT THIS ESTABLISHES, AND WHAT IT DOES NOT.
This screen uses the trigger signal s_t only, because s_t is cheap — it needs
a covariance pass and an eigendecomposition per universe, not the clustering
and VI computation. That makes it a screen, not an answer:

  - rho_bar high (say > 0.9): decisive. The statistics cannot be less
    correlated than this in any way that rescues the design. Stop; the
    multi-universe route does not work.
  - rho_bar low or moderate: encouraging but NOT sufficient. The design effect
    that actually governs Stage A depends on the joint (s, VI) score, and VI
    may be far more or far less shared across universes than s is. Proceed to
    the full pipeline on the surviving universes and recompute.

The MDE projection uses the exponent -0.4542 measured on synthetic data at
n = 233, 466, 932, anchored on the real Phase 2B measurement MDE80 = 0.2304
at n = 233. Both the exponent and the anchor are stated here so a reader can
substitute their own.
"""
from __future__ import annotations

import itertools
import numpy as np
from scipy import stats

REAL_MDE80 = 0.2304    # measured: n=233, b=13, alpha=0.05
REAL_N = 233
SCALING_EXPONENT = -0.4542   # fitted, R^2 = 0.9937

__all__ = ["design_effect", "projected_mde80", "screen"]


def projected_mde80(n_eff: float) -> float:
    """Extrapolate the measured MDE80 to a different effective sample size."""
    return REAL_MDE80 * (n_eff / REAL_N) ** SCALING_EXPONENT


def design_effect(series: dict[str, np.ndarray]) -> dict:
    """
    Mean pairwise Spearman correlation across universes, and the design effect
    it implies. All series must be on a common date index with equal length.
    """
    names = sorted(series)
    k = len(names)
    if k < 2:
        raise ValueError("need at least two universes")
    lengths = {len(series[nm]) for nm in names}
    if len(lengths) != 1:
        raise ValueError(f"series lengths differ: {lengths} — align dates first")
    n = lengths.pop()

    pairs = {}
    for a, b in itertools.combinations(names, 2):
        x, y = np.asarray(series[a], float), np.asarray(series[b], float)
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 3:
            raise ValueError(f"{a}/{b}: fewer than 3 finite paired observations")
        pairs[(a, b)] = float(stats.spearmanr(x[ok], y[ok]).statistic)

    vals = np.array(list(pairs.values()))
    rho_bar = float(vals.mean())
    deff = 1.0 + (k - 1) * rho_bar
    if deff <= 0:
        raise ValueError(f"non-positive design effect {deff:.3f} — "
                         "negative mean correlation, check inputs")
    n_eff = n * k / deff

    return {
        "universes": names,
        "k": k,
        "n_per_universe": n,
        "n_nominal": n * k,
        "pairwise": {f"{a}|{b}": round(v, 4) for (a, b), v in pairs.items()},
        "rho_bar": rho_bar,
        "rho_min": float(vals.min()),
        "rho_max": float(vals.max()),
        "design_effect": deff,
        "n_effective": n_eff,
        "gain_vs_single": n_eff / n,
        "gain_vs_nominal": n_eff / (n * k),
    }


def screen(series: dict[str, np.ndarray]) -> str:
    """design_effect plus the projected MDE80 and a verdict, as a report."""
    d = design_effect(series)
    mde = projected_mde80(d["n_effective"])
    rb = d["rho_bar"]

    if rb > 0.90:
        verdict = ("STOP. Mean pairwise correlation above 0.90 means the "
                   "universes carry nearly the same signal. Pooling cannot "
                   "deliver the sample size Stage A needs.")
    elif mde <= 0.15:
        verdict = ("PROMISING. Projected MDE80 clears 0.15 on the s screen. "
                   "Not sufficient on its own — recompute on the joint (s, VI) "
                   "score before writing a Phase 2C specification.")
    elif mde <= 0.20:
        verdict = ("MARGINAL. Projected MDE80 clears the 0.20 bar but with "
                   "little room, and this screen is optimistic relative to the "
                   "joint score. Adding universes or reconsidering the "
                   "structural measure is likely necessary.")
    else:
        verdict = ("INSUFFICIENT. Projected MDE80 does not clear 0.20 even on "
                   "the optimistic s screen.")

    lines = [
        f"universes         {d['k']}  ({', '.join(d['universes'])})",
        f"n per universe    {d['n_per_universe']}",
        f"n nominal         {d['n_nominal']}",
        "",
        "pairwise Spearman on s_t:",
        *[f"  {kk:<28} {vv:+.4f}" for kk, vv in d["pairwise"].items()],
        "",
        f"rho_bar           {d['rho_bar']:+.4f}   (min {d['rho_min']:+.4f}, "
        f"max {d['rho_max']:+.4f})",
        f"design effect     {d['design_effect']:.3f}",
        f"n effective       {d['n_effective']:.0f}",
        f"gain vs single    {d['gain_vs_single']:.2f}x",
        f"gain vs nominal   {d['gain_vs_nominal']:.2f}x  "
        f"(1.00 would mean fully independent)",
        "",
        f"projected MDE80   {mde:.4f}   "
        f"(anchor {REAL_MDE80} at n={REAL_N}, exponent {SCALING_EXPONENT})",
        "",
        verdict,
    ]
    return "\n".join(lines)
