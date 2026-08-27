# RAC-HRP — Reproducibility Manifest

Generated 2026-08-27T02:29:04.841936+00:00 at commit `4d5c4f900d5ad9ef0c1c76f461bf0b0b8362420e`
(branch `main`, working tree clean: True).

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
| `rac_hrp/backtest/region_lock.py` | `48ade2f18d598885` | 10404 |
| `rac_hrp/backtest/metrics.py` | `801011199bfc2535` | 3083 |
| `rac_hrp/data/panel.py` | `388acd1c038bd197` | 9240 |
| `rac_hrp/data/universe.py` | `15fa7d17a19b6f32` | 5252 |
| `rac_hrp/nulls/environments.py` | `29e3607e11ed672b` | 9067 |
| `rac_hrp/nulls/environments_static.py` | `6de4695e237cec81` | 6246 |
| `rac_hrp/phase2/config.py` | `44e6ef894050db1b` | 3963 |
| `rac_hrp/phase2/stats.py` | `3f8d29bf90878813` | 9503 |
| `rac_hrp/phase2/calibration.py` | `4b9e62951ea9f547` | 17261 |
| `scripts/run_phase05.py` | `56cfc4d79a81a427` | 10250 |
| `scripts/run_phase1.py` | `9086912bfc8e50fe` | 8916 |
| `scripts/run_phase2.py` | `6aa8f27610c825f1` | 7940 |
| `scripts/run_mechanism_null.py` | `9098fd5bc6f718c3` | 13255 |
| `scripts/run_mechanism_null_parallel.py` | `85767658d4a6b1fb` | 11220 |
| `scripts/diagnose_modal_gap_null.py` | `0e2d3e4a28bd9da5` | 7256 |
| `scripts/diag_bootstrap_calibration_B.py` | `6ebdcbad35c309f1` | 5508 |
| `tests/test_phase05.py` | `c149364040a9d921` | 12157 |
| `tests/test_phase2_stats.py` | `b26d7e0b6b2ecda9` | 6346 |
| `tests/test_covariance_ew.py` | `b26e289173bea3d0` | 7724 |
| `tests/test_region_lock.py` | `a925ea73080ae6ee` | 4548 |

### Result artefacts

| file | sha256 (first 16) | bytes |
|---|---|---:|
| `outputs/phase1/phase1_baselines.csv` | `d1e1032816592601` | 842 |
| `outputs/phase2/calibration_manifest.json` | `a65337bbc706aa4d` | 2257 |
| `outputs/phase2/calibration_table.csv` | `aff949fe9694a734` | 760 |
| `outputs/phase2_diagnostics/modal_gap_null.json` | `6b4c94b8f0383c01` | 1949 |
| `outputs/phase2_diagnostics/bootstrap_calibration_vs_B.json` | `02725b3557ce0426` | 1674 |
| `outputs/phase2_mechanism/mechanism_null.json` | `60e07aea0cee8983` | 1672112 |

### Governing documents

| file | sha256 (first 16) | bytes |
|---|---|---:|
| `RAC_HRP_Phase2_Gate_Result_Memo_v3.md` | `f7d4ef765a1e444d` | 10670 |
| `RAC_HRP_Phase2_rev5_ERRATUM_E1.md` | `cb473fb1f494e614` | 2627 |
| `RAC_HRP_Phase2_Reconciliation_111_vs_112.md` | `dfade405f992e507` | 3905 |
| `RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md` | `07d593a8a0dc7852` | 18047 |
| `RAC_HRP_Phase2D_Mechanism_Result_Memo.md` | `d6220152e472eeca` | 6652 |
| `RAC_HRP_Phase2D_ImplementationDeviationRecord_ID1.md` | `53a62955e1d2284b` | 7035 |
| `RAC_HRP_Phase1_INCIDENT_E2_deleted_allocator.md` | `3581db8cf567b1bd` | 6185 |
| `RAC_HRP_Phase1_EWMA_Robustness_Note.md` | `488314fffd1cd686` | 4081 |
| `RAC_HRP_Phase2_Audit_Bundle.md` | `722b96f1b8db852e` | 8014 |
| `docs/PRE_REGISTRATION.md` | `c4a0b5bd2fbd1259` | 5913 |
| `CHANGELOG.md` | `d2d78f50bae65f21` | 16531 |

