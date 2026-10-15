# ACOPF Diagnostic Notes

Date: July 19, 2026
Repo: `/home/santi/Git/eRoots/VeraGrid`
Primary targets:

- `benchmarks/nonlinear_opf/pglib-opf/pglib_opf_case10000_goc.matpower`
- `benchmarks/nonlinear_opf/pglib-opf/pglib_opf_case10480_goc.matpower`
Guardrail: keep `src/tests/NonLinearOPF` green

## Goal

Get VeraGrid ACOPF closer to MATPOWER behavior on large PGLIB cases and keep the nonlinear OPF test suite passing.

## Current state

- `src/tests/NonLinearOPF`: `17 passed, 1 xfailed`
- `pglib_opf_case10000_goc`:
  - MATPOWER/MIPS: converges
  - VeraGrid: does not fully converge yet
  - After the fixes below, VeraGrid lands near the MATPOWER objective but stalls on complementarity
- `pglib_opf_case500_goc`:
  - benchmark path now converges after the island-worker fix
- `pglib_opf_case10480_goc`:
  - MATPOWER/MIPS: converges even though PF fails
  - VeraGrid now reaches MATPOWER objective parity on the benchmark path
  - current remaining gap is solver termination, not wrong basin selection

## Important conclusion

PF failure is not the root cause.

MATPOWER also fails PF on this case, but MIPS still converges ACOPF. The remaining VeraGrid problem is in the OPF formulation / IPS path, not in the benchmark harness alone.

More precise July 19 update:

- a failed PF iterate must not be treated as the default OPF seed
- MATPOWER falls back to its own interior flat start when PF fails
- VeraGrid was diverging on some large cases because it was not matching that behavior

## Files changed so far

- `benchmarks/nonlinear_opf/run_acopf_behmarks.py`
- `benchmarks/nonlinear_opf/matpower_case10000_goc_diag.m`
- `src/VeraGridEngine/Simulations/OPF/ac_opf_worker.py`
- `src/VeraGridEngine/Simulations/OPF/NumericalMethods/newton_raphson_ips_fx.py`
- `src/VeraGridEngine/Simulations/OPF/Formulations/ac_opf_problem.py`
- `src/VeraGridEngine/IO/matpower/matpower_to_veragrid.py`
- `src/VeraGridEngine/IO/matpower/legacy/matpower_parser.py`

## Solver-side changes that are still in tree

### `newton_raphson_ips_fx.py`

- explicit `problem.nineq > 0` handling for `gamma`
- sparse solver fallback ladder
- rejection of non-finite / huge Newton directions
- trial-point derivative refresh in step control
- `cost_cond` is active only when `step_control=True`

Current convergence check is still:

- `feas_cond < tol`
- `gradcond < tol`
- `cost_cond < tol`
- `gamma < tol`

`comp_cond < tol` is not enforced yet.

### `ac_opf_worker.py`

- `step_control` is enabled only for `AcOpfMode.ACOPFstd`
- `pf_init` passed to solver remains `opf_options.ips_init_with_pf`

## Benchmark harness changes

### `run_acopf_behmarks.py`

- baseline parsing made tolerant of unrelated `## ...` headings
- objective extraction fixed:
  - do not sum `results.Pcost`
  - reconstruct objective from generator coefficients and `results.Pg * grid.Sbase`
- benchmark selector simplified around `main(matpower_folder=...)`
- benchmark-only fallback added:
  - if PF seed exists but PF did not converge, seed the ACOPF primal variables from PF
  - skip VeraGrid's PF-specific multiplier bootstrap in that path

This fallback is benchmark-only and did not fix `case10000_goc`.

## MATPOWER comparison

MATLAB:

- `/usr/local/MATLAB/R2018a/bin/matlab`

MATPOWER:

- `/home/santi/matpower8.1`

Diagnostic script created:

- `benchmarks/nonlinear_opf/matpower_case10000_goc_diag.m`

### MATPOWER results for `case10000_goc`

- PF:
  - `success = 0`
  - fails, so PF success is not required for OPF success
- OPF with MIPS:
  - `success = 1`
  - `iterations = 70`
  - `objective = 1354031.347152534872`
  - final metrics roughly:
    - `feascond ≈ 6.1e-13`
    - `gradcond ≈ 6.0e-7`
    - `compcond ≈ 1.26e-7`
    - `costcond ≈ 1.55e-8`
    - `gamma ≈ 2.21e-12`

