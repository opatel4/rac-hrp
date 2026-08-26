# PRE-SPECIFICATION — Phase 2A Post-Mortem: Pipeline-Level Structureless Null

*Mechanism diagnostic for the memo §4d question. Submitted for advisor
countersignature BEFORE any replication is run. No environment is registered and
no runner is written until this is signed.*

| | |
|---|---|
| **Experiment** | Post-gate mechanism diagnostic (Phase 2A post-mortem) |
| **Question** | Does the frozen RAC trigger architecture itself generate temporal burstiness on regime-free input? |
| **Prepared by** | Om Patel |
| **Status** | PRE-SPECIFICATION rev.4 — thirteen advisor fixes applied; awaiting countersignature |

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
| **S** | `static_corr` — **static covariance structure**: one fixed Sigma_0, i.i.d. draws through time (Sigma_0 is constant in time, NOT an equicorrelation matrix) | **Primary / adjudicating null** | written, sandbox-verified, registration pending this signature |
| **D** | `regime_switch_vol` — two-state Markov, vol AND factor loadings scale | **Positive control** | exists, verified below |

### S — complete mathematical specification (FIX 1)

Data-generating process, frozen:

> Raw draws: r*_t ~ iid N(0, Sigma_0) for every t, with Sigma_0 IDENTICAL at every date.
>
> **Emitted panel:** the generated series is subsequently recentred by its own
> simulated per-asset sample mean. This imposes a deterministic zero-sample-mean
> constraint, so the emitted rows are **not strictly independent**, although no
> temporal regime and no real-data future information is introduced. The claim
> frozen here is the DGP plus this recentring, not exact iid output.

Sigma_0 construction, documenting the existing implementation exactly (not an
idealisation of it):

| Element | Frozen |
|---|---|
| Estimation sample | **DEVELOPMENT-REGION ROWS ONLY** (dates < TEST_START = 2023-01-03), passed as an explicit boolean `fit_rows` mask |
| Estimator | pandas `DataFrame.cov()` — pairwise-complete sample covariance, mean-removed, ddof = 1 |
| NaN treatment (fit) | pairwise-complete: each entry uses dates where both assets are observed |
| Demeaning | yes, by the estimator (fit); the emitted panel is additionally recentred by its own simulated per-asset mean — see the DGP note above |
| Conditioning | ridge shrink toward the diagonal, `shrink = 0.10`: Sigma_0 = 0.9·S + 0.1·diag(S) |
| Non-finite repair | non-finite entries set to 0; non-finite/non-positive diagonal entries set to the median variance |
| Symmetrisation | Sigma_0 <- (Sigma_0 + Sigma_0^T)/2 |
| PSD correction | eigenvalue flooring at max(1e-12, 1e-8·lambda_max) via `numpy.linalg.eigh` |
| Factorisation | L = V·sqrt(w) from the floored eigendecomposition (Sigma_0 = L·L^T); NOT Cholesky, which fails on the indefinite pairwise-complete matrix |
| Simulation | X = Z·L^T with Z ~ iid standard normal, independent across rows |
| Asset volatility | preserved implicitly via Sigma_0's diagonal (no separate vol rescaling) |
| Universe mapping | fixed Sigma_0 over all panel columns; the real NaN mask is reapplied, so the point-in-time universe selects from it unchanged |

A fixed 10% diagonal shrinkage is applied as a **pre-specified regularisation step**
before PSD flooring. It is required for the factorisation to be well behaved on the
indefinite pairwise-complete matrix, but it changes the covariance structure supplied
to the experiment as well as its conditioning, and is therefore a modelling choice,
not pure conditioning. **No monotonic effect on downstream trigger burstiness is
assumed**: burstiness is produced downstream through covariance estimation,
eigendecomposition, smoothing, differencing and the rolling threshold, and its
response to off-diagonal shrinkage is not established to be monotonic. The value
0.10 is frozen here, before any mechanism-diagnostic result exists; no sensitivity
sweep is performed, as that would convert a narrow mechanism question into a tuning
exercise.

**Test-region leakage, found during specification and fixed.** The panel runs to
the CRSP vintage end (2024-12-31) and therefore contains test-region dates. Fitting
Sigma_0 on the full panel would embed test-region covariance structure in the null
environment. This produces no performance number and cannot affect Phase 2A, but it
violates the project's structural discipline. Sigma_0 is therefore fitted on
development-region rows only, via an explicit mask. **The same restriction applies
to environments A and D**, whose per-asset volatility matching (`real.std()`) has
the identical exposure: all three environments receive a development-region-only
fitting sample and emit full-length panels.

