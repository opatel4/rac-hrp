# RAC-HRP — Phase 2 Structural Calibration Gate: Result and Post-Gate Findings

*Revision 3 — archival record. Incorporates a subsequent review pass, the 111-vs-112
reconciliation (Erratum E1), the completed modal-gap null characterisation, and
a narrowing of the §4a interpretation. Phase 2 is CLOSED; the
methodology is not further refined within this experiment.*

**Status: PHASE 2 STOPS AT THE GATE — confirmed under review.** No
candidate γ satisfies every hard structural criterion. Per the frozen selection
rule, no "least bad" candidate is selected; the recorded conclusion is that the
current trigger specification is not admissible on the development region. This is
a reportable finding, not a pipeline failure.

The gate ran on the frozen specification (PHASE 2 PRE-REGISTRATION rev.5).
Performance was not computed and could not have influenced selection — the
orchestrator never calls the engine's return path and never touches the
risk-free series. Everything downstream of the gate (Null Gate v2, performance)
remains closed, because `cluster_informativeness` failed independently for every
candidate.

---

## 1. What ran

- **Universe / span:** point-in-time CRSP large-cap, N = 100; development region
  2003-01-08 → 2022-12-30 (5,031 days, 4 folds). Identical span and fold geometry
  to Phase 0.5 / Phase 1, so the calibration is comparable to them.
- **D4 covariance window:** W = 504 (median realized N = 100), applied *before*
  fold construction.
- **Structural pass:** 240 rebalances, 233 eligible; k frozen at 15 at the first
  eligible rebalance (fixed-per-run, no look-ahead).
- **Inference (frozen):** placebo seed 20260817, B = 100,000, 95th percentile,
  q ∈ 2..12; circular block bootstrap B = 10,000, Politis-White block length,
  Holm α = 0.05. Politis-White block length = 19 for every candidate; zero
  degenerate bootstrap replicates for every candidate.

## 2. Result (frozen)

| γ | events | firing | min ev/fold | cv_gap | modal_gap_share | J* | J_thr | D_VI | p_Holm | PASSES_ALL |
|-----|-------:|-------:|-----:|------:|------:|------:|------:|------:|------:|:--:|
| 0.5 | 149 | 0.639 | 35 | 1.116 | 0.824 | 0.400 | 0.446 | +0.033 | 0.556 | No |
| 1.0 | 111 | 0.476 | 26 | 1.458 | 0.791 | 0.326 | 0.382 | +0.022 | 0.556 | No |
| 1.5 |  81 | 0.348 | 18 | 1.676 | 0.763 | 0.263 | 0.320 | +0.080 | 0.254 | No |
| 2.0 |  58 | 0.249 | 11 | 1.823 | 0.791 | 0.208 | 0.259 | +0.096 | 0.221 | No |

(Turnover is a reported diagnostic only and gates nothing; the 1.5× multiplier
was asserted, not derived.)

**Audit note (Erratum E1).** The frozen pre-registration §1 records "112/233 =
48.1%" as the γ = 1.0 firing rate. That figure is a Phase 0.5 `refit`=True count
(112 of 240 rebalances), not a Phase 2 trigger count. The correct γ = 1.0 figure
is 111/233 = 47.6% (table above). This is a documentation provenance error in the
frozen document, corrected by attached Erratum E1 and reconciled in
`RAC_HRP_Phase2_Reconciliation_111_vs_112.md`; it changes no conclusion (47.6% >
40% ceiling; γ = 1.0 still fails informativeness).

## 3. Which criteria bind, and which do not

Checked against the frozen thresholds (firing ∈ [0.05, 0.40]; ≥ 3 events/fold;
cv_gap ≥ 0.50 **and** modal_gap_share ≤ 0.50; J* ≤ J_threshold; D_VI > 0 **and**
Holm-p < 0.05):

- **`separation` passes for every candidate.** No candidate exhibits
  periodic-schedule alignment exceeding the frozen placebo threshold: J* (maximised
  over q ∈ 2..12 and phase) ≤ J_threshold throughout. This is not a broader claim
  that no calendar structure exists.
- **`event_sufficiency` passes for every candidate.** 11–35 events per fold, all
  ≥ 3.
- **`informativeness` fails only at γ = 0.5 and γ = 1.0**, where firing (0.64,
  0.48) exceeds the 0.40 ceiling. γ = 1.5 and γ = 2.0 sit inside the band.
- **`timing_variation` fails for every candidate — on `modal_gap_share`, not
  cv_gap.** Every cv_gap clears its 0.50 floor (1.12–1.82); the failure is that
  modal_gap_share (0.76–0.82) exceeds the 0.50 ceiling. See §4a — the criterion is
  not vacuous at these densities; the source of the burstiness remains open (§4d).
- **`cluster_informativeness` fails for every candidate.** D_VI is positive
  throughout and increases with γ (+0.033 → +0.096); the Holm-adjusted p never
  clears 0.05 (best 0.221 at γ = 2.0).

Even the strongest candidate (γ = 2.0, which passes informativeness and
separation) is blocked by two criteria: `timing_variation` and
`cluster_informativeness`.

## 4. Two failure modes, both now characterised

The two failures are different in kind. The post-gate diagnostic below narrows
the timing question without fully closing it (§4a, §4d).

