#!/usr/bin/env python
"""
Why does idxcst_his have no exits?

`comp.idxcst_his` returned 503 rows for gvkeyx='000003', all with a NULL `thru`.
That is today's index, not its history. Over 2000-2025 there should be ~1,000+
spells and a fat cluster of exits around 2008-09.

Something is wrong with WHICH table or WHICH key we are reading. This script
dumps the raw facts so we stop guessing:

    python scripts/diagnose_idxcst.py --user opatel4
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=None)
    a = ap.parse_args()

    import wrds
    db = wrds.Connection(wrds_username=a.user)

    for tbl in ["comp.idxcst_his", "comp_na_daily_all.idxcst_his"]:
        print("\n" + "=" * 78)
        print(f"  {tbl}")
        print("=" * 78)
        try:
            df = db.raw_sql(f"SELECT * FROM {tbl} LIMIT 5")
        except Exception as e:
            print(f"  unreadable: {e}")
            continue

        print("\n  COLUMNS:", list(df.columns))
        print("\n  SAMPLE ROWS:")
        print(df.to_string(index=False))

        # total rows, and rows per index
        try:
            n = db.raw_sql(f"SELECT COUNT(*) AS n FROM {tbl}")["n"].iloc[0]
            print(f"\n  TOTAL ROWS (all indices): {int(n):,}")
        except Exception as e:
            print(f"  count failed: {e}")

        # which index codes exist, and how many constituents each has
        try:
            top = db.raw_sql(f"""
                SELECT gvkeyx, COUNT(*) AS n_spells
                FROM   {tbl}
                GROUP BY gvkeyx
                ORDER BY n_spells DESC
                LIMIT 15
            """)
            print("\n  BIGGEST INDICES BY SPELL COUNT:")
            print("  (S&P 500 should be one of the largest -- ~1,000+ spells since 1990.")
            print("   If 000003 shows ~500, we are reading a CURRENT snapshot.)")
            print(top.to_string(index=False))
        except Exception as e:
            print(f"  groupby failed: {e}")

        # the S&P 500 specifically: how many have an exit date?
        try:
            sp = db.raw_sql(f"""
                SELECT COUNT(*) AS total,
                       COUNT(thru) AS with_exit_date
                FROM   {tbl}
                WHERE  gvkeyx = '000003'
            """)
            print("\n  gvkeyx = '000003' (S&P 500):")
            print(sp.to_string(index=False))
        except Exception as e:
            print(f"  sp500 count failed: {e}")

    # Does a separate historical/CIQ constituents table exist?
    print("\n" + "=" * 78)
    print("  OTHER CANDIDATE CONSTITUENT TABLES")
    print("=" * 78)
    for t in [
        "comp.idxcst_his",
        "comp.idx_index",
        "comp.idx_ann",
        "ciq.ciqindexconstituent",
        "ciq_common.ciqindexconstituent",
        "comp_na_annual_all.idxcst_his",
        "compa.idxcst_his",
        "crsp.dsp500list",
    ]:
        try:
            db.raw_sql(f"SELECT * FROM {t} LIMIT 1")
            print(f"  READABLE   {t}")
        except Exception as e:
            m = str(e).lower()
            s = ("NO ACCESS" if "permission denied" in m
                 else "NOT THERE" if ("does not exist" in m or "undefined" in m)
                 else "ERROR")
            print(f"  {s:10s} {t}")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
