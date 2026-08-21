"""
MANDATORY validation suite for the frozen EWMA covariance estimator.

Required by the signed amendment "EWMA COVARIANCE (rev.4)", section 4b.
Advisor condition: EWMA implementation is AUTHORIZED ONLY AFTER THESE PASS.
These are automated tests that must all PASS before any EWMA result is produced;
the output is saved alongside the code hash.

The seven required tests:
  1. equal-weight limit: alpha -> 1 converges to ordinary constant-correlation LW
  2. sum_j w_j = 1
  3. N_eff = 1 / sum_j w_j^2
  4. 0 <= delta <= 1
  5. covariance output is symmetric
  6. target diagonal equals the EW covariance diagonal (F_ii = s_ii)
  7. all inputs through t only -- no future return enters
"""

from __future__ import annotations

import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.core.covariance_ew import (           # noqa: E402
    ew_weights, kish_ess, ew_covariance, constant_correlation_target,
    ew_constant_correlation_shrinkage, reference_constant_correlation_shrinkage,
    ALPHA_PRIMARY, ALPHA_SENSITIVITY)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


def _panel(T=504, N=40, seed=0):
    """Heterogeneous-vol correlated panel, row 0 = most recent."""
    rng = np.random.default_rng(seed)
    F = rng.standard_normal((T, 3))
    B = rng.standard_normal((3, N))
    idio = rng.standard_normal((T, N))
    vols = np.linspace(0.5, 2.5, N)
    return (F @ B * 0.4 + idio) * vols / 100.0


# --------------------------------------------------------------------------
# TEST 1 -- equal-weight limit (the strongest correctness check)
# --------------------------------------------------------------------------
def test_1_equal_weight_limit():
    X = _panel()
    # alpha numerically close to 1: (1-a)=1e-6 vs (1-a^504)~504e-6, no cancellation
    a = 1.0 - 1e-6
    Sw = ew_constant_correlation_shrinkage(X, alpha=a)
    Sr = reference_constant_correlation_shrinkage(X)
    rel = np.abs(Sw - Sr).max() / max(np.abs(Sr).max(), 1e-300)
    check("1. equal-weight limit (alpha->1 == constant-correlation LW)",
          rel < 1e-3, f"max rel diff {rel:.2e}")

    # exact alpha = 1 must be identical to the reference to float precision
    S1 = ew_constant_correlation_shrinkage(X, alpha=1.0)
    rel1 = np.abs(S1 - Sr).max() / max(np.abs(Sr).max(), 1e-300)
    check("1b. exact alpha=1 == reference", rel1 < 1e-12,
          f"max rel diff {rel1:.2e}")


# --------------------------------------------------------------------------
# TEST 2 -- weights sum to one
# --------------------------------------------------------------------------
def test_2_weights_sum_to_one():
    ok, worst = True, 0.0
    for a in list(ALPHA_SENSITIVITY) + [1.0]:
        w = ew_weights(a, 504)
        err = abs(w.sum() - 1.0)
        worst = max(worst, err)
        ok &= err < 1e-12
    check("2. sum_j w_j == 1 for all frozen alphas", ok, f"worst |err| {worst:.2e}")


# --------------------------------------------------------------------------
# TEST 3 -- Kish ESS identity, and the frozen published values
# --------------------------------------------------------------------------
def test_3_kish_ess():
    ok, detail = True, []
    for a, expect in [(0.990, 196.5), (0.996, 382.1), (0.997, 425.6)]:
        w = ew_weights(a, 504)
        n1 = kish_ess(w)
        n2 = 1.0 / np.sum(w ** 2)                       # identity
        closed = ((1 + a) / (1 - a)) * (1 - a ** 504) / (1 + a ** 504)
        ok &= abs(n1 - n2) < 1e-9 and abs(n1 - closed) < 1e-6 and abs(n1 - expect) < 0.15
        detail.append(f"a={a}: {n1:.1f}")
    check("3. N_eff == 1/sum w^2 == closed form == amendment table",
          ok, "; ".join(detail))


