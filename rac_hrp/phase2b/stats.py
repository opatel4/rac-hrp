"""
Phase 2B statistical core.

Implements the Spearman rank-association test specified in PHASE2B_SPEC.md §1 and
the size / power / falsification checks required by §2.

This module is deliberately free of repo dependencies. It operates on two aligned
1-D arrays and knows nothing about covariance estimation, clustering, or the
trigger. Wiring it to the repo is a separate, mechanical step (see load_series
docstring at the bottom).

NOTE ON BLOCK LENGTH: this file contains a self-contained Politis-White
implementation so the module can be tested standalone. The repo already has a
validated Politis-White used by Phase 2A. PREFER THE REPO'S. Pass it in via the
`block_length` argument rather than relying on the one here.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

__all__ = [
    "spearman_rho",
    "politis_white_block_length",
    "circular_block_indices",
    "bootstrap_test",
    "size_check",
    "power_curve",
    "falsification_check",
]


# ----------------------------------------------------------------------------
# statistic
# ----------------------------------------------------------------------------

def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation. Ties handled by average ranks."""
    return float(stats.spearmanr(x, y).statistic)


# ----------------------------------------------------------------------------
# block length
# ----------------------------------------------------------------------------

def politis_white_block_length(x: np.ndarray, k_max: int | None = None) -> int:
    """
    Politis & White (2004) automatic block length for the circular block bootstrap,
    with the Patton, Politis & White (2009) correction.

    Returns b >= 1. Prefer the repo's validated implementation over this one.
    """
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return 1

    x = x - x.mean()
    if np.allclose(x, 0.0):
        return 1

    m_max = int(np.ceil(np.sqrt(n))) + int(np.ceil(3.0 * np.sqrt(np.log10(n))))
    m_max = min(m_max, n - 1)
    if k_max is None:
        k_max = max(5, int(np.ceil(np.sqrt(np.log10(n)))))

    # autocorrelations
    var = np.dot(x, x) / n
    rho = np.empty(m_max + 1)
    rho[0] = 1.0
    for lag in range(1, m_max + 1):
        rho[lag] = np.dot(x[:-lag], x[lag:]) / (n * var)

    # smallest m such that the next k_max correlations are all negligible
    crit = 2.0 * np.sqrt(np.log10(n) / n)
    m_hat = m_max
    for m in range(1, m_max + 1):
        hi = min(m + k_max, m_max)
        if np.all(np.abs(rho[m:hi + 1]) < crit):
            m_hat = m - 1
            break
    m_hat = max(m_hat, 1)
    M = min(2 * m_hat, m_max)

    # flat-top lag window
    lags = np.arange(1, M + 1)
    lam = np.ones_like(lags, dtype=float)
    frac = np.abs(lags) / M
    mid = (frac >= 0.5) & (frac <= 1.0)
    lam[mid] = 2.0 * (1.0 - frac[mid])
    lam[frac > 1.0] = 0.0

    g_hat = 2.0 * np.sum(lam * lags * rho[1:M + 1]) * var
    acov0 = var
    acov = rho[1:M + 1] * var
    G0 = acov0 + 2.0 * np.sum(lam * acov)
    d_hat = (4.0 / 3.0) * G0 ** 2

    if d_hat <= 0 or not np.isfinite(d_hat) or not np.isfinite(g_hat):
        return 1

    b = ((2.0 * g_hat ** 2) / d_hat) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    b_max = int(np.ceil(min(3.0 * np.sqrt(n), n / 3.0)))
    return int(np.clip(np.round(b), 1, max(b_max, 1)))


# ----------------------------------------------------------------------------
# resampling
# ----------------------------------------------------------------------------

def circular_block_indices(n: int, b: int, rng: np.random.Generator) -> np.ndarray:
    """Index vector of length n drawn as circular blocks of length b."""
    b = max(1, min(b, n))
    n_blocks = int(np.ceil(n / b))
    starts = rng.integers(0, n, size=n_blocks)
    idx = (starts[:, None] + np.arange(b)[None, :]).ravel() % n
    return idx[:n]


# ----------------------------------------------------------------------------
# the test
# ----------------------------------------------------------------------------

