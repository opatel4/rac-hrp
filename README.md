# RAC-HRP — Regime-Adaptive Clustering Hierarchical Risk Parity

A pre-registered empirical study of whether **absorption-ratio-triggered re-clustering**
improves hierarchical risk parity portfolios under changing equity correlation regimes.

**Status:** Phase 0.5 complete (data engineering, validation, null gate).
Phase 1 in progress (static baselines). Test region untouched.

---

## The question

Hierarchical Risk Parity (López de Prado 2016) clusters assets by correlation structure
and allocates by recursive bisection. In practice the clustering is either estimated once
or re-estimated on a fixed schedule. Neither responds to the thing that should actually
motivate re-clustering: a change in the correlation structure itself.

RAC-HRP re-clusters **when the absorption ratio** (Kritzman et al. 2011) **signals a
structural break**, rather than on a calendar. The research question is whether that
conditional re-clustering earns its keep relative to (a) never re-clustering and
(b) re-clustering on a schedule.

This is a narrow, falsifiable question, and the repository is organised around trying
hard to falsify it.

---

## Why this repo looks the way it does

Most of the engineering here is not about generating returns. It is about making a
performance number mean something. Three commitments drive the structure:

**1. Decisions are pre-registered, hashed, and frozen before data is seen.**
Structural choices (universe, covariance window rule, fold geometry, decision rules) are
frozen in a pre-analysis plan. Amendments require a documented evidence trail and
independent approval. `CHANGELOG.md` is the audit trail; `docs/protocol/` holds the
frozen protocols.

**2. The pipeline must fail a null before it is trusted.**
A synthetic-null gate destroys the signal in the data, keeps the pipeline, and demands
a flat result. A pipeline that produces an edge on signal-free data is manufacturing it.
The gate is two-tier: a **primary gate** comparing RAC-HRP only against strategies that
differ *solely* in re-clustering policy (this is what can block progress), and a
**diagnostic panel** of cross-allocator comparisons that are reported but never gate.
That separation exists because an earlier version conflated "does the trigger work" with
"do HRP and ERC differ" — see `CHANGELOG.md`.

**3. Survivorship bias is treated as a gate, not a caveat.**
The universe is built point-in-time from CRSP with delisting returns spliced
(Shumway 1997). A reconstruction gate verifies that companies which actually failed —
Enron, Lehman, Washington Mutual, Bear Stearns, GM, AIG — are present in the panel *and*
book their collapses. A panel can contain a failed firm, drop it at the right moment, and
still be biased if the price series stops at the last quote instead of taking the
delisting return. That is the silent failure mode the gate is built to catch.

---

## Repository layout

```
rac_hrp/
  config.py            frozen pre-analysis decisions (D1–D10)
  data/                point-in-time panel, universe construction, validation gates
  core/                covariance estimators, MP spectrum, clustering, allocators
  backtest/            walk-forward engine, purged/embargoed folds, metrics
  nulls/               synthetic null environments; Null Gate v1 and v2
scripts/
  run_phase05.py       data engineering + reconstruction gate + null gate
  run_phase1.py        static baselines (development region only)
tests/                 unit tests
docs/
  protocol/            frozen protocols and decision memoranda
  literature/          our own review notes (third-party PDFs are not redistributed)
results/               curated, publishable result artifacts (see results/README.md)
```

---

## Reproducing

Requires a WRDS subscription with CRSP daily stock file access. **No data is
distributed with this repository** — CRSP is licensed and not redistributable.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. pull point-in-time CRSP data (requires WRDS credentials)
python -m rac_hrp.data.wrds_pull --outdir data/raw --user YOUR_WRDS_ID \
    --universe crsp_largecap

# 2. Phase 0.5 -- reconstruction gate + null gate
python scripts/run_phase05.py --raw data/raw --n 100 --universe crsp_largecap \
    --gate v2 --outdir outputs/phase05

# 3. Phase 1 -- static baselines (development region only)
python scripts/run_phase1.py --raw data/raw --n 100 --outdir outputs/phase1

# tests
python tests/test_phase05.py
```

Keep `data/` outside the repository, or rely on `.gitignore` — it excludes every
data pattern deliberately broadly.

---

## Universe (D1, amended)

The study was designed on the S&P 500. S&P **constituent history** is a premium licence
this institution does not hold, confirmed empirically: the accessible Compustat index
table returns current constituents with zero exit dates, while the same table carries
exits for non-US indices. Using a current-constituent list retroactively would be
survivorship bias in its purest form.

The universe was therefore amended to a **CRSP-native rule**: the N largest US common
shares by lagged market capitalisation (share codes 10–11, exchanges 1–3), reconstituted
monthly, delisting returns spliced. This is arguably the better design regardless — the
hypothesis concerns large-cap US equities, not index membership, and a mechanical
market-cap rule has no index committee whose discretionary additions and deletions are
entangled with the correlation dynamics being measured. Full evidence trail in
`CHANGELOG.md`.

---

## Method summary

| Component | Choice |
|---|---|
| Universe | top-N US common shares by lagged market cap, monthly reconstitution |
| Covariance | nonlinear Ledoit-Wolf shrinkage; window set by a deterministic rule (D4) |
| Regime signal | absorption ratio from the Marchenko–Pastur-filtered spectrum |
| Trigger | ΔAR exceeding a threshold (calibration gate pre-registered for Phase 2) |
| Allocation | HRP recursive bisection |
| Benchmarks | HRP-static, HRP-periodic, ERC, equal weight, minimum variance |
| Validation | purged/embargoed walk-forward; development folds have no model-selection role |

---

## Reproducibility artifacts

Null Gate v2 was frozen before execution. `results/` carries the freeze manifest —
SHA-256 hashes of the gate code, the base seed, replication counts, and decision rules —
so the claim that the executed code is the frozen code is verifiable rather than
asserted.

---

## References

López de Prado (2016), *Building Diversified Portfolios that Outperform Out of Sample*;
Kritzman, Li, Page & Rigobon (2011), *Principal Components as a Measure of Systemic
Risk*; Ledoit & Wolf (2004, 2020), covariance shrinkage; Molyboga (2020), *A Modified
Hierarchical Risk Parity Framework for Portfolio Management*; Shumway (1997), delisting
returns; Roncalli (2013), *Introduction to Risk Parity and Budgeting*.

Full annotated review in `docs/literature/`.

---

## Licence

See `LICENSE`. Third-party papers are not redistributed. CRSP/Compustat data is licensed
to the subscribing institution and is not included.
