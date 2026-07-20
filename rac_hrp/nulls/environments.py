"""
rac_hrp.nulls.environments
==========================
D9 -- the null environments.

WHAT A NULL CHECK IS FOR, AND WHY IT IS NOT AN ABLATION.

An ablation asks: "does component X contribute?" It runs the pipeline on REAL
data with X removed and compares. If the pipeline is fundamentally broken -- if
it has a look-ahead leak, or if its trigger is picking up a mechanical artifact
-- an ablation cannot tell you. Every arm inherits the same leak, so the
comparison still "works" and the ablation confirms that X matters. It will
cheerfully attribute a leak to your contribution.

A null check asks the opposite and much harder question: "when there is provably
nothing to find, does this pipeline correctly find nothing?" You destroy the
signal, keep the machinery, and demand a flat result. A pipeline that produces a
Sharpe edge on data with no signal in it is not a strategy. It is a bug, and
every number it will ever produce is uninterpretable.

This is a FALSIFICATION test. It can only fail the project, never confirm it.
That is what makes it worth running before three months of modelling.

THE FOUR ENVIRONMENTS
---------------------
A. IID GAUSSIAN         Per-asset volatility matched to the real panel; zero
                        mean; zero cross-correlation; no time dependence.
                        Catches: gross look-ahead, indexing bugs, any leak of
                        future returns into weights.

B. CROSS-SECTIONAL      Within each date, permute realised returns across assets.
   SHUFFLE              Preserves the market's own daily return, the fat tails,
                        the vol clustering -- and destroys the link between an
                        asset's covariance history and its future return.
                        Catches: leakage through asset identity. This is the one
                        that catches a pipeline that has learned WHICH asset to
                        hold from information it should not have.

C. TRIGGER-TIMING       Real returns, real everything -- but the absorption ratio
   (method-specific)    is computed on a CIRCULARLY SHIFTED copy of the panel, so
                        the trigger fires at times unrelated to the actual regime
                        changes in the returns being traded.
                        Catches: THE central threat to this specific paper. If
                        RAC-HRP beats static HRP just as well with a randomly
                        timed trigger, then the contribution is not "re-cluster
                        when the regime changes" -- it is "re-cluster sometimes",
                        and the absorption ratio is decoration. No other test in
                        the project can catch this.

D. NIKOLOPOULOS ENV-B   Regime-switching volatility, zero return signal. Vol and
   (regime-switch vol)  correlation genuinely shift between states, so the
                        absorption ratio genuinely moves and the trigger
                        genuinely fires -- but conditional expected returns are
                        zero throughout, so there is nothing to allocate toward.
                        Catches: an "edge" that is really volatility timing
                        dressed as regime-adaptive clustering. Identified in the
                        review as the most relevant falsification environment for
                        this pipeline, and it is the sharpest of the four,
                        because it is the only one where the trigger is doing
                        exactly what it was designed to do and the answer must
                        still be zero.

Every environment preserves the NaN mask of the real panel, so the point-in-time
universe, the eligibility screen and the delisting pattern are all unchanged.
Only the numbers are replaced. The machinery under test is bit-for-bit the same.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd


def _mask(real: pd.DataFrame) -> np.ndarray:
    return real.notna().values


def iid_gaussian(real: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Environment A."""
    M = _mask(real)
    sd = real.std(axis=0, skipna=True).values
    sd = np.where(np.isfinite(sd) & (sd > 0), sd, np.nanmedian(sd))
    X = rng.standard_normal(real.shape) * sd[None, :]
    X[~M] = np.nan
    return pd.DataFrame(X, index=real.index, columns=real.columns)


