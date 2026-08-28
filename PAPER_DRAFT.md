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
thresholds, so the tested regime-free architectural explanations are not supported. A
repaired positive control, calibrated so its regime durations exceed the covariance
window, brackets the observed burstiness at three of four thresholds where the original
control bracketed none.

Separately, a frozen estimator sensitivity sweep tests whether two components of
Molyboga's (2020) modified HRP transfer to this setting: within the development
region, exponentially
weighted constant-correlation covariance improves every covariance-dependent
strategy examined, whereas the equal-volatility allocation modification remains
below static HRP under every covariance estimator.

Two pre-specified post-gate diagnostics then ask why. The first recomputes the
cluster-informativeness statistic at a horizon matched to the trigger: the smoothing
and differencing steps telescope, so the trigger is algebraically a five-rebalance
change in the absorption ratio, while the gate's criterion measured a one-rebalance
change in the clustering. At the matched horizon the effect is statistically
resolved at one of four thresholds and suggestive at a second, once the procedure's
measured size on the real dependence structure is taken into account. The second
measures what the gate could have detected: against the effect sizes actually
observed, its power ranged from 11% to 33%, and the minimum effect detectable at 80%
power was two to nine times larger than any effect present. A third set of
diagnostics finds the clustering-change effect is not stable in the retained-component
count: it changes sign across the values examined.

The negative result is therefore not evidence that the mechanism is uninformative.
It is what an underpowered test applied at the wrong horizon produces. We report
this as the paper's central finding rather than a caveat, because it identifies a
limit of the protocol itself: a prospectively frozen specification constrains the
choices a researcher can make after seeing results, but it does not verify that the
specified procedure measures what it claims to measure. The frozen gate was
internally consistent and correctly executed, and it could not have detected the
effect it was built to look for.

All code, frozen specifications, decision records, errata, and a hash-pinned
reproducibility manifest are released, including eight revisions of the post-gate
specification and the invalidated output of one that was frozen, executed, and found
incapable of the measurement it specified.

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

**A diagnosed negative result for an absorption-ratio trigger.** No threshold in the
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

**A transfer test of modified HRP components.** A frozen estimator sweep applies two
of Molyboga's (2020) three modifications, separately, to a large-cap equity universe.
The covariance modification transfers; the equal-volatility allocation reverses sign
relative to its managed-futures result, under every estimator tested.

**A hash-pinned reproducibility record**, including a machine-checkable assertion
that the holdout sample was never opened. This is a single-author study, so the
protocol's commitments rest on hashed specifications and commit timestamps rather
than on independent review (Section 7.6).

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
shrinkage in a managed-futures context. Bongiorno et al. (2026) pursue learned
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

The smoothing and differencing steps telescope. For any rebalance at which the
five-period window is complete, substitution gives

> ΔAR^s*ₜ* = (1/5)(AR*ₜ* − AR*ₜ₋₅*),

so the trigger statistic is a five-rebalance change scaled by 1/5, not a local one.
At monthly rebalancing this is a change measured over approximately 105 trading days.
The smoothing window is defined in rebalances rather than days; the frozen
specification records the correction of an earlier configuration field that had
implied the latter. We state the identity explicitly because it governs the interpretation of two later results (Sections 5.5 and 6.1).

Three properties follow. First, consecutive values of ΔAR^s share four of five
constituent AR terms, so the series carries moving-average dependence by
construction. This compounds the persistence already induced by the covariance
window: consecutive *W* = 504 day windows stepped by 21 days share 483 observations,
an overlap of 95.8%. Second, an isolated jump in AR at date τ enters the difference
twice, at τ and again at τ + 5 with opposite sign, and because the threshold is
two-sided both crossings can fire. Third, a sustained drift in AR across several
rebalances keeps the difference large at consecutive *t*, producing runs of adjacent
events. The mechanism is a detector of low-frequency change in covariance
concentration, and its event sequence is expected to be temporally clustered rather
than isolated.

The scale is lagged one rebalance so that no contemporaneous information enters, and
the lag is what binds the warm-up: ΔAR^s is first defined at the second rebalance,
the scale window reaches six observations at the seventh, and the lag defers the
first admissible firing to the eighth. The five-period mean is computed with a
minimum of one observation, so the earliest values of AR^s are partial-window means
and the identity above holds exactly only from the sixth rebalance onward.

The pre-registration recorded, before the gate was specified, that the inherited
threshold's firing rate materially exceeds what an i.i.d. normal ΔAR would produce at
the same threshold — 46.7% against 31.7% — and attributed the excess to heavy tails
or volatility clustering in ΔAR combined with a short twelve-observation scale
estimate that is frequently too small, making the realised threshold looser than
γ = 1 implies. Both mechanisms, the moving-average dependence above and the noisy
scale denominator, push in the same direction, and neither is a property of the data
alone.

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

We note a limitation of that choice, since power is this paper's central problem.
Holm does not exploit dependence; it relaxes the Bonferroni constraint stepwise
under arbitrary dependence. The bootstrap stepdown procedure of Romano and Wolf
(2005) is designed for precisely this setting and would be more powerful at the same
family-wise error rate given the dependence documented here. It was not used, and
the gate is frozen, so the choice stands for the confirmatory result. The wider literature
on multiple testing in finance — White (2000), Hansen (2005), Harvey and Liu (2015),
Harvey, Liu and Zhu (2016) — bears directly on the design of gates of this kind.

### 4.4 The stopping rule

Among candidates passing *every* hard criterion, select the value closest to the
inherited γ = 1.0, breaking ties toward the larger γ. **If none passes, the
investigation stops; the "least bad" candidate is not selected.** This rule is
applied automatically in code, not by the researcher.

---

