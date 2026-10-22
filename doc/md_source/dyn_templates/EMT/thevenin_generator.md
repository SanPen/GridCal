# Thevenin generator

<!-- veragrid-block-introduction:start -->
**Thevenin generator** imposes or controls an electrical excitation in an EMT network. Depending on the variant, it prescribes voltage or current directly or through a source-equivalent impedance. It is used to represent the grid, a controlled converter terminal, or a standardized transient waveform.

## Typical use

- Use it as a network boundary, disturbance source, or controlled electrical terminal.
- Match polarity, phase convention, grounding, and source impedance to the connected topology.
<!-- veragrid-block-introduction:end -->

This model represents a Thevenin-equivalent generator source for EMT studies.

### Purpose

It is a grounded three-phase passive source with a real reciprocal R/L matrix.
Its explicit voltage mode selects balanced or per-phase internal emf independently
of whether initialization receives balanced PF or three-phase PF results.

### Behavior

- Uses three-phase terminal voltages as inputs.
- Evolves three phase-current states and one electrical-angle state.
- Reconstructs positive-sequence internal emf in balanced mode, or all three
  internal phasors in per-phase mode from `Eabc = Vabc + Zabc Iabc`.
- Injects abc currents into the EMT network according to a source-behind-impedance structure.

### Characteristics

- Compact EMT source model.
- Useful when a full synchronous machine and controls are not required.
- Supports higher-level shared-reference wiring without changing the local source equations.
## Characteristic equations

$$
u_k=e_k-v_k,\qquad \bar u=\frac{u_A+u_B+u_C}{3},\qquad
\bar i=\frac{i_A+i_B+i_C}{3}
$$

$$
\frac{di_k}{dt}=\omega_{base}\left(
\frac{u_k-\bar u-R_s(i_k-\bar i)}{X_s}
+\frac{\bar u-R_0\bar i}{X_0}\right),\quad k=A,B,C
$$

$$
R_{abc}=R_s I+\frac{R_0-R_s}{3}\mathbf1\mathbf1^T,\qquad
L_{abc}=\frac{X_s I+(X_0-X_s)\mathbf1\mathbf1^T/3}{\omega_{base}}
$$

$$
\frac{d\theta}{dt} = \omega_{base} f_{scale}
$$

$$
e_A = E_{scale} E_{pk} \sin(\theta + \theta_{dev})
$$

Equivalent `±2π/3` phase shifts are used for `e_B` and `e_C`.
In per-phase mode, the common angle starts at zero and
`e_k = sqrt(2) E_scale (Re(E_k) sin(theta + theta_dev) + Im(E_k) cos(theta + theta_dev))`.
Currents start at `sqrt(2) Im(I_k)` and their derivatives satisfy the same
runtime matrix law; periodic steady state does not mean zero derivative.

The passive reciprocal family requires `Z2 = Z1`, finite nonnegative
resistances, positive reactances, and grounded-star connection. Independent
negative-sequence machine impedances require a machine model. Exact joint
`R0=X0=1e-20` defaults use logged runtime `Z0=Z1`; exact joint negative-sequence
defaults assume reciprocal `Z2=Z1`. Known incompatible values are diagnosed.
Runtime defaults never overwrite physical device data or saved Block parameters.

Balanced mode retains its physical voltage constraint: an incompatible PF3
snapshot is not repaired by synthesizing zero- or negative-sequence emf.
The structural mode is stored in the existing declarative Block parameters.
Previously saved equations are not automatically migrated.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `v_A` | Instantaneous phase-A terminal voltage | pu |
| Input | `v_B` | Instantaneous phase-B terminal voltage | pu |
| Input | `v_C` | Instantaneous phase-C terminal voltage | pu |
| Output | `i_A` | Phase-A current injected into the EMT network | pu |
| Output | `i_B` | Phase-B current injected into the EMT network | pu |
| Output | `i_C` | Phase-C current injected into the EMT network | pu |
| Variable | `i_A` | Phase-A current state variable | pu |
| Variable | `i_B` | Phase-B current state variable | pu |
| Variable | `i_C` | Phase-C current state variable | pu |
| Variable | `theta` | Common internal electrical angle | rad |
| Variable | `e_A` | Internal phase-A emf | pu |
| Variable | `e_B` | Internal phase-B emf | pu |
| Variable | `e_C` | Internal phase-C emf | pu |
| Variable | `Pe` | Instantaneous electrical active power measured at the source terminals | pu |
| Variable | `Qe` | Existing cross-phase instantaneous reactive observable; not fundamental phasor Q under unbalance | pu |
| Parameter | `omega_base` | Base electrical angular frequency | rad/s |
| Parameter | `R_s` | Source resistance | pu |
| Parameter | `X_s` | Source reactance | pu |
| Parameter | `R_0`, `X_0` | Effective homopolar impedance used by the coupled matrix | pu |
| Parameter | `source_voltage_mode` | Immutable structural marker: balanced 0, per-phase 1 | 0/1 |
| Parameter | `UR_A/B/C`, `UI_A/B/C` | Terminal RMS voltage quadratures from PF | pu |
| Parameter | `IR_A/B/C`, `II_A/B/C` | Injected RMS current quadratures on the phase current base | pu |
| Parameter | `phi_v` | Power-flow-derived terminal voltage angle used for initialization | rad |
| Parameter | `phi` | Power-flow-derived current-to-voltage phase relation used for initialization | rad |
| Parameter | `Vpk` | Power-flow-derived peak phase-voltage magnitude used for initialization | pu |
| Parameter | `Ipk` | Power-flow-derived peak phase-current magnitude used for initialization | pu |
| Parameter | `theta_deviation_param` | Runtime angle-deviation offset applied to the internal emf | rad |
| Parameter | `f_scale` | Runtime frequency scaling applied to the angle state equation | pu |
| Parameter | `E_scale` | Runtime emf-magnitude scaling factor | pu |
| Parameter | `share_enable` | Higher-level flag used by orchestration logic for shared-reference behavior | 0/1 |
| Parameter | `P_share_ref` | Higher-level active-power sharing reference | pu |
| Parameter | `Q_share_ref` | Higher-level reactive-power sharing reference | pu |

## How to use it

- Use this template when you want a compact EMT source behind impedance.
- Use the EMT `Complete generator` instead when you need explicit machine, exciter, governor, and stabilizer dynamics.
