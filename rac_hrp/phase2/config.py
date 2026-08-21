"""
rac_hrp.phase2.config
=====================
FROZEN configuration for the Phase 2 regime-adaptive layer.

Implemented exactly to the signed pre-registration:
    "PHASE 2 - PRE-REGISTRATION & CALIBRATION GATE (rev.5)"
    [AUTHORIZE AND FREEZE: YES]

Every value here is locked. Changing any of them invalidates the freeze and
requires a formal amendment with a reason, timestamp, and a statement of its
relationship to information already observed -- NOT a further revision.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Tuple
import json

# --------------------------------------------------------------------------
# Trigger (rev.5 section 1) -- all values audited as-built, not chosen
# --------------------------------------------------------------------------
AR_SMOOTH_REBALANCES = 5        # rolling mean window, min_periods = 1
AR_SMOOTH_MIN_PERIODS = 1
AR_SIGMA_REBALANCES = 12        # rolling std window
AR_SIGMA_MIN_PERIODS = 6
AR_SIGMA_DDOF = 1               # AUDITED as-built: pandas .std() default
AR_SIGMA_SHIFT = 1              # strictly trailing

# --------------------------------------------------------------------------
# Candidate grid and structural gate (rev.5 section 2)
# --------------------------------------------------------------------------
GAMMA_CANDIDATES: Tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
GAMMA_INHERITED = 1.0           # reference; selection breaks ties toward it

FIRING_MIN = 0.05
FIRING_MAX = 0.40               # NOT revised to rescue gamma = 1.0
MIN_EVENTS_PER_FOLD = 3
CV_GAP_MIN = 0.50
MODAL_GAP_SHARE_MAX = 0.50

# --------------------------------------------------------------------------
# Separation statistic and its placebo Monte Carlo (rev.5 section 3)
# --------------------------------------------------------------------------
SEPARATION_PERIODS: Tuple[int, ...] = tuple(range(2, 13))   # q = 2..12
PLACEBO_SEED = 20260817
PLACEBO_DRAWS = 100_000
PLACEBO_PERCENTILE = 95.0       # numpy linear interpolation
# Pass rule is WEAK at the cutoff: J* <= q_0.95 passes.

# --------------------------------------------------------------------------
# D_VI bootstrap (rev.5 section 4)
# --------------------------------------------------------------------------
BOOTSTRAP_KIND = "circular_block"
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED_BASE = PLACEBO_SEED + 2000       # + candidate index c
HOLM_ALPHA = 0.05

# --------------------------------------------------------------------------
# Comparators
# --------------------------------------------------------------------------
PRIMARY_PERFORMANCE_COMPARATOR = "HRP_periodic_3"


@dataclass(frozen=True)
class Phase2Config:
    gamma_candidates: Tuple[float, ...] = GAMMA_CANDIDATES
    gamma_inherited: float = GAMMA_INHERITED
    firing_min: float = FIRING_MIN
    firing_max: float = FIRING_MAX
    min_events_per_fold: int = MIN_EVENTS_PER_FOLD
    cv_gap_min: float = CV_GAP_MIN
    modal_gap_share_max: float = MODAL_GAP_SHARE_MAX
    separation_periods: Tuple[int, ...] = SEPARATION_PERIODS
    placebo_seed: int = PLACEBO_SEED
    placebo_draws: int = PLACEBO_DRAWS
    placebo_percentile: float = PLACEBO_PERCENTILE
    bootstrap_kind: str = BOOTSTRAP_KIND
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES
    bootstrap_seed_base: int = BOOTSTRAP_SEED_BASE
    holm_alpha: float = HOLM_ALPHA
    ar_smooth_rebalances: int = AR_SMOOTH_REBALANCES
    ar_sigma_rebalances: int = AR_SIGMA_REBALANCES
    ar_sigma_ddof: int = AR_SIGMA_DDOF

    def bootstrap_seed_for(self, gamma: float) -> int:
        """seed = base + c, c = index of gamma in the frozen candidate tuple."""
        return self.bootstrap_seed_base + self.gamma_candidates.index(gamma)

    def to_json(self) -> str:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, tuple):
                d[k] = list(v)
        return json.dumps(d, indent=2, sort_keys=True)
