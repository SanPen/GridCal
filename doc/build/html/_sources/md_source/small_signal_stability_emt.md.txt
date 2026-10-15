# 🧬 EMT Small-Signal stability: Floquet analysis

EMT Small-Signal stability analysis studies whether small perturbations grow or decay around a **periodic steady-state trajectory**. VeraGrid performs this assessment with Floquet theory.

This distinction is fundamental. In RMS Small-Signal analysis, the operating point is normally a constant equilibrium in phasor or rotating-frame variables. In phase-domain EMT simulation, a healthy AC steady state is not constant: the instantaneous voltages, currents, fluxes, and many controller signals repeat in time. The object being linearized is therefore a closed periodic orbit, also called a limit cycle, rather than one fixed point.

An intuitive way to view the method is:

1. Follow the settled EMT waveform for one complete repeat period.
2. Add an infinitesimal perturbation at the beginning of that period.
3. Propagate the perturbation through the same complete period.
4. Measure whether it is smaller or larger when the waveform returns to the same phase of its cycle.

The one-period linear map is the **monodromy operator**. Its eigenvalues are the **Floquet multipliers**.

```{important}
VeraGrid captures one complete period from the end of the EMT settling simulation. That entire captured period must already be in periodic steady state. If amplitude, phase, controller states, DC voltage, speed, or any other slow quantity is still drifting, the segment is not a valid periodic orbit and its multipliers must not be interpreted as Floquet stability results.
```

Use [RMS Small-Signal stability](small_signal_stability_rms.md) for modal analysis around an RMS equilibrium. Use [EMT simulations](emt_simulations.md) for the underlying waveform-domain workflow.

## Why ordinary eigenvalue analysis is not enough

For an autonomous or time-invariant model at an equilibrium $x^*$, Small-Signal analysis linearizes once:

$$
\dot{\delta x}=A\delta x.
$$

The eigenvalues of the constant matrix $A$ determine local stability. This is the familiar RMS picture.

For an EMT model in instantaneous phase coordinates, the steady-state trajectory $x^*(t)$ normally satisfies

$$
x^*(t+T)=x^*(t),
$$

and the linearized matrix changes along the waveform:

$$
\dot{\delta x}=A(t)\delta x,
\qquad A(t+T)=A(t).
$$

A Jacobian evaluated at one arbitrary waveform sample describes only that instant. It does not include what the perturbation experiences during the remaining phase angles, switching configurations, saturations, or periodically varying control conditions. Floquet analysis resolves this by propagating the perturbation around the **whole period**.

## When to use Floquet analysis

Use EMT Floquet analysis when:

- the model must remain in instantaneous phase or waveform coordinates;
- the normal operating condition is periodic rather than constant;
- unbalance, harmonic coupling, converter controls, filters, or switching behavior are relevant;
- the objective is the local stability of a settled EMT operating trajectory;
- the important modes cannot be represented reliably by an RMS equilibrium model.

Typical applications include converter-grid interactions, phase-domain machine and network models, weak-grid control interactions, periodically switched systems, and comparisons between RMS and EMT modal behavior.

Floquet analysis is not a replacement for a nonlinear EMT disturbance study. It answers what happens to **infinitesimal** perturbations around one periodic orbit. Fault clearing, protection sequences, large reference steps, current limiting, topology changes, and transitions between operating modes still require time-domain simulation.

## VeraGrid workflow

The complete workflow is:

1. Build the grid and assign valid EMT models.
2. Solve the balanced or three-phase power flow used to initialize the EMT problem.
3. Run an ordinary EMT simulation long enough to verify that the intended periodic steady state is reached.
4. Determine the full repeat period $T$ of that trajectory.
5. Choose an EMT time step $h$ that divides $T$ into an integer number of steps.
6. Set `ss_assessment_time` long enough for all startup transients to decay.
7. Run `SmallSignalStabilityEmtDriver`.
8. Inspect multiplier magnitudes, Floquet exponents, damping, frequencies, participation factors, and numerical sensitivity.

