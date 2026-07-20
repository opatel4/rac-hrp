"""
rac_hrp.data.mock
=================
Synthetic CRSP-shaped raw tables.

WHY THIS EXISTS. Phase 0.5 has to prove the *machinery* is correct before it is
pointed at real data. If the first time you run the pipeline end-to-end is also
the first time you have real CRSP data in hand, then every bug you hit is
ambiguous: is the pipeline broken, or is the data pull wrong? This module cuts
that knot. It emits the exact five-table schema `wrds_pull.py` writes, so every
downstream module can be exercised, unit-tested and null-gated with no network.

IT IS NOT A DATA SOURCE. No number produced from mock data belongs in the paper.
The generator writes a `MOCK` sentinel file into the output directory, and the
Phase 0.5 runner prints a loud banner whenever it finds one.

The generative process is deliberately built to have the features the pipeline
must handle:
  * a 2-state Markov volatility/correlation regime (crisis = higher market beta
    dispersion AND higher factor share -> a genuinely moving absorption ratio)
  * sector factors, so clustering has something real to find
  * index churn (~22 changes/yr) with genuine delistings that go to near-zero
  * missing history for new entrants, so the eligibility screen actually bites
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

MOCK_SENTINEL = "_MOCK_DATA_DO_NOT_PUBLISH"


def generate(outdir: str,
             start: str = "1995-01-03",
             end: str = "2025-11-28",
             n_pool: int = 900,
             index_size: int = 500,
             n_sectors: int = 11,
             changes_per_year: int = 22,
             universe: str = "sp500",
             seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    os.makedirs(outdir, exist_ok=True)

    dates = pd.bdate_range(start, end)
    T = len(dates)
    permnos = np.arange(10001, 10001 + n_pool)

    # ---- regime process: 2-state Markov (calm / crisis) ------------------
    p_stay_calm, p_stay_crisis = 0.997, 0.985
    state = np.zeros(T, dtype=int)
    for t in range(1, T):
        u = rng.random()
        if state[t - 1] == 0:
            state[t] = 0 if u < p_stay_calm else 1
        else:
            state[t] = 1 if u < p_stay_crisis else 0

    mkt_vol = np.where(state == 0, 0.008, 0.022)
    # In crisis the market factor absorbs more variance: idio vol falls relative
    # to factor vol, which is precisely what the absorption ratio should detect.
    idio_vol = np.where(state == 0, 0.016, 0.018)
    sector_vol = np.where(state == 0, 0.006, 0.009)

    sector = rng.integers(0, n_sectors, size=n_pool)
    beta = rng.normal(1.0, 0.35, size=n_pool).clip(0.2, 2.2)
    sector_load = rng.normal(1.0, 0.25, size=n_pool).clip(0.2, 2.0)

    f_mkt = rng.standard_normal(T) * mkt_vol
    f_sec = rng.standard_normal((T, n_sectors)) * sector_vol[:, None]
    eps = rng.standard_normal((T, n_pool)) * idio_vol[:, None]

    rets = (f_mkt[:, None] * beta[None, :]
            + f_sec[:, sector] * sector_load[None, :]
            + eps)
    # crisis beta amplification -> correlation regime shift, not just vol
    rets[state == 1] *= 1.15

    R = pd.DataFrame(rets, index=dates, columns=permnos)

    # ---- listing lifetimes ------------------------------------------------
    # Every name has a listing date; late entrants have short history, which is
    # what makes the eligibility screen (and its seasoning bias) real.
    list_pos = np.zeros(n_pool, dtype=int)
    n_late = n_pool - index_size - 100
    list_pos[index_size + 100:] = rng.integers(int(T * 0.05), int(T * 0.85),
                                               size=max(n_late, 0))

    # ---- index membership spells -----------------------------------------
    years = sorted(set(dates.year))
    current = list(rng.choice(np.arange(index_size + 100), size=index_size,
                              replace=False))
    spells = {i: [(0, None)] for i in current}
    delistings = []

    for y in years[1:]:
        yr_pos = int(np.searchsorted(dates, pd.Timestamp(f"{y}-06-15")))
        if yr_pos >= T:
            break
        n_ch = int(rng.poisson(changes_per_year / 2))  # adds == drops
        n_ch = max(n_ch, 1)

        outs = list(rng.choice(current, size=min(n_ch, len(current)), replace=False))
        for o in outs:
            spells[o][-1] = (spells[o][-1][0], yr_pos)
            current.remove(o)
            # a third of exits are genuine delistings (bankrupt / acquired), and
            # the performance-related ones go to near-zero on the exit date
            u = rng.random()
            if u < 0.20:
                delistings.append({"idx": o, "pos": yr_pos, "dlret": rng.uniform(-0.95, -0.55),
                                   "dlstcd": int(rng.choice([560, 574, 580]))})
            elif u < 0.33:
                delistings.append({"idx": o, "pos": yr_pos, "dlret": np.nan,
                                   "dlstcd": int(rng.choice([560, 572]))})  # missing -> Shumway
            elif u < 0.45:
                delistings.append({"idx": o, "pos": yr_pos, "dlret": rng.uniform(-0.05, 0.15),
                                   "dlstcd": 200})  # merger

        avail = [i for i in range(n_pool)
                 if i not in current and list_pos[i] < yr_pos - 260
                 and not any(d["idx"] == i for d in delistings)]
        ins = list(rng.choice(avail, size=min(n_ch, len(avail)), replace=False))
        for i in ins:
            spells.setdefault(i, []).append((yr_pos, None))
            current.append(i)

    memb_rows = []
    for i, sp in spells.items():
        for (s, e) in sp:
            memb_rows.append({
                "permno": int(permnos[i]),
                "mbrstartdt": dates[max(s, list_pos[i])],
                "mbrenddt": dates[e] if e is not None else pd.Timestamp(end),
            })
    membership = pd.DataFrame(memb_rows)

    if universe == "crsp_largecap":
        # No index. "Membership" = eligibility: every listed common share, for
        # its whole listing life. The top-N cut then happens on lagged mcap in
        # UniverseBuilder, exactly as it does on real CRSP data.
        membership = pd.DataFrame({
            "permno": permnos.astype(int),
            "mbrstartdt": [dates[list_pos[i]] for i in range(n_pool)],
            "mbrenddt": pd.Timestamp(end),
        })

    # ---- truncate returns at listing / delisting -------------------------
    arr = R.values.copy()
    for i in range(n_pool):
        if list_pos[i] > 0:
            arr[:list_pos[i], i] = np.nan
    delist_rows = []
    for d in delistings:
        i, p = d["idx"], d["pos"]
        arr[p:, i] = np.nan          # dsf simply STOPS. This is the trap.
        delist_rows.append({
            "permno": int(permnos[i]),
            "dlstdt": dates[p],
            "dlret": d["dlret"],
            "dlstcd": d["dlstcd"],
        })
    delist = pd.DataFrame(delist_rows,
                          columns=["permno", "dlstdt", "dlret", "dlstcd"])
    R = pd.DataFrame(arr, index=dates, columns=permnos)

    # ---- prices, shares, market cap --------------------------------------
    px0 = rng.uniform(15, 220, size=n_pool)
    px = px0[None, :] * np.cumprod(1.0 + np.nan_to_num(R.values), axis=0)
    shr = rng.uniform(50_000, 3_000_000, size=n_pool)   # thousands of shares
    shr_t = np.tile(shr, (T, 1))

    long = (R.stack(future_stack=True)
             .rename("ret").reset_index()
             .rename(columns={"level_0": "date", "level_1": "permno"}))
    long = long.dropna(subset=["ret"])
    pos_of = {d: k for k, d in enumerate(dates)}
    col_of = {p: k for k, p in enumerate(permnos)}
    ri = long["date"].map(pos_of).values
    ci = long["permno"].map(col_of).values
    long["prc"] = px[ri, ci]
    long["shrout"] = shr_t[ri, ci]
    long["cfacpr"] = 1.0
    long["cfacshr"] = 1.0
    dsf = long[["permno", "date", "ret", "prc", "shrout", "cfacpr", "cfacshr"]]

    names = pd.DataFrame({
        "permno": permnos,
        "namedt": [dates[list_pos[i]] for i in range(n_pool)],
        "nameendt": pd.Timestamp(end),
        "shrcd": 11,
        "exchcd": 1,
        "ticker": [f"MK{i:04d}" for i in range(n_pool)],
        "comnam": [f"MOCK CORP {i:04d}" for i in range(n_pool)],
    })

    rf = pd.DataFrame({"date": dates,
                       "rf": np.full(T, 0.02 / 252.0)})

    dsf.to_parquet(os.path.join(outdir, "dsf.parquet"), index=False)
    membership.to_parquet(os.path.join(outdir, "membership.parquet"), index=False)
    delist.to_parquet(os.path.join(outdir, "delist.parquet"), index=False)
    names.to_parquet(os.path.join(outdir, "names.parquet"), index=False)
    rf.to_parquet(os.path.join(outdir, "rf.parquet"), index=False)
    with open(os.path.join(outdir, MOCK_SENTINEL), "w") as fh:
        fh.write("Synthetic data. Pipeline testing only. Never publish numbers "
                 "computed from this directory.\n")

    print(f"mock CRSP written to {outdir}/  "
          f"({len(dsf):,} permno-days, {len(membership):,} spells, "
          f"{len(delist):,} delistings, {state.mean():.1%} crisis days)")


def is_mock(raw_dir: str) -> bool:
    return os.path.exists(os.path.join(raw_dir, MOCK_SENTINEL))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="data/mock")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    generate(a.outdir, seed=a.seed)
