"""
rac_hrp.backtest.engine
=======================
The Stage-1 N-invariant pipeline: point-in-time universe -> covariance (NLS) ->
MP spectrum -> absorption ratio -> re-clustering decision -> HRP/ERC/EW weights
-> daily returns, turnover, costs.

The whole experiment lives in ONE parameter, `recluster`:

    "never"        static HRP        -- tree fitted once, then frozen
    "periodic:k"   fixed comparator  -- tree refitted every k rebalances
    "ar_trigger"   RAC-HRP           -- tree refitted when |dAR| > 1 sigma

Everything else -- universe, covariance, spectrum, execution, costs -- is
IDENTICAL across the three. That is deliberate and it is the only way the
comparison means anything: if the pipeline differed anywhere else, a win for
ar_trigger would be unattributable.

------------------------------------------------------------------------------
THE UNIVERSE-CHURN PROBLEM  (a real design decision, flagged in the README)
------------------------------------------------------------------------------
"Freeze the tree" is ill-defined when the universe changes underneath it. Over
2000-2025 the S&P 500 turns over ~22 names a year; a tree frozen in 2005 is a
tree over assets that no longer exist.

Naive fixes both corrupt the experiment:
  * refit the tree whenever the universe changes -> "static" HRP silently
    re-clusters ~12x/year and there is no static baseline left.
  * hold out non-members -> the universe is no longer point-in-time.

What this engine does instead (`ClusterState.adapt`), applied IDENTICALLY to all
three policies so it cannot favour any of them:
  * EXITS  are removed from the frozen leaf order (order of survivors preserved).
  * ENTRANTS are spliced in immediately adjacent to their nearest neighbour among
    the already-placed assets, distance measured in the CURRENT PCA space.
Structure is inherited; only the churn is absorbed. A "static" tree stays static
in the sense that matters -- its partition of the surviving assets is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import Config
from ..core.covariance import estimate
from ..core.pca_mp import spectrum, absorption_ratio, pca_features, Spectrum
from ..core.clustering import build_tree, cluster_labels, n_clusters_from_rule
from ..core.allocators import hrp_weights, erc_weights, equal_weight, min_variance
from ..data.panel import Panels
from ..data.universe import UniverseBuilder


# --------------------------------------------------------------------------
# Cluster state
# --------------------------------------------------------------------------
@dataclass
class ClusterState:
    permnos: np.ndarray        # assets in the frozen tree, in LEAF ORDER
    labels: np.ndarray         # cluster label per permno (same order)
    fitted_on: pd.Timestamp
    n_clusters: int

    def adapt(self, current: np.ndarray, spec: Spectrum,
              cur_permnos: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Map the frozen order onto today's universe.

        Returns (leaf_order_positions_into_current, labels_for_current).
        """
        cur_index = {p: i for i, p in enumerate(cur_permnos)}
        kept = [p for p in self.permnos if p in cur_index]
        kept_labels = {p: l for p, l in zip(self.permnos, self.labels) if p in cur_index}

        entrants = [p for p in cur_permnos if p not in kept_labels]

        if kept and entrants:
            F = pca_features(spec)                       # current PCA coords
            kept_pos = np.array([cur_index[p] for p in kept])
            order = list(kept)
            for p in entrants:
                i = cur_index[p]
                d = np.linalg.norm(F[kept_pos] - F[i][None, :], axis=1)
                j = int(np.argmin(d))
                nearest = kept[j]
                order.insert(order.index(nearest) + 1, p)
                kept_labels[p] = kept_labels[nearest]    # inherit the label
        elif entrants:                                   # nothing survived
            order = list(cur_permnos)
            for p in entrants:
                kept_labels[p] = 1
        else:
            order = list(kept)

        pos = np.array([cur_index[p] for p in order], dtype=int)
        labels = np.array([kept_labels[p] for p in cur_permnos])
        return pos, labels


# --------------------------------------------------------------------------
# Strategy spec
# --------------------------------------------------------------------------
@dataclass
class Strategy:
    name: str
    allocator: str = "hrp"          # {"hrp", "erc", "ew", "minvar", "oracle"}
    recluster: str = "never"        # {"never", "periodic:k", "ar_trigger"}
    cluster_space: str = "pca"      # {"pca", "correlation"}
    oracle_strength: float = 0.0    # DIAGNOSTIC ONLY -- see below

    def needs_tree(self) -> bool:
        return self.allocator == "hrp"


