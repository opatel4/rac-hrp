# CLAUDE.md — RAC-HRP

This is a pre-registered empirical finance study. Specifications are frozen before
implementing code is written, and the ordering is the whole point. Nothing below is
stylistic.

There is no second human reviewing decisions. That makes these constraints the only
barrier between the protocol and specification search, so they are enforced, not
advisory.

## Never

- **Never compute a performance quantity in gate or diagnostic code.** No Sharpe
  ratio, drawdown, alpha, information ratio, or risk-free series in any module under
  a structural-gate or diagnostic path. Turnover may be computed as a reported
  diagnostic only, and may never pass or fail a candidate.
- **Never touch the holdout** (2023-01-01 to 2024-12-31). It is single-use. Opening
  it requires an explicit written unlock recorded in a commit. Absent that commit,
  any code path reaching those dates is a defect.
- **Never change a parameter in response to an observed output.** Thresholds, grids,
  horizons, seeds, block lengths, and criteria are fixed in the spec before
  execution. If a result suggests a different value, that is a finding to report,
  not an edit to make.
- **Never modify a hash-frozen file.** Halt and report instead.
- **Never resolve an ambiguity in a specification.** Halt and report. A guess that
  happens to be reasonable is still an unrecorded decision made by an agent.
- **Never replace a full directory tree.** Single-file updates only. Full-tree
  copies have silently reverted patched files in this repo before.

## Always

- Run every test suite after any code change, and report the counts.
- Verify code hashes against the freeze manifest before running frozen code.
- Use the seed recorded in the spec. Never a fresh or arbitrary seed.
- Report the number of observations actually used, alongside the number expected.
  Silent boundary losses have caused errors here.
- State when a computed number disagrees with a number in the manuscript. Do not
  reconcile it silently.
- Keep gate and diagnostic work on a branch with no reachable path to performance
  code.

## Order of operations

For any new phase:

1. Specification written and committed. **Committed and pushed, not gitignored.**
2. Validation checks from the spec implemented and run — size, power, falsification.
3. Only if those pass: implementing code written, hashed, entered in the manifest.
4. Analysis executed once.

Implementing code written before step 1 invalidates the freeze. If you find yourself
at step 3 without steps 1 and 2 complete, stop and say so.

## Current phase

Phase 2B. Spec: `PHASE2B_SPEC.md`. Section 2 of that file must pass before any
Phase 2B analysis runs. If size, power, or falsification fails, Phase 2B does not
run and that outcome is reported.

## Context worth having

- Phase 2A applied a five-criterion performance-blind gate and returned no admissible
  threshold. Post-gate work established the decisive criterion was underpowered
  (MDE₈₀ two to nine times any effect present) and sampled at the wrong horizon.
- Phase 2D confirmed the trigger's bursty event timing is not manufactured by the
  pipeline.
- Two specifications in this project were frozen, correctly implemented, and executed
  before anyone noticed they could not measure what they claimed. Both were caught by
  absurd output, not by review. This is why validation-before-freeze is mandatory
  rather than recommended.

## Environment

- Repo: `~/Desktop/GIT projects/rac-hrp/` (note the space).
- Raw CRSP data outside the repo at `~/rac_hrp_data/raw/`.
- conda `base`, not a project venv.
- `OPENBLAS_NUM_THREADS=1` gives a large speedup on 100×100 matrices and is verified
  result-neutral.
- `scripts/verify_numbers.py` checks manuscript claims against artefacts. Run it
  after any result changes.
