# Deferred items

## EWMA covariance (Molyboga component (i))
Status: DEFERRED baseline extension pending source verification or a separately
frozen implementation specification.

Reason: the exponentially weighted covariance estimator requires a decay/half-life
parameter not stated in the abstract. The full paper (JFDS 2020, 2(3), 128-139) is
not yet obtained; interlibrary loan was unsuccessful; a direct reprint request to
the author is outstanding. The parameter is a free parameter and is NOT guessed
(pre-registration discipline).

Does NOT block: the RAC-HRP contribution, ordinary HRP benchmarks, the
equal-volatility component, or Phase 2. This is an optional baseline extension, not
necessary evidence for the central hypothesis.

Resolution paths (advisor to rule when unblocked):
  (a) implement with the paper's value once obtained;
  (b) cite RiskMetrics (J.P. Morgan 1996) lambda=0.94 daily, as a separately frozen
      spec not attributed to Molyboga;
  (c) pre-registered decay sensitivity sweep, reported as a curve.
