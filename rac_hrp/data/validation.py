"""
rac_hrp.data.validation
=======================
Phase 0.5, Task 3 -- reconstruction validation. NON-NEGOTIABLE GATE #4.

The claim "our universe is point-in-time and survivorship-bias-free" is worth
nothing unless it is checked against facts about the S&P 500 that are known
independently of CRSP. Without this step, a reconstruction bug reintroduces
survivorship silently, every downstream number is wrong, and nothing in the
backtest will tell you -- a survivorship-biased backtest looks *better*, not
broken.

Each check returns PASS / WARN / FAIL plus the evidence it was judged on.
A single FAIL blocks Phase 1.

The checks are deliberately about *shape*, not exact numbers: the aim is to
catch a reconstruction that is wrong by a mile (index of 300 names, no exits
ever, delistings that never happened), not to match CRSP against itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from .panel import Panels

# Publicly known properties of the S&P 500, used as external reference points.
EXPECTED_MEMBER_COUNT = (450, 520)     # index is 500 names (a few dual-class)
EXPECTED_ANNUAL_CHANGES = (5, 70)      # S&P typically makes ~20-25 changes/yr

# Known index exits. Ticker resolution is best-effort: CRSP tickers get reused
# and rewritten, so a miss is a WARN (cannot verify), never a FAIL.
KNOWN_EXITS = [
    ("ENE",   2001, 2002, "Enron -- bankruptcy"),
    ("LEH",   2008, 2009, "Lehman Brothers -- bankruptcy"),
    ("WM",    2008, 2009, "Washington Mutual -- bank failure"),
    ("GM",    2009, 2010, "General Motors -- bankruptcy"),
]


@dataclass
class Check:
    name: str
    status: str          # PASS | WARN | FAIL
    detail: str
    evidence: Optional[pd.DataFrame] = None

    def __str__(self) -> str:
        mark = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[self.status]
        return f"  [{mark}] {self.name}: {self.detail}"


class ReconstructionReport:
    def __init__(self, checks: List[Check], series: pd.DataFrame):
        self.checks = checks
        self.series = series

    @property
    def passed(self) -> bool:
        return not any(c.status == "FAIL" for c in self.checks)

    def __str__(self) -> str:
        head = "RECONSTRUCTION VALIDATION  (Phase 0.5, Gate 4)"
        body = "\n".join(str(c) for c in self.checks)
        verdict = "GATE PASSED" if self.passed else "GATE FAILED -- DO NOT PROCEED"
        return f"{head}\n{'-' * len(head)}\n{body}\n\n  => {verdict}\n"


def _membership_count_series(panels: Panels, freq: str = "ME") -> pd.DataFrame:
    """Number of point-in-time index members at each month end."""
    dates = panels.returns.index
    marks = pd.Series(1, index=dates).resample(freq).last().index
    marks = [d for d in marks if dates[0] <= d <= dates[-1]]
    rows = []
    m = panels.membership
    for d in marks:
        live = m[(m.mbrstartdt <= d) & (m.mbrenddt >= d)]
        rows.append({"date": d, "n_members": live.permno.nunique()})
    return pd.DataFrame(rows).set_index("date")


def _annual_changes(panels: Panels) -> pd.DataFrame:
    m = panels.membership
    adds = m.groupby(m.mbrstartdt.dt.year).size().rename("adds")
    drops = m.groupby(m.mbrenddt.dt.year).size().rename("drops")
    out = pd.concat([adds, drops], axis=1).fillna(0).astype(int)
    out["changes"] = out["adds"] + out["drops"]
    return out


def validate(panels: Panels,
             names: Optional[pd.DataFrame] = None,
             sample_start: str = "2000-01-03",
             sample_end: str = "2025-11-28") -> ReconstructionReport:
    checks: List[Check] = []
    lo, hi = pd.Timestamp(sample_start), pd.Timestamp(sample_end)

    # ---- C1: index size is ~500 throughout ------------------------------
    cnt = _membership_count_series(panels)
    cnt = cnt.loc[(cnt.index >= lo) & (cnt.index <= hi)]
    bad = cnt[(cnt.n_members < EXPECTED_MEMBER_COUNT[0]) |
              (cnt.n_members > EXPECTED_MEMBER_COUNT[1])]
    if len(bad) == 0:
        checks.append(Check(
            "index size", "PASS",
            f"member count stays in [{cnt.n_members.min()}, {cnt.n_members.max()}] "
            f"across {len(cnt)} month-ends"))
    else:
        checks.append(Check(
            "index size", "FAIL",
            f"{len(bad)} month-ends outside {EXPECTED_MEMBER_COUNT}; "
            f"range observed [{cnt.n_members.min()}, {cnt.n_members.max()}]. "
            "A reconstructed index that is not ~500 names is not the S&P 500.",
            bad))

    # ---- C2: the index actually churns ----------------------------------
    ch = _annual_changes(panels)
    ch = ch.loc[(ch.index >= lo.year) & (ch.index <= hi.year)]
    # The terminal year is censored (open spells capped at `end`), so exclude it.
    ch_i = ch.loc[ch.index < hi.year]
    out_of_band = ch_i[(ch_i.changes < EXPECTED_ANNUAL_CHANGES[0]) |
                       (ch_i.changes > EXPECTED_ANNUAL_CHANGES[1])]
    if len(ch_i) == 0:
        checks.append(Check("index turnover", "FAIL",
                            "no membership changes found at all -- this is a "
                            "static constituent list, i.e. survivorship bias."))
    elif len(out_of_band) == 0:
        checks.append(Check(
            "index turnover", "PASS",
            f"median {ch_i.changes.median():.0f} changes/yr "
            f"(range {ch_i.changes.min()}-{ch_i.changes.max()}), consistent with "
            "the ~20-25/yr the S&P Index Committee actually makes"))
    else:
        checks.append(Check(
            "index turnover", "WARN",
            f"{len(out_of_band)} years outside {EXPECTED_ANNUAL_CHANGES}; "
            "inspect before trusting the membership spells", out_of_band))

    # ---- C3: delisting returns were actually spliced --------------------
    audit = panels.delist_audit
    if audit is None or len(audit) == 0:
        checks.append(Check(
            "delisting splice", "WARN",
            "zero delisting returns spliced. Legitimate for the CIZ/v2 vintage "
            "(delisting is embedded in dsf_v2). On the legacy vintage this is a "
            "FAIL in disguise -- confirm which vintage you pulled."))
    else:
        a = audit[(audit.dlstdt >= lo) & (audit.dlstdt <= hi)]
        shum = (a.source == "shumway_-0.30").sum()
        checks.append(Check(
            "delisting splice", "PASS",
            f"{len(a)} delisting returns spliced in-sample; {shum} used the "
            f"Shumway -30% fill for a missing performance-related dlret. "
            "Those {} would otherwise have vanished at par.".format(shum)))

    # ---- C4: no member trades after its index exit ----------------------
    m = panels.membership
    ret = panels.returns
    violations = []
    for _, row in m.iterrows():
        p = row.permno
        if p not in ret.columns:
            continue
        end = row.mbrenddt
        if end >= hi:
            continue
        after = ret[p].loc[ret.index > end].dropna()
        # A stock can legitimately keep trading after leaving the index (it was
        # removed, not delisted). The bug we are hunting is the opposite: an
        # index member with NO return data at all while it was a member.
        _ = after
    covered = []
    for _, row in m.iterrows():
        p = row.permno
        if p not in ret.columns:
            covered.append({"permno": p, "coverage": 0.0})
            continue
        s, e = max(row.mbrstartdt, lo), min(row.mbrenddt, hi)
        if s > e:
            continue
        win = ret[p].loc[(ret.index >= s) & (ret.index <= e)]
        covered.append({"permno": p,
                        "coverage": float(win.notna().mean()) if len(win) else 0.0})
    cov = pd.DataFrame(covered)
    if len(cov) == 0:
        checks.append(Check("member return coverage", "FAIL",
                            "no overlap between membership spells and returns"))
    else:
        gaps = cov[cov.coverage < 0.90]
        frac = len(gaps) / len(cov)
        if frac < 0.05:
            checks.append(Check(
                "member return coverage", "PASS",
                f"{100 * (1 - frac):.1f}% of membership spells have >=90% return "
                "coverage while in the index"))
        else:
            checks.append(Check(
                "member return coverage", "FAIL",
                f"{100 * frac:.1f}% of spells have <90% coverage -- the returns "
                "panel does not cover the members you claim to hold", gaps.head(30)))

    # ---- C5: known bankruptcies exit the index --------------------------
    if names is not None and len(names):
        rows = []
        for tic, y0, y1, why in KNOWN_EXITS:
            hit = names[names.ticker == tic]
            if len(hit) == 0:
                rows.append({"ticker": tic, "event": why, "status": "not found"})
                continue
            ok = False
            for p in hit.permno.unique():
                sp = m[m.permno == p]
                if len(sp) and sp.mbrenddt.max().year in (y0, y1):
                    ok = True
            rows.append({"ticker": tic, "event": why,
                         "status": "exits as expected" if ok else "NO EXIT FOUND"})
        ev = pd.DataFrame(rows)
        miss = ev[ev.status == "NO EXIT FOUND"]
        found = ev[ev.status != "not found"]
        if len(found) == 0:
            checks.append(Check("known bankruptcy exits", "WARN",
                                "no reference tickers resolved -- cannot verify", ev))
        elif len(miss) == 0:
            checks.append(Check(
                "known bankruptcy exits", "PASS",
                f"{len(found)}/{len(KNOWN_EXITS)} reference exits (Enron, Lehman, "
                "WaMu, GM) land in the right year", ev))
        else:
            checks.append(Check(
                "known bankruptcy exits", "FAIL",
                f"{len(miss)} known bankruptcies never leave the reconstructed "
                "index. They are still in your universe. That is survivorship "
                "bias, verbatim.", ev))
    else:
        checks.append(Check("known bankruptcy exits", "WARN",
                            "names table not supplied -- check skipped"))

    series = cnt.join(pd.DataFrame({"year": cnt.index.year}).set_index(cnt.index))
    return ReconstructionReport(checks, series)
