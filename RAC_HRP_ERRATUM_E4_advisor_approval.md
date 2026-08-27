# ERRATUM E4 — Advisor Approval Statements

**Issued:** [date]
**Affects:** `docs/protocol/RAC-HRP_Phase05_Completion_Memo_rev4.docx` (statements on approval
medium and approval dates); `RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md` (status line);
`RAC_HRP_Phase2D_Mechanism_Result_Memo.md` (references to a countersigned pre-specification);
`RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md`.
**Severity:** false statement of fact regarding independent authorization. No result, verdict,
seed, or code path is affected.
**Frozen documents are not edited.** This erratum is the correction of record, consistent with the
handling of E1 and E3.

## 1. Statements as issued

The Phase 0.5 completion memorandum states that approval was given by dated advisor correspondence
and records approval dates. The Phase 2D documents describe a countersigned pre-specification and a
countersigned serial runner.

## 2. Correction

No independent party approved, authorized, reviewed, or countersigned any decision in this project.
It is a single-author study. Every reference to advisor approval, advisor correspondence, advisor
ruling, or countersignature is withdrawn.

Dates previously attributed to advisor correspondence reflect the author's own decisions on those
dates. They remain accurate as decision dates and are inaccurate as approval dates.

## 3. What is not withdrawn

The prospective character of the specifications is unaffected and independently verifiable:
documents were hashed before the implementing code was committed, and the commit timestamps
establish the ordering. The decision memoranda were written before the decisions they describe were
acted on, and are released. What did not occur is external authorization.

## 4. Correction of record

Manuscript §7.6 (no independent authorization) and `docs/CORRECTION_NOTICE_single_author.md`.

## 5. Pattern

This is the fourth documented defect in this project, and the first that is not a transposition.
E1, E2 and E3 each attached a correct quantity to the wrong context. E4 is a claim about a person
who does not exist, propagated from a document template into summary documents and then into the
manuscript. It was found the same way as the others: by comparing a claim against the artefact
that was supposed to support it. In this case the supporting artefacts — blank sign-off blocks in
every frozen specification — contradicted the claim directly.
