# RAC-HRP — Phase 2E Post-Gate Diagnostics: Pre-Specification

**Status:** rev.8 — FROZEN. Hashed and committed before any Phase 2E code was written.
**Author:** Om Patel
**Region:** Development region only (2003-01-08 to 2022-12-30). Test region remains structurally
locked.

**Revision history.** rev.1 initial draft. rev.2 restructured the power experiment as a target-γ
sparse-alternative design so the frozen Holm family is reproduced; made the seed scheme
replication-level; made the placement comparison paired; reworded the horizon-diagnostic
non-rejection outcome so it does not read as support for the topology account; softened the
exchangeability claim; made the δ = 0 comparison rule exact; specified behaviour when no grid point
reaches 80% power. rev.3 renamed the two diagnostics to avoid collision with Phase 2B; replaced the
sign-off block with a self-binding freeze record; strengthened the provenance statement. rev.3 was
committed at `fc4fd84` with the two base seeds still unfilled, which left the specification's most
consequential frozen parameters unfrozen; rev.4 fills them and supersedes it. rev.3 is preserved
unaltered as the historical record. rev.5 corrects §3.2, which contracted the eligible set to 228 on
the stated ground that VI-at-t-minus-5 requires a clustering five rebalances earlier. That ground is
mistaken: rebalances 3 through 7 exist and carry labels, they are merely ineligible to fire. More
decisively, the frozen gate itself computes VI against the previous rebalance and therefore already
draws on labels from ineligible earlier dates — the first eligible date, rebalance 8, is compared
against rebalance 7. Contracting the set would make the diagnostic inconsistent with the procedure it
is designed to mirror. The eligible set is 233, matching the gate. rev.4 is preserved unaltered.
This amendment was made before any Phase 2E code was written and is the only substantive change.
rev.6 corrects §2.2 and §2.5. rev.5 specified drawing synthetic VI paths from the empirical-size
generator, which draws i.i.d. standard-normal VI and i.i.d. Bernoulli firing at 48%. That makes the
specified comparison undefined: the real series is strongly dependent (block length 13), so power
measured on an i.i.d. path is an upper bound under strictly easier conditions; and condition R plants
at the observed trigger sets "preserving the observed burst structure", which an i.i.d. firing series
does not have and whose event counts would not match the frozen 149/111/81/58. rev.6 uses the
observed VI series, median-centred, as the base path, preserving both the dependence and the burst
structure so the resulting minimum detectable effect applies to the design as it ran. A
dependence-matched synthetic generator was considered and rejected because each calibration choice
would be a free parameter selected after the problem was known. The δ = 0 cell is correspondingly
redefined: it no longer tests against the published i.i.d. size figure, which is not comparable, but
reports empirical size on the real dependence structure with a single gross-malfunction abort at
0.20. Discovered while implementing 2E-POWER; no 2E-POWER result existed when this amendment was
made. 2E-HORIZON had already been run and reported at this point (Outcome H, committed 28d5f92);
nothing in that result bears on the choice made here, which concerns only the power benchmark.
rev.5 is preserved unaltered. rev.7 corrects §2.3. rev.6 claimed the R-versus-U difference
"isolates the cost of the target trigger's burstiness". It cannot: the frozen inference selects its
block length from the series it is handed, that series is the planted path, and planting along the
burst structure raises apparent persistence under R but not under U. The difference therefore
reflects the combined effect of clustered placement on both the statistic and the selected block
length. §2.3 now says so, reports realised block lengths per cell, and records that holding the block
length fixed was rejected because it would require overriding a parameter the frozen inference
computes internally. rev.7 also removes a stale reference to a "synthetic VI realisation" left in
§2.3 by the rev.6 base-path change. Discovered while implementing 2E-POWER, after reading the
bootstrap internals; no 2E-POWER result existed at this amendment. rev.6 is preserved unaltered.

