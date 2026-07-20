"""
rac_hrp.data.universe
=====================
Phase 0.5, Task 2 -- point-in-time universe + eligibility screen.

Everything in this module is evaluated AS OF a formation date and may look only
backwards. Three separate look-ahead traps live here, and each is closed
explicitly:

  1. MEMBERSHIP.   Use the S&P 500 constituents as of the formation date, from
                   the CRSP membership spells -- never today's constituent list.
  2. RANKING.      Market cap for the top-N cut is LAGGED (D1: 21 trading days).
                   Ranking on same-day mcap ranks on same-day price, which is
                   the same information as the return you are about to trade.
  3. ELIGIBILITY.  Require >= min_history_days of valid returns strictly BEFORE
                   the formation date.

Trap 3 introduces a SEASONING BIAS: a stock that enters the index and has fewer
than W_min days of history is excluded until it seasons. This is not eliminable
without reintroducing look-ahead. It is instead *bounded and reported* -- the
realized-N series and the index-turnover series below are the evidence that the
exclusion is small and not concentrated in any regime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from .panel import Panels
from ..config import Config


@dataclass
class UniverseSnapshot:
    date: pd.Timestamp
    permnos: np.ndarray        # selected, ordered by lagged mcap desc
    n_members: int             # point-in-time index members
    n_eligible: int            # members passing the history screen
    n_selected: int            # min(n_assets, n_eligible)
    n_dropped_history: int     # members failing the screen (seasoning bias)


class UniverseBuilder:
    def __init__(self, panels: Panels, cfg: Config):
        self.panels = panels
        self.cfg = cfg
        self._valid = panels.returns.notna()
        # Cumulative count of valid returns, so the history screen is O(1) per
        # date instead of a rolling window over 25 years x 1000 permnos.
        self._cum_valid = self._valid.cumsum()

    def snapshot(self, date: pd.Timestamp) -> UniverseSnapshot:
        cfg = self.cfg
        ret = self.panels.returns
        idx = ret.index

        pos = idx.searchsorted(date, side="right") - 1
        if pos < 0:
            raise ValueError(f"{date} precedes the panel start {idx[0]}")

        # --- 1. point-in-time membership ---------------------------------
        member_mask = self.panels.is_member(date)

        # --- 3. eligibility: history strictly before the formation date ---
        # cum_valid at `pos` counts through today; we want through yesterday.
        prev = max(pos - 1, 0)
        hist = self._cum_valid.iloc[prev].values
        enough_history = hist >= cfg.min_history_days

        # Must also be trading now (not yet delisted, not a stale column).
        alive = self._valid.iloc[pos].values

        eligible = member_mask & enough_history & alive
        n_members = int(member_mask.sum())
        n_eligible = int(eligible.sum())

        # --- 2. rank by LAGGED market cap ---------------------------------
        lag_pos = max(pos - cfg.mcap_lag_days, 0)
        mc = self.panels.mcap.iloc[lag_pos].values.astype(float)
        mc = np.where(eligible, mc, np.nan)
        # A newly-added member can be eligible but have no mcap at the lagged
        # date. Fall back to the most recent mcap at or before the lag date.
        if np.isnan(mc[eligible]).any():
            back = self.panels.mcap.iloc[:lag_pos + 1].ffill().iloc[-1].values
            mc = np.where(eligible & np.isnan(mc), back, mc)

        order = np.argsort(-np.nan_to_num(mc, nan=-np.inf))
        keep = order[: min(cfg.n_assets, n_eligible)]
        keep = keep[eligible[keep]]
        permnos = ret.columns.values[keep]

        return UniverseSnapshot(
            date=idx[pos],
            permnos=permnos,
            n_members=n_members,
            n_eligible=n_eligible,
            n_selected=len(permnos),
            n_dropped_history=int((member_mask & ~enough_history).sum()),
        )

    def snapshots(self, dates) -> List[UniverseSnapshot]:
        return [self.snapshot(pd.Timestamp(d)) for d in dates]


def realized_n_report(snaps: List[UniverseSnapshot]) -> pd.DataFrame:
    """Realized-N and index-turnover series. Deliverable for the 0.5 gate."""
    rows = []
    prev: Optional[set] = None
    for s in snaps:
        cur = set(s.permnos.tolist())
        if prev is None:
            turn = np.nan
        else:
            turn = len(cur ^ prev) / (2.0 * max(len(cur), 1))
        rows.append({
            "date": s.date,
            "n_members": s.n_members,
            "n_eligible": s.n_eligible,
            "n_selected": s.n_selected,
            "n_dropped_history": s.n_dropped_history,
            "universe_turnover": turn,
        })
        prev = cur
    return pd.DataFrame(rows).set_index("date")


def covariance_window_from_universe(rep: pd.DataFrame) -> int:
    """D4 applied to the realized universe. Deterministic, no tuning."""
    from ..config import select_cov_window
    return select_cov_window(float(rep["n_selected"].median()))
