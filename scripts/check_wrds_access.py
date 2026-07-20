#!/usr/bin/env python
"""
Which CRSP tables can you ACTUALLY read?

WRDS distinguishes two things that look identical from Python:
  * a table you can SEE        (it appears in list_tables)
  * a table you can SELECT FROM (your institution licensed that product)

`wrds_pull.py` originally auto-detected the CRSP vintage by LISTING tables. That
is wrong: it happily found `dsp500list_v2`, chose the CIZ path, and then died with
`permission denied for schema crsp_a_indexes`. The only reliable probe is to run a
one-row SELECT and see whether it comes back.

Run this before the real pull:

    python scripts/check_wrds_access.py --user <your_wrds_username>
"""

from __future__ import annotations

import argparse
import sys

CANDIDATES = [
    # (label, library.table, what it's for)
    ("membership  SIZ", "crsp.dsp500list",     "point-in-time S&P 500 spells (legacy)"),
    ("membership  SIZ", "crsp_a_indexes.dsp500list", "same, schema-qualified"),
    ("membership  CIZ", "crsp.dsp500list_v2",  "point-in-time S&P 500 spells (v2)"),
    ("dailystock  SIZ", "crsp.dsf",            "daily returns/prices (legacy)"),
    ("dailystock  SIZ", "crsp_a_stock.dsf",    "same, schema-qualified"),
    ("dailystock  CIZ", "crsp.dsf_v2",         "daily returns/prices (v2)"),
    ("delisting   SIZ", "crsp.dsedelist",      "delisting returns (legacy)"),
    ("delisting   SIZ", "crsp_a_stock.dsedelist", "same, schema-qualified"),
    ("names       SIZ", "crsp.dsenames",       "share codes / tickers (legacy)"),
    ("names       SIZ", "crsp_a_stock.dsenames", "same, schema-qualified"),
    ("names       CIZ", "crsp.stksecurityinfohist_v2", "security info (v2)"),
    ("riskfree",        "ff.factors_daily",    "Fama-French daily rf"),
    ("riskfree",        "ff_all.factors_daily", "same, alternate library"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=None)
    a = ap.parse_args()

    try:
        import wrds
    except ImportError:
        print("pip install wrds")
        return 1

    db = wrds.Connection(wrds_username=a.user)
    print("\nProbing each table with a 1-row SELECT. Visibility != permission.\n")
    print(f"  {'STATUS':10s} {'TABLE':36s} {'PURPOSE'}")
    print("  " + "-" * 92)

    ok = {}
    for label, table, purpose in CANDIDATES:
        try:
            db.raw_sql(f"SELECT * FROM {table} LIMIT 1")
            status = "READABLE"
            ok.setdefault(label.split()[0], []).append(table)
        except Exception as e:
            msg = str(e).lower()
            if "permission denied" in msg:
                status = "NO ACCESS"
            elif "does not exist" in msg or "undefined" in msg:
                status = "NOT THERE"
            else:
                status = "ERROR"
        print(f"  {status:10s} {table:36s} {purpose}")

    print("\n" + "=" * 94)
    need = ["membership", "dailystock", "delisting", "names", "riskfree"]
    missing = [n for n in need if n not in ok]

    for n in need:
        got = ok.get(n)
        print(f"  {n:12s} -> {got[0] if got else '*** NOTHING READABLE ***'}")

    if missing:
        print(f"\n  MISSING: {', '.join(missing)}")
        print("  You cannot build a survivorship-bias-free universe without all of")
        print("  membership + dailystock + delisting. Contact your WRDS librarian and")
        print("  ask specifically which CRSP product your institution licenses.")
        db.close()
        return 1

    print("\n  All required components are readable. Run the pull.")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
