"""
Generate the paper figures from frozen artefacts.

    OPENBLAS_NUM_THREADS=1 python scripts/make_paper_figures.py --raw ~/rac_hrp_data/raw

Fig 1  absorption ratio and dAR/sigma with trigger events marked  (RECOMPUTED:
       the AR series is not persisted by any artefact, only its summary
       statistics; structural_pass is re-run on the development region, which
       reproduces the frozen numbers exactly)
Fig 2  D_VI and Holm-adjusted p across gamma            (calibration_table.csv)
Fig 3  B_gamma null distributions by environment        (mechanism_null.json)
Fig 4  estimator sensitivity                            (Table 2 values)

Outputs 300-dpi PNG and vector PDF into figures/.
"""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Publication styling: greyscale-safe, no chartjunk.
plt.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 300, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "legend.frameon": False, "figure.autolayout": True,
})
INK, ACC, MUT = "#1a1a1a", "#c1121f", "#8d99ae"
GAMMAS = (0.5, 1.0, 1.5, 2.0)


def save(fig, name, outdir):
    for ext in ("png", "pdf"):
        fig.savefig(Path(outdir) / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {name}.png / .pdf")


# ---------------------------------------------------------------- Fig 1
def fig1_ar_series(raw, n_assets, outdir):
    from rac_hrp.config import (Config, TEST_START, select_cov_window,
                                SAMPLE_START, DEV_END)
    from rac_hrp.data import panel
    from rac_hrp.data.universe import UniverseBuilder, realized_n_report
    from rac_hrp.backtest.folds import FoldGenerator
    from rac_hrp.phase2.calibration import structural_pass

    P = panel.build_panels(raw)
    cfg0 = Config(n_assets=n_assets)
    cal = P.returns.index
    probe = cal[(cal >= SAMPLE_START) & (cal <= DEV_END)][::cfg0.rebalance_freq]
    med_n = float(realized_n_report(
        UniverseBuilder(P, cfg0).snapshots(probe)).n_selected.median())
    cfg = Config(n_assets=n_assets, cov_window=select_cov_window(med_n))
    folds = FoldGenerator(cal, cfg).dev_folds()
    eval_pos = np.concatenate([f.test_pos for f in folds])
    fb = [(int(f.test_pos[0]), int(f.test_pos[-1])) for f in folds]
    if (cal[eval_pos] >= pd.Timestamp(TEST_START)).any():
        raise PermissionError("figure generation reached the test region")

    sp = structural_pass(P, cfg, eval_pos, fb, verbose=False)
    dates = pd.to_datetime(sp.dates)
    elig = np.where(sp.eligible)[0]
    E = len(elig)
    print(f"  structural pass: E={E} eligible (frozen record: 233)")

    fig, ax = plt.subplots(2, 1, figsize=(7.2, 5.0), sharex=True,
                           gridspec_kw={"height_ratios": [1, 1.25]})

    ax[0].plot(dates, sp.ar, color=INK, lw=1.1)
    ax[0].set_ylabel("absorption ratio")
    ax[0].set_title(f"Absorption ratio, development region "
                    f"(k = 15 fixed, W = {cfg.cov_window})", loc="left")

    z = np.full(len(sp.ar), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        z[elig] = np.abs(sp.d_ar[elig]) / sp.sigma[elig]
    ax[1].plot(dates, z, color=MUT, lw=0.9, label=r"$|\Delta AR_t|/\hat\sigma_t$")
    for g, ls in zip(GAMMAS, [":", "-.", "--", "-"]):
        ax[1].axhline(g, color=INK, lw=0.7, ls=ls, alpha=0.8,
                      label=rf"$\gamma$ = {g}")
    fired = elig[np.abs(sp.d_ar[elig]) > 2.0 * sp.sigma[elig]]
    ax[1].plot(dates[fired], z[fired], "o", ms=3.2, color=ACC,
               label=r"fires at $\gamma$ = 2.0")
    # A single ~12.5 spike (2020) otherwise compresses all four thresholds into
    # the bottom sixth of the panel. Log scale keeps them separable while
    # retaining the outliers.
    ax[1].set_yscale("log")
    ax[1].set_ylim(0.08, 20)
    ax[1].set_yticks([0.1, 0.5, 1, 2, 5, 10])
    ax[1].set_yticklabels(["0.1", "0.5", "1", "2", "5", "10"])
    ax[1].set_ylabel("standardised |change|  (log)")
    ax[1].set_xlabel("")
    ax[1].legend(ncol=3, fontsize=7.5, loc="upper left")
    ax[1].set_title("Standardised absorption-ratio change and trigger thresholds",
                    loc="left")
    save(fig, "fig1_absorption_ratio_and_triggers", outdir)
    return sp, E


# ---------------------------------------------------------------- Fig 2
def fig2_dvi(outdir):
    t = pd.read_csv(ROOT / "outputs" / "phase2" / "calibration_table.csv")
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.9))

    ax[0].plot(t.gamma, t.D_VI, "o-", color=INK, ms=5, lw=1.2)
    ax[0].axhline(0, color=MUT, lw=0.8)
    for _, r in t.iterrows():
        ax[0].annotate(f"n={int(r.n_events)}", (r.gamma, r.D_VI),
                       textcoords="offset points", xytext=(0, 9),
                       ha="center", fontsize=7, color=MUT)
    ax[0].set_xlabel(r"$\gamma$"); ax[0].set_ylabel(r"$D_{VI}$")
    ax[0].set_ylim(-0.008, t.D_VI.max() * 1.30)   # room for the n= annotations
    ax[0].set_title(r"Clustering-change effect (point estimates)", loc="left")

    ax[1].plot(t.gamma, t.p_holm, "o-", color=INK, ms=5, lw=1.2,
               label="Holm-adjusted")
    ax[1].plot(t.gamma, t.p_raw, "s--", color=MUT, ms=4, lw=1.0, label="raw")
    ax[1].axhline(0.05, color=ACC, lw=1.0, ls="--", label=r"$\alpha$ = 0.05")
    ax[1].set_xlabel(r"$\gamma$"); ax[1].set_ylabel("p-value")
    ax[1].set_ylim(0, 0.62)
    ax[1].legend(fontsize=7.5)
    ax[1].set_title("No candidate clears the pre-registered level", loc="left")
    save(fig, "fig2_cluster_informativeness", outdir)


