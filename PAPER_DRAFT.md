---
output:
  pdf_document: default
  html_document: default
---
# Admissibility Before Performance: A Performance-Blind Structural Gate for Regime-Adaptive Hierarchical Risk Parity

**Om Patel**
*Stevens Institute of Technology, Hoboken, NJ*
opatel4@stevens.edu

**JEL classification:** G11 (Portfolio Choice; Investment Decisions); G17
(Financial Forecasting and Simulation); C58 (Financial Econometrics); C52 (Model
Evaluation, Validation, and Selection)

---

## Abstract

Adaptive portfolio construction methods are conventionally evaluated by
out-of-sample performance. This creates a well-documented inferential problem: the
specification of the adaptive mechanism — thresholds, smoothing, event definitions
— is typically fixed after the researcher has observed how those choices affect
returns. We propose and apply an alternative protocol in which an adaptive
mechanism must first demonstrate *structural informativeness* against a
prospectively frozen, performance-blind admissibility gate, and only then becomes
eligible for performance evaluation.

We instantiate this protocol for Regime-Adaptive Clustered Hierarchical Risk Parity
(RAC-HRP), in which re-clustering of the HRP dendrogram is triggered by changes in
the absorption ratio (Kritzman et al., 2011). The gate evaluates four
pre-registered trigger thresholds against five hard structural criteria, none of
which references any return quantity. On a CRSP-native large-cap universe over a
development region of 2003–2022, **no threshold is admissible.** Triggered
rebalances exhibit greater clustering change than non-triggered rebalances at every
threshold, and the effect grows with selectivity, but no candidate attains
statistical significance after pre-registered multiplicity control (Holm-adjusted
*p* ∈ [0.221, 0.556]). Because the gate is conjunctive and performance-blind, the
experiment terminates without a portfolio ever being constructed and without the
holdout sample being opened.

A pre-registered post-mortem then asks whether the trigger's unusually bursty
timing is an artefact of the estimation pipeline. Across 1,500 replications of the
frozen machinery on regime-free inputs, real-data excess burstiness exceeds the
97.5th percentile of both an uncorrelated and a static-covariance null at all four
thresholds, so the tested regime-free architectural explanations are not supported.

Separately, a frozen estimator sensitivity sweep decomposes two components of
Molyboga's (2020) modified HRP: within the development region, exponentially
weighted constant-correlation covariance improves every covariance-dependent
strategy examined, whereas the equal-volatility allocation modification remains
below static HRP under every covariance estimator.

We argue the resulting negative result is more informative than a comparable
performance-based null, precisely because no performance quantity was available at
the decision point. All code, frozen specifications, decision records, and a
hash-pinned reproducibility manifest are released.

**Keywords:** hierarchical risk parity; absorption ratio; regime detection;
pre-registration; multiple testing; reproducible research

---

## 1. Introduction

Hierarchical Risk Parity (López de Prado, 2016) allocates capital using a
correlation-derived dendrogram rather than a matrix inversion, which makes it
robust in the high-dimensional regime where sample covariance is poorly
conditioned. A natural extension is to make the dendrogram *adaptive*: rather than
re-clustering on a fixed calendar, re-cluster when the market's correlation
structure actually changes. The absorption ratio — the share of total variance
captured by the leading eigenvectors — is an appealing trigger because it is a
direct, model-free measure of covariance concentration and is known to move around
episodes of systemic fragility (Kritzman et al., 2011).

This paper is about what happened when we tried to test that idea honestly.

### 1.1 The inferential problem

An adaptive mechanism of this kind is a *specification family*, not a single
specification. The researcher must choose a smoothing window, a scale for
normalising changes, a firing threshold, and a re-clustering rule. Each choice
changes both the number of trigger events and, downstream, the portfolio's
returns. If the choices are made while performance is observable — even
informally, even in good faith — the resulting out-of-sample statistic is
conditioned on the outcome it purports to test.

The magnitude of this problem is not hypothetical. Nikolopoulos (2026) shows that
adaptive specification search generates statistically significant backtests even
under martingale-difference nulls, and proposes falsifying complete predictive
workflows against synthetic reference classes — including zero-predictability
environments — rather than auditing individual results. Sheppert (2026) documents
the corresponding degradation in reported strategy performance under realistic
search intensity, and Bailey, Borwein, López de Prado and Zhu (2014) give the
general account of how backtest overfitting propagates into out-of-sample claims.
The concern is structural rather than a matter of researcher discipline: DeMiguel,
Garlappi and Uppal (2009) found that none of fourteen optimisation methods they
tested consistently beat naive 1/N out-of-sample, a result frequently attributed to
estimation error but equally consistent with specification search in the methods
being compared. In a literature where hierarchical methods are
already reported inconsistently — Deković and Posedel Šimović (2025) find 1/N
outperforms HRP on risk-adjusted return across every setup they test, while other
replications report the reverse — the credibility of any new adaptive variant
depends heavily on how its specification was chosen.