# ---------------------------------------------------------------------------
# THE ORACLE ALLOCATOR -- a deliberate cheat, used ONLY to measure gate power.
#
# It tilts toward the assets that WILL do well over the coming holding period.
# It is look-ahead by construction and its results are meaningless as finance.
#
# It exists because of a subtlety that is easy to miss: HRP, ERC and min-variance
# are all VARIANCE-based allocators. They never form a view on expected returns.
# So the classic "leak future returns into the estimation window" test does not
# perturb them at all -- they would ignore the leaked means and the null gate
# would report, correctly but uselessly, that nothing happened. A null gate whose
# positive control cannot move it is a null gate with unmeasured power.
#
# The oracle injects an edge of KNOWN size that a portfolio allocator CAN express
# (a weight tilt), so we can ask the only question that validates the gate:
# "how large must a manufactured edge be before this gate catches it?"
#
# `oracle_strength` in [0, 1] blends equal-weight with the cheat:
#     w = (1 - s) * EW + s * (forward-return tilt)
# so sweeping s traces the gate's minimum detectable effect.
# ---------------------------------------------------------------------------
def _oracle_weights(fwd: np.ndarray, strength: float) -> np.ndarray:
    n = len(fwd)
    ew = np.full(n, 1.0 / n)
    if strength <= 0 or not np.isfinite(fwd).any():
        return ew
    f = np.nan_to_num(fwd, nan=0.0)
    r = f.argsort().argsort().astype(float)      # ranks, 0..n-1
    tilt = r / max(r.sum(), 1e-12)
    w = (1.0 - strength) * ew + strength * tilt
    s = w.sum()
    return w / s if s > 0 else ew


