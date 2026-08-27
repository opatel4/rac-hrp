# Phase 1 Robustness — EWMA Covariance (Amendment rev.4): Closing Note

**Status:** amendment rev.4 closed. The EWMA constant-correlation estimator is
implemented, validated (8/8), wired into the shared dispatcher as `ewma_cc`, and
included in the Phase 1 estimator sensitivity sweep.

**Scope discipline (D10).** This sweep is a DIAGNOSTIC. It documents sensitivity;
it selects nothing. The estimator remains whatever the frozen pre-analysis plan
specifies (`nls`).

## Result — development-region estimator sensitivity (Sharpe)

| strategy | ewma_cc | lw_linear | nls | sample |
|---|---:|---:|---:|---:|
| ERC | 0.558 | 0.549 | 0.549 | 0.549 |
| EW | 0.508 | 0.508 | 0.508 | 0.508 |
| HRP_static | **0.608** | 0.591 | 0.574 | 0.594 |
| MHRP_EV | 0.568 | 0.554 | 0.534 | 0.557 |
| MinVar | 0.588 | 0.551 | 0.576 | 0.556 |

**Negative control.** EW is identical (0.508) across all four estimators, as it
must be: equal weighting never consults the covariance matrix. This confirms the
sweep is wired correctly and that observed differences are attributable to the
estimator rather than to run-to-run variation.

## Two findings, stated within their sample bounds

**(a) Exponentially weighted constant-correlation covariance improves every
covariance-dependent strategy examined.** Within the frozen development-region
estimator sweep, `ewma_cc` raises Sharpe for ERC, HRP_static, MHRP_EV and MinVar;
the largest effect is HRP_static, 0.574 -> 0.608. This is the largest estimator
effect in the table.

**(b) The equal-volatility allocation modification is not supported.** MHRP_EV
remains below HRP_static under EVERY covariance estimator examined
(0.568 vs 0.608; 0.554 vs 0.591; 0.534 vs 0.574; 0.557 vs 0.594). The ordering is
invariant to the estimator, so the underperformance is attributable to the
allocation rule rather than to a covariance interaction.

Taken together these separate the two Molyboga components tested here:

> Within the frozen development-region estimator sweep, exponentially weighted
> constant-correlation covariance improves every covariance-dependent strategy
> examined, whereas the equal-volatility MHRP allocation remains below static HRP
> under every covariance estimator.

This is deliberately sample-bounded. The test region has not been opened, so no
claim is made about out-of-sample transfer.

Note that only component (ii) of Molyboga's three modifications is implemented as
`MHRP_EV`. Component (i) (exponentially weighted covariance) is implemented
separately as the `ewma_cc` estimator; component (iii) (volatility targeting) is
excluded as a leverage overlay. The decomposition above therefore compares (i) and
(ii) as implemented here, not Molyboga's full construction.

## Discipline point

`ewma_cc` outperforms the pre-registered `nls` specification on four of the five
strategies. Per D10 and the frozen pre-analysis plan, **the design is not
retroactively changed to exploit this.** The pre-registered NLS specification is
not the ex-post best-performing covariance estimator in this sample; that is
recorded as a fact about the sweep, not as grounds for revision, and no claim is
made that NLS is theoretically or statistically conservative.

## Provenance

Produced by `scripts/run_phase1.py --estimators sample,lw_linear,nls,ewma_cc`
against the development region (2003-01-08 -> 2022-12-30, 5,031 days, N = 100,
W = 504). Accounting reconciliation passed for all five baselines (median absolute
difference 0.0 between independently recomputed and engine gross returns).

The `ewma_cc` dispatcher entry applies a row reversal: the EWMA estimator expects
row 0 = most recent, while the pipeline slices forward. Omitting it would invert
the decay (oldest observation weighted 7.5x the newest at alpha = 0.996, W = 504)
and produce a well-formed but wrong matrix that no existing check would catch —
Kish ESS, weight normalisation, symmetry and PSD are all order-invariant. The
adapter is verified: wired output equals a direct call on reversed input, and
differs from unreversed input (max absolute difference 0.205).