**Why S is the adjudicating null.** A has no cross-asset correlation structure, so any covariance concentration comes
only from cross-sectional variance heterogeneity; AR has little genuine movement and
dAR is close to estimation noise. If A bursts, that is decisive evidence of a mechanical artefact — but if A
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
each asset unconditionally to its development-region volatility target, which damps
absolute vol regimes while leaving the relative concentration shift intact — which
is the property AR responds to.

### D — complete specification (FIX 2)

Existing implementation `regime_switch_vol`, parameters frozen as its defaults:

| Element | Frozen |
|---|---|
| States | two, Markov |
| Transition | P(stay in state 0) = 0.99; P(stay in state 1) = 0.97; equivalently p_01 = 0.01, p_10 = 0.03 |
| Expected durations | ~100 **daily return observations** in state 0, ~33 in state 1 (the state advances once per panel row, not per rebalance) |
| Initial state | state[0] = 0 (low state), deterministic |
| Factors | `n_factors = 3`, loadings B ~ N(0,1), drawn once per replication |
| Volatility scaling | `vol_ratio = 2.5` applied to BOTH factor scores F and idiosyncratic E |
| Concentration shift | `corr_shift = 1.4` applied to the FACTOR COMPONENT ONLY |
| Generating equation | X = (F·B^T)·load·0.35 + E, with scale on F and E, load on the factor term |
| Volatility target | per-asset volatility estimated from **development-region rows only** (`fit_rows`); no test-region returns enter the fitted targets |
| Normalisation | unconditional per-asset rescale to that target, then per-asset demean (unconditional, not per-state) |
| Conditional means | zero in both states |

**Regime frequency relative to the estimation window (stated limitation).** Because
the state advances daily, expected episodes are ~100 and ~33 trading days, i.e.
~4.8 and ~1.6 rebalance periods. At stationarity the chain spends approximately 75%
of observations in state 0 and 25% in state 1 (pi_0 = p_10/(p_01+p_10) = 0.75), with
a mean low/high cycle of ~133 days. A 504-day covariance window therefore spans
roughly **3.8 complete cycles** on average, so the estimator materially averages
across the designed regimes rather than seeing any single one. D is consequently a **high-frequency**
positive control: it establishes what the frozen machinery does when covariance
concentration shifts on a timescale short relative to W, not what it would do under
slow, persistent regimes. Read the Outcome-2 D-overlap clause with that in mind; a
non-overlap does not by itself argue against slower real regimes.

The two independent multipliers are what make D a valid positive control: the
factor/idiosyncratic variance ratio shifts between states, so covariance
*concentration* changes and AR responds. A common scalar volatility regime
(Sigma_2 = c·Sigma_1) would cancel in the AR ratio and be useless here.

### Post-generation recentring differs by environment (FIX 10)

Documented as implemented, not idealised:

| Env | Post-draw operations on the generated panel |
|---|---|
| **A** | none — raw vol-matched iid draws, no recentring, no rescaling |
| **S** | recentred by simulated per-asset sample mean |
| **D** | rescaled by the simulated per-asset `nanstd` to the development-region volatility target, then recentred by simulated per-asset mean |

S and D therefore emit rows that are not strictly independent (zero-sample-mean
constraint); A does. No environment introduces temporal regime structure or
real-data future information by these operations.

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

**Undefined-timing edge case (FIX 5).** If a replication yields n_gamma < 2 there
are no inter-event gaps and M, CV, B are mathematically undefined. Such
replications are recorded with `timing_defined = False` and M = CV = B = NA; f_gamma
is recorded normally. They are **not silently dropped** — Pr(n_gamma < 2) is
reported per environment and gamma alongside the distributions, because an
environment that rarely triggers at gamma = 2.0 is itself informative.
Distributional comparisons use defined values only, with that proportion stated.

**NOT computed per replication:** the J* 100,000-draw placebo, the D_VI 10,000-
replicate bootstrap, portfolio returns, Sharpe, or any Null Gate quantity. They are
irrelevant to the mechanism question and would dominate runtime.

### The B_gamma statistic

Raw modal-gap share depends on event count, and each replication produces its own
n_gamma, so raw M is not comparable across replications. Define

> B_gamma = M_gamma − median( M^placement | n_gamma )

where m(n) is a **deterministic, cached lookup** keyed on the event count (FIX 3):

> m(n) = median( M^placement | n events among E = 233 ), from 10,000 placement
> draws under `default_rng(MECH_SEED_BASE + 500000 + n)`.

One value per distinct n, computed once and cached. Two replications with the same
event count therefore receive **identical** density corrections — a fresh
per-replication placement simulation would inject Monte Carlo noise into the very
statistic being compared, for no benefit. **The real-data B_gamma uses the same
lookup**, making the comparison exactly apples-to-apples. The lookup reuses the
placement machinery from `scripts/diagnose_modal_gap_null.py` and is trivial
relative to `structural_pass`.

