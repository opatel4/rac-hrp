#!/usr/bin/env python3
"""
RAC-HRP housekeeping pass.

Performs every mechanical repository change that can be made safely and
deterministically. Where a target string is uncertain, REPORTS the location
instead of guessing. Idempotent: safe to run twice.

Run from the repository root:
    python rac_hrp_housekeeping.py
    python rac_hrp_housekeeping.py --apply      # actually write changes

Default is a dry run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path.cwd()
DOWNLOADS = pathlib.Path.home() / "Downloads"
PREREG_DIR = ROOT / "docs" / "protocol" / "phase2_prereg"

report: list[str] = []
manual: list[str] = []


def log(msg: str) -> None:
    report.append(msg)
    print(msg)


def needs_hand(msg: str) -> None:
    manual.append(msg)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. Commit the Phase 2 pre-registration set
# ---------------------------------------------------------------------------
def stage_prereg(apply: bool) -> None:
    docx = sorted(DOWNLOADS.glob("RAC-HRP_Phase2_PreRegistration*.docx"))
    if not docx:
        needs_hand("No pre-registration .docx found in ~/Downloads.")
        return

    txt = sorted((ROOT / "outputs" / "prereg").glob("*.txt"))
    if not txt:
        needs_hand("No extracted .txt in outputs/prereg/. Re-run the extraction first.")

    log(f"[prereg] {len(docx)} .docx, {len(txt)} .txt to stage into {PREREG_DIR.relative_to(ROOT)}")
    if not apply:
        return

    PREREG_DIR.mkdir(parents=True, exist_ok=True)
    for f in docx + txt:
        dest = PREREG_DIR / f.name
        if dest.exists() and sha256(dest) == sha256(f):
            continue
        shutil.copy2(f, dest)

    sums = PREREG_DIR / "SHA256SUMS.txt"
    lines = [f"{sha256(p)}  {p.name}" for p in sorted(PREREG_DIR.iterdir())
             if p.name != "SHA256SUMS.txt" and p.is_file()]
    sums.write_text("\n".join(lines) + "\n")
    log(f"[prereg] wrote {sums.relative_to(ROOT)} ({len(lines)} entries)")

    freeze = PREREG_DIR / "RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx"
    if freeze.exists():
        log(f"[prereg] rev5 SHA-256: {sha256(freeze)}")


# ---------------------------------------------------------------------------
# 2. Approval attestation template
# ---------------------------------------------------------------------------
ATTESTATION = """# Phase 2 Pre-Registration — Approval Attestation

This attestation records advisor approval of the frozen Phase 2 pre-registration. It exists so a
replicator can verify the approval claim made in the manuscript without access to private
correspondence.

| Field | Value |
|---|---|
| Document | `RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx` |
| SHA-256 | `{sha}` |
| Approval date and time | [TO BE COMPLETED] |
| Medium of approval | dated correspondence (not signature) |
| Authorisation decision | [TO BE COMPLETED] |

The approver confirms that approval of the above document preceded any Phase 2 gate
implementation. The earliest Phase 2 implementation commit is `f6e09dc` (2026-08-20 22:46 EDT);
the cluster-informativeness statistic (`a25cd87`) and calibration runner (`633ce27`) followed on
2026-08-21.

The underlying correspondence is retained privately. Its hash, or a redacted transcript, may be
published at the approver's discretion.

Approver name: ______________________________

Signature: __________________________________

