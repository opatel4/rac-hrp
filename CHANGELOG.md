# Changelog

## D1 AMENDED — universe changed from S&P 500 to CRSP large-cap
**Date:** 2026-07-14 · **Status:** FORCED (data licensing), decided BEFORE any result was seen

### Was
CRSP point-in-time S&P 500 universe, 2000–2025, via `crsp.dsp500list`.

### Now
The **N largest US common stocks by lagged market capitalisation**, from CRSP:
share codes 10–11, exchanges 1–3 (NYSE/AMEX/Nasdaq), ranked on market cap lagged
21 trading days, reconstituted monthly, delisting returns spliced (Shumway 1997).

### Why — this was not a choice
S&P 500 constituent *history* is not reachable from this WRDS account by any route:

| Source | Status |
|---|---|
| `crsp.dsp500list` / `crsp_a_indexes` | NO ACCESS (not licensed) |
| `crsp.ccmxpf_lnkhist` (CCM link) | NO ACCESS (not licensed) |
| `comp.idxcst_his`, gvkeyx=000003 | READABLE but **503 spells, 0 exit dates** |

The diagnostic that settled it: the same Compustat table carries **1,267 exits for
the S&P/TSX** and **420 for the Nasdaq 100**, but **zero** for every S&P *US* index
(500, Smallcap 600, 1500). S&P licenses US constituent history as a premium product
this institution does not hold. It is a licensing boundary, not a bug, and no query
recovers it.

Using the 503 current constituents retroactively would have been survivorship bias
in its purest form — every firm that failed between 2000 and 2025 silently absent.
That is a fatal, unfixable flaw, and it is the exact thing the Phase 0.5
reconstruction gate exists to prevent. The gate did its job before a single result
was produced.

### Why the replacement is defensible on the merits, not merely tolerable
1. **The hypothesis never mentioned the S&P 500.** The claim concerns
   absorption-ratio-triggered re-clustering under changing equity correlation
   regimes. "Large-cap US equities" *is* the population of interest; index
   membership was only ever a proxy for it.
2. **The S&P Index Committee is a confound.** It adds names after they have
   performed and removes them after they have not. That discretionary selection is
   entangled with the correlation dynamics under study. A mechanical market-cap rule
   has no committee, no announcement effect, no discretion to control for.
3. **It is more reproducible.** Any standard CRSP subscription rebuilds this
   universe exactly. Without the premium S&P license — which now includes us —
   nobody can rebuild an S&P 500 one.

### Consequences
- `rac_hrp/data/crsp_universe.py` (new): eligibility spells + two-stage pull
  pre-screen (monthly file → permnos ever in top-750 → daily pull).
- `rac_hrp/data/validation_crsp.py` (new): **T3 gate rewritten.** "Index size ≈ 500"
  and "Lehman leaves the index" are meaningless now. The survivorship question is
  tested *more* directly instead: Enron / Lehman / WaMu / Bear / GM / AIG must be
  **present** in the universe beforehand, **absent** after, and must **book their
  actual losses** — the third being the failure mode a biased panel passes silently
  (a price series that stops at the last quote never takes the hit).
- Downstream code is **unchanged**. `is_member()` now means "US ordinary common
  share on a major exchange" rather than "in the index"; the top-N-by-lagged-mcap
  cut happens exactly where it always did.
- **Paper must state the universe definition explicitly**, and why.

### Open
S&P 500 remains desirable as a *robustness subsample*. Librarian request for
`crsp_a_indexes` / CCM is outstanding; if granted, the pull already prefers it
automatically (`--universe sp500`) with no code change.

---

## Phase 0.5 — implementation

### D9 amended: null gate is ONE-SIDED
- **Was:** two-sided equivalence band, |mean dSharpe| <= 0.10.
- **Now:** `null_gate_sided = "one"`. Only a POSITIVE edge blocks the gate.
- **Rationale:** the null gate exists to falsify *manufactured signal*, which is
  directional. RAC-HRP UNDER-performing static HRP on a signal-free panel is not
  manufactured signal — it is the trigger churning the tree for nothing. That is a
  real cost, but it is a Phase 2/3 turnover question, not a validity question.
