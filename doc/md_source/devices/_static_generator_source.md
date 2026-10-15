## StaticGenerator

A `StaticGenerator` is a bus-connected injection. The default `control_mode = PQ`
preserves fixed P/Q behaviour, including existing phase inputs and profiles.
`control_mode = Q-V droop` enables the same steady-state reactive droop curve as a VSC,
without introducing a DC bus or a converter branch.

### Q-V droop inputs and convention

Select **Q-V droop** in the Static Generator properties and provide:

| Property | Meaning |
| --- | --- |
| `P`, `Q` | Total active injection and reactive reference, MW and MVAr. Positive values inject into the network. |
| `Snom` | Positive nominal apparent power in MVA; base of the droop percentage. |
| `droop` | Positive voltage droop in percent on `Snom`. For example, 3 means 3%, not 0.03. |
| `Vset` | Voltage reference in pu. |
| `Vset_min`, `Vset_max` | Clamps on the measured voltage used by the curve; defaults 0.9 and 1.1 pu. These do not enforce network voltage limits. |

If `use_kw` is enabled, enter `P`, `Q` and `Snom` in kW, kVAr and kVA;
compilation converts them to MW, MVAr and MVA, following the generator convention.

With `u = clip(abs(U1), Vset_min, Vset_max)`, the injected reactive power is
`Qinj = Q + (100 * Snom / droop) * (Vset - u)` in MVAr.
The implementation calls the existing VSC `voltage_q_droop()` function and converts
between absorbed and injected power signs and system pu units.
It retains that function's present behaviour: voltage clamping, with no additional
reactive-power clipping. The curve is not an SVC capability-limit or dynamic model.

### Q-V droop in positive-sequence and ABC power flow

In positive-sequence power flow, `U1` is the local bus voltage. The controller is
evaluated in the residual of the existing full nonlinear formulation, using the
same curve as the VSC. For NR, LM or Powell, select the existing
`use_autodiff_jacobian = True` option, as in the VSC droop study: it evaluates the
Jacobian numerically from the residual. No analytic droop derivatives are added,
and neither the Jacobian implementation nor its selection is changed.

In ABC power flow, `U1 = (Ua + a*Ub + a^2*Uc)/3`, with `a = exp(j*2*pi/3)`.
The existing positive-sequence controller projects this voltage and injects balanced
positive-sequence current corresponding to the total `P + j*Qinj`.
It does not impose equal phase voltages or equal phase powers under imbalance.
There are no passive zero- or negative-sequence branches for this static equivalent.
All three AC phases are required. In this mode, total `P` and `Q` (and their profiles)
are used; separate per-phase power inputs do not define the controlled injection.
The ABC formulation retains its existing numerical Jacobian by default.

### Fixed PQ with sequence responses in ABC power flow

For a three-phase PQ device without explicit phase powers, a floating-star `conn = Y`
or nonzero sequence-impedance data selects the sequence model automatically.
There is no separate selector. The source maintains `P + j*Q` in positive sequence:
`I1 = conj((P + j*Q) / (Sbase * U1))` in system pu.
Passive negative-sequence current is `I2 = -U2 / (R2 + j*X2)`.
Terminal total power includes the absorption in the passive sequence branches;
the source does not compensate those losses. Balanced power flow is unchanged.

The existing `conn` property determines the return path. **Y** and **D** block
terminal zero-sequence current. **Yg** uses `I0 = -U0 / (R0 + j*X0)` and requires
a finite, nonzero effective zero-sequence impedance. An explicit neutral (**Yn**)
is not supported by this sequence model. `R0`, `X0`, `R2` and `X2` are in pu on the
network's `Sbase`, irrespective of `use_kw`. All three AC phases must be connected.
An unset `R2 = X2 = 0` means no passive negative-sequence response, not a short circuit;
provide the physical impedance when that response is required.

The implementation reuses the existing Fortescue transform, shunt-admittance storage
and positive-sequence current projection. It adds no earth connections or voltage
reference constraints. In a component with no homopolar return path, absolute
phase-to-earth voltages can remain indeterminate; compare phase-to-phase voltages
and the determined sequence components without interpreting a common displacement
as a physical voltage drop.

Explicit phase powers and their profiles take precedence and retain the phase-power
model, without passive sequence branches. Existing Yg/D PQ devices with no sequence
data also retain that model. Q-V droop keeps its separate behaviour described above.
These are steady-state power-flow models, not converter fault-current-limit controls.

### PowerFactory import and persistence

`ElmGenstat` devices imported as fixed-PQ static generators retain `phtech`,
`nneutral` and `r0/x0/r2/x2` through the same connection and impedance conversion
as PV generators. Machine-base impedances are converted to system base, including
parallel units. In particular, **3PH** blocks terminal I0 rather than creating an
earth connection. The PQ sequence source reproduces the P1/Q1 behaviour validated
against native PowerFactory constq cases; it does not copy the PV controller's
terminal-power compensation. Connection and sequence data survive native save/load.

Without the explicit VSC import option, `ElmSvs` with voltage droop
(`i_ctrl = 1`, `i_droop != 0`) becomes a `StaticGenerator` in Q-V droop mode.
`Srated`, `ddroop` and `usetp` map to `Snom`, `droop` and `Vset`;
the P/Q references are zero, as in the existing SVC-to-VSC route.
Other SVC modes keep their previous shunt mapping. Selecting VSC import retains
the converter mapping. This is a local terminal-voltage equivalent.

The control settings survive native `.veragrid` save/load. Older native static
generators default to PQ. This addition extends power flow and DGS import;
it does not add the droop equations to OPF, dynamic simulation or the DGS exporter.
