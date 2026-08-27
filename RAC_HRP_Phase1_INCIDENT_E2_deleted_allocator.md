# INCIDENT E2 — Phase 1: silent deletion of the MHRP_EV allocator

**Classification:** reproducibility / code-integrity INCIDENT.
Distinguished from E1, which is a documentation erratum. E2 temporarily broke
exact reproducibility of a committed result and is recorded as an incident with a
full chronology, not as a documentation correction.

**Type:** code deleted; result unaffected.
**Effect on any reported number:** NONE — the archived value reproduces exactly.
**Status:** RESOLVED. Code restored from history; result verified.

## The defect

Commit `be7aa60` ("Phase 1: Molyboga equal-vol variant (0.534 vs 0.574) + test-region
lock hardening") implemented the MHRP_EV allocator and produced the Phase 1
baseline result recorded in `outputs/phase1/phase1_baselines.csv`:

> MHRP_EV, Sharpe = 0.5340985519084631

Commit `f6e09dc` ("Phase 2 + EWMA: implement frozen specs; validation suites pass
(8/8, 12/12, 21/21)") subsequently **deleted the producing code**:

| File | Removed |
|---|---|
| `rac_hrp/core/allocators.py` | 66 lines: `_cluster_vol` helper, `hrp_equalvol_weights`, and the documentation recording which Molyboga components were and were not implemented |
| `rac_hrp/backtest/engine.py` | 3 lines: the import, the `needs_tree()` membership test, and the `hrp_equalvol` allocator branch |

`f6e09dc` was otherwise purely additive (Phase 2 modules, EWMA estimator, test
suites, records). No other allocator was touched: `hrp_weights`, `erc_weights`,
`equal_weight`, `min_variance` and the recursive bisection are unchanged, so no
other Phase 1 or Phase 2 number was affected.

**Consequence.** From `f6e09dc` until this erratum, the repository contained a
committed result that could not be regenerated from the committed code.
`scripts/run_phase1.py` still declared `Strategy("MHRP_EV",
allocator="hrp_equalvol", ...)`, so any attempt to re-run Phase 1 failed with
`ValueError: unknown allocator 'hrp_equalvol'`.

**Why it went undetected.** Nothing re-ran Phase 1 between `f6e09dc` and the EWMA
sensitivity work. The three test suites (21/21, 12/12, 8/8) all passed throughout:
none exercises the Phase 1 baseline list, so no test covered the path. The defect
surfaced only when Phase 1 was re-run to add the `ewma_cc` estimator column.

## Chronology of record

| Stage | Commit | Event |
|---|---|---|
| Producing commit | `be7aa60` | MHRP_EV allocator implemented; Sharpe 0.534 produced and committed |
| Deletion | `f6e09dc` | 66 lines removed from `allocators.py`, 3 from `engine.py`; result orphaned |
| Outage | — | Committed result not regenerable from committed code; undetected because nothing re-ran Phase 1 and no suite covered the path |
| Discovery | — | Surfaced when Phase 1 was re-run to add the `ewma_cc` estimator column |
| Restoration | (this commit) | Both files restored from `be7aa60` (original code, not a reimplementation) |
| Verification | — | Phase 1 re-run; MHRP_EV reproduces Sharpe 0.534; accounting reconciles for all five baselines |

**No result was revised during or as a consequence of the outage.** No number was
recomputed, reinterpreted, or replaced; the archived value was reproduced, not
superseded.

## Resolution

Both files were restored from `be7aa60` — the **original implementation**, not a
reimplementation, so behaviour is identical rather than approximately so:

```
git checkout be7aa60 -- rac_hrp/core/allocators.py
git checkout be7aa60 -- rac_hrp/backtest/engine.py
```

Restoration diffs were confirmed to be insertions only (66 and 5 lines
respectively, with 2 deletions in `engine.py` accounted for by the import line
being rewrapped), so nothing added after `be7aa60` was lost.

**Verification.** Phase 1 was re-run in full. MHRP_EV reproduced

> Sharpe = 0.534 (archived: 0.5340985519084631)

and the accounting reconciliation passed for all five baselines (median absolute
difference 0.0; recomputed gross return == engine gross return). All three test
suites pass unchanged, with every frozen Phase 2 value identical (0.3818, 0.1714,
0.291667, p = 0.00599, seed 20262819).

## Preventive measure

This is the third silent code reversion identified in this project (two affecting
`rac_hrp/backtest/folds.py`, one affecting the allocator path), all arising from
whole-file or whole-tree copies overwriting separately-patched files. Two
mitigations are in place or proposed:

1. **In place** — `tests/test_region_lock.py::test_lock_implementation_is_not_shadowed`
   fails if `folds.py` shadows the durable lock implementation.
2. **In place** — `tests/test_phase05.py::test_phase1_baselines_have_implemented_allocators`
   asserts that every `Strategy` declared in `scripts/run_phase1.py`'s `BASELINES`
   references an allocator the engine implements. This is the check that would
   have caught E2 immediately.
3. **Proposed** — migration of the suites to pytest, sequenced AFTER the
   scientific results are hashed so engineering churn does not blur their
   provenance. Note: pytest auto-discovery removes the
   "test defined but never registered" failure mode, but does NOT make production-
   code deletion structurally impossible. Discovery must be paired with explicit
   invariants — registry-completeness tests, import/dispatch tests for every
   declared strategy, golden-result reproduction tests for critical baselines, a
   collected-test-count assertion, and no `sys.exit()` structure that can leave
   definitions unreachable.

   The coverage test in (2) was itself initially inert: appended below the
   runner's `sys.exit()`, it never executed while the suite reported green. The
   test written to catch silent deletions was silently doing nothing — the same
   failure shape as the defect it targets.

Standing policy, reaffirmed: no `cp -R` into `rac_hrp/`; copy named files only and
run `git status` immediately after any install.

## Disposition

No reported quantity changes. The Phase 1 baselines table, the estimator
sensitivity table, and every downstream Phase 2 result stand as recorded. This
erratum documents a period during which one archived result was not reproducible
from the repository, and its resolution.
