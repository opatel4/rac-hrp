"""Invariants for the provenance-tagged test-region lock."""
import json
import os
import pytest

from rac_hrp.backtest.region_lock import TestRegionLock


@pytest.fixture
def lock(tmp_path):
    return TestRegionLock(audit_log_path=tmp_path / "touches.jsonl")


# --- provenance & counting ------------------------------------------------- #

def test_analysis_unlock_is_durable_and_counted(lock):
    lock.unlock("phase 4 pre-registered touch")
    assert lock.analysis_touches() == 1
    events = lock._read_events()
    assert len(events) == 1 and events[0]["provenance"] == "analysis"
    assert events[0]["reason"] == "phase 4 pre-registered touch"


def test_selftest_unlock_is_ephemeral_and_uncounted(lock):
    lock.unlock_for_selftest("unit test")           # we ARE under pytest
    assert lock._unlocked is True                    # region really did open
    assert lock.analysis_touches() == 0              # but nothing durable
    assert lock._read_events() == []


def test_analysis_count_ignores_unit_test_touches(lock):
    lock.unlock_for_selftest("unit test")
    lock.relock()
    lock.unlock("the one real touch")
    assert lock.analysis_touches() == 1              # only the analysis touch


def test_provenance_cannot_default_to_unit_test(lock, monkeypatch):
    # Ordinary code path is unlock(); it is analysis even if pytest is present.
    lock.unlock("some analysis")
    assert lock._read_events()[0]["provenance"] == "analysis"
    # And the guarded self-test path is unreachable outside pytest.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(RuntimeError):
        lock.unlock_for_selftest("pretending to be a test")


# --- durability across "process restart" ----------------------------------- #

def test_events_persist_across_instances(tmp_path):
    path = tmp_path / "touches.jsonl"
    TestRegionLock(audit_log_path=path).unlock("touch A")
    # Fresh instance == fresh process for our purposes; _touches resets, the
    # durable count does not.
    reborn = TestRegionLock(audit_log_path=path)
    assert reborn._touches == 0
    assert reborn.analysis_touches() == 1
    reborn.unlock("touch B")
    assert reborn.analysis_touches() == 2


# --- tamper evidence ------------------------------------------------------- #

def test_chain_verifies_and_detects_tampering(tmp_path):
    path = tmp_path / "touches.jsonl"
    lock = TestRegionLock(audit_log_path=path)
    lock.unlock("touch A")
    lock.unlock("touch B")
    lock.verify_chain()                              # clean chain OK

    rows = [json.loads(l) for l in path.read_text().splitlines()]
    rows[0]["reason"] = "edited after the fact"      # silent edit
    path.write_text("\n".join(json.dumps(r, sort_keys=True,
                                         separators=(",", ":")) for r in rows) + "\n")
    with pytest.raises(ValueError):
        TestRegionLock(audit_log_path=path).verify_chain()


def test_chain_detects_deletion(tmp_path):
    path = tmp_path / "touches.jsonl"
    lock = TestRegionLock(audit_log_path=path)
    lock.unlock("touch A")
    lock.unlock("touch B")
    rows = path.read_text().splitlines()
    path.write_text(rows[1] + "\n")                  # drop the first event
    with pytest.raises(ValueError):
        TestRegionLock(audit_log_path=path).verify_chain()


# --- existing behaviour preserved ------------------------------------------ #

def test_check_gate_matches_lock_state(lock):
    with pytest.raises(PermissionError):
        lock.check()                                 # locked at construction
    lock.unlock_for_selftest("unit test")
    lock.check()                                      # unlocked -> access allowed
    lock.relock()
    with pytest.raises(PermissionError):
        lock.check()                                  # locked again after relock


def test_relock_does_not_erase_durable_history(lock):
    lock.unlock("real touch")
    lock.relock()
    assert lock.analysis_touches() == 1              # history survives relock


def test_lock_implementation_is_not_shadowed():
    """A full-tree copy restoring the old in-folds TestRegionLock would silently
    revert the durable audit log; the suite stays green because the reverted
    state is internally consistent. This makes that revert a red test."""
    from rac_hrp.backtest.folds import TestRegionLock as Shimmed
    assert Shimmed.__module__ == "rac_hrp.backtest.region_lock"
    assert hasattr(Shimmed, "unlock_for_selftest")
    assert hasattr(Shimmed, "analysis_touches")