### 1.2 Admissibility before performance

Our response is to separate two questions that are usually answered together:

1. **Is the adaptive mechanism structurally informative?** Do its trigger events
   identify moments when the dependence structure actually changes?
2. **Does acting on it improve performance?**

We argue (1) should be settled first, using statistics that do not reference
returns, and that failure at (1) should terminate the investigation. A mechanism
that cannot demonstrate it is detecting the thing it claims to detect has no
principled basis for a performance claim, and a performance evaluation conducted
anyway will be uninterpretable — a positive result cannot be distinguished from
specification search, and a negative result cannot be distinguished from bad luck.

Concretely, we pre-register a **conjunctive structural gate** with five hard
criteria evaluated on a development region, freeze and hash it before any Phase 2
gate code is written, and implement it so that the selection rule is applied
automatically in code. The freeze is evidenced by the document hash recorded in the
released manifest together with the commit timestamps of the implementing code, not
by a countersignature: this is a single-author study and no independent party
authorised the specification (§7.6). The Phase 2 calibration implementation never
calls the return-performance path or risk-free series and cannot produce a Sharpe
ratio. Phase 0.5 did compute Sharpe ratios as part of the falsification audit:
environments A, B and D used null return environments, while environment C retained
development-region returns but randomised trigger timing. Performance evaluation is
reachable only through the gate.

### 1.3 Contributions

**A performance-blind admissibility protocol.** We give a complete, executable
specification of a structural gate for adaptive re-clustering mechanisms —
informativeness, event sufficiency, timing variation, calendar separation, and
cluster informativeness — with frozen inference, pre-registered multiplicity
control, and a stopping rule that forbids selecting a "least bad" candidate.

**A clean negative result for an absorption-ratio trigger.** No threshold in the
pre-registered grid is admissible. The binding failure is cluster informativeness:
the clustering-change effect is positive in direction at every threshold and
increases with selectivity, but is statistically unresolved under the frozen
inference procedure. Because the gate is performance-blind, this conclusion is not
conditioned on any return outcome.

**A mechanism post-mortem that rules out two architectural explanations.** The
trigger fires in unusually tight temporal bursts. We pre-register a pipeline-level
null in which regime-free returns are pushed through the identical frozen
machinery, and show across 1,500 replications that neither an uncorrelated nor a
static-covariance environment reproduces the observed burstiness at any threshold.

**A decomposition of modified HRP.** A frozen estimator sweep separates two of
Molyboga's (2020) modifications, finding that the covariance modification helps in
this sample while the allocation modification does not.

**A hash-pinned reproducibility record**, including a machine-checkable assertion
that the holdout sample was never opened.

---

## 2. Related Work

**Hierarchical allocation.** López de Prado (2016) introduced HRP, motivated by the
instability of quadratic optimisers under estimation error; the mechanism is
avoidance of covariance inversion. Subsequent work extends the tree construction
(Avellaneda, 2019, hierarchical PCA; Pergher et al., 2026, orthogonal hierarchical
allocation) or the risk-budgeting rule (Molyboga, 2020). Earlier work established
clustering as a preprocessing step for allocation more generally (León et al.,
2017). Empirical replications are mixed: Deković and Posedel Šimović (2025) report
1/N dominating HRP on risk-adjusted return over 2005–2023 on S&P 500 constituents
(Sharpe 0.868 vs 0.534 on the full index) while confirming HRP's volatility
reduction of roughly one percentage point. We note that their universe is the
constituent set as of March 2023 — the authors state the limitation explicitly —
so their backtest is subject to survivorship bias. Our universe is constructed
point-in-time from CRSP membership, which removes that channel. The general pattern — HRP reduces risk but underweights the
high-volatility names that drive trending markets — motivates adaptivity. The
antecedent idea, that clustering can serve as a preprocessing step before
allocation, predates HRP's specific formulation: León et al. (2017) compare seven
clustering algorithms on intraday Russell 1000 data and report that hierarchical
methods achieve the best trade-off between accumulated return and Omega ratio,
with all clustering approaches producing lower volatility than mean-variance
optimisation.

