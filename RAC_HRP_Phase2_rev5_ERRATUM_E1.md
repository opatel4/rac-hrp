# ERRATUM E1 — Phase 2 Pre-Registration rev.5, Section 1

**Attaches to:** RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx (frozen, countersigned)
**Type:** documentation provenance correction. NOT a methodological amendment.
**Effect on decision rule or any gate conclusion:** NONE.
**Issued:** post-gate, on advisor ruling. The frozen document is not edited; this
erratum is issued and hashed alongside it and the calibration manifest.

## The error

Section 1 states, of the gamma = 1.0 candidate:

> "At gamma = 1.0, f = 112/233 = 48.1% — gamma = 1.0 has already failed the
> firing-rate criterion."

The figure **112** is not a Phase 2 trigger count. It is the count of
`refit = True` observations in the Phase 0.5 diagnostic artefact
`archive/phase05_final/v1_preserved/rac_diagnostics.csv` (112 of 240 total
rebalances), produced by pre-freeze Phase 0.5 code under a different absorption-
ratio construction. It was transcribed into the pre-registration as if it were
the frozen Phase 2 trigger firing rate over the 233 eligible rebalances. It is
not.

## The correct figure

Under the frozen Phase 2 trigger definition (`|dAR| > gamma * sigma`, sigma =
`rolling(12, min_periods=6).std(ddof=1).shift(1)`, k frozen at 15), the gamma =
1.0 trigger count is:

> **111 of 233 eligible rebalances = 47.6%.**

Source: frozen calibration run, `outputs/phase2/calibration_table.csv`,
gamma = 1.0 row (`n_events = 111`, `n_eligible = 233`).

## Why the conclusion is unchanged

The pre-registration's substantive claim in Section 1 — that gamma = 1.0 fails
the informativeness criterion — holds under the corrected figure:

> 47.6% > 40% ceiling  =>  gamma = 1.0 fails informativeness.

The 40% ceiling is not revised. More broadly, the Phase 2 stop does not rest on
this figure: every candidate independently fails `cluster_informativeness`
(Holm-adjusted p in [0.221, 0.556]; none < 0.05), so no admissible gamma exists
regardless of the informativeness criterion or this correction.

## Provenance of this erratum

The discrepancy was raised in advisor review of the gate-result memo and
reconciled in `RAC_HRP_Phase2_Reconciliation_111_vs_112.md`, which documents four
independent confirmations that `refit` (Phase 0.5) and the Phase 2 trigger are
different statistics, and why a date-level diff between them cannot be performed
(no comparable trigger set survives; the Phase 0.5 source is absent; the archived
AR series was built under a different k-rule and is not guaranteed equal to the
frozen-gate AR).

Status: **Resolved — documentation provenance error, not trigger drift or
implementation inconsistency.**
