# PI line

<!-- veragrid-block-introduction:start -->
**PI line** represents passive network physics through resistance, inductance, capacitance, coupling, or switching topology. Its equations enforce voltage-current constitutive relations and therefore affect energy storage, damping, propagation, fault current, or grounding behavior.

## Typical use

- Use it to reproduce the electrical path between sources, converters, machines, and loads.
- Keep phases, terminal orientation, connection type, and SI/per-unit parameter bases consistent.
<!-- veragrid-block-introduction:end -->

This model represents a conductor-selective pi-section transmission line for EMT studies. It can retain any configured subset of the full NABC conductor set, so ABC is a common case rather than a restriction.

### Purpose

It is a phase-selective EMT pi-line model with explicit mapped `R`, inverse `L`, half-shunt `C` and physical half-shunt `G` matrices.

### Behavior

- Uses active from-side and to-side terminal voltages as inputs.
- Evolves series-current and shunt-charge-related dynamic variables.
- Computes branch-port currents on both ends.
- Reduces the full NABC parameter matrices to the physically active phase set.
- Creates terminal ports and states only for enabled neutral and phase conductors; examples include A, AB, AC, ABC, NA, NAB, and NABC.

### Characteristics

- EMT branch model based on a pi equivalent.
- Suitable for detailed phase-domain line studies.
- More detailed than the RMS line power-flow-style template.
## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `vf_N` | From-side neutral terminal voltage when the neutral is active | pu |
| Input | `vf_A` | From-side phase-A terminal voltage when phase A is active | pu |
| Input | `vf_B` | From-side phase-B terminal voltage when phase B is active | pu |
| Input | `vf_C` | From-side phase-C terminal voltage when phase C is active | pu |
| Input | `vt_N` | To-side neutral terminal voltage when the neutral is active | pu |
| Input | `vt_A` | To-side phase-A terminal voltage when phase A is active | pu |
| Input | `vt_B` | To-side phase-B terminal voltage when phase B is active | pu |
| Input | `vt_C` | To-side phase-C terminal voltage when phase C is active | pu |
| Output | `if_N` | From-side neutral current when the neutral is active | pu |
| Output | `if_A` | From-side phase-A current when phase A is active | pu |
| Output | `if_B` | From-side phase-B current when phase B is active | pu |
| Output | `if_C` | From-side phase-C current when phase C is active | pu |
| Output | `it_N` | To-side neutral current when the neutral is active | pu |
| Output | `it_A` | To-side phase-A current when phase A is active | pu |
| Output | `it_B` | To-side phase-B current when phase B is active | pu |
| Output | `it_C` | To-side phase-C current when phase C is active | pu |
| Variable | `i_ser_phase` | Series-current state for each active conductor | pu |
| Variable | `q_f_phase` | From-side shunt-charge state for each active conductor | pu·s equivalent state |
| Variable | `q_t_phase` | To-side shunt-charge state for each active conductor | pu·s equivalent state |
| Variable | `i_cap_f_phase` | From-side shunt-capacitor current variable for each active conductor | pu |
| Variable | `i_cap_t_phase` | To-side shunt-capacitor current variable for each active conductor | pu |
| Variable | `if_phase` | From-side branch-port current variable for each active conductor | pu |
| Variable | `it_phase` | To-side branch-port current variable for each active conductor | pu |
| Parameter | `Rnn..Rcc` | Full NABC resistance matrix entries mapped from the line data | pu |
| Parameter | `Linv_nn..Linv_cc` | Full NABC inverse-inductance matrix entries mapped from the line data | 1/(pu·s) |
| Parameter | `Cnn..Ccc` | Full NABC shunt-capacitance matrix entries mapped from the line data | pu·s |
| Parameter | `Gnn..Gcc` | Physical half-shunt conductance matrix entries | pu |
| Parameter | `vtap_f`, `vtap_t` | Terminal-to-common-reference voltage ratios; defaults are one | pu |
| Parameter | `G_damp` | Local numerical conductance at each bus port; default `1e-5` | pu |

## Equations and initialization

The line state uses the common from-terminal voltage reference, with $u_f=v_f/t_f$ and $u_t=v_t/t_t$. For each active conductor set,

$$
\dot i_{ser}=L^{-1}(u_f-u_t-Ri_{ser}),\qquad q_f=Cu_f,\quad q_t=Cu_t,
$$

$$
i_f=(i_{ser}+\dot q_f+Gu_f)/t_f+G_{damp}v_f,\qquad
i_t=(-i_{ser}+\dot q_t+Gu_t)/t_t+G_{damp}v_t.
$$

Voltage and current transformations are paired to preserve port power. The physical total shunt is split once between the two ends. Numerical damping remains a local port conductance and adds its own loss; it is not included in the physical line matrices. Set it to zero for exact comparison with a PF model that has no numerical shunt.

Explicit initialization reconstructs the common-reference series current from both terminal currents after subtracting the physical shunt and local damping. Charge and capacitor-current initialization use $Cv/t$ and $C\dot v/t$. Derivative initialization uses the same state equations. Balanced-PF startup consumes the declared mapped taps; PF3 startup retains the existing phase-power convention.

These laws follow the physical PI and ideal-transformer relations in the [EMTP PI documentation](https://emtp.com/documents/EMTP-Documentation/doc/pi/pi.pdf) and [EMTP ideal-unit documentation](https://emtp.com/documents/EMTP-Documentation/doc/transformers/ideal-unit.pdf). Applying those relations to per-unit bus coordinates is the implementation's coordinate conversion. The tests qualify equations, native startup and refined steps; they do not establish parity with an EMTP executable.

Saved no-tap Blocks keep their recorded equations and declared parameters on load or copy. Only explicit template reassignment selects the current PI equations. An unknown historical voltage reference is not inferred from current bus metadata.

## How to use it

- Use this template for phase-domain EMT line studies when a pi-equivalent representation is sufficient.
- Use Bergeron or JMARTI-style alternatives when propagation-delay behavior is more important.