**Regime detection and the absorption ratio.** Kritzman et al. (2011) introduced
the absorption ratio as a systemic-risk measure and documented that increases
precede market drawdowns. Regime-switching approaches (Hamilton, 1989; Kim &
Nelson, 1998; Ang & Timmermann, 2012) establish that volatility and correlation
regimes are persistent and economically costly to ignore. Recent work couples
regime detection with allocation directly. Akioyamen et al. (2020) apply PCA to 48
macroeconomic series and recover a two-regime crisis/non-crisis split by k-means
with the regime count inferred from silhouette width rather than assumed; Horvath
and Issa (2023) detect regimes online through a path-signature two-sample test;
Zhang et al. (2025) and Kriuk and Kriuk (2026) build regime-aware allocation
systems on sectoral and correlation-network structure respectively.

Our trigger sits in this family but is deliberately minimal: a two-sided threshold
on the standardised change in a smoothed absorption ratio. This is by design. The
question we ask is not whether a sophisticated regime detector can be built, but
whether a simple, transparent, fully pre-specifiable one clears a structural
admissibility standard — and a minimal trigger makes the gate's verdict
interpretable in a way an elaborate one would not.

**Covariance estimation.** Ledoit & Wolf (2004) established linear shrinkage
toward structured targets; Ledoit & Wolf (2022) extend to nonlinear shrinkage.
Molyboga (2020) applies exponentially weighted covariance with constant-correlation
shrinkage in a managed-futures context. Bongiorno et al. (2025) pursue learned
covariance cleaning. Our sensitivity analysis compares sample, linear-shrinkage,
nonlinear-shrinkage, and exponentially weighted constant-correlation estimators.

**Evaluation methodology.** López de Prado (2018) formalises purged, embargoed
cross-validation for financial time series; Bailey et al. (2014) quantify the
deflation of reported Sharpe ratios under multiple testing. Our contribution is
orthogonal and complementary to both: purging addresses leakage *within* an
evaluation and deflation adjusts a statistic *after* it is computed, whereas the
gate addresses what is permitted to reach evaluation at all. The distinction
matters because deflation requires knowing the number of trials, which is precisely
what informal specification search leaves unrecorded.

**Positioning.** Pre-registration is established in clinical and, increasingly,
psychological research, and has been proposed for finance, but published
applications in empirical portfolio construction remain rare. To our knowledge this
is the first study in this literature to pre-register a conjunctive structural gate
whose selection rule is executed in code, to hash the specification before writing the implementing code, and to report the resulting negative outcome without
amendment.

---

## 3. Data and Universe

The panel is constructed from CRSP daily stock files. Ordinary common shares
(share codes 10, 11) on NYSE, AMEX and Nasdaq (exchange codes 1, 2, 3) are
retained. Delisting returns are spliced following Shumway's convention, with an
audit record of every splice. Prices recorded as bid/ask midpoints (negative in
CRSP) are taken in absolute value for market-capitalisation computation.

The investable universe at each rebalance is the largest *N* = 100 eligible names
by lagged market capitalisation, subject to a minimum history screen and a maximum
missing-observation fraction, constructed point-in-time so that no future
membership information enters. Rebalancing is monthly (21 trading days).

**Region definition.** The development region runs 2003-01-08 to 2022-12-30
(5,031 trading days, 240 rebalances). The holdout region begins 2023-01-03. The
holdout was *never opened* (Section 7.3).

The covariance window is selected by a pre-registered deterministic rule (D4) from
candidates {504, 756, 1260} as a function of the median realised universe size;
for *N* = 100 this yields *W* = 504.

---

## 4. Methodology

### 4.1 The trigger

Let Σ̂*ₜ* be the covariance estimate over the trailing *W* = 504 trading days ending
at rebalance *t*, with eigenvalues λ₁ ≥ … ≥ λ_N. The absorption ratio is

> AR*ₜ* = (Σ_{i=1..k} λ_{i,t}) / (Σ_{i=1..N} λ_{i,t}),

with *k* fixed at the Marchenko–Pastur count of the first eligible rebalance and
held for the entire run (*k* = 15). Fixing *k* ex ante avoids a subtle look-ahead
channel: a *k* that adapts to each window makes AR partly a function of how many
components happen to clear the noise threshold at that date.

The series is smoothed over five rebalances, differenced, and standardised by a
strictly trailing scale:

> AR^s*ₜ* = mean(AR over 5 rebalances); ΔAR*ₜ* = AR^s*ₜ* − AR^s*ₜ₋₁*;
> σ̂*ₜ* = rolling(12, min_periods = 6).std(ddof = 1).shift(1) of ΔAR.

A trigger fires when |ΔAR*ₜ*| > γ · σ̂*ₜ*, two-sided with zero location and strict
inequality. Because σ̂ requires six observations, the first seven rebalances can
never fire; the eligible set is |E| = 240 − 7 = 233.