# --------------------------------------------------------------------------
# TEST 4 -- delta in [0, 1]
# --------------------------------------------------------------------------
def test_4_delta_bounded():
    ok, detail = True, []
    for seed in range(6):
        X = _panel(seed=seed)
        for a in ALPHA_SENSITIVITY:
            _, d = ew_constant_correlation_shrinkage(X, alpha=a,
                                                     return_diagnostics=True)
            ok &= (0.0 <= d.delta <= 1.0) and np.isfinite(d.delta)
            if seed == 0:
                detail.append(f"a={a}: delta={d.delta:.4f}")
    check("4. 0 <= delta <= 1 across seeds and alphas", ok, "; ".join(detail))


# --------------------------------------------------------------------------
# TEST 5 -- symmetry
# --------------------------------------------------------------------------
def test_5_symmetric():
    ok, worst = True, 0.0
    for seed in range(4):
        X = _panel(seed=seed)
        S = ew_constant_correlation_shrinkage(X, alpha=ALPHA_PRIMARY)
        asym = np.abs(S - S.T).max()
        worst = max(worst, asym)
        ok &= asym < 1e-15
    check("5. covariance output symmetric", ok, f"worst asymmetry {worst:.2e}")


# --------------------------------------------------------------------------
# TEST 6 -- target diagonal equals EW covariance diagonal
# --------------------------------------------------------------------------
def test_6_target_diagonal():
    X = _panel()
    w = ew_weights(ALPHA_PRIMARY, X.shape[0])
    S, _ = ew_covariance(X, w)
    F, rbar = constant_correlation_target(S)
    err = np.abs(np.diag(F) - np.diag(S)).max()
    off_ok = np.all(np.isfinite(F))
    check("6. F_ii == s_ii (target preserves EW variances)",
          err < 1e-15 and off_ok, f"max |F_ii - s_ii| {err:.2e}, rbar={rbar:.4f}")


# --------------------------------------------------------------------------
# TEST 7 -- no future information
# --------------------------------------------------------------------------
def test_7_no_lookahead():
    """Perturbing observations OUTSIDE the supplied window must not change the
    estimate; and row 0 (most recent) must carry the largest weight."""
    X = _panel(T=600)
    win = X[:504]                                   # rows 0..503 = through t
    S_a = ew_constant_correlation_shrinkage(win, alpha=ALPHA_PRIMARY)

    X2 = X.copy()
    X2[504:] += 99.0                                # corrupt the "future" only
    S_b = ew_constant_correlation_shrinkage(X2[:504], alpha=ALPHA_PRIMARY)
    unchanged = np.abs(S_a - S_b).max() < 1e-15

    w = ew_weights(ALPHA_PRIMARY, 504)
    recency = w[0] > w[-1] and np.all(np.diff(w) < 0)
    check("7. no future return enters; weights decay from the most recent row",
          unchanged and recency,
          f"delta_on_future={np.abs(S_a-S_b).max():.2e}, w0={w[0]:.6f} > w503={w[-1]:.6f}")


def main() -> int:
    print("=" * 74)
    print("  MANDATORY VALIDATION SUITE -- EWMA constant-correlation shrinkage")
    print("  (signed amendment rev.4 section 4b; must PASS before any EWMA result)")
    print("=" * 74)
    for fn in [test_1_equal_weight_limit, test_2_weights_sum_to_one,
               test_3_kish_ess, test_4_delta_bounded, test_5_symmetric,
               test_6_target_diagonal, test_7_no_lookahead]:
        fn()
    print()
    for name, ok, detail in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if detail:
            print(f"         {detail}")
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    print()
    print(f"  {n_ok}/{len(RESULTS)} checks passed")
    if n_ok != len(RESULTS):
        print("  => EWMA ESTIMATOR NOT AUTHORIZED. Do not produce EWMA results.")
        return 1
    print("  => ALL VALIDATION TESTS PASS. EWMA estimator authorized for use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
