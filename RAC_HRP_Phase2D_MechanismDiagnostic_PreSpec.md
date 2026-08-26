# PRE-SPECIFICATION — Phase 2A Post-Mortem: Pipeline-Level Structureless Null

*Mechanism diagnostic for the memo §4d question. Submitted for advisor
countersignature BEFORE any replication is run. No environment is registered and
no runner is written until this is signed.*

| | |
|---|---|
| **Experiment** | Post-gate mechanism diagnostic (Phase 2A post-mortem) |
| **Question** | Does the frozen RAC trigger architecture itself generate temporal burstiness on regime-free input? |
| **Prepared by** | Om Patel |
| **Status** | PRE-SPECIFICATION — awaiting countersignature |

## 0. Binding constraint on any outcome

> **This experiment diagnoses the mechanism behind the already-observed Phase 2A
> failure. No outcome can reopen Phase 2A, change a frozen threshold, select a new
> gamma, or authorize performance evaluation.**

Phase 2A is closed with no admissible gamma. `cluster_informativeness` failed
independently for every candidate, so no timing result — in either direction —
bears on that conclusion.

## 1. Motivation

Memo v3 §4a established that real trigger dates are far more temporally clustered
than uniform random *placements* of the same count (observed modal-gap share
0.76–0.82 versus placement nulls of 0.19–0.69). §4d records what that does **not**
establish: whether the burstiness is regime-driven or endogenous to the trigger
construction. A placement null cannot separate them, because overlapping 504-day
covariance windows, five-rebalance AR smoothing, first differencing, the rolling
12-rebalance sigma denominator, and persistence in estimated eigenspectra can each
induce temporal dependence in the trigger series with no regime structure present.

This diagnostic presents the **frozen pipeline** with regime-free input and asks
whether it bursts anyway.

## 2. Environments (three, with distinct roles)

| Label | Generator | Role | Status |
|---|---|---|---|
| **A** | `iid_gaussian` — vol-matched, zero cross-correlation, no time dependence | **Floor control** | exists |
| **S** | `static_corr` — one fixed Sigma_0 from the real panel, i.i.d. draws through time | **Primary / adjudicating null** | written, sandbox-verified, registration pending this signature |
| **D** | `regime_switch_vol` — two-state Markov, vol AND factor loadings scale | **Positive control** | exists, verified below |

**Why S is the adjudicating null.** A has an approximately flat population
eigenspectrum, so AR has little genuine movement and dAR is close to estimation
noise. If A bursts, that is decisive evidence of a mechanical artefact — but if A
does *not* burst, the trigger is not thereby cleared, because the suspected
mechanism is the interaction of ~96%-overlapping estimation windows with
*persistent* correlation structure, which A never presents. S supplies exactly
that: identical population covariance at every date, zero regimes, yet strongly
persistent *estimated* eigenspectra.

**D verified as a genuine positive control.** Because AR is a ratio of
eigenvalues, a common scalar volatility regime (Sigma_2 = c·Sigma_1) cancels and
would leave population AR unchanged — making a vol-only switch useless here. D
does not have this defect: it applies two separate multipliers, `scale`
(vol_ratio 2.5) to both factor and idiosyncratic components, and `load`
(corr_shift 1.4) to the **factor component only**, so the factor/idiosyncratic
variance ratio shifts between states. That is a genuine change in covariance
concentration, which is what AR measures. Noted for the record: D renormalises
each asset to its real full-sample volatility unconditionally, which damps
absolute vol regimes while leaving the relative concentration shift intact — which
is the property AR responds to.

## 3. What is held fixed (the machinery under test must be bit-for-bit frozen)

Preserved unchanged from the real panel and the frozen configuration: NaN mask,
point-in-time membership, market caps, eligibility screen, rebalance dates,
W = 504, k = 15 (fixed_per_run), five-rebalance AR smoothing, sigma =
`rolling(12, min_periods=6).std(ddof=1).shift(1)`, and all four frozen gammas
{0.5, 1.0, 1.5, 2.0}. Only the return-generating mechanism changes.