Date: _______________________________________
"""


def write_attestation(apply: bool) -> None:
    freeze = PREREG_DIR / "RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx"
    dest = PREREG_DIR / "APPROVAL_ATTESTATION.md"
    if dest.exists():
        log("[attestation] already exists, leaving untouched")
        return
    if not freeze.exists():
        needs_hand("Attestation not written: rev5 not yet staged.")
        return
    log(f"[attestation] would write {dest.relative_to(ROOT)}")
    if apply:
        dest.write_text(ATTESTATION.format(sha=sha256(freeze)))


# ---------------------------------------------------------------------------
# 3. gate_v2.py docstring: "signed" -> "approved"
# ---------------------------------------------------------------------------
def fix_gate_v2(apply: bool) -> None:
    p = ROOT / "rac_hrp" / "nulls" / "gate_v2.py"
    if not p.exists():
        needs_hand(f"{p} not found.")
        return
    t = p.read_text()
    old = "authorized by the signed protocol (rev.2)"
    new = "authorized by the approved protocol (rev.2; approval by dated correspondence)"
    if new in t:
        log("[gate_v2] already corrected")
        return
    if t.count(old) != 1:
        needs_hand(f"gate_v2.py: expected 1 occurrence of the docstring phrase, found {t.count(old)}")
        return
    log("[gate_v2] would replace 'signed protocol' -> 'approved protocol'")
    if apply:
        p.write_text(t.replace(old, new))


# ---------------------------------------------------------------------------
# 4. Report remaining "countersigned" / "signed" occurrences
# ---------------------------------------------------------------------------
def audit_countersigned() -> None:
    pat = re.compile(r"countersign|signed protocol", re.I)
    hits: list[str] = []
    skip = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"}
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(s in p.parts for s in skip):
            continue
        if p.suffix.lower() not in {".py", ".md", ".tex", ".json", ".txt", ".cff"}:
            continue
        if "phase2_prereg" in p.parts:
            continue
        try:
            for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if pat.search(line):
                    hits.append(f"  {p.relative_to(ROOT)}:{i}: {line.strip()[:110]}")
        except Exception:
            continue
    if hits:
        needs_hand("Review these 'countersigned'/'signed' occurrences by hand:\n" + "\n".join(hits))
    else:
        log("[countersigned] no remaining occurrences outside the prereg directory")


# ---------------------------------------------------------------------------
# 5. null_gate_sided in the freeze manifest
# ---------------------------------------------------------------------------
def check_freeze_manifest() -> None:
    p = ROOT / "results" / "freeze_manifest.json"
    if not p.exists():
        needs_hand("results/freeze_manifest.json not found.")
        return
    data = json.loads(p.read_text())
    if "null_gate_sided" in data or "null_gate_sided" in data.get("config_json", ""):
        log("[freeze_manifest] null_gate_sided already recorded")
        return
    needs_hand(
        "results/freeze_manifest.json does not record `null_gate_sided`, and the v1 verdict "
        "depends on it (gate.py:282). Confirm the configured value, then add it to the manifest "
        "and to the embedded config_json. Do NOT edit the archived copy under archive/; issue the "
        "change against results/ and note it in the changelog."
    )


# ---------------------------------------------------------------------------
# 6. gate.py one-sided/two-sided language
# ---------------------------------------------------------------------------
def audit_gate_sidedness() -> None:
    p = ROOT / "rac_hrp" / "nulls" / "gate.py"
    if not p.exists():
        needs_hand(f"{p} not found.")
        return
    lines = p.read_text().splitlines()
    flagged = [f"  gate.py:{i}: {l.strip()[:110]}"
               for i, l in enumerate(lines, 1)
               if "abs(mean)" in l or "|dSharpe|" in l]
    if flagged:
        needs_hand(
            "gate.py describes the equivalence rule in two-sided terms while the configured "
            "behaviour is one-sided. Reconcile these by hand (no verdict changes; changelog "
            "entry required):\n" + "\n".join(flagged)
        )


# ---------------------------------------------------------------------------
# 7. Rebuild the reproducibility manifest, run tests
# ---------------------------------------------------------------------------
def rebuild_and_test(apply: bool) -> None:
    if not apply:
        log("[verify] would run manifest builder and full test suite")
        return
    builder = ROOT / "scripts" / "build_reproducibility_manifest.py"
    if builder.exists():
        r = subprocess.run([sys.executable, str(builder)], capture_output=True, text=True)
        log(f"[verify] manifest builder exit {r.returncode}")
        if r.returncode:
            log(r.stderr[-1500:])
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                       capture_output=True, text=True)
    log("[verify] " + (r.stdout.strip().splitlines() or ["no output"])[-1])
    if r.returncode:
        needs_hand("TEST SUITE FAILED — stop and investigate before committing anything.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    if not (ROOT / "rac_hrp").is_dir():
        sys.exit("Run this from the repository root.")

    mode = "APPLY" if args.apply else "DRY RUN"
    log(f"=== RAC-HRP housekeeping ({mode}) ===\n")

    stage_prereg(args.apply)
    write_attestation(args.apply)
    fix_gate_v2(args.apply)
    audit_countersigned()
    check_freeze_manifest()
    audit_gate_sidedness()
    rebuild_and_test(args.apply)

    print("\n=== NEEDS A HUMAN ===")
    if manual:
        for m in manual:
            print("\n* " + m)
    else:
        print("Nothing.")

    print("\n=== NOT AUTOMATED (paste from the manuscript-edits document) ===")
    for item in [
        "§4.5 Phase 0.5 subsection + four line edits",
        "§6.3 and Contribution 4 — Molyboga reframe",
        "§4.1 — five-lag identity paragraphs",
        "§7.2 — horizon alignment, plus renumbering of §7.3–§7.5",
        "§6.2 — corrected firing-rate ordering",
        "Bibliography — Nikolopoulos arXiv:2604.15531",
        "Table 4 — burst-count column (confirm modal gap is 1 first)",
    ]:
        print("  - " + item)


if __name__ == "__main__":
    main()
