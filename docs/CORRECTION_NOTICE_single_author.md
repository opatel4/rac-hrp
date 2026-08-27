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
