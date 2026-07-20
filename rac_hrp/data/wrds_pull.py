"""
rac_hrp.data.wrds_pull
======================
Phase 0.5, Task 1 -- CRSP point-in-time data pull.

THIS IS THE ONLY MODULE THAT REQUIRES WRDS CREDENTIALS AND NETWORK ACCESS.
It cannot run in a sandbox. Run it once on your own machine:

    python -m rac_hrp.data.wrds_pull --outdir data/raw

It writes five parquet files that every other module in the project consumes.
After that, the entire pipeline is offline and reproducible.

Outputs
-------
  membership.parquet   permno, mbrstartdt, mbrenddt        (S&P 500 spells)
  dsf.parquet          permno, date, ret, prc, shrout, cfacpr, cfacshr
  delist.parquet       permno, dlstdt, dlret, dlstcd
  names.parquet        permno, namedt, nameendt, shrcd, exchcd, ticker, comnam
  rf.parquet           date, rf                            (Fama-French daily)

Notes on WRDS table naming
--------------------------
WRDS addresses everything as `library.table`. CRSP has two vintages:

  LEGACY (SIZ):  crsp.dsp500list      cols: permno, start,      ending
                 crsp.dsf             cols: permno, date, ret, prc, shrout
                 crsp.dsedelist       cols: permno, dlstdt, dlret, dlstcd
                 crsp.dsenames        cols: permno, namedt, nameendt, shrcd, exchcd

  V2 (CIZ):      crsp.dsp500list_v2   cols: permno, mbrstartdt, mbrenddt
                 crsp.dsf_v2          cols: permno, dlycaldt, dlyret, dlyprc, ...
                 (delisting is folded INTO dsf_v2 as dlyretx/dlydelflg)

This script auto-detects which vintage your subscription exposes and normalises
column names, so downstream code sees one schema either way.
"""

from __future__ import annotations

import argparse
import os
from typing import Optional

import pandas as pd

from ..config import DATA_START, TEST_END


# --------------------------------------------------------------------------
# SQL
# --------------------------------------------------------------------------

SQL_MEMBERSHIP_LEGACY = """
    SELECT permno, start AS mbrstartdt, ending AS mbrenddt
    FROM   {table}
    WHERE  ending >= '{start}'
"""

SQL_MEMBERSHIP_V2 = """
    SELECT permno, mbrstartdt, mbrenddt
    FROM   {table}
    WHERE  mbrenddt >= '{start}'
"""

SQL_DSF_LEGACY = """
    SELECT a.permno, a.date, a.ret, a.prc, a.shrout, a.cfacpr, a.cfacshr
    FROM   {table} AS a
    WHERE  a.date BETWEEN '{start}' AND '{end}'
      AND  a.permno IN ({permnos})
"""

SQL_DSF_V2 = """
    SELECT permno,
           dlycaldt  AS date,
           dlyret    AS ret,
           dlyprc    AS prc,
           shrout,
           dlyfacprc AS cfacpr
    FROM   {table}
    WHERE  dlycaldt BETWEEN '{start}' AND '{end}'
      AND  permno IN ({permnos})
"""

SQL_DELIST = """
    SELECT permno, dlstdt, dlret, dlstcd
    FROM   {table}
    WHERE  dlstdt BETWEEN '{start}' AND '{end}'
"""

SQL_NAMES = """
    SELECT permno, namedt, nameendt, shrcd, exchcd, ticker, comnam
    FROM   {table}
    WHERE  nameendt >= '{start}'
"""

SQL_RF = """
    SELECT date, rf
    FROM   {table}
    WHERE  date BETWEEN '{start}' AND '{end}'
"""


def _readable(db, table: str) -> bool:
    """Can we ACTUALLY select from this table?

    NOT `table in db.list_tables(...)`. WRDS will happily list a table your
    institution has not licensed; the permission error only surfaces when you
    query it. The original version of this file detected the CRSP vintage by
    listing, found `dsp500list_v2`, chose the CIZ path, and then died with
    `permission denied for schema crsp_a_indexes`. Visibility is not permission.
    The only honest probe is to try.
    """
    try:
        db.raw_sql(f"SELECT * FROM {table} LIMIT 1")
        return True
    except Exception:
        return False


def _first_readable(db, candidates: list[str], what: str) -> str:
    for t in candidates:
        if _readable(db, t):
            return t
    raise SystemExit(
        f"\nCannot read any {what} table. Tried:\n"
        + "".join(f"    {t}\n" for t in candidates)
        + "\nRun `python scripts/check_wrds_access.py --user <you>` to see exactly\n"
          "what your subscription exposes, then talk to your WRDS librarian.\n"
    )


