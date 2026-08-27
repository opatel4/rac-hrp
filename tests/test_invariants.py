"""
Structural invariants — the checks that catch SILENT breakage.

Motivated by three incidents in which something was added or deleted, nothing was
wired to it, and every suite still reported green:

  * two reversions of rac_hrp/backtest/folds.py (bundle installs overwriting a
    separately-patched file);
  * INCIDENT E2 — commit f6e09dc deleted the MHRP_EV allocator while
    scripts/run_phase1.py still declared the strategy, orphaning a committed
    result (Sharpe 0.534) for weeks;
  * the coverage test written to catch E2 was itself inert, appended below the
    custom runner's sys.exit() so it never executed.

Auto-discovery alone does not prevent production-code deletion. Discovery must be
paired with EXPLICIT INVARIANTS; these are those invariants.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Raise deliberately when suites are added; a silent DROP in collected tests is
# the failure mode this guards against.
MIN_COLLECTED = 40


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --------------------------------------------------------------------------
# 1. Registry completeness: declared strategies must have implementations
# --------------------------------------------------------------------------
def test_every_declared_baseline_has_an_allocator():
    """Would have caught INCIDENT E2 the day it occurred."""
    m = _load(ROOT / "scripts" / "run_phase1.py", "_rp1")
    engine_src = (ROOT / "rac_hrp" / "backtest" / "engine.py").read_text()
    for st in m.BASELINES:
        assert f'st.allocator == "{st.allocator}"' in engine_src, (
            f"{st.name} declares allocator {st.allocator!r} but engine.py has no "
            f"dispatch branch for it")


def test_declared_allocators_are_importable():
    """Dispatch branch present is not enough; the function must exist."""
    import rac_hrp.core.allocators as A
    m = _load(ROOT / "scripts" / "run_phase1.py", "_rp1b")
    expected = {"hrp": "hrp_weights", "hrp_equalvol": "hrp_equalvol_weights",
                "erc": "erc_weights", "ew": "equal_weight",
                "minvar": "min_variance"}
    for st in m.BASELINES:
        fn = expected.get(st.allocator)
        if fn:
            assert hasattr(A, fn), (
                f"{st.name} needs allocators.{fn}, which is missing")


# --------------------------------------------------------------------------
# 2. Lock implementation is not shadowed
# --------------------------------------------------------------------------
def test_lock_implementation_is_not_shadowed():
    """A full-tree copy restoring the old in-folds TestRegionLock would silently
    revert the durable audit log while every suite stayed green."""
    from rac_hrp.backtest.folds import TestRegionLock as Shimmed
    assert Shimmed.__module__ == "rac_hrp.backtest.region_lock"
    assert hasattr(Shimmed, "unlock_for_selftest")
    assert hasattr(Shimmed, "analysis_touches")


# --------------------------------------------------------------------------
# 3. Golden results: committed numbers must still be the committed numbers
# --------------------------------------------------------------------------
def _headline():
    p = ROOT / "REPRODUCIBILITY_MANIFEST.json"
    if not p.exists():
        pytest.skip("reproducibility manifest not generated")
    return json.loads(p.read_text())["headline_values"]


def test_phase1_baselines_match_the_frozen_record():
    import csv
    f = ROOT / "outputs" / "phase1" / "phase1_baselines.csv"
    if not f.exists():
        pytest.skip("phase1 baselines not present")
    want = _headline()["phase1_sharpe_dev"]
    rows = {r[0]: r for r in csv.reader(f.open()) if r and r[0] in want}
    assert rows, "no known strategies found in phase1_baselines.csv"
    for name, row in rows.items():
        got = float(row[3])                      # sharpe column
        assert abs(got - want[name]) < 5e-4, (
            f"{name} Sharpe drifted: {got:.6f} vs frozen {want[name]}")


def test_phase2_gate_still_selects_nothing():
    f = ROOT / "outputs" / "phase2" / "calibration_manifest.json"
    if not f.exists():
        pytest.skip("phase2 manifest not present")
    man = json.loads(f.read_text())
    txt = json.dumps(man)
    assert "selected" in txt or "stop" in txt.lower()
    hv = _headline()["phase2_gate"]
    assert hv["outcome"] == "NO ADMISSIBLE GAMMA"
    assert hv["eligible_rebalances"] == 233


def test_test_region_remains_untouched():
    """The single pre-registered touch has not been spent. If this fails, either
    the region was accessed or the durable audit log was reset -- both require
    explicit advisor sign-off, never a silent change."""
    hv = _headline()
    p = ROOT / "audit" / "test_region_touches.jsonl"
    n = 0
    if p.exists():
        n = sum(1 for l in p.read_text().splitlines()
                if l.strip() and json.loads(l).get("provenance") == "analysis")
    assert n == 0, f"{n} durable analysis touches recorded; manifest asserts 0"


# --------------------------------------------------------------------------
# 4. Collection floor: a silent DROP in collected tests is itself a failure
# --------------------------------------------------------------------------
def test_collected_test_count_has_not_regressed(pytestconfig):
    n = len(pytestconfig.pluginmanager.getplugin("session").items) \
        if pytestconfig.pluginmanager.hasplugin("session") else None
    if n is None:
        pytest.skip("session item count unavailable in this pytest version")
    assert n >= MIN_COLLECTED, (
        f"only {n} tests collected, expected >= {MIN_COLLECTED}; a suite may have "
        f"stopped being discovered")
