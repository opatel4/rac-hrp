# RAC-HRP — Reproducibility Manifest

Generated 2026-08-28T22:12:52.371256+00:00 at commit `3364955bd11e87f32dd392838d22c2981494fcdf`
(branch `main`, working tree clean: False).

Pins every reported number to a verifiable state. Generated **before** engineering
migration (pytest, refactors) so later churn cannot blur the provenance of the
scientific outputs.

## Environment
Python 3.12.2 on macOS-15.0.1-arm64-arm-64bit;
numpy 1.26.4, pandas 2.2.2,
scipy 1.14.1.

Single-thread BLAS is the project standard: ~13x faster on this workload (100x100 matrices) and verified result-neutral (the --quick Phase 2 gate reproduces bit-for-bit under both settings). Set at process launch; setting it inside a script after numpy import may be too late.

## Data
CRSP via WRDS (user opatel4); CRSP-native large-cap universe; vintage ends 2024-12-31
Path: `/Users/ompatel/rac_hrp_data/raw`

| file | sha256 (first 16) | bytes |
|---|---|---:|
| `delist.parquet` | `6c0f4b19842b238c` | 390921 |
| `dsf.parquet` | `cf93a57a456b6c97` | 85203140 |
| `membership.parquet` | `4e7bfa35dbf42f60` | 58612 |
| `names.parquet` | `79f02aa04c4b6414` | 1540208 |
| `rf.parquet` | `ec3e256ec2c8fae2` | 71745 |

## Regions
- Development: 2003-01-08 .. 2022-12-30 (5,031 days)
- Test: TEST_START 2023-01-03 .. 2024-12-31
- **Test-region analysis touches: 0**

The single pre-registered test-region touch has NOT been used. No adaptive specification passed the development-stage structural gate, so performance evaluation was conditionally inaccessible by design.

### Code

| file | sha256 (first 16) | bytes |
|---|---|---:|
| `rac_hrp/config.py` | `f7871458760bf83e` | 7177 |
| `rac_hrp/core/covariance.py` | `2bcb5d0c03eba36d` | 6313 |
| `rac_hrp/core/covariance_ew.py` | `b79f13747b501bb3` | 9030 |
| `rac_hrp/core/allocators.py` | `ab5bd50fa2e57040` | 8602 |
| `rac_hrp/core/clustering.py` | `b34e83b71cacf8b3` | 7414 |
| `rac_hrp/core/pca_mp.py` | `781178bd5d2fa595` | 5919 |
| `rac_hrp/backtest/engine.py` | `14774900f0dbd44a` | 19300 |
| `rac_hrp/backtest/folds.py` | `1f4a6e7424072877` | 7185 |
| `rac_hrp/backtest/region_lock.py` | `4f916da094fe596e` | 10394 |
| `rac_hrp/backtest/metrics.py` | `801011199bfc2535` | 3083 |
| `rac_hrp/data/panel.py` | `388acd1c038bd197` | 9240 |
| `rac_hrp/data/universe.py` | `15fa7d17a19b6f32` | 5252 |
| `rac_hrp/nulls/environments.py` | `29e3607e11ed672b` | 9067 |
| `rac_hrp/nulls/environments_static.py` | `25997e6bf1f5f8cf` | 6239 |
| `rac_hrp/phase2/config.py` | `44e6ef894050db1b` | 3963 |
| `rac_hrp/phase2/stats.py` | `88f9fba50a3dc45b` | 9516 |
| `rac_hrp/phase2/calibration.py` | `4b9e62951ea9f547` | 17261 |
| `scripts/run_phase05.py` | `c329c09289353198` | 10250 |
| `scripts/run_phase1.py` | `9086912bfc8e50fe` | 8916 |
| `scripts/run_phase2.py` | `bfcd96433a4e209d` | 7926 |
| `scripts/run_mechanism_null.py` | `9098fd5bc6f718c3` | 13255 |
| `scripts/run_mechanism_null_parallel.py` | `85767658d4a6b1fb` | 11220 |
| `scripts/diagnose_modal_gap_null.py` | `7e69ba51cf1b5f3b` | 7240 |
| `scripts/diag_bootstrap_calibration_B.py` | `0c43965a5d43cc52` | 5500 |
| `tests/test_phase05.py` | `c149364040a9d921` | 12157 |
| `tests/test_phase2_stats.py` | `b26d7e0b6b2ecda9` | 6346 |
| `tests/test_covariance_ew.py` | `6815445052f2a27d` | 7719 |
| `tests/test_region_lock.py` | `a925ea73080ae6ee` | 4548 |
| `tests/test_invariants.py` | `f998f6fb393cf204` | 5917 |
| `tests/conftest.py` | `9945a7cd928df9bb` | 2454 |
| `rac_hrp/phase2/horizon.py` | `8334a0f923e392a9` | 13732 |
| `rac_hrp/phase2/power.py` | `dcd2eef443714510` | 14321 |
| `scripts/run_phase2e_horizon.py` | `5a991fba0c5acd3f` | 7616 |
| `scripts/run_phase2e_power.py` | `e71191be23136ebc` | 9408 |
| `scripts/run_phase2e_power_parallel.py` | `de0610a8be762db5` | 11614 |
| `scripts/run_phase2f_control.py` | `031be5d2b38c6438` | 14762 |
| `scripts/run_phase2g.py` | `321461a3e81ba50e` | 17493 |
| `scripts/explore_power_construction.py` | `65bcb843088a48fd` | 9306 |

