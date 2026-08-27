"""
pytest configuration and project-wide invariants.

WHY PYTEST IS CANONICAL
    The suites were originally driven by hand-written runners that collected an
    explicit list of functions. Three failures this project has seen share one
    shape -- something is added or removed, nothing is wired to it, and the suite
    stays green:

      * folds.py silently reverted twice by whole-tree copies (caught by grep,
        not by tests);
      * the MHRP_EV allocator deleted by f6e09dc while run_phase1.py still
        declared it (Incident E2; caught weeks later when Phase 1 was re-run);
      * the coverage test written to catch E2 was itself inert -- appended below
        the runner's sys.exit(), it never executed while the suite reported green.

    pytest auto-discovery removes the third failure mode entirely. It does NOT
    remove the first two: discovery finds tests, it does not notice deleted
    production code. That requires explicit invariants, which live in
    tests/test_invariants.py.

    The legacy runners still work (`python tests/test_phase05.py`) and are kept so
    existing habits and any CI that calls them do not break. pytest is the
    canonical entry point: `pytest tests/ -q`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Minimum number of tests expected to be collected. Guards against a whole file
# silently failing to import (which pytest reports as a collection error but which
# is easy to miss in a long log) or a suite being dropped. Raise deliberately when
# tests are added; never lower it to make a run pass.
MIN_COLLECTED = 50


def pytest_collection_modifyitems(session, config, items):
    n = len(items)
    if n < MIN_COLLECTED:
        raise pytest.UsageError(
            f"collected only {n} tests, expected at least {MIN_COLLECTED}. "
            "A test module probably failed to import or was dropped. "
            "If tests were intentionally removed, lower MIN_COLLECTED in "
            "tests/conftest.py in the same commit, with a reason.")


def pytest_report_header(config):
    return [
        f"rac-hrp root: {ROOT}",
        f"OPENBLAS_NUM_THREADS={os.environ.get('OPENBLAS_NUM_THREADS', '<unset>')}"
        "  (project standard is 1; ~13x faster on this workload, verified "
        "result-neutral)",
    ]