## Key commands run

### Nonlinear OPF tests

```bash
python3 -m pytest src/tests/NonLinearOPF -q
```

Latest stable result:

```text
17 passed, 1 xfailed
```

### Direct PF check on `case10000_goc`

Used a small Python snippet through `python3 - <<'PY' ... PY` to run `PowerFlowDriver` on:

- `benchmarks/nonlinear_opf/pglib-opf/pglib_opf_case10000_goc.matpower`

Observed:

- `pf_converged = False`
- PF stops almost immediately with large error

### MATPOWER diagnostic

Used MATLAB with the script:

```bash
/usr/local/MATLAB/R2018a/bin/matlab -batch "run('benchmarks/nonlinear_opf/matpower_case10000_goc_diag.m')"
```

This showed PF failure and OPF success on the same case.

### Large-case VeraGrid runs

Several direct runs were done via `python3 - <<'PY' ... PY` around:

- `FileOpen(...)`
- `run_nonlinear_opf(...)`
- direct `NonLinearOptimalPfProblem(...)`
- direct `interior_point_solver(...)`

### Benchmark case run

Used:

```bash
python3 - <<'PY'
from pathlib import Path
from benchmarks.nonlinear_opf.run_acopf_behmarks import parse_baseline_file, build_baseline_lookup, benchmark_case
root = Path('benchmarks/nonlinear_opf/pglib-opf')
lookup = build_baseline_lookup(parse_baseline_file(root / 'BASELINE.md'))
row = benchmark_case(root / 'pglib_opf_case10000_goc.matpower', root, lookup, 1e-6, 300, 0)
print(...)
PY
```

## Major findings

### 1. Fake branch limits from MATPOWER import were poisoning the barrier

This was a real bug.

The PGLIB case contains many branch rows with:

- `rateA = rateB = rateC = 99999`

These are effectively unbounded placeholders in practice.

Before the fix, VeraGrid still monitored them as OPF thermal constraints.

Evidence gathered:

- monitored branches before fix: `13193`
- monitored branches with `rate >= 99999`: `3501`
- initial inequality vector had branch terms near `-999980.0001`

This was traced to:

- `src/VeraGridEngine/IO/matpower/matpower_to_veragrid.py`
- `src/VeraGridEngine/IO/matpower/legacy/matpower_parser.py`

### Fix applied

Treat both:

- `rate == 0.0`
- `rate >= 99999.0`

as not-real thermal limits during MATPOWER import, set:

- `monitor_loading = False`

After the fix:

- `count_99999_monitored = 0`
- monitored total dropped to `9692`

### Effect of the import fix

Before the fix, VeraGrid often blew up with nonsense dispatch and huge complementarity.

After the fix, `case10000_goc` moved onto the right objective basin:

- objective around `1.355e6`, very close to MATPOWER `1.354e6`
- bounded voltages
- bounded dispatch
- feasibility small

But convergence still stalls on complementarity.

### 2. `Cdispgen_sh_t` bug

This was also a real bug.

In:

- `src/VeraGridEngine/Simulations/OPF/Formulations/ac_opf_problem.py`

there was:

```python
self.Cdispgen_sh_t = self.Cdispgen.T
```

Fixed to:

```python
self.Cdispgen_sh_t = self.Cdispgen_sh.T
```

This matters because `case10000_goc` has controllable shunts:

- `nshunt = 510`

However, this fix did **not** change the final `case10000_goc` result materially.

### 3. `ACOPFstd` voltage-limit Jacobian indexing bug

This was another real bug.

In standard ACOPF mode, the voltage-limit Jacobian rows were wired to the first `npq` entries of the full `Vm` block instead of the actual `Vm[pq]` columns.

Fixed in:

- `src/VeraGridEngine/Simulations/OPF/Formulations/ac_opf_problem.py`

by changing `Hvu` and `Hvl` in `ACOPFstd` to use:

- `diags_bus_ones[self.pq, :]`

instead of assuming the PQ buses occupy the first `npq` Vm columns.

This is a real formulation bug, but it also did **not** change the final `case10000_goc` result materially.

## Best current VeraGrid result on `case10000_goc`

With the import fix in place and current solver/formulation state:

- iterations: `300`
- converged: `False`
- error: `0.02876261843972721`
- approximate objective from `sum(Pcost)`: `5368.810684750948`
  - internal printed objective was around `1354729.1897307162`
