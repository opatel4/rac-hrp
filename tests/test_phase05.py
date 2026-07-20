"""
Phase 0.5 test suite.

These are not decoration. Each test pins a property the paper's claims depend on.
If one of these breaks, a number in the paper is wrong.

    python -m pytest tests/ -v      (or just: python tests/test_phase05.py)
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.config import Config, select_cov_window
from rac_hrp.core.covariance import (nonlinear_shrinkage, linear_shrinkage,
                                     sample_cov, cov_to_corr)
from rac_hrp.core.pca_mp import spectrum, absorption_ratio, mp_upper_edge
from rac_hrp.core.clustering import build_tree, cluster_labels, adjusted_rand_index
from rac_hrp.core.allocators import (hrp_weights, erc_weights, equal_weight,
                                     risk_contributions)
from rac_hrp.backtest.folds import FoldGenerator, TestRegionLock
from rac_hrp.backtest.metrics import sharpe


def _factor_data(N=80, T=600, k=3, seed=0):
    rng = np.random.default_rng(seed)
    B = rng.normal(0, 1, (N, k))
    Sig = B @ B.T * 0.02 + np.diag(rng.uniform(0.5, 1.5, N))
    X = rng.standard_normal((T, N)) @ np.linalg.cholesky(Sig).T
    return X, Sig


# --------------------------------------------------------------------------
# D3 -- covariance
# --------------------------------------------------------------------------
def test_nls_is_positive_definite():
    X, _ = _factor_data()
    S = nonlinear_shrinkage(X)
    assert np.all(np.linalg.eigvalsh(S) > 0), "NLS must be PD -- HRP inverts diagonals"


def test_nls_is_symmetric():
    X, _ = _factor_data()
    S = nonlinear_shrinkage(X)
    assert np.allclose(S, S.T, atol=1e-12)


def test_nls_beats_sample_and_linear():
    """The reason D3 chose nonlinear over the 2004 linear estimator."""
    X, Sig = _factor_data(N=100, T=150)     # N/T = 0.67, the D4 boundary
    f = lambda A: np.linalg.norm(A - Sig, "fro")
    s, l, n = f(sample_cov(X)), f(linear_shrinkage(X)), f(nonlinear_shrinkage(X))
    assert n < s, "NLS must beat the sample covariance"
    assert n < l, "NLS must beat linear shrinkage at N/T=0.67, or D3 is unjustified"


def test_nls_improves_conditioning():
    X, _ = _factor_data(N=100, T=150)
    assert np.linalg.cond(nonlinear_shrinkage(X)) < np.linalg.cond(sample_cov(X))


# --------------------------------------------------------------------------
# D2 -- Marchenko-Pastur
# --------------------------------------------------------------------------
def test_mp_retains_nothing_on_pure_noise():
    """The core claim of D2: on i.i.d. noise there is no structure, and MP must
    say so. A retention rule that finds factors in noise is worthless."""
    rng = np.random.default_rng(3)
    N, W = 100, 750
    X = rng.standard_normal((W, N))
    sp = spectrum(sample_cov(X), W, min_components=0)
    assert sp.k <= 2, f"MP retained {sp.k} components from pure noise"


def test_mp_recovers_injected_factors():
    X, _ = _factor_data(N=100, T=750, k=5, seed=11)
    sp = spectrum(nonlinear_shrinkage(X), 750, min_components=0)
    assert 2 <= sp.k <= 7, f"MP found k={sp.k}, expected ~5"


def test_mp_edge_grows_with_q():
    assert mp_upper_edge(0.5) > mp_upper_edge(0.1)


def test_absorption_ratio_bounds_and_monotonicity():
    X, _ = _factor_data()
    sp = spectrum(nonlinear_shrinkage(X), 600)
    ar = absorption_ratio(sp)
    assert 0.0 < ar <= 1.0
    # AR is mechanically increasing in k -- this is exactly why k is frozen
    # per fold (see config NOTE). If this assertion ever fails, the freeze is
    # unnecessary; while it holds, the freeze is mandatory.
    assert absorption_ratio(sp, k=10) > absorption_ratio(sp, k=2)


# --------------------------------------------------------------------------
# allocators
# --------------------------------------------------------------------------
def test_hrp_weights_valid():
    X, _ = _factor_data()
    cov = nonlinear_shrinkage(X)
    sp = spectrum(cov, 600)
    _, order, _ = build_tree(cov, sp, space="pca")
    w = hrp_weights(cov, order)
    assert abs(w.sum() - 1.0) < 1e-10
    assert np.all(w >= 0), "long-only violated"


def test_hrp_is_permutation_invariant():
    """Relabelling the assets must not change ANY asset's weight.

    This fails without a canonical leaf order, because HRP bisects the leaf list
    by position and the dendrogram admits 2^(N-1) valid leaf orders. See the long
    comment in clustering.build_tree: an unstable leaf order manufactures turnover
    that has nothing to do with the regime, which would directly contaminate this
    project's central claim and its transaction-cost analysis.
    """
    X, _ = _factor_data(seed=5)
    cov = nonlinear_shrinkage(X)
    N = cov.shape[0]
    sp = spectrum(cov, 600)
    _, order, _ = build_tree(cov, sp, space="pca")
    w1 = hrp_weights(cov, order)

    p = np.random.default_rng(9).permutation(N)
    cov2 = cov[np.ix_(p, p)]
    sp2 = spectrum(cov2, 600)
    _, order2, _ = build_tree(cov2, sp2, space="pca")
    w2 = hrp_weights(cov2, order2)

    w2_orig = np.empty(N)
    w2_orig[p] = w2                       # map back to original asset ids
    assert np.allclose(w1, w2_orig, atol=1e-10), (
        f"HRP weights depend on column order (max diff "
        f"{np.abs(w1 - w2_orig).max():.2e}). The leaf order is not canonical.")


def test_noncanonical_order_is_actually_unstable():
    """The negative control for the test above: confirm the instability is real
    and that optimal_leaf_ordering is what removes it (rather than the test
    passing for some unrelated reason)."""
    X, _ = _factor_data(seed=5)
    cov = nonlinear_shrinkage(X)
    N = cov.shape[0]
    sp = spectrum(cov, 600)
    _, order, _ = build_tree(cov, sp, space="pca", canonical_order=False)
    w1 = hrp_weights(cov, order)

    p = np.random.default_rng(9).permutation(N)
    cov2 = cov[np.ix_(p, p)]
    sp2 = spectrum(cov2, 600)
    _, order2, _ = build_tree(cov2, sp2, space="pca", canonical_order=False)
    w2 = hrp_weights(cov2, order2)
    w2_orig = np.empty(N)
    w2_orig[p] = w2
    assert not np.allclose(w1, w2_orig, atol=1e-10), (
        "Expected non-canonical ordering to be permutation-dependent. If this "
        "now passes, scipy changed and the canonical-order fix may be moot.")


def test_erc_equalises_risk_contributions():
    """The definition of ERC. If this fails, the benchmark is not ERC."""
    X, _ = _factor_data()
    cov = nonlinear_shrinkage(X)
    rc = risk_contributions(cov, erc_weights(cov))
    assert rc.max() - rc.min() < 1e-6, f"risk contributions not equal: {rc.max()-rc.min():.2e}"


def test_erc_on_identity_is_equal_weight():
    cov = np.eye(20)
    assert np.allclose(erc_weights(cov), equal_weight(cov), atol=1e-8)


# --------------------------------------------------------------------------
# clustering
# --------------------------------------------------------------------------
def test_ari_bounds():
    a = np.array([1, 1, 2, 2, 3, 3])
    assert adjusted_rand_index(a, a) == 1.0
    assert abs(adjusted_rand_index(a, np.array([1, 2, 3, 1, 2, 3]))) < 0.5


def test_clustering_finds_planted_blocks():
    """Two genuinely separate blocks must land in separate clusters."""
    rng = np.random.default_rng(2)
    N, T = 40, 800
    f1, f2 = rng.standard_normal(T), rng.standard_normal(T)
    X = np.column_stack([
        np.column_stack([f1 * 1.0 + rng.standard_normal(T) * 0.3 for _ in range(20)]),
        np.column_stack([f2 * 1.0 + rng.standard_normal(T) * 0.3 for _ in range(20)]),
    ])
    cov = nonlinear_shrinkage(X)
    sp = spectrum(cov, T)
    Z, _, _ = build_tree(cov, sp, space="pca")
    lab = cluster_labels(Z, 2)
    truth = np.array([0] * 20 + [1] * 20)
    assert adjusted_rand_index(lab, truth) > 0.9


# --------------------------------------------------------------------------
# D4 -- window rule
# --------------------------------------------------------------------------
def test_cov_window_rule():
    assert select_cov_window(100) == 504        # 100/504 = 0.198
    assert select_cov_window(400) == 756        # 400/504 = 0.79 > .67; 400/756 = 0.53
    assert select_cov_window(500) == 756        # 500/756 = 0.66 <= 0.67
    try:
        select_cov_window(2000)
        assert False, "should refuse: no window satisfies the cap"
    except ValueError:
        pass


# --------------------------------------------------------------------------
# D10 -- folds, purge, embargo, single-touch
# --------------------------------------------------------------------------
def _cal():
    return pd.bdate_range("1995-01-02", "2025-11-28")


def test_folds_have_no_overlap_and_honour_purge():
    cfg = Config(cov_window=504)
    fg = FoldGenerator(_cal(), cfg)
    folds = fg.dev_folds()
    assert len(folds) == cfg.n_dev_folds
    for f in folds:
        assert len(np.intersect1d(f.train_pos, f.test_pos)) == 0
        gap = f.test_pos[0] - f.train_pos[-1] - 1
        assert gap >= cfg.purge_days, f"purge gap {gap} < {cfg.purge_days}"


def test_folds_never_enter_the_test_region():
    cfg = Config(cov_window=504)
    fg = FoldGenerator(_cal(), cfg)
    for f in fg.dev_folds():
        assert f.test_pos.max() <= fg.dev_end_pos
        assert f.train_pos.max() <= fg.dev_end_pos


def test_test_region_is_locked():
    cfg = Config(cov_window=504)
    fg = FoldGenerator(_cal(), cfg)
    try:
        fg.test_fold()
        assert False, "test region must be locked by default"
    except PermissionError:
        pass
    fg.lock.unlock("unit test")
    assert fg.test_fold().label.startswith("TEST")


def test_purge_is_in_trading_days_not_calendar_days():
    """Position-based, per the roadmap. A 21-position purge must be exactly 21
    rows of the trading calendar, whatever the calendar dates happen to be."""
    cfg = Config(cov_window=504, purge_days=21)
    cal = _cal()
    fg = FoldGenerator(cal, cfg)
    f = fg.dev_folds()[1]
    assert int(f.test_pos[0] - f.train_pos[-1] - 1) == 21


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def test_sharpe_uses_excess_returns():
    idx = pd.bdate_range("2020-01-01", periods=500)
    r = pd.Series(0.001, index=idx)
    rf = pd.Series(0.001, index=idx)
    assert abs(sharpe(r, rf)) < 1e-9 or np.isnan(sharpe(r, rf))
    assert sharpe(r, None) > 0    # raw returns would show a "Sharpe". They must not.


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            fails += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            fails += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