The candidate grid is γ ∈ {0.5, 1.0, 1.5, 2.0}, fixed ex ante. **γ was not tuned.**

### 4.2 The structural gate

A candidate is admissible only if it satisfies all five criteria:

| Criterion | Statistic | Pass rule |
|---|---|---|
| Informativeness | *f_γ* = \|T_γ\|/\|E\| | 0.05 ≤ *f_γ* ≤ 0.40 |
| Event sufficiency | events per development fold | ≥ 3 in all four folds |
| Timing variation | CV of inter-event gaps; modal-gap share | CV ≥ 0.50 **and** modal share ≤ 0.50 |
| Separation | *J\*_γ*, max Jaccard overlap with any periodic schedule *q* ∈ {2..12} and phase *r* | ≤ placebo 95th percentile at that candidate's own event count |
| Cluster informativeness | *D_VI* = median(VI \| fired) − median(VI \| not fired) | *D_VI* > 0 **and** Holm-adjusted *p* < 0.05 |

**No criterion references any return quantity.** Turnover is computed and reported
as a diagnostic but cannot pass or fail a candidate.

The *separation* criterion deserves comment. A trigger that fires on a fixed
calendar is not regime-adaptive, whatever its label. Maximising Jaccard overlap
over both period *and phase* is essential: a trigger firing every second rebalance
on odd-indexed dates scores *J\** = 0.252 without phase adjustment (passing) and
1.000 with it (caught). The threshold is recomputed by Monte Carlo at each
candidate's own event count, because it depends strongly on that count — the 95th
percentile is 0.171 at 12 events and 0.382 at 112.

The *cluster informativeness* criterion is the heart of the gate. It asks whether
triggered rebalances coincide with larger changes in the hierarchical clustering
than non-triggered ones, measured by variation of information (VI) between
consecutive clusterings on the intersection of consecutive universes.
Critically, the counterfactual clustering is recomputed at *every* eligible
rebalance, including those a live strategy would skip; without this, triggered and
non-triggered structural change are not comparable.

### 4.3 Frozen inference

All inference parameters were fixed before execution: placebo seed 20260817 with
100,000 draws; circular block bootstrap with 10,000 replicates and Politis–White
automatic block length, resampling the pair (VI*ₜ*, I*ₜ*) jointly in blocks to
preserve alignment; one-sided H₀: *D_VI* ≤ 0 with replicates centred on the
observed statistic; Holm step-down across the four candidates at family-wise
α = 0.05. Holm rather than Bonferroni because the trigger sets are highly
dependent across γ.

### 4.4 The stopping rule

Among candidates passing *every* hard criterion, select the value closest to the
inherited γ = 1.0, breaking ties toward the larger γ. **If none passes, the
investigation stops; the "least bad" candidate is not selected.** This rule is
applied automatically in code, not by the researcher.

---

## 5. Results

### 5.1 Static baselines and estimator sensitivity

Table 1 reports development-region performance for five static baselines under the
pre-registered nonlinear-shrinkage estimator.

**Table 1.** Static baselines, development region (2003–2022, 5,031 days).

| Strategy | Ann. return | Ann. vol | Sharpe | Max DD | Calmar | Ann. turnover |
|---|---:|---:|---:|---:|---:|---:|
| MinVar | 0.092 | 0.154 | 0.576 | −0.426 | 0.215 | 1.502 |
| HRP_static | 0.096 | 0.163 | 0.574 | −0.461 | 0.208 | 1.455 |
| ERC | 0.096 | 0.173 | 0.549 | −0.502 | 0.191 | 0.656 |
| MHRP_EV | 0.093 | 0.175 | 0.534 | −0.511 | 0.183 | 1.779 |
| EW | 0.094 | 0.191 | 0.508 | −0.560 | 0.168 | 0.640 |

An independent accounting reconciliation — recomputing the portfolio return series
from the stored weight path and realised asset returns, without reusing the
engine's arithmetic — matches the engine's gross returns to a median absolute
difference of 0.0 for all five strategies.

**Table 2** and Figure 4 report the estimator sensitivity sweep. Diagnostic only;
selects nothing.

**Table 2.** Estimator sensitivity (Sharpe).

| Strategy | ewma_cc | lw_linear | nls | sample |
|---|---:|---:|---:|---:|
| ERC | 0.558 | 0.549 | 0.549 | 0.549 |
| EW | 0.508 | 0.508 | 0.508 | 0.508 |
| HRP_static | **0.608** | 0.591 | 0.574 | 0.594 |
| MHRP_EV | 0.568 | 0.554 | 0.534 | 0.557 |
| MinVar | 0.588 | 0.551 | 0.576 | 0.556 |