### 4.5 Phase 0.5: staged falsification audit

Before the structural gate was specified, the full RAC-HRP implementation was subjected
to a staged falsification audit of the kind advocated by Nikolopoulos (2026): the
complete pipeline is executed on inputs that destroy the quantity it claims to exploit,
and is required to produce no material edge. A pipeline that manufactures Sharpe from
signal-free data cannot support a claim of Sharpe from real data. The audit ran in two
versions. The first (v1) executed under its original rules and its results are preserved
unaltered; the second (v2) was prospectively frozen after v1's outcome was decomposed,
and is the version whose verdicts we rely on. We describe both and the transition between
them, because the transition is itself a decision this paper's thesis makes relevant.

Four environments were used: A, i.i.d. Gaussian, testing for look-ahead; B,
cross-sectional shuffle, testing for leakage through asset identity; C, which retains
real development-region returns but randomises the timing at which the absorption-ratio
trigger fires, testing whether the trigger's timing contributes anything; and D,
regime-switching volatility with no return signal, testing whether any edge is volatility
timing in disguise. The decision rule is a one-sided equivalence test against a
materiality margin of +0.10 in annualised Sharpe units. The rule is one-sided because a
pipeline manufacturing signal from noise produces a positive edge; a negative excursion
is not the failure mode the audit exists to detect. All runs are on the development
region.

Environment C is the sharpest test of this paper's premise, since a pipeline that
performs as well with a randomly timed trigger has no absorption-ratio content. It
passed: a Sharpe difference of -0.0016 against static HRP and +0.0046 against periodic
HRP, both far inside the margin. Environments A and B passed cleanly against the
same-policy baselines.

Version 1 returned one failure: RAC-HRP versus ERC under environment D, +0.102, CI
[+0.038, +0.167]. One further cell, RAC-HRP versus equal weighting under the same
environment, had a confidence interval extending to -0.108 and so past the margin on the
untested side; it passed the rule as specified and is noted for completeness.

The pattern around the failing cell is diagnostic. A trigger-specific manufactured
advantage should appear against otherwise identical same-policy baselines, which differ
from RAC-HRP only in re-clustering rule; it did not. RAC-HRP showed no edge over static
HRP (-0.006, CI [-0.066, +0.054]) and none over equal weighting. A paired recovery replay
confirmed that static HRP, which never re-clusters, beats ERC under D by +0.109 (CI
[+0.049, +0.168]), so essentially the entire difference is an HRP-versus-ERC allocator
property under volatility clustering and none of it is attributable to the trigger. We
claim only the allocator-family interpretation; the mechanism by which the two allocators
diverge is not asserted.

We record how the cell was resolved, and we do so at length because the sequence is one
this paper elsewhere criticises. A comparator restriction was adopted immediately after
the cell it affects returned a failure. Before adopting it, a decision memorandum was
written setting out two alternatives -- restricting environment D to same-policy
comparators, extending a principle already applied to environment C during
implementation, or leaving the gate unchanged and reporting the failure as a
characterised finding -- together with the decomposition above and an explicit statement
that the sequence resembles altering a test until it passes. That memorandum is released.
But this is a single-author study: the author wrote the options and chose between them,
and no independent party ruled. The mitigation the memorandum itself identified is
therefore absent.

We do not ask the reader to accept the choice on trust. Both verdicts are reported. Under
the original v1 rule, the audit fails on one cross-allocator cell. Under the v2 rule,
which restricts the gating tier to same-policy comparators and retains cross-allocator
contrasts as non-gating diagnostics, it passes. The decomposition above is the
substantive argument for the restriction and is independent of who made it; a reader who
finds it unpersuasive may apply the v1 rule throughout, in which case the audit is
reported as failing on an HRP-versus-ERC allocator contrast under a regime-switching
volatility environment, with the same downstream consequences for Phase 2, which is
unaffected either way. Version 1 results are preserved unaltered and released.

The v2 protocol was written and hashed before v2 execution: the protocol document, the
code, the base seed, the replication counts, and the decision rules were all fixed in
advance, and the holdout remained closed throughout. What v2 lacks relative to the design
as originally conceived is external authorisation, not prospective specification.

Under v2, all eight primary cells passed, with the largest same-policy difference +0.0132
against a margin of +0.10, and every positive control correctly classified as failing,
establishing that the gate had power to reject. The diagnostic panel records the
cross-allocator differences in full, including RAC-HRP versus ERC under D at +0.093
alongside static HRP versus ERC at +0.083.

Two limitations. The v1 run used 100 replications, at which the positive control was
inconclusive at zero injected signal, so the margin sat near the resolution limit; v2
raised replication counts to 150 per environment and 200 for D. And a clean pass supports
only that the trigger does not manufacture a material positive difference against
same-policy baselines. It does not establish the mechanism of the cross-allocator
difference, which would require weight-path analysis outside this paper's scope.

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
to a covariance interaction. Molyboga (2020) evaluates his three modifications
incrementally and reports a marginal gain at each; the two separately implementable
here behave differently in this setting. The covariance modification transfers to
this equity universe; the allocation modification does not.

We note that `ewma_cc` outperforms the pre-registered `nls` specification on four
of five strategies. The pre-registered specification is therefore not the ex-post
best-performing estimator in this sample. **The design is not retroactively
changed to exploit this.**

A sharper version of the same observation deserves stating. For HRP_static, `nls`
is strictly the worst of the four estimators (0.574), below even unshrunk sample
covariance (0.594); the same ordering holds for MHRP_EV (0.534 against 0.557).
Nonlinear shrinkage underperforming the sample estimator is unexpected under the
usual argument for shrinkage, and HRP offers a candidate explanation: the allocator
consumes only the correlation-distance ordering and the resulting dendrogram, not
the covariance matrix itself. Aggressive eigenvalue shrinkage can alter that
ordering without improving the quantities HRP actually uses. We do not test this and
report it as an observation, not a finding.

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