rev.8 replaces the 2E-POWER base-path construction. rev.7 specified median-centring the observed VI
series, which cannot null the statistic — subtracting a scalar leaves the difference between two
subgroup medians unchanged — and which, being a fixed path, supplied no sampling variation across
replications. Executed, it produced a δ = 0 rejection rate of exactly 0.0000 in 2,000 replications
and power curves that stepped from 0.000 to 1.000 between adjacent grid points. The output was
absurd on its face, which is how the defect was found; it was not caught by review of the
specification.

The replacement draws each replication's path by circular block resampling the observed series at
its selected block length and pairs it with the frozen masks. This nulls the statistic by
construction, preserves serial dependence, and restores replication-level variation. It was verified
on synthetic data before being frozen: size near nominal across autocorrelation from 0.47 to 0.87,
power rising smoothly rather than stepping, and non-zero variation in the realised statistic. The
verification harness is committed as `scripts/explore_power_construction.py`, marked exploratory.

§2.3 is reframed in consequence. Exploratory testing showed the statistic barely responds to
dispersed effects at any magnitude, so Power_R − Power_U measures the criterion's blindness to
non-clustered effects rather than a cost of burstiness. §2.5 becomes a genuine size check with a
pass band, now that the base path is actually null. The rev.7 run is preserved as
`power_result_INVALID_rev7.json` and is not a result.

**Note on the revision count.** This specification required five substantive corrections: unfilled
seeds (rev.4), an eligible-set contraction inconsistent with the gate (rev.5), a base-path generator
whose properties made the specified comparison undefined (rev.6), an overclaim about what the
placement comparison isolates (rev.7), and a base-path construction that could produce neither a
null nor a sampling distribution (rev.8).

Four were caught before the affected result existed. The fifth was not: rev.7 was frozen, coded, and
run to completion — 130,000 replications over 31 minutes — before its output revealed that the
construction was incapable of the measurement it specified. No reading of the specification had
caught it, and the specification was internally consistent.

The manuscript reports this count and this distinction. Prospective specification constrains the
choices a researcher can make after seeing results; it does not verify that the specified procedure
measures what it claims to measure. Those are different guarantees, and conflating them would
overstate what a freeze buys. What caught the rev.7 defect was an output that was absurd rather than
merely wrong — a δ = 0 rejection rate of exactly zero and power curves that were step functions. A
subtler error of the same kind would have survived.

**Naming.** The two diagnostics are **2E-POWER** and **2E-HORIZON**. They are not related to Phase
2B, which is reserved for a second-generation trigger and is not pursued here.

---

## 0. Standing constraints

**0.1 The Phase 2A gate verdict is final.** No result in this memo can render any γ admissible,
reopen the calibration gate, or alter any frozen value. The gate returned NO ADMISSIBLE γ and that
verdict stands regardless of what these diagnostics show.

**0.2 The holdout remains closed.** Neither diagnostic touches the test region. The durable audit
log must record zero analysis touches of the test region on completion, verified by the existing
assertion in the released test suite.

**0.3 Both diagnostics are reported in full regardless of outcome.** There is no result at which
either is withheld, relegated to a supplement, or reframed.

**0.4 Provenance.** The horizon mismatch was noticed after the Phase 2A gate failure, while auditing
the frozen specification. The algebraic identity itself is deterministic and result-independent, but
the decision to investigate its implications is post-gate. The analyses are specified here before
execution and this memo is hashed and committed before any implementing code exists, but the
manuscript must state that ordering and must not describe them as pre-registered alongside the gate.

**0.5 Single author.** No independent party has reviewed or authorised this specification. Its
prospective character rests on the freeze record in §6: the memo's hash, the commit that records it,
and the absence of implementing code at that commit. This is weaker than independent review on
judgement calls and stronger on questions of ordering, which a hash and a commit timestamp can
establish and an assertion cannot.

---

## 1. Motivation

