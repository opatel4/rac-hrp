"""
Build the RAC-HRP reproducibility manifest.

Captures, at the current commit, everything needed to reproduce every reported
number: code hashes, data checksums, environment, result artefacts, and the
governing frozen documents. Run this BEFORE any engineering migration (pytest,
refactors) so the scientific outputs are pinned to a verifiable state and later
churn cannot blur their provenance.

    python scripts/build_reproducibility_manifest.py

Writes REPRODUCIBILITY_MANIFEST.json and REPRODUCIBILITY_MANIFEST.md.
"""
from __future__ import annotations

import hashlib, json, os, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Modules that produced at least one reported number.
CODE = [
    "rac_hrp/config.py",
    "rac_hrp/core/covariance.py",
    "rac_hrp/core/covariance_ew.py",
    "rac_hrp/core/allocators.py",
    "rac_hrp/core/clustering.py",
    "rac_hrp/core/pca_mp.py",
    "rac_hrp/backtest/engine.py",
    "rac_hrp/backtest/folds.py",
    "rac_hrp/backtest/region_lock.py",
    "rac_hrp/backtest/metrics.py",
    "rac_hrp/data/panel.py",
    "rac_hrp/data/universe.py",
    "rac_hrp/nulls/environments.py",
    "rac_hrp/nulls/environments_static.py",
    "rac_hrp/phase2/config.py",
    "rac_hrp/phase2/stats.py",
    "rac_hrp/phase2/calibration.py",
    "scripts/run_phase05.py",
    "scripts/run_phase1.py",
    "scripts/run_phase2.py",
    "scripts/run_mechanism_null.py",
    "scripts/run_mechanism_null_parallel.py",
    "scripts/diagnose_modal_gap_null.py",
    "scripts/diag_bootstrap_calibration_B.py",
    "tests/test_phase05.py",
    "tests/test_phase2_stats.py",
    "tests/test_covariance_ew.py",
    "tests/test_region_lock.py",
    "tests/test_invariants.py",
    "tests/conftest.py",
    # --- Phase 2E / 2F / 2G post-gate diagnostics ---
    "rac_hrp/phase2/horizon.py",
    "rac_hrp/phase2/power.py",
    "scripts/run_phase2e_horizon.py",
    "scripts/run_phase2e_power.py",
    "scripts/run_phase2e_power_parallel.py",
    "scripts/run_phase2f_control.py",
    "scripts/run_phase2g.py",
    "scripts/explore_power_construction.py",   # EXPLORATORY, not a result
]

RESULTS = [
    "outputs/phase1/phase1_baselines.csv",
    "outputs/phase1/phase1_estimator_sensitivity.csv",
    # --- Phase 0.5 falsification audit ---
    "results/null_gate_v1.csv",
    "results/primary_gate.csv",
    "results/diagnostic_panel.csv",
    "results/replication_sharpe_matrix.csv",
    "outputs/phase2/calibration_manifest.json",
    "outputs/phase2/calibration_table.csv",
    "outputs/phase2_diagnostics/modal_gap_null.json",
    "outputs/phase2_diagnostics/bootstrap_calibration_vs_B.json",
    "outputs/phase2_mechanism/mechanism_null.json",
    # --- Phase 2E / 2F / 2G results ---
    "results/phase2e_horizon_result.json",
    "results/phase2e_power_result.json",
    "results/phase2f_control_result.json",
    "results/phase2g_result.json",
]

