# ERRATUM E3 — Environment Label Transposition, Phase 0.5 Completion Memo rev.4

**Issued:** [date]
**Affects:** `docs/protocol/RAC-HRP_Phase05_Completion_Memo_rev4.docx`, §on v1 preservation (line 80
of the extracted text)
**Severity:** documentation provenance error. No result, verdict, decision, or downstream conclusion
is affected.
**Frozen document is not edited.** This erratum is the correction of record, consistent with the
handling of Erratum E1.

---

## 1. The statement as issued

> "v1 is preserved as an immutable record and did not pass universally. Two cells fell outside the
> ±0.10 margin: A vs EW (CI [−0.108, +0.032]) and D vs ERC (+0.102, a cross-allocator contrast).
> The thesis-critical Environment C passed cleanly."

## 2. The correction

Two errors, one of attribution and one of characterisation.

**2.1 Environment label.** The confidence interval [−0.108, +0.032] belongs to
**D_regime_switch_vol vs EW**, not to A_iid_gaussian vs EW. From `results/null_gate_v1.csv`:

| environment | vs | mean ΔSharpe | 95% CI | verdict |
|---|---|---|---|---|
| A_iid_gaussian | EW | −0.0508 | [−0.084, −0.017] | PASS |
| D_regime_switch_vol | EW | −0.0377 | [−0.108, +0.032] | PASS |

A vs EW lies well inside the margin on both sides and was never a cell of concern.

**2.2 Characterisation of the rule.** The v1 decision rule is **one-sided at +0.10** (completion
memo rev.4, §on gate configuration: "one-sided paired-t, margin +0.10"; implemented at
`rac_hrp/nulls/gate.py:282`, branching on `cfg.null_gate_sided`). Under a one-sided rule, a
confidence interval extending to −0.108 does not fall outside the margin, because the margin is not
tested on that side. The rule is one-sided by design: a pipeline manufacturing signal from noise
produces a *positive* edge, so a negative excursion is not the failure mode of interest.

Consequently **one** cell failed, not two.

## 3. Corrected statement

> "v1 is preserved as an immutable record and did not pass universally. One cell failed the
> one-sided +0.10 equivalence rule: D vs ERC at +0.102, CI [+0.038, +0.167], a cross-allocator
> contrast. A second cell, D vs EW at −0.0377, had a confidence interval extending to −0.108, past
> the margin on the untested side; it passed the rule as specified and is noted for completeness.
> The thesis-critical Environment C passed cleanly."

## 4. Provenance of the error

The transposition appears to originate in the completion memo alone; the underlying result file
`null_gate_v1.csv` is correct, and the Environment-D decision memorandum tabulates the D vs EW cell
correctly in its own §4 table alongside the D vs ERC failure. The error is confined to the summary
layer.

## 5. Downstream propagation

The transposed label was carried into an advisor review of the Phase 0.5 disclosure draft, which
cited the completion record. That draft has been corrected before commit. No published artefact
carries the error.

## 6. Pattern

This is the third defect in this project sharing a single structure: a correct quantity attributed
to the wrong context.

| | Defect | Correct quantity | Wrong context |
|---|---|---|---|
| E1 | Phase 2 pre-registration figure | Phase 0.5 re-clustering count over 240 rebalances | presented as a γ = 1.0 trigger count over 233 eligible rebalances |
| E2 | Phase 1 archived result | equal-volatility allocator result | driver still declared an allocator deleted by a later commit |
| E3 | Phase 0.5 completion memo | CI [−0.108, +0.032] | attributed to environment A rather than D |

All three were found by cross-checking a document against the artefact it describes. None was
detectable by the test suite, and none would have been caught by any automated check the project
currently runs. The manuscript's limitations section records the pattern rather than the individual
instances.

## 7. Related code-documentation defect (not an erratum)

`rac_hrp/nulls/gate.py` describes the equivalence rule in two-sided terms — line 169 prints
`|dSharpe| <= tolerance`, line 269 computes `material = abs(mean) > tol` — while the configured
behaviour at line 282 is one-sided. The executed rule is the configured one and no verdict is
affected, but the module's own language is inconsistent with what it does. Corrected as a code
change with a changelog entry, not by erratum.

Additionally, `null_gate_sided` should be recorded in `results/freeze_manifest.json`, which
currently pins the base seed, replication counts, comparators, materiality margin and code hashes
but not the sidedness. The verdict depends on it.

## 8. Actions

- [ ] Commit this erratum alongside E1 and E2
- [ ] Cite E3 in `RAC_HRP_Phase2_Audit_Bundle.md` artefact table
- [ ] Correct `gate.py` docstring and `abs(mean)` language; changelog entry
- [ ] Add `null_gate_sided` to `freeze_manifest.json`; re-run manifest builder
- [ ] Append the pattern paragraph to manuscript §7.4