D, however, does not bracket the real data either. As specified it was the positive
control — the environment in which covariance concentration genuinely shifts and
which the pipeline should therefore resolve — and its failure to bracket meant the
experiment's sensitivity was never demonstrated. Two features explain it. D's states
persist approximately 100 and 34 daily observations against *W* = 504, so a single
covariance window spans roughly four complete regime cycles and materially averages
the designed structure away. And the D margins are thin: real exceeds the upper
bound by only +0.006 at γ = 1.5, within Monte Carlo variation at 500 replications.

**A W-calibrated positive control.** We therefore pre-specified a repaired control,
frozen and hashed before implementation, differing from D in one respect: the state
persistence probabilities are lengthened from (0.99, 0.97) to (0.999, 0.9985), giving
mean regime durations of 1000 and 667 days against 100 and 34. Both now exceed *W*,
so a covariance window can lie within a single regime. Everything else is unchanged —
factor structure, volatility and loading scaling, zero conditional mean in both
states — and the density correction is loaded from the frozen manifest rather than
recomputed, so the arms remain directly comparable. The frozen D result stands
unaltered; this is an addition, not a replacement. The transition mechanism itself was
verified correct by simulation before the repair, so the defect is duration alone.

Realised regime durations averaged 1224 and 761 days across 500 replications, with
37.2% of time in the high state.

**Table 5.** W-calibrated positive control, 500 replications.

| γ | real *B* | D_slow (2.5–97.5%) | frozen D (2.5–97.5%) | real is |
|---|---:|:---:|:---:|:---:|
| 0.5 | 0.182 | 0.044 – 0.201 | 0.045 – 0.166 | inside |
| 1.0 | 0.318 | 0.128 – 0.339 | 0.140 – 0.306 | inside |
| 1.5 | 0.413 | 0.176 – 0.437 | 0.163 – 0.407 | inside |
| 2.0 | 0.526 | 0.163 – 0.512 | 0.105 – 0.440 | above |

The repaired control brackets the observed burstiness at three of four thresholds,
against none under the original. Under the pre-registered decision rule this is the
outcome in which the control resolves and the burstiness result survives: real
burstiness is consistent with genuine slow regime structure while remaining
inconsistent with the regime-free environments A and S. The frozen D remains
informative as a *high-frequency* control, and its non-overlap is now attributable to
the estimator attenuating rapid switching rather than to any failure of the regime
explanation.

One residual. At γ = 2.0 the real value still exceeds the upper bound, by +0.014.
The most selective threshold produces burstiness beyond what even slow regime
switching generates in this design, and we do not explain it.

A further qualification carries over from the original run: S produced *less* excess
burstiness than A at every γ, contrary to the hypothesis that motivated S as the
adjudicating null. We report this without explanation; establishing one would require
further work.

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
test is biased *toward* rejection, and no candidate rejected. Section 5.5 measures the
same quantity on the real dependence structure rather than on independent data and
obtains 7.3%; the argument here survives, and its magnitude was understated.

---

### 5.5 Post-gate diagnostics (pre-specified, non-gating)

Two diagnostics were specified after the gate returned its verdict, frozen and
hashed before any implementing code was written, and run once each. Neither can
render any threshold admissible; the Phase 2A verdict is unchanged by both. The
holdout remained closed throughout.

**Horizon-matched cluster informativeness.** Section 4.1 establishes that the
trigger statistic is a five-rebalance change in the absorption ratio, while the
gate's cluster-informativeness criterion measures change in the clustering between
consecutive rebalances. The two are sampled at different horizons. We recompute
*D_VI* with variation of information taken between the clustering at *t* and at
*t*−5, on the intersection of the corresponding universes, using the frozen
statistic and the frozen inference unchanged.

| γ | events | *D_VI*(5) | *p* raw | *p* Holm | block | med VI fired | med VI not |
|---|---|---|---|---|---|---|---|
| 0.5 | 149 | +0.0662 | 0.043 | 0.086 | 13 | 0.8226 | 0.7564 |
| 1.0 | 111 | +0.0600 | 0.045 | 0.086 | 13 | 0.8215 | 0.7616 |
| 1.5 | 81 | +0.0814 | 0.005 | 0.018 | 13 | 0.8382 | 0.7567 |
| 2.0 | 58 | +0.1038 | 0.014 | 0.042 | 13 | 0.8620 | 0.7582 |

At the matched horizon, Holm-adjusted *p* clears 0.05 at γ = 1.5 and γ = 2.0. That
comparison is against a nominal level, and the same diagnostic measures the
procedure's actual size on this dependence structure as 0.0730. Judged against
actual rather than nominal size, only γ = 1.5 (raw *p* = 0.005) is resolved; γ = 2.0
(raw *p* = 0.014) is suggestive but weaker than its Holm value implies; and γ = 0.5
and γ = 1.0 (raw *p* = 0.043 and 0.045) sit at or below the measured size and carry
essentially no evidence. We apply this correction to the positive result because we
apply it to the null in Section 5.4, and applying it in only one direction would be
the asymmetry this paper exists to criticise.

At the gate's
horizon no threshold cleared. The point estimates are larger at every threshold and
the ordering with selectivity is preserved.

**Detectable effect size.** We measure the smallest true *D_VI* the frozen inference
could have detected at 80% power, on the dependence structure the gate faced. Each
replication draws a circular block resample of the observed VI series at its
selected block length, pairs it with the frozen trigger masks, and plants an effect
δ at the positions designated for one target threshold, leaving the other three
null. All four candidate tests are computed and Holm-adjusted exactly as the gate
does, and rejection of the target is recorded. Two placement conditions are used:
the realised trigger positions, and an equal number drawn uniformly.