- **Consequence:** under the two-sided rule, Env-D vs HRP_static (mean -0.093)
  demanded ~5,900 replications to establish equivalence — a wall, not a gate.
- **Decided by:** Om, before any real-data result was seen. Source: Phase 0.5
  implementation review.

### Three design issues discovered during implementation
1. **HRP leaf ordering is permutation-dependent.** A dendrogram admits 2^(N-1)
   valid leaf orders; HRP bisects by list position, so column order changes the
   portfolio. Re-clustering could therefore manufacture turnover unrelated to any
   regime change, contaminating Phase 3. Fixed with `optimal_leaf_ordering`
   (Bar-Joseph 2001). Pinned by 2 tests.
2. **Null gate must be an equivalence test, not a difference test.** "CI contains
   zero" is unfalsifiable at low replication counts. Replaced with a three-way
   PASS / FAIL / INCONCLUSIVE verdict requiring the entire CI inside the margin.
3. **Comparator sets are environment-specific.** Env-C keeps returns real and nulls
   only trigger timing, so demanding "no edge over EW" would demand that HRP never
   beat equal-weight. Env-C uses same-policy comparators only (static, periodic).

### Open decisions (unresolved, flagged in README)
- `mp_k_mode`: MP-implied k drifts and AR is mechanically increasing in k.
  Currently frozen per fold. Needs an explicit ruling.
- `ClusterState.adapt`: how a "frozen" tree absorbs universe churn.
- `purge_days = 21`: precautionary; the pipeline is causal, so arguably 0.

---

## Phase 0.5 — two bugs caught by the T3 gate on first real-data run

### BUG 1 (real): delisting splice injected ~25,000 phantom permnos
`_splice_delisting` outer-merged the panel against the **full CRSP delisting table**
(~28k permnos, every stock that ever died) rather than against the permnos actually
pulled. Result: a returns panel of 7,552 x **27,851** instead of 7,552 x ~3,022 —
about 1.7GB of NaN columns. Fixed by restricting the delist table to permnos present
in `dsf` **before** the merge. The outer merge is still required after that filter,
because a delisting date can fall one day after the stock's last `dsf` row and that
row must be *created*, not dropped — which is the entire point of the splice.

### BUG 2 (in the gate itself): known-failure check resolved companies by TICKER
Tickers are recycled. **`WM` today is WASTE MANAGEMENT, not Washington Mutual** —
so the check resolved to a healthy company, found no crash, and reported
survivorship bias that did not exist. `LEH`, `BSC` and `ENE` have likewise been
reissued. Ironic, given `membership_compustat.py` explicitly warns against ticker
joins for exactly this reason.

Fixed: companies are now resolved by **CRSP company name** (`comnam`) and the
matched permno is reported in the evidence table so the resolution is auditable.

Also changed the crash test from **worst single day** to **cumulative window
return** (< -70%). GM and AIG bled out over months rather than gapping in one
session; a worst-day test would have wrongly cleared a panel that never booked the
collapse at all.

### Still open, and material: CRSP daily data ends 2024-12-31
The pulled calendar runs 1995-01-03 → **2024-12-31**, but the pre-registered test
region is 2023-01-03 → **2025-11-28**. The last ~11 months of the single-touch test
window do not exist in this CRSP vintage. Requires a decision: amend `TEST_END`, or
obtain an updated CRSP vintage. Do not silently truncate.

---

## Null Gate v2 — implemented and frozen (signed protocol rev.2)

Two-tier gate authorized by the signed protocol and its amendments. v1 is untouched
and remains the immutable historical record; v2 is a separate module set.

### New files
- `rac_hrp/nulls/gate_v2_config.py` — all frozen parameters. base seed 522618064
  (OS entropy, never previously executed/inspected); reps D=200, A/B/C=150;
  margin +0.10; comparators {HRP_static, HRP_periodic_3}.
- `rac_hrp/nulls/gate_v2_stats.py` — exact formulas: one-sided paired-t bounds
  [A-2], deterministic location-shift controls, paired percentile bootstrap [A-4],
  trigger-activation rule [A-3]. Unit-verified against hand computation.
- `rac_hrp/nulls/gate_v2.py` — two-tier orchestration, per-replication persistence
  [A-5], freeze manifest with SHA256 code hashes [P§8].

