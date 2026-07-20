"""
rac_hrp.data.membership_compustat
=================================
Point-in-time S&P 500 membership WITHOUT the CRSP index files and WITHOUT CCM.

WHY THIS EXISTS
---------------
The canonical source is `crsp.dsp500list` (CRSP index product). Failing that, the
standard substitute is Compustat constituents joined to CRSP through the
CRSP/Compustat Merged link table (`crsp.ccmxpf_lnkhist`).

Some subscriptions license Compustat but not CCM. That is the case here. So we
fall back one further, to the pre-CCM method: link on CUSIP.

    comp.idxcst_his   gvkey, iid, from, thru      (gvkeyx = '000003' -> S&P 500)
    comp.security     gvkey, iid, cusip           (9-char CUSIP)
    crsp.dsenames     permno, ncusip, cusip       (8-char; NCUSIP is HISTORICAL)

    join on:  comp.cusip[:8]  ==  crsp.ncusip

WHY CUSIP AND NOT TICKER. Tickers are recycled aggressively -- when a company
dies its ticker is handed to someone else, often within months. Matching on
ticker would silently attach a dead company's index membership to a completely
different living firm. CUSIPs are issuer-specific and are not reused. This is not
a stylistic preference; a ticker join would corrupt precisely the bankruptcies the
project exists to keep.

WHY NCUSIP AND NOT CUSIP ON THE CRSP SIDE. CRSP's `cusip` column is the LATEST
(header) CUSIP for a permno. `ncusip` is the CUSIP *as it stood at the time*.
Companies change CUSIP (reorganisations, share-class changes), so the header
CUSIP can miss a match that the historical one catches. We try NCUSIP first and
fall back to the header CUSIP.

WHAT THIS METHOD COSTS YOU -- BE HONEST ABOUT IT IN THE PAPER
-------------------------------------------------------------
CCM exists because CUSIP matching is imperfect. Known failure modes:
  * a gvkey/iid whose CUSIP never appears in CRSP (non-US listings, oddities)
  * multiple share classes mapping to one permno, or vice versa
  * CUSIP changes not reflected on one side at the moment of the change

So the match rate will NOT be 100%, and the residual is not random -- it skews
toward corporate-action-heavy names, which skews toward distress. The mitigation
is not to hope; it is to MEASURE. `build_membership` returns a full audit, and
the Phase 0.5 reconstruction gate (T3) then independently checks the result
against known S&P 500 history: index size ~500, ~22 changes/yr, and Enron /
Lehman / WaMu / GM actually leaving in the right year.

If the gate passes, the reconstruction is defensible and you say in the paper
exactly how it was built. If it fails, you do not have a universe, and no amount
of downstream cleverness will fix it.

REPORT THE MATCH RATE IN THE PAPER. A reviewer who sees "CUSIP-linked Compustat
constituents, 98.4% match rate, validated against known index history" will accept
it. One who sees an unexplained universe will not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

SP500_GVKEYX = "000003"


SQL_IDXCST = """
    SELECT gvkey, iid, "from" AS from_dt, thru AS thru_dt
    FROM   {table}
    WHERE  gvkeyx = '{gvkeyx}'
"""

SQL_SECURITY = """
    SELECT gvkey, iid, cusip, tic
    FROM   {table}
    WHERE  cusip IS NOT NULL
"""

SQL_DSENAMES_LINK = """
    SELECT permno, ncusip, cusip, namedt, nameendt, comnam, ticker
    FROM   {table}
    WHERE  ncusip IS NOT NULL