### Result artefacts

| file | sha256 (first 16) | bytes |
|---|---|---:|
| `outputs/phase1/phase1_baselines.csv` | `d1e1032816592601` | 842 |
| `outputs/phase1/phase1_estimator_sensitivity.csv` | `63a37583983b1e97` | 451 |
| `results/null_gate_v1.csv` | `fb9e5dec27a1b1a0` | 1277 |
| `results/primary_gate.csv` | `3b3e5e9303508b00` | 783 |
| `results/diagnostic_panel.csv` | `d956d8542be34da5` | 723 |
| `results/replication_sharpe_matrix.csv` | `a705ddb36d7ede03` | 78202 |
| `outputs/phase2/calibration_manifest.json` | `a65337bbc706aa4d` | 2257 |
| `outputs/phase2/calibration_table.csv` | `aff949fe9694a734` | 760 |
| `outputs/phase2_diagnostics/modal_gap_null.json` | `6b4c94b8f0383c01` | 1949 |
| `outputs/phase2_diagnostics/bootstrap_calibration_vs_B.json` | `02725b3557ce0426` | 1674 |
| `outputs/phase2_mechanism/mechanism_null.json` | `60e07aea0cee8983` | 1672112 |
| `results/phase2e_horizon_result.json` | `d7ca6d48ead08999` | 2004 |
| `results/phase2e_power_result.json` | `aecc35bb240c4a7d` | 14626 |
| `results/phase2f_control_result.json` | `a78bc78a30b8e5b0` | 521442 |
| `results/phase2g_result.json` | `20b3a500c5d1c8b6` | 13632 |

### Governing documents

| file | sha256 (first 16) | bytes |
|---|---|---:|
| `RAC_HRP_Phase2_Gate_Result_Memo_v3.md` | `f3a0cd64e6db99a5` | 10650 |
| `RAC_HRP_Phase2_rev5_ERRATUM_E1.md` | `3f4a34db0d6f5ebe` | 2593 |
| `RAC_HRP_Phase2_Reconciliation_111_vs_112.md` | `e9552129ba813c49` | 3880 |
| `RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md` | `9703a626ecbaf5dd` | 18028 |
| `RAC_HRP_Phase2D_Mechanism_Result_Memo.md` | `9509d8a8378c6831` | 6638 |
| `RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md` | `c1eb5d1c05fc9dca` | 7014 |
| `RAC_HRP_Phase1_INCIDENT_E2_deleted_allocator.md` | `86d0d1aa04ab335f` | 6151 |
| `RAC_HRP_Phase1_EWMA_Robustness_Note.md` | `488314fffd1cd686` | 4081 |
| `RAC_HRP_Phase2_Audit_Bundle.md` | `cb1f2074bbba8b7f` | 8025 |
| `docs/PRE_REGISTRATION.md` | `c4a0b5bd2fbd1259` | 5913 |
| `CHANGELOG.md` | `d2d78f50bae65f21` | 16531 |
| `docs/CORRECTION_NOTICE_single_author.md` | `33a4368a3bb2cab6` | 5398 |
| `RAC_HRP_ERRATUM_E4_advisor_approval.md` | `bbf5b5d36c661d06` | 2429 |
| `RAC_HRP_Phase05_ERRATUM_E3_environment_label.md` | `196b13b33cbdd0ba` | 4933 |
| `RAC_HRP_Phase2E_PreSpec_rev3.md` | `74198263f1979836` | 17005 |
| `RAC_HRP_Phase2E_PreSpec_rev4.md` | `dfd736acdeb96e35` | 17190 |
| `RAC_HRP_Phase2E_PreSpec_rev5.md` | `6153831fa0da7a52` | 18277 |
| `RAC_HRP_Phase2E_PreSpec_rev6.md` | `0975b0010d1c5b83` | 20644 |
| `RAC_HRP_Phase2E_PreSpec_rev7.md` | `df7cc9066f786a0e` | 23912 |
| `RAC_HRP_Phase2E_PreSpec_rev8.md` | `cfdd64cca9a23a1d` | 27172 |
| `PHASE2E_FREEZE.txt` | `914cb16a01895950` | 778 |
| `RAC_HRP_Phase2F_PreSpec_rev1.md` | `ca47b609096a04eb` | 7828 |
| `RAC_HRP_Phase2F_PreSpec_rev2.md` | `1adee84e80e10eed` | 7985 |
| `PHASE2F_FREEZE.txt` | `cf51d54d288f3951` | 343 |
| `RAC_HRP_Phase2G_PreSpec_rev1.md` | `c431974eb7bd611b` | 10771 |
| `PHASE2G_FREEZE.txt` | `b54d4f3d6aebcc2b` | 315 |
| `RAC_HRP_Phase2EFG_Audit_Bundle.md` | `be47a0d3a6ad7f7a` | 9865 |