Empirical size at δ = 0 is 0.0730 (Monte Carlo standard error 0.0058), against the
0.0660 previously measured on independent data. The procedure is mildly
anti-conservative on the real dependence structure, somewhat more so than the
earlier figure indicated.

| γ | observed *D_VI* | power at that effect | MDE₈₀ (realised placement) |
|---|---|---|---|
| 0.5 | +0.033 | ≈0.13 | (0.15, 0.20] |
| 1.0 | +0.022 | ≈0.11 | (0.15, 0.20] |
| 1.5 | +0.080 | ≈0.28 | (0.15, 0.20] |
| 2.0 | +0.096 | ≈0.33 | (0.20, 0.30] |

Against the effects actually observed, the gate's power ranged from roughly 11% to
33%. The smallest effect it could have detected at 80% power was between two and
nine times larger than any effect present in the data.

Under uniform placement, power never reaches 0.08 at any threshold or any effect
size, and falls monotonically below nominal size as δ grows, reaching 0.022 at
δ = 0.30. A large effect distributed evenly across the eligible dates makes the test
*less* likely to reject than no effect at all. The difference-of-medians statistic
is not merely insensitive to dispersed effects; it is biased against them. This is a
property of the criterion rather than of the trigger, and any mechanism evaluated
against this criterion inherits it.

### 5.6 Robustness diagnostics (pre-specified, non-gating)

Three further diagnostics were specified together after the gate returned its
verdict, frozen and hashed before implementation, and run once. As with the
diagnostics in Section 5.5, none can render a threshold admissible. The
specification also fixed in advance that no result here would cause the confirmatory
analysis to be re-specified: the gate remains *k* = 15, difference-of-medians, and a
one-rebalance horizon whatever these show. Each diagnostic contains a cell required
to reproduce a frozen result exactly, and all three reproduced.

**Sensitivity to the retained-component count.** The absorption ratio is the share of
variance in the leading *k* components, and *k* = 15 was fixed at the
Marchenko–Pastur count of the first eligible rebalance and held for twenty years. We
recompute the entire trigger series and the frozen gate statistic at
*k* ∈ {10, 15, 20, 25}.

| *k* | AR range | events (γ = 0.5 … 2.0) | *D_VI* (γ = 0.5 … 2.0) | Holm *p* |
|---|---|---|---|---|
| 10 | 0.498–0.779 | 147, 112, 83, 60 | +0.005, +0.029, +0.064, +0.061 | 0.554, 0.554, 0.282, 0.476 |
| 15 | 0.566–0.812 | 149, 111, 81, 58 | +0.033, +0.022, +0.080, +0.096 | 0.559, 0.559, 0.246, 0.195 |
| 20 | 0.617–0.838 | 155, 110, 79, 59 | −0.040, −0.005, −0.009, −0.002 | 1.000, 1.000, 1.000, 1.000 |
| 25 | 0.662–0.861 | 151, 111, 73, 60 | +0.041, +0.095, +0.081, +0.124 | 0.135, 0.025, 0.025, 0.003 |

The *k* = 15 row reproduces the frozen gate exactly, as required. The result is not
stable across the grid. The effect is weakly positive at *k* = 10, positive at the
frozen *k* = 15, **negative at every threshold at *k* = 20**, and positive and
nominally significant at three thresholds at *k* = 25. Event counts are broadly
similar throughout, so the instability is in the statistic rather than in how often
the trigger fires.

We do not report the *k* = 25 column as a finding. The specification fixed *k* = 15
before the gate ran and fixed, before this diagnostic ran, that no value would be
re-selected in light of it. What the sweep establishes is that the sign of the
clustering-change effect depends on a parameter chosen by a rule applied at a single
date in 2003, and that the paper's central quantity is therefore not robust to it.

**A continuous alternative to the binarised statistic.** The frozen criterion
thresholds the trigger and compares medians across the two arms, discarding the
magnitude of |ΔAR|/σ̂ entirely. Section 5.5 showed the resulting statistic is biased
against dispersed effects. We therefore compute the Spearman rank correlation between
*VI_t* and the continuous trigger strength *z_t* = |ΔAR_t|/σ̂_t over the eligible
rebalances, with the frozen inference otherwise unchanged: circular block bootstrap,
10,000 replicates, Politis–White block length, the pair resampled jointly, one-sided.

ρ = +0.072, one-sided *p* = 0.239, block length 19, *n* = 233. There is no
multiplicity adjustment because there is no threshold grid and hence exactly one
test, which also makes this *p*-value incomparable to the gate's Holm-adjusted
values.

The continuous statistic does not resolve an effect the binarised one missed. This is
informative against a natural objection: the gate's criterion discards information,
but recovering that information does not recover an effect. Binarisation was not the
binding constraint.

**Robustness of the horizon-matched result.** Section 5.5 reports the
clustering-change effect at *h* = 5, the horizon the frozen smoother forces. A reader
cannot distinguish a pre-specified horizon that happens to work from a knife-edge
without the curve, so we compute *D_VI* at *h* ∈ {1, …, 8}.