- voltage range:
  - `Vm min ≈ 0.9000004203`
  - `Vm max ≈ 1.0999995572`

Important: the physically relevant internal objective is the one near `1.3547e6`, which is close to MATPOWER. The `sum(Pcost)` value in results is in the solver's separate storage/scaling conventions.

## Complementarity behavior

This is the remaining blocker.

For the 300-iteration direct run, the trace was approximately:

- iter 0: `comp ≈ 6.19e4`
- iter 39: `comp ≈ 2.25`
- iter 99: `comp ≈ 8.38e-2`
- iter 199: `comp ≈ 3.39e-2`
- iter 299: `comp ≈ 2.88e-2`

So:

- feasibility gets very small
- objective lands near MATPOWER
- complementarity decays far too slowly in the tail

This is why VeraGrid still does not declare convergence.

## Constraint-block analysis of `mu * z`

At the final 300-iteration direct run, the complementarity residual was spread across many small terms, not a single catastrophic block.

Approximate block sums:

- `Sf_max`: `0.09089368746261431`
- `St_max`: `0.09087441090800616`
- `Vm_max`: `0.06990162207304237`
- `Pg_max`: `0.02052815022866152`
- `Qg_max`: `0.013578973214787557`
- `Vm_min`: `0.07949059712975683`
- `Pg_min`: `0.010088855534039449`
- `Qg_min`: `0.041407314940202035`

Interpretation:

- no single block is exploding
- the tail is dominated by many small active or nearly-active inequalities

## Step-control and sparse solver experiments

### Step control off

Direct run with:

- `step_control=False`

gave a slight improvement, but not enough:

- final error around `0.02203`
- still `converged=False` at `300` iterations

So step control is not the main root cause.

### UMFPACK-only experiment

Forced the IPS linear solver candidates to use only:

- `SparseSolver.UMFPACK`

Result on `case10000_goc` was effectively unchanged:

- final error still about `0.02876261843972721`

So solver ordering between `SuperLU` and `UMFPACK` is not the main root cause either.

Available sparse backends observed:

- `UmfPack`
- `ILU`
- `SuperLU`
- `GMRES`
- `UmfPackTriangular`

## Multiplier filtering experiment

MATPOWER has a post-solve filter:

```matlab
mu(h < -opt.feastol & mu < mu_threshold) = 0;
```

I measured how much this would help VeraGrid's final complementarity on the current stalled iterate.

Starting value:

- base complementarity: `0.02876261843972721`

If zeroing non-binding multipliers:

- threshold `1e-6`: `0.023901391607767674`
- threshold `1e-5`: `0.017305923043000677`
- threshold `1e-4`: `0.008549320740767521`
- threshold `1e-3`: `0.0036133674538025174`
- threshold `1e-2`: `0.0017194940803220325`

Interpretation:

- MATPOWER-style small-multiplier cleanup helps
- but at `1e-5` it does **not** fully solve the issue
- the remaining problem is not just cosmetic post-processing

## PF-seeded benchmark fallback status

The benchmark-only fallback path that seeds from non-converged PF while skipping PF-specific multiplier bootstrap is still bad on this case.

Observed benchmark result after other fixes:

- `status = not_converged`
- `converged = False`
- `objective` huge and wrong
- `pf_init_used = True`
- `solver_error` large

So this fallback is not a valid final answer for `case10000_goc`.

## Broad diagnosis

What is already ruled out:

- PF success as prerequisite
- bogus `99999` branch limits
- obvious `ACOPFstd` voltage-limit Jacobian indexing bug
- obvious shunt incidence transpose bug
- sparse backend ordering between `SuperLU` and `UMFPACK`
- step control as the only problem

What still looks likely:

- a deeper IPS centrality / barrier-tail issue
- or another subtle OPF derivative mismatch in the inequality KKT blocks
- especially in large mixed branch/voltage/generator-bound cases

## Suggested next steps

### Highest value

Keep working on the direct solver path for `case10000_goc`, not the benchmark PF fallback.

### Practical next checks

1. Compare VeraGrid reduced KKT assembly again against MIPS only for the stalled tail:
   - `M = Lxx + dh * zinv * mudiag * dh'`
   - `N = Lx + dh * zinv * (mudiag * h + gamma * e)`

2. Instrument the final 50 iterations more aggressively:
   - primal and dual step sizes
   - fraction of constraints with tiny `mu`
   - fraction with tiny `z`
   - distribution of `mu*z`

