"""
Provenance-tagged test-region lock.

Drop-in replacement for the `TestRegionLock` currently in
`rac_hrp/backtest/folds.py`.  Same public surface as before
(`unlock(reason)`, `relock()`, `_unlocked`, the `TEST REGION UNLOCKED`
print), extended so that the audit control is durable and honest:

  * `unlock(reason)`            -> ALWAYS an `analysis` touch.  Writes a
                                   durable, hash-chained event to disk.
                                   This is the number that participates in
                                   single-touch / countersignature reconciliation.

  * `unlock_for_selftest(reason)` -> the ONLY way to produce a `unit_test`
                                   touch.  Guarded: raises unless it is
                                   actually running under pytest.  Ephemeral
                                   (in-memory only) -- pytest runs never write
                                   to the durable log and never move the
                                   analysis count.

Design invariants (see the test module):
  * Provenance FAILS TOWARD `analysis`.  There is no way for an ordinary
    caller to self-declare `unit_test`; the only unit_test path is the
    guarded self-test entrypoint.  A genuine analysis touch that somehow
    runs under pytest is still logged as analysis.
  * The durable log is append-only and hash-chained: deleting, editing, or
    reordering any past event breaks the chain and `verify_chain()` fails.
  * `_touches` remains a per-process diagnostic ONLY.  The audit truth is
    `analysis_touches`, derived from the durable log, and it survives
    process restart.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

# In-repo, version-controlled, and additionally hash-chained.  Analysis
# touches are rare (ideally exactly one, at Phase 4), so committing the log
# after a genuine touch does not create git-hygiene noise -- and unit_test
# touches never write here, so `pytest` runs leave the working tree clean.
# (This is the opposite call from the raw CRSP data, which lives OUTSIDE the
# repo because it is large and churns; the audit log is small, write-rare,
# and we WANT it under version control as a second tamper-evidence layer.)
#
# Anchored to THIS FILE's location, never to the current working directory.
# A cwd-relative path would silently start a second, empty audit log the first
# time an analysis script is launched from anywhere but the repo root -- the
# count would read 1 while the real history sat in another file. That is the
# exact failure this mechanism exists to prevent, so the path is derived from
# rac_hrp/backtest/region_lock.py -> parents[2] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_LOG = REPO_ROOT / "audit" / "test_region_touches.jsonl"

_GENESIS = "0" * 64  # prev_hash of the first event in an empty chain


def _under_pytest() -> bool:
    # PYTEST_CURRENT_TEST is set by pytest *per test*, only during actual test
    # execution -- not merely when pytest happens to be importable in the env.
    # Checking this (rather than `import pytest` / sys.modules) is what keeps an
    # analysis script that runs in a pytest-installed conda env from being
    # misclassified.
    return "PYTEST_CURRENT_TEST" in os.environ


def _git_info(cwd: Path | None = None) -> tuple[str | None, bool | None]:
    """(commit_hash, dirty).  Degrades to (None, None) outside a git repo."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd, capture_output=True, text=True, check=True,
        ).stdout.strip()
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd, capture_output=True, text=True, check=True,
        ).stdout
        return commit, bool(porcelain.strip())
    except Exception:
        return None, None


