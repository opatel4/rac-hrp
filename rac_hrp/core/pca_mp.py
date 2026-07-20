"""
rac_hrp.core.pca_mp
===================
D2 -- Marchenko-Pastur retention, replacing the 60% variance cutoff.

THE PROBLEM WITH 60%. "Keep components until 60% of variance is explained" is a
number with no theory behind it. It answers no question. Worse, the count it
produces drifts with N and with the market: in a crisis the first eigenvalue
alone can carry 50%+, so a 60% rule silently collapses to k=2 exactly when the
correlation structure is most interesting.

WHAT MP ASKS INSTEAD. If N assets over W days were pure noise -- i.i.d., zero
correlation -- the eigenvalues of the sample CORRELATION matrix would still not
be 1. They would spread out, filling the Marchenko-Pastur support:

    q = N / W,   lambda_max = sigma^2 (1 + sqrt(q))^2

Any eigenvalue above lambda_max cannot be explained by sampling noise at that
(N, W). Those are the components that carry real structure; the rest is the bulk.
This is a falsifiable criterion, and it is the one Kritzman-style absorption
analysis should have been using all along.

THE sigma^2 SUBTLETY. The textbook bound assumes sigma^2 = 1 (a correlation
matrix of pure noise). Real markets have a huge market factor, so the bulk sits
*below* 1: the market eigenvalue eats variance that the noise bulk therefore
does not have. Using sigma^2 = 1 over-retains. We instead FIT sigma^2 to the
bulk (Laloux et al. 1999 / Potters-Bouchaud): the retained variance is removed
and sigma^2 is set to the residual variance per remaining mode, iterated to a
fixed point. This is `fit_sigma=True` and it is the default.

k-STABILITY. See the NOTE in config.py: MP-implied k is data-dependent, and a
moving k puts a mechanical sawtooth straight into the absorption ratio (AR is
increasing in k by construction). Default `mp_k_mode="fixed_per_fold"` freezes k
within a fold. The trigger-timing null exists to catch exactly what happens if
this is got wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .covariance import cov_to_corr


@dataclass
class Spectrum:
    eigenvalues: np.ndarray      # descending, of the CORRELATION matrix
    eigenvectors: np.ndarray     # columns, matching order
    cov_eigenvalues: np.ndarray  # descending, of the COVARIANCE matrix
    lambda_max: float            # MP upper edge
    sigma2: float                # fitted bulk variance
    k: int                       # number of retained components
    q: float                     # N / W


def mp_upper_edge(q: float, sigma2: float = 1.0) -> float:
    """Marchenko-Pastur upper edge."""
    return sigma2 * (1.0 + np.sqrt(q)) ** 2


def fit_bulk_sigma2(eigvals: np.ndarray, q: float,
                    max_iter: int = 50, tol: float = 1e-8) -> tuple[float, int]:
    """Fixed-point fit of the noise-bulk variance.

    Start assuming everything is noise (sigma^2 = 1). Compute the MP edge, drop
    the eigenvalues above it, recompute sigma^2 as the average of what is left,
    and repeat until k stops changing.
    """
    N = len(eigvals)
    sigma2 = 1.0
    k_prev = -1
    for _ in range(max_iter):
        edge = mp_upper_edge(q, sigma2)
        k = int(np.sum(eigvals > edge))
        k = min(k, N - 1)                      # never retain everything
        if k == k_prev:
            break
        resid = eigvals[k:]
        if len(resid) == 0:
            break
        new_sigma2 = float(resid.sum() / len(resid))
        if abs(new_sigma2 - sigma2) < tol and k == k_prev:
            break
        sigma2, k_prev = new_sigma2, k
    return sigma2, max(int(k_prev if k_prev >= 0 else 0), 0)


def spectrum(cov: np.ndarray, window: int,
             fit_sigma: bool = True,
             min_components: int = 1,
             force_k: Optional[int] = None) -> Spectrum:
    """Eigen-decompose and apply MP retention."""
    N = cov.shape[0]
    q = N / float(window)

    corr = cov_to_corr(cov)
    w, v = np.linalg.eigh(corr)
    order = np.argsort(w)[::-1]
    w, v = w[order], v[:, order]

    cw = np.linalg.eigvalsh(cov)[::-1]

    if fit_sigma:
        sigma2, k = fit_bulk_sigma2(w, q)
    else:
        sigma2 = 1.0
        k = int(np.sum(w > mp_upper_edge(q, sigma2)))

    k = max(k, min_components)
    k = min(k, N - 1)
    if force_k is not None:
        k = max(min(int(force_k), N - 1), min_components)

    return Spectrum(eigenvalues=w, eigenvectors=v, cov_eigenvalues=cw,
                    lambda_max=mp_upper_edge(q, sigma2), sigma2=sigma2,
                    k=k, q=q)


def absorption_ratio(spec: Spectrum, k: Optional[int] = None) -> float:
    """Kritzman et al. (2011) absorption ratio.

    Fraction of total asset variance captured by the first k eigenvectors.
    Computed on the COVARIANCE spectrum (it is a variance-absorption statistic,
    not a correlation one). `k` defaults to the MP-retained count, but callers
    running in `fixed_per_fold` mode pass an explicit k so the ratio moves only
    with the spectrum and never with a changing component count.
    """
    kk = spec.k if k is None else int(k)
    kk = max(1, min(kk, len(spec.cov_eigenvalues)))
    tot = float(spec.cov_eigenvalues.sum())
    if tot <= 0:
        return np.nan
    return float(spec.cov_eigenvalues[:kk].sum() / tot)


def pca_features(spec: Spectrum, k: Optional[int] = None) -> np.ndarray:
    """Asset coordinates in retained-eigenvector space, for clustering.

    Loadings are scaled by sqrt(eigenvalue) so a component that explains more
    variance exerts proportionally more pull on the distance metric. Clustering
    on raw unit-norm eigenvectors would treat the market factor and the 8th
    component as equally important, which they are not.
    """
    kk = spec.k if k is None else int(k)
    kk = max(1, min(kk, spec.eigenvectors.shape[1]))
    V = spec.eigenvectors[:, :kk]
    s = np.sqrt(np.maximum(spec.eigenvalues[:kk], 0.0))
    return V * s[None, :]
