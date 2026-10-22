# Line

<!-- veragrid-block-introduction:start -->
**Line** represents passive network physics through resistance, inductance, capacitance, coupling, or switching topology. Its equations enforce voltage-current constitutive relations and therefore affect energy storage, damping, propagation, fault current, or grounding behavior.

## Typical use

- Use it to reproduce the electrical path between sources, converters, machines, and loads.
- Keep phases, terminal orientation, connection type, and SI/per-unit parameter bases consistent.
<!-- veragrid-block-introduction:end -->

This model represents a positive-sequence RMS transmission line branch.

### Purpose

It is a positive-sequence AC line model that computes sending-end and receiving-end active and reactive power from terminal voltage magnitudes and angles.

### Behavior

- Uses from-side and to-side terminal voltage magnitudes and angles as inputs.
- Computes active and reactive power at both ends of the line.
- Includes series admittance and the physical total shunt conductance and susceptance.
- Converts each terminal magnitude to the line's common from-terminal reference using the mapped virtual taps.
- Uses the event variable `u` to enable or disable the branch contribution.

### Characteristics

- Algebraic-only RMS branch model.
- Intended for positive-sequence branch power-flow behavior inside RMS dynamic simulations.
- Appropriate for electromechanical timescale studies.
- Does not model phase-domain wave propagation or electromagnetic line detail.

## How it works

The template evaluates the positive-sequence PI powers using common-reference magnitudes $U_f=V_{mf}/t_f$ and $U_t=V_{mt}/t_t$. The line's existing virtual-tap owner supplies $t_f=1$ and $t_t=V_{nom,f}/V_{nom,t}$. Both default to one when unassigned. Each end receives half the physical shunt. When `u = 0`, all four powers, including the shunt contributions, are suppressed.

## Characteristic equations

$$
P_f = u\left[U_f^2\left(g+\frac{g_{sh}}{2}\right) - g U_f U_t \cos(\theta_f - \theta_t) + b U_f U_t \cos\left(\theta_f - \theta_t + \frac{\pi}{2}\right)\right]
$$

$$
Q_f = u\left[U_f^2\left(-\frac{b_{sh}}{2} - b\right) - g U_f U_t \sin(\theta_f - \theta_t) + b U_f U_t \sin\left(\theta_f - \theta_t + \frac{\pi}{2}\right)\right]
$$

Equivalent expressions are used for `P_t` and `Q_t` at the receiving end.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `Vmf` | From-side voltage magnitude | pu |
| Input | `Vaf` | From-side voltage angle | rad |
| Input | `Vmt` | To-side voltage magnitude | pu |
| Input | `Vat` | To-side voltage angle | rad |
| Output | `Pf` | Active power flowing from the from-side terminal into the line model | pu |
| Output | `Pt` | Active power flowing from the to-side terminal into the line model | pu |
| Output | `Qf` | Reactive power flowing from the from-side terminal into the line model | pu |
| Output | `Qt` | Reactive power flowing from the to-side terminal into the line model | pu |
| Variable | `Pf` | Algebraic from-side active-power variable | pu |
| Variable | `Pt` | Algebraic to-side active-power variable | pu |
| Variable | `Qf` | Algebraic from-side reactive-power variable | pu |
| Variable | `Qt` | Algebraic to-side reactive-power variable | pu |
| Variable | `u` | Branch enable multiplier used to switch the model contribution on or off | 0/1 |
| Parameter | `g` | Series conductance of the positive-sequence line model | pu |
| Parameter | `b` | Series susceptance of the positive-sequence line model | pu |
| Parameter | `bsh` | Total shunt susceptance term used by the line model | pu |
| Parameter | `gsh` | Total physical shunt conductance, split equally between ends | pu |
| Parameter | `vtap_f`, `vtap_t` | Terminal-to-common-reference voltage ratios; structural defaults are one | pu |

Saved Blocks retain their recorded equations. Loading or copying an older no-tap template does not regenerate it; explicit template reassignment selects the current equations. Direct per-unit data with an unknown historical voltage reference are preserved without inferring original SI equipment.

## How to use it

- Use this template when branch active and reactive powers are the quantities of interest in RMS simulations.
- Do not use it when EMT traveling-wave behavior, switching transients, or unbalanced phase-domain line behavior is needed.
