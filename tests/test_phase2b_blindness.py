"""Phase 2B section 2 blindness invariant.

WHAT THIS ENFORCES
    PHASE2B_SPEC.md section 2: "Test asserting no return-performance symbol or
    risk-free series is reachable from the Phase 2B module. Runs in CI."

    Two halves, and the second was ambiguous until it was settled by the author:

      performance   no `rac_hrp.backtest` import anywhere in the transitive
                    import closure of rac_hrp.phase2b.stats, checked both
                    statically (AST) and dynamically (sys.modules).
      risk-free     no `rf` reference -- as attribute, bare name, or subscript
                    key -- in any closure module, with rac_hrp/data/panel.py
                    allowlisted. panel.py DEFINES the series as a field on
                    Panels; the assertion is that nothing on the Phase 2B path
                    reads it.

WHY STATIC AND DYNAMIC BOTH
    The dynamic check is the honest one -- it observes what the interpreter
    actually loaded. But it can only see the import graph that ran, so a lazy
    `import rac_hrp.backtest.metrics` inside a function body would pass it
    untouched until that function is called. The static walk descends into
    function bodies and catches exactly that. Neither subsumes the other.

WHY A SUBPROCESS FOR THE DYNAMIC CHECK
    sys.modules is process-global. Other tests in the same session import
    rac_hrp.backtest.region_lock, which would put a `rac_hrp.backtest` key in
    sys.modules and make an in-process assertion fire on someone else's import
    -- or, worse, a future refactor could make the check pass for the wrong
    reason. A fresh interpreter observes this module's imports and nothing else.

WHY AST AND NOT GREP
    `perf` contains "rf". So does `rf_df`, in panel.py. A textual scan either
    false-positives on those or gets loosened until it stops catching anything.
    Node-identity matching on Name.id / Attribute.attr / Subscript key is exact
    and cannot be fooled either way.

WHY test_closure_resolves EXISTS
    If the resolver ever returns an empty dict, every other assertion in this
    file passes vacuously and the suite reports green. That is the third failure
    shape documented in tests/conftest.py -- a test that was inert while looking
    healthy. The closure is asserted to be non-empty and to contain the modules
    it is known to contain.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pytest

ROOT = Path(__file__).resolve().parents[1]

ENTRY = "rac_hrp.phase2b.stats"
FORBIDDEN_PACKAGE = "rac_hrp.backtest"

# panel.py defines Panels.rf. It is the one place the series is allowed to
# appear on this path. test_allowlist_is_justified keeps this honest.
RF_ALLOWLIST = {"rac_hrp.data.panel"}

# Known members of the closure. Not an exhaustive contract -- the closure may
# legitimately grow -- but it must never collapse to nothing or lose the entry.
EXPECTED_IN_CLOSURE = {
    "rac_hrp.phase2b.stats",
    "rac_hrp.phase2.horizon",
    "rac_hrp.phase2.calibration",
    "rac_hrp.core.clustering",
    "rac_hrp.data.panel",
    "rac_hrp.config",
}


# --------------------------------------------------------------------------
# Static closure
# --------------------------------------------------------------------------
def _module_path(dotted: str) -> Optional[Path]:
    """Resolve a dotted rac_hrp module name to a source file under ROOT."""
    parts = dotted.split(".")
    mod = ROOT.joinpath(*parts).with_suffix(".py")
    if mod.is_file():
        return mod
    pkg = ROOT.joinpath(*parts) / "__init__.py"
    if pkg.is_file():
        return pkg
    return None


def _imports_of(tree: ast.AST, dotted: str, path: Path) -> List[str]:
    """Every rac_hrp module name imported by `tree`, relative ones resolved.

    ast.walk descends into function and class bodies, so deferred imports are
    reported alongside module-level ones.
    """
    # A package __init__ IS its package; a module's package is its parent.
    base = dotted.split(".") if path.name == "__init__.py" else dotted.split(".")[:-1]

    out: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    out.append(node.module)
                continue
            pkg = list(base)
            for _ in range(node.level - 1):
                pkg = pkg[:-1]
            if node.module:
                pkg = pkg + node.module.split(".")
            if pkg:
                out.append(".".join(pkg))
    return [m for m in out if m.startswith("rac_hrp")]


def _closure(entry: str) -> Dict[str, Path]:
    """Transitive rac_hrp import closure of `entry`, by source inspection."""
    found: Dict[str, Path] = {}
    todo = [entry]
    while todo:
        name = todo.pop()
        if name in found:
            continue
        path = _module_path(name)
        if path is None:
            continue
        found[name] = path
        tree = ast.parse(path.read_text(), filename=str(path))
        todo.extend(_imports_of(tree, name, path))
    return found


@pytest.fixture(scope="module")
def closure() -> Dict[str, Path]:
    return _closure(ENTRY)


# --------------------------------------------------------------------------
# 1. the closure is real
# --------------------------------------------------------------------------
def test_closure_resolves(closure):
    assert closure, (
        "the import closure resolved to nothing; every other assertion in this "
        "file would pass vacuously. Fix the resolver before trusting a green run.")
    assert ENTRY in closure, f"{ENTRY} missing from its own closure"

    missing = EXPECTED_IN_CLOSURE - set(closure)
    assert not missing, (
        f"closure lost known members {sorted(missing)}; the resolver is not "
        "walking the graph it used to")


# --------------------------------------------------------------------------
# 2. no performance code, statically
# --------------------------------------------------------------------------
def test_no_backtest_import_static(closure):
    violations: List[str] = []
    for name, path in sorted(closure.items()):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            mods: List[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for m in mods:
                if m == FORBIDDEN_PACKAGE or m.startswith(FORBIDDEN_PACKAGE + "."):
                    violations.append(f"{name}:{node.lineno} imports {m}")

    assert not violations, (
        "performance code is reachable from the Phase 2B module:\n  "
        + "\n  ".join(violations))


# --------------------------------------------------------------------------
# 3. no performance code, dynamically
# --------------------------------------------------------------------------
def test_no_backtest_import_dynamic():
    code = (
        "import sys\n"
        f"import {ENTRY}\n"
        f"print(sorted(m for m in sys.modules "
        f"if m.startswith({FORBIDDEN_PACKAGE!r})))\n"
    )
    env = dict(os.environ, PYTHONPATH=str(ROOT), OPENBLAS_NUM_THREADS="1")
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, timeout=180)

    assert proc.returncode == 0, (
        f"importing {ENTRY} in a clean interpreter failed:\n{proc.stderr}")
    assert proc.stdout.strip() == "[]", (
        f"importing {ENTRY} pulled in performance modules: {proc.stdout.strip()}")


# --------------------------------------------------------------------------
# 4. no risk-free series
# --------------------------------------------------------------------------
def _rf_hits(tree: ast.AST) -> List[str]:
    """Every reference to the name `rf`, in each form it can take."""
    hits: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "rf":
            hits.append(f"line {node.lineno}: name `rf`")
        elif isinstance(node, ast.Attribute) and node.attr == "rf":
            hits.append(f"line {node.lineno}: attribute `.rf`")
        elif isinstance(node, ast.Subscript):
            s = node.slice
            if isinstance(s, ast.Constant) and s.value == "rf":
                hits.append(f"line {node.lineno}: subscript ['rf']")
        elif isinstance(node, ast.keyword) and node.arg == "rf":
            hits.append(f"line {node.lineno}: keyword argument rf=")
        elif isinstance(node, ast.arg) and node.arg == "rf":
            hits.append(f"line {node.lineno}: parameter named rf")
        elif isinstance(node, ast.alias) and "rf" in (node.name, node.asname):
            hits.append(f"line {node.lineno}: import alias rf")
    return hits


def test_no_rf_reference(closure):
    violations: List[str] = []
    for name, path in sorted(closure.items()):
        if name in RF_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        violations.extend(f"{name} {h}" for h in _rf_hits(tree))

    assert not violations, (
        "the risk-free series is referenced on the Phase 2B path:\n  "
        + "\n  ".join(violations))


def test_allowlist_is_justified(closure):
    """An allowlist entry that no longer needs to be there hides regressions."""
    assert RF_ALLOWLIST == {"rac_hrp.data.panel"}, (
        "the rf allowlist changed; PHASE2B_SPEC.md section 2 was committed with "
        "exactly one exemption and widening it is a specification change")

    for name in RF_ALLOWLIST:
        assert name in closure, f"allowlisted {name} is not in the closure"
        tree = ast.parse(closure[name].read_text())
        assert _rf_hits(tree), (
            f"{name} is allowlisted for rf but no longer references it; remove "
            "the exemption so a future reintroduction is caught")
