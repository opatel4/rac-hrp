"""
rac_hrp.config
==============
Single source of truth for every parameter frozen in the Pre-Analysis Plan.

Nothing downstream is allowed to invent a parameter. If a number appears in the
pipeline and is not in this file, that is a bug: it means a free parameter has
entered the analysis without being pre-registered.

FROZEN (Pre-Analysis Plan, locked decisions 1-10):
  D1  CRSP point-in-time S&P 500 universe; staged N in {100, 200, full},
      selected by LAGGED market cap.
  D2  Marchenko-Pastur eigenvalue retention (replaces the 60% variance cutoff).
  D3  Nonlinear Ledoit-Wolf shrinkage for covariance.
  D4  Deterministic covariance-window rule: pick the smallest W in
      {504, 756, 1260} whose median N/W over the development region is <= 0.67.
  D5  Absorption-ratio trigger threshold fixed EX ANTE at 1.0 sigma.
      Re-clustering frequencies are FIXED COMPARATORS, never selected.
  D6  Ledoit-Wolf (2008) studentized bootstrap = primary inference.
      Jobson-Korkie / Memmel = comparability reporting only.
  D7  Politis-White (2004) automatic block length.
  D8  Conjunctive primary endpoint: RAC-HRP must beat BOTH static HRP and ERC.
  D9  Three-null gate, including a trigger-timing null.
  D10 Development folds have NO model-selection role.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Tuple, Dict, Any
import json

# --------------------------------------------------------------------------
# Calendar
# --------------------------------------------------------------------------
TRADING_DAYS_PER_YEAR = 252

# Lookback buffer: the longest covariance window is 1260 trading days (~5y),
# so a universe that starts trading in 2000 needs price history from ~1995.
DATA_START = "1995-01-01"       # buffer start (raw pull)
SAMPLE_START = "2000-01-03"     # first date any portfolio may be formed
DEV_END = "2022-12-31"          # development region ends here
TEST_START = "2023-01-03"       # single-touch test region
TEST_END = "2025-11-28"


# --------------------------------------------------------------------------
# D4 - covariance window rule
# --------------------------------------------------------------------------
COV_WINDOW_CANDIDATES: Tuple[int, ...] = (504, 756, 1260)
MAX_MEDIAN_N_OVER_W = 0.67


def select_cov_window(n_median: float,
                      candidates: Tuple[int, ...] = COV_WINDOW_CANDIDATES,
                      cap: float = MAX_MEDIAN_N_OVER_W) -> int:
    """D4. Deterministic: smallest candidate window W with median(N)/W <= cap.

    This is a *rule*, not a tuning knob. It consumes only the realized universe
    size, which is a property of the data, not of any performance metric.
    """
    for w in sorted(candidates):
        if n_median / w <= cap:
            return w
    raise ValueError(
        f"No candidate window satisfies N/W <= {cap} for median N={n_median:.1f}. "
        f"Largest candidate {max(candidates)} gives {n_median / max(candidates):.3f}. "
        "Universe is too large for the pre-registered window set."
    )


@dataclass(frozen=True)
class Config:
    # ---- universe (D1) ---------------------------------------------------
    n_assets: int = 100                     # staged build: 100 -> 200 -> full
    mcap_lag_days: int = 21                 # market cap lagged 1 month for ranking
    min_history_days: int = 252             # W_min: eligibility screen
    max_missing_frac: float = 0.05          # within the covariance window

    # ---- covariance (D3, D4) --------------------------------------------
    cov_window: int = 756                   # OVERWRITTEN by select_cov_window()
    cov_estimator: str = "nls"              # {"nls", "lw_linear", "sample"}
    store_weights: bool = False             # opt-in; Phase 1 accounting check only

    # ---- PCA / Marchenko-Pastur (D2) ------------------------------------
    mp_k_mode: str = "fixed_per_fold"       # {"fixed_per_fold", "rolling"}  <-- see NOTE
    ar_min_components: int = 1

    # ---- clustering ------------------------------------------------------
    cluster_space: str = "pca"              # {"pca", "correlation"}
    linkage_method: str = "ward"            # ward in PCA space; "single" if correlation
    n_clusters_rule: str = "mp_k"           # #clusters = #MP-retained components
    n_clusters_min: int = 2
    n_clusters_max: int = 20

    # ---- regime trigger (D5) --------------------------------------------
    ar_trigger_sigma: float = 1.0           # FROZEN. Sensitivity curve is Phase 2b.
    ar_sigma_window: int = 252              # trailing window for sigma(dAR)
    ar_smooth_days: int = 5                 # AR smoothing before differencing

    # ---- rebalancing / execution ----------------------------------------
    rebalance_freq: int = 21                # trading days (monthly)
    implementation_lag: int = 1             # D: one-day lag, weights live at t+1
    tc_bps_one_way: float = 0.0             # Phase 0.5 runs gross. Phase 3 = 5/10bps.
    long_only: bool = True

    # ---- folds (D10) -----------------------------------------------------
    n_dev_folds: int = 4
    purge_days: int = 21                    # position-based, trading days
    embargo_days: int = 20                  # position-based, trading days

    # ---- null gate (D9) --------------------------------------------------
    null_replications: int = 20
    null_sharpe_tolerance: float = 0.10     # equivalence margin, Sharpe units
    null_gate_sided: str = "one"            # {"two", "one"}  <-- OPEN DECISION
    seed: int = 20260711

    # ---- comparators -----------------------------------------------------
    periodic_recluster_freqs: Tuple[int, ...] = (1, 3, 12)  # in rebalances

    meta: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        d["periodic_recluster_freqs"] = list(d["periodic_recluster_freqs"])
        return json.dumps(d, indent=2, sort_keys=True)


# --------------------------------------------------------------------------
# NOTE ON mp_k_mode  (flagged as an OPEN decision -- see README)
# --------------------------------------------------------------------------
# Kritzman et al. (2011) hold the number of eigenvectors FIXED (n = N/5) when
# computing the absorption ratio. We replaced the arbitrary 60% cutoff with
# Marchenko-Pastur retention (D2) -- but MP-implied k is data-dependent and
# moves over time. If k moves, the absorption ratio jumps for reasons that have
# nothing to do with correlation structure: AR = sum_{i<=k} lambda_i / sum lambda_i
# is mechanically increasing in k.
#
# That would put a spurious sawtooth directly into the trigger signal -- exactly
# the failure mode the trigger-timing null is designed to catch.
#
# Default resolution: k is fixed PER FOLD, at the MP-implied k computed from the
# first covariance window of that fold's training block, then held constant for
# the whole fold. AR then varies only through the eigenvalue spectrum.
# `mp_k_mode="rolling"` reproduces the naive time-varying-k behaviour and is
# retained only so the sawtooth can be demonstrated, not used.
