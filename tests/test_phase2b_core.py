"""Unit tests for the Phase 2B statistical core.

SYNTHETIC DATA ONLY. Nothing here loads a panel, builds a universe, or touches
the observed (s, VI) series. These tests exercise the machinery, not the study:
they must stay runnable in CI without the CRSP data, which lives outside the
repo.

THIS IS NOT ANY OF THE SECTION 2 CHECKS. Size, power and falsification are
separate harnesses run against the real series and gated by the spec. A unit
test asserting that `bootstrap_test` returns a p in (0, 1] says nothing about
whether the procedure is correctly sized on this dependence structure, and
passing here confers nothing on section 2.

EVERY SEED IS FIXED. Both the data generation and the bootstrap draw take
explicit seeds, so each assertion below is deterministic rather than
probabilistic. A failure here is a real regression, not a bad roll.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy import stats as sps

from rac_hrp.phase2b.stats import (_plant, bootstrap_test,
                                   circular_block_indices, mde80, spearman_rho)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _ar1(n: int, phi: float, rng: np.random.Generator) -> np.ndarray:
    """Stationary AR(1), started from its unconditional distribution."""
    e = rng.normal(size=n)
    x = np.empty(n)
    x[0] = e[0] / np.sqrt(1.0 - phi ** 2)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


# --------------------------------------------------------------------------
# circular_block_indices
# --------------------------------------------------------------------------
@pytest.mark.parametrize("n,b", [(50, 1), (50, 7), (233, 13), (233, 19), (60, 60)])
def test_circular_block_indices_shape_and_range(n, b):
    idx = circular_block_indices(n, b, np.random.default_rng(0))
    assert idx.shape == (n,)
    assert idx.min() >= 0 and idx.max() < n


@pytest.mark.parametrize("n,b", [(50, 7), (233, 13), (233, 19)])
def test_circular_block_indices_blocks_are_contiguous_mod_n(n, b):
    """Within a block, consecutive positions must step by +1 modulo n.

    Block k occupies output positions [k*b, (k+1)*b), so j and j+1 are in the
    same block exactly when (j+1) % b != 0. Wrap-around is the point of the
    circular bootstrap and is why the comparison is mod n.
    """
    idx = circular_block_indices(n, b, np.random.default_rng(1))
    for j in range(n - 1):
        if (j + 1) % b:
            assert idx[j + 1] == (idx[j] + 1) % n, f"break inside block at {j}"


def test_circular_block_indices_clamps_b():
    rng = np.random.default_rng(2)
    assert circular_block_indices(20, 999, rng).shape == (20,)   # b > n
    assert circular_block_indices(20, 0, rng).shape == (20,)     # b < 1


# --------------------------------------------------------------------------
# spearman_rho
# --------------------------------------------------------------------------
def test_spearman_rho_known_value():
    """Hand-computable case: sum d^2 = 4, n = 5 -> 1 - 6*4/(5*24) = 0.8."""
    x = np.array([1.0, 2, 3, 4, 5])
    y = np.array([2.0, 1, 4, 3, 5])
    assert spearman_rho(x, y) == pytest.approx(0.8)


def test_spearman_rho_perfect_monotone():
    x = np.arange(1.0, 21.0)
    assert spearman_rho(x, x) == pytest.approx(1.0)
    assert spearman_rho(x, -x) == pytest.approx(-1.0)


def test_spearman_rho_matches_scipy():
    rng = np.random.default_rng(3)
    x, y = rng.normal(size=80), rng.normal(size=80)
    assert spearman_rho(x, y) == pytest.approx(sps.spearmanr(x, y).statistic)


def test_spearman_rho_invariant_to_monotone_transform():
    """Rank correlation depends only on order, so any increasing map is free.

    This is the property the spec relies on when it chooses ranks over OLS: the
    heavy right tail of s_t changes the values but not the ordering.
    """
    rng = np.random.default_rng(4)
    x, y = rng.normal(size=120), rng.normal(size=120)
    base = spearman_rho(x, y)

    assert spearman_rho(np.exp(x), y) == pytest.approx(base)   # increasing
    assert spearman_rho(x, y ** 3) == pytest.approx(base)      # increasing, odd
    assert spearman_rho(np.exp(x), y ** 3) == pytest.approx(base)
    assert spearman_rho(-x, y) == pytest.approx(-base)         # decreasing flips


# --------------------------------------------------------------------------
# bootstrap_test -- contract
# --------------------------------------------------------------------------
def test_bootstrap_test_contract():
    rng = np.random.default_rng(5)
    s, vi = rng.normal(size=120), rng.normal(size=120)
    out = bootstrap_test(s, vi, seed=101, replicates=300)

    assert 0.0 < out["p"] <= 1.0
    assert out["p_floor"] == pytest.approx(1.0 / (out["replicates_kept"] + 1))
    assert out["p"] >= out["p_floor"]
    assert out["n"] == 120
    assert out["replicates_requested"] == 300
    assert 0 < out["replicates_kept"] <= 300
    assert out["seed"] == 101
    assert out["block_length"] >= 1


def test_bootstrap_test_is_deterministic_given_seed():
    rng = np.random.default_rng(6)
    s, vi = rng.normal(size=100), rng.normal(size=100)
    a = bootstrap_test(s, vi, seed=42, replicates=200)
    b = bootstrap_test(s, vi, seed=42, replicates=200)
    assert a == b

    c = bootstrap_test(s, vi, seed=43, replicates=200)
    assert c["rho"] == a["rho"]          # statistic is not seed-dependent
    assert c["p"] != a["p"] or c["replicates_kept"] != a["replicates_kept"]


def test_bootstrap_test_honours_explicit_block_length():
    rng = np.random.default_rng(7)
    s, vi = rng.normal(size=90), rng.normal(size=90)
    assert bootstrap_test(s, vi, seed=1, replicates=100,
                          block_length=7)["block_length"] == 7


def test_bootstrap_test_raises_on_length_mismatch():
    with pytest.raises(ValueError, match="length mismatch"):
        bootstrap_test(np.zeros(10), np.zeros(11), seed=1, replicates=10)


# --------------------------------------------------------------------------
# bootstrap_test -- behaviour
# --------------------------------------------------------------------------
def test_bootstrap_test_null_is_not_significant():
    """Two independent AR(1) series: no association to find.

    Serial dependence is present in each series, so this also exercises the
    block machinery rather than an i.i.d. shortcut. Seeds are fixed, so this
    is one deterministic draw and NOT a size check -- it cannot tell you the
    rejection rate, only that this particular null pair is not flagged.
    """
    rng = np.random.default_rng(20260901)
    s = _ar1(240, 0.6, rng)
    vi = _ar1(240, 0.6, rng)
    out = bootstrap_test(s, vi, seed=777, replicates=500)
    assert out["p"] > 0.05, f"independent AR(1) pair flagged, p = {out['p']}"


def test_bootstrap_test_strong_signal_is_significant():
    """A near-deterministic monotone pair pins p at its floor.

    With rho_hat ~ 1 the centred exceedance condition is rho* >= 2*rho_hat ~ 2,
    which no correlation can satisfy, so the count is exactly zero and
    p == p_floor. That makes the assertion exact rather than approximate.
    """
    rng = np.random.default_rng(8)
    s = np.sort(rng.normal(size=200))
    vi = s ** 3 + 1e-9 * rng.normal(size=200)
    out = bootstrap_test(s, vi, seed=99, replicates=400)

    assert out["rho"] > 0.99
    assert out["p"] == pytest.approx(out["p_floor"])
    assert out["p"] < 0.05


# --------------------------------------------------------------------------
# mde80
# --------------------------------------------------------------------------
def _curve(rhos, powers):
    return [{"achieved_rho": r, "power": p} for r, p in zip(rhos, powers)]


def test_mde80_interpolates():
    """Crossing between (0.10, 0.50) and (0.20, 0.90): 0.1 + 0.3*0.1/0.4."""
    got = mde80(_curve([0.10, 0.20], [0.50, 0.90]))
    assert got == pytest.approx(0.175)


def test_mde80_returns_none_when_power_never_reaches_080():
    assert mde80(_curve([0.05, 0.10, 0.20], [0.10, 0.30, 0.60])) is None


def test_mde80_handles_curve_already_above_080():
    """No crossing to interpolate; the smallest rho on the grid is returned."""
    assert mde80(_curve([0.10, 0.20], [0.85, 0.95])) == pytest.approx(0.10)


def test_mde80_is_monotone_in_the_curve():
    """Uniformly more power at every rho cannot raise the detectable effect."""
    rhos = [0.10, 0.20, 0.30]
    weak = mde80(_curve(rhos, [0.50, 0.70, 0.90]))
    strong = mde80(_curve(rhos, [0.60, 0.85, 0.95]))

    assert weak == pytest.approx(0.25)
    assert strong == pytest.approx(0.18)
    assert strong < weak


# --------------------------------------------------------------------------
# _plant
# --------------------------------------------------------------------------
def test_plant_increases_rho_monotonically_in_c():
    """The planted signal is what power_curve varies, so its dose-response
    must be monotone or the power curve is not reading an effect size."""
    rng = np.random.default_rng(9)
    s = rng.normal(size=300)
    vi = rng.normal(size=300)

    rhos = [spearman_rho(s, _plant(s, vi, c))
            for c in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)]

    for lo, hi in zip(rhos, rhos[1:]):
        assert hi > lo, f"rho not increasing in c: {rhos}"
    assert rhos[0] == pytest.approx(spearman_rho(s, vi))
    assert rhos[-1] > 0.9


def test_plant_at_zero_is_identity():
    rng = np.random.default_rng(10)
    s, vi = rng.normal(size=50), rng.normal(size=50)
    assert np.allclose(_plant(s, vi, 0.0), vi)