def _event_hash(event: dict) -> str:
    """SHA-256 over the canonical event *excluding* its own event_hash field."""
    payload = {k: v for k, v in event.items() if k != "event_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class TouchEvent:
    touch_id: int
    timestamp: str
    provenance: str          # only ever "analysis" in the durable log
    reason: str
    git_commit: str | None
    git_dirty: bool | None
    prev_hash: str
    event_hash: str


class TestRegionLock:
    """Structural guard on the single-touch test region."""

    # Name starts with "Test", so pytest tries to collect it as a test class and
    # warns because of __init__. This opts the class out of collection.
    __test__ = False

    def __init__(self, audit_log_path: str | os.PathLike | None = None,
                 repo_dir: str | os.PathLike | None = None):
        self._unlocked = False
        self._touches = 0                       # per-process diagnostic ONLY
        self._audit_log_path = Path(audit_log_path) if audit_log_path \
            else DEFAULT_AUDIT_LOG
        self._repo_dir = Path(repo_dir) if repo_dir else REPO_ROOT

    # ------------------------------------------------------------------ #
    # public unlock surface
    # ------------------------------------------------------------------ #
    def unlock(self, reason: str) -> None:
        """Genuine (analysis) unlock.  Durable, reconciled, tamper-evident."""
        self._unlocked = True
        self._touches += 1
        self._append_event(provenance="analysis", reason=reason)
        n = self.analysis_touches()
        print(f"\n*** TEST REGION UNLOCKED (analysis touch #{n}): {reason} ***")
        if n > 1:
            print("*** WARNING: the test region has now recorded more than one "
                  "ANALYSIS touch across the project's history. The single-touch "
                  "guarantee in the pre-analysis plan is broken. Any test-region "
                  "number you report is contaminated. ***\n")

    def unlock_for_selftest(self, reason: str) -> None:
        """Unit-test unlock. Ephemeral, tagged `unit_test`, NEVER written to the
        durable log, NEVER counted toward reconciliation.  Guarded so it cannot
        be used as a bypass: raises unless actually running under pytest."""
        if not _under_pytest():
            raise RuntimeError(
                "unlock_for_selftest() may only be called under pytest "
                "(PYTEST_CURRENT_TEST is not set). Ordinary code must use "
                "unlock(), which records a durable analysis touch."
            )
        self._unlocked = True
        self._touches += 1
        print(f"\n*** TEST REGION UNLOCKED (unit_test, ephemeral): {reason} ***")

    def relock(self) -> None:
        """Re-lock. Does NOT touch any counter or the durable log: re-locking
        must not erase the fact that an unlock occurred."""
        self._unlocked = False

    def check(self) -> None:
        """Gate before any test-region access. Raises unless the region has been
        explicitly unlocked. Preserved verbatim from the original TestRegionLock
        so existing call sites (and the `except PermissionError` in the suite)
        keep working unchanged."""
        if not self._unlocked:
            raise PermissionError(
                "Refusing to access the test region (2023-2025).\n"
                "Phase 0.5 runs on the DEVELOPMENT region only. The test region "
                "is touched exactly once, in Phase 4, after every rule in the "
                "pre-analysis plan is frozen.\n"
                "If you are certain: lock.unlock('reason')."
            )

    # ------------------------------------------------------------------ #
    # durable, hash-chained audit log
    # ------------------------------------------------------------------ #
    def _read_events(self) -> list[dict]:
        if not self._audit_log_path.exists():
            return []
        with self._audit_log_path.open("r") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def analysis_touches(self) -> int:
        """The audit truth: number of durable analysis touches. Survives restart."""
        return sum(1 for e in self._read_events() if e["provenance"] == "analysis")

    def _append_event(self, provenance: str, reason: str) -> TouchEvent:
        events = self._read_events()
        prev_hash = events[-1]["event_hash"] if events else _GENESIS
        commit, dirty = _git_info(self._repo_dir)
        event = {
            "touch_id": len(events) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provenance": provenance,
            "reason": reason,
            "git_commit": commit,
            "git_dirty": dirty,
            "prev_hash": prev_hash,
        }
        event["event_hash"] = _event_hash(event)
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log_path.open("a") as fh:
            fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        return TouchEvent(**event)

    def verify_chain(self) -> None:
        """Re-walk the log; raise if any event was edited, deleted, or reordered."""
        prev = _GENESIS
        for i, e in enumerate(self._read_events(), start=1):
            if e.get("prev_hash") != prev:
                raise ValueError(f"Broken chain at event {i}: prev_hash mismatch.")
            if e.get("event_hash") != _event_hash(e):
                raise ValueError(f"Broken chain at event {i}: content was altered.")
            prev = e["event_hash"]