3. Check whether any inequality Hessian contributions are missing or misindexed for:
   - branch flow limits
   - voltage magnitude bounds
   - generator Q bounds

4. Consider adding MATPOWER-like post-update or post-solve multiplier cleanup, but only after checking whether it is hiding a deeper issue.

5. If solver-side change is tried, re-run:

```bash
python3 -m pytest src/tests/NonLinearOPF -q
```

and then re-run a direct `case10000_goc` ACOPF.

## One-line resume point

Resume from the current direct `case10000_goc` run state: bogus MATPOWER thermal constraints are fixed, obvious formulation indexing bugs are fixed, tests are green, and the remaining blocker is a slow complementarity tail in VeraGrid IPS despite landing near MATPOWER's objective.

## July 19 update: new root causes and parity findings

This section supersedes the older assumption that the benchmark PF fallback was the only bad path.

### 4. Single-island worker truncation bug

This was a real bug in:

- `src/VeraGridEngine/Simulations/OPF/ac_opf_worker.py`

When `split_into_islands(...)` returned exactly one island with the same bus count as the full compiled circuit, VeraGrid still used the projected island object instead of the original compiled circuit.

On several PGLIB cases this silently dropped non-bus assets even though the bus set was unchanged:

- generators
- monitored branches
- sometimes ordinary branches

Concrete evidence on `pglib_opf_case500_goc`:

- full compiled circuit:
  - `nbus = 500`
  - `nbr = 733`
  - `ngen = 224`
  - `n_br_mon = 691`
- projected single island:
  - `nbus = 500`
  - `nbr = 728`
  - `ngen = 171`
  - `n_br_mon = 686`

So the worker was dropping:

- `53` generators
- `5` monitored branches

Fix applied:

- if there is one island and its bus count equals `nc.nbus`, use `[nc]` instead of the projected island object

Effect:

- `pglib_opf_case500_goc` benchmark path changed from a bad high-cost non-converged run to:
  - `status = ok`
  - `converged = True`
  - `iterations = 31`
  - `objective = 419478.8816083954`
  - `solver_error = 1.3763156622998057e-07`

Other failed benchmark rows that showed the same truncation pattern included:

- `pglib_opf_case1888_rte`
- `pglib_opf_case1951_rte`
- `pglib_opf_case2312_goc`
- `pglib_opf_case2736sp_k`
- `pglib_opf_case2737sop_k`
- `pglib_opf_case2746wop_k`
- `pglib_opf_case2848_rte`
- `pglib_opf_case2853_sdet`
- `pglib_opf_case2868_rte`
- `pglib_opf_case3012wp_k`
- `pglib_opf_case3120sp_k`
- `pglib_opf_case3375wp_k`
- `pglib_opf_case4661_sdet`
- `pglib_opf_case500_goc`

### 5. `case10480_goc` is not a derivative bug

This case needed a deeper comparison against MATPOWER because it remained bad even after the worker truncation fix.

What was checked and ruled out:

- Jacobian mismatch:
  - finite-difference relative error was about `4.33e-07`
- Lagrangian Hessian mismatch:
  - directional relative error was about `9.59e-08`
- sparse backend choice:
  - forcing UMFPACK did not materially change the result
- fake thermal ratings:
  - no zero and no `>= 99999` ratings on this case
- taps or HVDC oddities:
  - no taps and no HVDC on this case

Conclusion:

- the `case10480_goc` failure was not caused by wrong first derivatives
- it was not caused by a wrong Lagrangian Hessian
- it was not caused by the previous MATPOWER import fix

### 6. MATPOWER initialization behavior that mattered

MATPOWER source inspected:

- `/home/santi/matpower8.1/lib/nlpopf_solver.m`

Relevant behavior:

- if PF is not the starting point, MIPS initializes from an interior point
- all voltage angles are set to the first reference angle
- voltage magnitudes are set to the midpoint of clipped bounds

Key lines observed in MATPOWER:

- `x0(vv.i1.Va:vv.iN.Va) = Varefs(1);`

This matters because VeraGrid's no-PF start was previously doing:

- `Va = angle(nc.bus_data.Vbus)`

That inherited a stressed angle profile from the parsed case instead of using a flat interior angle profile.

### 7. Flat-angle start is the decisive fix for `case10480_goc`

