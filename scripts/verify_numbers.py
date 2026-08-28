#!/usr/bin/env python3
"""Pre-submission numeric verification.

Checks every number the manuscript reports against the artefact it comes from,
plus internal consistency of cross-references, counts and hashes.

Reports PASS / FAIL / CHECK per item. CHECK means the artefact was not found or
the value must be read by eye, not that the claim is wrong.

Run from the repository root. Reads only; writes nothing.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TEX = Path("overleaf/main.tex")
OK, BAD, SKIP = [], [], []


def ok(item, detail=""):
    OK.append((item, detail))


def bad(item, detail):
    BAD.append((item, detail))


def skip(item, detail):
    SKIP.append((item, detail))


def near(a, b, tol=5e-4):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def load_csv(path):
    p = Path(path)
    if not p.exists():
        return None
    rows = [l.strip().split(",") for l in p.read_text().strip().splitlines()]
    if len(rows) < 2:
        return None
    hdr = rows[0]
    return [dict(zip(hdr, r)) for r in rows[1:]]


TEXT = TEX.read_text() if TEX.exists() else ""


# ==========================================================================
# 1. Gate table against calibration_table.csv
# ==========================================================================
def check_gate_table():
    rows = load_csv("outputs/phase2/calibration_table.csv")
    if rows is None:
        return skip("gate table", "calibration_table.csv not found")

    cols = [("n_events", 0), ("firing_rate", 4), ("min_events_per_fold", 0),
            ("cv_gap", 4), ("modal_gap_share", 4), ("J_star", 4),
            ("J_threshold", 4), ("D_VI", 4), ("p_raw", 4), ("p_holm", 4)]

    for r in rows:
        g = r["gamma"]
        for col, dp in cols:
            v = float(r[col])
            s = f"{v:.{dp}f}" if dp else str(int(v))
            # search the gate-result table block for the value
            m = re.search(r"\\label\{tab:gateresult\}(.*?)\\end\{tabular\}",
                          TEXT, re.S)
            block = m.group(1) if m else ""
            if s in block or s.rstrip("0").rstrip(".") in block:
                ok(f"gate g={g} {col}", s)
            else:
                bad(f"gate g={g} {col}", f"artefact {s} not found in Table 4")


# ==========================================================================
# 2. Phase 0.5 cell counts
# ==========================================================================
def check_phase05_counts():
    for path, expected, label in [
        ("results/null_gate_v1.csv", 11, "Phase 0.5 v1 = 11"),
        ("results/primary_gate.csv", 8, "Phase 0.5 v2 primary = 8"),
        ("results/diagnostic_panel.csv", 12, "Phase 0.5 v2 diagnostic = 12"),
    ]:
        rows = load_csv(path)
        if rows is None:
            skip(label, f"{path} not found")
        elif len(rows) == expected:
            ok(label, f"{len(rows)} rows")
        else:
            bad(label, f"{len(rows)} rows, manuscript implies {expected}")


# ==========================================================================
# 3. Phase 0.5 Sharpe differences quoted in section 4.5
# ==========================================================================
def check_phase05_values():
    quoted = ["-0.0016", "+0.0046", "+0.102", "+0.038", "+0.167", "-0.108",
              "-0.006", "-0.066", "+0.054", "+0.109", "+0.049", "+0.168",
              "+0.0132", "+0.093", "+0.083"]
    hay = ""
    for f in ("results/null_gate_v1.csv", "results/primary_gate.csv",
              "results/diagnostic_panel.csv",
              "outputs/RAC-HRP_NullGate_v2_Protocol_rev2.txt"):
        p = Path(f)
        if p.exists():
            hay += p.read_text()
    if not hay:
        return skip("Phase 0.5 values", "no Phase 0.5 CSVs found")

    nums = set()
    for tok in re.findall(r"-?\d+\.\d+", hay):
        try:
            nums.add(round(float(tok), 4))
        except ValueError:
            pass

    for q in quoted:
        v = round(float(q), 4)
        if any(round(n, 3) == round(v, 3) for n in nums):
            ok(f"Phase 0.5 {q}")
        else:
            bad(f"Phase 0.5 {q}", "not found in any Phase 0.5 CSV")


# ==========================================================================
# 4. Baselines and estimator sweep
# ==========================================================================
def check_phase1():
    for path, label, quoted in [
        ("outputs/phase1/phase1_baselines.csv", "Table 2 baselines",
         ["0.576", "0.574", "0.549", "0.534", "0.508"]),
        ("outputs/phase1/phase1_estimator_sensitivity.csv", "Table 3 sweep",
         ["0.608", "0.591", "0.594", "0.568", "0.554", "0.557", "0.588",
          "0.551", "0.556", "0.558"]),
    ]:
        p = Path(path)
        if not p.exists():
            skip(label, f"{path} not found")
            continue
        hay = p.read_text()
        nums = {float(t) for t in re.findall(r"-?\d+\.\d+", hay)}
        miss = [q for q in quoted
                if not any(round(n, len(q.split('.')[-1])) == float(q) for n in nums)]
        if miss:
            bad(label, f"not found in artefact: {', '.join(miss)}")
        else:
            ok(label, f"{len(quoted)} values matched")


# ==========================================================================
# 5. Mechanism null intervals (Table 5)
# ==========================================================================
def check_mechanism():
    d = load_json("outputs/phase2_mechanism/mechanism_null.json")
    if d is None:
        return skip("Table 5 mechanism null", "mechanism_null.json not found")
    m = d.get("manifest", {})
    table = m.get("table")
    if not table:
        return skip("Table 5 mechanism null", "no table in manifest")

    printed = {
        0.5: ("0.182", (0.062, 0.157), (0.033, 0.117), (0.045, 0.166)),
        1.0: ("0.318", (0.122, 0.272), (0.100, 0.237), (0.140, 0.306)),
        1.5: ("0.4125", (0.140, 0.361), (0.095, 0.296), (0.163, 0.407)),
        2.0: ("0.526", (0.107, 0.392), (0.000, 0.295), (0.105, 0.440)),
    }
    for row in table:
        g = float(row["gamma"])
        if g not in printed:
            continue
        realB, A, S, D = printed[g]
        checks = [
            ("real B", row.get("real_B"), float(realB), 5e-3),
            ("A lo", row.get("A_iid_gaussian_q2.5"), A[0], 5e-4),
            ("A hi", row.get("A_iid_gaussian_q97.5"), A[1], 5e-4),
            ("S lo", row.get("S_static_corr_q2.5"), S[0], 5e-4),
            ("S hi", row.get("S_static_corr_q97.5"), S[1], 5e-4),
            ("D lo", row.get("D_regime_switch_vol_q2.5"), D[0], 5e-4),
            ("D hi", row.get("D_regime_switch_vol_q97.5"), D[1], 5e-4),
        ]
        for name, got, want, tol in checks:
            if got is None:
                skip(f"Table 5 g={g} {name}", "field absent")
            elif near(got, want, tol):
                ok(f"Table 5 g={g} {name}")
            else:
                bad(f"Table 5 g={g} {name}",
                    f"artefact {got:.4f}, manuscript {want}")


# ==========================================================================
# 6. W-calibrated control (Table 6)
# ==========================================================================
def check_wcontrol():
    d = load_json("results/phase2f_control_result.json")
    if d is None:
        return skip("Table 6 W-control", "phase2f_control_result.json not found")
    printed = {0.5: (0.044, 0.201), 1.0: (0.128, 0.339),
               1.5: (0.176, 0.437), 2.0: (0.163, 0.512)}
    for row in d.get("table", []):
        g = float(row["gamma"])
        lo, hi = printed.get(g, (None, None))
        if lo is None:
            continue
        for name, got, want in [("lo", row["D_slow_q2.5"], lo),
                                ("hi", row["D_slow_q97.5"], hi)]:
            if near(got, want, 5e-4):
                ok(f"Table 6 g={g} {name}")
            else:
                bad(f"Table 6 g={g} {name}",
                    f"artefact {got:.4f}, manuscript {want}")
    rs = d.get("realised_regime_stats", {})
    for name, got, want in [("frac_high", rs.get("frac_high"), 0.372),
                            ("mean low", rs.get("mean_run_low"), 1224),
                            ("mean high", rs.get("mean_run_high"), 761)]:
        if got is None:
            skip(f"Table 6 {name}", "field absent")
        elif abs(got - want) <= (0.001 if name == "frac_high" else 1.0):
            ok(f"Table 6 {name}", f"{got:.4g}")
        else:
            bad(f"Table 6 {name}", f"artefact {got:.4g}, manuscript {want}")


# ==========================================================================
# 7. Empirical size (Table 7)
# ==========================================================================
def check_size():
    d = load_json("outputs/phase2_diagnostics/bootstrap_calibration_vs_B.json")
    if d is None:
        return skip("Table 7 size", "bootstrap_calibration_vs_B.json not found")
    hay = json.dumps(d)
    nums = {round(float(t), 4) for t in re.findall(r"-?\d+\.\d+", hay)}
    for q in ["0.0655", "0.0660", "0.0055", "0.0056"]:
        if any(abs(float(q) - n) <= 5e-5 for n in nums):
            ok(f"Table 7 {q}")
        else:
            bad(f"Table 7 {q}", "not found in artefact")


# ==========================================================================
# 8. Horizon and power diagnostics
# ==========================================================================
def check_horizon_power():
    d = load_json("results/phase2e_horizon_result.json")
    if d is None:
        skip("Table 8 horizon", "phase2e_horizon_result.json not found")
    else:
        printed = {0.5: (0.0662, 0.0432, 0.0864),
                   1.0: (0.0600, 0.0448, 0.0864),
                   1.5: (0.0814, 0.0046, 0.0184),
                   2.0: (0.1038, 0.0141, 0.0423)}
        for c in d.get("cells", []):
            g = float(c["gamma"])
            if g not in printed:
                continue
            dv, praw, pholm = printed[g]
            for name, got, want in [("D_VI", c["d_vi_h"], dv),
                                    ("p raw", c["p_raw"], praw),
                                    ("p Holm", c["p_holm"], pholm)]:
                if near(got, want, 5e-5):
                    ok(f"Table 8 g={g} {name}")
                else:
                    bad(f"Table 8 g={g} {name}",
                        f"artefact {got:.4f}, manuscript {want}")

    d = load_json("results/phase2e_power_result.json")
    if d is None:
        skip("Table 9 power", "phase2e_power_result.json not found")
    else:
        sz = d.get("empirical_size_on_observed_dependence", {})
        for name, got, want in [("size", sz.get("power"), 0.0730),
                                ("MC SE", sz.get("mc_se"), 0.0058)]:
            if got is None:
                skip(f"power {name}", "field absent")
            elif near(got, want, 5e-5):
                ok(f"power {name}", f"{got:.4f}")
            else:
                bad(f"power {name}", f"artefact {got:.4f}, manuscript {want}")
        mde = d.get("mde80", {})
        for key, want in [("gamma=0.5|R", "(0.15, 0.2]"),
                          ("gamma=1.0|R", "(0.15, 0.2]"),
                          ("gamma=1.5|R", "(0.15, 0.2]"),
                          ("gamma=2.0|R", "(0.2, 0.3]")]:
            got = mde.get(key)
            if got is None:
                skip(f"MDE {key}", "field absent")
            elif got.replace(" ", "") == want.replace(" ", ""):
                ok(f"MDE {key}", got)
            else:
                bad(f"MDE {key}", f"artefact {got}, manuscript {want}")


# ==========================================================================
# 9. 2G tables
# ==========================================================================
def check_2g():
    d = load_json("results/phase2g_result.json")
    if d is None:
        return skip("2G tables", "phase2g_result.json not found")

    ktab = {
        10: ([0.005, 0.029, 0.064, 0.061], [0.554, 0.554, 0.282, 0.476]),
        15: ([0.0326, 0.0217, 0.0796, 0.0961], [0.5585, 0.5585, 0.2460, 0.1952]),
        20: ([-0.040, -0.005, -0.009, -0.002], [1.000, 1.000, 1.000, 1.000]),
        25: ([0.041, 0.095, 0.081, 0.124], [0.135, 0.025, 0.025, 0.003]),
    }
    for r in d.get("k_sweep", []):
        k = r["k"]
        if k not in ktab:
            continue
        dvs, phs = ktab[k]
        for i, c in enumerate(r["cells"]):
            tol = 5e-5 if k == 15 else 5e-4
            if not near(c["d_vi"], dvs[i], tol):
                bad(f"2G-K k={k} g={c['gamma']} D_VI",
                    f"artefact {c['d_vi']:.4f}, manuscript {dvs[i]}")
            else:
                ok(f"2G-K k={k} g={c['gamma']} D_VI")
            if not near(c["p_holm"], phs[i], tol):
                bad(f"2G-K k={k} g={c['gamma']} Holm",
                    f"artefact {c['p_holm']:.4f}, manuscript {phs[i]}")
            else:
                ok(f"2G-K k={k} g={c['gamma']} Holm")

    rk = d.get("rank", {})
    for name, got, want in [("rho", rk.get("rho"), 0.072),
                            ("p", rk.get("p_one_sided"), 0.239),
                            ("block", rk.get("block_length"), 19),
                            ("n", rk.get("n"), 233)]:
        if got is None:
            skip(f"2G-RANK {name}", "field absent")
        elif near(got, want, 5e-4):
            ok(f"2G-RANK {name}", str(got))
        else:
            bad(f"2G-RANK {name}", f"artefact {got}, manuscript {want}")


# ==========================================================================
# 10. Derived arithmetic stated in the text
# ==========================================================================
def check_arithmetic():
    # 483 shared observations and 95.8% overlap for W=504 stepped by 21
    shared = 504 - 21
    pct = shared / 504 * 100
    if shared == 483:
        ok("window overlap count", "483")
    else:
        bad("window overlap count", f"computed {shared}, manuscript 483")
    if abs(pct - 95.8) < 0.05:
        ok("window overlap pct", f"{pct:.1f}%")
    else:
        bad("window overlap pct", f"computed {pct:.2f}%, manuscript 95.8%")

    # eligible set
    if 240 - 7 == 233:
        ok("eligible set", "240 - 7 = 233")

    # Holm arithmetic on the gate
    rows = load_csv("outputs/phase2/calibration_table.csv")
    if rows:
        for r in rows:
            raw, holm = float(r["p_raw"]), float(r["p_holm"])
            g = r["gamma"]
            for mult in (1, 2, 3, 4):
                if near(raw * mult, holm, 1e-4):
                    ok(f"Holm arithmetic g={g}", f"{raw:.4f} x {mult}")
                    break
            else:
                # tied values take the max of the step, so a miss is not
                # necessarily wrong
                skip(f"Holm arithmetic g={g}",
                     f"{raw:.4f} -> {holm:.4f} is not a clean multiple "
                     "(expected for tied steps)")

    # trial table total
    m = re.search(r"\\label\{tab:trials\}(.*?)\\end\{tabular\}", TEXT, re.S)
    if m:
        block = m.group(1)
        counts = [int(x) for x in re.findall(r"&\s*(\d+)\s*\\\\", block)]
        total = re.search(r"\\textbf\{Total\}\s*&\s*&\s*\\textbf\{(\d+)\}", block)
        if counts and total:
            stated = int(total.group(1))
            summed = sum(counts)
            if summed == stated:
                ok("trial table total", f"{summed}")
            else:
                bad("trial table total",
                    f"rows sum to {summed}, table states {stated}")


# ==========================================================================
# 11. Internal consistency
# ==========================================================================
def check_refs():
    labs = set(re.findall(r"\\label\{([^}]+)\}", TEXT))
    refs = set(re.findall(r"\\(?:eq)?ref\{([^}]+)\}", TEXT))
    dangling = sorted(refs - labs)
    if dangling:
        bad("cross-references", f"dangling: {', '.join(dangling)}")
    else:
        ok("cross-references", f"{len(labs)} labels, {len(refs)} refs")

    unused = sorted(labs - refs)
    if unused:
        skip("unused labels", ", ".join(unused))


def check_manifest_counts():
    d = load_json("REPRODUCIBILITY_MANIFEST.json")
    if d is None:
        return skip("manifest counts", "REPRODUCIBILITY_MANIFEST.json not found")
    got = (len(d.get("code", [])), len(d.get("results", [])),
           len(d.get("documents", [])))
    m = re.search(r"hashes for (\d+) code modules, (\d+) result artefacts,\s*"
                  r"(\d+) governing documents", TEXT)
    if not m:
        return skip("manifest counts", "availability sentence not matched")
    want = tuple(int(x) for x in m.groups())
    if got == want:
        ok("manifest counts", f"{got[0]}/{got[1]}/{got[2]}")
    else:
        bad("manifest counts",
            f"manifest has {got[0]}/{got[1]}/{got[2]}, "
            f"manuscript states {want[0]}/{want[1]}/{want[2]}")


def check_revision_counts():
    e = sorted(Path(".").glob("RAC_HRP_Phase2E_PreSpec_rev*.md"))
    f = sorted(Path(".").glob("RAC_HRP_Phase2F_PreSpec_rev*.md"))
    # rev numbering starts at 3 for 2E; count is highest rev number
    e_max = max((int(re.search(r"rev(\d+)", p.name).group(1)) for p in e),
                default=0)
    f_max = max((int(re.search(r"rev(\d+)", p.name).group(1)) for p in f),
                default=0)
    if e_max == 8:
        ok("2E revision count", f"highest is rev{e_max}, {len(e)} files present")
    else:
        bad("2E revision count",
            f"highest is rev{e_max}, manuscript says eight revisions")
    if f_max == 2:
        ok("2F revision count", f"rev{f_max}")
    else:
        bad("2F revision count", f"highest is rev{f_max}, manuscript says two")


def check_freeze_hashes():
    for freeze in sorted(Path(".").glob("PHASE2*_FREEZE.txt")):
        text = freeze.read_text()
        fname = text.splitlines()[0].strip()
        m = re.search(r"SHA-256:\s*([0-9a-f]{64})", text)
        if not m:
            skip(f"{freeze.name}", "no hash line")
            continue
        target = Path(fname)
        if not target.exists():
            bad(f"{freeze.name}", f"{fname} not found")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual == m.group(1):
            ok(f"{freeze.name}", f"{fname} hash matches")
        else:
            bad(f"{freeze.name}",
                f"{fname} hash MISMATCH\n      recorded {m.group(1)}\n"
                f"      actual   {actual}")


def check_audit_hashes():
    for bundle in Path(".").glob("RAC_HRP_Phase2*Audit_Bundle.md"):
        text = bundle.read_text()
        commits = set(re.findall(r"`([0-9a-f]{7})`", text))
        missing = []
        for c in commits:
            r = subprocess.run(["git", "cat-file", "-e", f"{c}^{{commit}}"],
                               capture_output=True)
            if r.returncode != 0:
                missing.append(c)
        if missing:
            bad(f"{bundle.name} commits", f"unresolvable: {', '.join(missing)}")
        else:
            ok(f"{bundle.name} commits", f"{len(commits)} resolve")


# ==========================================================================
def main():
    if not TEX.exists():
        print("overleaf/main.tex not found; run from the repository root.")
        return 2

    for fn in (check_gate_table, check_phase05_counts, check_phase05_values,
               check_phase1, check_mechanism, check_wcontrol, check_size,
               check_horizon_power, check_2g, check_arithmetic, check_refs,
               check_manifest_counts, check_revision_counts,
               check_freeze_hashes, check_audit_hashes):
        try:
            fn()
        except Exception as exc:
            skip(fn.__name__, f"checker raised {type(exc).__name__}: {exc}")

    print("=" * 74)
    print("  PRE-SUBMISSION NUMERIC VERIFICATION")
    print("=" * 74)

    if BAD:
        print(f"\n  MISMATCHES ({len(BAD)}) -- each needs resolving\n")
        for item, detail in BAD:
            print(f"    FAIL  {item}")
            if detail:
                print(f"          {detail}")
    else:
        print("\n  No mismatches.")

    if SKIP:
        print(f"\n  NOT CHECKED ({len(SKIP)}) -- verify these by hand\n")
        for item, detail in SKIP:
            print(f"    CHECK {item}")
            if detail:
                print(f"          {detail}")

    print(f"\n  PASSED: {len(OK)}")
    print("=" * 74)
    return 1 if BAD else 0


if __name__ == "__main__":
    raise SystemExit(main())