def bootstrap_test(
    s: np.ndarray,
    vi: np.ndarray,
    *,
    seed: int,
    replicates: int = 10_000,
    block_length: int | None = None,
) -> dict:
    """
    One-sided block-bootstrap test of H0: rho_s <= 0.

    The pair (s_t, vi_t) is resampled jointly in circular blocks, preserving both
    serial dependence and the cross-series pairing. The resulting distribution is
    centred on the observed statistic, giving

        p = (1 + #{rho* - rho_hat >= rho_hat}) / (B_kept + 1)

    which is the Phase 2A convention.
    """
    s = np.asarray(s, dtype=float)
    vi = np.asarray(vi, dtype=float)
    if s.shape != vi.shape:
        raise ValueError(f"length mismatch: s={s.shape}, vi={vi.shape}")
    n = s.size

    if block_length is None:
        b_s = politis_white_block_length(s)
        b_v = politis_white_block_length(vi)
        block_length = max(b_s, b_v)

    rho_hat = spearman_rho(s, vi)
    rng = np.random.default_rng(seed)

    reps = np.empty(replicates)
    reps.fill(np.nan)
    for i in range(replicates):
        idx = circular_block_indices(n, block_length, rng)
        ss, vv = s[idx], vi[idx]
        if np.all(ss == ss[0]) or np.all(vv == vv[0]):
            continue  # degenerate
        reps[i] = spearman_rho(ss, vv)

    kept = reps[np.isfinite(reps)]
    b_kept = kept.size
    if b_kept == 0:
        raise RuntimeError("all bootstrap replicates degenerate")

    centred = kept - rho_hat
    p = (1 + int(np.sum(centred >= rho_hat))) / (b_kept + 1)

    return {
        "rho": rho_hat,
        "p": p,
        "n": n,
        "block_length": int(block_length),
        "replicates_kept": b_kept,
        "replicates_requested": replicates,
        "p_floor": 1.0 / (b_kept + 1),
        "seed": seed,
    }


# ----------------------------------------------------------------------------
# §2 checks
# ----------------------------------------------------------------------------

def size_check(
    s: np.ndarray,
    vi: np.ndarray,
    *,
    seed: int,
    reps: int = 2_000,
    replicates: int = 2_000,
    block_length: int | None = None,
    alpha: float = 0.05,
) -> dict:
    """
    Empirical size under a true null.

    Each replication resamples s and vi in circular blocks with INDEPENDENT index
    vectors. That preserves each series' own serial dependence while destroying any
    association between them, so H0 holds by construction.

    Spec §2 fails this check if empirical size exceeds 0.10.
    """
    s = np.asarray(s, dtype=float)
    vi = np.asarray(vi, dtype=float)
    n = s.size

    if block_length is None:
        block_length = max(
            politis_white_block_length(s), politis_white_block_length(vi)
        )

    rng = np.random.default_rng(seed)
    rejects = 0
    for r in range(reps):
        s_star = s[circular_block_indices(n, block_length, rng)]
        v_star = vi[circular_block_indices(n, block_length, rng)]
        out = bootstrap_test(
            s_star, v_star,
            seed=int(rng.integers(0, 2**31 - 1)),
            replicates=replicates,
            block_length=block_length,
        )
        rejects += int(out["p"] < alpha)

    size = rejects / reps
    return {
        "empirical_size": size,
        "mc_se": float(np.sqrt(size * (1 - size) / reps)),
        "nominal": alpha,
        "reps": reps,
        "block_length": int(block_length),
        "pass": size <= 0.10,
    }


def _plant(s: np.ndarray, vi: np.ndarray, c: float) -> np.ndarray:
    """Add a monotone signal of strength c, scaled to vi's own spread."""
    z = stats.rankdata(s)
    z = (z - z.mean()) / z.std(ddof=0)
    return vi + c * np.std(vi, ddof=1) * z


