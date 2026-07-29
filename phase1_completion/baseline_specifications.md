# Phase 1 baseline specifications (frozen)

Development region only: 2003-01-08 -> 2022-12-30, 5,031 trading days, N = 100.
Covariance estimator: nonlinear Ledoit-Wolf (nls). Covariance window W = 504 (D4 rule,
median realized N = 100). Monthly rebalance, one-day implementation lag, long-only.

## Strategies

| Name | Allocator | Re-cluster | Definition |
|---|---|---|---|
| EW | equal_weight | n/a | 1/N |
| ERC | erc | n/a | equal risk contribution (Spinu 2013 cyclical coordinate descent, log-barrier) |
| MinVar | minvar | n/a | long-only minimum variance |
| HRP_static | hrp | never | canonical HRP recursive bisection (Lopez de Prado 2016), inverse-variance budgeting |
| MHRP_EV | hrp_equalvol | never | Molyboga (2020) component (ii) ONLY: equal-volatility budgeting. Within-cluster weights 1/sigma; split on cluster volatility sqrt(v). |

## Scope note on MHRP_EV
MHRP_EV implements ONLY the second of Molyboga's three MHRP modifications
(equal-volatility allocation). It is NOT full MHRP. Components (i) EWMA+Ledoit-Wolf
covariance and (iii) volatility targeting are not implemented. Must be labelled
"Molyboga equal-volatility allocation modification", never "MHRP" unqualified.

## Development-region results (nls, frozen estimator)

| Strategy | Sharpe | ann_return | ann_vol | max_dd | ann_turnover |
|---|---|---|---|---|---|
| MinVar | 0.576 | 0.092 | 0.154 | -0.426 | 1.502 |
| HRP_static | 0.574 | 0.096 | 0.163 | -0.461 | 1.455 |
| ERC | 0.549 | 0.096 | 0.173 | -0.502 | 0.656 |
| MHRP_EV | 0.534 | 0.093 | 0.175 | -0.511 | 1.779 |
| EW | 0.508 | 0.094 | 0.191 | -0.560 | 0.640 |

DEVELOPMENT-REGION ONLY. No test-region evaluation performed.

## Finding
Molyboga's equal-volatility allocation (component ii, in isolation) UNDERPERFORMS
inverse-variance HRP on large-cap US equities (0.534 vs 0.574), robustly across all
three covariance estimators (sample/lw_linear/nls). Consistent with the a priori
caution that Molyboga's ~50% CTA-portfolio improvement should not be assumed to
transfer to equities. Narrow claim only: component (ii) alone, not full MHRP.