Once the rolling window is fully populated, the frozen trigger's smoothing and differencing steps
telescope:

```
ΔAR^s_t = (1/5)(AR_t − AR_{t−5})
```

The trigger statistic is a five-rebalance change, approximately 105 trading days at monthly
rebalancing. The cluster-informativeness criterion measures variation of information between
clusterings at consecutive rebalances — a one-rebalance change. The two quantities are measured at
different horizons. The gate was frozen without imposing horizon alignment between them, which is a
defect in the gate's construction rather than in its execution.

Two accounts of the gate outcome remain open:

- **Horizon account.** |ΔAR^s| tracks structural change at a five-rebalance horizon; the criterion
  samples that change at one rebalance.
- **Topology account.** AR responds to changes in the magnitude of covariance concentration that
  leave the dendrogram topology substantially intact.

Separately, the gate's power was never assessed. §5.4 of the manuscript establishes empirical size
(≈6.6% against nominal 5%) but not power. Because trigger events arrive in tight bursts, the number
of independent episodes is materially smaller than the nominal event count, and a failure to reject
may reflect an underpowered design rather than an absent effect.

2E-POWER addresses the second question. 2E-HORIZON addresses the first. Neither can be interpreted
without the other, and the two are reported together.

---

## 2. 2E-POWER — planted-effect power curve

### 2.1 Purpose

To establish the smallest true D_VI the frozen inference procedure could have detected at 80% power
at each γ, and to quantify how much power is lost to the burstiness of the trigger's event placement
rather than to sample size.

### 2.2 Design: target-γ sparse alternative

The frozen Phase 2A test applies Holm jointly across the four candidates. A power experiment that
treats each γ as an isolated test does not reproduce the decision the gate actually made, because
the adjusted p-value for any candidate depends on the other three p-values in its family.

For a **target** candidate g ∈ {0.5, 1.0, 1.5, 2.0}, effect size δ, placement condition, and
replication index r:

1. Draw this replication's base path by circular block resampling the observed VI series at the
   233 eligible rebalances, using the Politis–White block length selected on that series. Pair the
   resampled path with the **frozen** trigger masks.

   Resampling breaks the association between the path and the masks, so the base path is null by
   construction — no subgroup carries an effect. Blocks preserve serial dependence, which matters:
   the observed series has lag-1 autocorrelation near 0.47 and a selected block length of 13, and a
   path without that dependence would make every power figure an optimistic upper bound. A fresh
   draw per replication supplies the sampling variation a power curve requires.
2. Plant δ **only** at the positions designated for the target candidate g, under the placement
   condition below. The other three candidates carry no effect on this path, which now follows
   automatically from the base path being null.
3. Compute all four candidate test statistics and their raw p-values from this single path, exactly
   as the gate does.
4. Apply Holm step-down across those four p-values at family-wise α = 0.05, exactly as the gate does.
5. Record whether the **target** candidate g rejects.

Power at (g, δ, condition) is the rejection rate of the target across replications.

This is a sparse-alternative design: one true effect within a family of four dependent tests, which
is the configuration the gate would have faced had the effect been real at a single threshold. It is
a choice about how detectability is defined, not a claim about nature, and §5 records that.

### 2.3 Placement conditions, paired

- **Condition R (realised placement).** δ is planted at the actual trigger index set T_g from the
  frozen gate run, preserving the observed burst structure.
- **Condition U (uniform placement).** δ is planted at |T_g| positions drawn without replacement
  uniformly across the eligible set, using the placement machinery built for the modal-gap null
  characterisation.

Only the target candidate's event placement changes between R and U; the other three candidates'
null constructions are held fixed, so both conditions face the same multiplicity environment. R and
U share the base path and the bootstrap seed at matched (g, δ, r), making the comparison paired.