### 4a. Timing variation — the trigger is bursty relative to random placement
*(established against a placement null only; the SOURCE of the burstiness is
not established — see 4d)*

A pre-specified null characterisation was run (pre-specified, post-gate,
non-rescuing): for each candidate's event count over the E = 233 eligible
rebalances, 10,000 random equal-size trigger placements were scored with the
**frozen** `timing_variation`, forming the null distribution of modal_gap_share.
Seed 20260821; the statistic's implementation was hand-verified against a manual
gap computation (`match: True`).

| γ | n | observed modal share | random null (2.5–97.5%) | feasibility floor | verdict |
|-----|---:|------:|:---:|------:|:--|
| 0.5 | 149 | 0.824 | 0.595 – 0.689 | 0.432 | more bursty than random |
| 1.0 | 111 | 0.791 | 0.409 – 0.545 | 0.000 | more bursty than random |
| 1.5 |  81 | 0.763 | 0.275 – 0.438 | 0.000 | more bursty than random |
| 2.0 |  58 | 0.790 | 0.193 – 0.351 | 0.000 | more bursty than random |

At every γ the observed modal share sits far above the random null band, and the
gap widens as the trigger thins (null mean falls 0.64 → 0.26 while observed holds
~0.76–0.82). The 0.50 ceiling is combinatorially attainable at every event count
(the packing floor, max(0, 2n−E−1)/(n−1), is 0.432 at the densest candidate and
0 elsewhere), so the failure cannot be attributed to the 0.50 ceiling being
combinatorially unreachable at the observed event densities. (This does not
establish that 0.50 was a well-designed threshold in an economic or statistical
sense — only that it was attainable.)

**What this establishes.** Trigger events are substantially more temporally
clustered than uniformly random event placements of the same count. The 0.50
criterion is attainable at every observed event density, so its failure cannot be
attributed solely to combinatorial event density. `modal_gap_share` is therefore
not a vacuous criterion at these densities.

**What this does NOT establish.** It does not show that the burstiness reflects
genuine market regime behaviour, and it does not retire the earlier
structureless-mock observation. A random-placement null is not equivalent to
structureless *returns* passed through the full pipeline: overlapping 504-day
covariance windows, five-rebalance AR smoothing, first differencing, the rolling
12-rebalance σ denominator, and persistence in estimated eigenvalue spectra can
each induce temporal dependence in the trigger series with no regime structure in
the underlying data. The burstiness may therefore originate in the trigger
construction itself. The diagnostic run here cannot separate those two sources.

### 4b. Cluster informativeness — positive in direction, statistically unresolved

D_VI is positive at every γ and grows with selectivity (+0.033 → +0.096), the
direction the hypothesis predicts, but no Holm-adjusted p clears 0.05 (best 0.221).
The defensible statement is **positive in direction, statistically unresolved** —
a positive point estimate does not establish that the effect is real. On the
development region, triggered re-clusterings are not shown to correspond to
statistically distinguishable changes in clustering structure under the
pre-registered inference procedure.

### 4c. The two findings say different true things

The trigger clumps in time relative to random placement (4a), but its firings do
not map onto distinguishable clustering changes (4b). Neither rescues the other.
Both are honest negatives, and both were produced performance-blind — which is
more informative than discovering the same pattern after inspecting Sharpe ratios.

### 4d. Open mechanism question (post-mortem, NOT part of Phase 2)

Whether the observed burstiness is regime-driven or an artefact of the trigger
construction is unresolved and cannot be settled by a placement null. Settling it
requires a **pipeline-level structureless null**: generate returns with no
designed regime structure, push them through the identical frozen
returns → Σ̂ → AR → AR^s → ΔAR → trigger machinery, and examine the resulting
distribution of f_γ, cv_gap, modal share, and D_VI. If the pipeline generates
bursts on structureless input, that diagnoses a structural weakness of the
trigger; if not, the real-data burstiness becomes more plausibly market-driven.

This would be a **post-gate mechanism diagnostic**, not part of the Phase 2
selection procedure, and it cannot alter the Phase 2 outcome.

## 5. What is deliberately NOT done

`MODAL_GAP_SHARE_MAX` and the γ candidate set are **not** revisited. The results
are known, so any change to a threshold or the candidate grid would be
result-contingent — the failure mode the pre-registration exists to prevent. The
frozen record stands. Erratum E1 corrects a documentation figure only; it is not
a methodological amendment.

## 6. Interpretation retained for later (not a finding)

As γ increases, firing falls (0.64 → 0.25) while D_VI rises (+0.033 → +0.096) and
Holm p improves (0.556 → 0.221, still far from significance). This is consistent
with a mechanism in which large |ΔAR| events preferentially identify larger
hierarchical-structure changes, but with too few independent structural
transitions — or too much temporal dependence — for the development sample to
establish it statistically. This is a hypothesis generated by the failed gate,
not a confirmed result, and is recorded for later interpretation only.

---

*Attached / hashed artefacts:*
`outputs/phase2/calibration_manifest.json`, `outputs/phase2/calibration_table.csv`
(frozen gate record); `outputs/phase2_diagnostics/modal_gap_null.json` (diagnostic
record); `RAC_HRP_Phase2_Reconciliation_111_vs_112.md`;
`RAC_HRP_Phase2_rev5_ERRATUM_E1.md`. Manifests embed the code hashes of the
producing modules; those should be checked against the committing revision.
