# Results

Curated, publishable artifacts only. Working output lives in `outputs/` (gitignored).

## What belongs here

Aggregate statistics and integrity artifacts — safe to publish because they contain no
licensed CRSP data, only derived summary numbers:

| File | What it is |
|---|---|
| `freeze_manifest.json` | seed, replication counts, decision rules, SHA-256 of gate code |
| `output_manifest.txt` | SHA-256 of the result files below |
| `primary_gate.csv` | Null Gate v2 primary (gating) verdicts |
| `diagnostic_panel.csv` | cross-allocator diagnostics (non-gating) |
| `replication_sharpe_matrix.csv` | per-replication Sharpe by strategy |
| `null_gate_v1.csv` | Null Gate v1, preserved as an immutable record |
| `phase1_baselines.csv` | static baseline performance, development region |
| `phase1_estimator_sensitivity.csv` | estimator sensitivity (diagnostic; selects nothing) |
| `phase1_accounting.csv` | accounting reconciliation |
| `phase2e_horizon_result.json` | 2E-HORIZON, post-gate diagnostic (**non-gating**; confers no admissibility) |

## What must NOT go here

- Any CRSP-derived panel, price, or return series at security level
- Anything containing permnos joined to prices
- WRDS credentials

The rule of thumb: **aggregate statistics across strategies are publishable; anything
that could reconstruct the licensed panel is not.**

## Populating

Copy from your archived Phase 0.5 run:

    cp archive/phase05_final/null_gate_v2/*.csv        results/
    cp archive/phase05_final/null_gate_v2/freeze_manifest.json results/
    cp archive/phase05_final/v1_preserved/null_gate_v1.csv     results/
    cp outputs/phase1/*.csv                            results/

Then verify nothing licensed slipped in:

    grep -l "permno" results/*.csv || echo "clean -- no security-level identifiers"

## Post-gate diagnostics

`phase2e_horizon_result.json` is a **post-gate, non-gating** diagnostic specified in
`RAC_HRP_Phase2E_PreSpec_rev5.md`, hashed and committed before the implementing code was
written. It recomputes the cluster-informativeness statistic at a horizon matched to the
trigger (five rebalances rather than one) and cannot render any gamma admissible. The
Phase 2A verdict — NO ADMISSIBLE GAMMA — is unchanged. It must be read alongside 2E-POWER,
which bounds the design's sensitivity.