**What the difference measures.** Not a cost of burstiness. Exploratory testing of the rev.8
construction found that under condition U the realised statistic stays near zero at every δ,
including δ = 0.30 on a series whose standard deviation is 0.228. Planting a large effect at
uniformly scattered positions produces almost no shift in the difference of medians, because the
fired and non-fired subsamples are then drawn from the same part of the path.

Power_R − Power_U therefore measures something more basic than a cost: **the frozen statistic
responds only to effects that arrive in runs, and is close to blind to effects of the same magnitude
that are dispersed.** That is a property of the cluster-informativeness criterion itself, not of the
trigger, and it is reported as such.

A secondary contribution runs alongside it. The frozen inference selects its block length from the
planted path, so clustered planting raises apparent persistence under R and not under U, and the
selected length can differ between conditions. Both effects are consequences of clustered placement
and neither is separated from the other; the difference is not a decomposition and is not reported
as one. Realised block lengths are reported for every cell.

Realised block lengths are reported for every cell so that any divergence between conditions is
visible rather than inferred. Holding the block length fixed across cells was considered and
rejected: it would require overriding a parameter the frozen inference computes internally, which
the specification forbids.

### 2.4 Frozen parameters and seed scheme

| Parameter | Value |
|---|---|
| Replications per cell | 2,000 |
| Bootstrap replicates B | 2,000 |
| δ grid | {0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30}, plus δ = 0 as a single shared cell (§2.5) |
| Target candidates g | {0.5, 1.0, 1.5, 2.0} (frozen grid, ordering preserved) |
| Placement conditions | R, U |
| α | 0.05, family-wise, Holm across the four candidates within each replication |
| Base seed | 292828877 (OS entropy) |

Seeds are derived at replication level and distinguish all four coordinates:

```
seed(g, δ, condition, r) = base
                         + 10_000_000 · g_index
                         +    100_000 · δ_index
                         +     10_000 · condition_index
                         +              r
```

with `g_index` and `δ_index` from the frozen orderings above and `condition_index` ∈ {0 = R, 1 = U}.
The base path is the observed VI series and is identical across all cells; `seed(g, δ, R, r)`
governs the bootstrap draw and `seed(g, δ, U, r)` additionally governs the uniform placement draw.
R and U at matched (g, δ, r) therefore share a bootstrap seed, making the comparison paired. This is what
makes the pairing exact.

The δ grid brackets the observed point estimates (+0.033 to +0.096) on both sides. It is fixed here
and is not extended after inspecting results (§2.7).

### 2.5 The δ = 0 integrity check

At δ = 0 no effect is planted anywhere, so the target index and placement condition are immaterial.
δ = 0 is run **once**, at 2,000 replications and B = 2,000, and is a genuine size check: under the
rev.8 construction the base path is null, so the rejection rate should approximate the nominal 0.05.

**It is not compared against the published i.i.d. figure.** That figure (0.0660, MC SE 0.0056) was
measured on i.i.d. normal VI with i.i.d. Bernoulli firing. The base path here preserves the observed
dependence, so the two measure different things. The δ = 0 cell is reported as the empirical size of
the frozen procedure on the real dependence structure, a quantity the project has not previously
measured.

Exploratory testing on synthetic AR(1) paths with autocorrelation from 0.47 to 0.87 returned sizes
of 0.047, 0.047 and 0.033, with the selected block length rising from 4 to 13 as dependence rose.
The procedure is therefore approximately calibrated across the range that brackets the real series,
drifting mildly conservative at high persistence rather than anti-conservative.

**What is reported.** The δ = 0 rejection rate with its Monte Carlo standard error, stated as the
empirical size of the frozen inference procedure on the observed dependence structure, alongside the
previously published i.i.d. figure with an explicit note that the two measure different things.

**Pass band.** The cell passes if the rate falls in [0.02, 0.10]. Outside that band the procedure is
not adequately calibrated on this dependence structure and a power curve built on it would be
uninterpretable: the run aborts and the fact is reported. The band is set here, before the cell is
computed, and is wide enough to accommodate the conservative drift observed in exploratory testing
while excluding the failure modes seen under rev.7, where the rate was exactly 0.000.

