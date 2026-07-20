# Pre-registered decisions

Structural choices frozen before results were seen. Amendments require a documented
evidence trail and independent approval; every change is traced in `CHANGELOG.md`.

The authoritative machine-readable copy is `rac_hrp/config.py`, a frozen dataclass.
This document is the human-readable statement of the same decisions.

---

## Calendar

| | |
|---|---|
| Raw data pull | from 1995-01-01 (lookback buffer for the longest covariance window) |
| First portfolio formation | 2000-01-03 |
| Development region ends | 2022-12-31 |
| Test region | 2023-01-03 → 2025-11-28 (**single touch**) |

The test region is structurally locked. Phase 0.5 and Phase 1 raise an error if any
evaluation position falls on or after `TEST_START`.

**Open item.** The available CRSP vintage ends 2024-12-31, so the pre-registered test
endpoint of 2025-11-28 is not reachable. Resolution is pending and must be recorded
before any test-region result is computed. No test-region performance has been inspected.

---

## D1 — Universe *(amended; see CHANGELOG)*

The N largest US common shares by market capitalisation lagged 21 trading days;
CRSP share codes 10–11, exchange codes 1–3; reconstituted at each monthly rebalance;
delisting returns spliced (Shumway 1997).

Eligibility screen: at least 252 trading days of history, at most 5% missing observations
within the covariance window.

Staged build: N = 100 → 200 → full.

*Originally specified as the S&P 500. Amended because S&P constituent history is not
licensed to this institution — confirmed empirically, not assumed. See `CHANGELOG.md`
for the full evidence trail and the argument that the CRSP-native rule is preferable on
its merits.*

## D2 — Spectrum

Marchenko–Pastur filtering of the correlation eigenspectrum. Retained-component count
is fixed per fold (`mp_k_mode = "fixed_per_fold"`). Minimum one component.

## D3 — Covariance estimator

Nonlinear Ledoit–Wolf shrinkage (`nls`). Alternatives `lw_linear` and `sample` exist and
are reported as **sensitivity diagnostics only** — they select nothing (see D10).

## D4 — Covariance window *(a rule, not a knob)*

The smallest window `W ∈ {504, 756, 1260}` satisfying `median(N) / W ≤ 0.67`.

This consumes only the realised universe size — a property of the data, not of any
performance metric. It is evaluated before folds are built, because fold geometry depends
on `min_train = W + min_history_days`.

## D5 — Regime trigger

Re-cluster when ΔAR (absorption ratio, smoothed over 5 days, differenced) exceeds
**1.0 σ**, where σ is estimated over a trailing 252-day window.

The 1σ threshold is inherited from Kritzman et al. (2011). It is **a free parameter, not
a derived optimum**, and is frozen for Phase 1. A mandatory sensitivity curve across
{0.5σ, 0.75σ, 1σ, 1.25σ, 1.5σ} is pre-registered as a Phase 2b calibration gate.

## D6–D8 — Clustering, allocation, execution

Clustering in PCA space with Ward linkage; cluster count equals the number of
MP-retained components, bounded to [2, 20]; canonical optimal leaf ordering.

Allocation by HRP recursive bisection. Long-only.

Monthly rebalancing (21 trading days). **One-day implementation lag** — weights formed at
`t` are live at `t+1`. Phase 0.5 and Phase 1 run gross; transaction costs of 5 bps and
10 bps one-way are pre-registered for Phase 3.

## D9 — Null gate

A synthetic-null gate destroys the signal in the data, keeps the pipeline, and requires a
flat result. Equivalence margin **δ = 0.10** Sharpe units, **one-sided** — the gate is
designed to detect a manufactured *positive* advantage; underperformance on signal-free
data reflects turnover cost, not manufactured signal.

Null Gate v2 is two-tier:

- **Primary gate (gating).** RAC-HRP against same-policy comparators only
  — `HRP_static` and `HRP_periodic_3` — which differ from it *solely* in re-clustering
  policy. One-sided paired *t*: PASS if the upper 95% bound ≤ +0.10, FAIL if the lower
  bound > +0.10, otherwise INCONCLUSIVE.
- **Diagnostic panel (non-gating).** Cross-allocator comparisons against equal weight and
  ERC. Reported and characterised; never gates.

Additional preconditions: a **trigger-activation requirement** (an environment is
informative only if the median firing rate is ≥ 5% and ≥ 90% of replications contain ≥ 3
trigger events) and **deterministic location-shift controls** (a null control at 0.00
must PASS and a positive control at +0.20 must FAIL in every primary cell, otherwise the
whole gate returns INCONCLUSIVE regardless of primary results).

Replication counts and seeds are frozen before execution and recorded in the freeze
manifest. No sequential addition of replications.

## D10 — Validation design

Four purged and embargoed walk-forward development folds. Purge 21 trading days, embargo
20 trading days, both position-based.

**Development folds have no model-selection role.** Estimator comparisons, threshold
sweeps, and sensitivity tables computed on development data are reported as diagnostics
and select nothing. Anything that would otherwise constitute selection is either
pre-registered as a rule (D4) or deferred to an explicit calibration gate (D5/Phase 2b).

---

## Phase plan

| Phase | Content | Status |
|---|---|---|
| 0.5 | point-in-time data, reconstruction gate, null gate | complete |
| 1 | static baselines: ERC, Ledoit-Wolf, Molyboga MHRP variant | in progress |
| 2 | regime-adaptive layer; ΔAR threshold calibration gate; cluster stability (ARI) | pending |
| 3 | transaction-cost robustness at 5 bps and 10 bps | pending |
| 4 | inference (studentized bootstrap, block bootstrap), sub-period robustness | pending |

Inference: Ledoit–Wolf (2008) studentized bootstrap is primary; Jobson–Korkie/Memmel is
reported for comparability only. Politis–White automatic block-length selection for the
block bootstrap.