| *h* | γ = 0.5 | γ = 1.0 | γ = 1.5 | γ = 2.0 |
|---|---|---|---|---|
| 1 | +0.033 (0.571) | +0.022 (0.571) | +0.080 (0.239) | +0.096 (0.185) |
| 2 | +0.094 (0.014) | +0.022 (0.530) | +0.095 (0.021) | +0.102 (0.054) |
| 3 | +0.060 (0.058) | +0.067 (0.030) | +0.093 (0.010) | +0.129 (0.029) |
| 4 | +0.085 (0.043) | +0.060 (0.126) | +0.100 (0.011) | +0.121 (0.016) |
| 5 | +0.066 (0.093) | +0.060 (0.093) | +0.081 (0.018) | +0.104 (0.047) |
| 6 | +0.097 (0.000) | +0.102 (0.000) | +0.123 (0.000) | +0.154 (0.000) |
| 7 | +0.058 (0.155) | −0.007 (0.656) | +0.075 (0.101) | +0.135 (0.000) |
| 8 | +0.011 (0.649) | +0.015 (0.649) | +0.069 (0.266) | +0.105 (0.044) |

Holm-adjusted *p* in parentheses. *h* = 1 reproduces the frozen gate and *h* = 5 the
horizon-matched result, both as required.

The result at *h* = 5 is not a knife-edge: effects appear across *h* = 2 to *h* = 6.
But the curve is not monotone and does not peak at the pre-specified horizon. *h* = 6
is the strongest cell in the table at every threshold, and *h* = 7 collapses. We
report *h* = 5 as the inferential claim because the specification fixed it before
execution and because it follows algebraically from the frozen smoother. Reporting
the maximum over *h* would be a search of the kind this paper exists to avoid, and we
note that a reader who does not accept the *h* = 5 pre-specification has, in this
table, everything needed to reach a different conclusion.

One implementation note. At *h* = 8 a single rebalance falls below the
minimum-overlap floor for the universe intersection, producing an undefined *VI*. The
frozen difference-of-medians statistic takes medians without filtering, so one
undefined value propagates to both arms. Positions with undefined *VI* are dropped
from the series and the trigger masks together before the statistic and the
bootstrap, and the retained count is recorded. No other horizon is affected, and the
frozen gate is unaffected because its single undefined position falls outside the
eligible set.

### 5.7 Total trial count

A paper arguing that unrecorded trial counts are the disease should record its own.
Table 12 gives every test statistic computed on the development region across all
phases.

| Phase | What was computed | Tests |
|---|---:|---:|
| 2A gate | five criteria × four γ | 20 |
| 2A separation | Monte Carlo threshold at each candidate's own event count | 4 |
| 2A inference | bootstrap + Holm across four γ | 4 |
| Phase 0.5 v1 | primary and cross-allocator cells | 11 |
| Phase 0.5 v2 | eight primary + twelve diagnostic-panel cells | 20 |
| Estimator sweep | five strategies × four estimators | 20 |
| 2D burstiness null | four γ × three environments | 12 |
| 2E-HORIZON | four γ at one horizon | 4 |
| 2E-POWER | 64 grid cells + one size cell | 65 |
| 2F control | four γ, one environment | 4 |
| 2G-K | four k × four γ | 16 |
| 2G-RANK | one rank correlation | 1 |
| 2G-HORIZON | eight horizons × four γ | 32 |
| **Total** | | **213** |

The raw total is not the relevant multiplicity, and reporting it alone would
overstate the problem as badly as omitting it would understate it. What matters for
inference is how many of these were points at which a specification choice could have
been made in light of a result.

By construction, almost none were. The five gate criteria are conjunctive and were
fixed before any was evaluated; failing one is sufficient, so they do not constitute
a search across criteria. The estimator sweep selects nothing and is labelled
diagnostic in its own table caption. The 2E-POWER grid is a simulation over planted
effect sizes, not a set of hypotheses about the data. The 2G cells are sensitivity
analysis under a specification clause that forbids re-selecting the confirmatory
analysis in light of them, and Section 5.6 reports the *k* = 25 column without
adopting it. The post-gate diagnostics were each frozen before implementation with
their decision rules fixed.

The genuine selection points are the four values of γ, and multiplicity across them
is controlled by Holm within each criterion, as pre-registered.

Two qualifications against our own position. First, the sequence of post-gate
diagnostics was itself chosen after seeing that the gate returned a null, and each
was motivated by a specific failure — the horizon mismatch by an algebraic property,
the power analysis by external review, the *k* sweep likewise. That the individual
analyses were frozen before execution does not make the decision to run them
independent of the outcome that prompted them, and Section 5.5 states this ordering.
Second, one specification required eight revisions and another two, all recorded; a
reader may reasonably count revision as a form of search even where each revision is
documented with its reason and every superseded version is preserved.

## 6. Discussion

### 6.1 What the negative result establishes

Under a prospectively frozen, performance-blind admissibility standard, an
absorption-ratio change trigger does not qualify as an adaptive re-clustering
mechanism on this universe and development region. The trigger is not equivalent to
a fixed schedule, and its events are genuinely bursty relative to both random
placement and two regime-free pipeline nulls. But triggered rebalances are not
shown to identify moments of greater hierarchical restructuring.

That statement is accurate and it is the outcome the protocol produced. What the two
post-gate diagnostics establish is that it should not be read as evidence about the
mechanism.

The gate had between 11% and 33% power against the effect sizes actually present
(Section 5.5). A test with 33% power fails to reject two times in three when the
effect is real. A null from such a test carries almost no information about whether
an effect exists, and the interpretation that a performance-blind null is more informative than a performance-based one does not survive it. Blindness to returns protects against one failure mode. It does
not confer sensitivity.

The horizon diagnostic identifies a second, independent problem. The criterion
sampled structural change at a one-rebalance horizon while the trigger operates at
five. At the matched horizon the effect is resolved at one threshold and suggestive
at a second, judged against the procedure's measured size rather than its nominal
level (Section 5.5).
Either defect alone would have produced the observed null; both were present.

