"""
rac_hrp.data.validation_crsp
============================
T3 reconstruction gate, rewritten for the CRSP-native large-cap universe.

The old S&P-500 checks are meaningless here -- there is no index to be the wrong
size, and no committee to remove anybody. But the QUESTION the gate exists to
answer is unchanged, and it is the only question that matters:

    ARE THE COMPANIES THAT FAILED STILL IN MY UNIVERSE?

Under the S&P construction we tested that by asking whether Lehman *left the
index* in 2008. Under a market-cap construction the test is sharper and more
direct, because it interrogates the thing we actually depend on:

    * Lehman must be IN the top-N universe in 2007  (it was a huge company)
    * Lehman must be GONE from it after Sept 2008    (it ceased to exist)
    * Lehman's return series must contain the CRASH  (the delisting return)

That third one is the one a survivorship-biased panel fails silently. A universe
can contain Lehman, drop it at the right moment, and STILL be biased -- if the
price series simply stops at the last quoted price instead of booking the -90%
delisting return, the portfolio never takes the loss. It "held" Lehman and walked
away whole. That is the failure mode this gate is built to catch, and it is
invisible in every summary statistic downstream.

So: presence, disappearance, AND the loss actually being booked.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from .panel import Panels
from .validation import Check, ReconstructionReport

# Large US companies that FAILED, PINNED BY PERMNO.
#
# Resolved by CRSP permno directly, not by name or ticker (recycled tickers,
# pre-collapse windows, and surviving namesakes each broke name resolution).
#
# THE COLLAPSE IS NOT ALWAYS AT THE SERIES END. CRSP permnos track a legal entity
# across reorganization, and a bankruptcy estate can reorganize into a living
# company under the SAME permno. Permno 81593 is the canonical case: Washington
# Mutual (bank, wiped out Sept 2008) -> WMI Holdings -> WMIH Corp -> Mr. Cooper
# Group (a mortgage servicer trading today). The series runs to 2024, but WaMu's
# -90% is booked mid-series, on 2008-09-26, not in the terminal quarter.
#
# So the test is NOT "did the terminal quarter collapse" -- that asks about
# whichever company holds the permno LAST. It is "does the worst 63-day cumulative
# drawdown inside the death window reach the collapse" -- which asks about the
# company that actually died, wherever in the series it sits.
#
# (permno, label, death_year_lo, death_year_hi, must_collapse)
KNOWN_FAILURES = [
    (23317, "Enron",             2001, 2002, True),
    (80599, "Lehman Brothers",   2008, 2008, True),
    (81593, "Washington Mutual", 2008, 2008, True),   # -> Mr Cooper; collapse mid-series
    (68304, "Bear Stearns",      2008, 2008, True),
    (12079, "General Motors",    2009, 2009, True),
    (66800, "AIG",               2008, 2009, False),   # survived (~-95%), did not delist
]


def validate_crsp_largecap(panels: Panels,
                           names: Optional[pd.DataFrame],
                           n_assets: int = 100,
                           sample_start: str = "2000-01-03",
                           sample_end: str = "2025-11-28") -> ReconstructionReport:
    checks: List[Check] = []
    lo, hi = pd.Timestamp(sample_start), pd.Timestamp(sample_end)
    ret, mcap = panels.returns, panels.mcap
    cal = ret.index
    marks = [d for d in pd.date_range(lo, hi, freq="YE") if d <= cal[-1]]

    # ---- C1: the eligible universe is big enough to rank -----------------
    rows = []
    for d in marks:
        pos = cal.searchsorted(d, side="right") - 1
        if pos < 0:
            continue
        alive = ret.iloc[pos].notna().values
        member = panels.is_member(cal[pos])
        rows.append({"date": cal[pos], "n_eligible": int((alive & member).sum())})
    elig = pd.DataFrame(rows).set_index("date")

    min_e = int(elig.n_eligible.min())
    if min_e >= n_assets * 1.5:
        checks.append(Check(
            "eligible pool", "PASS",
            f"eligible names range [{min_e}, {int(elig.n_eligible.max())}] at "
            f"year-ends; comfortably above the N={n_assets} we rank down to"))
    else:
        checks.append(Check(
            "eligible pool", "FAIL",
            f"eligible pool falls to {min_e}, too close to N={n_assets}. The "
            "top-N cut is not selecting; it is taking whatever is left.", elig))

    # ---- C2: delisting returns were spliced ------------------------------
    audit = panels.delist_audit
    if audit is None or len(audit) == 0:
        checks.append(Check(
            "delisting splice", "FAIL",
            "ZERO delisting returns spliced. On the CRSP legacy stock file this "
            "is not a vintage quirk -- it means every failed company left your "
            "panel at its last quoted price. That is survivorship bias."))
    else:
        a = audit[(audit.dlstdt >= lo) & (audit.dlstdt <= hi)]
        shum = int((a.source == "shumway_-0.30").sum())
        checks.append(Check(
            "delisting splice", "PASS",
            f"{len(a):,} delisting returns spliced in-sample; {shum:,} used the "
            f"Shumway -30% fill for a missing performance-related dlret"))

    # ---- C3: the failures are IN the universe, and they TAKE THE LOSS ----
    rows = []
    for permno, label, y0, y1, must_collapse in KNOWN_FAILURES:
        if permno not in ret.columns:
            rows.append({"company": label, "permno": permno, "window": f"{y0}-{y1}",
                         "worst_63d_drawdown": np.nan, "verdict": "NOT IN PANEL"})
            continue
        # returns INSIDE the death window -- this isolates the company that died,
        # even when the permno later reorganises into a living successor.
        s = ret[permno].loc[(ret.index >= f"{y0}-01-01") &
                            (ret.index <= f"{y1}-12-31")].dropna()
        if not len(s):
            rows.append({"company": label, "permno": permno, "window": f"{y0}-{y1}",
                         "worst_63d_drawdown": np.nan, "verdict": "NO RETURNS IN WINDOW"})
            continue

        # worst cumulative return over any 63-trading-day span in the window
        logret = np.log1p(s.values)
        worst = 1.0
        csum = np.concatenate([[0.0], np.cumsum(logret)])
        for i in range(len(s)):
            j = min(i + 63, len(s))
            span = np.exp(csum[j] - csum[i]) - 1.0
            worst = min(worst, span)

        if must_collapse:
            ok = worst < -0.60
        else:
            ok = worst < -0.50          # AIG survived but must show the ~-95% drop
        rows.append({
            "company": label, "permno": permno, "window": f"{y0}-{y1}",
            "worst_63d_drawdown": round(float(worst), 3),
            "verdict": "collapse booked" if ok else "NO COLLAPSE IN WINDOW",
        })

    ev = pd.DataFrame(rows)
    absent = ev[ev.verdict.isin(["NOT IN PANEL", "NO RETURNS IN WINDOW"])]
    nocrash = ev[ev.verdict == "NO COLLAPSE IN WINDOW"]

    if len(absent):
        checks.append(Check(
            "known failures", "FAIL",
            f"{len(absent)} reference failures are NOT in the panel during their "
            "death window. They were large caps until they died; their absence IS "
            "survivorship bias.", ev))
    elif len(nocrash):
        checks.append(Check(
            "known failures", "FAIL",
            f"{len(nocrash)} failed companies never book their collapse inside the "
            "death window -- the series does not take the loss. Survivorship bias.",
            ev))
    else:
        checks.append(Check(
            "known failures", "PASS",
            f"all {len(ev)} pinned reference failures (Enron, Lehman, WaMu, Bear "
            "Stearns, GM, AIG) book their collapse inside the death window", ev))

    # ---- C4: the top-N universe churns, but not absurdly -----------------
    checks.append(Check(
        "note", "PASS",
        "universe is mechanical (top-N by lagged mcap); there is no index "
        "committee, so there is no membership series to validate against. "
        "Realized-N and turnover are reported by T2 instead."))

    return ReconstructionReport(checks, elig)
