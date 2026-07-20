"""
rac_hrp.core.allocators
=======================
Weight functions. Every allocator has the same signature:

    w = allocator(cov, **kwargs) -> np.ndarray, sums to 1, long-only by default.

HRP  -- Lopez de Prado (2016). Quasi-diagonalise the covariance by the cluster
        tree's leaf order, then recursively bisect, splitting risk budget between
        the two halves by their inverse cluster variance. The KEY property is
        that it never inverts the covariance matrix, which is why it survives
        N/W ratios that break mean-variance.

        NOTE on the tree: HRP's tree is normally rebuilt every rebalance from the
        current correlation matrix. In THIS project the tree is a *decision
        variable* -- static HRP freezes it, periodic HRP rebuilds it on a
        schedule, RAC-HRP rebuilds it when the absorption ratio jumps. So the
        leaf order is passed IN rather than derived here. That separation is the
        whole experiment.

ERC  -- Roncalli (2013). Equal risk contribution: find w such that every asset
        contributes the same share of portfolio variance,
            w_i (Sigma w)_i  =  w_j (Sigma w)_j  for all i, j
        Solved by the cyclical-coordinate-descent scheme of Spinu (2013), which
        is the reliable one -- Newton on the raw first-order conditions is
        fragile at N=500. ERC is a REQUIRED benchmark (it is the gap in the ML
        portfolio literature the review identified), not a nice-to-have.

EW   -- the honest floor. Beating equal weight is harder than most papers admit.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np


# --------------------------------------------------------------------------
# Equal weight
# --------------------------------------------------------------------------
def equal_weight(cov: np.ndarray, **_) -> np.ndarray:
    n = cov.shape[0]
    return np.full(n, 1.0 / n)


# --------------------------------------------------------------------------
# HRP
# --------------------------------------------------------------------------
def _inverse_variance_weights(cov: np.ndarray, idx: Sequence[int]) -> np.ndarray:
    iv = 1.0 / np.maximum(np.diag(cov)[idx], 1e-16)
    return iv / iv.sum()


def _cluster_variance(cov: np.ndarray, idx: Sequence[int]) -> float:
    idx = np.asarray(idx, dtype=int)
    sub = cov[np.ix_(idx, idx)]
    w = _inverse_variance_weights(cov, idx)
    return float(w @ sub @ w)


def hrp_weights(cov: np.ndarray, leaf_order: np.ndarray, **_) -> np.ndarray:
    """Recursive bisection over a GIVEN leaf order."""
    n = cov.shape[0]
    order = np.asarray(leaf_order, dtype=int)
    if len(order) != n:
        raise ValueError(f"leaf_order length {len(order)} != cov dim {n}")

    w = np.ones(n)
    clusters = [order]
    while clusters:
        nxt = []
        for c in clusters:
            if len(c) <= 1:
                continue
            half = len(c) // 2
            left, right = c[:half], c[half:]
            vl, vr = _cluster_variance(cov, left), _cluster_variance(cov, right)
            alpha = 1.0 - vl / (vl + vr) if (vl + vr) > 0 else 0.5
            w[left] *= alpha
            w[right] *= (1.0 - alpha)
            nxt.extend([left, right])
        clusters = nxt

    s = w.sum()
    return w / s if s > 0 else np.full(n, 1.0 / n)


# --------------------------------------------------------------------------
# ERC
# --------------------------------------------------------------------------
def erc_weights(cov: np.ndarray, tol: float = 1e-10, max_iter: int = 5000,
                **_) -> np.ndarray:
    """Equal risk contribution via Spinu (2013) cyclical coordinate descent.

    Minimises  0.5 w' Sigma w - (1/n) sum log(w_i)  over w > 0, then normalises.
    The log barrier is what forces every risk contribution equal; it also keeps
    the iterate strictly positive, so the long-only constraint is automatic.
    """
    n = cov.shape[0]
    vol = np.sqrt(np.maximum(np.diag(cov), 1e-16))
    x = (1.0 / vol) / np.sum(1.0 / vol)      # inverse-vol warm start
    Sx = cov @ x

    for _ in range(max_iter):
        x_old = x.copy()
        for i in range(n):
            aii = cov[i, i]
            if aii <= 1e-16:
                continue
            # Sx_i without own contribution
            ci = Sx[i] - aii * x[i]
            # solve  aii*x + ci - 1/(n*x) = 0   ->   aii x^2 + ci x - 1/n = 0
            disc = ci ** 2 + 4.0 * aii / n
            x_new = (-ci + np.sqrt(max(disc, 0.0))) / (2.0 * aii)
            x_new = max(x_new, 1e-16)
            if x_new != x[i]:
                Sx += cov[:, i] * (x_new - x[i])
                x[i] = x_new
        if np.max(np.abs(x - x_old)) < tol:
            break

    s = x.sum()
    return x / s if s > 0 else np.full(n, 1.0 / n)


def risk_contributions(cov: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Diagnostic: should be ~flat for ERC. Used in the unit tests."""
    mrc = cov @ w
    rc = w * mrc
    tot = rc.sum()
    return rc / tot if tot > 0 else rc


# --------------------------------------------------------------------------
# Minimum variance (reported unconstrained alongside, per the risk register)
# --------------------------------------------------------------------------
def min_variance(cov: np.ndarray, long_only: bool = True, **_) -> np.ndarray:
    n = cov.shape[0]
    try:
        inv = np.linalg.pinv(cov)
    except np.linalg.LinAlgError:
        return equal_weight(cov)
    ones = np.ones(n)
    w = inv @ ones
    d = ones @ w
    w = w / d if abs(d) > 1e-16 else equal_weight(cov)
    if long_only:
        w = np.maximum(w, 0.0)
        s = w.sum()
        w = w / s if s > 0 else equal_weight(cov)
    return w