### 2.6 Prohibited

Computing power at the observed D_VI. Observed power is a monotone transform of the observed p-value
and carries no information beyond it. The reported quantity is the detectable effect size of the
design, not the power against the estimate the design produced.

### 2.7 Reporting, including the failure case

Reported regardless of outcome:

- Power curves, one panel per target candidate, both placement conditions, power against δ, with
  Monte Carlo standard errors on every rejection rate.
- **MDE₈₀**, the minimum detectable effect at 80% power, reported for each (g, condition) as the
  interval between bracketing grid points, not as an interpolated point estimate.
- If no grid point reaches 80% power, report **MDE₈₀ > 0.30**. The grid is not extended.
- If the empirical power curve is visibly non-monotone in δ, report the raw curve and the bracketing
  values; do not interpolate through it and do not smooth it.
- The number of distinct trigger bursts at each γ, defined as one plus the count of inter-event gaps
  exceeding one rebalance, alongside the nominal event count.
- Power_R − Power_U at every (g, δ), with a paired Monte Carlo standard error, and
  the realised block length for every cell.
- An explicit statement that the reported MDE is conditional on the observed dependence
  realisation of the VI series. The base path is the sample the gate actually tested, not a
  draw from a fitted process, so the quantity answers what this design could have detected on
  this data rather than what it would detect on average across resamples of a population.

### 2.8 Timing probe and the one permitted amendment

The target-γ design computes four candidate tests per replication rather than one, so cost is
roughly four times a naive design. Before the full run, a probe measures wall-clock time for one
(g, δ, condition) cell at 50 replications.

If the extrapolated full run exceeds 12 hours on the target hardware, the **replication count** is
reduced to 1,000 uniformly across every cell. This is the only parameter that may be adjusted for
runtime, the reduction applies to every cell or to none, and it is recorded as a dated amendment
appended to this memo before the full run begins, stating the measured timing and the resulting
count. No other parameter is adjusted for any reason.

---

## 3. 2E-HORIZON — horizon-matched cluster informativeness

### 3.1 Statistic

Let VI⁽⁵⁾_t denote the variation of information between the hierarchical clustering at rebalance t
and the clustering at rebalance t−5, computed on the intersection of the universes at those two
dates, using the frozen `variation_of_information` implementation and the frozen tree-cut rule
without modification. Then

```
D_VI⁽⁵⁾ = median(VI⁽⁵⁾_t | I_t = 1) − median(VI⁽⁵⁾_t | I_t = 0)
```

As in the gate, the counterfactual clustering is recomputed at every eligible rebalance including
those a live strategy would skip.

Both arms of the contrast are taken at the same horizon. This removes the explicit horizon mismatch
between the trigger statistic and the criterion, which is the purpose of the diagnostic. It does not
establish that triggered and non-triggered dates are otherwise exchangeable, and no such claim is
made.

### 3.2 Eligible set

VI⁽⁵⁾_t requires a clustering at rebalance t−5. Rebalances 3 through 7 exist and carry labels; they
are ineligible to fire, but eligibility is a property of the trigger's scale estimate, not of the
clustering. The frozen gate already relies on this: it computes VI against the previous rebalance,
so its first eligible date is compared against rebalance 7, which is itself ineligible.

The eligible set is therefore **|E⁵| = 233**, identical to the gate's. The trigger index sets are the
frozen sets unchanged, and the event counts are 149 / 111 / 81 / 58. Any departure from these counts
indicates an implementation error and aborts the run.

### 3.3 Inference

Identical in form to the frozen gate procedure: circular block bootstrap, 10,000 replicates,
Politis–White automatic block length, (VI⁽⁵⁾_t, I_t) resampled jointly in blocks, one-sided
H₀: D_VI⁽⁵⁾ ≤ 0, replicates centred on the observed statistic, Holm step-down across the four γ at
family-wise α = 0.05.

