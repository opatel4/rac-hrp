"""
rac_hrp.data.crsp_universe
==========================
D1 (AMENDED) -- CRSP-native large-cap US equity universe.

WHY THIS REPLACED THE S&P 500
-----------------------------
Forced. This account's Compustat subscription exposes S&P *US* index membership
as a CURRENT-CONSTITUENTS view only: `comp.idxcst_his` returns 503 spells for
gvkeyx='000003' with ZERO exit dates, while the same table carries 1,267 exits for
the S&P/TSX and 420 for the Nasdaq 100. S&P licenses US constituent HISTORY as a
premium product and this institution does not hold it. CRSP's index files
(`crsp_a_indexes`) are likewise not licensed. There is no query that recovers the
history; it is a licensing boundary, not a bug.

Using the 503 current constituents retroactively would have been survivorship bias
in its purest form -- every firm that failed between 2000 and 2025 silently absent.

THE REPLACEMENT UNIVERSE

    The N largest US common stocks by LAGGED market capitalisation, from CRSP:
      * share codes 10, 11        (ordinary common shares; no ADRs, REITs, closed-
                                   end funds, units, or trusts)
      * exchange codes 1, 2, 3    (NYSE, AMEX, Nasdaq)
      * ranked on market cap lagged 21 trading days
      * reconstituted at each monthly rebalance
      * delisting returns spliced (Shumway 1997)

THIS IS NOT A CONSOLATION PRIZE. Three reasons it is arguably the better design:

1. The hypothesis never mentioned the S&P 500. The claim is about absorption-ratio-
   triggered re-clustering under changing equity correlation regimes. "Large-cap US
   equities" IS the population of interest; index membership was only ever a proxy
   for it.

2. The S&P Index Committee is a discretionary selection mechanism, and a confound.
   They add names after they have performed and remove them after they have not.
   That discretion is entangled with the very correlation dynamics being measured.
   A mechanical market-cap rule has no committee, no announcement effect, and no
   discretion to control for.

3. It is more reproducible. Anyone with a standard CRSP subscription can rebuild
   this universe exactly. Anyone WITHOUT the premium S&P history license -- which
   now includes us -- cannot rebuild an S&P 500 one.

IMPLEMENTATION NOTE: THE TWO-STAGE PULL
---------------------------------------
Ranking the whole CRSP cross-section by market cap needs market cap for the whole
CRSP cross-section: ~20,000 permnos x 6,500 days is tens of millions of daily rows
and multiple GB, most of it micro-caps that can never enter a top-500 universe.

So we pre-screen on the MONTHLY file (`crsp.msf`, ~100x smaller), take the union of
every permno that was EVER inside the top `screen_k` by month-end market cap, and
pull the daily file only for those. With screen_k comfortably above the largest N
we will ever use, this is lossless for our purposes: a stock that was never in the
top 750 at any month-end in 25 years cannot be in a top-500 daily universe.

The screen is applied on a LAGGED, point-in-time basis and includes delisted names
by construction -- Lehman was in the top 750 until it wasn't.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

# Ordinary common shares, major exchanges.
VALID_SHRCD = (10, 11)
VALID_EXCHCD = (1, 2, 3)


SQL_MSF = """
    SELECT permno, date, prc, shrout
    FROM   {table}
    WHERE  date BETWEEN '{start}' AND '{end}'
      AND  prc IS NOT NULL
      AND  shrout IS NOT NULL
"""


def screen_permnos(msf: pd.DataFrame,
                   names: pd.DataFrame,
                   screen_k: int = 750) -> np.ndarray:
    """Union of permnos ever in the top `screen_k` by month-end market cap.

    This is a PRE-SCREEN for the data pull, not the universe rule. It exists only
    to keep the daily pull tractable. It must be generous enough that it cannot
    bind: any permno that could ever appear in a top-N universe (N <= 500) must
    survive it.
    """
    m = msf.copy()
    m["date"] = pd.to_datetime(m["date"])
    m["permno"] = m["permno"].astype(int)
    m["mktcap"] = m["prc"].abs() * m["shrout"]
    m = m[m["mktcap"] > 0]

    # share-code / exchange filter, applied POINT-IN-TIME via the names spells
    nm = names.copy()
    nm["permno"] = nm["permno"].astype(int)
    nm["namedt"] = pd.to_datetime(nm["namedt"])
    nm["nameendt"] = pd.to_datetime(nm["nameendt"])
    nm = nm[nm["shrcd"].isin(VALID_SHRCD) & nm["exchcd"].isin(VALID_EXCHCD)]

    m = m.merge(nm[["permno", "namedt", "nameendt"]], on="permno", how="inner")
    m = m[(m["date"] >= m["namedt"]) & (m["date"] <= m["nameendt"])]

    keep = set()
    for _, grp in m.groupby("date"):
        top = grp.nlargest(screen_k, "mktcap")
        keep.update(top["permno"].tolist())

    return np.array(sorted(keep), dtype=int)


def eligibility_spells(names: pd.DataFrame, end: str) -> pd.DataFrame:
    """Build 'membership' spells for the CRSP-native universe.

    KEY IDEA: the downstream pipeline is unchanged. `Panels.is_member(date)` asks
    'is this permno in the universe on this date'. For the S&P 500 that meant
    'in the index'. Here it means 'a US ordinary common share listed on a major
    exchange'. The top-N-by-lagged-market-cap cut then happens exactly where it
    always did, in `universe.UniverseBuilder`.

    So the universe rule changes and NOT ONE LINE of the allocation, clustering,
    regime or backtest code has to know. Same schema: permno, mbrstartdt, mbrenddt.
    """
    nm = names.copy()
    nm["permno"] = nm["permno"].astype(int)
    nm["namedt"] = pd.to_datetime(nm["namedt"])
    nm["nameendt"] = pd.to_datetime(nm["nameendt"]).fillna(pd.Timestamp(end))

    ok = nm[nm["shrcd"].isin(VALID_SHRCD) & nm["exchcd"].isin(VALID_EXCHCD)]

    spells = (ok[["permno", "namedt", "nameendt"]]
              .rename(columns={"namedt": "mbrstartdt", "nameendt": "mbrenddt"})
              .sort_values(["permno", "mbrstartdt"])
              .reset_index(drop=True))

    # A permno gets a new names row on every ticker/exchange change, so its
    # eligibility is fragmented into many adjacent spells. Merge contiguous ones,
    # otherwise the spell count is meaningless and `is_member` does more work than
    # it needs to.
    out = []
    for permno, grp in spells.groupby("permno"):
        cur_s = cur_e = None
        for _, r in grp.iterrows():
            if cur_s is None:
                cur_s, cur_e = r.mbrstartdt, r.mbrenddt
            elif r.mbrstartdt <= cur_e + pd.Timedelta(days=5):
                cur_e = max(cur_e, r.mbrenddt)
            else:
                out.append({"permno": permno, "mbrstartdt": cur_s, "mbrenddt": cur_e})
                cur_s, cur_e = r.mbrstartdt, r.mbrenddt
        if cur_s is not None:
            out.append({"permno": permno, "mbrstartdt": cur_s, "mbrenddt": cur_e})

    return pd.DataFrame(out)