In the GUI, the EMT Small-Signal command requires an available three-phase power-flow result. The scripting driver accepts either `PowerFlowResults` or `PowerFlowResults3Ph`.

## The captured period is the operating point

### What the driver captures

The current driver:

1. simulates the EMT DAE from $t=0$ to `ss_assessment_time` with `StructuralVectorizedSolver`;
2. computes the number of samples as

   $$
   N_T=\operatorname{int}\left(\frac{T}{h}\right);
   $$

3. extracts the final $N_T$ trajectory samples; and
4. builds the one-period perturbation operator along that captured segment.

The captured window is therefore the **last** period before `ss_assessment_time`. `EmtOptions.simulation_time` does not select this window; the Floquet driver uses `ss_assessment_time` as its settling horizon.

The driver does not currently certify automatically that the final period is periodic. Periodicity validation is an engineering prerequisite that must be performed before trusting the modal results.

### How to verify periodic steady state

Before running Floquet analysis, use an ordinary EMT simulation and compare at least the final two complete periods. At matching phase instants, verify that

$$
x(t+T)\approx x(t)
$$

for all relevant states, and that terminal waveforms also repeat. A useful normalized closure measure for one signal is

$$
e_x=
\frac{\max_{t\in[t_0,t_0+T]}|x(t+T)-x(t)|}
{\max_{t\in[t_0,t_0+T]}|x(t)|+\varepsilon}.
$$

There is no universal acceptable value for $e_x$; it must be small compared with the perturbations and modal growth rates being studied. At minimum, check:

- phase voltages and currents;
- DC-link or stored-energy states;
- PLL angle and frequency;
- converter and machine controller integrators;
- rotor speed or other slow mechanical states;
- switching or sampled-control states when present;
- the initial-to-final state mismatch over the candidate period.

Increase `ss_assessment_time` if the final two periods do not overlap, if their envelope is changing, or if the computed multipliers change materially when more settling time is allowed.

```{warning}
A visually sinusoidal voltage is not sufficient evidence of periodic steady state. A slow controller, DC-link, thermal, mechanical, or retained procedural state may still be drifting while the terminal voltage appears settled.
```

### Choosing the correct period

For a waveform whose complete state repeats once per fundamental cycle,

$$
T=\frac{1}{f_{base}}.
$$

This gives $T=0.02$ s at 50 Hz and approximately $T=0.0166667$ s at 60 Hz.

The fundamental electrical period is not always the full system period:

- ordinary harmonics repeat within the fundamental period and do not necessarily require a longer $T$;
- a controller sequence or modulation pattern may repeat only after several fundamental cycles;
- subharmonic behavior requires a multiple of the fundamental period;
- a switching model may require the common repeat period of the electrical waveform, carrier, and sampled controls;
- an averaged converter without explicit carrier switching may repeat at the grid period;
- a truly quasiperiodic trajectory has no single finite repeat period and does not satisfy the assumptions of this Floquet calculation.

Choose the smallest period that reproduces the **entire model state**, not only one selected voltage waveform.

### Period and time-step consistency

Select an integer number of EMT steps per period:

$$
h=\frac{T}{N_T}.
$$

For example, $T/200$ or $T/400$ gives exactly 200 or 400 steps per period. Because the current implementation uses integer truncation when calculating `target_period / time_step`, a non-integer ratio means that the represented window is shorter than the requested period. This creates a phase-closure error in the monodromy map.

Repeat important studies with a smaller $h$ and proportionally more steps per period. A physical critical multiplier should converge as the EMT discretization is refined.

## Settings

Floquet-specific settings are stored in `SmallSignalStabilityEmtOptions`. The EMT integrator settings come from `EmtOptions`.

### Main settings

