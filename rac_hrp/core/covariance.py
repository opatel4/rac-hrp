"""
rac_hrp.core.covariance
=======================
D3 -- nonlinear Ledoit-Wolf shrinkage.

`nonlinear_shrinkage` is a port of Ledoit & Wolf's ANALYTICAL nonlinear shrinkage
estimator (Ledoit & Wolf, "Analytical Nonlinear Shrinkage of Large-Dimensional
Covariance Matrices", Annals of Statistics 48(5), 2020; the estimator carried
forward in their 2022 quadratic-shrinkage work). It is the closed-form kernel
estimator, not the QuEST numerical inversion -- QuEST needs a nonlinear solver
per estimate and is not viable inside a 25-year walk-forward with ~300 rebalance
dates times 20 null replications.

Why nonlinear rather than the 2004 linear shrinkage the project started with:
linear shrinkage pulls every eigenvalue toward the grand mean by ONE common
intensity. The sample spectrum's distortion is not uniform -- small eigenvalues
are biased down much harder than large ones are biased up. HRP's recursive
bisection allocates on inverse variance and is therefore most sensitive to
exactly the small-eigenvalue end that linear shrinkage handles worst. Nonlinear
shrinkage applies a *different* intensity to each eigenvalue.

All estimators here take X as (T x N) and return (N x N). No annualisation is
applied anywhere: everything downstream is in daily units until the metrics
layer.
"""

from __future__ import annotations

import numpy as np


def _check(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if X.ndim != 2:
        raise ValueError("X must be 2-D (T x N)")
    T, N = X.shape
    if T < 12:
        raise ValueError(f"need T >= 12 for shrinkage, got T={T}")
    return X


def sample_cov(X: np.ndarray) -> np.ndarray:
    X = _check(X)
    Xc = X - X.mean(axis=0, keepdims=True)
    return (Xc.T @ Xc) / (X.shape[0] - 1)


def nonlinear_shrinkage(X: np.ndarray) -> np.ndarray:
    """Analytical nonlinear shrinkage (Ledoit-Wolf 2020).

    Shrinks each sample eigenvalue individually using a kernel estimate of the
    limiting spectral density and its Hilbert transform. Eigenvectors are left
    untouched -- only the spectrum is corrected.
    """
    X = _check(X)
    T, N = X.shape
    Xc = X - X.mean(axis=0, keepdims=True)
    n = T - 1                                   # dof after demeaning
    S = (Xc.T @ Xc) / n

    lam, u = np.linalg.eigh(S)                  # ascending
    lam = lam[max(0, N - n):]                   # drop structural zeros if N > n
    p = N

    h = n ** (-1.0 / 3.0)                       # bandwidth
    H = h * lam[None, :]                        # 1 x k
    x = (lam[:, None] - lam[None, :]) / H       # k x k

    # Epanechnikov kernel density estimate of the spectral density
    ftilde = (3.0 / 4.0 / np.sqrt(5.0)) * np.mean(
        np.maximum(1.0 - x ** 2 / 5.0, 0.0) / H, axis=1)

    # Hilbert transform of the same kernel
    with np.errstate(divide="ignore", invalid="ignore"):
        Hf = ((-3.0 / 10.0 / np.pi) * x
              + (3.0 / 4.0 / np.sqrt(5.0) / np.pi)
              * (1.0 - x ** 2 / 5.0)
              * np.log(np.abs((np.sqrt(5.0) - x) / (np.sqrt(5.0) + x))))
    Hf[np.abs(x) == np.sqrt(5.0)] = (-3.0 / 10.0 / np.pi) * x[np.abs(x) == np.sqrt(5.0)]
    Hf = np.nan_to_num(Hf, nan=0.0, posinf=0.0, neginf=0.0)
    Hftilde = np.mean(Hf / H, axis=1)

    if p <= n:
        q = p / n
        denom = (np.pi * q * lam * ftilde) ** 2 + \
                (1.0 - q - np.pi * q * lam * Hftilde) ** 2
        dtilde = lam / denom
    else:
        # p > n: the null space needs its own shrunk eigenvalue.
        Hftilde0 = (1.0 / np.pi) * (
            3.0 / 10.0 / h ** 2
            + 3.0 / 4.0 / np.sqrt(5.0) / h * (1.0 - 1.0 / 5.0 / h ** 2)
            * np.log((1.0 + np.sqrt(5.0) * h) / (1.0 - np.sqrt(5.0) * h))
        ) * np.mean(1.0 / lam)
        dtilde0 = 1.0 / (np.pi * (p - n) / n * Hftilde0)
        dtilde1 = lam / (np.pi ** 2 * lam ** 2 * (ftilde ** 2 + Hftilde ** 2))
        dtilde = np.concatenate([np.full(p - n, dtilde0), dtilde1])

    Sigma = (u * dtilde[None, :]) @ u.T
    return 0.5 * (Sigma + Sigma.T)              # kill float asymmetry


def linear_shrinkage(X: np.ndarray) -> np.ndarray:
    """Ledoit-Wolf (2004) linear shrinkage to a scaled identity.

    Retained only as a comparator/fallback; D3 selects nonlinear.
    """
    X = _check(X)
    T, N = X.shape
    Xc = X - X.mean(axis=0, keepdims=True)
    S = (Xc.T @ Xc) / T

    mu = np.trace(S) / N
    F = mu * np.eye(N)
    d2 = np.sum((S - F) ** 2)

    b2_bar = 0.0
    for t in range(T):
        xt = Xc[t][:, None]
        b2_bar += np.sum((xt @ xt.T - S) ** 2)
    b2 = min(b2_bar / (T ** 2), d2)

    shrink = b2 / d2 if d2 > 0 else 0.0
    return shrink * F + (1.0 - shrink) * S


def _ewma_cc(X: np.ndarray) -> np.ndarray:
    """EWMA + constant-correlation Ledoit-Wolf shrinkage (amendment rev.4).

    ROW ORDER: ew_constant_correlation_shrinkage expects row 0 = MOST RECENT.
    The pipeline slices forward (returns.iloc[lo:t+1]), so row 0 is the OLDEST
    observation and X MUST be reversed here. Omitting the reversal inverts the
    decay -- the oldest observation would receive 7.5x the weight of the newest
    at alpha=0.996, W=504 -- and produces a well-formed but wrong matrix. No
    existing check catches it: Kish ESS, sum(w)=1, symmetry and PSD are all
    order-invariant.

    alpha is bound to the frozen ALPHA_PRIMARY; the sensitivity sweep over
    {0.990, 0.996, 0.997} is a separate robustness exercise and is not wired
    into this shared dispatcher.
    """
    from .covariance_ew import ew_constant_correlation_shrinkage, ALPHA_PRIMARY
    return ew_constant_correlation_shrinkage(np.asarray(X)[::-1],
                                             alpha=ALPHA_PRIMARY)


ESTIMATORS = {
    "nls": nonlinear_shrinkage,
    "lw_linear": linear_shrinkage,
    "sample": sample_cov,
    "ewma_cc": _ewma_cc,
}


def estimate(X: np.ndarray, method: str = "nls") -> np.ndarray:
    try:
        fn = ESTIMATORS[method]
    except KeyError:
        raise ValueError(f"unknown covariance estimator {method!r}; "
                         f"choose from {sorted(ESTIMATORS)}")
    return fn(X)


def cov_to_corr(S: np.ndarray) -> np.ndarray:
    d = np.sqrt(np.diag(S))
    d = np.where(d <= 0, 1e-12, d)
    C = S / np.outer(d, d)
    np.fill_diagonal(C, 1.0)
    return np.clip(C, -1.0, 1.0)