### Design points (all per signed rulings)
- **Primary gate (gating):** RAC-HRP vs same-policy {static, periodic_3}, one-sided
  paired-t, PASS if U≤+0.10, FAIL if L>+0.10, else INCONCLUSIVE.
- **Diagnostic panel (non-gating):** RAC-HRP and static vs {EW, ERC}, reported only.
- **Controls:** location shift d^(δ)=(d−d̄)+δ per cell; null δ=0.00 must PASS,
  positive δ=+0.20 must FAIL; misclassification → whole-gate
  INCONCLUSIVE — CONTROL VALIDATION REQUIREMENT NOT MET. Verified: D at 200 reps
  gives positive-control lower bound 0.1645 > 0.10 (self-validating power).
- **Trigger activation:** median firing ≥5% AND ≥90% of reps with ≥3 events, else
  env cells → INCONCLUSIVE — LOW TRIGGER ACTIVATION.
- **No sequential stopping.** Counts fixed.
- **Oracle power-check** retained as separately-labeled non-gating diagnostic only.

### Run
    python scripts/run_phase05.py --raw data/raw --n 100 --universe crsp_largecap \
        --gate v2 --outdir outputs/n100_v2

Reps are taken from the frozen config, not --reps. Writes primary_gate.csv,
diagnostic_panel.csv, replication_sharpe_matrix.csv, freeze_manifest.json.

---

## Phase 1 — static baseline harness (development region only)

Authorized scope: development-region implementation only. Test-region evaluation
remains blocked pending the endpoint resolution.

### New
- `scripts/run_phase1.py` — static baselines (EW, ERC, HRP_static, MinVar) on the
  dev region; estimator sensitivity sweep {sample, lw_linear, nls} as a DIAGNOSTIC
  (D10: dev folds select nothing); accounting reconciliation; turnover reporting.
  Contains a **structural test-region guard**: raises PermissionError if any
  evaluation position falls on/after TEST_START.

### Changed (additive, default-off)
- `engine.py` / `config.py`: opt-in `store_weights` flag records the rebalance
  weight path. OFF by default so all prior runs — including frozen Null Gate v2 —
  are bit-identical. Phase 1 enables it solely to run the accounting check.

### Accounting reconciliation
Independently recomputes portfolio gross return from the stored weight path and
compares against the engine's own `gross_returns` (NOT `returns`, which books
turnover cost on rebalance days and would differ by construction). On mock:
238 rebalance dates/strategy, median |diff| = 0.0, max ~1e-6.

**The check cannot pass vacuously.** If no weight path was recorded, the result is
UNVERIFIED and returns non-zero — it is not reported as a pass. Same rule as the
null gate's trigger-activation requirement.

### Not yet implemented — awaiting decision
Molyboga (2020) sub-cluster covariance variant. Blocked on disambiguation of
"EW covariance": the literature review records Molyboga as *exponentially
weighted* covariance + Ledoit-Wolf, not *equal-weighted*. These are different
estimators and the choice is pre-registered, so it is not being guessed.

---

## Phase 2 + EWMA — implementation against FROZEN specifications

Both specifications countersigned and frozen before any code was written:
  * "PHASE 2 — PRE-REGISTRATION & CALIBRATION GATE (rev.5)"  [AUTHORIZE AND FREEZE: YES]
  * "AMENDMENT — EWMA COVARIANCE (rev.4)"                    [ADOPT AND FREEZE]

### New: rac_hrp/core/covariance_ew.py
Weighted constant-correlation Ledoit-Wolf extension. Truncated/renormalised
weights w_j = (1−α)α^j/(1−α^504); weighted-mean centring; constant-correlation
target (F_ii = s_ii, F_ij = r̄√(s_ii s_jj)) — the JPM "Honey" target Molyboga
cites, NOT the JMVA scaled-identity target used by the existing `lw_linear`.
Full weighted π̂/ρ̂/γ̂/κ̂/δ. α primary 0.996; sensitivity {0.990, 0.996, 0.997}.

Labelled in-code as a PROSPECTIVELY SPECIFIED EXTENSION, not the Ledoit-Wolf
analytical estimator: LW assumes i.i.d. observations and exponential weighting
breaks that, so substituting w_j for 1/T and N_eff for T is not a theorem.