| Option | Default | Meaning |
| --- | ---: | --- |
| `k` | `6` | Positive number of multipliers to retain. Unlike the RMS driver, the current EMT implementation does not use `k = 0` to request the complete spectrum. |
| `target_period` | `0.02` | Full repeat period $T$ in **seconds**. It is a duration, not a frequency. |
| `target_frequency_hz` | `None` | Optional modal frequency target for the standard Arnoldi path. |
| `max_krylov_dim` | `30` | Krylov subspace dimension budget. |
| `ss_assessment_time` | `0.1` | Time simulated before extracting the final period. It must be at least one period and long enough to reach periodic steady state. |
| `build_type` | `Arnoldi` | `SmallSignalEmtBuildTypes.Arnoldi` or `SmallSignalEmtBuildTypes.HybridArnoldi`. |
| `verbose` | `0` | Diagnostic output level. |

The `target_period` value is expressed in seconds. Enter `0.02` for a 50 Hz fundamental period, not `50`.

### EMT settings used by the assessment

The most important `EmtOptions` fields are:

- `time_step`: integration step $h$ used both to settle the model and to traverse the captured period;
- `integration_method`: normally `DynamicIntegrationMethod.DaeTrapezoidal` for EMT;
- `tolerance`: nonlinear solution tolerance used by the EMT problem;
- initialization and problem settings used to construct the underlying EMT DAE.

The Floquet analysis inherits the numerical model created by these choices. Changing the integration method or time step changes the discrete one-period map and should therefore be included in sensitivity checks.

### Hybrid Arnoldi controls

The following advanced settings primarily affect `HybridArnoldi`:

| Option | Default | Purpose |
| --- | ---: | --- |
| `max_restarts` | `4` | Maximum explicit restart cycles. |
| `restart_tol` | `1e-6` | Relative Ritz-pair residual tolerance. |
| `use_refined_ritz` | `True` | Use refined Ritz vectors when restarting. |
| `adaptive_restart` | `True` | Adapt block size or Krylov depth when residuals stagnate. |
| `stagnation_improve_ratio` | `0.90` | Improvement threshold used for stagnation detection. |
| `stagnation_patience` | `2` | Restart cycles observed before adaptation. |
| `deflation_tol` | `1e-12` | Threshold for removing linearly dependent block vectors. |
| `prefer_ak_operator` | `True` | Prefer the explicit per-step transition stack when available. |
| `use_numba_kernels` | `True` | Use accelerated block propagation and orthogonalization when available. |
| `min_block_size` | `None` | Optional lower block-size bound. |
| `max_block_size` | `None` | Optional upper block-size bound. |
| `max_krylov_dim_cap` | `None` | Optional cap for adaptive Krylov expansion. |

These controls are available through scripting even when only the principal settings are exposed in the GUI.

## Floquet theory

### Periodic nonlinear DAE

Let the EMT model be written as

$$
\dot{x}=f(x,y,t),
$$

$$
0=g(x,y,t),
$$

where $x$ contains differential states and $y$ algebraic variables. Let $(x^*(t),y^*(t))$ be the captured $T$-periodic solution.

Linearizing along the orbit gives

$$
\dot{\delta x}=f_x(t)\delta x+f_y(t)\delta y,
$$

$$
0=g_x(t)\delta x+g_y(t)\delta y.
$$

When $g_y(t)$ is nonsingular, the algebraic perturbation can be eliminated:

$$
\delta y=-g_y(t)^{-1}g_x(t)\delta x,
$$

which produces the reduced linear time-periodic system

$$
\dot{\delta x}=A(t)\delta x,
$$

$$
A(t)=f_x(t)-f_y(t)g_y(t)^{-1}g_x(t),
\qquad A(t+T)=A(t).
$$

VeraGrid applies the equivalent DAE perturbation propagation without requiring the dense reduced matrix to be formed at every sample.

### Fundamental and monodromy matrices

The fundamental matrix $\Phi(t,t_0)$ maps an initial perturbation to a later perturbation:

$$
\delta x(t)=\Phi(t,t_0)\delta x(t_0).
$$

It satisfies

$$
\frac{d\Phi}{dt}=A(t)\Phi,
\qquad \Phi(t_0,t_0)=I.
$$