def default_strategies(cfg: Config) -> List[Strategy]:
    """The Phase 0.5 comparator set. RAC-HRP plus everything it must beat."""
    s = [
        Strategy("EW", allocator="ew"),
        Strategy("ERC", allocator="erc"),
        Strategy("HRP_static", allocator="hrp", recluster="never"),
        Strategy("RAC_HRP", allocator="hrp", recluster="ar_trigger"),
    ]
    for k in cfg.periodic_recluster_freqs:
        s.append(Strategy(f"HRP_periodic_{k}", allocator="hrp",
                          recluster=f"periodic:{k}"))
    return s


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
@dataclass
class BacktestResult:
    name: str
    returns: pd.Series                      # daily net portfolio returns
    gross_returns: pd.Series
    turnover: pd.Series                     # per rebalance
    weights: Dict[pd.Timestamp, pd.Series] = field(default_factory=dict)
    recluster_dates: List[pd.Timestamp] = field(default_factory=list)
    diagnostics: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def n_reclusters(self) -> int:
        return len(self.recluster_dates)


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------
class WalkForward:
    """Runs every strategy over one evaluation window, sharing all estimation.

    Covariance and eigendecomposition are computed ONCE per rebalance date and
    reused across strategies. That is a ~4x saving on the real run and the
    difference between a null gate that finishes and one that does not: 3 nulls x
    20 replications x 7 strategies x ~270 rebalances is 113k covariance
    estimates if you are careless, and 16k if you are not.
    """

    def __init__(self, panels: Panels, cfg: Config,
                 signal_returns: Optional[pd.DataFrame] = None):
        self.panels = panels
        self.cfg = cfg
        self.ub = UniverseBuilder(panels, cfg)
        # `signal_returns` decouples the series the TRIGGER sees from the series
        # the PORTFOLIO earns. Identical by default. The trigger-timing null
        # passes a shifted panel here -- see nulls/environments.py.
        self.signal_returns = signal_returns

    # -- one rebalance ----------------------------------------------------
    def _estimate(self, t_pos: int, permnos: np.ndarray,
                  returns: pd.DataFrame) -> Optional[Tuple[np.ndarray, Spectrum]]:
        cfg = self.cfg
        lo = t_pos - cfg.cov_window + 1
        if lo < 0:
            return None
        X = returns.iloc[lo:t_pos + 1][permnos]

        ok = X.notna().mean() >= (1.0 - cfg.max_missing_frac)
        permnos = permnos[ok.values]
        if len(permnos) < 10:
            return None
        X = X[permnos].fillna(0.0)

        cov = estimate(X.values, cfg.cov_estimator)
        spec = spectrum(cov, cfg.cov_window,
                        min_components=cfg.ar_min_components)
        return cov, spec, permnos

    def run(self, strategies: List[Strategy],
            eval_pos: np.ndarray,
            returns: Optional[pd.DataFrame] = None,
            verbose: bool = False) -> Dict[str, BacktestResult]:

        cfg = self.cfg
        R = self.panels.returns if returns is None else returns
        S = R if self.signal_returns is None else self.signal_returns
        cal = R.index
        rf = self.panels.rf

        lo, hi = int(eval_pos[0]), int(eval_pos[-1])
        rebal = list(range(lo, hi + 1, cfg.rebalance_freq))

        # ---- shared estimation pass --------------------------------------
        shared: Dict[int, tuple] = {}
        ar_series: Dict[pd.Timestamp, float] = {}
        fold_k: Optional[int] = None

        for t in rebal:
            snap = self.ub.snapshot(cal[t])
            if len(snap.permnos) < 10:
                continue
            est = self._estimate(t, snap.permnos, R)
            if est is None:
                continue
            cov, spec, permnos = est

            # D2 / config NOTE: freeze k within the fold so the absorption ratio
            # cannot move just because the component count moved.
            if cfg.mp_k_mode == "fixed_per_fold":
                if fold_k is None:
                    fold_k = spec.k
                k_ar = fold_k
            else:
                k_ar = spec.k

            # The trigger reads the SIGNAL panel, which is normally the same
            # panel. Under the trigger-timing null it is not.
            if S is R:
                spec_sig = spec
            else:
                est_s = self._estimate(t, permnos, S)
                spec_sig = est_s[1] if est_s is not None else spec

            ar = absorption_ratio(spec_sig, k=k_ar)
            ar_series[cal[t]] = ar
            shared[t] = (cov, spec, permnos, ar, k_ar)

        if not shared:
            raise RuntimeError("no valid rebalance dates in the evaluation window")

        # ---- absorption-ratio trigger (D5) --------------------------------
        ars = pd.Series(ar_series).sort_index()
        ars_s = ars.rolling(cfg.ar_smooth_days, min_periods=1).mean()
        dar = ars_s.diff()
        # sigma of dAR from a TRAILING window only -- using the full-sample sigma
        # would leak the future into the trigger, which is the exact bug the
        # trigger-timing null is built to expose.
        sig_win = max(int(cfg.ar_sigma_window / cfg.rebalance_freq), 6)
        dar_sd = dar.rolling(sig_win, min_periods=6).std().shift(1)
        trigger = (dar.abs() > cfg.ar_trigger_sigma * dar_sd).fillna(False)

        # ---- per-strategy pass --------------------------------------------
        out: Dict[str, BacktestResult] = {}
        for st in strategies:
            out[st.name] = self._run_one(st, shared, rebal, trigger, ars, cal,
                                         R, rf, hi)
            if verbose:
                r = out[st.name]
                print(f"    {st.name:20s} reclusters={r.n_reclusters:3d}")
        return out

    def _run_one(self, st: Strategy, shared, rebal, trigger, ars, cal,
                 R, rf, hi) -> BacktestResult:
        cfg = self.cfg
        state: Optional[ClusterState] = None
        since = 0
        period = None
        if st.recluster.startswith("periodic:"):
            period = int(st.recluster.split(":")[1])

        daily_gross: List[pd.Series] = []
        daily_net: List[pd.Series] = []
        turn_rows, diag_rows, rc_dates = [], [], []
        weight_path: Dict[pd.Timestamp, pd.Series] = {}
        prev_w: Optional[pd.Series] = None

        keys = [t for t in rebal if t in shared]
        for i, t in enumerate(keys):
            cov, spec, permnos, ar, k_ar = shared[t]
            date = cal[t]
            n = len(permnos)

            # ---- re-clustering decision --------------------------------
            refit = False
            if st.needs_tree():
                if state is None:
                    refit = True                       # first fit, all policies
                elif st.recluster == "never":
                    refit = False
                elif period is not None:
                    refit = (since >= period)
                elif st.recluster == "ar_trigger":
                    refit = bool(trigger.get(date, False))

            if st.needs_tree():
                if refit:
                    nc = n_clusters_from_rule(spec, cfg.n_clusters_rule,
                                              cfg.n_clusters_min, cfg.n_clusters_max)
                    Z, order, _ = build_tree(cov, spec, space=st.cluster_space,
                                             method=cfg.linkage_method, k=k_ar)
                    labels = cluster_labels(Z, nc)
                    state = ClusterState(permnos=permnos[order], labels=labels[order],
                                         fitted_on=date, n_clusters=nc)
                    leaf = order
                    since = 0
                    rc_dates.append(date)
                else:
                    leaf, _ = state.adapt(permnos, spec, permnos)
                    since += 1

            # ---- holding window (needed BEFORE weights: the oracle reads it) --
            start = t + cfg.implementation_lag
            end = keys[i + 1] + cfg.implementation_lag - 1 if i + 1 < len(keys) else hi
            if start > end:
                continue
            seg = R.iloc[start:end + 1][permnos]

            # ---- weights -------------------------------------------------
            if st.allocator == "hrp":
                w = hrp_weights(cov, leaf)
            elif st.allocator == "erc":
                w = erc_weights(cov)
            elif st.allocator == "ew":
                w = equal_weight(cov)
            elif st.allocator == "minvar":
                w = min_variance(cov, long_only=cfg.long_only)
            elif st.allocator == "oracle":
                fwd = (1.0 + seg.fillna(0.0)).prod(axis=0).values - 1.0
                w = _oracle_weights(fwd, st.oracle_strength)
            else:
                raise ValueError(f"unknown allocator {st.allocator!r}")
            w = pd.Series(w, index=permnos)

            # Optional weight-path recording. OFF by default so existing runs
            # (including the frozen Null Gate v2) are bit-identical; Phase 1
            # turns it on to run an independent accounting reconciliation.
            if getattr(cfg, "store_weights", False):
                weight_path[R.index[start]] = w.copy()

            # ---- turnover & cost ----------------------------------------
            if prev_w is None:
                dw = w.abs().sum()
            else:
                al = w.reindex(w.index.union(prev_w.index)).fillna(0.0)
                pl = prev_w.reindex(al.index).fillna(0.0)
                dw = float((al - pl).abs().sum())
            cost = dw * cfg.tc_bps_one_way / 1e4
            turn_rows.append({"date": date, "turnover": 0.5 * dw, "cost": cost})

            # ---- hold to the next rebalance -----------------------------
            g, drift = self._hold(seg, w, rf.iloc[start:end + 1])
            net_seg = g
            if cost > 0 and len(g):
                net_seg = g.copy()
                net_seg.iloc[0] = (1.0 + net_seg.iloc[0]) * (1.0 - cost) - 1.0
            daily_gross.append(g)
            daily_net.append(net_seg)

            diag_rows.append({
                "date": date, "n_assets": n, "ar": ar, "mp_k": spec.k,
                "k_used": k_ar, "sigma2": spec.sigma2,
                "refit": refit, "n_clusters": state.n_clusters if state else np.nan,
            })
            prev_w = drift

        net = pd.concat(daily_net).sort_index() if daily_net else pd.Series(dtype=float)
        gross = pd.concat(daily_gross).sort_index() if daily_gross else pd.Series(dtype=float)
        turn = pd.DataFrame(turn_rows).set_index("date")["turnover"] if turn_rows \
            else pd.Series(dtype=float)

        return BacktestResult(
            name=st.name, returns=net, gross_returns=gross, turnover=turn,
            recluster_dates=rc_dates, weights=weight_path,
            diagnostics=pd.DataFrame(diag_rows).set_index("date") if diag_rows
            else pd.DataFrame(),
        )

    @staticmethod
    def _hold(seg: pd.DataFrame, w: pd.Series,
              rf_seg: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Buy-and-hold between rebalances, with weights drifting on realised
        returns. A delisted name (NaN return after its spliced final day) is
        treated as liquidated at the last close and held in cash at rf -- which
        is what actually happens, and is the honest alternative to quietly
        renormalising its weight away."""
        cur = w.copy()
        rets, idx = [], []
        for d, row in seg.iterrows():
            alive = row.notna()
            wa = cur.where(alive, 0.0)
            invested = float(wa.sum())
            cash = 1.0 - invested
            r = float((wa * row.fillna(0.0)).sum()) + cash * float(rf_seg.get(d, 0.0))
            rets.append(r)
            idx.append(d)
            grown = wa * (1.0 + row.fillna(0.0))
            tot = grown.sum() + cash * (1.0 + float(rf_seg.get(d, 0.0)))
            if tot > 0:
                cur = grown / tot
        return pd.Series(rets, index=idx), cur
