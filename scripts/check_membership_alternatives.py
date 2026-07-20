#!/usr/bin/env python
"""
Fallback membership sources.

Your subscription has CRSP STOCK (dsf, dsedelist, dsenames) but not CRSP INDEX
(crsp_a_indexes). So `dsp500list` -- the point-in-time S&P 500 membership spells
-- is unavailable, and that is the one table the whole project is built on.

There is exactly ONE legitimate substitute: Compustat's index-constituent history,
linked back to CRSP permnos through the CRSP/Compustat Merged link table.

    comp.idxcst_his        gvkey, gvkeyx, from, thru   (gvkeyx='000003' = S&P 500)
    crsp.ccmxpf_lnkhist    gvkey <-> permno, with valid link date ranges

This is a real, widely-used reconstruction, not a hack -- but it is NOT free. The
CCM link is many-to-many over time and has to be filtered properly
(linktype in ('LU','LC'), linkprim in ('P','C')), or you silently duplicate or
drop names. It is more moving parts than dsp500list, hence: only if you must.

WHAT IS *NOT* ACCEPTABLE, AND WHY
---------------------------------
Scraping today's S&P 500 constituent list (Wikipedia, a broker, an ETF holdings
file) and applying it backwards through 2000-2025. Every company in that list
survived to today BY CONSTRUCTION. Enron, Lehman, WaMu, GM, Bear Stearns,
Countrywide, Circuit City -- all gone, none in the list, none in your universe.
You would be backtesting on 25 years of known survivors. Sharpe goes up, the
result is meaningless, and it is unfixable after the fact.

That is the single most common fatal flaw in student quant-finance papers, and it
is the reason Phase 0.5 has a reconstruction gate at all.

    python scripts/check_membership_alternatives.py --user <you>
"""

from __future__ import annotations

import argparse
import sys

PROBES = [
    ("comp.idxcst_his",        "Compustat index constituents (S&P 500 = gvkeyx 000003)"),
    ("comp_na_daily_all.idxcst_his", "same, schema-qualified"),
    ("crsp.ccmxpf_lnkhist",    "CRSP/Compustat link history (gvkey <-> permno)"),
    ("crsp.ccmxpf_linktable",  "CCM link table (older name)"),
    ("crsp_a_ccm.ccmxpf_lnkhist", "same, schema-qualified"),
    ("comp.security",          "Compustat security master"),
    ("crsp.msp500list",        "monthly S&P 500 list (index product -- long shot)"),
    ("crsp.msix",              "CRSP index series (long shot)"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=None)
    a = ap.parse_args()

    import wrds
    db = wrds.Connection(wrds_username=a.user)

    print("\nProbing alternative membership routes.\n")
    ok = set()
    for table, purpose in PROBES:
        try:
            db.raw_sql(f"SELECT * FROM {table} LIMIT 1")
            status, good = "READABLE", True
        except Exception as e:
            m = str(e).lower()
            status = ("NO ACCESS" if "permission denied" in m
                      else "NOT THERE" if ("does not exist" in m or "undefined" in m)
                      else "ERROR")
            good = False
        if good:
            ok.add(table)
        print(f"  {status:10s} {table:32s} {purpose}")

    have_idx = any(t.endswith("idxcst_his") for t in ok)
    have_link = any("ccmxpf" in t for t in ok)

    print("\n" + "=" * 90)
    if have_idx and have_link:
        print("  VIABLE: Compustat route is open.")
        print("  comp.idxcst_his gives S&P 500 constituent spells; the CCM link maps")
        print("  gvkey -> permno so they join to the CRSP stock files you already have.")
        print("  Tell Claude and it will rewrite wrds_pull.py to use this route.")
        rc = 0
    elif have_idx and not have_link:
        print("  PARTIAL: you have Compustat constituents but NOT the CCM link table.")
        print("  Without the link you cannot map gvkey -> permno, so the constituents")
        print("  cannot be joined to CRSP returns. Ask the librarian for CCM.")
        rc = 1
    else:
        print("  BLOCKED: no usable membership source.")
        print("  You need either CRSP index files (crsp_a_indexes) or")
        print("  Compustat + CCM. Neither is available. This requires a librarian.")
        rc = 1

    print("\n  Under NO circumstances substitute a current constituent list.")
    print("  That is survivorship bias and it is fatal to the paper.")
    db.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