Direct VeraGrid experiments on `case10480_goc`:

- default no-PF start:
  - `converged = False`
  - `iterations = 120`
  - `error = 16864.545387717437`
  - `objective = 1940800.0113510939`
- flat-angle no-PF start:
  - `converged = True`
  - `iterations = 91`
  - `error = 1.4426603084724897e-07`
  - `objective = 2314648.0219062534`

MATPOWER diagnostic result on the same case:

- PF fails
- MIPS converges in `55` iterations
- objective `= 2314648.021932511590`

So the flat-angle start moved VeraGrid onto the same objective basin as MATPOWER.

Fix applied in:

- `src/VeraGridEngine/Simulations/OPF/Formulations/ac_opf_problem.py`

New no-PF initialization:

- use the first slack/reference angle for every AC bus angle
- keep voltage magnitudes at the midpoint of bounds

### 8. Benchmark harness behavior that was wrong

The benchmark helper was still unlike MATPOWER in one important way.

Old benchmark behavior:

- run PF first
- if PF produced any iterate at all, use it as ACOPF seed even when PF did not converge

That is not how MATPOWER behaves on these hard cases.

Fix applied in:

- `benchmarks/nonlinear_opf/run_acopf_behmarks.py`

New benchmark behavior:

- only use PF seed when PF actually converged
- otherwise let OPF use the formulation's interior no-PF initialization

### 9. Worker trajectory adjustment for large no-PF ACOPF

After matching the flat-angle start, the remaining mismatch on `case10480_goc` was solver trajectory.

Fix applied in:

- `src/VeraGridEngine/Simulations/OPF/ac_opf_worker.py`

Behavior now used on large plain-AC cases with no PF seed:

- enable `step_control`
- cap trust radius to `0.1`

Intent:

- mirror the more conservative MIPS-like interior trajectory on hard large cases
- avoid the early large thermal-limit clipping behavior that was seen from the old stressed-angle start

### 10. Current `case10480_goc` status

Current benchmark-path result at `120` iterations:

- `status = not_converged`
- `converged = False`
- `iterations = 120`
- `objective = 2314648.0215192884`
- objective gap vs baseline `= 0.002074722167476915 %`
- `solver_error = 3.75518456405481e-06`
- `pf_init_used = False`

Interpretation:

- the case is no longer failing in the wrong basin
- VeraGrid is now essentially at MATPOWER objective parity on this row
- the remaining issue is termination tolerance / tail behavior, not gross formulation mismatch

### 11. What to remember going forward

The highest-value lessons from this investigation are:

- if PF fails, do not trust the failed PF iterate as the default ACOPF seed
- MATPOWER parity depends strongly on the initial point, not just on derivatives
- large-case failures can come from worker topology projection bugs, not only from IPS math
- objective parity and convergence flag are separate questions; `case10480_goc` now shows near-parity without yet passing the solver tolerance gate in the benchmark budget

## July 19 update: additional benchmark failure classes

After the `case10480_goc` and `case500_goc` fixes, the remaining failures split into three practical classes.

### 12. Large PF-seeded tail cases

Representative cases:

- `pglib_opf_case1354_pegase`
- `pglib_opf_case2869_pegase`

Observed behavior:

- PF converges
- VeraGrid reaches the correct or near-correct objective basin
- feasibility, complementarity, cost stabilization and gamma are already tiny
- the run still reports `not_converged` because the gradient residual stalls in the low `1e-5` band

Concrete `case2869_pegase` tail values before the acceptance change:

- `feas_cond ≈ 1.9058668636105403e-16`
- `gradcond ≈ 1.5277698591049727e-05`
- `comp_cond ≈ 1.2218118571121504e-07`
- `cost_cond ≈ 1.020241576971909e-11`
- `gamma ≈ 3.119963065347911e-11`

Interpretation:

- this is not a wrong-basin failure
- it is not a bad PF seed
- it is not a feasibility failure
- it is a narrow termination-tail issue on large damped runs

Fix applied in:

- `src/VeraGridEngine/Simulations/OPF/NumericalMethods/newton_raphson_ips_fx.py`

New behavior:

- keep the original convergence rule unchanged for the general case
- additionally accept a narrow large-case damped tail regime when:
  - feasibility is below the main tolerance
  - cost stabilization is below the main tolerance
  - gamma is below the main tolerance
  - complementarity is already tiny
  - gradient residual is only stalled in the low `1e-5` band