def cross_sectional_shuffle(real: pd.DataFrame,
                            rng: np.random.Generator) -> pd.DataFrame:
    """Environment B. Permute across assets WITHIN each date."""
    V = real.values.astype(float).copy()   # coerce: real CRSP panels can be object
    for i in range(V.shape[0]):
        row = V[i]
        ok = np.where(np.isfinite(row))[0]
        if len(ok) > 1:
            row[ok] = rng.permutation(row[ok])
    out = pd.DataFrame(V, index=real.index, columns=real.columns)
    # Demean each asset so no residual drift survives the permutation and gets
    # mistaken for an allocable signal.
    return out - out.mean(axis=0)


def trigger_timing(real: pd.DataFrame,
                   rng: np.random.Generator,
                   min_shift: int = 252) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Environment C. Returns (performance_panel, signal_panel).

    The performance panel is the REAL data, untouched. The signal panel is the
    same data circularly shifted in time, so the absorption ratio -- and hence
    every re-clustering decision -- is computed from a regime process that has
    nothing to do with the returns actually being earned.

    A circular shift is used rather than a fresh simulation on purpose: the
    signal panel keeps the exact marginal distributions, vol clustering and
    correlation dynamics of the real data. The AR series it produces is
    statistically indistinguishable from the true one in every respect except
    that it is pointed at the wrong dates. So this null holds the *character* of
    the trigger fixed and destroys only its *timing*, which isolates the claim.
    """
    T = len(real)
    hi = T - min_shift
    if hi <= min_shift:
        shift = T // 2
    else:
        shift = int(rng.integers(min_shift, hi))
    V = np.roll(real.values, shift, axis=0)
    signal = pd.DataFrame(V, index=real.index, columns=real.columns)
    # Keep the real NaN mask so the universe/eligibility logic is unchanged.
    signal = signal.where(real.notna())
    return real, signal


def regime_switch_vol(real: pd.DataFrame,
                      rng: np.random.Generator,
                      n_factors: int = 3,
                      p_stay: Tuple[float, float] = (0.99, 0.97),
                      vol_ratio: float = 2.5,
                      corr_shift: float = 1.4) -> pd.DataFrame:
    """Environment D -- Nikolopoulos Environment B.

    Two-state Markov regime. In the high state BOTH the volatility and the factor
    loadings scale up, so total variance rises AND the share of variance absorbed
    by the top components rises -- a genuine, detectable correlation regime.
    Conditional means are zero everywhere: there is no return signal, in either
    state, at any horizon.
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

    B = rng.normal(0.0, 1.0, size=(N, n_factors))
    scale = np.where(state == 0, 1.0, vol_ratio)[:, None]
    load = np.where(state == 0, 1.0, corr_shift)[:, None]

    F = rng.standard_normal((T, n_factors)) * scale
    E = rng.standard_normal((T, N)) * scale
    X = (F @ B.T) * load * 0.35 + E
    X = X * sd[None, :] / np.nanstd(X, axis=0, keepdims=True)
    X = X - X.mean(axis=0, keepdims=True)     # enforce zero unconditional mean
    X[~M] = np.nan
    return pd.DataFrame(X, index=real.index, columns=real.columns)


ENVIRONMENTS = {
    "A_iid_gaussian": "IID Gaussian, vol-matched, zero correlation",
    "B_xsec_shuffle": "Cross-sectional shuffle within each date",
    "C_trigger_timing": "Real returns, circularly-shifted AR signal",
    "D_regime_switch_vol": "Nikolopoulos Env-B: regime-switching vol, zero signal",
}


def draw(env: str, real: pd.DataFrame, rng: np.random.Generator
         ) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """Return (performance_panel, signal_panel_or_None)."""
    if env == "A_iid_gaussian":
        return iid_gaussian(real, rng), None
    if env == "B_xsec_shuffle":
        return cross_sectional_shuffle(real, rng), None
    if env == "C_trigger_timing":
        return trigger_timing(real, rng)
    if env == "D_regime_switch_vol":
        return regime_switch_vol(real, rng), None
    raise ValueError(f"unknown null environment {env!r}; "
                     f"choose from {sorted(ENVIRONMENTS)}")
