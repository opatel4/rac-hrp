"""
rac_hrp.nulls.gate
==================
NULL GATE v1 -- Phase 0.5's hard stop. If this fails, Phase 1 does not happen.

THE DECISION RULE (fixed ex ante, D9) -- AN EQUIVALENCE TEST, NOT A DIFFERENCE TEST

This distinction is the whole design and it is easy to get wrong. We are not
trying to detect an effect; we are trying to DEMONSTRATE ITS ABSENCE. Those are
not the same test, and "the CI contains zero" does not demonstrate absence -- it
is satisfied trivially by any sufficiently underpowered experiment. Run three
replications, get a CI of [-2, +2], "contains zero", declare victory. That is a
gate you cannot fail, which is a gate that tests nothing.

The correct framing is equivalence (TOST-style). Fix a margin of practical
irrelevance -- here 0.10 annualised Sharpe units, `null_sharpe_tolerance` -- and
require the ENTIRE confidence interval to fall inside it:

    for each replication m:   dSR_m = Sharpe(RAC_HRP) - Sharpe(comparator)
    95% CI for mean(dSR) = [lo, hi]

    PASS          iff  -tol <= lo  and  hi <= +tol
                       (the edge is bounded below materiality, WITH precision)
    FAIL          iff  CI excludes zero AND |mean| > tol
                       (a material, systematic edge exists under a null)
    INCONCLUSIVE  otherwise
                       (the CI is too wide to conclude anything -- this is an
                        UNDERPOWERED result, not a pass. Remedy: more replications.)

The gate PASSES only if every cell PASSES. An INCONCLUSIVE cell blocks Phase 1
just as a FAIL does, but the remedy is different: FAIL means fix the code,
INCONCLUSIVE means run more replications.

The margin is in Sharpe units because that is the unit the paper's claim is made
in. A pipeline that manufactures 0.10 of Sharpe from pure noise cannot support a
claim of 0.15 of Sharpe from real data.

COMPARATOR SETS ARE ENVIRONMENT-SPECIFIC (and this is not a detail)

Environments A, B and D destroy the RETURN SIGNAL. Every strategy should earn
zero, so EVERY pairwise difference must be zero, and the full comparator set
{EW, ERC, HRP_static} applies.

Environment C does NOT destroy the return signal -- the returns are real. It
destroys only the TRIGGER'S TIMING. So under C, HRP may legitimately beat equal
weight, for the ordinary reason that risk-based allocation on real correlations
is a real thing. Demanding "no edge over EW" under C would not be testing a null
hypothesis; it would be demanding that the strategy not work. The only valid
comparators under C are the ones that are IDENTICAL TO RAC-HRP EXCEPT IN THEIR
RE-CLUSTERING POLICY: static HRP and periodic HRP. Everything else -- universe,
covariance, spectrum, allocator -- is held fixed, so the contrast isolates the
one thing C nulls out. That is what makes it a null test rather than a demand.

WHAT FAILURE MEANS, PER ENVIRONMENT

  A fails  -> look-ahead. Weights are seeing returns they should not. Fix the
              indexing before anything else; nothing downstream is meaningful.
  B fails  -> leakage through asset identity. The pipeline is using cross-
              sectional information it should not have.
  C fails  -> THE ONE THAT MATTERS FOR THIS PAPER. RAC-HRP beats static HRP just
              as well with a RANDOMLY TIMED trigger. The absorption ratio is then
              contributing nothing; the "contribution" is that re-clustering at
              all beats never re-clustering, which is a much weaker and already-
              known claim. If C fails, the paper's thesis is false and no amount
              of tuning saves it -- it must be reframed.
  D fails  -> the edge is volatility timing wearing a regime-clustering costume.

NOTE ON POWER. A gate that passes because the test is too weak to detect anything
is worthless. `power_check()` therefore runs a POSITIVE CONTROL: it injects a
deliberate look-ahead leak into the pipeline and confirms the gate catches it.
A null gate you have never seen fail is a null gate you have no reason to trust.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import Config
from ..backtest.engine import WalkForward, Strategy
from ..backtest.metrics import sharpe
from ..data.panel import Panels
from .environments import ENVIRONMENTS, draw

FOCAL = "RAC_HRP"

# Environments A/B/D destroy the return signal -> every difference must vanish.
# Environment C keeps returns real and destroys only the trigger timing -> the
# only legitimate contrasts are strategies identical to RAC-HRP except in their
# re-clustering policy. See the module docstring.
SIGNAL_DESTROYING = ["EW", "ERC", "HRP_static"]
POLICY_ONLY = ["HRP_static", "HRP_periodic_3"]

COMPARATOR_SETS = {
    "A_iid_gaussian": SIGNAL_DESTROYING,
    "B_xsec_shuffle": SIGNAL_DESTROYING,
    "C_trigger_timing": POLICY_ONLY,
    "D_regime_switch_vol": SIGNAL_DESTROYING,
}


def gate_strategies() -> List[Strategy]:
    """Only what the gate needs. The full periodic sweep is Phase 2's job;
    running it here would triple the cost for no gate-relevant information.
    HRP_periodic_3 is included because environment C requires it."""
    return [
        Strategy("EW", allocator="ew"),
        Strategy("ERC", allocator="erc"),
        Strategy("HRP_static", allocator="hrp", recluster="never"),
        Strategy("HRP_periodic_3", allocator="hrp", recluster="periodic:3"),
        Strategy(FOCAL, allocator="hrp", recluster="ar_trigger"),
    ]


@dataclass
class CellResult:
    env: str
    comparator: str
    dsr: np.ndarray                 # dSR per replication
    mean: float = 0.0
    se: float = 0.0
    ci_lo: float = 0.0
    ci_hi: float = 0.0
    frac_positive: float = 0.0
    verdict: str = "INCONCLUSIVE"   # PASS | FAIL | INCONCLUSIVE
    reason: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"


@dataclass
class GateReport:
    cells: List[CellResult] = field(default_factory=list)
    n_reps: int = 0
    tolerance: float = 0.10
    trigger_counts: Dict[str, List[int]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.cells) > 0 and all(c.passed for c in self.cells)

    @property
    def any_fail(self) -> bool:
        return any(c.verdict == "FAIL" for c in self.cells)

    @property
    def any_inconclusive(self) -> bool:
        return any(c.verdict == "INCONCLUSIVE" for c in self.cells)

    def table(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "environment": c.env,
            "vs": c.comparator,
            "mean_dSharpe": round(c.mean, 4),
            "95%_CI": f"[{c.ci_lo:+.3f}, {c.ci_hi:+.3f}]",
            "P(dSR>0)": round(c.frac_positive, 2),
            "verdict": c.verdict,
            "why": c.reason,
        } for c in self.cells])

    def __str__(self) -> str:
        head = (f"NULL GATE v1   ({self.n_reps} replications; "
                f"equivalence margin |dSharpe| <= {self.tolerance})")
        lines = [head, "=" * len(head), "",
                 self.table().to_string(index=False), ""]
        if self.trigger_counts:
            lines.append("AR trigger firings per replication (median):")
            for e, v in self.trigger_counts.items():
                lines.append(f"    {e:24s} {int(np.median(v)):3d}")
            lines.append("  (A trigger that never fires passes the gate vacuously.")
            lines.append("   These counts are the evidence that it actually fired.)")
            lines.append("")
        for n in self.notes:
            lines.append(f"  NOTE: {n}")
        if self.notes:
            lines.append("")

        if self.passed:
            verdict = "GATE PASSED -- the pipeline returns nothing when there is nothing. Proceed to Phase 1."
        elif self.any_fail:
            verdict = ("GATE FAILED -- the pipeline manufactures an edge from noise. "
                       "DO NOT PROCEED. Diagnose the failing environment.")
        else:
            verdict = (f"GATE INCONCLUSIVE -- underpowered at {self.n_reps} replications. "
                       "This is NOT a pass. Increase --reps and re-run.")
        lines += [f"=> {verdict}"]
        return "\n".join(lines)


def _run_replication(panels: Panels, cfg: Config, eval_pos: np.ndarray,
                     env: str, rng: np.random.Generator) -> tuple:
    perf, signal = draw(env, panels.returns, rng)

    # The universe/eligibility layer must see the SAME point-in-time structure,
    # so we swap only the numbers, never the mask or the membership.
    null_panels = Panels(returns=perf, mcap=panels.mcap,
                         membership=panels.membership, rf=panels.rf,
                         delist_audit=panels.delist_audit)

    wf = WalkForward(null_panels, cfg, signal_returns=signal)
    res = wf.run(gate_strategies(), eval_pos)

    srs = {k: sharpe(v.returns, panels.rf) for k, v in res.items()}
    n_trig = res[FOCAL].n_reclusters
    return srs, n_trig


def run_gate(panels: Panels,
             cfg: Config,
             eval_pos: np.ndarray,
             environments: Optional[List[str]] = None,
             n_reps: Optional[int] = None,
             verbose: bool = True) -> GateReport:
    envs = environments or list(ENVIRONMENTS.keys())
    M = n_reps or cfg.null_replications
    rep = GateReport(n_reps=M, tolerance=cfg.null_sharpe_tolerance)

    for env in envs:
        if verbose:
            print(f"\n  [{env}] {ENVIRONMENTS[env]}")
        rows, trigs = [], []
        for m in range(M):
            rng = np.random.default_rng(cfg.seed + 1000 * envs.index(env) + m)
            srs, nt = _run_replication(panels, cfg, eval_pos, env, rng)
            rows.append(srs)
            trigs.append(nt)
            if verbose:
                print(f"      rep {m + 1:2d}/{M}  "
                      f"SR(RAC)={srs[FOCAL]:+.3f}  "
                      f"dSR vs static={srs[FOCAL] - srs['HRP_static']:+.3f}  "
                      f"triggers={nt}")
        rep.trigger_counts[env] = trigs

        df = pd.DataFrame(rows)
        tol = cfg.null_sharpe_tolerance
        for c in COMPARATOR_SETS[env]:
            if c not in df.columns:
                continue
            d = (df[FOCAL] - df[c]).values
            d = d[np.isfinite(d)]
            if len(d) < 2:
                continue
            mean = float(np.mean(d))
            se = float(np.std(d, ddof=1) / np.sqrt(len(d)))
            lo, hi = mean - 1.96 * se, mean + 1.96 * se

            # SIDEDNESS -- an open decision, see README.
            # "two": the edge must be bounded in BOTH directions. Conservative.
            #        A large NEGATIVE dSharpe under a null blocks the gate too.
            # "one": only a POSITIVE edge blocks. The failure mode the gate exists
            #        to catch is "the pipeline manufactures signal from noise",
            #        which is directional. RAC-HRP UNDER-performing static HRP on
            #        a signal-free panel is not manufactured signal -- it is the
            #        trigger churning the tree for nothing, which is a real cost
            #        but a Phase 2/3 turnover question, not a validity question.
            if cfg.null_gate_sided == "one":
                within = (hi <= tol)
                excludes_zero = (lo > 0.0)
                material = mean > tol
            else:
                within = (lo >= -tol) and (hi <= tol)
                excludes_zero = not (lo <= 0.0 <= hi)
                material = abs(mean) > tol

            if within:
                verdict = "PASS"
                reason = "edge bounded below materiality, with precision"
            elif excludes_zero and material:
                verdict = "FAIL"
                reason = "material systematic edge under a null -- signal is manufactured"
            else:
                verdict = "INCONCLUSIVE"
                # How many replications WOULD settle it? The CI half-width shrinks
                # as 1/sqrt(M), so solve 1.96 * sd / sqrt(M) <= tol - |mean|.
                sd = float(np.std(d, ddof=1))
                room = (tol - mean) if cfg.null_gate_sided == "one" else (tol - abs(mean))
                if room <= 0:
                    reason = (f"|mean| {abs(mean):.3f} already exceeds the margin "
                              f"{tol}; more replications will not help")
                    need = None
                else:
                    need = int(np.ceil((1.96 * sd / room) ** 2))
                    reason = (f"CI half-width {1.96 * se:.3f} > margin {tol}; "
                              f"need ~{need} reps")
                rep.notes.append(
                    f"{env} vs {c}: INCONCLUSIVE at {len(d)} reps"
                    + (f" -- re-run with --reps {need}" if need else
                       " -- effect exceeds the margin regardless of reps"))

            rep.cells.append(CellResult(
                env=env, comparator=c, dsr=d, mean=mean, se=se,
                ci_lo=lo, ci_hi=hi,
                frac_positive=float(np.mean(d > 0)),
                verdict=verdict, reason=reason))

    # A trigger that never fires passes the gate for the wrong reason.
    for env, t in rep.trigger_counts.items():
        if np.median(t) == 0:
            rep.notes.append(
                f"{env}: the AR trigger NEVER FIRED. This cell passed vacuously "
                "-- it tested nothing. Check ar_trigger_sigma and the dAR "
                "standard-deviation window before trusting it.")
    return rep


# --------------------------------------------------------------------------
# Positive control
# --------------------------------------------------------------------------
def power_check(panels: Panels, cfg: Config, eval_pos: np.ndarray,
                strengths: Optional[List[float]] = None,
                n_reps: int = 5, verbose: bool = True) -> pd.DataFrame:
    """POSITIVE CONTROL: what is the smallest manufactured edge this gate catches?

    A null gate that has never been seen to fail is a null gate you have no
    reason to trust. Passing it might mean the pipeline is clean, or it might
    mean the gate cannot detect anything. Those two states are indistinguishable
    from a PASS alone, and only one of them is good news.

    So we substitute an ORACLE strategy -- one with a deliberate look-ahead tilt
    of KNOWN strength (see engine._oracle_weights) -- in place of RAC-HRP, run it
    through the identical gate machinery on the IID-Gaussian null, and sweep the
    strength. The output is the gate's minimum detectable effect (MDE) in Sharpe
    units at the current replication count.

    Read it like this: if the gate only catches edges above 0.4 Sharpe, then its
    PASS on the real pipeline rules out large fraud and nothing more, and the
    0.10 equivalence margin is a fiction. If it catches 0.10, the margin is real.
    """
    strengths = strengths or [0.0, 0.005, 0.01, 0.025, 0.05]
    tol = cfg.null_sharpe_tolerance
    if verbose:
        print("\n  POSITIVE CONTROL (gate power): oracle look-ahead tilt sweep")

    rows = []
    for s in strengths:
        ds = []
        for m in range(n_reps):
            rng = np.random.default_rng(cfg.seed + 99_000 + m)
            perf, _ = draw("A_iid_gaussian", panels.returns, rng)
            np_ = Panels(returns=perf, mcap=panels.mcap,
                         membership=panels.membership, rf=panels.rf,
                         delist_audit=panels.delist_audit)
            wf = WalkForward(np_, cfg)
            res = wf.run([
                Strategy("HRP_static", allocator="hrp", recluster="never"),
                Strategy("ORACLE", allocator="oracle", oracle_strength=s),
            ], eval_pos)
            ds.append(sharpe(res["ORACLE"].returns, panels.rf)
                      - sharpe(res["HRP_static"].returns, panels.rf))

        d = np.array([x for x in ds if np.isfinite(x)])
        mean = float(d.mean())
        se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else np.nan
        lo, hi = mean - 1.96 * se, mean + 1.96 * se
        within = (lo >= -tol) and (hi <= tol)
        caught = (not (lo <= 0 <= hi)) and abs(mean) > tol
        rows.append({
            "oracle_strength": s,
            "mean_dSharpe": round(mean, 3),
            "95%_CI": f"[{lo:+.3f}, {hi:+.3f}]",
            "gate_verdict": "FAIL (caught)" if caught
                            else ("PASS (missed)" if within else "INCONCLUSIVE"),
        })
        if verbose:
            print(f"      strength={s:.2f}  dSharpe={mean:+.3f}  {rows[-1]['gate_verdict']}")

    return pd.DataFrame(rows)
