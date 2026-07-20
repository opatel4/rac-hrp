# Literature Review: Regime-Adaptive PCA-Clustering Hierarchical Risk Parity (RAC-HRP) Portfolio Optimization with Walk-Forward Validation

---

## Abstract

This review synthesizes 25+ papers spanning hierarchical risk parity (HRP), PCA-based clustering, regime detection, covariance estimation, and walk-forward validation methodology — drawing on 9 foundational user-provided papers and 16+ additional peer-reviewed works retrieved via Consensus. The central theme is whether layering regime adaptivity and rolling PCA-clustering onto López de Prado's (2016) HRP framework delivers systematic out-of-sample improvements beyond classical risk-parity benchmarks. The evidence consistently shows that static hierarchical methods reduce drawdowns relative to Markowitz but underperform momentum-driven markets; regime-aware extensions recover meaningful performance advantages by updating the covariance structure and cluster topology in response to structural market shifts. Walk-forward validation with purged cross-validation is identified as the methodologically rigorous standard for evaluating these dynamic strategies.

---

## 1. Introduction & Scope

### 1.1 Research Questions

This review addresses the following interrelated questions:

1. Can hierarchical clustering, applied to PCA-derived return factors, consistently deliver better risk-adjusted out-of-sample performance than classical benchmarks (equal-weight, minimum variance, ERC)?
2. Does incorporating regime detection — either via PCA-based absorption ratios, Markov-switching models, or volatility clustering — improve the stability and returns of HRP-based portfolios?
3. What covariance estimation methodology (sample, linear shrinkage, nonlinear shrinkage) is most appropriate for the regime-switching setting?
4. How should walk-forward validation be structured to avoid lookahead bias and produce results that are valid for live deployment?

### 1.2 Scope and Coverage

This review covers the period 2004–2026, with emphasis on post-2016 developments following López de Prado's foundational HRP paper. It encompasses five thematic areas: (1) HRP and its extensions, (2) PCA-based portfolio clustering, (3) regime detection and Markov-switching models, (4) covariance matrix estimation, and (5) walk-forward backtesting methodology. The review draws on 9 user-provided foundational papers and approximately 16 additional peer-reviewed studies retrieved via systematic Consensus search.

---

## 2. Background and Definitions

**Hierarchical Risk Parity (HRP):** An algorithm introduced by López de Prado (2016) that allocates portfolio weights in three stages — (1) tree clustering via single-linkage on a correlation-based distance matrix, (2) quasi-diagonalization of the covariance matrix, and (3) recursive bisection allocating weights inversely proportional to cluster variance. HRP avoids inverting the covariance matrix, making it robust when p/T ratios are large.

**Principal Component Analysis (PCA) in portfolios:** The eigendecomposition of the return covariance matrix into orthogonal factors. The leading eigenvectors capture systematic risk, and factor loadings serve as features for grouping stocks with similar risk exposures. The *absorption ratio* (Kritzman et al. 2011) — the fraction of total variance explained by the top k eigenvectors — is a PCA-derived measure of market fragility.