The transition over one complete period is the monodromy matrix

$$
M=\Phi(t_0+T,t_0).
$$

Changing $t_0$ moves the reference point around the same periodic orbit. The matrix representation changes, but its Floquet multipliers do not.

### Floquet multipliers

The Floquet multipliers are the eigenvalues of the monodromy map:

$$
Mr_i=\mu_i r_i.
$$

If a perturbation is aligned with mode $i$, its amplitude after successive periods behaves approximately as

$$
\delta x(t_0+nT)\propto \mu_i^n.
$$

Therefore:

| Multiplier | Interpretation |
| --- | --- |
| $\lvert\mu_i\rvert<1$ | The perturbation decays from period to period. |
| $\lvert\mu_i\rvert=1$ | Marginal behavior; physical symmetries and numerical error must be considered. |
| $\lvert\mu_i\rvert>1$ | The perturbation grows and the periodic orbit is locally unstable. |

The spectral radius is

$$
\rho(M)=\max_i|\mu_i|.
$$

For an autonomous continuous-time system, a periodic orbit normally has one trivial multiplier at $\mu=1$ associated with shifting the phase along the orbit. A grid-forced, sampled, or explicitly time-periodic EMT model does not necessarily have the same autonomous symmetry. Do not discard a near-unit multiplier automatically; identify its participating states and verify the model timing and reference conditions first.

### Floquet exponents, damping, and frequency

VeraGrid maps each multiplier to a continuous-time Floquet exponent:

$$
\lambda_i=\frac{1}{T}\log(\mu_i)
=\alpha_i+j\beta_i.
$$

It then reports

$$
\zeta_i=-\frac{\alpha_i}{\sqrt{\alpha_i^2+\beta_i^2}},
$$

$$
f_i=\frac{|\beta_i|}{2\pi}.
$$

The complex logarithm is multi-valued. Consequently, exponent frequencies are defined modulo $1/T$ unless a branch is selected from additional physical information. A mode at frequency $f$ and another at $f+m/T$ can map to the same multiplier. Interpret high-frequency modes together with the EMT sampling rate, expected controller or network bandwidth, and the selected target frequency.

### Relation to the Poincaré map

Imagine observing the EMT system once per period at exactly the same waveform phase. The periodic orbit appears as a fixed point of this sampled return map. The monodromy matrix is the local derivative of that return map, and the Floquet multipliers are its eigenvalues. This is why stability is judged with the unit circle: the analysis asks whether the perturbation shrinks at each return.

## Numerical implementation in VeraGrid

### Matrix-free one-period propagation

A dense monodromy matrix is generally expensive to assemble and store. VeraGrid instead exposes the monodromy action as a `scipy.sparse.linalg.LinearOperator`. Applying the operator to a perturbation propagates that perturbation through all EMT steps of the captured period.

The implementation provides three paths:

| Operator | Role |
| --- | --- |
| `EmtFloquetOperator` | Vector-by-vector propagation with cached sparse LU factorizations. |
| `BlockEmtFloquetOperator` | Matrix-by-matrix propagation used by block Krylov methods. |
| `AkStackBlockEmtFloquetOperator` | Product of an explicit stack of per-step state-transition matrices when the EMT problem exposes it. |

Conceptually, if the discrete perturbation map of step $j$ is $A_j$, the monodromy action is

$$
M=A_{N_T-1}A_{N_T-2}\cdots A_1A_0.
$$

The order matters: a perturbation must traverse every step in chronological order around the complete cycle.

### Arnoldi

`SmallSignalEmtBuildTypes.Arnoldi` is the standard path.

- Small systems use a dense fallback by applying the operator to basis vectors.
- Larger systems use ARPACK through `scipy.sparse.linalg.eigs`.
- Without a target frequency, the retained modes are those with the largest multiplier magnitude and are therefore closest to instability.
- With `target_frequency_hz`, the driver targets multipliers close to

  $$
  \sigma=e^{j2\pi f_{target}T}
  $$

  and its conjugate.

