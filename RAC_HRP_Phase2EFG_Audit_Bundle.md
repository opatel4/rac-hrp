# Phase 2E / 2F / 2G — Audit Bundle Index

**Experiments:** post-gate diagnostics for the Phase 2A structural calibration gate
(development region only). Phase 2A is CLOSED throughout; nothing in this bundle reopens it.

**Outcomes.**
- **2E-HORIZON** — Outcome H. The clustering-change effect is statistically resolved at a
  horizon matched to the trigger, at one threshold and suggestively at a second once the
  procedure's measured size is taken into account.
- **2E-POWER** — the gate had 11–33% power against the effect sizes observed. MDE₈₀ is
  (0.15, 0.20] at γ ∈ {0.5, 1.0, 1.5} and (0.20, 0.30] at γ = 2.0.
- **2F** — Outcome C. A *W*-calibrated positive control brackets the observed burstiness at
  three of four thresholds, where the original control bracketed none.
- **2G** — the clustering-change effect is **not stable in the retained-component count**,
  changing sign at *k* = 20. A continuous rank statistic does not resolve it (ρ = +0.072,
  *p* = 0.239). The horizon curve is non-monotone and peaks at *h* = 6, not the
  pre-specified *h* = 5.

**Single author.** No independent party reviewed or authorised any specification here. Each
freeze rests on the document hash, the commit recording it, and the absence of implementing
code at that commit. See `docs/CORRECTION_NOTICE_single_author.md`.

This index binds the artefacts. Commit hashes are the authoritative pointers; result
manifests additionally embed the code hashes of the producing modules.

---

## Specifications and freeze records

Every specification was hashed and committed before any implementing code existed. Where a
specification required correction, the superseded revision is preserved unaltered and the
reason is recorded in its successor's revision history.

| Phase | Frozen revision | SHA-256 | Freeze commit |
|---|---|---|---|
| 2E | `RAC_HRP_Phase2E_PreSpec_rev8.md` | `cfdd64cc…c403674` | `fa13a8b` |
| 2F | `RAC_HRP_Phase2F_PreSpec_rev2.md` | `1adee84e…5709417f` | `8b1a809` |
| 2G | `RAC_HRP_Phase2G_PreSpec_rev1.md` | `c431974e…79794fd2` | `946f5d8` |

Freeze files: `PHASE2E_FREEZE.txt`, `PHASE2F_FREEZE.txt`, `PHASE2G_FREEZE.txt`.

### Superseded revisions and why

| Revision | Commit | Superseded because |
|---|---|---|
| 2E rev.3 | `fc4fd84` | base seeds left unfilled at freeze |
| 2E rev.4 | `78d6e95` | eligible-set contraction inconsistent with the gate's own construction |
| 2E rev.5 | `8b5bd90` | governing revision for 2E-HORIZON; superseded for 2E-POWER only |
| 2E rev.6 | `601ad64` | §2.3 overclaimed what the placement comparison isolates |
| 2E rev.7 | `14ca67b` | base path could produce neither a null nor a sampling distribution |
| 2F rev.1 | `ba5c946` | base seed left unfilled at freeze |

**2E-HORIZON was specified and run under rev.5.** rev.6 through rev.8 amend the 2E-POWER
base path only and do not touch that diagnostic; its governing revision is rev.5 and the
runner records this.

**rev.7 is the substantive failure.** It was frozen, implemented, and executed to completion
— 130,000 replications over 31 minutes — before its output revealed the specified
construction was incapable of the measurement it specified. The invalidated output is
preserved at `outputs/phase2e_power/power_result_INVALID_rev7.json` and is **not a result**.
Manuscript §7.7 reports this as evidence about what freezing does and does not guarantee.

---

## Artefacts

| # | Artefact | Path | Role |
|---|---|---|---|
| 1 | 2E-HORIZON result | `results/phase2e_horizon_result.json` | horizon-matched D_VI, all four γ |
| 2 | 2E-POWER result | `results/phase2e_power_result.json` | power curves, MDE₈₀, empirical size |
| 3 | 2E-POWER invalidated | `outputs/phase2e_power/power_result_INVALID_rev7.json` | rev.7 output, preserved, **not a result** |
| 4 | 2F control result | `results/phase2f_control_result.json` | *W*-calibrated positive control |
| 5 | 2G result | `results/phase2g_result.json` | k sweep, rank statistic, horizon curve |
| 6 | Horizon module | `rac_hrp/phase2/horizon.py` | labelled pass + VI at arbitrary lag |
| 7 | Power module | `rac_hrp/phase2/power.py` | block-resampled base path, planted effects |
| 8 | 2E-HORIZON runner | `scripts/run_phase2e_horizon.py` | reproduces #1 |
| 9 | 2E-POWER runner (serial) | `scripts/run_phase2e_power.py` | reproduces #2 |
| 10 | 2E-POWER runner (parallel) | `scripts/run_phase2e_power_parallel.py` | bit-identical; `--verify` mode |
| 11 | 2F runner | `scripts/run_phase2f_control.py` | reproduces #4 |
| 12 | 2G runner | `scripts/run_phase2g.py` | reproduces #5 |
| 13 | Exploratory harness | `scripts/explore_power_construction.py` | synthetic verification of the rev.8 construction; **not a result** |

