"""
Automated tests for the frozen Phase 2 statistics.

Verifies the implementation against values fixed in the signed pre-registration
"PHASE 2 - PRE-REGISTRATION & CALIBRATION GATE (rev.5)". Any failure here means
the code no longer matches the frozen document.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rac_hrp.phase2.config import Phase2Config, AR_SIGMA_DDOF   # noqa: E402
from rac_hrp.phase2.stats import (                              # noqa: E402
    j_star, placebo_threshold, timing_variation, d_vi,
    circular_block_bootstrap_p, politis_white_block_length, holm_adjust)

E = 233
RESULTS: list[tuple[str, bool, str]] = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def test_adversarial_calendar_is_caught():
    """The failure mode that defeated the pre-phase-adjustment statistic."""
    T_odd = [j for j in range(E) if j % 2 == 1]
    js, (q, r) = j_star(T_odd, E)
    check("adversarial calendar trigger caught (J* = 1.000)",
          abs(js - 1.0) < 1e-12 and q == 2 and r == 1,
          f"J*={js:.4f} at q={q}, r={r}")

    # and it must NOT be caught if phase is ignored -- documents why phase matters
    js0, _ = j_star(T_odd, E, periods=[2, 3, 4, 6])
    single_phase = max(
        len(set(T_odd) & set(range(0, E, q))) /
        len(set(T_odd) | set(range(0, E, q))) for q in (2, 3, 4, 6))
    check("phase adjustment is what catches it",
          single_phase < 0.30 and js0 > 0.99,
          f"phase-blind J*={single_phase:.3f} vs phase-adjusted {js0:.3f}")


def test_placebo_reproduces_frozen_values():
    th112 = placebo_threshold(E, 112)          # full frozen 100,000 draws
    check("placebo 95th at |T|=112 == 0.3818 (frozen)",
          abs(th112 - 0.3818) < 0.0015, f"{th112:.4f}")
    th12 = placebo_threshold(E, 12, draws=20_000)
    check("threshold moves with event count (|T|=12 -> ~0.171)",
          abs(th12 - 0.1714) < 0.01 and th12 < th112, f"{th12:.4f}")


def test_placebo_is_deterministic():
    a = placebo_threshold(E, 70, draws=5_000)
    b = placebo_threshold(E, 70, draws=5_000)
    check("placebo is deterministic under the frozen seed", a == b, f"{a:.6f}")


def test_timing_on_perfect_calendar():
    ts = timing_variation([j for j in range(E) if j % 2 == 1])
    check("perfect calendar -> CV = 0, modal share = 1",
          abs(ts.cv_gap) < 1e-12 and abs(ts.modal_gap_share - 1.0) < 1e-12,
          f"CV={ts.cv_gap:.4f}, modal={ts.modal_gap_share:.4f}")


def test_bootstrap_null_calibration():
    ps = []
    for s in range(2000):
        rng = np.random.default_rng(1000 + s)
        vi = rng.standard_normal(E)
        fired = rng.random(E) < 0.48
        r = circular_block_bootstrap_p(vi, fired, seed=20260817 + 2000,
                                       replicates=600)
        if np.isfinite(r.p_value):
            ps.append(r.p_value)
    ps = np.array(ps)
    rate = float(np.mean(ps <= 0.05))
    check("bootstrap correctly calibrated under the null",
          abs(rate - 0.05) < 0.02,
          f"P(p<=0.05) = {rate:.3f} over 2000 null datasets "
          f"(B_boot=600; MC SE ~{(rate*(1-rate)/len(ps))**0.5:.4f})")


def test_bootstrap_detects_real_effect():
    rng = np.random.default_rng(7)
    vi = rng.standard_normal(E)
    fired = rng.random(E) < 0.48
    vi[fired] += 1.2
    r = circular_block_bootstrap_p(vi, fired, seed=20260817 + 2000, replicates=2000)
    check("bootstrap detects a real D_VI effect",
          r.d_hat > 0.5 and r.p_value < 0.01,
          f"D={r.d_hat:+.3f}, p={r.p_value:.4f}")


def test_bootstrap_deterministic():
    rng = np.random.default_rng(11)
    vi = rng.standard_normal(E)
    fired = rng.random(E) < 0.48
    a = circular_block_bootstrap_p(vi, fired, seed=123, replicates=500).p_value
    b = circular_block_bootstrap_p(vi, fired, seed=123, replicates=500).p_value
    check("bootstrap deterministic under a fixed seed", a == b, f"p={a:.5f}")


def test_politis_white():
    rng = np.random.default_rng(3)
    iid = rng.standard_normal(E)
    ar = np.zeros(E)
    for t in range(1, E):
        ar[t] = 0.85 * ar[t - 1] + rng.standard_normal()
    li, la = politis_white_block_length(iid), politis_white_block_length(ar)
    check("Politis-White distinguishes iid from serial dependence",
          li <= 3 and la > 5, f"iid L={li}, AR(1) rho=0.85 L={la}")


def test_holm():
    adj = holm_adjust({0.5: 0.01, 1.0: 0.04, 1.5: 0.03, 2.0: 0.20})
    mono = adj[0.5] <= adj[1.5] <= adj[1.0] <= adj[2.0]
    check("Holm adjusted, monotone, >= raw",
          abs(adj[0.5] - 0.04) < 1e-12 and mono,
          ", ".join(f"{g}:{v:.3f}" for g, v in sorted(adj.items())))


def test_frozen_config_values():
    c = Phase2Config()
    ok = (c.gamma_candidates == (0.5, 1.0, 1.5, 2.0)
          and c.firing_max == 0.40 and c.firing_min == 0.05
          and c.placebo_seed == 20260817 and c.placebo_draws == 100_000
          and c.bootstrap_replicates == 10_000
          and c.separation_periods == tuple(range(2, 13))
          and AR_SIGMA_DDOF == 1
          and c.bootstrap_seed_for(1.5) == 20260817 + 2000 + 2)
    check("frozen config matches the signed document", ok,
          f"ddof={AR_SIGMA_DDOF}, q={c.separation_periods[0]}..{c.separation_periods[-1]}, "
          f"seed(gamma=1.5)={c.bootstrap_seed_for(1.5)}")


def main() -> int:
    print("=" * 74)
    print("  PHASE 2 STATISTICS -- verification against the frozen specification")
    print("=" * 74)
    for fn in [test_adversarial_calendar_is_caught,
               test_placebo_reproduces_frozen_values,
               test_placebo_is_deterministic,
               test_timing_on_perfect_calendar,
               test_bootstrap_null_calibration,
               test_bootstrap_detects_real_effect,
               test_bootstrap_deterministic,
               test_politis_white, test_holm, test_frozen_config_values]:
        fn()
    print()
    for name, ok, detail in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if detail:
            print(f"         {detail}")
    n = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n  {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