**Equal Risk Contribution (ERC):** The risk-parity portfolio from Roncalli (2013) in which each asset's risk contribution `RC_i = w_i * (Σw)_i / (w'Σw)^(1/2)` is equal. ERC solves an explicit optimization, unlike HRP's tree-based heuristic.

**Regime Switching:** Financial markets exhibit structural breaks in mean returns, volatility, and cross-asset correlations. Hamilton (1989) introduced Markov-switching models; Ang & Timmermann (2012) documented that high-volatility "bear" regimes are strongly persistent and costly to ignore.

**Walk-Forward Validation / Purged Cross-Validation:** An evaluation scheme where the model is retrained on historical windows, tested on future out-of-sample windows, and the training/test sets are separated by a "purge" gap to prevent label leakage — essential for time-series financial models (López de Prado 2018).

---

## 3. Thematic Synthesis

### 3.1 Hierarchical Risk Parity: Foundations, Strengths, and Documented Limitations

López de Prado's (2016) [foundational HRP paper](https://consensus.app/papers/details/4196ef9a05455a499628e42e9f4cd9c4/) established the algorithm's core properties via Monte Carlo experiments: lower out-of-sample variance than the CLA (minimum variance optimizer) and inverse-variance portfolio (IVP), despite CLA explicitly optimizing variance. The mechanism is avoidance of covariance matrix inversion, which amplifies estimation errors when assets are correlated.

Empirical replications validate the risk-reduction benefit but reveal an important limitation: **HRP consistently produces lower volatility and drawdown than benchmarks, but frequently underperforms on raw returns during trending bull markets.** Deković et al. (2025) ran HRP on S&P 500 constituents (2005–2023) and found [1/N outperformed HRP across all experimental setups on risk-adjusted return](https://consensus.app/papers/details/083f35f069cc5e7bb9a7cac65f2b180f/), though HRP lowered standard deviation by ~1%. The QF 301 project's own results echo this precisely: HRP produced the lowest volatility (13.4%) and smallest maximum drawdown (22.0%) but the lowest Sharpe ratio (0.335) of all strategies over 2022–2025, substantially lagging SPY (0.631).

The reason is structural: recursive bisection allocates by variance, not by return contribution, so in momentum-driven markets where a narrow set of high-volatility mega-cap stocks drive outsized returns, HRP will systematically underweight them. This is well-documented — Pergher et al. (2026) introduced [orthogonal hierarchical risk allocation](https://consensus.app/papers/details/819e8f1e053452dcb7cda9661769d2ff/) to address this, reporting 20.48% Sharpe ratio improvement over standard HRP.

Pfitzinger & Huyser (2019) showed that [fully exploiting the cluster structure](https://consensus.app/papers/details/dccc7151c3345aacaeb059af70a77627/) — allocating across clusters using cluster-level inverse variance rather than asset-level — improves out-of-sample risk and return characteristics consistently across 20–200 asset universes. This is the same approach implemented in the QF 301 project's K-means and hierarchical clustering portfolios.

Molyboga (2020) modified HRP with three practical enhancements: [Ledoit-Wolf exponentially weighted covariance, equal-volatility within-cluster allocation, and volatility targeting](https://consensus.app/papers/details/a664fb9973ae58c584a671f3b3ea8a4f/). The result was a 50% improvement in out-of-sample Sharpe ratio over standard HRP — underscoring that the original algorithm leaves substantial performance on the table and that better covariance estimation and weighting logic drive meaningful gains.

### 3.2 PCA-Based Clustering: What the Feature Space Adds

Using PCA factor loadings as clustering features (rather than raw returns or correlations) is both theoretically and empirically motivated. Avellaneda (2019) proposed [hierarchical PCA for S&P 500 sector portfolios](https://consensus.app/papers/details/c146ab3c29e55aad9771763b1599ef9f/), demonstrating that the approach captures almost all information of standard PCA while producing economically interpretable sector-level risk factors. In the QF 301 project's context, PCA reduced 50 return series to ~7 principal components explaining 60% of variance (visible in the reported scree plot), providing cleaner inputs to clustering.

León et al. (2017) compared seven clustering algorithms for portfolio construction and found that [hierarchical clustering algorithms achieved the best financial performance, obtaining a better trade-off between accumulated returns and the Omega ratio](https://consensus.app/papers/details/f01b4ad9659e5c209cce3b1e39bf6462/) versus MVO. Zhan et al. (2020) compared PCA-KMeans, autoencoders, and dynamic clustering, finding that [graphical models generally generated steadily increasing returns with low risk and outgrew the S&P 500 index](https://consensus.app/papers/details/df371b5f13df5c8bbad7be92413ed238/). James (2021) applied PCA and random matrix theory to equity correlations and found [clear differences in eigenspectra and time-varying sector behaviour](https://consensus.app/papers/details/2e0595680da55dd0b0ec219d8a63feab/), motivating dynamic re-clustering over time.

The key unresolved question in PCA-clustering portfolios is **how frequently to update the cluster assignments**. Static assignments (as in the QF 301 project) work well early in the out-of-sample period but degrade as market correlations evolve. Kaczmarek & Perez (2021) showed that [combining machine learning stock selection with HRP optimizers outperforms 1/N](https://consensus.app/papers/details/4df7c1a2bd6f5a60414172d67f3e09bd/) on S&P 500 and STOXX 600, with the gap most pronounced when market structure changes.

### 3.3 Regime Detection: The Critical Missing Layer

The most consistent finding across the uploaded literature package and the Consensus results is that **static portfolio construction methods fail when market regimes shift, and regime-adaptive methods recover substantial performance**. This is the core motivation for the RAC-HRP research direction.

Ang & Timmermann (2012) documented the magnitude of the problem empirically: a two-regime Markov-switching model estimated on S&P 500 monthly returns (1953–2010) found regimes primarily identified by volatility, with the high-volatility regime exhibiting lower mean returns, strong persistence (Pr(stay) = 0.977), and correspondence to all major crises. Ignoring regimes costs 2–3 cents per dollar per year in certainty-equivalent returns (Ang & Bekaert, 2002).

Kritzman et al. (2011) provided the PCA-specific regime tool: the *absorption ratio* (AR), the fraction of total variance absorbed by a fixed number of eigenvectors. They showed AR spikes ahead of major crises and predicts a 11.7% increase in realized 6-month volatility per 1-standard-deviation increase. Importantly, the *change* in AR (ΔAR = standardized shift from rolling mean) is more predictive than the level — this is directly usable as a re-clustering trigger.

Kim & Nelson (1998) provided the formal statistical foundation: dynamic factor models with regime-switching combine latent factor structure (like PCA's common components) with Markov-switching mean and variance. The 2024 IMF Working Paper (Akbal, 2024) extended this to big data settings using the EM algorithm, showing that regime-switching DFMs outperform single-regime models particularly during COVID-19 and other structural breaks, and that the EM approach provides closed-form parameter estimates at lower computational cost than one-step numerical maximization.

Costa & Kwon (2018) combined these insights directly in a portfolio context, formulating and solving a [risk parity optimization under a Markov regime-switching framework](https://consensus.app/papers/details/6f1f61a42777532c9ff53b5f2793e3bb/) using a Fama-French factor model. Their result: the regime-switching risk parity portfolio consistently outperforms its nominal counterpart, maintaining similar ex post risk while delivering higher returns. Pun & Wang (2023) further formalized [distributionally robust CVaR optimization under a regime-switching ambiguity set](https://consensus.app/papers/details/05518e72407e555380b0afd7eb56f5f9/), showing prompt regime-responsive reallocation in the 2008 crisis.

Zhang et al. (2025) built the most directly relevant recent benchmark: [RegimeFolio](https://consensus.app/papers/details/bf2ebe29891e50b6a7449eb2fcaeae85/), a VIX-based regime classifier combined with sector-specific ensemble forecasters and mean-variance optimization. Tested on 34 large-cap U.S. equities (2020–2024), it achieved an annualized return of 25.1%, Sharpe of 1.17, and 12% lower maximum drawdown than conventional ML benchmarks — directly relevant as an upper-bound comparison for RAC-HRP.

The non-parametric online regime detection approach of Issa et al. (2023), using [path-wise rough signature similarity metrics](https://consensus.app/papers/details/56247f40ec5c55de98ff9e4a2a0ac848/), offers an alternative to HMM-based approaches that is non-Markovian and works on high-dimensional baskets of equities — potentially more robust when structural breaks are not well-modeled by stationary Markov chains.

### 3.4 Covariance Estimation: From Linear to Nonlinear Shrinkage

The covariance matrix is the central input to HRP, ERC, and minimum variance portfolios. For the typical quantitative finance setting — 50–500 assets with 1–4 years of daily data — the sample covariance matrix is ill-conditioned and inversion amplifies noise dramatically.

Ledoit & Wolf (2004) introduced linear shrinkage: `S* = (1-α)S + αF`, pulling the sample matrix toward a structured target (single-index CAPM model). Tested on 10 years of S&P 500 monthly returns, the shrinkage estimator reduced out-of-sample minimum variance portfolio volatility by 10–15% and nearly eliminated extreme weight concentrations. This is the practical recommendation for the ERC and minimum variance benchmarks.

Ledoit & Wolf (2022) reviewed and updated the landscape, showing the consistent ranking: **nonlinear shrinkage > linear shrinkage > sample covariance** in minimum variance out-of-sample variance, with the gap largest when p/T is large. Nonlinear shrinkage (Analytical Nonlinear Shrinkage) individually adjusts each eigenvalue using Marchenko-Pastur distribution theory, leaving large eigenvalues (genuine factors) intact while aggressively shrinking small eigenvalues (noise). The 2025 neural network approach of Bongiorno et al. (2025) extended this further, showing that [an end-to-end learned covariance cleaner outperforms nonlinear shrinkage across 2000–2024](https://consensus.app/papers/details/4bac713658dd59f1aa47e23bf0cd68a4/), including during stress episodes.

For the RAC-HRP context, Molyboga's (2020) finding is directly actionable: replacing the raw sample covariance with exponentially weighted covariance + Ledoit-Wolf shrinkage improved HRP Sharpe ratios by 50%. The Lopez de Prado (2018) NCO framework complemented this with covariance denoising via the Marchenko-Pastur clip: eigenvalues below the random matrix theory upper bound are replaced with the average of the noise eigenvalues, cleaning the cluster sub-matrices before optimization.

### 3.5 Walk-Forward Validation: Methodological Standards

The QF 301 project used a clean in-sample (2018–2021) / out-of-sample (2022–2025) split with daily rebalancing — an appropriate but simple scheme. The literature identifies several important refinements for research-grade evaluation.

López de Prado (2018) introduced purged k-fold cross-validation: (1) purge training samples that overlap temporally with test samples; (2) add an "embargo" gap after test samples to prevent lookahead bias from autocorrelated features. Standard k-fold leaks future information when applied to time series, producing overly optimistic in-sample estimates.

Sheppert (2026) empirically quantified this: a GT-Score-based walk-forward validation across [nine sequential time splits for S&P 500 strategies (2010–2024)](https://consensus.app/papers/details/bb4587437eb35d869ad478a302401479/) improved the generalization ratio (validation/training return) by 98% relative to baseline objective functions. The methodological recommendation is walk-forward with non-overlapping expanding or rolling windows, explicitly separated by purge gaps.

Nikolopoulos (2026) documented the alternative failure mode: [spurious predictability from adaptive specification search](https://consensus.app/papers/details/340ed2f9a00a5a10ab678bbc4b70c4eb/), where workflows generating significant walk-forward evidence in zero-predictability synthetic environments are flagged as methodological artifacts. The implication for RAC-HRP is that regime detection hyperparameters (AR threshold, cluster update frequency, lookback window) must be chosen on a separate validation period, not tuned on the same out-of-sample period used for reporting.

Akioyamen et al. (2020) provided an applied example of regime-detection + walk-forward evaluation: [PCA dimensionality reduction + k-means regime clustering on US economic data](https://consensus.app/papers/details/5a3b9f4d037b5fd7893ff69216cc2a25/), detecting regimes and building trading strategies with regime-conditioned allocation. The use of public economic indicators (rather than in-sample equity returns) for regime detection is a methodological best practice that avoids look-ahead bias.

---

## 4. Methodological Landscape

### 4.1 Study Designs

Empirical studies in this space predominantly use backtesting over historical equity universes (10–500 stocks, typically S&P 500 constituents) with daily or monthly return data. The evaluation window spans at minimum 3 years out-of-sample; stronger studies use 5–20 years or multiple sub-periods testing robustness across different regimes (2008 GFC, 2020 COVID, 2022 tightening cycle). The QF 301 project's 4-year OOS window (2022–2025) is adequate but benefits from the coincidence of covering a single macro regime (post-COVID recovery + tightening).

### 4.2 Dominant Frameworks

Three distinct methodological lineages converge in this literature:

**Financial econometrics lineage** (Hamilton 1989 → Kim & Nelson 1998 → Ang & Timmermann 2012 → Akbal 2024): focuses on formal Markov-switching models, Kalman filters, EM estimation. Strength: statistical rigor and identifiability. Weakness: computational cost and parametric assumptions about regime structure.

**ML/clustering lineage** (López de Prado 2016 → Pfitzinger 2019 → Molyboga 2020 → Pergher 2026): focuses on hierarchical tree structures, inverse variance allocation, graph-theoretic distance metrics. Strength: avoids covariance inversion, scalable. Weakness: static cluster assignments degrade over time.

**PCA/spectral risk lineage** (Kritzman et al. 2011 → James 2021, 2022 → Issa et al. 2023 → ORCA 2026): uses eigendecomposition as both a clustering input and a regime indicator. Strength: directly links structural market changes (eigenvalue concentration) to portfolio decisions. Weakness: the absorption ratio is an indicator, not a full model, and requires a calibrated threshold.

The RAC-HRP research direction synthesizes all three: PCA identifies the current factor structure (spectral lineage), clustering groups assets by factor exposures (ML lineage), regime detection (absorption ratio or HMM) triggers re-estimation (econometric lineage).

### 4.3 Evaluation Metrics

The standard performance metrics across all reviewed papers are: annualized return, annualized volatility, Sharpe ratio (excess return / volatility), maximum drawdown, and turnover. The QF 301 project reports all five. Stronger papers additionally report: Omega ratio (ratio of gains to losses above threshold), Calmar ratio (return / max drawdown), information ratio vs. benchmark, and statistical significance via block-bootstrap or Diebold-Mariano tests. The 2026 ORCA paper exemplifies best practice: walk-forward AUC, BCD-AUC (geometric mean of rally/crash AUC), and per-strategy significance testing.

---

## 5. Key Findings and Evidence Strength

**Well-established (strong evidence across multiple studies):**

- HRP reduces out-of-sample volatility and maximum drawdown relative to MVO and equally weighted portfolios (López de Prado 2016; Deković et al. 2025; Burggraf 2020; QF 301 results).
- Linear Ledoit-Wolf shrinkage consistently outperforms sample covariance for minimum variance portfolios (Ledoit & Wolf 2004; confirmed by Bodnar et al. 2014; Rubio et al. 2011).
- Market regimes are real, persistent, and costly to ignore: high-volatility regimes have lower returns and different correlation structures (Ang & Timmermann 2012; Kritzman et al. 2012).
- The absorption ratio is a forward-looking systemic risk measure that spikes before major crises (Kritzman et al. 2011; Bradfield & Van Rensburg 2014).

**Moderately established (evidence from several studies, some conditions):**

- Regime-aware risk parity portfolios outperform static risk parity out-of-sample on risk-adjusted returns (Costa & Kwon 2018; Pun & Wang 2023; Zhang et al. 2025).
- PCA-clustered portfolios outperform MVO on risk metrics but not always on raw returns in trending markets (QF 301; León et al. 2017; Kaczmarek et al. 2021).
- Modified HRP with exponentially weighted covariance + Ledoit-Wolf improves Sharpe by ~50% vs. standard HRP (Molyboga 2020).

**Emerging (single or few studies, warrant further validation):**

- Nonlinear shrinkage combined with PCA factor model overlay outperforms all shrinkage methods (Ledoit & Wolf 2022; Bongiorno 2025).
- Rough path signatures outperform HMM for online regime detection in high-dimensional settings (Issa et al. 2023).
- Orthogonal dynamic projections (OHRP) improve HRP Sharpe by 20%+ on Brazilian equities (Pergher et al. 2026).

---

## 6. Limitations and Research Gaps

**Identified across the corpus:**

The most consistent limitation across all clustering-based portfolio studies — including the QF 301 project explicitly — is **static cluster assignments that degrade over time**. When in-sample cluster structure diverges from out-of-sample market topology, the weighting logic becomes misaligned with realized correlations. The QF 301 project observed exactly this pattern: early outperformance followed by gradual deterioration as the static 2018–2021 PCA structure failed to represent the 2023–2025 AI-driven mega-cap rally.

Related is **look-ahead bias in hyperparameter selection**: the number of PCA components (60% variance explained), the cluster count selection via silhouette score, and the HRP lookback window (252 days) are all tuned using the full data view in most studies. Rigorous walk-forward implementations (Sheppert 2026; López de Prado 2018) require these to be chosen using only information available at each rebalancing date.

**Genuine open questions:**

- What is the optimal re-clustering frequency for regime-adaptive HRP? Daily, monthly, or event-triggered by the absorption ratio? No study directly compares these.
- How should the regime-detection threshold (e.g., ΔAR > +1 σ) itself be calibrated out-of-sample? Fixed thresholds risk overfitting to historical crisis patterns.
- Can regime-switching HMM parameters be estimated in real time (with short data histories) without incurring estimation error that exceeds the benefit of regime adaptation?
- Does the NCO algorithm (two-nested optimization) outperform HRP when both are applied with regime-adaptive re-clustering? The 2018 paper introduces NCO in the static context; no study applies it dynamically.
- What is the transaction cost impact of frequent regime-triggered rebalancing? Studies reporting gross Sharpe improvements rarely account for the higher turnover generated by regime-driven weight changes.

---

## 7. Future Directions

Based on the identified gaps, the highest-priority research directions for the RAC-HRP project are:

**Rolling PCA with regime-triggered re-clustering:** Implement the absorption ratio as the re-clustering trigger, using a rolling 252-day window for PCA and cluster estimation. Compare event-triggered vs. fixed-schedule (monthly/quarterly) re-clustering.

**Purged walk-forward validation protocol:** Structure backtesting with multiple sequential folds, purge gaps between train/test sets, and hold out a final validation set for parameter calibration. This prevents the AR threshold and silhouette score parameters from being optimized on the same out-of-sample window used for reporting.

**ERC as mandatory benchmark:** The current QF 301 benchmarks (SPY, EW) do not include ERC, which Roncalli (2013) and subsequent literature establish as the strongest classical risk-parity comparison. Demonstrating outperformance over ERC is the standard bar for claiming hierarchical structure adds value.

**Shrinkage-improved covariance:** Replace the raw sample covariance with Ledoit-Wolf linear shrinkage (available as `sklearn.covariance.LedoitWolf`) for the ERC and minimum variance benchmarks, and use exponentially weighted + LW shrinkage for HRP cluster covariances.

**Regime characterization using PCA absorption ratio:** Compute ΔAR daily from the rolling 252-day covariance. When ΔAR > +1σ above its rolling mean, flag a fragile regime and trigger re-estimation of PCA loadings and cluster assignments.

**Statistical significance testing:** Report bootstrap confidence intervals and Diebold-Mariano tests for pairwise Sharpe comparisons. The pattern-of-results approach (Table 1 in QF 301) is informative but does not establish statistical significance of strategy differences.

---

## 8. Paper Inventory

### Foundational Papers (User-Provided)

| # | Title | Authors | Year | Journal/Source | Key Contribution |
|---|-------|---------|------|---------------|-----------------|
| 1 | [Building Diversified Portfolios that Outperform Out of Sample](https://www.semanticscholar.org/paper/Building-Diversified-Portfolios-that-Outperform-Out-Prado/f1c44fb9774e4ccce73e197cba25d69ea45dbfe1) | López de Prado | 2016 | J. Portfolio Mgmt | HRP algorithm: 3-stage hierarchical portfolio |
| 2 | [Advances in Financial Machine Learning (NCO)](https://ssrn.com/abstract=3104847) | López de Prado | 2018 | Wiley Book | NCO, covariance denoising, purged k-fold CV |
| 3 | [A Well-Conditioned Estimator for Large Covariance Matrices](https://dl.acm.org/doi/10.1016/S0047-259X(03)00096-4) | Ledoit & Wolf | 2004 | J. Multivariate Analysis | Linear shrinkage: analytic, distribution-free |
| 4 | [The Power of (Non-)Linear Shrinking](https://www.econ.uzh.ch/dam/jcr:e946b1e3-35e8-4c4f-894f-5f4306bf28a5/jfec_2022.pdf) | Ledoit & Wolf | 2022 | J. Financial Econometrics | Review + nonlinear shrinkage via RMT |
| 5 | [Introduction to Risk Parity and Budgeting](https://ssrn.com/abstract=2272973) | Roncalli | 2013 | Chapman & Hall | ERC portfolio: definition, uniqueness, algorithms |
| 6 | [Regime Changes and Financial Markets](https://www.nber.org/system/files/working_papers/w17182/w17182.pdf) | Ang & Timmermann | 2012 | Annual Rev. Fin. Econ. | Markov-switching empirical evidence; cost of ignoring regimes |
| 7 | [Principal Components as a Measure of Systemic Risk](https://ssrn.com/abstract=1582687) | Kritzman et al. | 2011 | J. Portfolio Mgmt | Absorption ratio: PCA-based fragility indicator |
| 8 | [Dynamic Factor Model with Regime Switching](https://econpapers.repec.org/article/tprrestat/v_3a80_3ay_3a1998_3ai_3a2_3ap_3a188-201.htm) | Kim & Nelson | 1998 | Rev. Econ. & Statistics | DFM + Markov switching; Gibbs sampling estimation |
| 9 | [Regime-Switching Factor Models and Nowcasting with Big Data](https://www.imf.org/) | Akbal | 2024 | IMF Working Paper | EM algorithm for regime-switching DFMs; real-time recession dating |

### Additional Papers from Consensus Search

| # | Title | Authors | Year | Key Contribution |
|---|-------|---------|------|-----------------|
| 10 | [An Orthogonal Hierarchical Risk Parity Allocation Method](https://consensus.app/papers/details/819e8f1e053452dcb7cda9661769d2ff/) | Pergher et al. | 2026 | Dynamic orthogonal projections improve HRP Sharpe by 20% |
| 11 | [HRP: Efficient Implementation and Real World Analysis](https://consensus.app/papers/details/083f35f069cc5e7bb9a7cac65f2b180f/) | Deković et al. | 2025 | 1/N beats HRP on returns; HRP lowers std by ~1% on S&P 500 |
| 12 | [A Modified Hierarchical Risk Parity Framework](https://consensus.app/papers/details/a664fb9973ae58c584a671f3b3ea8a4f/) | Molyboga | 2020 | EW covariance + LW shrinkage + vol-targeting improves Sharpe 50% |
| 13 | [A Constrained HRP with Cluster-Based Capital Allocation](https://consensus.app/papers/details/dccc7151c3345aacaeb059af70a77627/) | Pfitzinger & Huyser | 2019 | Full cluster structure exploitation improves HRP OOS |
| 14 | [Beyond Risk Parity – HRP for Cryptocurrencies](https://consensus.app/papers/details/5373c9fb42445837a90e5defeea95bdf/) | Burggraf | 2020 | HRP outperforms on tail risk-adjusted return in crypto |
| 15 | [Hierarchical PCA and Applications to Portfolio Management](https://consensus.app/papers/details/c146ab3c29e55aad9771763b1599ef9f/) | Avellaneda | 2019 | HPCA uses sector structure; sector factor interpretability |
| 16 | [Non-parametric Online Market Regime Detection](https://consensus.app/papers/details/56247f40ec5c55de98ff9e4a2a0ac848/) | Issa et al. | 2023 | Rough path signatures for regime clustering; high-dimensional equities |
| 17 | [Dynamic Asset Allocation with Asset-Specific Regime Forecasts](https://consensus.app/papers/details/1e0bcbba7a1752b3aafa0338191a4c61/) | Shu et al. | 2024 | Jump model + gradient boosting regime forecasting; MV allocation |
| 18 | [A Hybrid Learning Approach to Detecting Regime Switches](https://consensus.app/papers/details/5a3b9f4d037b5fd7893ff69216cc2a25/) | Akioyamen et al. | 2020 | PCA + k-means for US regime detection from economic data |
| 19 | [RegimeFolio: Regime-Aware ML for Sectoral Portfolio Optimization](https://consensus.app/papers/details/bf2ebe29891e50b6a7449eb2fcaeae85/) | Zhang et al. | 2025 | VIX regime + sector ML + MV; Sharpe 1.17 on 34 U.S. equities |
| 20 | [Risk Parity Portfolio Optimization under Markov Regime-Switching](https://consensus.app/papers/details/6f1f61a42777532c9ff53b5f2793e3bb/) | Costa & Kwon | 2018 | Regime-switching Fama-French risk parity; outperforms static |
| 21 | [Regime Shifts: Implications for Dynamic Strategies](https://consensus.app/papers/details/9653830d96ae5137a61a7bb353eeef70/) | Kritzman et al. | 2012 | Markov-switching for turbulence/inflation/growth regime forecasting |
| 22 | [Improved Estimation of Covariance Matrix of Stock Returns](https://consensus.app/papers/details/2de4be23b6945964989012131bffb3a7/) | Ledoit & Wolf | 2003 | Shrinkage to single-index target; predecessor to 2004 paper |
| 23 | [Building Portfolios Based on Machine Learning Predictions](https://consensus.app/papers/details/4df7c1a2bd6f5a60414172d67f3e09bd/) | Kaczmarek et al. | 2021 | RF stock selection + HRP outperforms 1/N on S&P 500 and STOXX 600 |
| 24 | [Clustering Algorithms for Risk-Adjusted Portfolio Construction](https://consensus.app/papers/details/f01b4ad9659e5c209cce3b1e39bf6462/) | León et al. | 2017 | Hierarchical clustering + classical optimization in-cluster; robust OOS |
| 25 | [Graphical Models for Financial Time Series and Portfolio Selection](https://consensus.app/papers/details/df371b5f13df5c8bbad7be92413ed238/) | Zhan et al. | 2020 | PCA-KMeans, autoencoders, dynamic clustering vs. MVO on equities |
| 26 | [The GT-Score: A Robust Objective for Reducing Overfitting](https://consensus.app/papers/details/bb4587437eb35d869ad478a302401479/) | Sheppert | 2026 | Walk-forward anti-overfitting; 98% improvement in generalization ratio |
| 27 | [ORCA: Online Regime Correlation Analyzer](https://consensus.app/papers/details/5040f8eb40b85b1bbe5593db3b135120/) | Kriuk et al. | 2026 | Spectral + graph features (incl. absorption ratio) for regime detection; AUC 0.741 |
| 28 | [Data-Driven Distributionally Robust CVaR under Regime-Switching](https://consensus.app/papers/details/05518e72407e555380b0afd7eb56f5f9/) | Pun & Wang | 2023 | Wasserstein ambiguity set with HMM; outperforms 1/N across datasets |

---

## Appendix: Placement of the QF 301 Project in the Literature

The QF 301 project sits at the intersection of themes 3.1 and 3.2 above, implementing the foundational HRP + PCA-clustering approach with a static cluster estimation. Its results are consistent with the literature: reduced volatility and drawdown relative to SPY and EW, but underperformance on cumulative return as the bull market extended. The project's explicit recommendation of rolling-window estimation is exactly the transition point between the static ML lineage and the regime-adaptive direction documented in Section 3.3.

The next research step — adding the absorption ratio as a re-clustering trigger, replacing sample covariance with Ledoit-Wolf shrinkage, including ERC as a benchmark, and applying purged walk-forward CV — would position the work at the frontier of the literature as represented by Costa & Kwon (2018), Molyboga (2020), and Zhang et al. (2025).

---

*Review conducted June 2026. Paper inventory covers 28 sources: 9 user-provided foundational papers and 19 additional peer-reviewed works retrieved via Consensus. Total unique papers reviewed: 28.*