---

## Commit hashes (implementation-control manifest)

| Commit | Scope |
|---|---|
| `fc4fd84` | 2E rev.3 freeze (seeds unfilled) |
| `78d6e95` | 2E rev.4 freeze |
| `8b5bd90` | 2E rev.5 freeze — governing for 2E-HORIZON |
| `285d5b1` | 2E-HORIZON module, no results |
| `b50e8c1` | 2E-HORIZON runner, no results |
| `28d5f92` | **2E-HORIZON result** |
| `601ad64` | 2E rev.6 freeze |
| `e7df5f0` | 2E-HORIZON runner records rev.5 as governing |
| `14ca67b` | 2E rev.7 freeze |
| `5ad13c6` | 2E-POWER module against rev.7, no results |
| `6869314` | 2E-POWER serial runner, no results |
| `855713a` | 2E-POWER parallel runner, no results |
| `6dfee31` | exploratory construction harness (synthetic only) |
| `fa13a8b` | 2E rev.8 freeze |
| `9a7cbb4` | 2E-POWER to the rev.8 construction |
| `1569cc8` | parallel runner guard fix |
| `dc09b28` | **2E-POWER result** |
| `ba5c946` | 2F rev.1 freeze (seed unfilled) |
| `8b1a809` | 2F rev.2 freeze |
| `737873c` | 2F runner, no results |
| `ef34ecb` | **2F result** |
| `946f5d8` | 2G rev.1 freeze |
| `83112ea` | correction notice: k-regime naming defects |
| `119bbae` | 2G module and runner, no results |
| `527f750` | **2G result** |

Every result commit postdates its specification freeze, and every implementation commit
postdates the freeze it implements. This is checkable from the log without trusting the table.

---

## Reproduction checks

Each diagnostic contains at least one cell required to reproduce a frozen result exactly.
All passed; a failure aborts before any statistic is reported.

| Check | Requirement | Outcome |
|---|---|---|
| 2E-HORIZON equivalence | one-step VI recomputed from retained labels must match the frozen gate **bitwise** | pass |
| 2E-HORIZON eligibility | E = 233; event counts 149/111/81/58 | pass |
| 2E-POWER δ = 0 | empirical size inside the frozen band [0.02, 0.10] | 0.0730, pass |
| 2F duration | realised regime runs must exceed *W* = 504 | 1224 / 761 days, pass |
| 2G-K at *k* = 15 | must reproduce the frozen gate's event counts and D_VI | pass |
| 2G-HORIZON at *h* = 1 | must reproduce the frozen gate's D_VI | pass |
| 2G-HORIZON at *h* = 5 | must reproduce the 2E-HORIZON result | pass |

**Cross-machine reproduction.** 2E-HORIZON was run on both a macOS laptop and a Linux VM
under pinned numpy 1.26.4, pandas 2.2.2 and scipy 1.14.1, returning identical values to four
decimal places at every γ, including block lengths.

**Parallel equivalence.** The 2E-POWER parallel runner was verified against the serial one
replication by replication (`--verify 100`), returning identical rejection decisions and
block lengths. Seeds are replication-level, so execution order cannot affect results.

---

## Implementation deviations

| Deviation | Reason |
|---|---|
| `horizon.py` duplicates the gate's structural loop | `calibration.py` is hashed in `outputs/phase2/calibration_manifest.json` and must not be modified; the duplication risk is converted into a checked invariant by the bitwise equivalence assertion |
| `run_phase2f_control.py` dispatches the slow regime environment directly | `environments.py` is hashed in `outputs/phase2_mechanism/mechanism_null.json`; registering a new environment would shift the ordering used for seed derivation, exactly as `environments_static.py` avoids for environment S |
| 2G h-sweep drops undefined VI positions | at *h* = 8 one rebalance falls below the universe-overlap floor; the frozen statistic takes medians without filtering, so one undefined value propagates to both arms |
| 2F loads the density cache from the frozen manifest | recomputing would give identical values by construction; loading guarantees it |

---

## What these diagnostics establish, and what they do not

They do not render any threshold admissible. The gate is conjunctive and every candidate
fails timing variation on modal-gap share alone; two also fail informativeness. No portfolio
was constructed and the holdout was not opened.

They establish that the Phase 2A null was overdetermined. The criterion sampled structural
change at a one-rebalance horizon while the trigger operates at five, and it had 11–33% power
against the effects present. Either alone would have produced the observed result.

They also establish that the horizon-matched effect does not survive robustness testing
intact: its sign depends on the retained-component count, a parameter fixed by a rule applied
at a single date at the start of the sample and never varied before the gate was frozen.

---

## Open

**Phase 2B**, if pursued, is a new pre-registered specification and not an amendment. Phase
2E and 2G narrow its design question considerably. The alignment question — what |ΔAR| is
responding to — is partly answered: it relates to hierarchical restructuring measured over
the interval the trigger actually spans. The unanswered question is why that relationship is
unstable in *k*, and any second-generation criterion should be demonstrated stable in both
the component count and the measurement horizon **before** it is frozen, not after.

**Status: 2E, 2F and 2G COMPLETE. Archived; not further edited.**
