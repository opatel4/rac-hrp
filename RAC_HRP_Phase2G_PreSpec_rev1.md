# RAC-HRP — Phase 2G: Robustness Diagnostics

**Status:** rev.1 — FREEZE CANDIDATE. To be hashed and committed before any implementing code is
written.
**Author:** Om Patel
**Region:** Development region only (2003-01-08 to 2022-12-30). Test region remains structurally
locked.

**Single author.** No independent party has reviewed or authorised this specification. Its
prospective character rests on the freeze record in §7.

**Scope.** Three diagnostics, specified together because none is confirmatory, all share the same
standing constraints, and each is cheap enough that separate freeze records would be ceremony rather
than discipline. They are **2G-K** (sensitivity to the retained-component count), **2G-RANK** (a
continuous alternative to the binarised gate statistic), and **2G-HORIZON** (a robustness curve for
the horizon-matched result).

---

## 0. Standing constraints

**0.1 Non-gating.** Nothing in this memo can render any γ admissible, reopen the Phase 2A
calibration gate, or alter any frozen value. The Phase 2A verdict — NO ADMISSIBLE γ — stands
regardless of every outcome below.

**0.2 The holdout remains closed.** No diagnostic touches the test region. The durable audit log
must record zero analysis touches on completion.

**0.3 The frozen specification is not revised in light of any result here.** This is the binding
clause. If 2G-K shows the results are more favourable at some k ≠ 15, if 2G-RANK resolves an effect
the gate could not, or if 2G-HORIZON shows a larger effect at some h ≠ 5, **none of those becomes
the reported analysis**. The gate remains k = 15, difference-of-medians, one-rebalance horizon. The
confirmatory results are the frozen ones and these diagnostics describe their sensitivity, nothing
more.

**0.4 Reported in full regardless of outcome.** There is no result at which any of these is
withheld, relegated, or reframed. Results unfavourable to the paper's interpretation are reported
identically to favourable ones.

**0.5 Provenance.** All three questions arose after the Phase 2A verdict, two of them from external
review. The analyses are specified here before execution and this memo is hashed and committed
before any implementing code exists. The manuscript must state that ordering.

---

## 1. 2G-K — sensitivity to the retained-component count

### 1.1 Why

The absorption ratio is the share of variance in the leading k components. k = 15 was fixed at the
Marchenko–Pastur count of the first eligible rebalance and held for twenty years, a choice made to
avoid a look-ahead channel: a k that adapts to each window makes AR partly a function of how many
components happen to clear the noise threshold at that date.

The cost is that k determines the entire trigger series, and its appropriateness may drift as the
spectrum evolves across 2003–2022. The paper reports a four-estimator sweep on the static baselines,
which are secondary, and no sensitivity on k, which is primary. This diagnostic supplies it.

### 1.2 Procedure

For each k ∈ {10, 15, 20, 25}, run the frozen `structural_pass` with that k held for the whole run,
exactly as the gate does with k = 15, and evaluate the frozen cluster-informativeness statistic and
inference at every γ. k = 15 reproduces the frozen gate and serves as an internal check: if it does
not reproduce the frozen event counts and D_VI values exactly, the run aborts.

| Parameter | Value |
|---|---|
| k grid | {10, 15, 20, 25}, fixed here |
| γ candidates | {0.5, 1.0, 1.5, 2.0}, frozen grid and ordering |
| Inference | frozen: circular block bootstrap, 10,000 replicates, Politis–White, one-sided, Holm across the four γ within each k |
| Base seed | 131276444 (OS entropy) |
| Seed derivation | `seed(k, γ) = base + 1000·k_index + γ_index` |

### 1.3 Reporting

For each k: the realised absorption-ratio range, event counts at every γ, D_VI, raw and
Holm-adjusted p, and the selected block length. Reported as a table with k = 15 identified as the
frozen row.

**Abort condition.** If the k = 15 row does not reproduce event counts 149/111/81/58 and D_VI values
+0.033/+0.022/+0.080/+0.096, the implementation differs from the gate and the run aborts.

**No decision rule.** This diagnostic decides nothing. Stability across k is informative; instability
across k is equally informative and is reported identically.

---

## 2. 2G-RANK — a continuous alternative to the binarised statistic

### 2.1 Why

The frozen criterion thresholds the trigger and compares medians of VI across the two arms. That
discards the magnitude of |ΔAR|/σ̂ entirely: a rebalance just above the threshold and one far above
it are treated identically, as are all rebalances below.

The power diagnostic showed the consequence is worse than a loss of information. Under uniform
placement the frozen statistic is not merely insensitive to dispersed effects; its rejection rate
falls monotonically below nominal size as the planted effect grows, reaching 0.022 at δ = 0.30. The
statistic is biased against effects that do not arrive in runs.

A rank correlation between VI and the continuous trigger strength uses all 233 observations and
every gradation of the signal. Whether it resolves an effect the gate could not is the question.

### 2.2 Statistic

Spearman rank correlation ρ between VI_t and z_t = |ΔAR_t|/σ̂_t over the eligible rebalances.