Seeds do not reuse the gate's. A separate base seed is fixed here, with the same derivation rule as
the frozen `bootstrap_seed_for`, and the γ ordering is preserved.

| Parameter | Value |
|---|---|
| Bootstrap replicates | 10,000 |
| Horizon | 5 rebalances |
| Base seed | 100756712 (OS entropy) |
| α | 0.05, family-wise, Holm across the four γ |

### 3.4 Decision rule, fixed in advance

The verdict rests on Holm-adjusted p-values. Magnitudes are reported as descriptive context.

- **Outcome H — the effect is resolved at the matched horizon.** At least one γ attains
  Holm-adjusted p < 0.05 with D_VI⁽⁵⁾ > 0. Reported as: the clustering-change effect becomes
  statistically resolved when measured at a horizon matched to the trigger statistic, and was not
  resolved at the gate's horizon. This confers no admissibility (§0.1).
- **Outcome T — horizon alignment does not recover statistically detectable cluster
  informativeness.** No γ attains Holm-adjusted p < 0.05. Reported as: matching the measurement
  horizon does not yield statistical evidence of greater cluster restructuring at triggered
  rebalances. The topology account remains compatible with this result but is **not identified**,
  because non-rejection may equally reflect limited power. 2E-POWER supplies the power context and
  the two results are reported together.
- **Outcome U — unresolved.** Any result not falling cleanly into H or T, including sign reversals
  or non-monotonicity in γ that the above does not anticipate, is reported as unresolved with the
  anomaly stated and no interpretation asserted.

Intermediate horizons {2, 3, 4} are **not** run. Horizon 5 follows mechanically from the frozen
five-rebalance smoother; running a sweep and reporting the best would convert the diagnostic into a
search of exactly the kind this project exists to avoid.

### 3.5 Reporting

Point estimates, raw and Holm-adjusted p-values, and event counts for all four γ, presented
alongside the frozen gate values for direct comparison, in a table labelled post-gate and
non-gating. Median VI⁽⁵⁾ levels and dispersion are reported so the effect size is interpretable on
its own scale — a gap in the manuscript's presentation of the original D_VI that is corrected in the
same revision.

---

## 4. Manuscript placement

Both diagnostics are reported in a results subsection headed to make their status visible in the
table of contents, e.g. "Post-gate diagnostics (pre-specified, non-gating)." The discussion section
may rely on them; the gate section may not. Figure and table captions repeat the non-gating status.

The limitations section already records that the gate was frozen without imposing horizon alignment
(§7.2) and that no independent party authorised any decision (§7.6).

---

## 5. What this cannot establish

2E-POWER bounds the design's sensitivity; it does not establish that any true effect exists, and the
sparse-alternative configuration is a choice about how detectability is defined rather than a claim
about nature.

2E-HORIZON distinguishes two accounts of a null result and, under Outcome T, identifies neither.
Neither outcome constitutes evidence that the trigger is useful for portfolio construction, which is
a performance question that remains inaccessible.

Neither diagnostic addresses the single-universe and single-trigger-family limitations.

---

## 6. Freeze record

This memo is frozen by hashing and committing it before any implementing code exists. There is no
countersignature; §0.5 states what replaces it.

| Field | Value |
|---|---|
| SHA-256 of this file | `__________________` (computed after seeds are filled) |
| Commit recording it | `__________________` |
| Commit date | `__________________` |
| Implementing code present at that commit | none |

**Verification a replicator can perform.** Hash this file and compare against the value above.
Check that the recording commit contains no Phase 2E implementation. Check that every subsequent
commit touching Phase 2E code postdates it.

**Amendments.** Only the §2.8 replication-count reduction is permitted, and only before the full run
begins. Any other change requires a new revision of this memo, hashed and committed separately, with
the reason stated and the superseded revision preserved.