DOCS = [
    # --- Phase 2 pre-registration: every revision through the freeze ---
    "outputs/prereg/RAC-HRP_Phase2_PreRegistration.txt",
    "outputs/prereg/RAC-HRP_Phase2_PreRegistration_rev2.txt",
    "outputs/prereg/RAC-HRP_Phase2_PreRegistration_rev3.txt",
    "outputs/prereg/RAC-HRP_Phase2_PreRegistration_rev4.txt",
    "outputs/prereg/RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.txt",
    "RAC_HRP_Phase2_Gate_Result_Memo_v3.md",
    "RAC_HRP_Phase2_rev5_ERRATUM_E1.md",
    "RAC_HRP_Phase2_Reconciliation_111_vs_112.md",
    "RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md",
    "RAC_HRP_Phase2D_Mechanism_Result_Memo.md",
    "RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md",
    "RAC_HRP_Phase1_INCIDENT_E2_deleted_allocator.md",
    "RAC_HRP_Phase1_EWMA_Robustness_Note.md",
    "RAC_HRP_Phase2_Audit_Bundle.md",
    "docs/PRE_REGISTRATION.md",
    "CHANGELOG.md",
    # --- single-author correction and errata ---
    "docs/CORRECTION_NOTICE_single_author.md",
    "RAC_HRP_ERRATUM_E4_advisor_approval.md",
    "RAC_HRP_Phase05_ERRATUM_E3_environment_label.md",
    # --- Phase 2E: eight revisions, superseded ones preserved ---
    "RAC_HRP_Phase2E_PreSpec_rev3.md",
    "RAC_HRP_Phase2E_PreSpec_rev4.md",
    "RAC_HRP_Phase2E_PreSpec_rev5.md",
    "RAC_HRP_Phase2E_PreSpec_rev6.md",
    "RAC_HRP_Phase2E_PreSpec_rev7.md",
    "RAC_HRP_Phase2E_PreSpec_rev8.md",
    "PHASE2E_FREEZE.txt",
    # --- Phase 2F ---
    "RAC_HRP_Phase2F_PreSpec_rev1.md",
    "RAC_HRP_Phase2F_PreSpec_rev2.md",
    "PHASE2F_FREEZE.txt",
    # --- Phase 2G ---
    "RAC_HRP_Phase2G_PreSpec_rev1.md",
    "PHASE2G_FREEZE.txt",
    # --- audit bundle for the post-gate phases ---
    "RAC_HRP_Phase2EFG_Audit_Bundle.md",
]


def sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def hash_group(paths, base=ROOT):
    out = {}
    for rel in paths:
        p = base / rel
        out[rel] = {"sha256": sha256(p),
                    "bytes": p.stat().st_size if p.exists() else None,
                    "present": p.exists()}
    return out


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def main() -> int:
    raw = Path(os.path.expanduser("~/rac_hrp_data/raw"))
    data = {}
    if raw.exists():
        for f in sorted(raw.glob("*.parquet")):
            data[f.name] = {"sha256": sha256(f), "bytes": f.stat().st_size}

    # Ignore this manifest's own output when judging tree cleanliness:
    # the files are written after this check, so they would always appear
    # untracked and the flag could never report clean.
    _self = {"REPRODUCIBILITY_MANIFEST.json", "REPRODUCIBILITY_MANIFEST.md"}
    dirty = "\n".join(
        l for l in (git("status", "--porcelain") or "").splitlines()
        if l.split()[-1] not in _self)
    m = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": ("Pins every reported number to a verifiable state. Generated "
                    "BEFORE engineering migration so later churn cannot blur "
                    "provenance."),
        "git": {"commit": git("rev-parse", "HEAD"),
                "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                "remote": git("config", "--get", "remote.origin.url"),
                "working_tree_clean": (dirty == ""),
                "uncommitted": [l for l in (dirty or "").splitlines()]},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
            "note": ("Single-thread BLAS is the project standard: ~13x faster on "
                     "this workload (100x100 matrices) and verified result-neutral "
                     "(the --quick Phase 2 gate reproduces bit-for-bit under both "
                     "settings). Set at process launch; setting it inside a script "
                     "after numpy import may be too late."),
        },
        "packages": {},
        "data": {"path": str(raw), "files": data,
                 "source": "CRSP via WRDS (user opatel4); CRSP-native large-cap "
                           "universe; vintage ends 2024-12-31"},
        "regions": {"development": "2003-01-08 .. 2022-12-30 (5,031 days)",
                    "test": "TEST_START 2023-01-03 .. 2024-12-31",
                    "test_region_analysis_touches": 0,
                    "test_region_note": ("The single pre-registered test-region "
                                         "touch has NOT been used. No adaptive "
                                         "specification passed the development-stage "
                                         "structural gate, so performance evaluation "
                                         "was conditionally inaccessible by design.")},
        "code": hash_group(CODE),
        "results": hash_group(RESULTS),
        "documents": hash_group(DOCS),
        "headline_values": {
            "phase1_sharpe_dev": {"MinVar": 0.576, "HRP_static": 0.574,
                                  "ERC": 0.549, "MHRP_EV": 0.534, "EW": 0.508},
            "phase2_gate": {"outcome": "NO ADMISSIBLE GAMMA",
                            "eligible_rebalances": 233,
                            "n_events": {"0.5": 149, "1.0": 111,
                                         "1.5": 81, "2.0": 58},
                            "p_raw": {"0.5": 0.2778, "1.0": 0.3523,
                                      "1.5": 0.0846, "2.0": 0.0552},
                            "p_holm": {"0.5": 0.5555, "1.0": 0.5555,
                                       "1.5": 0.2538, "2.0": 0.2208},
                            "bootstrap_seed_base": 20262817,
                            "bootstrap_replicates": 10000},
            "phase2d_mechanism": {"outcome": "2_beyond_regime_free_mechanics"},
            "bootstrap_empirical_size": {"nominal": 0.05, "measured": 0.066,
                                         "stable_across_B": [600, 2000, 10000]},
        },
    }
    for pkg in ("numpy", "pandas", "scipy", "sklearn", "pyarrow"):
        try:
            m["packages"][pkg] = __import__(pkg).__version__
        except Exception:
            m["packages"][pkg] = None

    (ROOT / "REPRODUCIBILITY_MANIFEST.json").write_text(json.dumps(m, indent=2))

    def tbl(group, title):
        rows = [f"### {title}", "", "| file | sha256 (first 16) | bytes |",
                "|---|---|---:|"]
        for k, v in group.items():
            h = (v["sha256"] or "MISSING")[:16]
            rows.append(f"| `{k}` | `{h}` | {v['bytes'] or '-'} |")
        return "\n".join(rows) + "\n"

    md = f"""# RAC-HRP — Reproducibility Manifest

Generated {m['generated_utc']} at commit `{m['git']['commit']}`
(branch `{m['git']['branch']}`, working tree clean: {m['git']['working_tree_clean']}).

Pins every reported number to a verifiable state. Generated **before** engineering
migration (pytest, refactors) so later churn cannot blur the provenance of the
scientific outputs.

## Environment
Python {m['environment']['python']} on {m['environment']['platform']};
numpy {m['packages'].get('numpy')}, pandas {m['packages'].get('pandas')},
scipy {m['packages'].get('scipy')}.

{m['environment']['note']}

## Data
{m['data']['source']}
Path: `{m['data']['path']}`

| file | sha256 (first 16) | bytes |
|---|---|---:|
""" + "\n".join(
        f"| `{k}` | `{v['sha256'][:16]}` | {v['bytes']} |"
        for k, v in m["data"]["files"].items()) + f"""

## Regions
- Development: {m['regions']['development']}
- Test: {m['regions']['test']}
- **Test-region analysis touches: {m['regions']['test_region_analysis_touches']}**

{m['regions']['test_region_note']}

{tbl(m['code'], 'Code')}
{tbl(m['results'], 'Result artefacts')}
{tbl(m['documents'], 'Governing documents')}
"""
    (ROOT / "REPRODUCIBILITY_MANIFEST.md").write_text(md)
    missing = [k for g in (m["code"], m["results"], m["documents"])
               for k, v in g.items() if not v["present"]]
    print(f"commit {m['git']['commit']}  clean={m['git']['working_tree_clean']}")
    print(f"code {len(CODE)}  results {len(RESULTS)}  docs {len(DOCS)}  "
          f"data {len(data)}")
    if missing:
        print("\nMISSING (check paths):")
        for k in missing:
            print("   ", k)
    print("\nwrote REPRODUCIBILITY_MANIFEST.json and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