Equal weighting is invariant across estimators (0.508), as it must be: it never
consults the covariance matrix. This serves as a negative control confirming that
the observed differences are attributable to the estimator.

Two findings follow, both bounded to the development region. First, exponentially
weighted constant-correlation covariance improves every covariance-dependent
strategy examined, most strongly HRP_static (0.574 → 0.608); it is the largest
estimator effect in the table. Second, the equal-volatility allocation
(MHRP_EV) remains below static HRP under *every* estimator (0.568 vs 0.608; 0.554
vs 0.591; 0.534 vs 0.574; 0.557 vs 0.594). Since the ordering is invariant to the
estimator, the underperformance is attributable to the allocation rule rather than
to a covariance interaction. Taken together these separate two components of
Molyboga's (2020) construction: the covariance modification transfers to this
equity universe; the allocation modification does not.

We note that `ewma_cc` outperforms the pre-registered `nls` specification on four
of five strategies. The pre-registered specification is therefore not the ex-post
best-performing estimator in this sample. **The design is not retroactively
changed to exploit this.**

### 5.2 The structural gate: no admissible threshold

Figure 1 shows the absorption-ratio series over the development region together
with the standardised change and the four candidate thresholds; Figure 2 summarises
the cluster-informativeness result.

**Table 3.** Frozen structural calibration gate. 233 eligible rebalances, *k* = 15.

| γ | events | firing | min ev/fold | CV gap | modal gap | *J\** | *J* thr | *D_VI* | *p* Holm | Admissible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 0.5 | 149 | 0.639 | 35 | 1.116 | 0.824 | 0.400 | 0.446 | +0.033 | 0.556 | No |
| 1.0 | 111 | 0.476 | 26 | 1.458 | 0.791 | 0.326 | 0.382 | +0.022 | 0.556 | No |
| 1.5 | 81 | 0.348 | 18 | 1.676 | 0.763 | 0.263 | 0.320 | +0.080 | 0.254 | No |
| 2.0 | 58 | 0.249 | 11 | 1.823 | 0.791 | 0.208 | 0.259 | +0.096 | 0.221 | No |

No candidate is admissible. The pattern of failure is informative:

**Separation passes everywhere.** *J\** ≤ threshold at every γ. The trigger is not
a disguised fixed schedule — a substantive negative finding, since that is the most
common failure mode for signals of this kind.

**Event sufficiency passes everywhere** (11–35 events per fold, all ≥ 3).

**Informativeness fails only at γ ∈ {0.5, 1.0}**, where firing rates of 0.639 and
0.476 exceed the 0.40 ceiling. The inherited γ = 1.0 fires on nearly half of all
eligible rebalances, which is difficult to reconcile with a description of the
events as unusual.

**Timing variation fails everywhere, on modal-gap share alone.** Every CV clears
its floor comfortably (1.116–1.823); the failure is that modal-gap share
(0.763–0.824) never approaches the 0.50 ceiling. Section 5.3 examines this.

**Cluster informativeness fails everywhere.** *D_VI* is positive at every γ and
increases with selectivity (+0.033 → +0.096), the direction the hypothesis
predicts. But no Holm-adjusted *p* clears 0.05 (best 0.221 at γ = 2.0). The
defensible statement is that the effect is **positive in direction but
statistically unresolved**: a positive point estimate does not establish that the
effect is real.

Even the strongest candidate, γ = 2.0 — which passes informativeness and
separation — is blocked by two criteria. Because failure is conjunctive and
because cluster informativeness fails independently at every γ, the conclusion does
not rest on the contested timing criterion.

**Per the frozen stopping rule, the investigation terminates here. No portfolio was
constructed and no performance quantity was computed.**

### 5.3 Post-mortem: is the burstiness an artefact of the pipeline?

The timing failure has a specific character: high CV *and* high modal-gap share
together mean most inter-event gaps are one rebalance with occasional long
quiescent stretches — the trigger fires in bursts. Two mechanisms could produce
this. Real markets may cluster covariance-concentration episodes in time; or the
estimation pipeline may manufacture bursts from overlapping windows, smoothing,
differencing, and a rolling scale denominator.

A placement null (random reallocation of the same number of events across the same
grid) rejects the hypothesis that the burstiness is a mere consequence of event
density: observed modal-gap share exceeds the placement null at every γ. But a
placement null cannot separate the two mechanisms above, because it never exercises
the pipeline.

