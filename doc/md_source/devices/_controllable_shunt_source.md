## ControllableShunt

A `ControllableShunt` provides reactive support with continuous, discrete or locked control.

### Continuous voltage control in ABC power flow

Continuous control automatically regulates the local positive-sequence voltage magnitude,
`abs(U1) = Vset`, where `U1 = (Ua + a*Ub + a^2*Uc)/3` and `a = exp(j*2*pi/3)`.
It adjusts one common susceptance for the three phases. Phase voltage magnitudes may
differ under imbalance; there is no option to constrain them independently.

The device retains its physical shunt response: current is proportional to voltage,
including its negative-sequence component. **Yg** also carries zero-sequence current;
**Y** and **D** block terminal I0. No extra earth connection or U0 constraint is added.
For Y/D, the current depends on `Uabc - U0`; for Yg it depends on `Uabc`.
All three phases and local voltage control are required. Explicit-neutral and remote
continuous ABC regulation currently produce a diagnostic instead of changing the connection.

The existing `Bmin`/`Bmax` convention is retained: the injected nominal susceptance lies
between `-Bmax` and `-Bmin`, in MVAr at 1 pu. With reactive-limit enforcement enabled,
reaching a bound releases voltage regulation and holds susceptance constant. Terminal
reactive power therefore varies with voltage squared; it is not clamped as a constant Q.
Total conductance `G` remains a fixed balanced admittance. The initial `B` is replaced
by the solved susceptance, so it is not counted twice. At an ideal slack bus, the shunt
keeps its fixed `G + j*B` and does not add another voltage constraint.

`Vset` and `active` profiles are respected. With `use_kw`, conductance and nominal
susceptance inputs are converted from kW/kVAr to MW/MVAr. Independent phase inputs
do not define separate controls in continuous mode.

Colocated U1 generators and continuous shunts share one voltage constraint and must
use the same setpoint. Their existing capability ranges determine participation:
the common control variable moves each device through the same fraction of its range.
Generator limits apply to terminal Q; shunt limits apply to nominal susceptance.
The implementation reuses the existing U1 residual and limit enforcement, without
changes to numerical solvers or Jacobian routines.

Discrete and locked control retain their existing behaviour. Positive-sequence power
flow retains its existing formulation. This extension does not add short-circuit or
dynamic control equations.

### PowerFactory import

Without explicit VSC import, an `ElmSvs` in voltage control without droop is represented
by a continuous `ControllableShunt`. Its susceptances connect AB/BC/CA, so import uses
**D**. ABC regulation uses U1 and a common susceptance, as for PowerFactory's balanced
SVS control with positive-sequence voltage selected.

When bank data are available, the importer reuses the existing VSC-route range:
`Bmin = qmin*nxcap + Qfixcap*nfixcap` and `Bmax = tcrmax + Qfixcap*nfixcap`.
Here, native `qmin` describes one capacitor step, not the whole bank. Legacy exports
without bank data retain the earlier `qmin/qmax` fallback. Reimport the DGS to update
previously imported connections and bank limits.

The separate [StaticGenerator Q-V droop](static_generator.md) route is unchanged.
