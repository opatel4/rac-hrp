# Phase 2A / 2D — Audit Bundle Index

**Experiment:** RAC-HRP Phase 2A, structural calibration gate for the
absorption-ratio change trigger (development region only).
**Outcome:** PHASE 2 CLOSED — NO ADMISSIBLE gamma. Negative result.
**Frozen specification:** RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx (frozen and hashed; single-author, no independent authorization).

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
| 1 | Frozen pre-registration | RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx | frozen spec, docs/protocol/phase2_prereg/ |
| 2 | Gate manifest | outputs/phase2/calibration_manifest.json | frozen gate record; embeds code hashes |
| 3 | Gate table | outputs/phase2/calibration_table.csv | per-gamma criteria + pass/fail |
| 4 | Erratum E1 | RAC_HRP_Phase2_rev5_ERRATUM_E1.md | corrects §1 112->111 provenance error |
| 5 | Reconciliation note | RAC_HRP_Phase2_Reconciliation_111_vs_112.md | 111-vs-112, resolved (refit != trigger) |
| 6 | Diagnostic record | outputs/phase2_diagnostics/modal_gap_null.json | modal-gap null characterisation |
| 7 | Diagnostic script | scripts/diagnose_modal_gap_null.py | reproduces #6; seed 20260821, B=10,000 |
| 8 | Orchestrator | scripts/run_phase2.py | reproduces #2, #3 from ~/rac_hrp_data/raw |
| 9 | Archival memo | RAC_HRP_Phase2_Gate_Result_Memo_v3.md | archival result memo |

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

## Phase 2D — post-gate mechanism diagnostic (COMPLETE)

The §4d mechanism question listed as open at Phase 2A archival has since been
executed and closed. It did not, and could not, alter the Phase 2A outcome.

**Question.** Is the observed temporal burstiness regime-driven, or endogenous to
the trigger construction?

**Result: OUTCOME 2 — beyond regime-free mechanics.** At each of the four frozen
gammas, real-data excess burstiness B_gamma lies above the 97.5th percentile of
BOTH pre-registered regime-free environments (A: zero-correlation vol-matched
Gaussian; S: one static covariance structure). The tested regime-free
architectural explanations are therefore not supported.

| gamma | real B | A q97.5 | S q97.5 | D q97.5 |
|---:|---:|---:|---:|---:|
| 0.5 | 0.1824 | 0.1566 | 0.1165 | 0.1661 |
| 1.0 | 0.3182 | 0.2723 | 0.2370 | 0.3056 |
| 1.5 | 0.4125 | 0.3612 | 0.2963 | 0.4068 |
| 2.0 | 0.5263 | 0.3921 | 0.2953 | 0.4402 |

Qualifications carried in the result memo: (i) D (positive control) does NOT
overlap, so the optional D-consistency clause is unavailable — and because D's
regimes last ~100/~33 daily observations against W = 504, this indicates rapid
regime switching is heavily attenuated by the estimator rather than that regimes
are excluded; (ii) the D margins are thin (+0.006 at gamma = 1.5) and should not
carry independent weight; (iii) S produced LESS excess burstiness than A at every
gamma, contrary to the hypothesis that motivated S — recorded as an observation,
quarantined, not explained.

### Phase 2D artefacts

| # | Artefact | Path |
|---|---|---|
| 1 | Pre-specification rev.4 (frozen, hashed) | RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md |
| 2 | Result memo | RAC_HRP_Phase2D_Mechanism_Result_Memo.md |
| 3 | Implementation deviation record ID1 | RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md |
| 4 | Run manifest + replications | outputs/phase2_mechanism/mechanism_null.json |
| 5 | Run log | mechanism_run.log |
| 6 | Serial runner (frozen, unmodified) | scripts/run_mechanism_null.py |
| 7 | Parallel runner (executed) | scripts/run_mechanism_null_parallel.py |
| 8 | Environment S (standalone; NOT registered) | rac_hrp/nulls/environments_static.py |
| 9 | Timing probe | probe_structural_pass_timing.py |

### Phase 2D commit hashes

| Commit | Scope |
|--------|-------|
| 5dd92b4 | pre-specification rev.4 (frozen, hashed) |
| 194bb6d | mechanism runner + environment S (standalone) |
| 516df25 | Sigma_0 factorisation cache + parallel runner |
| 703ea97 | mechanism null result + run log |
| dfb2126 | result memo (Outcome 2, narrowed) + ID1 |

### Execution notes of record

- 500 replications x 3 environments = 1,500 passes, run ONCE, 33.5 min, 12 workers.
- Environment matched to the frozen gate: numpy 1.26.4, pandas 2.2.2.
- **Cross-machine reproduction:** the diagnostic's real-data reference reproduced
  the frozen Phase 2A gate exactly on independent hardware (E = 233,
  n = 149/111/81/58). The frozen Phase 2A result is portable.
- **Threading invariance:** the frozen gate reproduces bit-for-bit under both
  default and `OPENBLAS_NUM_THREADS=1`. (Pinning is ~13x faster on small matrices;
  the penalty is thread-contention overhead, not computation.)
- Three output-neutral implementation deviations occurred; see ID1.

## Open

- **Phase 2B:** a second-generation trigger, if pursued, is a NEW pre-registered
  specification, not an amendment. Phase 2D reframes its question: the burstiness-
  suppression hypothesis is no longer the leading explanation, so the design
  question becomes **what |dAR| is actually responding to, if not statistically
  distinguishable cluster restructuring** — an ALIGNMENT question (AR change vs
  eigenspace rotation, correlation-matrix distance, tree/cluster distance,
  lead/lag) rather than a firing-frequency one.
- **Bootstrap self-test replication count:** the `P(p<=0.05)` calibration check in
  the Phase 2 stats suite runs 200 null datasets (MC SE ~0.017). Raising it to
  2,000 is a pre-results Monte Carlo precision change; RNG isolation has been
  verified (all generators in `stats.py` are local `default_rng(seed)`; no global
  state), so it cannot perturb any frozen value. Not yet executed.

**Status: Phase 2A CLOSED. Phase 2D COMPLETE. Both archived; not further edited.**
