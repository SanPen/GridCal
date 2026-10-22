# SPDX-License-Identifier: MPL-2.0
"""Static excitation with a compound source, commutation loading and field limits."""
from __future__ import annotations

from enum import Enum

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class CompoundExciterKind(Enum):
    """Explicit physical coupling and minimum-excitation signal location."""
    ADDITIVE_BRIDGE = 1
    MULTIPLICATIVE_BRIDGE = 2
    GATED_MULTIPLICATIVE_BRIDGE = 3


def build_exst2_template(vf: VarFactory, name: str | None = None,
                         transducer_time: float = .02, regulator_gain: float = 20.0,
                         regulator_time: float = .05, regulator_max: float = 5.0,
                         regulator_min: float = -5.0, field_feedback: float = 1.0,
                         exciter_time: float = .5, rate_gain: float = .05,
                         rate_time: float = 1.0, potential_gain: float = 1.0,
                         current_gain: float = 0.0, commutation_gain: float = .1,
                         field_max: float = 5.0, initial_field_voltage: float = 1.0,
                         kind: CompoundExciterKind = CompoundExciterKind.ADDITIVE_BRIDGE) -> RmsModelTemplate:
    """Build a static exciter with compound rectifier supply and bounded field voltage.

    The voltage error combines reference, sensed voltage and supplementary
    control, minus a field-voltage washout. A non-windup regulator drives a
    compound-source bridge whose potential is ``VE = abs(KP*Vt + j*KI*It)``.
    Commutation loading uses ``IN = KC*Ifd/VE`` and a five-region rectifier
    characteristic: unity for nonpositive IN, a descending linear region up to
    0.433, a square-root region up to 0.75, a final linear region up to one,
    and zero beyond one. Bridge voltage ``VB = VE*FEX(IN)`` multiplies regulator
    output in the multiplicative structures, giving
    ``TE*dEfd/dt = VR*VB - KE*Efd``. The additive structure instead sums bridge
    voltage and regulator forcing: ``TE*dEfd/dt = VR + VB - KE*Efd``. These
    couplings have different operating points and disturbance responses.

    Rectifier supply is exactly zero when VE is zero; the normalized loading
    calculation uses an explicit zero-denominator branch so a fault does not
    introduce NaN through ``0*infinity``. If both KP and KI are configured zero,
    an independent unit bridge supply is selected instead. That is a structural
    supply choice, not a small nonzero potential used during voltage collapse.

    Inputs, in order, are sensed ``VmPu``, ``VRefPu``, additive ``VsPu``, terminal
    phasor ``VrPu``, ``ViPu``, outgoing stator current ``IrPu``, ``IiPu`` and
    normalized ``IfdPu``. The gated structure appends a ninth voltage-error
    minimum-excitation input and exposes the pre-gate error as a second output.
    Its high-value gate follows the supplementary/feedback summation and precedes
    the regulator. Connecting that input to the pre-gate output bypasses an absent
    limiter exactly, without an arbitrary constant. Current and KI must share a
    declared base. Output
    ``EfdPu`` uses the machine's excitation base. Four states represent sensed
    voltage, regulator, field-feedback memory and field voltage when TR/TA are
    positive; zero TR or TA removes the corresponding state exactly. The field
    integrator is non-windup between zero and EFDMAX. Initial regulator/reference
    values balance the declared field operating point against the actual bridge.

    :param vf: Symbol factory owning this exciter graph.
    :param name: Optional label, defaulting to EXST2.
    :param transducer_time: Nonnegative sensed-voltage lag TR in seconds.
    :param regulator_gain: Positive voltage-regulator gain KA.
    :param regulator_time: Nonnegative regulator lag TA in seconds.
    :param regulator_max: Upper non-windup regulator limit VRMAX.
    :param regulator_min: Lower non-windup regulator limit VRMIN.
    :param field_feedback: Linear exciter field feedback KE.
    :param exciter_time: Positive field-integrator time TE in seconds.
    :param rate_gain: Nonnegative field-voltage washout numerator KF.
    :param rate_time: Positive washout denominator TF in seconds.
    :param potential_gain: Nonnegative terminal-voltage source coefficient KP.
    :param current_gain: Nonnegative current-compounding source coefficient KI.
    :param commutation_gain: Nonnegative rectifier-loading coefficient KC.
    :param field_max: Positive field-voltage upper limit EFDMAX.
    :param initial_field_voltage: Initial field voltage; host initialization replaces it.
    :param kind: Additive or multiplicative bridge coupling and limiter structure.
    :return: Native static exciter with explicit compound-source and field dynamics.
    :raises ValueError: Nonfinite settings or invalid dynamics, gains or bounds.
    """
    if min(regulator_gain,exciter_time,rate_time,field_max) <= 0:
        raise ValueError('Compound static exciter gains/dynamic times must be positive')
    elif min(transducer_time,regulator_time,rate_gain,potential_gain,current_gain,commutation_gain) < 0:
        raise ValueError('Compound static exciter times/source gains cannot be negative')
    elif regulator_max <= regulator_min or not 0 <= initial_field_voltage <= field_max:
        raise ValueError('Compound static exciter regulator/field limits are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf,'EXST2' if name is None else name)
    tr: Var = builder.parameter('TR',transducer_time)
    ka: Var = builder.parameter('KA',regulator_gain)
    ta: Var = builder.parameter('TA',regulator_time)
    vrmax: Var = builder.parameter('VRMAX',regulator_max)
    vrmin: Var = builder.parameter('VRMIN',regulator_min)
    ke: Var = builder.parameter('KE',field_feedback)
    te: Var = builder.parameter('TE',exciter_time)
    kf: Var = builder.parameter('KF',rate_gain)
    tf: Var = builder.parameter('TF',rate_time)
    kp: Var = builder.parameter('KP',potential_gain)
    ki: Var = builder.parameter('KI',current_gain)
    kc: Var = builder.parameter('KC',commutation_gain)
    ceiling: Var = builder.parameter('EFDMAX',field_max)
    field0: Var = builder.parameter('Efd0Pu',initial_field_voltage)
    measured_input: Var = builder.input('VmPu',Const(1.0))
    reference: Var = builder.input('VRefPu',Const(1.0))
    supplement: Var = builder.input('VsPu',Const(0.0))
    vr: Var = builder.input('VrPu',Const(1.0))
    vi: Var = builder.input('ViPu',Const(0.0))
    ir: Var = builder.input('IrPu',Const(.5))
    ii: Var = builder.input('IiPu',Const(0.0))
    field_current: Var = builder.input('IfdPu',Const(1.0))
    if potential_gain == 0 and current_gain == 0:
        bridge: Var = builder.algebraic('BridgePu',Const(1.0),Const(1.0))
    else:
        potential: Expr = sym.sqrt((kp*vr-ki*ii)**2+(kp*vi+ki*ir)**2)
        potential_var: Var = builder.algebraic('PotentialPu',potential,potential)
        loading: Var = builder.algebraic('LoadingPu',sym.safe_divide(kc*field_current,potential_var,1.0),
            sym.safe_divide(kc*field_current,potential_var,1.0))
        bridge = builder.algebraic('BridgePu',potential_var*_esst3a_fex(loading),potential_var*_esst3a_fex(loading))
    field: Var = vf.add_var(name=f'EfdPu_{builder.name}')
    measured: Var = builder.lag('MeasuredPu',measured_input,tr,transducer_time,measured_input)
    feedback: Var = builder.washout('FeedbackPu',field,tf,rate_time,kf/tf,field0)
    regulator_initial: Expr = ke*field0-bridge if kind == CompoundExciterKind.ADDITIVE_BRIDGE else ke*field0/bridge
    builder.block.init_eqs[reference] = measured_input+regulator_initial/ka
    error: Var = builder.algebraic('ErrorPu',reference-measured+supplement-feedback,regulator_initial/ka)
    demand: Expr
    if kind == CompoundExciterKind.GATED_MULTIPLICATIVE_BRIDGE:
        minimum: Var = builder.input('UelPu',regulator_initial/ka)
        demand = sym.max(error,minimum)
    else:
        demand = error
    regulator: Var = builder.lag('RegulatorPu',ka*demand,
        ta,regulator_time,regulator_initial,vrmin,vrmax)
    forcing: Expr = regulator+bridge if kind == CompoundExciterKind.ADDITIVE_BRIDGE else regulator*bridge
    builder.differential(field,(forcing-ke*field)/te,field0,Const(0.0),ceiling)
    outputs: tuple[Var,...] = (field,error) if kind == CompoundExciterKind.GATED_MULTIPLICATIVE_BRIDGE else (field,)
    return builder.finish(outputs,'Static exciter with compound rectifier supply, rate feedback and bounded field integration')