That result does not survive robustness testing intact. The clustering-change effect
is positive at three of the four component counts examined and *negative at every
threshold* at the fourth (Section 5.6), so its sign depends on a parameter fixed by a
rule applied at a single date at the start of the sample. A continuous rank statistic,
which discards none of the trigger's magnitude information, does not resolve the
effect either. And the horizon curve, while showing effects across a range of horizons
rather than at an isolated point, peaks at h = 6 rather than at the pre-specified
h = 5.

The honest summary is that the trigger's relationship to hierarchical restructuring is
not robustly established. It appears at some horizons and some component counts, is
absent at others, and the design had 11% to 33% power against the effect sizes
involved. We report the pre-specified results as the inferential claims and the
sensitivity alongside them, and we do not represent the horizon-matched result as a
finding that survives scrutiny it has not survived.

What survives is narrower than the horizon result alone suggested. The trigger's
timing is not random, and its burstiness is not reproduced by either regime-free
pipeline null while being consistent with a *W*-calibrated regime environment
(Section 5.3); neither of those results depends on the component count. What does not
survive is the stronger claim that triggered rebalances reliably coincide with greater
hierarchical restructuring.

None of this makes any threshold admissible. The gate is conjunctive, and every
candidate fails timing variation on modal-gap share alone — the two lowest also fail
informativeness. Even setting cluster informativeness aside entirely, no threshold
passes. The mechanism as specified is not usable, and the diagnostics do not change
that; they change what we can conclude about why.

### 6.2 Why performance-blindness matters here

Had this study measured performance first, the natural path would have been: pick
γ = 1.0 (inherited), observe results, and — on encountering a 47.6% firing rate —
adjust the threshold. Each adjustment is individually defensible and collectively
fatal, in exactly the way Nikolopoulos (2026) quantifies.

The gate makes that path unavailable, and the record shows the constraint binding at
the moment it cost something. The firing rate of the inherited threshold was known
before the gate was specified: an early revision of the pre-registration reports it
as a central vulnerability and analyses its causes (Section 4.1). The 0.40
informativeness ceiling was then set in full knowledge that γ = 1.0 exceeded it.
Every subsequent revision, through to the frozen version, records that γ = 1.0 has
already failed the firing-rate criterion and states explicitly that the ceiling is
not revised. The γ grid was fixed before any event count was computed, and the
stopping rule was executed in code.

What the design excludes is not knowledge of the trigger's structural behaviour,
which was necessary to specify a sensible gate at all, but knowledge of what any
specification choice would do to returns. No performance quantity for any adaptive
specification existed on the development region at any point in the process. The
distinction matters: a gate calibrated in ignorance of firing behaviour would have
been arbitrary, whereas a gate calibrated against firing behaviour and then held
fixed against the researcher's own inherited preference is the case where
pre-registration does work.

### 6.3 Transfer of the modified HRP components

The estimator sweep produces an unanticipated finding about an existing result.
Molyboga (2020) proposes three modifications to HRP and evaluates them incrementally,
constructing a ladder from the base algorithm through exponentially weighted shrinkage
covariance, then equal-volatility allocation, then volatility targeting, and reporting a
marginal improvement at each rung. The decomposition is his, not ours. What our sweep
contributes is a test of whether the two separately implementable components transfer to
a different asset class and a much larger cross-section.

They do not transfer alike. Within the development region, exponentially weighted
constant-correlation covariance improves every covariance-dependent strategy examined,
most strongly static HRP. The equal-volatility allocation, by contrast, remains below
static HRP under every one of the four covariance estimators tested. In Molyboga's
setting that component improved performance; here its sign is reversed, and the reversal
holds under each estimator independently.

The relevant difference is plausibly the cross-sectional dimension. Molyboga's portfolios
contain between five and twenty managed-futures programmes; ours contain one hundred
equities. Equal-volatility allocation distributes weight without reference to the
covariance structure within a cluster, which is a defensible approximation when clusters
are small and their members are already volatility-targeted, and a costlier one when
clusters are large and heterogeneous in volatility. We do not test this explanation and
do not claim it; establishing it would require a weight-path decomposition across cluster
sizes.

The invariance is what carries the finding. Because the ordering of static HRP above the
equal-volatility variant is preserved across sample, linear-shrinkage,
nonlinear-shrinkage and exponentially weighted covariance alike, the underperformance is
attributable to the allocation rule rather than to an interaction with any particular
estimator. Equal weighting, which never consults the covariance matrix, is invariant
across estimators as it must be, confirming that the observed differences are estimator
effects rather than noise in the backtest.

Two constraints on how far this can be taken. These are development-region results; the
holdout was not opened and no out-of-sample claim is made. And no inference is attached to
the individual Sharpe differences in Table 3, which are point estimates from a single
sample without standard errors or multiplicity control across the twenty
estimator-strategy cells. The claim we make is the qualitative one -- that the sign of the
allocation effect reverses relative to Molyboga's setting and does so under every
estimator -- not that any particular magnitude in the table is distinguishable from
zero.

---

## 7. Limitations

### 7.1 Statistical power

The gate's power against the effect sizes present in the data was measured after the
fact and found to be between 11% and 33% (Section 5.5). The minimum effect
detectable at 80% power was in the interval (0.15, 0.20] at three thresholds and
(0.20, 0.30] at the fourth, against observed effects of +0.022 to +0.096.

This is a design failure, not a sampling accident. With 233 eligible rebalances,
strong serial dependence in the variation-of-information series — lag-1
autocorrelation near 0.47, selected block length 13 — and trigger events arriving in
tight bursts that reduce the number of independent episodes far below the nominal
event count, the design never had the resolution its criterion required. A power
analysis conducted before the gate was frozen would have shown this, and the
pre-registration did not require one.