# ---------------------------------------------------------------- Fig 3
def fig3_mechanism(outdir):
    rec = json.load(open(ROOT / "outputs" / "phase2_mechanism" / "mechanism_null.json"))
    reps, man = rec["replications"], rec["manifest"]
    envs = [("A_iid_gaussian", "A: no correlation"),
            ("S_static_corr", "S: static covariance"),
            ("D_regime_switch_vol", "D: designed regimes")]
    real = {float(g): v["B"] for g, v in man["real"].items()}

    fig, axes = plt.subplots(1, 4, figsize=(7.6, 2.9), sharey=False)
    for ax, g in zip(axes, GAMMAS):
        data = [[r["gammas"][str(g)]["B"] for r in reps[e]
                 if r["gammas"][str(g)]["timing_defined"]] for e, _ in envs]
        bp = ax.boxplot(data, widths=0.55, showfliers=False,
                        patch_artist=True, medianprops=dict(color=INK, lw=1.2))
        for patch in bp["boxes"]:
            patch.set(facecolor="#e9ecef", edgecolor=INK, lw=0.8)
        ax.axhline(real[g], color=ACC, lw=1.5, zorder=3)
        ax.annotate("real", (3.42, real[g]), color=ACC, fontsize=7.5,
                    va="center", annotation_clip=False)
        # Headroom: the real value must sit clearly INSIDE the axes, not on the
        # frame, or the gap between it and the nulls reads as zero.
        lo = min(min(d) for d in data)
        hi = max(max(max(d) for d in data), real[g])
        pad = 0.14 * (hi - lo)
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_xlim(0.4, 3.6)
        ax.set_xticks([1, 2, 3]); ax.set_xticklabels(["A", "S", "D"])
        ax.set_title(rf"$\gamma$ = {g}", loc="left", fontsize=9)
        if ax is axes[0]:
            ax.set_ylabel(r"excess burstiness $B_\gamma$")
    fig.suptitle("Real-data burstiness (red) against regime-free pipeline nulls, "
                 "500 replications per environment", fontsize=9, y=1.04, x=0.02,
                 ha="left")
    save(fig, "fig3_mechanism_null", outdir)


# ---------------------------------------------------------------- Fig 4
def fig4_estimators(outdir):
    est = ["sample", "lw_linear", "nls", "ewma_cc"]
    vals = {"HRP_static": [0.594, 0.591, 0.574, 0.608],
            "MHRP_EV":    [0.557, 0.554, 0.534, 0.568],
            "MinVar":     [0.556, 0.551, 0.576, 0.588],
            "ERC":        [0.549, 0.549, 0.549, 0.558],
            "EW":         [0.508, 0.508, 0.508, 0.508]}
    fig, ax = plt.subplots(figsize=(5.4, 3.1))
    x = np.arange(len(est))
    for name, v in vals.items():
        style = dict(lw=1.6, ms=5) if name in ("HRP_static", "MHRP_EV") else dict(lw=1.0, ms=4, alpha=0.75)
        ax.plot(x, v, "o-", label=name,
                color=ACC if name == "HRP_static" else (INK if name == "MHRP_EV" else MUT),
                **style)
    ax.set_xticks(x); ax.set_xticklabels(est)
    ax.set_ylabel("Sharpe (development region)")
    ax.set_title("Estimator sensitivity: diagnostic only, selects nothing", loc="left")
    ax.legend(fontsize=7.5, ncol=2)
    ax.annotate("EW is covariance-free\n(negative control)", (3, 0.508),
                textcoords="offset points", xytext=(-92, -2), fontsize=7, color=MUT)
    save(fig, "fig4_estimator_sensitivity", outdir)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.expanduser("~/rac_hrp_data/raw"))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--outdir", default=str(ROOT / "figures"))
    ap.add_argument("--skip-fig1", action="store_true",
                    help="skip the figure that requires recomputing the AR series")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    print(f"figures -> {a.outdir}")
    if not a.skip_fig1:
        fig1_ar_series(a.raw, a.n, a.outdir)
    fig2_dvi(a.outdir)
    fig3_mechanism(a.outdir)
    fig4_estimators(a.outdir)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