Spearman rather than a regression slope: it requires no functional-form assumption about how VI
responds to trigger strength, and it is robust to the heavy tails documented in the standardised
change series. Spearman rather than Kendall: no strong reason, and the choice is fixed here so it is
not made later.

### 2.3 Inference

Circular block bootstrap, mechanically identical to the frozen procedure except that the resampled
pair is (VI_t, z_t) rather than (VI_t, I_t): 10,000 replicates, Politis–White automatic block length
selected on the VI series, blocks resampled jointly to preserve alignment, one-sided H₀: ρ ≤ 0,
replicates centred on the observed statistic.

| Parameter | Value |
|---|---|
| Bootstrap replicates | 10,000 |
| Base seed | 115262612 (OS entropy) |
| α | 0.05 |

**No multiplicity adjustment**, because there is no γ grid: the statistic has no threshold and there
is exactly one test. This makes the resulting p-value **not comparable** to the gate's Holm-adjusted
values, and it is reported as a separate quantity rather than as a corrected version of the gate
result.

### 2.4 Reporting

ρ, the raw one-sided p-value, the selected block length, and a scatter of VI_t against z_t. Reported
alongside the frozen D_VI values with an explicit statement that the two are different statistics
answering different questions, and that the frozen one is the confirmatory analysis.

**No decision rule.** A significant ρ does not render any γ admissible (§0.1) and does not replace
the frozen criterion (§0.3). It would establish that the trigger carries information the gate's
statistic was constructed not to see, which is a claim about the criterion.

---

## 3. 2G-HORIZON — robustness of the horizon-matched result

### 3.1 Why

The horizon-matched diagnostic reported an effect at h = 5, the horizon the frozen smoother forces.
That h was not searched: it follows algebraically from the five-rebalance moving average. But a
reader cannot distinguish "the pre-specified horizon happened to be the one that works" from "the
result is a knife-edge at one horizon" without seeing the curve.

### 3.2 Procedure

Compute D_VI with VI taken between the clustering at t and at t−h, for h ∈ {1, …, 8}, with the
frozen inference at each h and every γ. h = 1 reproduces the frozen gate; h = 5 reproduces the
horizon-matched result. Both serve as internal checks.

| Parameter | Value |
|---|---|
| h grid | {1, 2, 3, 4, 5, 6, 7, 8} |
| γ candidates | {0.5, 1.0, 1.5, 2.0}, frozen grid and ordering |
| Inference | frozen, Holm across the four γ within each h |
| Base seed | 560119915 (OS entropy) |
| Seed derivation | `seed(h, γ) = base + 1000·h + γ_index` |

**Abort conditions.** If h = 1 does not reproduce the frozen gate's D_VI values, or h = 5 does not
reproduce the horizon-matched result (+0.0662/+0.0600/+0.0814/+0.1038), the implementation differs
and the run aborts.

### 3.3 Reporting

D_VI and Holm-adjusted p at every (h, γ), as a curve. h = 5 remains the inferential claim; the sweep
is robustness and is labelled as such.

**The result is not re-selected.** If some h ≠ 5 shows a larger effect, that is reported and h = 5
remains the claim (§0.3). Reporting the maximum over h would be a search of exactly the kind this
project exists to avoid.

Judged against the procedure's measured size on the real dependence structure (0.0730), not its
nominal level, consistent with how the h = 5 result is reported.

---

## 4. What these cannot establish

None of the three is confirmatory. 2G-K describes sensitivity to a parameter, not the correct value
of it. 2G-RANK measures a different quantity than the gate did and cannot retrospectively change
what the gate measured. 2G-HORIZON describes the shape of a curve around a pre-specified point.

None bears on whether any threshold is admissible, and none touches performance, which remains
inaccessible.

---

## 5. Manuscript placement

Reported in a results subsection labelled post-gate and non-gating, alongside the existing
diagnostics. The discussion may rely on them; the gate section may not.

Where a diagnostic bears on a limitation already stated — 2G-RANK on the statistic's construction,
2G-K on the fixed component count — the limitation is updated to cite the measurement rather than
the conjecture.

---

## 6. Compute

Each diagnostic requires between one and four structural passes plus bootstrap sets. Prior
measurement puts a structural pass at roughly 1.5 minutes and the slow-regime control at 11 seconds
per replication, so all three together are expected to complete in well under an hour serially. No
replication-count reduction clause is included, because none is expected to be needed; if one proves
necessary it requires a new revision of this memo.

---

## 7. Freeze record

| Field | Value |
|---|---|
| SHA-256 of this file | recorded in `PHASE2G_FREEZE.txt` at the recording commit |
| Commit recording it | `__________________` |
| Implementing code present at that commit | none |

**Verification a replicator can perform.** Hash this file and compare. Check that the recording
commit contains no Phase 2G implementation, and that every subsequent commit touching Phase 2G code
postdates it.

**Amendments.** Any change requires a new revision, hashed and committed separately, with the reason
stated and the superseded revision preserved.