The reported figures are conditional on the observed dependence realisation: they
answer what this design could have detected on this data, not what it would detect
on average across a population.

### 7.2 Horizon alignment between trigger and criterion

The trigger statistic measures change in the absorption ratio over five rebalances
(Section 4.1) while the cluster-informativeness criterion measures change in the
clustering over one. The pre-registration did not require these horizons to agree, and
the gate was frozen without the mismatch being identified. The negative result
therefore establishes that the trigger is uninformative about one-rebalance
restructuring under the frozen procedure; it does not establish that the trigger is
uninformative about hierarchical structure generally. A subsequent pre-registration of
this protocol should specify the trigger and criterion horizons jointly.

The instability is broader than horizon alone. Section 5.6 reports that the
clustering-change effect changes sign across the retained-component count, being
negative at every threshold at k = 20. The gate's construction therefore involved at
least two choices — the measurement horizon and the component count — on which the
central result depends and neither of which the pre-registration subjected to
sensitivity analysis. A subsequent application of this protocol should require both.

### 7.3 Single universe and single trigger family

One universe (CRSP large-cap, *N* = 100), one region, one trigger construction. The
absorption-ratio trigger is one member of a large family; failure here does not
generalise to eigenspace-rotation, correlation-distance, or change-point triggers.

### 7.4 The holdout was never opened

The single pre-registered holdout touch was not used. A machine-checkable assertion
in the released test suite verifies that the durable audit log records zero
analysis touches of the test region. This is a consequence of the design, not an
omission: performance evaluation was *conditionally inaccessible*, and no adaptive
specification earned access.

### 7.5 Reproducibility incidents

Four defects were found and are documented in full, each by an erratum that leaves the frozen document unedited. A figure in the frozen
pre-registration cited a Phase 0.5 re-clustering count as though it were a trigger
count (corrected by erratum; no conclusion affected). Separately, a commit deleted
the equal-volatility allocator while the driver still declared it, rendering an
archived result temporarily unreproducible; the code was restored from history and
the archived value reproduced exactly. A third defect, found during pre-submission review, attached a correct confidence
interval to the wrong environment label in a completion record. A fourth withdrew every
statement of advisor approval and countersignature from the project's records: no
independent party reviewed or authorised any decision, and the earlier wording was
false (Section 7.6). All four are recorded in the released supplement as errata that leave the frozen
documents unedited. Regression tests were added for the two failure modes that admit
them, and guard against recurrence rather than detection.

The four share a structure worth naming. Each attached a correct quantity, or a correct
procedure, to the wrong context, and each was found by comparing a document against the artefact it described rather
than by any automated check. None was found by a test, and no test in the suite would
have detected them; the regressions added afterwards guard against recurrence.

---

### 7.6 No independent authorisation

This is a single-author study. The pre-registration was written, frozen, and applied by
the same person, and no independent party ruled on any specification choice or
amendment. The protocol's commitments are therefore evidenced by artefacts rather than
by review: specification documents are hashed and their hashes recorded in a released
manifest, the implementing code carries commit timestamps that postdate those hashes,
the selection rule is executed by a function rather than applied by hand, and the
calibration implementation cannot compute a performance quantity.

These devices constrain the specific failure they were built for -- selecting a
threshold after observing its effect on returns -- because the gate is structurally
incapable of producing a return quantity and the decision rule is executed in code.
They do not constrain judgement calls made between phases, where a self-imposed rule
can be reinterpreted by the person who wrote it. One such decision is reported in full
in Section 4.5, with both the original and revised outcomes, so that a reader may apply
either rule.

Independent authorisation would strengthen the protocol, and any subsequent application
of it should include a party who does not benefit from the outcome.

### 7.7 What a frozen specification does not guarantee

The post-gate specification for the diagnostics in Section 5.5 required eight
revisions. Seven were corrected before the affected result existed. The eighth was
not: a revision was frozen, hashed, implemented, and executed to completion before
its output revealed that the specified construction could produce neither a null
hypothesis nor a sampling distribution, and was therefore incapable of the
measurement it specified. The defect was caught because the output was absurd — a
rejection rate of exactly zero, and power curves that stepped from 0 to 1 between
adjacent grid points — not because anyone read the specification and found the
error. The specification was internally consistent throughout.

We report this because it bears on what the protocol in this paper can claim.
Freezing a specification constrains the choices a researcher can make after seeing
results. It does not verify that the specified procedure measures what it claims to
measure. Those are different guarantees, and the second is the one that failed here.

The same failure is visible in the gate itself. The cluster-informativeness
criterion was frozen, correctly executed, and sampled structural change at a horizon
the trigger does not operate on (Sections 5.5 and 7.2). Nothing in the
pre-registration process would have caught that, because the criterion was
internally coherent and its defect only became apparent when the trigger's algebra
was examined after the fact.

A protocol of this kind would be materially strengthened by requiring, before the
freeze, an explicit demonstration that each criterion can detect the effect it
targets: a power analysis at plausible effect sizes, and a check that the criterion
and the mechanism are measured on commensurate scales. Neither was required here. We
recommend both for any application of this protocol, and note that the requirement
is cheap relative to the cost of discovering the omission afterwards.

## 8. Conclusion

We proposed and applied a protocol in which an adaptive portfolio mechanism must
demonstrate structural informativeness against a frozen, performance-blind gate
before performance evaluation becomes available. Applied to an absorption-ratio
re-clustering trigger, the gate returned no admissible threshold, and the
investigation terminated without a portfolio being constructed and without the
holdout being opened.

The mechanism's timing is not random and is not reproduced by two regime-free
pipeline nulls, so it is detecting something. What it detects is related to hierarchical
restructuring when that restructuring is measured over the interval the trigger actually
spans, but not robustly: the relationship changes sign across the retained-component
count, and the gate that failed to find it had 11% to 33% power against the effect sizes
present.

