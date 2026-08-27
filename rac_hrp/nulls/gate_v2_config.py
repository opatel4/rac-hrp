"""
rac_hrp.nulls.gate_v2_config
============================
FROZEN configuration for Null Gate v2.

This module encodes the parameters fixed in the frozen protocol (rev.2) and its
amendments. Every value here is locked. Changing any of them invalidates the
freeze and the gate must be re-authorized. The freeze manifest (see
gate_v2.freeze_manifest) hashes this file so alteration is detectable.

frozen protocol references are given inline as [P§n] / [A-n].
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Tuple
import json

# --------------------------------------------------------------------------
# Randomness [P§6, A-6]
# --------------------------------------------------------------------------
# New base seed, drawn from OS entropy, never previously executed or inspected,
# frozen before execution. Supersedes all provisional parameters.
V2_BASE_SEED = 522618064

# Per-replication seeding: default_rng(V2_BASE_SEED + 1000*env_index + r)
ENV_INDEX: Dict[str, int] = {
    "A_iid_gaussian": 0,
    "B_xsec_shuffle": 1,
    "C_trigger_timing": 2,
    "D_regime_switch_vol": 3,
}

# Bootstrap seed [A-4]: V2_BASE_SEED + 500000 + 100*e + c
BOOTSTRAP_SEED_OFFSET = 500_000
BOOTSTRAP_RESAMPLES = 10_000

# --------------------------------------------------------------------------
# Replication counts [P§7, A-7] -- FROZEN, no sequential addition
# --------------------------------------------------------------------------
REPLICATIONS: Dict[str, int] = {
    "A_iid_gaussian": 150,
    "B_xsec_shuffle": 150,
    "C_trigger_timing": 150,
    "D_regime_switch_vol": 200,
}

# --------------------------------------------------------------------------
# Decision rule [A-2] -- one-sided paired-t, materiality margin +0.10
# --------------------------------------------------------------------------
MATERIALITY_MARGIN = 0.10            # delta; one-sided
CONFIDENCE = 0.95                    # one-sided 95% bound => t.ppf(0.95, n-1)

# --------------------------------------------------------------------------
# Primary-gate comparators [A-1] -- same-policy only
# --------------------------------------------------------------------------
# HRP_periodic_3: initial cluster on first eligible construction date, re-cluster
# every 3rd scheduled rebalance; all else identical to RAC-HRP.
PRIMARY_COMPARATORS: Tuple[str, ...] = ("HRP_static", "HRP_periodic_3")
FOCAL = "RAC_HRP"

# Diagnostic panel [P§2.2] -- cross-allocator, NON-GATING
DIAGNOSTIC_COMPARATORS: Dict[str, Tuple[str, ...]] = {
    "A_iid_gaussian": ("EW", "ERC"),
    "B_xsec_shuffle": ("EW", "ERC"),
    "C_trigger_timing": (),          # returns real; cross-allocator N/A
    "D_regime_switch_vol": ("EW", "ERC"),
}

# --------------------------------------------------------------------------
# Trigger-activation requirement [A-3]
# --------------------------------------------------------------------------
MIN_MEDIAN_FIRING_RATE = 0.05        # median firing rate across reps >= 5%
MIN_EVENTS_PER_REP = 3               # >=90% of reps have >=3 trigger events
MIN_FRAC_REPS_ACTIVE = 0.90

# --------------------------------------------------------------------------
# Calibration controls [control-construction ruling]
# --------------------------------------------------------------------------
# Deterministic location shift on centered replication residuals:
#   d_control_r = (d_r - mean(d)) + delta
NULL_CONTROL_DELTA = 0.00            # must PASS
POSITIVE_CONTROL_DELTA = 0.20        # must FAIL

# --------------------------------------------------------------------------
# Environment order (must match environments.ENVIRONMENTS) [A-6]
# --------------------------------------------------------------------------
ENVIRONMENT_ORDER: Tuple[str, ...] = (
    "A_iid_gaussian", "B_xsec_shuffle", "C_trigger_timing", "D_regime_switch_vol",
)


@dataclass(frozen=True)
class GateV2Config:
    base_seed: int = V2_BASE_SEED
    materiality_margin: float = MATERIALITY_MARGIN
    confidence: float = CONFIDENCE
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES
    bootstrap_seed_offset: int = BOOTSTRAP_SEED_OFFSET
    null_delta: float = NULL_CONTROL_DELTA
    positive_delta: float = POSITIVE_CONTROL_DELTA
    min_median_firing_rate: float = MIN_MEDIAN_FIRING_RATE
    min_events_per_rep: int = MIN_EVENTS_PER_REP
    min_frac_reps_active: float = MIN_FRAC_REPS_ACTIVE
    replications: Dict[str, int] = field(default_factory=lambda: dict(REPLICATIONS))
    primary_comparators: Tuple[str, ...] = PRIMARY_COMPARATORS

    def seed_for(self, env: str, rep: int) -> int:
        return self.base_seed + 1000 * ENV_INDEX[env] + rep

    def bootstrap_seed_for(self, env: str, comparator: str) -> int:
        c = self.primary_comparators.index(comparator)
        return self.base_seed + self.bootstrap_seed_offset + 100 * ENV_INDEX[env] + c

    def to_json(self) -> str:
        d = asdict(self)
        d["primary_comparators"] = list(d["primary_comparators"])
        return json.dumps(d, indent=2, sort_keys=True)
