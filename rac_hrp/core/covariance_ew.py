"""
rac_hrp.core.covariance_ew
==========================
FROZEN implementation of the exponentially weighted covariance estimator with a
weighted constant-correlation linear shrinkage.

Specified in, and implemented exactly to, the signed amendment:
    "AMENDMENT - EWMA COVARIANCE (rev.4)"  [ADOPTED AND FROZEN]

EPISTEMIC LABEL (amendment section 4)
-------------------------------------
This is a PROSPECTIVELY SPECIFIED EXPONENTIALLY WEIGHTED LINEAR-SHRINKAGE
EXTENSION OF LEDOIT-WOLF (2004). It is NOT the Ledoit-Wolf analytical estimator.
Ledoit-Wolf's derivation assumes observations i.i.d. through time; exponential
weighting deliberately imposes unequal deterministic weights, so substituting
w_j for 1/T and N_eff for T is a plausible extension, not a theorem. Its
optimality is not established. Do not describe it otherwise in any writeup.

WHICH LEDOIT-WOLF (amendment section 1)
---------------------------------------
Molyboga (2020) cites "Honey, I Shrunk the Sample Covariance Matrix", JPM 30(4),
110-119, whose target is CONSTANT CORRELATION. That is the target used here. The
repository's separate `covariance.lw_linear` uses a scaled-identity target, which
is the OTHER 2004 paper (JMVA 88(2)). They are not interchangeable.

FROZEN PARAMETERS
-----------------
    alpha primary      0.996   (Pafka, Potters & Kondor 2004)
    alpha sensitivity  {0.990, 0.996, 0.997}
    window W           504     (D4 rule, frozen elsewhere)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

# Frozen decay parameters (amendment section 5)
ALPHA_PRIMARY = 0.996
ALPHA_SENSITIVITY = (0.990, 0.996, 0.997)


# --------------------------------------------------------------------------
# 3.1  Weights
# --------------------------------------------------------------------------
def ew_weights(alpha: float, W: int) -> np.ndarray:
    """Truncated and renormalised exponential weights.

        w_j(alpha) = (1 - alpha) * alpha^j / (1 - alpha^W),   j = 0..W-1

    Truncation matters: at alpha = 0.996 about 13.3% of the infinite EWMA mass
    lies beyond W = 504, and 22.0% at 0.997. "EWMA with alpha = 0.996" is not a
    complete specification without stating the renormalisation.

    j = 0 is the MOST RECENT observation.
    """
    if not (0.0 < alpha <= 1.0):
        raise ValueError(f"alpha must be in (0, 1], got {alpha}")
    if alpha == 1.0:
        # exact equal-weight limit; the general formula is 0/0 here
        return np.full(W, 1.0 / W)
    j = np.arange(W, dtype=float)
    w = (1.0 - alpha) * alpha ** j / (1.0 - alpha ** W)
    return w / w.sum()          # guard against float drift; analytically already 1


def kish_ess(w: np.ndarray) -> float:
    """N_eff = 1 / sum_j w_j^2, computed from the ACTUAL truncated weights.

    NOT the infinite-horizon (1+a)/(1-a): at alpha = 0.996 the true finite-window
    value is 382.1, not 499.0. The rev.2 "499 ~ 504" argument was withdrawn.
    """
    return float(1.0 / np.sum(np.asarray(w, dtype=float) ** 2))


# --------------------------------------------------------------------------
# 3.2  EW covariance and the constant-correlation target
# --------------------------------------------------------------------------
def ew_covariance(X: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Weighted-mean-centred exponentially weighted covariance.

    X : (T, N) returns, row 0 = MOST RECENT (aligned with w).
    Returns (Sigma_EW, Y) where Y is the centred data used downstream.

        rbar_w = sum_j w_j r_(t-j)
        Sigma  = sum_j w_j (r_(t-j) - rbar_w)(r_(t-j) - rbar_w)'
    """
    X = np.asarray(X, dtype=float)
    w = np.asarray(w, dtype=float)
    if X.shape[0] != len(w):
        raise ValueError(f"X has {X.shape[0]} rows but {len(w)} weights")
    mean_w = w @ X                       # (N,)
    Y = X - mean_w                       # (T, N) centred
    S = (Y * w[:, None]).T @ Y           # (N, N)
    return 0.5 * (S + S.T), Y            # symmetrise against float asymmetry