We therefore pre-registered a **pipeline-level null**, frozen and hashed before execution, with the decision rule fixed in advance and applied mechanically. Three
environments are pushed through the *identical unmodified* frozen machinery,
preserving the real NaN mask, membership path, market caps, rebalance dates,
*W*, *k*, smoothing and σ̂:

- **A** — vol-matched Gaussian, zero cross-correlation, no time dependence (floor control);
- **S** — one static covariance Σ₀ fitted on development rows only, drawn i.i.d. through time: persistent cross-sectional structure, no regimes (adjudicating null);
- **D** — two-state Markov process in which both volatility *and* factor loadings scale, so covariance *concentration* genuinely shifts (positive control).

Because modal-gap share depends on event count, comparisons use a density-adjusted
statistic *B_γ* = *M_γ* − median(*M*^placement | *n_γ*), where the placement median
is a deterministic cached lookup keyed on the event count and shared with the real
data. 500 replications per environment (1,500 total).

Figure 3 shows the full null distributions against the real values.

**Table 4.** Pipeline-level null. Excess burstiness *B_γ*, 500 reps/environment.

| γ | real *B* | A (2.5–97.5%) | S (2.5–97.5%) | D (2.5–97.5%) |
|---|---:|:---:|:---:|:---:|
| 0.5 | 0.182 | 0.062 – 0.157 | 0.033 – 0.117 | 0.045 – 0.166 |
| 1.0 | 0.318 | 0.122 – 0.272 | 0.100 – 0.237 | 0.140 – 0.306 |
| 1.5 | 0.413 | 0.140 – 0.361 | 0.095 – 0.296 | 0.163 – 0.407 |
| 2.0 | 0.526 | 0.107 – 0.392 | 0.000 – 0.295 | 0.105 – 0.440 |

At every γ the real value exceeds the 97.5th percentile of both A and S, satisfying
the pre-registered condition for the "beyond regime-free mechanics" outcome. The
tested regime-free architectural explanations are therefore not supported.

Three qualifications. First, D does not bracket the real data either, so the
optional consistency-with-nonstationarity statement is unavailable; but since D's
states last approximately 100 and 33 daily observations against *W* = 504, a
504-day window spans roughly 3.8 complete cycles and materially averages the
designed regimes away. D is a *high-frequency* positive control, and its
non-overlap indicates that rapid regime switching is heavily attenuated by the
estimator rather than that regime explanations are excluded. Second, the D margins
are thin (+0.006 at γ = 1.5) and should not carry independent weight. Third, S
produced *less* excess burstiness than A at every γ — contrary to the hypothesis
that motivated S as the adjudicating null. We report this without explanation;
establishing one would require further work.

### 5.4 Empirical size of the inference procedure

Because the cluster-informativeness criterion is the binding constraint, its
calibration matters. We measured the empirical rejection rate under the null over
2,000 synthetic datasets at three replicate counts.

**Table 5.** Empirical size at nominal α = 0.05.

| *B* | rate | MC SE | 95% CI |
|---:|---:|---:|:---:|
| 600 | 0.0655 | 0.0055 | 0.0547 – 0.0763 |
| 2,000 | 0.0660 | 0.0056 | 0.0551 – 0.0769 |
| 10,000 | 0.0655 | 0.0055 | 0.0547 – 0.0763 |

The rate is stable across a seventeen-fold increase in replicates, so the
departure is a property of the procedure rather than a finite-*B* artefact. The
test is **mildly anti-conservative**: empirical size ≈ 6.6% against nominal 5%.

This strengthens rather than weakens the central result. The cluster-informativeness
test is biased *toward* rejection, and no candidate rejected.

---

## 6. Discussion

### 6.1 What the negative result establishes

Under a prospectively frozen, performance-blind admissibility standard, an
absorption-ratio change trigger does not qualify as an adaptive re-clustering
mechanism on this universe and development region. The trigger is not equivalent to
a fixed schedule, and its events are genuinely bursty relative to both random
placement and two regime-free pipeline nulls. But triggered rebalances are not
shown to identify moments of greater hierarchical restructuring.

The interesting asymmetry is that the trigger evidently responds to *something*.
Its timing is far from random, and its burstiness survives two architectural
explanations. What it does not do is align with the quantity the adaptive
hypothesis requires. A signal can react strongly to real covariance events without
those events being moments when re-clustering changes the tree in a statistically
reliable way — for instance if AR responds to concentration changes that leave the
dendrogram topology intact, or if it responds at a horizon offset from the
restructuring.

### 6.2 Why performance-blindness matters here

Had this study measured performance first, the natural path would have been: pick
γ = 1.0 (inherited), observe results, and — on encountering a 47.6% firing rate —
adjust the threshold. Each adjustment is individually defensible and collectively
fatal, in exactly the way Nikolopoulos (2026) quantifies.