def power_curve(
    s: np.ndarray,
    vi: np.ndarray,
    *,
    seed: int,
    c_grid=(0.0, 0.09, 0.15, 0.18, 0.21, 0.24, 0.30, 0.45),
    reps: int = 400,
    replicates: int = 1_000,
    block_length: int | None = None,
    alpha: float = 0.05,
) -> list[dict]:
    """
    Power against planted monotone association.

    Each replication block-resamples vi and s independently (true null), then adds a
    signal proportional to the standardised ranks of s. Reports achieved Spearman
    rho alongside power so MDE can be read on the rho scale, which is what the spec
    thresholds on (MDE80 <= 0.20).
    """
    s = np.asarray(s, dtype=float)
    vi = np.asarray(vi, dtype=float)
    n = s.size

    if block_length is None:
        block_length = max(
            politis_white_block_length(s), politis_white_block_length(vi)
        )

    rng = np.random.default_rng(seed)
    rows = []
    for c in c_grid:
        rejects, rhos = 0, []
        for _ in range(reps):
            s_star = s[circular_block_indices(n, block_length, rng)]
            v_star = vi[circular_block_indices(n, block_length, rng)]
            v_star = _plant(s_star, v_star, c)
            out = bootstrap_test(
                s_star, v_star,
                seed=int(rng.integers(0, 2**31 - 1)),
                replicates=replicates,
                block_length=block_length,
            )
            rejects += int(out["p"] < alpha)
            rhos.append(out["rho"])
        rows.append({
            "c": c,
            "achieved_rho": float(np.mean(rhos)),
            "power": rejects / reps,
            "reps": reps,
        })
    return rows


def mde80(curve: list[dict]) -> float | None:
    """
    Smallest achieved rho at which power reaches 0.80, by linear interpolation.

    Sensitive to grid resolution: a coarse grid straddling 0.80 interpolates across
    a convex stretch of the power curve and overestimates. Verified on synthetic
    data, where a five-point grid gave 0.216 and a refined grid gave 0.183 for the
    same setup. Keep the grid dense near the crossing.
    """
    pts = sorted(((r["achieved_rho"], r["power"]) for r in curve))
    for (r0, p0), (r1, p1) in zip(pts, pts[1:]):
        if p0 < 0.80 <= p1:
            if p1 == p0:
                return r1
            return r0 + (0.80 - p0) * (r1 - r0) / (p1 - p0)
    return None if pts[-1][1] < 0.80 else pts[0][0]


def falsification_check(
    environments: list[tuple[np.ndarray, np.ndarray]],
    *,
    seed: int,
    replicates: int = 2_000,
    alpha: float = 0.05,
) -> dict:
    """
    Run the test end to end on the Phase 2D structureless null environments.

    `environments` is a list of (s, vi) pairs produced by the existing structureless
    generators. Spec §2 fails if the test is significant in more than 10% of them.
    """
    rng = np.random.default_rng(seed)
    results = []
    for s_env, vi_env in environments:
        out = bootstrap_test(
            s_env, vi_env,
            seed=int(rng.integers(0, 2**31 - 1)),
            replicates=replicates,
        )
        results.append(out)
    rate = float(np.mean([r["p"] < alpha for r in results]))
    return {
        "rejection_rate": rate,
        "n_environments": len(results),
        "alpha": alpha,
        "pass": rate <= 0.10,
        "detail": results,
    }


# ----------------------------------------------------------------------------
# repo wiring — TO BE IMPLEMENTED AGAINST THE ACTUAL REPO
# ----------------------------------------------------------------------------

def load_series():
    """
    Return (s, vi_h5, vi_h1, dates) aligned on the Phase 2B eligible set.

        s      : |dAR_t| / sigma_hat_t  on the eligible set
        vi_h5  : VI between clusterings at t and t-5, on the intersection of the
                 corresponding universes, recomputed at EVERY eligible rebalance
                 including those a live strategy would skip
        vi_h1  : same at h=1, reported but non-gating
        dates  : rebalance dates, for the artefact record

    Implementation notes for whoever wires this up:
      - Reuse the existing clustering and VI code. Do not reimplement either.
      - Report n actually returned against the 233 expected. They may differ at the
        h=5 boundary; state the difference, do not silently absorb it.
      - This function must not import anything on the return-performance path.
    """
    raise NotImplementedError("wire to repo; see PHASE2B_SPEC.md §4")
