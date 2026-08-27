#!/usr/bin/env python3
"""
RAC-HRP advisor-attribution sweep.

Removes attributions to an advisor who does not exist, while PRESERVING every
methodological constraint those references describe. A docstring saying "advisor
wording constraint" loses the attribution and keeps the constraint.

EXCLUDED BY CONSTRUCTION:
  - hash-bearing:  rac_hrp/phase2/calibration.py, scripts/run_mechanism_null*.py,
                   any *manifest*.json
  - historical:    CHANGELOG.md  (append a dated entry by hand instead)
  - frozen:        docs/protocol/**, outputs/**, archive/**

Usage, from the repository root:
    python rac_hrp_advisor_sweep.py
    python rac_hrp_advisor_sweep.py --apply
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path.cwd()
applied: list[str] = []
missed: list[str] = []
skipped: list[str] = []

FORBIDDEN = {
    "rac_hrp/phase2/calibration.py",
    "scripts/run_mechanism_null.py",
    "scripts/run_mechanism_null_parallel.py",
    "CHANGELOG.md",
}


def flex(phrase: str) -> re.Pattern:
    return re.compile(r"\s+".join(re.escape(w) for w in phrase.split()), re.IGNORECASE)


def edit(relpath: str, old: str, new: str, apply: bool) -> None:
    if relpath in FORBIDDEN:
        skipped.append(f"{relpath}: EXCLUDED (hash-bearing or historical)")
        return
    p = ROOT / relpath
    if not p.exists():
        missed.append(f"{relpath}: FILE NOT FOUND")
        return
    text = p.read_text(errors="replace")
    pat = flex(old)
    n = len(pat.findall(text))
    if not n:
        if flex(new).search(text):
            skipped.append(f"{relpath}: already done — '{old[:50]}...'")
        else:
            missed.append(f"{relpath}: NO MATCH — '{old[:65]}...'")
        return
    applied.append(f"{relpath}: {n}x '{old[:50]}...' -> '{new[:50]}...'")
    if apply:
        p.write_text(pat.sub(lambda _: new, text))


# ---------------------------------------------------------------------------
# Manuscript-adjacent memos: attributions removed, findings kept
# ---------------------------------------------------------------------------
MEMO_EDITS: list[tuple[str, str, str]] = [
    ("RAC_HRP_Phase2_Audit_Bundle.md",
     "Negative result, advisor-approved.",
     "Negative result."),
    ("RAC_HRP_Phase2_Audit_Bundle.md",
     "| 9 | Archival memo | RAC_HRP_Phase2_Gate_Result_Memo_v3.md | advisor-approved result memo |",
     "| 9 | Archival memo | RAC_HRP_Phase2_Gate_Result_Memo_v3.md | archival result memo |"),
    ("RAC_HRP_Phase2_Audit_Bundle.md",
     "| 2 | Result memo (advisor-approved) | RAC_HRP_Phase2D_Mechanism_Result_Memo.md |",
     "| 2 | Result memo | RAC_HRP_Phase2D_Mechanism_Result_Memo.md |"),
    ("RAC_HRP_Phase2_Audit_Bundle.md",
     "| 6 | Serial runner (countersigned, unmodified) | scripts/run_mechanism_null.py |",
     "| 6 | Serial runner (frozen, unmodified) | scripts/run_mechanism_null.py |"),

    ("RAC_HRP_Phase2_Gate_Result_Memo_v3.md",
     "Incorporates advisor review, the 111-vs-112",
     "Incorporates a subsequent review pass, the 111-vs-112"),
    ("RAC_HRP_Phase2_Gate_Result_Memo_v3.md",
     "the advisor's narrowing of the §4a interpretation",
     "a narrowing of the §4a interpretation"),
    ("RAC_HRP_Phase2_Gate_Result_Memo_v3.md",
     "confirmed under advisor review.",
     "confirmed under review."),
    ("RAC_HRP_Phase2_Gate_Result_Memo_v3.md",
     "(advisor-approved, post-gate,",
     "(pre-specified, post-gate,"),

    ("RAC_HRP_Phase2_rev5_ERRATUM_E1.md",
     "**Issued:** post-gate, on advisor ruling.",
     "**Issued:** post-gate."),
    ("RAC_HRP_Phase2_rev5_ERRATUM_E1.md",
     "The discrepancy was raised in advisor review of the gate-result memo",
     "The discrepancy was raised in review of the gate-result memo"),

    ("RAC_HRP_Phase2_Reconciliation_111_vs_112.md",
     "**Question raised (advisor review):**",
     "**Question raised (review):**"),
    ("RAC_HRP_Phase2_Reconciliation_111_vs_112.md",
     "The advisor's proposed remedy",
     "The proposed remedy"),

    ("RAC_HRP_Phase1_INCIDENT_E2_deleted_allocator.md",
     "**Classification (advisor ruling):**",
     "**Classification:**"),
    ("RAC_HRP_Phase1_INCIDENT_E2_deleted_allocator.md",
     "Note (advisor ruling): pytest auto-discovery removes the",
     "Note: pytest auto-discovery removes the"),

    ("phase1_completion/deferred_items.md",
     "Resolution paths (advisor to rule when unblocked):",
     "Resolution paths (to be decided when unblocked):"),

    # Phase 2D trio
    ("RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md",
     "rev.4 (countersigned)", "rev.4 (frozen, hashed)"),
    ("RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md",
     "**Advisor disposition:** ACCEPTED", "**Disposition:** ACCEPTED"),
    ("RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md",
     "would have perturbed the countersigned Phase 0.5 gate",
     "would have perturbed the frozen Phase 0.5 gate"),
    ("RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md",
     "countersigned serial script", "frozen serial script"),

    ("RAC_HRP_Phase2D_Mechanism_Result_Memo.md",
     "Executed once against the countersigned pre-specification",
     "Executed once against the frozen pre-specification"),
    ("RAC_HRP_Phase2D_Mechanism_Result_Memo.md",
     "The countersigned serial script is unmodified",
     "The frozen serial script is unmodified"),

    ("RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md",
     "Submitted for advisor countersignature BEFORE any replication is run.",
     "Frozen and hashed BEFORE any replication is run."),
    ("RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md",
     "rev.4 — thirteen advisor fixes applied; awaiting countersignature",
     "rev.4 — thirteen review fixes applied; frozen and hashed before execution"),
    ("RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md",
     "| Advisor signature / date | Conditions / notes |",
     "| Freeze hash / date | Conditions / notes |"),
]

# ---------------------------------------------------------------------------
# Code docstrings: attribution removed, constraint preserved verbatim
# ---------------------------------------------------------------------------
CODE_EDITS: list[tuple[str, str, str]] = [
    ("rac_hrp/phase2/stats.py",
     "and can be recorded in the run manifest, as the advisor requires.",
     "and can be recorded in the run manifest, as the frozen specification requires."),

    ("rac_hrp/nulls/env_d_contrast.py",
     "Condition 2 of the advisor ruling on Null Gate v1.",
     "Condition 2 of the Null Gate v1 decision."),
    ("rac_hrp/nulls/env_d_contrast.py",
     "WHAT THIS CONTRAST CAN AND CANNOT ESTABLISH (advisor wording constraint)",
     "WHAT THIS CONTRAST CAN AND CANNOT ESTABLISH (reporting constraint)"),
    ("rac_hrp/nulls/env_d_contrast.py",
     '"""Advisor\'s three-way interpretation rule."""',
     '"""Frozen three-way interpretation rule."""'),

    ("tests/test_covariance_ew.py",
     "Advisor condition: EWMA implementation is AUTHORIZED ONLY AFTER THESE PASS.",
     "Precondition: EWMA implementation is AUTHORIZED ONLY AFTER THESE PASS."),

    ("tests/test_invariants.py",
     "explicit advisor sign-off, never a silent change.",
     "an explicit, logged decision, never a silent change."),

    ("scripts/diagnose_modal_gap_null.py",
     "Advisor ruling (rev.): APPROVED with a corrected decision rule.",
     "Decision (rev.): APPROVED with a corrected decision rule."),
    ("scripts/diagnose_modal_gap_null.py",
     "Advisor's hand-check: gaps, frequencies, modal gap, hand share vs the",
     "Hand-check: gaps, frequencies, modal gap, hand share vs the"),

    ("scripts/condition2_static_vs_erc.py",
     "CONDITION 2 (advisor ruling) -- paired static-HRP vs ERC contrast under Env-D.",
     "CONDITION 2 -- paired static-HRP vs ERC contrast under Env-D."),

    ("scripts/diagnostic_static_vs_erc.py",
     "Condition 2 (advisor ruling, Null Gate v1) -- the decisive diagnostic.",
     "Condition 2 (Null Gate v1) -- the decisive diagnostic."),

    ("scripts/diag_bootstrap_calibration_B.py",
     "the self-test tolerance stays at +/- 0.02 pending advisor review.",
     "the self-test tolerance stays at +/- 0.02 pending review."),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not (ROOT / "rac_hrp").is_dir():
        sys.exit("Run from the repository root.")

    dirty = subprocess.run(["git", "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    dirty = "\n".join(l for l in dirty.splitlines()
                      if "rac_hrp_advisor_sweep" not in l)
    if dirty and args.apply:
        print("Working tree is dirty. Commit or stash first:\n")
        print(dirty)
        sys.exit(1)

    print(f"=== advisor-attribution sweep ({'APPLY' if args.apply else 'DRY RUN'}) ===\n")

    for relpath, old, new in MEMO_EDITS + CODE_EDITS:
        edit(relpath, old, new, args.apply)

    print(("--- APPLIED " if args.apply else "--- WOULD APPLY ") + f"({len(applied)}) ---")
    for a in applied:
        print("  " + a)

    if skipped:
        print(f"\n--- SKIPPED ({len(skipped)}) ---")
        for s in skipped:
            print("  " + s)

    if missed:
        print(f"\n--- NO MATCH, CHECK BY HAND ({len(missed)}) ---")
        for m in missed:
            print("  " + m)

    print("\n--- STILL BY HAND ---")
    for b in [
        "CHANGELOG.md lines 138, 140, 212, 251, 281 — append a dated correction entry; "
        "leave the originals intact as the historical record.",
        "calibration.py:352 and run_mechanism_null*.py:242/216 — hash-bearing. Correct in one "
        "commit that regenerates calibration_manifest.json and mechanism_null.json, with a "
        "changelog note.",
        "Data and Code Availability — recount '11 governing documents' after the manifest rebuild.",
        "References — Dekovic is out of alphabetical order; Bongiorno has no venue; verify the "
        "Kriuk and Pergher 2026 citations.",
        "git rm --cached the correction scripts once you are done with them.",
    ]:
        print("  * " + b)

    if args.apply:
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                           capture_output=True, text=True)
        print("\n--- TESTS --- " + (r.stdout.strip().splitlines() or ["no output"])[-1])
        if r.returncode:
            print("  FAILED. Review with: git diff")


if __name__ == "__main__":
    main()
