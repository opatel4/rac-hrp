# RAC-HRP — Phase 2F: W-Calibrated Positive Control

**Status:** rev.1 — FREEZE CANDIDATE. To be hashed and committed before any implementing code is
written.
**Author:** Om Patel
**Region:** Development region only (2003-01-08 to 2022-12-30). Test region remains structurally
locked.

**Single author.** No independent party has reviewed or authorised this specification. Its
prospective character rests on the freeze record in §6: the memo's hash, the commit recording it,
and the absence of implementing code at that commit.

---

## 0. Standing constraints

**0.1 Non-gating.** Nothing here can render any γ admissible, reopen the Phase 2A calibration gate,
or alter any frozen value. The Phase 2A verdict — NO ADMISSIBLE γ — stands regardless of outcome.

**0.2 The holdout remains closed.** The test region is not touched. The durable audit log must
record zero analysis touches on completion.

**0.3 The frozen mechanism-null result is not superseded.** `outputs/phase2_mechanism/` and the
Phase 2D result memo stand unaltered. This run adds an environment; it does not re-execute or
replace the original three.

**0.4 Reported regardless of outcome.** There is no result at which this is withheld or reframed.

---

## 1. Why this exists

The frozen mechanism null (Phase 2D) used three environments: A, uncorrelated and vol-matched; S,
static covariance; and D, a two-state Markov regime in which both volatility and factor loadings
scale, intended as the **positive control** — an environment in which covariance concentration
genuinely shifts and which the pipeline should therefore be able to detect.

Real-data excess burstiness exceeded D's 97.5th percentile at every γ. D did not bracket the
observed values, so the experiment's sensitivity was never demonstrated. The Phase 2D memo offered
the explanation and it is almost certainly right: D's states persist for approximately 100 and 34
daily observations, against a covariance window of W = 504. A single window therefore spans roughly
four complete regime cycles and averages the designed structure away. D is a *high-frequency*
positive control applied to a low-frequency estimator.

The transition mechanism itself was checked and is correct: simulation of the frozen state machine
over 200,000 steps returns P(0→1) = 0.0100 and P(1→0) = 0.0293 against intended 0.01 and 0.03, with
mean runs of 100 and 34 days. **There is no defect in the Markov sampling.** The mismatch is
between the regime durations and W, and nothing else.

Drawing the conclusion that "the tested regime-free architectural explanations are not supported"
from an experiment whose positive control failed is unsound. This run repairs the control.

---

## 2. The environment

`D_slow_regime_switch` is the frozen `regime_switch_vol` process with one change: the state
persistence probabilities.

| Parameter | Frozen D | This run | Mean run length |
|---|---|---|---|
| `p_stay[0]` (low state) | 0.99 | 0.999 | 100 d → 1000 d |
| `p_stay[1]` (high state) | 0.97 | 0.9985 | 34 d → 667 d |
| `n_factors` | 3 | 3 | unchanged |
| `vol_ratio` | 2.5 | 2.5 | unchanged |
| `corr_shift` | 1.4 | 1.4 | unchanged |

Both mean durations now exceed W = 504, so a covariance window can lie within a single regime rather
than straddling several. Nothing else about the process changes: same factor structure, same
volatility and loading scaling, same zero conditional mean in both states, same NaN mask, membership
path, market caps, rebalance dates, W, k, smoothing and σ̂.

**Implementation constraint.** `rac_hrp/nulls/environments.py` is hashed in
`outputs/phase2_mechanism/mechanism_null.json` and **must not be modified**. The slow variant is
implemented in a separate module and dispatched directly, exactly as `environments_static.py` does
for environment S, and for the same reason: registering it in `ENVIRONMENTS` would shift the
dictionary ordering that `list(ENVIRONMENTS.keys()).index(ENV)` uses for seed derivation and would
invalidate frozen seeds.

---

## 3. Procedure

Identical to the frozen mechanism null in every respect except the environment. The statistic is the
density-adjusted excess burstiness

```
B_γ = M_γ − median(M^placement | n_γ)
```

with the placement median a deterministic cached lookup keyed on event count, shared with the real
data. Trigger construction, eligibility, γ grid and ordering are the frozen ones.

| Parameter | Value |
|---|---|
| Replications | 500 |
| γ candidates | {0.5, 1.0, 1.5, 2.0}, frozen grid and ordering |
| Base seed | `__________________` (fixed before hashing) |
| Seed derivation | `seed(rep) = base + rep` |
| Reported interval | 2.5th–97.5th percentile of B_γ across replications |

500 replications matches the frozen run. The comparison of interest is against a 2.5–97.5 percentile
interval, which places roughly twelve observations beyond each cutoff at this count; reducing the
count would widen the interval for reasons of sample size rather than of the environment's
behaviour, and would make the result non-comparable to the frozen A and S arms.

---

## 4. Decision rule, fixed in advance

Let `real_γ` denote the observed excess burstiness, unchanged from the frozen run.

- **Outcome C — the control works and the burstiness claim survives.** `real_γ` lies inside the
  2.5–97.5 interval of `D_slow` at a majority of γ. The pipeline can resolve genuine
  low-frequency regime structure, and real-data burstiness is consistent with such structure while
  being inconsistent with the regime-free environments A and S. The Phase 2D conclusion is
  supported, now with a working positive control.
- **Outcome X — the control works and the burstiness claim does not survive.** `real_γ` lies
  **above** the 97.5th percentile of `D_slow` at a majority of γ, as it did for frozen D. Real
  burstiness then exceeds what genuine slow regime switching produces, and the Phase 2D conclusion
  that the trigger "is detecting something" attributable to regime structure is **withdrawn**. What
  the trigger detects would remain unexplained by any environment tested.
- **Outcome N — the control still does not resolve.** `D_slow` produces excess burstiness
  indistinguishable from A and S, meaning the pipeline cannot detect regime structure at any
  frequency. The Phase 2D interpretation is then unavailable in either direction and the burstiness
  result is reported as uninterpretable pending a redesigned control.

Outcome X retires a claim the current manuscript makes in §6.1 and §8. It is written into this memo
before execution because that is the point of writing it before execution.

---

## 5. Reporting

Reported regardless of outcome, in the results section alongside the frozen mechanism null:

- B_γ percentile intervals for `D_slow` at all four γ, beside the frozen A, S and D intervals.
- The realised fraction of time in the high state and the realised mean run lengths, verifying the
  durations came out as specified.
- Explicit statement that frozen D remains a high-frequency control whose result is unaltered, and
  that `D_slow` is an addition rather than a replacement.
- The outcome label from §4 and the consequence it carries for §6.1 and §8.

---

## 6. Freeze record

| Field | Value |
|---|---|
| SHA-256 of this file | recorded in `PHASE2F_FREEZE.txt` at the recording commit |
| Commit recording it | `__________________` |
| Implementing code present at that commit | none |

**Verification a replicator can perform.** Hash this file and compare. Check that the recording
commit contains no Phase 2F implementation, and that every subsequent commit touching Phase 2F code
postdates it.

**Amendments.** Any change requires a new revision, hashed and committed separately, with the reason
stated and the superseded revision preserved.
