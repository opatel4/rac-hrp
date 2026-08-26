"""
Environment S -- STATIC CORRELATION (regime-free but persistently structured).

STANDALONE MODULE -- install as rac_hrp/nulls/environments_static.py.

Deliberately NOT appended to environments.py and NOT registered in ENVIRONMENTS.
Three call sites derive environment lists or SEEDS from that dict's contents and
ordering (gate.py:220; condition2_static_vs_erc.py:102 and
diagnostic_static_vs_erc.py:69 via list(ENVIRONMENTS.keys()).index(ENV)), and
gate_v2_config.py:89 keeps a parallel ENVIRONMENT_ORDER tuple. Adding a fifth key
would perturb the countersigned Phase 0.5 gate. The mechanism runner dispatches
this function directly instead; nothing in rac_hrp/nulls/ is edited.

Named S, not C, because C_trigger_timing already exists.

WHY THIS ENVIRONMENT EXISTS

Environment A (iid_gaussian) has ZERO cross-sectional correlation. Its population
eigenspectrum is flat, so the absorption ratio has little genuine movement and
dAR is close to pure estimation noise. If A produces bursty triggers that is
devastating evidence of a mechanical artefact -- but if A does NOT burst, the
trigger is not thereby cleared, because the mechanism under suspicion is the
interaction of 96%-overlapping 504-day covariance windows with PERSISTENT
correlation structure, which A never presents.

Environment S draws i.i.d. through time from a single fixed covariance matrix
estimated once from the real panel. There are no regimes whatsoever -- every
date has identical population covariance -- yet consecutive 504-day estimates
overlap by ~96% at monthly rebalances, so the ESTIMATED eigenspectrum is
strongly persistent. That is the sharp test of the suspected mechanism, and it
is the adjudicating null for the mechanism diagnostic.

The real NaN mask is preserved, exactly as every other environment does, so the
point-in-time universe, eligibility screen and delisting pattern are unchanged.
Only the numbers are replaced.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Sigma_0 FACTORISATION CACHE
#
# Sigma_0 depends ONLY on (X_fit, shrink) -- both fixed for an entire run -- yet
# the naive implementation recomputed a pairwise-complete covariance over a
# ~3,000-column panel on EVERY replication. That dominated runtime (a 500-rep
# serial run spent the bulk of ~9 hours here).
#
# The cached quantity is the factor L with Sigma_0 == L @ L.T. The random
# generator is consumed ONLY AFTER this point (Z = rng.standard_normal), so
# caching cannot perturb the draws: output is bit-identical to the uncached
# implementation. Verified by direct comparison; see verify_sigma0_cache().
# ---------------------------------------------------------------------------
_L_CACHE: dict = {}


def _cache_key(X_fit: np.ndarray, shrink: float) -> str:
    h = hashlib.sha256(np.ascontiguousarray(X_fit).tobytes()).hexdigest()
    return f"{h}:{shrink!r}:{X_fit.shape}"


def static_corr(real: pd.DataFrame, rng: np.random.Generator,
                shrink: float = 0.10,
                fit_rows: np.ndarray | None = None) -> pd.DataFrame:
    """Environment S. One fixed Sigma_0 for all t; i.i.d. draws through time.

    Sigma_0 is the pairwise-complete sample covariance of the real panel, ridge-
    shrunk toward its diagonal so the Cholesky factor exists (the real panel has
    far more assets than any single asset's overlapping history supports, so the
    raw pairwise-complete matrix is routinely indefinite).

    `shrink` is a numerical-conditioning device, not a modelling choice: it is
    the smallest convenient amount that guarantees positive definiteness. It
    slightly REDUCES covariance concentration, which makes this a conservative
    null -- any burstiness it produces would be at least as large under the
    unshrunk structure.
    """
    M = real.notna().values
    X_real = real.values.astype(float)

    # Sigma_0 is FITTED ON DEVELOPMENT-REGION ROWS ONLY. The panel runs to the
    # CRSP vintage end (2024-12-31) and therefore contains test-region dates;
    # fitting on all of it would embed test-region covariance structure in the
    # null environment. `fit_rows` is a boolean mask over rows selecting the
    # dates permitted for estimation. Output is still full-length so the
    # calendar, NaN mask and eligibility logic are unchanged.
    X_fit = X_real if fit_rows is None else X_real[fit_rows]

    key = _cache_key(X_fit, shrink)
    if key in _L_CACHE:
        L = _L_CACHE[key]
    else:
        L = _compute_L(X_fit, shrink)
        _L_CACHE[key] = L

    T, N = real.shape
    Z = rng.standard_normal((T, N))
    X = Z @ L.T

    X = X - X.mean(axis=0, keepdims=True)
    X[~M] = np.nan
    return pd.DataFrame(X, index=real.index, columns=real.columns)


def _compute_L(X_fit: np.ndarray, shrink: float) -> np.ndarray:
    """Sigma_0 factorisation. Deterministic in (X_fit, shrink); no RNG use."""
    # Pairwise-complete covariance, then ridge-shrink toward the diagonal.
    S = pd.DataFrame(X_fit).cov().values
    d = np.diag(np.diag(S))
    S0 = (1.0 - shrink) * S + shrink * d
    # Replace any non-finite entries (assets with too little history) by 0
    # covariance / median variance, so the factorisation cannot fail on NaN.
    med_var = np.nanmedian(np.diag(S0))
    S0 = np.where(np.isfinite(S0), S0, 0.0)
    diag = np.diag(S0).copy()
    diag = np.where(np.isfinite(diag) & (diag > 0), diag, med_var)
    np.fill_diagonal(S0, diag)

    # Symmetrise, then force positive definiteness via eigenvalue flooring.
    S0 = 0.5 * (S0 + S0.T)
    w, V = np.linalg.eigh(S0)
    floor = max(1e-12, 1e-8 * float(np.max(w)))
    w = np.where(w > floor, w, floor)
    return V * np.sqrt(w)[None, :]       # S0 == L @ L.T


def verify_sigma0_cache(real: pd.DataFrame, fit_rows=None, shrink: float = 0.10,
                        seed: int = 0) -> bool:
    """Prove the cache is bit-identical: cached vs freshly-computed L, same seed."""
    a = static_corr(real, np.random.default_rng(seed), shrink, fit_rows)
    _L_CACHE.clear()
    b = static_corr(real, np.random.default_rng(seed), shrink, fit_rows)
    return bool(np.array_equal(a.values, b.values, equal_nan=True))
