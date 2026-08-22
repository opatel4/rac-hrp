# Phase 2A — Audit Bundle Index

**Experiment:** RAC-HRP Phase 2A, structural calibration gate for the
absorption-ratio change trigger (development region only).
**Outcome:** PHASE 2 CLOSED — NO ADMISSIBLE gamma. Negative result, advisor-approved.
**Frozen specification:** RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx (countersigned).

This index binds the artefacts that constitute the Phase 2A record. Commit hashes
below are the authoritative pointers; the manifests additionally embed the code
hashes of the producing modules, which should agree with the committing revision.

## Result (one line)

Under the prospectively frozen specification, the proposed absorption-ratio change
trigger did not demonstrate sufficient structural informativeness to qualify as
the adaptive re-clustering mechanism. Every candidate gamma in {0.5, 1.0, 1.5, 2.0}
failed at least two hard criteria; every candidate failed `cluster_informativeness`
independently, so the stop does not depend on the timing criterion. No performance
quantity was ever computed.

## Artefacts

| # | Artefact | Path | Role |
|---|----------|------|------|
| 1 | Frozen pre-registration | RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx | countersigned spec (external) |
| 2 | Gate manifest | outputs/phase2/calibration_manifest.json | frozen gate record; embeds code hashes |
| 3 | Gate table | outputs/phase2/calibration_table.csv | per-gamma criteria + pass/fail |
| 4 | Erratum E1 | RAC_HRP_Phase2_rev5_ERRATUM_E1.md | corrects §1 112->111 provenance error |
| 5 | Reconciliation note | RAC_HRP_Phase2_Reconciliation_111_vs_112.md | 111-vs-112, resolved (refit != trigger) |
| 6 | Diagnostic record | outputs/phase2_diagnostics/modal_gap_null.json | modal-gap null characterisation |
| 7 | Diagnostic script | scripts/diagnose_modal_gap_null.py | reproduces #6; seed 20260821, B=10,000 |
| 8 | Orchestrator | scripts/run_phase2.py | reproduces #2, #3 from ~/rac_hrp_data/raw |
| 9 | Archival memo | RAC_HRP_Phase2_Gate_Result_Memo_v3.md | advisor-approved result memo |

## Commit hashes (implementation-control manifest)

Fill in the memo hash after committing v3; the rest are recorded from this session.

| Commit | Scope |
|--------|-------|
| 5d5656b | provenance-tagged durable test-region lock (replaced process-local counter) |
| b582af2 | shadow-guard test: fail loudly if folds.py shadows the durable lock |
| a25cd87 | variation_of_information added to core.clustering (frozen VI statistic) |
| 633ce27 | calibration runner, steps 1-3 of frozen procedure |
| 74e517d | version frozen calibration record (manifest, table) + diagnostic record |
| 86224a4 | audit: reconcile 111 vs 112; Erratum E1 |
| 8a5e4fe | modal-gap null characterisation script |
| _(fill)_ | run_phase2.py orchestrator commit |
| _(fill)_ | gate-result memo v3 (archival) |

## Findings of record

1. Inherited gamma = 1.0 fires too frequently (47.6% > 40% ceiling).
2. Increasing gamma resolves the firing-rate problem (gamma in {1.5, 2.0} inside band).
3. The trigger is NOT equivalent to a fixed periodic schedule under the frozen
   separation test (no candidate exceeds the placebo threshold).
4. Trigger events are substantially more temporally clustered than uniform random
   placement of the same count (post-gate diagnostic; placement null only).
5. More selective thresholds show larger D_VI point estimates (+0.033 -> +0.096),
   but positive in direction, statistically unresolved (Holm p in [0.221, 0.556]).
6. Insufficient evidence that trigger dates identify greater cluster restructuring.
7. Therefore the proposed RAC mechanism does not clear its own structural
   admissibility standard.

## Open (NOT part of Phase 2A; do not amend Phase 2A to pursue)

- **Mechanism question (§4d of the memo):** whether the observed burstiness is
  regime-driven or endogenous to the trigger construction is unresolved. Settling
  it requires a pipeline-level structureless null (regime-free returns through the
  identical frozen returns -> Sigma -> AR -> AR^s -> dAR -> trigger machinery). This
  is a post-gate mechanism diagnostic and cannot alter the Phase 2A outcome.
- **Phase 2B:** if a second-generation trigger is pursued, it is a NEW
  pre-registered specification motivated by this failure, not an amendment to
  Phase 2A. Mechanism family to be chosen only after the structureless-null
  diagnostic.

**Status: Phase 2A CLOSED. Archived; not further edited.**
