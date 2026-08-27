# ERRATUM E2 — Phase 1: silent deletion of the MHRP_EV allocator

**Type:** reproducibility defect. Code deleted; result unaffected.
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
2. **Proposed** — a coverage test asserting that every `Strategy` declared in
   `scripts/run_phase1.py`'s `BASELINES` references an allocator the engine
   implements. One assertion; converts this class of deletion from a discovery
   weeks later into a red test immediately.

Standing policy, reaffirmed: no `cp -R` into `rac_hrp/`; copy named files only and
run `git status` immediately after any install.

## Disposition

No reported quantity changes. The Phase 1 baselines table, the estimator
sensitivity table, and every downstream Phase 2 result stand as recorded. This
erratum documents a period during which one archived result was not reproducible
from the repository, and its resolution.