Because only `k` modes are retained, a sparse result is a selected part of the spectrum, not proof that no uncomputed unstable mode exists outside the requested search behavior.

### Hybrid Arnoldi

`SmallSignalEmtBuildTypes.HybridArnoldi` is intended for larger or more difficult cases. It uses block propagation, Block Modified Gram-Schmidt orthogonalization, SVD-based deflation, refined Ritz vectors, explicit restarts, and optional adaptation when residual improvement stagnates.

The hybrid path targets dominant multiplier magnitudes. `target_frequency_hz` is currently a standard-Arnoldi feature and should not be assumed to redirect the hybrid selection.

## Results

### Modes

`ResultTypes.Modes` contains one row per retained multiplier:

| Column | Meaning |
| --- | --- |
| `Mu Re` | Real part of $\mu_i$. |
| `Mu Im` | Imaginary part of $\mu_i$. |
| <code>&#124;Mu&#124;</code> | Multiplier magnitude $\lvert\mu_i\rvert$ and direct unit-circle stability indicator. |
| `Damp Ratio` | Damping ratio computed from the selected Floquet exponent branch. |
| `Freq [Hz]` | Frequency obtained from the imaginary part of that exponent. |

The multiplier plot shows the complex multipliers and the unit circle. Points outside the circle are unstable. Points close to the circle require time-step, period, settling, and eigensolver convergence checks.

`results.report_stability()` reports the spectral radius and uses the implementation tolerance around unity. For engineering conclusions, inspect individual modes and numerical sensitivity rather than relying only on that summary string.

### Participation factors

VeraGrid forms left and right modal vectors, bi-orthonormalizes them, and computes normalized magnitudes of

$$
p_{ki}\propto |r_{ki}l_{ki}|.
$$

Rows correspond to EMT state variables and columns to retained Floquet modes. Participation factors help identify which states dominate a critical mode, but they are referenced to the selected point on the periodic orbit and summarize the one-period map. They are not a time-resolved participation waveform.

Closely spaced, repeated, or poorly converged multipliers can make individual eigenvectors and participation factors sensitive. Use grouped physical interpretation when the spectral gap is small.

### Registered result properties

`SmallSignalStabilityEmtResults` stores:

| Property | Type | Description |
| --- | --- | --- |
| `multipliers` | `CxVec` | Eigenvalues of the monodromy map. |
| `right_vecs` | `CxMat` | Right eigenvectors or Ritz vectors of retained modes. |
| `left_vecs` | `CxMat` | Left or dual vectors used for participation factors. |
| `period` | `float` | Analysed period $T$ in seconds. |
| `eigenvalues` | `CxVec` | Floquet exponents `log(multipliers) / period`. |
| `damping_ratios` | `Vec` | Damping ratios derived from the exponents. |
| `conjugate_frequencies` | `Vec` | Exponent frequencies in hertz. |
| `participation_factors` | `Mat` | Mode-normalized state participation factors. |
| `stat_vars_array` | `StrVec` | EMT state labels used in result tables. |

`validate_spectral_gaps(h_step)` can help identify retained multipliers that are poorly isolated relative to the integration-step scale. It is a numerical diagnostic, not a substitute for a residual or convergence study.

## Interpreting a result safely

Use the following order:

1. Confirm that the power flow and EMT initialization converged.
2. Confirm closure of the final two or more waveform periods.
3. Confirm that `target_period / time_step` is an integer.
4. Locate multipliers outside or closest to the unit circle.
5. Inspect their participation factors and associated physical states.
6. Repeat with a longer `ss_assessment_time`.
7. Repeat with a smaller EMT time step.
8. Increase `k` or change the Krylov configuration when the relevant spectral region may be incomplete.
9. Reproduce predicted growth or decay with a small time-domain perturbation.

Only after these checks should a near-unit multiplier be classified as a physical weakly damped or unstable mode.

## GUI workflow

