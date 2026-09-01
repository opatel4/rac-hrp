# Phase 2B — Spec

Re-tests the existing absorption-ratio trigger against a criterion that can
actually detect the effect. Mechanism unchanged: Eqs. (1)–(5) carried over
verbatim, `W = 504`, `k = 15`, grid `γ ∈ {0.5, 1.0, 1.5, 2.0}`. Only the
measurement changes.

---

## 1. Decisions

**Statistic.** One-sided Spearman `ρ_s` between `s_t = |ΔAR_t| / σ̂_t` and
`VI(t, t−5)`. `H₀ : ρ_s ≤ 0`, `α = 0.05`. Pass on `p < 0.05` and `ρ_s > 0`.

Ranks rather than OLS because `σ̂` is a twelve-observation estimate that is
often too small, giving `s_t` a heavy right tail; under OLS that tail becomes
leverage and the slope is set by a handful of dates where the denominator
collapsed.

**Inference.** Circular block bootstrap, 10,000 replicates, Politis–White
automatic block length, pair `(s_t, VI_t)` resampled jointly in blocks.
Replicates centred on the observed statistic. `p = (1 + #exceed)/(B_kept + 1)`.
One test, so no multiplicity correction. **Seed base 20260901** — distinct from
all Phase 2A seeds, so 2B is independent of the result it re-examines.

**Horizon `h = 5`, fixed.** Eq. (5): `ΔAR^s_t = (1/5)(AR_t − AR_{t−5})` is an
exact identity. No sweep — that would reintroduce as a free parameter something
the algebra determines. `h = 1` computed and reported, non-gating.

**Retained criteria, unchanged from 2A:** `f_γ ∈ [0.05, 0.40]`; ≥ 3 events in
all four development folds; `J*_γ ≤` placebo 95th percentile at the candidate's
own event count.

**Dropped: timing variation** (CV ≥ 0.50, modal gap ≤ 0.50). The trigger's
construction predicts run-clustering — 95.8% overlap between consecutive 504-day
windows, four of five shared terms in consecutive `ΔAR^s`, drift producing
adjacent firings — and Phase 2D confirmed the burstiness is not a pipeline
artifact. The criterion penalises what the mechanism is built to do. Its stated
purpose, catching disguised calendar rules, is served correctly by `J*_γ`.

**Dropped: `D_VI` difference of medians.** MDE₈₀ was (0.15, 0.20], two to nine
times any effect present. Under uniform placement power never reached 0.08 and
fell to 0.022 at δ = 0.30, below nominal size. Per the manuscript, the bias
belongs to the criterion and any mechanism evaluated against it inherits it.

**Threshold selection, if the test passes.** Largest γ passing the retained
criteria. A regime trigger should fire on structural breaks, not routinely;
fewer events also means less turnover into Phase 3.

> Disclosure: I checked which γ this selects before locking the rule. From
> Table 6 event counts and `|E| = 233`, `f = 0.639, 0.476, 0.348, 0.249`; the
> first two exceed the band, so the rule picks **γ = 2.0** — not the γ = 1.5
> that resolved at matched horizon. That the rule misses the known winner is
> the evidence it wasn't reverse-engineered, but the check happened. Verify the
> four `f_γ` values against artefacts before relying on this.

**Ordering.** Test gates threshold selection; both gate performance. No
performance quantity is computable in Phase 2B.

**Stop conditions.** Test fails → stop. Test passes but no candidate clears the
retained criteria → stop; do not pick a least-bad candidate. Any §2 check fails
→ stop before execution.

---

## 2. Run before anything else

None of §1 executes until these pass. This is the part that would have caught
both of the failures documented in the manuscript's §7.6.

**Size.** Block resamples of observed `VI` paired with an independently
resampled `s`. 2,000 reps. Report empirical size at nominal 0.05.
**Fail if > 0.10.** Interpret the eventual result against measured size, not
nominal, in both directions.

**Power.** Plant monotone association of known strength, report the curve.
**Fail if MDE₈₀ > `ρ_s = 0.20`.**

> The 0.20 bar is a judgment call, not a derivation. Phase 2A's MDE₈₀ of
> (0.15, 0.20] was in `D_VI` units — a difference of medians — which is a
> different scale from a rank correlation, so the resemblance is coincidence
> and the two are not comparable. On synthetic data with plausible persistence
> the test reaches 80% power at `ρ_s ≈ 0.18`, so 0.20 is a real bar rather than
> a formality. If the real data lands just over it, that is a decision for the
> author, not an occasion to quietly move the threshold. Report the full power
> curve either way and interpret the eventual result against it.

**Falsification.** Run the whole test on the Phase 2D structureless null
environments, which already exist in the repo. **Fail if significant at 0.05 in
more than 10% of them.** A criterion that fires on structureless data is
measuring the pipeline.

**Blindness.** Test asserting no return-performance symbol or risk-free series
is reachable from the Phase 2B module. Runs in CI.

If size, power, or falsification fails, Phase 2B does not run. That result is
worth knowing and costs days rather than months.

---

## 3. Constraints on the agent

With no reviewer in the loop these are the only thing standing between the
protocol and specification search, so enforce them structurally, not by
instruction.

- Implement this spec. Do not choose, tune, or amend it.
- Any ambiguity halts and reports rather than being resolved locally.
- No parameter changes in response to an observed output.
- Work on a branch with no reachable path to performance code. The blindness
  test enforces it; the branch makes it physical.
- Any modification to a hash-frozen file halts and reports.
- All test suites run after any code change.
- Single-file updates only, no full-tree replacements.
- Holdout unreachable without an explicit written unlock in a commit.

---

## 4. Before this is used

- Verify the four `f_γ` values against released artefacts — derived above from
  Table 6, not recomputed.
- Confirm `n` for `VI(t, t−5)`; 233 is the trigger-series count and the `h = 5`
  count may differ at the boundary.
- Commit and push this file. The Phase 2 pre-registration revisions being
  gitignored is an open disclosure item; don't repeat it.

Manuscript note, unrelated to 2B: §3.3 records placebo seed `20260817`, §4.7
records gate seed base `20262817`. One digit apart, one is likely a typo.
