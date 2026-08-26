# Phase 2D — Implementation Deviation Record ID1

**Attaches to:** `RAC_HRP_Phase2D_MechanismDiagnostic_PreSpec.md` rev.4 (countersigned)
**Governs:** the single executed mechanism-null run, `outputs/phase2_mechanism/mechanism_null.json`
**Class:** output-neutral implementation deviations. **NOT methodological amendments.**
**Advisor disposition:** ACCEPTED — output-neutral implementation deviations.

Three deviations from the signed text occurred. None alters a statistic, seed,
environment definition, threshold, or decision rule. Each is recorded below in the
form: pre-specified → executed → reason → why output-neutral → verification →
hashes.

---

## D1 — Environment S not registered in `ENVIRONMENTS`

**Pre-specified.** Section 2 lists S with status "registration pending this
signature", i.e. S would be added to `rac_hrp.nulls.environments.ENVIRONMENTS` and
dispatched through `draw()`.

**Executed.** S was NOT registered. It lives in a separate module,
`rac_hrp/nulls/environments_static.py`, and is dispatched directly by the runner.
Nothing under `rac_hrp/nulls/` was edited. A and D continue to go through the
unmodified `draw()`.

**Reason.** Registration would have perturbed the countersigned Phase 0.5 gate.
Three call sites derive behaviour from that dict's contents or ordering:
- `rac_hrp/nulls/gate.py:220` — `envs = environments or list(ENVIRONMENTS.keys())`.
  A fifth key silently enrols S in the frozen Phase 0.5 null gate whenever
  `run_gate()` is called without an explicit environment list.
- `scripts/condition2_static_vs_erc.py:102` and
  `scripts/diagnostic_static_vs_erc.py:69` — `list(ENVIRONMENTS.keys()).index(ENV)`,
  i.e. **seed derivation by dict position**.
- `rac_hrp/nulls/gate_v2_config.py:89` — `ENVIRONMENT_ORDER`, a parallel tuple
  required to agree with the dict.

**Why output-neutral.** The generator function invoked is identical either way;
only the dispatch path differs. Registration affects other, unrelated pipelines,
not this diagnostic's numbers.

**Verification.** `git status --porcelain rac_hrp/nulls/` showed only the new
untracked module; `environments.py`, `gate.py`, `gate_v2.py` and
`gate_v2_config.py` are unmodified in the committed tree.

---

## D2 — Sigma_0 factorisation cached

**Pre-specified.** Section 2 specifies Sigma_0's construction (pairwise-complete
`DataFrame.cov()`, ddof = 1, 10% ridge, eigenvalue flooring, `L = V·sqrt(w)`), with
no statement about when it is computed.

**Executed.** The factorisation `L` is memoised per worker process, keyed on the
SHA-256 of the fitting matrix and the shrink parameter.

**Reason.** The naive implementation recomputed a pairwise-complete covariance over
~3,000 columns on every replication. Measured cost scales quadratically in panel
width (0.18 s at N = 200; 0.74 s at N = 500; 2.90 s at N = 1,000), extrapolating to
~26 s per call at N = 3,022. Over 500 S replications this was ~3.6 hours of
recomputing an identical matrix, and it dominated the serial runtime.

**Why output-neutral.** Sigma_0 depends only on `(X_fit, shrink)`, both fixed for
the whole run. The random generator is consumed **only after** the factorisation
(`Z = rng.standard_normal(...)`), so caching cannot advance or perturb the RNG
stream. Emitted draws are bit-identical.

**Verification.** `environments_static.verify_sigma0_cache()` compares a cached
draw against a freshly-computed one under an identical seed and returned `True`
(exact array equality including NaN placement). Independently, the diagnostic's
real-data reference reproduced the frozen Phase 2A gate exactly: E = 233,
n = 149/111/81/58.

---

## D3 — Parallel execution (12 workers)

**Pre-specified.** Section 5 states "No parallelism is used, which keeps the run
fully deterministic", with a serial runtime estimate of ~2.5 h.

**Executed.** `scripts/run_mechanism_null_parallel.py`, 12 worker processes. The
countersigned serial script `scripts/run_mechanism_null.py` was NOT modified; the
parallel runner is a separate entry point.

**Reason.** The serial run's measured cost was far above the pre-spec estimate
(see section 4). With D2 applied, parallel execution completed in 33.5 min.

**Why output-neutral.** Determinism here comes from the seeding scheme, not from
execution order:
- Seeding is **per replication**: `env_seed(env, rep) = 20260822 + 1000·env_index
  + rep`. No generator is threaded across replications, so the worker computing
  replication *r* produces exactly what the serial loop produced at *r*.
- `m(n)` is computed **in the parent** from one shared cache; workers return raw
  trigger indices only. Every replication therefore receives an identical density
  correction regardless of scheduling.
- Results are re-sorted into `(env_index, rep)` order **before** any statistic is
  formed.

**Verification.** Serial and parallel runners produced identical real-data
references (E = 233; n = 149/111/81/58; B = +0.1824 / +0.3182 / +0.4125 / +0.5263)
on two different machines and operating systems. Library versions were pinned to
match the frozen gate (numpy 1.26.4, pandas 2.2.2) inside a dedicated venv; the
loaded numpy was confirmed from `/proc/<pid>/maps` to resolve to that venv.

---

## 4. Chronology of the abandoned serial execution

A first serial run (`scripts/run_mechanism_null.py`, macOS, same commit lineage)
was started and terminated at approximately 55% completion (environment
`S_static_corr`, replication 319 of 500; environments A complete, D not started).

**Extent of what was observable, stated precisely.** The run's stdout was
block-buffered to a file and the process was terminated before any flush: the log
file `mechanism_run.log` was **0 bytes** at termination, and no JSON record was
written (the record is emitted only at process exit). No four-gamma table, no
quantile, and no outcome classification was ever produced by that execution.

Two things *were* observed from it, both while diagnosing runtime:
1. A `py-spy dump --locals` stack showing `env = "S_static_corr"`, `rep = 319`,
   `E = 233`, and an **elided** dict repr `row: {"rep": 318, "gammas": {...}}` —
   the nested statistic values were not expanded and were not seen.
2. Process-level resource figures (CPU time, RSS, %CPU).

Neither exposes a null-distribution statistic. No environment, statistic, seed,
threshold, or decision rule was altered after that run began, and no partial output
from it was used for substantive interpretation. The only changes made in response
were D2 and D3 above, both motivated solely by runtime.

**Retention.** The abandoned run produced no data files to retain (0-byte log, no
JSON). This record is the chronology.

---

## 5. Disposition

All three deviations are **output-neutral implementation changes**, not
methodological amendments. The 1,500 pre-registered replications stand; no rerun is
required. This record is hashed into the Phase 2D mechanism audit bundle alongside
the pre-specification, the result memo, the run manifest, and the producing code.