1. Create or open a grid with EMT models assigned to the relevant devices.
2. Run the three-phase power flow. The GUI uses this result to construct the EMT Floquet driver.
3. Run a normal EMT simulation and confirm that the final periods are settled and repeatable.
4. Open the EMT Small-Signal settings.
5. Set the EMT **Time step** and **Integration** method.
6. Set **Assessment time** long enough for settling.
7. Set **Target period** in seconds, for example `0.02` for 50 Hz.
8. Set a positive number of **Modes** and select **Arnoldi** or **Hybrid Arnoldi**.
9. Run **Small-Signal EMT Simulation**.
10. Inspect **Modes**, the multiplier plot, and **Participation factors**.

The GUI field represents a period in seconds. The value passed to `target_period` is always a duration, not a frequency.

## API

The maintained repository examples are under `trunk/Floquet_stability/`. The following compact pattern uses a three-phase power flow and chooses an integer number of EMT steps per period.

```python
import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import (
    SmallSignalStabilityEmtDriver,
)
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import (
    SmallSignalStabilityEmtOptions,
)
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_results import (
    SmallSignalStabilityEmtResults,
)
from VeraGridEngine.enumerations import DynamicIntegrationMethod, SmallSignalEmtBuildTypes


grid: MultiCircuit = gce.open_file("my_emt_case.veragrid")

pf_options: PowerFlowOptions = PowerFlowOptions(verbose=0)
pf_results: PowerFlowResults3Ph = gce.power_flow3ph(grid=grid, options=pf_options)

period_s: float = 1.0 / float(grid.fBase)
steps_per_period: int = 400
time_step_s: float = period_s / float(steps_per_period)

emt_options: EmtOptions = EmtOptions(
    time_step=time_step_s,
    tolerance=1e-6,
    integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
    verbose=0,
)

floquet_options: SmallSignalStabilityEmtOptions = SmallSignalStabilityEmtOptions(
    k=12,
    target_period=period_s,
    ss_assessment_time=20.0 * period_s,
    max_krylov_dim=40,
    build_type=SmallSignalEmtBuildTypes.Arnoldi,
    verbose=1,
)

driver: SmallSignalStabilityEmtDriver = SmallSignalStabilityEmtDriver(
    grid=grid,
    emt_options=emt_options,
    sss_options=floquet_options,
    pf_results=pf_results,
)
driver.run()

results: SmallSignalStabilityEmtResults | None = driver.results
if results is not None:
    multipliers: np.ndarray = np.asarray(results.multipliers, dtype=complex)
    floquet_exponents: np.ndarray = np.asarray(results.eigenvalues, dtype=complex)
    participation: np.ndarray = np.asarray(results.participation_factors, dtype=float)

    print(results.report_stability())
    print(multipliers)
    print(floquet_exponents)
    print(participation)
else:
    print("The EMT Floquet analysis did not produce results.")
```

The example value `20 * period_s` is illustrative, not a guarantee of settling. Models with slow controls or mechanical states may require a much longer assessment time. Verify periodic closure independently.

### Targeting a frequency

The standard Arnoldi path can prioritize multipliers close to an expected modal frequency:

```python
floquet_options: SmallSignalStabilityEmtOptions = SmallSignalStabilityEmtOptions(
    k=8,
    target_period=period_s,
    target_frequency_hz=120.0,
    build_type=SmallSignalEmtBuildTypes.Arnoldi,
)
```

Because frequency is aliased by the multiplier map, use physical knowledge of the system and compare nearby frequency branches.

## EMT Floquet versus RMS Small-Signal

| Aspect | RMS Small-Signal | EMT Floquet Small-Signal |
| --- | --- | --- |
| Reference solution | Constant equilibrium | Complete periodic trajectory |
| Linear model | Constant matrix or pencil | Linear time-periodic system |
| Primary spectrum | Eigenvalues $\lambda$ | Floquet multipliers $\mu$ |
| Stability boundary | Imaginary axis | Unit circle |
| Time evolution represented | Around one operating point | Around all instants of one period |
| Frequency detail | Fundamental phasor/control dynamics | EMT state and periodic waveform coupling |
| Main prerequisite | Consistent initialized equilibrium | Consistent initialized and settled periodic orbit |