## 5. Frozen parameters

| Element | Value |
|---|---|
| Replications | **500 per environment** (1,500 passes total) — FIX 6 |
| Seed derivation | `default_rng(MECH_SEED_BASE + 1000*env_index + rep)`, env_index = 0 (A), 1 (S), 2 (D) |
| `MECH_SEED_BASE` | **20260822** |
| Placement lookup m(n) | 10,000 draws per distinct n, `default_rng(MECH_SEED_BASE + 500000 + n)`, cached |
| BLAS | `OPENBLAS_NUM_THREADS=1` |
| Quantile implementation | `numpy.percentile(..., method="linear")`, computed over `timing_defined = True` replications only |
| Boundary equality | Outcome 1 interval endpoints **inclusive**; Outcome 2 requires **strictly greater than** the 97.5th percentile |

**Measured runtime.** One `structural_pass` = 6.0s (A) / 5.9s (D) with BLAS pinned
to one thread; 1,500 passes ≈ **2.5 hours serial**. 500 replications puts ~12–13
observations in each 2.5% tail rather than the 2–3 that 100 would give, which
matters because the decision rule uses a 97.5th-percentile boundary. No parallelism is used, which
keeps the run fully deterministic. (Unpinned, the same pass takes 79.6s — a 13×
thread-contention penalty on this machine. Pinning was verified **result-neutral**:
a `--quick` gate rerun reproduced every event count, J*, D_VI and p-value
bit-for-bit.)

## 6. Decision rule (fixed before execution)

S is the adjudicating environment; A and D interpret it. For each gamma, form the
null distribution of B_gamma and compare the real-data B_gamma to it.

**Quantifier, frozen (FIX 4): every rule below requires the stated condition to
hold for ALL FOUR gammas {0.5, 1.0, 1.5, 2.0}.** No subset, majority, or
"generally" reading is permitted. This is deliberately conservative; the
experiment is a post-mortem diagnostic, not a power competition.

**Outcome 1 — architectural burstiness.** If, for all four gammas,

> B_gamma^real ∈ [ Q^S_{.025,gamma} , Q^S_{.975,gamma} ]

then:

> The observed temporal clustering is compatible with burstiness generated by the
> frozen trigger architecture under persistent but regime-free covariance
> structure. **Comparable burstiness therefore does not require regime changes and
> cannot be uniquely attributed to them.** (Compatibility with S does not prove that
> real-market regimes played no role; it establishes that regimes are not necessary
> to reproduce comparable burstiness.)

If in addition B_gamma^real lies inside A's central 95% for all four gammas,
strengthen to: comparable burstiness can arise even without cross-asset correlation
structure — the clearest architectural diagnosis. This does not establish that the
real burstiness definitely arose mechanically.

**Outcome 2 — information beyond regime-free mechanics.** If, for all four gammas,

> B_gamma^real > Q^A_{.975,gamma}  AND  B_gamma^real > Q^S_{.975,gamma}

then:

> The observed burstiness exceeds that generated by the frozen pipeline under both
> uncorrelated and static-covariance regime-free inputs.

If D's central 95% additionally overlaps B_gamma^real for all four gammas, add:
the observed timing is *consistent with* the pipeline's behaviour under designed
nonstationarity. The wording is deliberate — consistent with, not proof that the
real episodes are regimes.

**Outcome 3 — mixed.** Any configuration not satisfying Outcome 1 or Outcome 2 in
full:

> The diagnostic does not yield a uniform mechanism classification across the four
> frozen gamma values. (A mixed result does not identify what proportion of the
> burstiness is "explained".)

No binary conclusion is forced. Under every outcome, Phase 2A remains failed and
closed.

**Reporting requirement.** The all-four-gamma rule is deliberately strict, so
Outcome 3 may well obtain — particularly if one gamma behaves differently from the
others. The full four-gamma distributional table (per environment: null quantiles,
real B_gamma, and Pr(n_gamma < 2)) is reported **regardless of which outcome the
formal classification returns**. The observed pattern may be scientifically
informative even when it fails the categorical rule. The rule is not weakened after
seeing results.

## 7. Deliverables

A hashed record `outputs/phase2_mechanism/mechanism_null.json` (per-environment,
per-gamma null distributions and the real-data comparison), the runner script, and
the environment-S registration. All committed and hashed into the implementation-
control manifest alongside the Phase 2A audit bundle.

## 8. Sign-off

AUTHORIZE:      YES      /      NOT YET

| Advisor signature / date | Conditions / notes |
| --- | --- |
