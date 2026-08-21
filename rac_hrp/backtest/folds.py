"""
rac_hrp.backtest.folds
======================
D10 -- development folds with NO model-selection role, plus the single-touch test.

POSITION-BASED, NOT DATE-BASED. Purge and embargo are specified in TRADING DAYS
and applied by integer position in the trading calendar, never by calendar date
arithmetic. A 20-calendar-day embargo is 14 trading days over a normal stretch
and 12 over Christmas -- it silently shrinks exactly when volatility clusters.
Positions are the only unit that means the same thing everywhere in the sample.

THE NESTED STRUCTURE

    |<---------------- DEVELOPMENT (2000 - 2022) ---------------->|<-- TEST -->|
    |  fold 1  |  fold 2  |  fold 3  |  fold 4  |                 | 2023-2025  |
                                                                    single touch

  * Development folds exist to ESTABLISH THAT THE MACHINERY RUNS and to report
    diagnostics. They do NOT select the threshold, the window, the estimator, or
    the re-clustering frequency -- all of those are frozen in config.py before
    any result is seen. That is D10, and it is the reason this project can claim
    its test result is a real out-of-sample number rather than the survivor of a
    search.
  * The test region is touched ONCE, at the very end, after every rule is frozen.
    `TestRegionLock` below makes that structural rather than a promise: the test
    slice raises unless it is explicitly unlocked, and the unlock is logged.

PURGE vs EMBARGO (they are not the same thing)

  PURGE   drops training observations whose ESTIMATION WINDOW overlaps the test
          block. A covariance estimated on the last day of training uses the
          trailing W days -- if the test block starts the next day, those two
          windows share nothing yet, but the *weights* formed at the training
          boundary are informed by returns that also inform the first test-block
          covariance. Purging `purge_days` positions off the training tail cuts
          that shared information.
  EMBARGO drops observations immediately AFTER the test block from any later
          training block, because serial correlation runs forwards: a training
          row 5 days after the test block still carries the test block's shock.
"""

from __future__ import annotations
from rac_hrp.backtest.region_lock import TestRegionLock  # noqa: F401

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import Config, SAMPLE_START, DEV_END, TEST_START, TEST_END


@dataclass(frozen=True)
class Fold:
    fold_id: int
    train_pos: np.ndarray     # integer positions into the trading calendar
    test_pos: np.ndarray
    label: str

    @property
    def n_train(self) -> int:
        return len(self.train_pos)

    @property
    def n_test(self) -> int:
        return len(self.test_pos)

    def describe(self, calendar: pd.DatetimeIndex) -> str:
        tr = f"{calendar[self.train_pos[0]].date()} -> {calendar[self.train_pos[-1]].date()}"
        te = f"{calendar[self.test_pos[0]].date()} -> {calendar[self.test_pos[-1]].date()}"
        return (f"fold {self.fold_id} [{self.label}]  "
                f"train {tr} ({self.n_train:5d}d)  eval {te} ({self.n_test:4d}d)")


class FoldGenerator:
    def __init__(self, calendar: pd.DatetimeIndex, cfg: Config):
        self.calendar = pd.DatetimeIndex(calendar)
        self.cfg = cfg
        self.lock = TestRegionLock()

        self.sample_start_pos = int(self.calendar.searchsorted(pd.Timestamp(SAMPLE_START)))
        self.dev_end_pos = int(self.calendar.searchsorted(pd.Timestamp(DEV_END), side="right") - 1)
        self.test_start_pos = int(self.calendar.searchsorted(pd.Timestamp(TEST_START)))
        self.test_end_pos = int(self.calendar.searchsorted(pd.Timestamp(TEST_END), side="right") - 1)

        if self.dev_end_pos <= self.sample_start_pos:
            raise ValueError("development region is empty -- check the calendar")

    # -- development ------------------------------------------------------
    def dev_folds(self, min_train: Optional[int] = None) -> List[Fold]:
        """Expanding-window walk-forward folds with position purge + embargo."""
        cfg = self.cfg
        min_train = min_train or (cfg.cov_window + cfg.min_history_days)

        lo, hi = self.sample_start_pos, self.dev_end_pos
        span = hi - lo + 1
        k = cfg.n_dev_folds

        usable = span - min_train
        if usable <= 0:
            raise ValueError(
                f"development region is {span} days but the first fold needs "
                f"{min_train} days of training (cov_window={cfg.cov_window} + "
                f"min_history={cfg.min_history_days}). Widen the region, shorten "
                f"the covariance window, or reduce n_dev_folds.")
        test_len = usable // k

        folds: List[Fold] = []
        for i in range(k):
            te_lo = lo + min_train + i * test_len
            te_hi = te_lo + test_len - 1 if i < k - 1 else hi
            if te_hi <= te_lo:
                continue

            # training = everything from sample start to the test block, MINUS
            # the purge tail. Embargo bites on the *previous* test blocks, whose
            # trailing days are already inside this training block.
            tr_hi = te_lo - 1 - cfg.purge_days
            tr = np.arange(lo, tr_hi + 1)

            if i > 0:
                prev_te_hi = lo + min_train + i * test_len - 1
                emb_lo = prev_te_hi + 1
                emb_hi = prev_te_hi + cfg.embargo_days
                tr = tr[(tr < emb_lo) | (tr > emb_hi)]

            if len(tr) < min_train // 2:
                continue

            folds.append(Fold(
                fold_id=i + 1,
                train_pos=tr,
                test_pos=np.arange(te_lo, te_hi + 1),
                label="dev",
            ))
        return folds

    # -- test -------------------------------------------------------------
    def test_fold(self) -> Fold:
        self.lock.check()
        tr_hi = self.test_start_pos - 1 - self.cfg.purge_days
        return Fold(
            fold_id=99,
            train_pos=np.arange(self.sample_start_pos, tr_hi + 1),
            test_pos=np.arange(self.test_start_pos, self.test_end_pos + 1),
            label="TEST-single-touch",
        )

    # -- audit -------------------------------------------------------------
    def leakage_audit(self, folds: List[Fold]) -> pd.DataFrame:
        """Prove the purge/embargo actually opened the gaps it claims to."""
        rows = []
        for f in folds:
            gap = int(f.test_pos[0] - f.train_pos[-1] - 1)
            overlap = int(len(np.intersect1d(f.train_pos, f.test_pos)))
            rows.append({
                "fold": f.fold_id,
                "train_end": self.calendar[f.train_pos[-1]].date(),
                "test_start": self.calendar[f.test_pos[0]].date(),
                "gap_trading_days": gap,
                "required_purge": self.cfg.purge_days,
                "train_test_overlap": overlap,
                "ok": (gap >= self.cfg.purge_days) and (overlap == 0),
            })
        return pd.DataFrame(rows)
