"""
rac_hrp.data.panel
==================
Phase 0.5, Task 1 (cont.) -- raw CRSP tables -> analysis panels.

The load-bearing step here is the DELISTING SPLICE. CRSP's daily stock file
simply stops when a stock delists. If you build a returns panel straight from
`dsf`, every company that went to zero exits your data with a benign final
return, and the panel is quietly survivorship-biased even though the universe
was point-in-time. The bias runs in the direction that flatters the strategy.

The splice:
    combined_t = (1 + ret_t) * (1 + dlret_t) - 1     on the delisting date

Missing dlret is not rare, and it is not missing at random -- it is most often
missing precisely for performance-related delistings (bankruptcy, insufficient
capital). Following Shumway (1997), a missing dlret on a performance-related
delisting code is replaced with -30%, not with 0 and not dropped. Dropping it is
the survivorship bias, restated.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# Shumway (1997): performance-related delisting codes.
PERF_DELIST_CODES = set(range(500, 600)) | {400, 401}
SHUMWAY_MISSING_DLRET = -0.30


@dataclass
class Panels:
    """The analysis-ready data layer. N-invariant: nothing here knows about N."""
    returns: pd.DataFrame      # date x permno, delisting-spliced simple returns
    mcap: pd.DataFrame         # date x permno, market cap ($000s)
    membership: pd.DataFrame   # permno, mbrstartdt, mbrenddt
    rf: pd.Series              # date -> daily risk-free rate
    delist_audit: pd.DataFrame # what the splice actually did (for the report)

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.returns.index

    def is_member(self, date: pd.Timestamp) -> np.ndarray:
        """Boolean mask over self.returns.columns: S&P 500 member ON `date`."""
        m = self.membership
        live = m[(m.mbrstartdt <= date) & (m.mbrenddt >= date)]
        return self.returns.columns.isin(live.permno.values)


def _splice_delisting(dsf: pd.DataFrame,
                      delist: pd.DataFrame,
                      shumway: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fold delisting returns into the daily return series.

    Returns (spliced_dsf, audit). The audit frame is not decoration: Phase 0.5's
    gate requires showing the reconstruction is right, and "how many delistings
    did you splice, and how many needed the Shumway fill" is the evidence.
    """
    if delist is None or len(delist) == 0:
        audit = pd.DataFrame(columns=["permno", "dlstdt", "dlret", "dlstcd",
                                      "source", "had_dsf_row"])
        return dsf.copy(), audit

    d = delist.copy()
    d["dlstdt"] = pd.to_datetime(d["dlstdt"])
    d["source"] = "crsp_dlret"

    # CRITICAL: the delisting table covers ALL of CRSP -- every permno that ever
    # died, ~28,000 of them. Our panel covers only the permnos we pulled. An outer
    # merge against the raw table therefore injects ~25,000 phantom columns that
    # have a delisting row and no returns, ballooning the panel to 1.7GB of NaN
    # and quietly corrupting every downstream shape check.
    #
    # Restrict the splice to permnos we actually hold. The outer merge is still
    # needed AFTER this filter, because a stock's delisting date can fall one day
    # after its last row in dsf -- that row must be created, not dropped. That is
    # the whole point of the splice.
    ours = set(dsf["permno"].unique().tolist())
    d = d[d["permno"].isin(ours)]

    missing = d["dlret"].isna()
    if shumway:
        perf = d["dlstcd"].isin(PERF_DELIST_CODES)
        fill = missing & perf
        d.loc[fill, "dlret"] = SHUMWAY_MISSING_DLRET
        d.loc[fill, "source"] = "shumway_-0.30"
        # Missing + non-performance delisting (merger, exchange move) -> 0.
        drop = missing & ~perf
        d.loc[drop, "dlret"] = 0.0
        d.loc[drop, "source"] = "nonperf_zero"
    else:
        d = d[~missing]

    df = dsf.copy()
    df["date"] = pd.to_datetime(df["date"])
    key = ["permno", "date"]
    d2 = d.rename(columns={"dlstdt": "date"})[["permno", "date", "dlret",
                                               "dlstcd", "source"]]

    merged = df.merge(d2, on=key, how="outer", indicator=True)
    merged["had_dsf_row"] = merged["_merge"] != "right_only"

    has_dl = merged["dlret"].notna()
    r = merged["ret"].fillna(0.0)
    merged.loc[has_dl, "ret"] = (1.0 + r[has_dl]) * (1.0 + merged.loc[has_dl, "dlret"]) - 1.0

    audit = merged.loc[has_dl, ["permno", "date", "dlret", "dlstcd",
                                "source", "had_dsf_row"]].copy()
    audit = audit.rename(columns={"date": "dlstdt"})

    merged = merged.drop(columns=["_merge", "dlret", "dlstcd", "source",
                                  "had_dsf_row"])
    return merged, audit


