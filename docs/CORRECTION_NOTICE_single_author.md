# Correction Notice — Single-Author Study

**Issued:** [date]

Several documents in this repository describe methodological decisions as having been approved,
authorized, or countersigned by an advisor. **No independent party reviewed or authorized any
decision in this project.** It is a single-author study throughout.

## Scope

The error is confined to the summary layer: completion memoranda, the audit bundle, module
docstrings, and earlier drafts of the manuscript. It does not affect:

- any result, statistic, verdict, seed, replication count, or code path
- the frozen specification documents themselves, whose sign-off blocks are blank and which
  therefore accurately record countersignature as *requested* and not granted
- the decision memoranda, which are accurate as unsigned memoranda

## Affected documents not edited

Frozen and hash-bearing artefacts are not modified, because editing them would break the
reproducibility chain. Where "countersigned" or "approved" appears in

- `docs/protocol/**`, `outputs/prereg/**`, `archive/**`
- generated manifests (`calibration_manifest.json`, `mechanism_null.json`)
- `CHANGELOG.md` entries predating this notice

it is superseded by this notice and by §7.6 of the manuscript, which is the correction of record.

## What the protocol still rests on

The commitment devices that do not require a second person remain intact and are verifiable:

- specification documents hashed, with hashes recorded in a released manifest
- implementing code committed after those hashes, with commit timestamps
- the selection rule executed by a function rather than applied by hand
- a calibration implementation structurally incapable of computing a performance quantity
- the test region never opened, verified by a machine-checkable assertion

What is absent is independent authorization of judgement calls. The manuscript states this in
§7.6 and reports the one decision most affected by it, in §4.5, with both the original and revised
outcomes so a reader may apply either rule.

## Source strings deliberately left unchanged

Three source files — `rac_hrp/phase2/calibration.py`, `scripts/run_mechanism_null.py`, and
`scripts/run_mechanism_null_parallel.py` — write the word "countersigned" into
`calibration_manifest.json` and `mechanism_null.json`. These strings are deliberately left
unchanged.

The manifests record SHA-256 hashes of those files. Editing the strings changes the hashes and
breaks the correspondence between the recorded values and the code that produced the frozen
results. Restoring that correspondence would require re-running the Phase 2A calibration and the
1,500-replication mechanism null, which would mean the released results came from a later
execution than the one the audit trail describes — a disproportionate change to correct a comment.

The term is inaccurate wherever it appears, in source and in generated artefacts alike, and is
superseded by this notice and by §7.6 of the manuscript.

At the time of this notice the recorded hashes were verified against the files on disk and all
three matched, confirming that the executed code is the code the manifests describe. Should these
phases be re-run for an unrelated reason, the strings should be corrected in that run.