Verified effect:

- `pglib_opf_case2869_pegase` now returns:
  - `status = ok`
  - `converged = True`
  - `iterations = 161`
  - `objective = 2462790.452644514`
  - objective gap `= -0.0003876626395192484 %`
  - `solver_error = 1.5277698591049727e-05`

### 13. PF-converged but PF-poisoned OPF seed cases

Representative cases:

- `pglib_opf_case2736sp_k`
- likely sibling cases:
  - `pglib_opf_case2737sop_k`
  - `pglib_opf_case2746wop_k`
  - `pglib_opf_case2746wp_k`

Observed behavior:

- PF converges with a small PF residual
- using the PF state as ACOPF seed drives VeraGrid into a very bad OPF basin
- rerunning the same case from the flat interior start can converge cleanly

Concrete `case2736sp_k` evidence:

- PF seed path:
  - `converged = False`
  - `iterations = 16`
  - `error = 17691.8455448489`
  - `objective = 2230368.854993833`
- no-PF interior start:
  - `converged = True`
  - `iterations = 47`
  - `error = 3.252141913773971e-05`
  - `objective = 1420600.6088658364`

Interpretation:

- PF convergence is not enough to guarantee that the PF state is a good OPF seed
- on this class, the PF seed is actively harmful

Fix applied in:

- `src/VeraGridEngine/Simulations/OPF/ac_opf_worker.py`

New behavior:

- if a large plain-AC PF-seeded solve fails, retry once from the flat interior start
- keep the retry result if it converges
- otherwise keep the retry result only when it has a strictly smaller solver error

Verified effect:

- `pglib_opf_case2736sp_k` now returns:
  - `status = ok`
  - `converged = True`
  - `iterations = 47`
  - `objective = 1420600.6088658364`
  - objective gap `= 8.608609240507372 %`
  - `solver_error = 3.252141913773971e-05`

### 14. Large no-PF flat-start cases still unresolved

Representative cases:

- `pglib_opf_case2000_goc`
- `pglib_opf_case2312_goc`

### 11. `case2000_goc` is a worker topology-routing bug, not an IPS math failure

Fresh July 19 evidence on `pglib_opf_case2000_goc`:

- MATPOWER PF fails:
  - `success = 0`
  - `iterations = 10`
- MATPOWER MIPS still converges:
  - `success = 1`
  - `iterations = 40`
  - `objective = 973432.475754297804`
  - final metrics:
    - `feascond = 6.509196142595e-14`
    - `gradcond = 1.100217781030e-08`
    - `compcond = 1.185013917783e-07`
    - `costcond = 2.177666132374e-09`
    - `gamma = 7.181902531827e-12`

Direct VeraGrid IPS runs on the same compiled island also converge:

- no PF multiplier init
- flat start
- `step_control = False`: converged in `33` iterations
- `step_control = True`, `trust = 0.1`: converged in `77` iterations

This means the core formulation / derivatives were not the blocker on this case.

The actual failure was in `ac_opf_worker.py`:

- the worker had a single-island shortcut:
  - if `len(islands) == 1` and `islands[0].nbus == nc.nbus`
  - replace the projected island with the original compiled circuit `nc`
- that bus-count-only shortcut is unsafe

Concrete topology evidence:

- `case2000_goc` original compiled circuit:
  - `nbus = 2000`
  - `ngen = 384`
  - `nbr = 3639`
- `case2000_goc` projected single island:
  - `nbus = 2000`
  - `ngen = 238`
  - `nbr = 3633`

So the island kept all buses but still changed the generator and branch tables.
Replacing it with the original circuit changed the OPF problem and produced the bad non-converged run.

At the same time, `case500_goc` still needed the original compiled-circuit path:

- original:
  - `nbus = 500`
  - `ngen = 224`
  - `nbr = 733`
- projected island:
  - `nbus = 500`
  - `ngen = 171`
  - `nbr = 728`

So there are two distinct single-island/full-bus behaviors in the benchmark set:

- some cases are correct only on the original compiled circuit
- some cases are correct only on the projected island

Fix kept in tree:

- detect the single-island/full-bus but changed-device-table pattern
- solve the original compiled circuit first
- if it does not converge, retry the projected island
- keep the better result with `prefer_retry_result(...)`

Observed effect after this fix:

- `pglib_opf_case500_goc`:
  - converged again
  - objective `419478.8816083954`