When an EMT model is an exact periodic realization of an RMS model, corresponding slow modes can be compared after mapping multipliers to exponents. Agreement is not automatic: the models may have different states, reference frames, bandwidth, switching detail, or initialization assumptions.

## Floquet versus ERA/Matrix Pencil

VeraGrid also contains an EMT ERA/Matrix Pencil workflow. The methods answer different questions.

| Method | Input | Output | Meaning |
| --- | --- | --- | --- |
| Floquet | Periodic EMT trajectory plus model Jacobians | Multipliers of the one-period map | Model-based local stability of a periodic orbit |
| ERA/Matrix Pencil | Selected ringdown time series | Identified poles, residues, and reconstruction diagnostics | Signal-based modal identification |

Use Floquet when the objective is the local stability of the periodic EMT model itself. Use ERA/Matrix Pencil when modes must be inferred from observable transient signals, including data that may not expose the complete model Jacobian.

## Validation and benchmark strategy

The cross-software results against STAMP, including the conversion from EMT
Floquet multipliers to continuous-time exponents, are documented in
[Dynamic simulation benchmarks](dynamic_benchmarks.md#3-stamp-comparison).

Useful repository examples are located in `trunk/Floquet_stability/`, including:

- `scripting_floquet_generator_piline_Rload_emt.py` for an EMT generator-line-load case;
- `kundur_small_signal_rms_vs_emt.py` for RMS/EMT modal comparison;
- `reduced_vs_dense.py` for operator comparisons;
- `hpc_stress_test.py` for Arnoldi and Hybrid Arnoldi stress testing;
- `demo_era_vs_floquet.py` for the distinction between model-based and signal-based modal analysis.

For a defensible study, compare dense and Krylov results on a small case, compare Arnoldi variants when possible, reduce the time step, increase settling time, and confirm predicted modal behavior with a small perturbation in EMT time simulation.

## Common mistakes

- Capturing one fundamental cycle while a slow state is still drifting.
- Treating `target_period` as frequency instead of seconds.
- Choosing a period that represents the voltage but not the complete switching or controller state.
- Using a time step that does not divide the period.
- Assuming `k = 0` has the RMS meaning of “all modes.”
- Interpreting a partial Arnoldi spectrum as the complete spectrum.
- Reading exponent frequency without considering logarithm-branch aliasing.
- Declaring a near-unit multiplier physical before checking time-step and period sensitivity.
- Treating participation factors as instantaneous waveforms.
- Using Floquet analysis for a trajectory that is transient, quasiperiodic, or undergoing a large event.

## References

1. G. Floquet, “Sur les équations différentielles linéaires à coefficients périodiques,” *Annales scientifiques de l'École Normale Supérieure*, 1883.
2. V. A. Yakubovich and V. M. Starzhinskii, *Linear Differential Equations with Periodic Coefficients*. Wiley, 1975.
3. Y. Saad, *Numerical Methods for Large Eigenvalue Problems*, 2nd ed. SIAM, 2011.
4. H. Li, C. Liu, X. Jiang, Y. Zeng, Z. Guo, and T. Q. Zheng, “A Time-Domain Stability Analysis Method for Grid-Connected Inverter With PR Control Based on Floquet Theory,” *IEEE Transactions on Industrial Electronics*, [doi:10.1109/TIE.2020.3036227](https://doi.org/10.1109/TIE.2020.3036227).
5. H. Li et al., “A Floquet theory-based fast time-domain stability analysis for N-parallel inverters system,” *IET Power Electronics*, [doi:10.1049/pel2.12225](https://doi.org/10.1049/pel2.12225).
6. N. Watson and J. Arrillaga, *Power Systems Electromagnetic Transients Simulation*, 2nd ed. IET, 2019.
