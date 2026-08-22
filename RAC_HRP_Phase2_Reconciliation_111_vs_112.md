# Audit Reconciliation: frozen "112" vs gate "111" at gamma = 1.0

**Question raised (advisor review):** the frozen Phase 2 pre-registration records
112/233 = 48.1% at gamma = 1.0; the gate produced 111/233 = 47.6%. A frozen
pipeline must reproduce its pre-freeze diagnostic exactly, or document why not.

**Conclusion: this is a definitional mismatch between two different statistics,
not a one-event drift in the trigger.** There is nothing to trace. Details below.

## What the two numbers actually are

- **Gate "111"** = `n_events` at gamma = 1.0 in the frozen calibration
  (`calibration.py:212`): the count of eligible rebalances where
  `|dAR| > 1.0 * sigma`. Denominator: **233 eligible** rebalances.

- **Frozen "112"** = the count of `refit = True` rows in the Phase 0.5 artefact
  `archive/phase05_final/v1_preserved/rac_diagnostics.csv`. That file's header is
  `date, n_assets, ar, mp_k, k_used, sigma2, refit, n_clusters`; `refit` tallies
  128 False / 112 True over **240** rebalances (no eligibility screen applied).

They differ in numerator (refit vs trigger), denominator (240 vs 233), and the
code that produced them. The near-equality (112 vs 111) is coincidental.

## Evidence that refit != gamma=1.0 trigger (four independent confirmations)

1. **`refit` does not exist in the current codebase.** `grep -rn "refit"
   rac_hrp/ --include="*.py"` returns nothing. The frozen gate never computes it;
   its only trigger path is `|dAR| > gamma*sigma`.
2. **Different denominator.** `refit` is 112/240 (all rebalances). The gate's 111
   is out of 233 eligible. 112 was never a fraction of 233; the "112/233" pairing
   in the memo/pre-reg is not how the number was generated.
3. **AR itself is computed differently upstream.** The gate freezes `k` at the
   first eligible rebalance and holds it (`calibration.py:108`,
   `mp_k_mode = fixed_per_run`). The archived diagnostics show `mp_k` varying
   (15, 16, ...) with `k_used` clamped to 15 -- a different k rule. Different k =>
   different absorption ratio at every date => different dAR => different trigger
   set. The gate's AR series is therefore NOT reconstructable from the archived
   `ar` column.
4. **No archived Phase 0.5 source.** `find archive/phase05_final -name "*.py"`
   returns nothing. The generating code for `refit` is not in the repository;
   only its per-rebalance output survives.

## What CANNOT be done, and why

The advisor's proposed remedy -- diff the two gamma=1.0 trigger sets and trace
the differing date through AR -> AR^s -> dAR -> sigma -- **cannot be executed**:

- there is no second trigger set on disk (the archived file stores `refit`, a
  re-clustering flag, not a trigger set);
- the gate's AR series cannot be reconstructed from the archived data because k
  was frozen under a different rule (point 3);
- the Phase 0.5 source that computed `refit` is absent (point 4).

Producing a date-level diff against the mismatched `ar` series would manufacture
a false reconciliation. It is not done.

## OPEN ITEM (pending freeze-document review)

If `RAC-HRP_Phase2_PreRegistration_rev5_FREEZE.docx` presents 112 / 48.1% as the
gamma = 1.0 **firing rate / trigger count**, that is a mislabelled figure in the
countersigned pre-registration: the value is a Phase 0.5 `refit` count, not a
trigger count. The number is real; it is attached to the wrong quantity. This is
a documentation defect in a frozen artefact, not a code bug. It must be confirmed
by reading the docx (not yet available in reproducible form) and, if present,
recorded as an erratum to the frozen document. It does NOT change any result.

## Bearing on the Phase 2 stop

None. The gate's own gamma = 1.0 firing rate is 111/233 = 47.6%, still above the
0.40 ceiling, so gamma = 1.0 fails `informativeness` regardless. And every
candidate fails `cluster_informativeness` independently (Holm p in
[0.221, 0.556]). The stop stands.
