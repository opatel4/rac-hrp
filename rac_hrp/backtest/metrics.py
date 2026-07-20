"""
rac_hrp.backtest.metrics
========================
Performance statistics. Daily in, annualised out.

Sharpe is computed on EXCESS returns against the Fama-French daily risk-free
rate, not on raw returns. Over 2000-2025 the risk-free rate averaged well above
zero for long stretches; a "Sharpe" on raw returns is a different, flattering
statistic, and it is not the one the Ledoit-Wolf (2008) test is built for.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ..config import TRADING_DAYS_PER_YEAR as APY


def excess(returns: pd.Series, rf: Optional[pd.Series]) -> pd.Series:
    if rf is None:
        return returns
    return returns - rf.reindex(returns.index).fillna(0.0)


def sharpe(returns: pd.Series, rf: Optional[pd.Series] = None) -> float:
    r = excess(returns, rf).dropna()
    if len(r) < 2:
        return np.nan
    sd = r.std(ddof=1)
    if sd <= 0:
        return np.nan
    return float(r.mean() / sd * np.sqrt(APY))


def ann_return(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) == 0:
        return np.nan
    return float((1.0 + r).prod() ** (APY / len(r)) - 1.0)


def ann_vol(returns: pd.Series) -> float:
    r = returns.dropna()
    return float(r.std(ddof=1) * np.sqrt(APY)) if len(r) > 1 else np.nan


def max_drawdown(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) == 0:
        return np.nan
    curve = (1.0 + r).cumprod()
    return float((curve / curve.cummax() - 1.0).min())


def calmar(returns: pd.Series) -> float:
    mdd = max_drawdown(returns)
    if mdd is None or np.isnan(mdd) or mdd == 0:
        return np.nan
    return float(ann_return(returns) / abs(mdd))


def summarize(returns: pd.Series,
              rf: Optional[pd.Series] = None,
              turnover: Optional[pd.Series] = None,
              name: str = "") -> dict:
    out = {
        "strategy": name,
        "ann_return": ann_return(returns),
        "ann_vol": ann_vol(returns),
        "sharpe": sharpe(returns, rf),
        "max_drawdown": max_drawdown(returns),
        "calmar": calmar(returns),
        "n_days": int(returns.dropna().shape[0]),
    }
    if turnover is not None and len(turnover):
        t = turnover.dropna()
        out["avg_turnover_per_rebal"] = float(t.mean())
        out["ann_turnover"] = float(t.mean() * (APY / 21.0))
    return out


def summary_table(results: dict,
                  rf: Optional[pd.Series] = None) -> pd.DataFrame:
    """results: {name -> BacktestResult}"""
    rows = []
    for name, res in results.items():
        rows.append(summarize(res.returns, rf, res.turnover, name))
    df = pd.DataFrame(rows).set_index("strategy")
    return df.sort_values("sharpe", ascending=False)


def sharpe_difference(a: pd.Series, b: pd.Series,
                      rf: Optional[pd.Series] = None) -> float:
    """SR(a) - SR(b) on the common date index. The null gate's core statistic."""
    idx = a.dropna().index.intersection(b.dropna().index)
    return sharpe(a.loc[idx], rf) - sharpe(b.loc[idx], rf)