def pull(outdir: str,
         start: str = DATA_START,
         end: str = TEST_END,
         wrds_username: Optional[str] = None,
         universe: str = "sp500",
         screen_k: int = 750) -> None:
    try:
        import wrds  # noqa
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "The `wrds` package is not installed.\n"
            "    pip install wrds\n"
            "Then run this script again on a machine that can reach wrds-cloud."
        ) from exc

    os.makedirs(outdir, exist_ok=True)
    db = wrds.Connection(wrds_username=wrds_username)

    nm_tbl = _first_readable(
        db, ["crsp.dsenames", "crsp_a_stock.dsenames"], "CRSP names")

    # ==================================================================
    # UNIVERSE ROUTE
    # ==================================================================
    if universe == "crsp_largecap":
        from .crsp_universe import (screen_permnos, eligibility_spells, SQL_MSF)

        print("[1/5] universe = CRSP LARGE-CAP  (D1 AMENDED)")
        print("      N largest US common stocks by lagged market cap.")
        print("      shrcd in (10,11), exchcd in (1,2,3), delisting spliced.")
        print("      Chosen because S&P US constituent HISTORY is not licensed to")
        print("      this account -- see rac_hrp/data/crsp_universe.py.\n")

        names = db.raw_sql(SQL_NAMES.format(start=start, table=nm_tbl),
                           date_cols=["namedt", "nameendt"])
        names["permno"] = names["permno"].astype(int)
        names["nameendt"] = names["nameendt"].fillna(pd.Timestamp(end))
        names.to_parquet(os.path.join(outdir, "names.parquet"), index=False)

        # -- two-stage pull: pre-screen on the MONTHLY file --------------
        msf_tbl = _first_readable(
            db, ["crsp.msf", "crsp_a_stock.msf"], "CRSP monthly stock")
        print(f"      pre-screening on {msf_tbl} (keeps the daily pull tractable)")
        msf = db.raw_sql(SQL_MSF.format(table=msf_tbl, start=start, end=end),
                         date_cols=["date"])
        print(f"      {len(msf):,} monthly rows")

        permnos = screen_permnos(msf, names, screen_k=screen_k)
        print(f"      permnos ever inside the top {screen_k} by month-end mcap: "
              f"{len(permnos):,}")
        print("      (this is a PULL pre-screen, not the universe rule -- it is")
        print("       generous enough that it cannot bind on a top-500 universe)")

        memb = eligibility_spells(names, end=end)
        memb = memb[memb.permno.isin(permnos)]
        memb = memb[memb.mbrenddt >= pd.Timestamp(start)]
        memb.to_parquet(os.path.join(outdir, "membership.parquet"), index=False)
        print(f"      {len(memb):,} eligibility spells, "
              f"{memb.permno.nunique():,} permnos")

    else:
        # ---- S&P 500: CRSP index files, else Compustat+CUSIP -------------
        memb_tbl = None
        for t in ["crsp.dsp500list", "crsp_a_indexes.dsp500list",
                  "crsp.dsp500list_v2"]:
            if _readable(db, t):
                memb_tbl = t
                break

        if memb_tbl is not None:
            v2 = memb_tbl.endswith("_v2")
            print(f"[1/5] membership via CRSP index files ({memb_tbl}) "
                  f"[{'CIZ/v2' if v2 else 'SIZ/legacy'}]")
            sql = (SQL_MEMBERSHIP_V2 if v2 else SQL_MEMBERSHIP_LEGACY).format(
                start=start, table=memb_tbl)
            memb = db.raw_sql(sql, date_cols=["mbrstartdt", "mbrenddt"])
            memb["permno"] = memb["permno"].astype(int)
            memb["mbrenddt"] = memb["mbrenddt"].fillna(pd.Timestamp(end))
        else:
            from .membership_compustat import (
                build_membership, SQL_IDXCST, SQL_SECURITY, SQL_DSENAMES_LINK,
                SP500_GVKEYX)
            idx_tbl = _first_readable(
                db, ["comp.idxcst_his", "comp_na_daily_all.idxcst_his"],
                "Compustat index constituents")
            sec_tbl = _first_readable(db, ["comp.security"], "Compustat security")
            print("[1/5] membership via COMPUSTAT + CUSIP LINK")
            idxcst = db.raw_sql(
                SQL_IDXCST.format(table=idx_tbl, gvkeyx=SP500_GVKEYX),
                date_cols=["from_dt", "thru_dt"])
            security = db.raw_sql(SQL_SECURITY.format(table=sec_tbl))
            dsenames = db.raw_sql(SQL_DSENAMES_LINK.format(table=nm_tbl),
                                  date_cols=["namedt", "nameendt"])
            memb, audit = build_membership(idxcst, security, dsenames, end=end)
            print()
            print(audit)
            n_exits = int((memb.mbrenddt < pd.Timestamp(end)).sum())
            if n_exits == 0:
                db.close()
                raise SystemExit(
                    "\n*** ZERO INDEX EXITS. ***\n"
                    "Every constituent is still a member. That is a CURRENT\n"
                    "constituent list, not a history -- S&P US constituent history\n"
                    "is a premium license this account does not hold.\n\n"
                    "Using it would be survivorship bias. Re-run with:\n"
                    "    --universe crsp_largecap\n")

        memb = memb[memb.mbrenddt >= pd.Timestamp(start)]
        memb.to_parquet(os.path.join(outdir, "membership.parquet"), index=False)
        print(f"      {len(memb):,} membership spells, "
              f"{memb.permno.nunique():,} permnos")

        names = db.raw_sql(SQL_NAMES.format(start=start, table=nm_tbl),
                           date_cols=["namedt", "nameendt"])
        names["permno"] = names["permno"].astype(int)
        names["nameendt"] = names["nameendt"].fillna(pd.Timestamp(end))
        names.to_parquet(os.path.join(outdir, "names.parquet"), index=False)
        permnos = sorted(memb.permno.unique().tolist())

    permno_list = ",".join(str(int(p)) for p in permnos)

    # ---- 2. daily stock file ---------------------------------------------
    dsf_tbl = _first_readable(
        db, ["crsp.dsf", "crsp_a_stock.dsf", "crsp.dsf_v2"], "daily stock")
    dsf_v2 = dsf_tbl.endswith("_v2")
    sql = (SQL_DSF_V2 if dsf_v2 else SQL_DSF_LEGACY).format(
        start=start, end=end, permnos=permno_list, table=dsf_tbl)
    print(f"[2/5] daily stock file via {dsf_tbl}")
    print("      (this is the slow one -- expect several minutes)")
    dsf = db.raw_sql(sql, date_cols=["date"])
    dsf["permno"] = dsf["permno"].astype(int)
    if "cfacshr" not in dsf.columns:
        dsf["cfacshr"] = 1.0
    dsf.to_parquet(os.path.join(outdir, "dsf.parquet"), index=False)
    print(f"      {len(dsf):,} permno-days")

    # ---- 3. delisting returns (the survivorship splice) ------------------
    print("[3/5] delisting returns")
    if dsf_v2:
        # CIZ folds delisting into dsf_v2; emit an empty frame with the right
        # schema so panel.py's splice step is a no-op rather than a branch.
        delist = pd.DataFrame(columns=["permno", "dlstdt", "dlret", "dlstcd"])
        print("      CIZ vintage: delisting already embedded in dsf_v2 returns")
    else:
        dl_tbl = _first_readable(
            db, ["crsp.dsedelist", "crsp_a_stock.dsedelist"], "delisting")
        delist = db.raw_sql(SQL_DELIST.format(start=start, end=end, table=dl_tbl),
                            date_cols=["dlstdt"])
        delist["permno"] = delist["permno"].astype(int)
        print(f"      {len(delist):,} delisting events via {dl_tbl}")
        if len(delist) == 0:
            print("      *** WARNING: ZERO delisting events on a LEGACY pull.")
            print("      *** That is survivorship bias. Do not proceed. ***")
    delist.to_parquet(os.path.join(outdir, "delist.parquet"), index=False)

    # ---- 4. names -- already pulled and written by the universe route -----
    print("[4/5] names (already written by the universe step)")

    # ---- 5. risk-free rate ------------------------------------------------
    print("[5/5] risk-free rate (Fama-French daily)")
    rf_tbl = _first_readable(
        db, ["ff.factors_daily", "ff_all.factors_daily"], "risk-free rate")
    rf = db.raw_sql(SQL_RF.format(start=start, end=end, table=rf_tbl),
                    date_cols=["date"])
    rf.to_parquet(os.path.join(outdir, "rf.parquet"), index=False)

    db.close()
    print(f"\nDone. Five parquet files written to {outdir}/")
    print("Next:  python scripts/run_phase05.py --raw data/raw --n 100 --reps 50")


def main() -> None:
    ap = argparse.ArgumentParser(description="CRSP point-in-time pull for RAC-HRP")
    ap.add_argument("--outdir", default="data/raw")
    ap.add_argument("--start", default=DATA_START)
    ap.add_argument("--end", default=TEST_END)
    ap.add_argument("--user", default=None, help="WRDS username")
    ap.add_argument("--universe", default="sp500",
                    choices=["sp500", "crsp_largecap"],
                    help="sp500 needs CRSP index files or licensed S&P history; "
                         "crsp_largecap needs only the CRSP stock files (D1 AMENDED)")
    ap.add_argument("--screen-k", type=int, default=750,
                    help="pull pre-screen: keep permnos ever in the top-K by "
                         "month-end market cap (must exceed the largest N used)")
    a = ap.parse_args()
    pull(a.outdir, a.start, a.end, a.user, a.universe, a.screen_k)


if __name__ == "__main__":
    main()