We suggest the value of this result lies less in the specific mechanism than in the
demonstration that a pre-registered structural standard can be specified precisely
enough to be executed automatically, and can return a negative answer, and that the answer can then be diagnosed rather than defended. This paper was substantially revised in response to review, and the revisions are recorded; what was not revised is the frozen specification or the verdict it produced. The natural next question is not how to
make this trigger pass, but what |ΔAR| is actually tracking — an alignment question
best addressed by comparing absorption-ratio changes against eigenspace rotation,
correlation-matrix distance, and tree instability directly.

---

## Acknowledgments

This is a single-author study. No independent party reviewed, discussed, or authorised
the methodological decisions described here, and the protocol's commitments rest on
hashed specifications and commit timestamps rather than on external review (§7.6).

The author used a large language model to assist with drafting, literature review,
auditing the project's own records, and identifying methodological defects. The author
reviewed and verified all output and is responsible for the content.

Any remaining errors are the author's own.

## Data and Code Availability

All code, frozen specifications, decision records, errata, and result artefacts are
available at `github.com/opatel4/rac-hrp`. A reproducibility manifest pins SHA-256
hashes for 38 code modules, 10 result artefacts, 27 governing documents (including every superseded revision of each frozen specification), and the
underlying data files, together with the software environment. CRSP data are
licensed and cannot be redistributed; the manifest records checksums so a licensed
replicator can verify identity.

## References

Akioyamen, P., Tang, Y. Z., & Hussien, H. (2020). A hybrid learning approach to detecting regime switches in financial markets. *ACM International Conference on AI in Finance (ICAIF '20)*, New York. DOI 10.1145/3383455.3422521.

Ang, A., & Timmermann, A. (2012). Regime changes and financial markets. *Annual Review of Financial Economics*, 4, 313–337. DOI 10.1146/annurev-financial-110311-101808.

Avellaneda, M. (2019). Hierarchical PCA and applications to portfolio management. Courant Institute of Mathematical Sciences, NYU. arXiv:1910.02310.

Bongiorno, C., Manolakis, E., & Mantegna, R. N. (2026). End-to-end large portfolio optimization for variance minimization with neural networks through covariance cleaning. *The Journal of Financial Data Science*, 12. arXiv:2507.01918.

Deković, D., & Posedel Šimović, P. (2025). Hierarchical risk parity: Efficient implementation and real world analysis. *Future Generation Computer Systems*, 167, 107744. DOI 10.1016/j.future.2025.107744.

Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). Pseudo-mathematics and financial charlatanism: The effects of backtest overfitting on out-of-sample performance. *Notices of the American Mathematical Society*, 61(5), 458–471. DOI 10.1090/noti1105.

DeMiguel, V., Garlappi, L., & Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? *Review of Financial Studies*, 22(5), 1915–1953.

Hansen, P. R. (2005). A test for superior predictive ability. *Journal of Business and Economic Statistics*, 23(4), 365–380. DOI 10.1198/073500105000000063.

Harvey, C. R., & Liu, Y. (2015). Backtesting. *Journal of Portfolio Management*, 42(1), 13–28. DOI 10.3905/jpm.2015.42.1.013.

Harvey, C. R., Liu, Y., & Zhu, H. (2016). … and the cross-section of expected returns. *Review of Financial Studies*, 29(1), 5–68. DOI 10.1093/rfs/hhv059.

Hamilton, J. D. (1989). A new approach to the economic analysis of nonstationary time series and the business cycle. *Econometrica*, 57(2), 357–384.

Horvath, B., & Issa, Z. (2023). Non-parametric online market regime detection and regime clustering for multidimensional and path-dependent data structures. arXiv:2306.15835.

Kim, C.-J., & Nelson, C. R. (1998). Business cycle turning points, a new coincident index, and tests of duration dependence based on a dynamic factor model with regime switching. *Review of Economics and Statistics*, 80(2), 188–201. DOI 10.1162/003465398557447.

Kriuk, B., & Kriuk, F. (2026). ORCA — Online Regime Correlation Analyzer. *IEEE Symposium on Computational Intelligence for Financial Engineering and Economics (CIFEr)*, Tokyo. arXiv:2604.17251.

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

Pergher, K. G. R., Soldera, J., & Scharcanski, J. (2026). An orthogonal hierarchical risk parity allocation method for improved portfolio out-of-sample performance. *IEEE Access*, 14, 16885. DOI 10.1109/ACCESS.2026.3656702.

Politis, D. N., & White, H. (2004). Automatic block-length selection for the dependent bootstrap. *Econometric Reviews*, 23(1), 53–70.

Romano, J. P., & Wolf, M. (2005). Stepwise multiple testing as formalized data snooping. *Econometrica*, 73(4), 1237–1282. DOI 10.1111/j.1468-0262.2005.00615.x.

Roncalli, T. (2013). *Introduction to Risk Parity and Budgeting*. Chapman & Hall/CRC.

Sheppert, A. P. (2026). The GT-Score: A robust objective function for reducing overfitting in data-driven trading strategies. *Journal of Risk and Financial Management* (MDPI), published 12 January 2026.

Shumway, T. (1997). The delisting bias in CRSP data. *Journal of Finance*, 52(1), 327–340.

White, H. (2000). A reality check for data snooping. *Econometrica*, 68(5), 1097–1126. DOI 10.1111/1468-0262.00152.

Zhang, Y., Goel, D., Ahmad, H., & Szabo, C. (2025). RegimeFolio: A regime aware ML system for sectoral portfolio optimization in dynamic markets. arXiv:2510.14986.