The gate makes that path unavailable. The 0.40 firing ceiling was fixed before the
firing rate was known and was *not* revised when γ = 1.0 exceeded it. The γ grid
was fixed before any event count was computed. The stopping rule was executed in
code. There is no point at which a performance number could have influenced a
specification choice, because no performance number existed.

### 6.3 The Molyboga decomposition

The estimator sweep produces an unanticipated positive finding. Molyboga (2020)
proposes three modifications to HRP; two are separately implementable here. Within
the development region, the covariance modification improves every
covariance-dependent strategy tested, whereas the allocation modification remains
below static HRP under every covariance estimator. This suggests reported gains
from "modified HRP" may be attributable to the covariance treatment rather than the
allocation rule — a decomposition obscured when the modifications are evaluated
jointly.

We emphasise this is in-sample within the development region. The holdout was not
opened, and no out-of-sample claim is made.

---

## 7. Limitations

### 7.1 Statistical power

The result is a failure to reject, not a demonstration of absence. With 233
eligible rebalances and 4 folds, the design has limited power against small effects,
and *D_VI* is positive at every threshold. A larger universe, a longer sample, or a
higher rebalance frequency could plausibly resolve the effect. The honest claim is
that this evidence is insufficient, not that the effect is zero.

### 7.2 Single universe and single trigger family

One universe (CRSP large-cap, *N* = 100), one region, one trigger construction. The
absorption-ratio trigger is one member of a large family; failure here does not
generalise to eigenspace-rotation, correlation-distance, or change-point triggers.

### 7.3 The holdout was never opened

The single pre-registered holdout touch was not used. A machine-checkable assertion
in the released test suite verifies that the durable audit log records zero
analysis touches of the test region. This is a consequence of the design, not an
omission: performance evaluation was *conditionally inaccessible*, and no adaptive
specification earned access.

### 7.4 Reproducibility incidents

Two defects were found and are documented in full. A figure in the frozen
pre-registration cited a Phase 0.5 re-clustering count as though it were a trigger
count (corrected by erratum; no conclusion affected). Separately, a commit deleted
the equal-volatility allocator while the driver still declared it, rendering an
archived result temporarily unreproducible; the code was restored from history and
the archived value reproduced exactly. Both are recorded in the released
supplement, and regression tests now cover both failure modes.

---

## 8. Conclusion

We proposed and applied a protocol in which an adaptive portfolio mechanism must
demonstrate structural informativeness against a frozen, performance-blind gate
before performance evaluation becomes available. Applied to an absorption-ratio
re-clustering trigger, the gate returned no admissible threshold, and the
investigation terminated without a portfolio being constructed and without the
holdout being opened.

The mechanism's timing is not random and is not reproduced by two regime-free
pipeline nulls, so it is detecting something. What it is not shown to detect is
statistically distinguishable change in the hierarchical dependence structure —
the quantity the adaptive hypothesis requires.

We suggest the value of this result lies less in the specific mechanism than in the
demonstration that a pre-registered structural standard can be specified precisely
enough to be executed automatically, and can return a negative answer that survives
adversarial review without being rewritten. The natural next question is not how to
make this trigger pass, but what |ΔAR| is actually tracking — an alignment question
best addressed by comparing absorption-ratio changes against eigenspace rotation,
correlation-matrix distance, and tree instability directly.

---

## Acknowledgments

The author thanks [names, if anyone read drafts or discussed the work] for helpful
discussion. This is a single-author study; no independent party reviewed or authorised
the methodological decisions described here, and the protocol's commitments rest on
hashed specifications and commit timestamps rather than on external review (§7.6).

The author used a large language model to assist with drafting, literature review,
auditing the project's own records, and identifying methodological defects. The author
reviewed and verified all output and is responsible for the content.

Any remaining errors are the author's own.

## Data and Code Availability

All code, frozen specifications, decision records, errata, and result artefacts are
available at `github.com/opatel4/rac-hrp`. A reproducibility manifest pins SHA-256
hashes for 30 code modules, 6 result artefacts, 11 governing documents, and the
underlying data files, together with the software environment. CRSP data are
licensed and cannot be redistributed; the manifest records checksums so a licensed
replicator can verify identity.

## References