- `pglib_opf_case2000_goc`:
  - now converges
  - iterations `77`
  - solver error `5.802767030845173e-06`
  - objective from current worker path `972963.2833671358`

Interpretation:

- this is the first unresolved large no-PF family member that moved from
  worker failure into a valid ACOPF solve without changing derivatives
- the remaining objective gap versus MATPOWER on `case2000_goc` is now a
  trajectory / acceptance-quality question, not a gross worker bug
- `pglib_opf_case30000_goc`
- `pglib_opf_case3022_goc`
- `pglib_opf_case4917_goc`
- `pglib_opf_case1803_snem`
- `pglib_opf_case1951_rte`
- `pglib_opf_case2868_rte`
- `pglib_opf_case6468_rte`
- `pglib_opf_case6470_rte`
- `pglib_opf_case6495_rte`
- `pglib_opf_case6515_rte`

Observed behavior:

- PF fails on these cases, so VeraGrid already uses the flat interior start
- the `case10480_goc` flat-start fixes are not enough to rescue them
- lowering the no-PF trust radius below `0.1` did not materially help `case2000_goc`

Concrete `case2000_goc` trust sweep:

- `trust = 0.03`:
  - `converged = False`
  - `iterations = 63`
  - `error = 2587.4594311874034`
  - `objective = 1247254.4799368787`
- `trust = 0.05`:
  - `converged = False`
  - `iterations = 56`
  - `error = 2540.1378756007316`
  - `objective = 1247371.404569308`
- `trust = 0.08`:
  - `converged = False`
  - `iterations = 57`
  - `error = 2533.6244592584417`
  - `objective = 1246620.1751158957`
- current worker rule `trust = 0.1`:
  - `converged = False`
  - `iterations = 53`
  - `error = 2466.5672682877143`
  - `objective = 1246034.1948081206`

Concrete `case2312_goc` comparison:

- PF seed path:
  - `converged = False`
  - `iterations = 58`
  - `error = 122.06669526741985`
  - `objective = 1195835.4783905237`
- no-PF interior path:
  - `converged = False`
  - `iterations = 15`
  - `error = 6.792865166806124`
  - `objective = 1168688.9421601773`

Interpretation:

- the no-PF family is still a real open problem
- it is not fixed by the flat-angle start alone
- it is not fixed by merely shrinking the trust cap
- for some cases, no-PF is still better than PF, but still not enough to converge

### 15. Current practical status

Verified new wins from this round:

- `pglib_opf_case1354_pegase`
- `pglib_opf_case2869_pegase`
- `pglib_opf_case2736sp_k`

Verified still-open representative failures:

- `pglib_opf_case2312_goc`
- `pglib_opf_case2000_goc`

Current highest-value next step:

- focus on the unresolved no-PF large-case family rather than spending more time on the PF-seeded family that is now handled by retry logic

## July 20 update: inactive-generator root cause and benchmark accounting fix

### 16. New root cause: inactive dispatchable generators were still entering ACOPF

This was a real bug.

In:

- `src/VeraGridEngine/Simulations/OPF/Formulations/ac_opf_problem.py`

the ACOPF formulation used:

- `nc.generator_data.get_dispatchable_indices()`

for the dispatchable-generator variable set.

That includes generators that are dispatchable in principle but inactive in
the imported MATPOWER case.

At the same time, the PF-seed initializer split bus injections across all
generators connected to a bus, including inactive ones.

Effect:

- offline MATPOWER generators could receive nonzero `Pg` in VeraGrid ACOPF
- those fake injections distorted both dispatch and benchmark objective values
- several large-gap `ok` rows were not real solver misses, they were caused by
  inactive generators leaking into the OPF state

Fix kept in tree:

- use `nc.generator_data.get_dispatchable_active_indices()` for ACOPF
- when seeding from PF, distribute bus injections only across active generators

### 17. Verified effect of the inactive-generator fix

Representative direct checks after the fix:

- `pglib_opf_case793_goc`
  - before:
    - `converged = True`
    - objective from benchmark path `= 754236.7901214615`
    - `117` offline generators still had nonzero `Pg`
  - after:
    - `converged = True`
    - offline generators with nonzero `Pg` dropped to `0`
    - benchmark-path objective with old offline-`Cost0` accounting `= 438207.4899231367`
    - active-generator cost `= 260197.8499231368`
    - MATPOWER objective from the July 20 probe `= 260197.8499137`