def _clip_to_names(returns: pd.DataFrame,
                   mcap: pd.DataFrame,
                   names: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Blank any (permno, date) outside that permno's valid names spells.

    CRSP REUSES PERMNOS. A permno identifies a security, and when a security is
    delisted its permno can later be assigned to a different company. Washington
    Mutual (permno 81593) died in September 2008; the same permno was reassigned to
    an unrelated security that began trading in 2015. A naive pivot of the daily
    file fuses the two into a single 30-year column -- WaMu's collapse followed,
    seven years later, by a different company's price history.

    Left unclipped this is not just a validation nuisance. Any covariance window
    that straddles the 2008->2015 seam mixes two unrelated return series under one
    identity, silently corrupting the correlation matrix, the clustering, and every
    weight derived from it. The names table is the authority on when a permno was
    which company, so we clip every permno to the union of its own names spells and
    blank everything else.
    """
    nm = names.copy()
    nm["permno"] = nm["permno"].astype(int)
    nm["namedt"] = pd.to_datetime(nm["namedt"])
    nm["nameendt"] = pd.to_datetime(nm["nameendt"])

    idx = returns.index
    n_blanked = 0
    valid = pd.DataFrame(False, index=idx, columns=returns.columns)
    for permno, grp in nm.groupby("permno"):
        if permno not in valid.columns:
            continue
        col = np.zeros(len(idx), dtype=bool)
        for _, r in grp.iterrows():
            col |= (idx >= r.namedt) & (idx <= r.nameendt)
        valid[permno] = col

    before = returns.notna().sum().sum()
    returns = returns.where(valid)
    mcap = mcap.where(valid)
    n_blanked = int(before - returns.notna().sum().sum())
    return returns, mcap, n_blanked


def build_panels(raw_dir: str,
                 shumway: bool = True,
                 share_code_filter: bool = True) -> Panels:
    """Load the five raw parquet files and produce the analysis panels."""
    p = lambda f: os.path.join(raw_dir, f)  # noqa: E731

    dsf = pd.read_parquet(p("dsf.parquet"))
    memb = pd.read_parquet(p("membership.parquet"))
    delist = pd.read_parquet(p("delist.parquet"))
    rf_df = pd.read_parquet(p("rf.parquet"))
    names = pd.read_parquet(p("names.parquet")) if os.path.exists(p("names.parquet")) else None

    dsf["date"] = pd.to_datetime(dsf["date"])
    memb["mbrstartdt"] = pd.to_datetime(memb["mbrstartdt"])
    memb["mbrenddt"] = pd.to_datetime(memb["mbrenddt"])

    # Ordinary common shares on NYSE/AMEX/Nasdaq. The S&P 500 satisfies this by
    # construction, so this is a validation screen, not a filter that should bite.
    if share_code_filter and names is not None and len(names):
        ok = names[names["shrcd"].isin([10, 11]) & names["exchcd"].isin([1, 2, 3])]
        dsf = dsf[dsf["permno"].isin(ok["permno"].unique())]

    dsf, audit = _splice_delisting(dsf, delist, shumway=shumway)

    # CRSP prices are negative when they are bid/ask midpoints rather than trades.
    dsf["prc_abs"] = dsf["prc"].abs()
    dsf["mktcap"] = dsf["prc_abs"] * dsf["shrout"]

    returns = dsf.pivot_table(index="date", columns="permno", values="ret",
                              aggfunc="last").sort_index()
    mcap = dsf.pivot_table(index="date", columns="permno", values="mktcap",
                           aggfunc="last").sort_index()
    mcap = mcap.reindex(index=returns.index, columns=returns.columns)

    # Force float64. On real CRSP data the pivot can produce object-dtype columns
    # (mixed int/float/None from the raw file), which np.isfinite rejects and which
    # trips pandas' fillna downcasting warnings all through the backtest. Mock data
    # was uniformly float, so this only ever bites on the real pull. Coercing once
    # here fixes both the null-gate crash and the FutureWarning spam at the source.
    returns = returns.astype("float64")
    mcap = mcap.astype("float64")

    rf_df["date"] = pd.to_datetime(rf_df["date"])
    rf = rf_df.set_index("date")["rf"].reindex(returns.index).ffill().fillna(0.0)

    return Panels(returns=returns, mcap=mcap, membership=memb, rf=rf,
                  delist_audit=audit)