**`structural_pass` runs UNMODIFIED**, including the counterfactual VI and
attributable-turnover computation that this diagnostic does not use. Stripping
that work would make the machinery under test a different pipeline and any
burstiness result contestable. The cost (measured below) is the price of the claim
being about the actual frozen trigger. This is a standing instruction: do not
"optimise" the diagnostic by removing pipeline stages.

## 4. Statistics recorded (timing side only)

For each environment, replication, and gamma:

- `f_gamma` — firing rate
- `CV_gamma` — coefficient of variation of inter-event gaps
- `M_gamma` — modal-gap share
- `B_gamma` — **density-adjusted excess burstiness** (below)

**NOT computed per replication:** the J* 100,000-draw placebo, the D_VI 10,000-
replicate bootstrap, portfolio returns, Sharpe, or any Null Gate quantity. They are
irrelevant to the mechanism question and would dominate runtime.

### The B_gamma statistic

Raw modal-gap share depends on event count, and each replication produces its own
n_gamma, so raw M is not comparable across replications. Define

> B_gamma = M_gamma − median( M^placement | n_gamma )

where the placement median is computed at **that replication's own event count**
using the existing random-placement machinery from
`scripts/diagnose_modal_gap_null.py`. B_gamma is excess temporal burstiness beyond
what event density alone implies, and is the primary comparison quantity. The
placement draw is computationally trivial relative to `structural_pass`.

## 5. Frozen parameters

| Element | Value |
|---|---|
| Replications | **100 per environment** (300 passes total) |
| Seed derivation | `default_rng(MECH_SEED_BASE + 1000*env_index + rep)`, env_index = 0 (A), 1 (S), 2 (D) |
| `MECH_SEED_BASE` | **20260822** |
| Placement sub-null for B_gamma | 2,000 draws per (replication, gamma), seed derived as above + 500000 |
| BLAS | `OPENBLAS_NUM_THREADS=1` |

**Measured runtime.** One `structural_pass` = 6.0s (A) / 5.9s (D) with BLAS pinned
to one thread; 300 passes ≈ **30 minutes serial**. No parallelism is used, which
keeps the run fully deterministic. (Unpinned, the same pass takes 79.6s — a 13×
thread-contention penalty on this machine. Pinning was verified **result-neutral**:
a `--quick` gate rerun reproduced every event count, J*, D_VI and p-value
bit-for-bit.)

## 6. Decision rule (fixed before execution)

S is the adjudicating environment; A and D interpret it. For each gamma, form the
null distribution of B_gamma and compare the real-data B_gamma to it.

**Outcome 1 — architectural burstiness.** If the real B_gamma values fall inside
the central 95% of the S distribution across the four gammas:

> The observed temporal clustering is compatible with burstiness generated by the
> frozen trigger architecture under persistent but regime-free covariance
> structure. It therefore cannot be attributed to regime changes.

If **A** also reproduces the real burstiness, strengthen to: the pipeline generates
comparable burstiness even absent cross-sectional correlation structure — the
clearest architectural diagnosis.

**Outcome 2 — information beyond regime-free mechanics.** If the real B_gamma lies
above the 97.5th percentile of **both A and S** consistently across the gamma grid:

> The observed burstiness exceeds that generated by the frozen pipeline under both
> uncorrelated and static-correlated regime-free inputs.

If D's distribution then overlaps the real values, add: the observed timing is
*consistent with* the pipeline's behaviour under designed nonstationarity. Wording
is deliberate — consistent with, not proof that the real episodes are regimes.

**Outcome 3 — mixed.** Anything else:

> The mechanism diagnostic is inconclusive; pipeline mechanics explain some but not
> all of the observed burstiness.

No binary conclusion is forced. Under every outcome, Phase 2A remains failed and
closed.

## 7. Deliverables

A hashed record `outputs/phase2_mechanism/mechanism_null.json` (per-environment,
per-gamma null distributions and the real-data comparison), the runner script, and
the environment-S registration. All committed and hashed into the implementation-
control manifest alongside the Phase 2A audit bundle.

## 8. Sign-off

AUTHORIZE:      YES      /      NOT YET

| Advisor signature / date | Conditions / notes |
| --- | --- |