def constant_correlation_target(S: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf (2004, JPM 'Honey') constant-correlation target.

        F_ii = s_ii
        F_ik = rbar * sqrt(s_ii * s_kk),   i != k

    where rbar is the average off-diagonal sample correlation implied by S.
    """
    S = np.asarray(S, dtype=float)
    N = S.shape[0]
    sd = np.sqrt(np.maximum(np.diag(S), 1e-300))
    outer = np.outer(sd, sd)
    R = S / outer
    off = ~np.eye(N, dtype=bool)
    rbar = float(R[off].mean()) if N > 1 else 0.0
    F = rbar * outer
    np.fill_diagonal(F, np.diag(S))
    return F, rbar


# --------------------------------------------------------------------------
# 3.3  Weighted shrinkage intensity
# --------------------------------------------------------------------------
@dataclass
class ShrinkageDiagnostics:
    pi_hat: float
    rho_hat: float
    gamma_hat: float
    kappa_hat: float
    delta: float
    n_eff: float
    rbar: float


def _weighted_intensity(Y: np.ndarray, w: np.ndarray, S: np.ndarray,
                        F: np.ndarray, rbar: float,
                        n_eff: float) -> ShrinkageDiagnostics:
    """The weighted analogues of Honey's pi, rho, gamma, kappa, delta.

    Every (1/T) sum_t in Honey is replaced by sum_j w_j; T is replaced by
    N_eff,504. See the epistemic label at the top of this module.
    """
    Y = np.asarray(Y, dtype=float)
    w = np.asarray(w, dtype=float)
    N = S.shape[0]

    # pi_ik = sum_j w_j [ y_ji y_jk - s_ik ]^2
    prod = Y[:, :, None] * Y[:, None, :]            # (T, N, N)
    dev = prod - S[None, :, :]
    pi_mat = np.einsum("t,tik->ik", w, dev ** 2)
    pi_hat = float(pi_mat.sum())

    # theta_ii,ik = sum_j w_j [ y_ji^2 - s_ii ] [ y_ji y_jk - s_ik ]
    diag_dev = Y ** 2 - np.diag(S)[None, :]         # (T, N)
    theta = np.einsum("t,ti,tik->ik", w, diag_dev, dev)   # theta[i,k] = theta_ii,ik

    # theta_kk,ik == theta[k, i]  (s is symmetric), so use theta.T
    sd = np.sqrt(np.maximum(np.diag(S), 1e-300))
    ratio = np.outer(1.0 / sd, sd)                  # ratio[i,k] = sd_k / sd_i
    term = ratio * theta + ratio.T * theta.T
    off = ~np.eye(N, dtype=bool)
    rho_hat = float(np.trace(pi_mat) + (rbar / 2.0) * term[off].sum())

    gamma_hat = float(np.sum((F - S) ** 2))

    if gamma_hat <= 0.0:
        kappa_hat, delta = 0.0, 0.0
    else:
        kappa_hat = (pi_hat - rho_hat) / gamma_hat
        delta = float(np.clip(kappa_hat / n_eff, 0.0, 1.0))

    return ShrinkageDiagnostics(pi_hat, rho_hat, gamma_hat, kappa_hat,
                                delta, n_eff, rbar)


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def ew_constant_correlation_shrinkage(
        X: np.ndarray,
        alpha: float = ALPHA_PRIMARY,
        return_diagnostics: bool = False):
    """Sigma_EW-LS = (1 - delta) Sigma_EW + delta F.

    X : (T, N) returns with row 0 the MOST RECENT observation. T is the window;
        the caller supplies exactly W rows (no second window is used).

    All inputs are through t only. No future observation enters.
    """
    X = np.asarray(X, dtype=float)
    T = X.shape[0]
    w = ew_weights(alpha, T)
    n_eff = kish_ess(w)

    S, Y = ew_covariance(X, w)
    F, rbar = constant_correlation_target(S)
    d = _weighted_intensity(Y, w, S, F, rbar, n_eff)

    Sigma = (1.0 - d.delta) * S + d.delta * F
    Sigma = 0.5 * (Sigma + Sigma.T)
    return (Sigma, d) if return_diagnostics else Sigma


def reference_constant_correlation_shrinkage(X: np.ndarray) -> np.ndarray:
    """EQUAL-WEIGHT reference: ordinary constant-correlation Ledoit-Wolf.

    Independent code path used by validation test 1: as alpha -> 1 the weighted
    estimator must converge to this. Written separately (not by calling the
    weighted routine with uniform weights) so the test has real content.
    """
    X = np.asarray(X, dtype=float)
    T, N = X.shape
    Y = X - X.mean(axis=0)
    S = (Y.T @ Y) / T
    S = 0.5 * (S + S.T)

    sd = np.sqrt(np.maximum(np.diag(S), 1e-300))
    outer = np.outer(sd, sd)
    R = S / outer
    off = ~np.eye(N, dtype=bool)
    rbar = float(R[off].mean()) if N > 1 else 0.0
    F = rbar * outer
    np.fill_diagonal(F, np.diag(S))

    prod = Y[:, :, None] * Y[:, None, :]
    dev = prod - S[None, :, :]
    pi_mat = dev.__pow__(2).mean(axis=0)
    pi_hat = float(pi_mat.sum())

    diag_dev = Y ** 2 - np.diag(S)[None, :]
    theta = np.einsum("ti,tik->ik", diag_dev, dev) / T

    ratio = np.outer(1.0 / sd, sd)
    term = ratio * theta + ratio.T * theta.T
    rho_hat = float(np.trace(pi_mat) + (rbar / 2.0) * term[off].sum())

    gamma_hat = float(np.sum((F - S) ** 2))
    delta = 0.0 if gamma_hat <= 0 else float(
        np.clip(((pi_hat - rho_hat) / gamma_hat) / T, 0.0, 1.0))

    Sigma = (1.0 - delta) * S + delta * F
    return 0.5 * (Sigma + Sigma.T)