### New: tests/test_covariance_ew.py — MANDATORY, gates EWMA use
All 7 required checks pass (8/8 including the exact-α=1 variant). Key result:
at α→1 the weighted estimator converges to an independently written
constant-correlation LW reference (1.6e-5 relative; 1.7e-15 at exactly α=1),
which is the transcription check on ρ̂. N_eff reproduces the amendment table
(196.5 / 382.1 / 425.6) from the ACTUAL truncated weights, not the
infinite-horizon formula.

### New: rac_hrp/phase2/{config,stats}.py
Frozen parameters and the exact statistical rules. Phase-adjusted separation
J* over q ∈ {2..12}, r ∈ {0..q−1}; placebo Monte Carlo (PCG64, seed 20260817,
B = 100,000, 95th pct, weak inequality), recomputed per candidate; timing
variation (CV and modal-gap share); circular block bootstrap for D_VI with
Politis-White block length, joint (VI_t, I_t) resampling, centred one-sided
p = (1 + #{D*_b − D̂ ≥ D̂})/(B+1); Holm across the four γ.
σ̂ uses ddof = 1 — AUDITED as-built (pandas default), not chosen.

### New: tests/test_phase2_stats.py — 12/12 pass
Reproduces the frozen values exactly: placebo 0.3818 at |T|=112 and 0.1714 at
|T|=12; the adversarial every-2nd-rebalance/odd-phase trigger scores J* = 1.000
with phase adjustment and only 0.252 without it. Bootstrap null calibration
P(p≤0.05) = 0.065 over 200 null datasets; Politis-White returns L = 2 on iid
and L = 17 on AR(1) ρ = 0.85.

### Manifest metadata to record at execution (advisor note, not a spec change)
Politis-White integer block length per candidate and the implementation used
(in-repo, no third-party package); count of degenerate bootstrap replicates
(one I class empty) — these are discarded from numerator and denominator and
the count is returned by `circular_block_bootstrap_p`.

### NOT yet implemented
The calibration runner that drives the trigger across γ candidates and applies
the deterministic selection rule. Requires engine integration.

---

## Phase 2 calibration runner — implemented

`rac_hrp/phase2/calibration.py`. Steps 1-3 of the frozen procedure:
structural diagnostics for every gamma; deterministic selection applied in code;
hashed frozen record written. Steps 4-5 (Null Gate v2, then performance) happen
elsewhere and only after this gate selects.

PERFORMANCE-BLIND BY CONSTRUCTION: the module never calls the engine's return
path and never touches the risk-free series, so it has no way to produce a
performance number. Selection cannot be influenced by one even accidentally.

- Counterfactual clusterings recomputed at EVERY eligible rebalance, so D_VI
  compares triggered against non-triggered structural change on equal footing.
  VI computed on the INTERSECTION of consecutive permno sets (universe turnover
  means the asset sets differ between dates).
- `variation_of_information` added to `core/clustering.py` alongside ARI, and
  the duplicate definition inside calibration.py was removed — one gating
  statistic, one implementation. Verified numerically identical before removal.
- Manifest records everything the advisor asked for: Politis-White integer block
  length per candidate, the in-repo implementation used, degenerate-replicate
  counts, code hashes, and — when no candidate passes — an explicit stop_reason
  plus the failed criteria per gamma.

Smoke test on mock data: runs end to end, no candidate passes, `phase2_stops`
recorded with reasons. That is the correct behaviour on synthetic data with no
genuine regime structure; it is NOT predictive of the real-data result.

Fixed while wiring: `cfg.cluster_count_rule`/`min_clusters`/`max_clusters` do not
exist; the real fields are `n_clusters_rule`/`n_clusters_min`/`n_clusters_max`.

### scripts/run_phase2.py — orchestrator
Drives the frozen calibration gate. Applies the D4 window rule BEFORE fold
construction (the Phase 1 bug, not repeated) and raises PermissionError on any
evaluation position at or after TEST_START. Prints the calibration table, the
selection outcome, and — when nothing passes — the failed criteria per gamma.

`--quick` reduces Monte Carlo counts for smoke testing and says loudly that the
results are not the frozen specification and must not be reported.