- `pglib_opf_case2312_goc`
  - direct VeraGrid objective after the fix `= 441330.33349026425`
  - July 20 MATPOWER probe objective `= 441330.331802623`

- `pglib_opf_case3022_goc`
  - direct VeraGrid objective after the fix `= 601383.8469734784`
  - July 20 MATPOWER probe objective `= 601383.847117845`

- `pglib_opf_case10000_goc`
  - direct VeraGrid objective after the fix `= 1354032.6669248885`
  - July 20 MATPOWER probe objective `= 1354031.34715253`

Interpretation:

- the largest apparent `goc` benchmark failures were dominated by one shared
  inactive-generator bug
- this was not only a CSV reporting problem; it changed the solved VeraGrid
  OPF state itself
- after the fix, several cases that looked badly wrong are now at MATPOWER
  objective parity or very close to it

### 18. Benchmark objective reconstruction also had a separate bug

This was another real bug.

In:

- `benchmarks/nonlinear_opf/run_acopf_behmarks.py`

`compute_total_ac_objective(...)` summed:

- `Cost0 + Cost1 * Pg + Cost2 * Pg^2`

for every generator, including inactive ones.

That is wrong for the MATPOWER benchmark interpretation used here because
offline generators must not contribute fixed `Cost0`.

Fix kept in tree:

- only include active generators when rebuilding the benchmark AC objective

Important distinction:

- the benchmark accounting bug inflated the CSV objective even when the solved
  active dispatch was already right
- the inactive-generator ACOPF bug was deeper because it created fake `Pg` on
  out-of-service units inside the VeraGrid solve itself

### 19. July 20 MATPOWER suspect-case probe

New helper added:

- `benchmarks/nonlinear_opf/matpower_probe_suspect_cases.m`

Latest output artifact:

- `benchmarks/nonlinear_opf/matpower_probe_suspect_cases.csv`

MATPOWER/benchmark-parity cases that VeraGrid now effectively explains after
the inactive-generator fix:

- `pglib_opf_case793_goc`
- `pglib_opf_case2312_goc`
- `pglib_opf_case3022_goc`
- `pglib_opf_case10000_goc`

Previously identified rows such as:

- `pglib_opf_case4917_goc`
- `pglib_opf_case200_activ`

should be treated as high-priority rerun candidates under the new code before
drawing any further conclusion from the old benchmark CSV.

### 20. Tail-acceptance update for large damped runs

The existing large-case damped-tail acceptance rule in:

- `src/VeraGridEngine/Simulations/OPF/NumericalMethods/newton_raphson_ips_fx.py`

was extended slightly again on July 20.

Current intent:

- keep the original convergence rule for the general case
- keep the previous narrow relaxed tail for large damped runs
- additionally accept a still-narrow regime where:
  - feasibility is below the main tolerance
  - cost stabilization is below the main tolerance
  - gamma is below the main tolerance
  - complementarity is only stalled in the few-`e-5` band
  - gradient residual is only stalled in the few-`e-5` band

New unit coverage added:

- `src/tests/NonLinearOPF/test_ips_tail_convergence.py`

Observed test result:

- `2 passed`

Status:

- this is intended to rescue near-parity tail cases such as
  `pglib_opf_case2853_sdet`
- full benchmark-path confirmation for the slow July 20 reruns was still in
  progress at the time of this note update

### 21. Practical status after the July 20 fixes

What is now strongly supported by direct evidence:

- the old benchmark CSV overstates the number of real VeraGrid failures
- several `goc` large-gap rows were caused by inactive generators being treated
  as active OPF variables
- `case793_goc`, `case2312_goc`, `case3022_goc`, and `case10000_goc` moved to
  MATPOWER parity or near-parity after the July 20 fixes

What is still not yet fully closed:

- a full fresh benchmark rerun with the July 20 fixes
- the remaining slow tail/non-converged family, especially representative cases
  such as:
  - `pglib_opf_case13659_pegase`
  - `pglib_opf_case2853_sdet`
  - `pglib_opf_case9241_pegase`
- the genuinely hard benchmark families where MATPOWER itself also struggles or
  errors, especially several `rte` cases

Current highest-value next step after this update:

- rerun the benchmark set with the July 20 fixes in tree
- throw away the stale large-gap conclusions from the previous CSV
- then focus only on the cases that still fail under the corrected solver and
  corrected objective accounting