"""


@dataclass
class LinkAudit:
    n_constituents: int          # gvkey/iid spells in idxcst_his
    n_matched: int               # spells that resolved to a permno
    match_rate: float
    unmatched: pd.DataFrame      # the ones that did not resolve -- INSPECT THESE
    via_ncusip: int
    via_header_cusip: int

    def __str__(self) -> str:
        return (
            f"  CUSIP link audit\n"
            f"    constituent spells      {self.n_constituents:,}\n"
            f"    matched to a permno     {self.n_matched:,}  "
            f"({self.match_rate:.1%})\n"
            f"      via historical NCUSIP {self.via_ncusip:,}\n"
            f"      via header CUSIP      {self.via_header_cusip:,}\n"
            f"    UNMATCHED               {len(self.unmatched):,}\n"
        )


def build_membership(idxcst: pd.DataFrame,
                     security: pd.DataFrame,
                     dsenames: pd.DataFrame,
                     end: str) -> tuple[pd.DataFrame, LinkAudit]:
    """Return (membership_spells, audit) in the same schema `dsp500list` would give.

    Output columns: permno, mbrstartdt, mbrenddt -- so every downstream module is
    unchanged and cannot tell which route the membership came from.
    """
    idx = idxcst.copy()
    idx["gvkey"] = idx["gvkey"].astype(str).str.zfill(6)
    idx["iid"] = idx["iid"].astype(str).str.strip()
    idx["from_dt"] = pd.to_datetime(idx["from_dt"])
    idx["thru_dt"] = pd.to_datetime(idx["thru_dt"]).fillna(pd.Timestamp(end))

    sec = security.copy()
    sec["gvkey"] = sec["gvkey"].astype(str).str.zfill(6)
    sec["iid"] = sec["iid"].astype(str).str.strip()
    sec["cusip8"] = sec["cusip"].astype(str).str.strip().str[:8].str.upper()

    nm = dsenames.copy()
    nm["ncusip"] = nm["ncusip"].astype(str).str.strip().str.upper()
    nm["cusip"] = nm["cusip"].astype(str).str.strip().str.upper()

    # constituent spell -> its CUSIP
    a = idx.merge(sec[["gvkey", "iid", "cusip8", "tic"]],
                  on=["gvkey", "iid"], how="left")

    # CRSP side: one row per (permno, cusip). A permno can carry several NCUSIPs
    # over its life; any of them is a valid handle onto that permno.
    n1 = (nm[["permno", "ncusip"]].dropna()
            .drop_duplicates().rename(columns={"ncusip": "cusip8"}))
    n1["src"] = "ncusip"
    n2 = (nm[["permno", "cusip"]].dropna()
            .drop_duplicates().rename(columns={"cusip": "cusip8"}))
    n2["src"] = "header"
    # prefer the historical NCUSIP; header only fills what NCUSIP missed
    xwalk = pd.concat([n1, n2]).drop_duplicates(subset="cusip8", keep="first")

    b = a.merge(xwalk, on="cusip8", how="left")

    matched = b[b.permno.notna()].copy()
    unmatched = b[b.permno.isna()][["gvkey", "iid", "tic", "cusip8",
                                    "from_dt", "thru_dt"]].copy()

    matched["permno"] = matched["permno"].astype(int)
    memb = (matched[["permno", "from_dt", "thru_dt"]]
            .rename(columns={"from_dt": "mbrstartdt", "thru_dt": "mbrenddt"}))

    # One permno can appear twice if two share classes of the same issuer were
    # both in the index (rare but real: GOOG/GOOGL, BRK.A/BRK.B). Collapse
    # overlapping spells for the same permno rather than double-counting it.
    memb = memb.sort_values(["permno", "mbrstartdt"]).reset_index(drop=True)
    out = []
    for permno, grp in memb.groupby("permno"):
        cur_s, cur_e = None, None
        for _, r in grp.iterrows():
            if cur_s is None:
                cur_s, cur_e = r.mbrstartdt, r.mbrenddt
            elif r.mbrstartdt <= cur_e + pd.Timedelta(days=1):
                cur_e = max(cur_e, r.mbrenddt)          # merge overlap
            else:
                out.append({"permno": permno, "mbrstartdt": cur_s, "mbrenddt": cur_e})
                cur_s, cur_e = r.mbrstartdt, r.mbrenddt
        if cur_s is not None:
            out.append({"permno": permno, "mbrstartdt": cur_s, "mbrenddt": cur_e})

    membership = pd.DataFrame(out)

    audit = LinkAudit(
        n_constituents=len(a),
        n_matched=len(matched),
        match_rate=len(matched) / max(len(a), 1),
        unmatched=unmatched,
        via_ncusip=int((matched.src == "ncusip").sum()),
        via_header_cusip=int((matched.src == "header").sum()),
    )
    return membership, audit