Akioyamen, P., Tang, Y. Z., & Hussien, H. (2020). A hybrid learning approach to detecting regime switches in financial markets. *ACM International Conference on AI in Finance (ICAIF '20)*, New York. DOI 10.1145/3383455.3422521.

Ang, A., & Timmermann, A. (2012). Regime changes and financial markets. *Annual Review of Financial Economics*, 4, 313–337. DOI 10.1146/annurev-financial-110311-101808.

Avellaneda, M. (2019). Hierarchical PCA and applications to portfolio management. Courant Institute of Mathematical Sciences, NYU. arXiv:1910.02310.

Bongiorno, C., Manolakis, E., & Mantegna, R. N. (2025). End-to-end large portfolio optimization for variance minimization with neural networks through covariance cleaning.

Deković, D., & Posedel Šimović, P. (2025). Hierarchical risk parity: Efficient implementation and real world analysis. *Future Generation Computer Systems*, 167, 107744. DOI 10.1016/j.future.2025.107744.

Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). Pseudo-mathematics and financial charlatanism: The effects of backtest overfitting on out-of-sample performance. *Notices of the American Mathematical Society*, 61(5), 458–471. DOI 10.1090/noti1105.

DeMiguel, V., Garlappi, L., & Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? *Review of Financial Studies*, 22(5), 1915–1953.

Hamilton, J. D. (1989). A new approach to the economic analysis of nonstationary time series and the business cycle. *Econometrica*, 57(2), 357–384.

Horvath, B., & Issa, Z. (2023). Non-parametric online market regime detection and regime clustering for multidimensional and path-dependent data structures. arXiv:2306.15835.

Kim, C.-J., & Nelson, C. R. (1998). Business cycle turning points, a new coincident index, and tests of duration dependence based on a dynamic factor model with regime switching. *Review of Economics and Statistics*, 80(2), 188–201. DOI 10.1162/003465398557447.

Kriuk, B., & Kriuk, F. (2026). ORCA — Online Regime Correlation Analyzer. Hong Kong University of Science and Technology / University of Technology Sydney.

Kritzman, M., Li, Y., Page, S., & Rigobon, R. (2011). Principal components as a measure of systemic risk. *Journal of Portfolio Management*, 37(4), 112–126. DOI 10.3905/jpm.2011.37.4.112.

Ledoit, O., & Wolf, M. (2004a). A well-conditioned estimator for large-dimensional covariance matrices. *Journal of Multivariate Analysis*, 88(2), 365–411. DOI 10.1016/S0047-259X(03)00096-4.

Ledoit, O., & Wolf, M. (2004b). Honey, I shrunk the sample covariance matrix. *Journal of Portfolio Management*, 30(4), 110–119.

Ledoit, O., & Wolf, M. (2022). The power of (non-)linear shrinking: A review and guide to covariance matrix estimation. *Journal of Financial Econometrics*, 20(1), 187–218. DOI 10.1093/jjfinec/nbaa007.

León, D., Aragón, A., Sandoval, J., Hernández, G., Arévalo, A., & Niño, J. (2017). Clustering algorithms for risk-adjusted portfolio construction. *Procedia Computer Science*, 108, 1334–1343. DOI 10.1016/j.procs.2017.05.185.

López de Prado, M. (2016). Building diversified portfolios that outperform out of sample. *Journal of Portfolio Management*, 42(4), 59–69. DOI 10.3905/jpm.2016.42.4.059.

López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. ISBN 978-1-119-48208-6.

Molyboga, M. (2020). A modified hierarchical risk parity framework for portfolio management. *Journal of Financial Data Science*, 2(3), 128–139.

Nikolopoulos, S. D. (2026). Spurious predictability in financial machine learning. arXiv:2604.15531 [preprint], University of Peloponnese.

Pafka, S., Potters, M., & Kondor, I. (2004). Exponential weighting and random-matrix-theory-based filtering of financial covariance matrices. arXiv:cond-mat/0402573.

Pergher, K. G. R., Soldera, J., & Scharcanski, J. (2026). An orthogonal hierarchical risk parity allocation method for improved portfolio out-of-sample performance. *IEEE Access*. DOI 10.1109/ACCESS.2026.3656702.

Politis, D. N., & White, H. (2004). Automatic block-length selection for the dependent bootstrap. *Econometric Reviews*, 23(1), 53–70.

Roncalli, T. (2013). *Introduction to Risk Parity and Budgeting*. Chapman & Hall/CRC.

Sheppert, A. P. (2026). The GT-Score: A robust objective function for reducing overfitting in data-driven trading strategies. *Journal of Risk and Financial Management* (MDPI), published 12 January 2026.

Shumway, T. (1997). The delisting bias in CRSP data. *Journal of Finance*, 52(1), 327–340.

Zhang, Y., Goel, D., Ahmad, H., & Szabo, C. (2025). RegimeFolio: A regime aware ML system for sectoral portfolio optimization in dynamic markets. arXiv:2510.14986.
