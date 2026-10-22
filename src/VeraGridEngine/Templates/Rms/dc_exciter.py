# SPDX-License-Identifier: MPL-2.0
"""Shared rotating-exciter field circuits with explicit sensing, saturation and limits."""
from __future__ import annotations

import math
from enum import Enum

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import _quadratic_saturation_coefficients
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class DcExciterKind(Enum):
    """Physical differences in the voltage regulator and field circuit."""
    TYPE1 = 1
    COMPENSATED_TYPE1 = 2
    DC1A = 3
    DC2 = 4
    DC2A = 5
    TYPE2 = 6
    COMPENSATED_TYPE2 = 7
    TYPE2A = 8
    BRUSHLESS = 9
    LIMITED_TYPE1 = 10
    BOUNDED_FIXED_SUPPLY = 11
    BOUNDED_TERMINAL_SUPPLY = 12


class RotatingLimiterLocation(Enum):
    """Additive error signal or takeover gate after phase compensation."""
    SUMMATION = 1
    TAKEOVER_GATE = 2


class DcExciterParameters:
    """Physical coefficients and optional operating-point rheostat calibration."""
    __slots__ = ('tr','ka','ta','tb','tc','vrmax','vrmin','ke','te','kf','tf',
                 'e1','se1','e2','se2','initial_field_voltage','tf2','tf3','field_min','field_max')

    def __init__(self, tr: float = .02, ka: float = 100.0, ta: float = .05,
                 tb: float = .2, tc: float = .1, vrmax: float | None = 5.0,
                 vrmin: float = -5.0, ke: float | None = 1.0, te: float = .5,
                 kf: float = .05, tf: float = 1.0, e1: float = 3.0,
                 se1: float = .1, e2: float = 4.0, se2: float = .3,
                 initial_field_voltage: float = 1.0, tf2: float = 1.0, tf3: float = 0.0,
                 field_min: float = 0.0, field_max: float = 999.0) -> None:
        """Store coefficients; construction validates their physical domains.

        :param tr: Voltage-transducer lag in seconds; zero is instantaneous.
        :param ka: Positive regulator gain.
        :param ta: Regulator lag in seconds; zero is instantaneous.
        :param tb: Phase-compensator lag in seconds; zero requires zero lead.
        :param tc: Phase-compensator lead in seconds.
        :param vrmax: Upper regulator capability, or None to derive it at e2.
        :param vrmin: Lower regulator capability, superseded by symmetric derived limits.
        :param ke: Field resistance coefficient, or None for slow rheostat calibration.
        :param te: Positive exciter field time constant, in seconds.
        :param kf: Nonnegative field-voltage rate feedback gain.
        :param tf: Positive rate-feedback time constant, in seconds.
        :param e1: First field-voltage saturation sample.
        :param se1: Saturation factor at the first sample.
        :param e2: Second field-voltage saturation sample.
        :param se2: Saturation factor at the second sample.
        :param initial_field_voltage: Field-voltage initialization seed in per unit.
        :param tf2: Second regulator-feedback filter time constant, when present.
        :param tf3: Brushless field-current feedback lead time in seconds.
        :param field_min: External output lower bound for limited type 1, or field-memory lower stop for bounded circuits.
        :param field_max: Field-memory upper stop for the bounded rotating circuits.
        """
        self.tr: float = tr
        self.ka: float = ka
        self.ta: float = ta
        self.tb: float = tb
        self.tc: float = tc
        self.vrmax: float | None = vrmax
        self.vrmin: float = vrmin
        self.ke: float | None = ke
        self.te: float = te
        self.kf: float = kf
        self.tf: float = tf
        self.e1: float = e1
        self.se1: float = se1
        self.e2: float = e2
        self.se2: float = se2
        self.initial_field_voltage: float = initial_field_voltage
        self.tf2: float = tf2
        self.tf3: float = tf3
        self.field_min: float = field_min
        self.field_max: float = field_max


def build_dc_exciter(vf: VarFactory, name: str, kind: DcExciterKind,
                      parameters: DcExciterParameters | None = None,
                      minimum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                      maximum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION) -> RmsModelTemplate:
    """Assemble the field-controlled exciter from shared physical stages.

    Inputs are compensated voltage, voltage reference, additive stabilizing
    voltage, underexcitation signal and actual terminal-voltage magnitude.
    Outputs are field voltage and the pre-limiter regulator demand. A caller
    without a high-value limiter connects its underexcitation input to that
    demand, disabling the gate exactly without an artificial negative constant.

    Saturation is the excess field voltage B*max(Efd-A,0)**2, fitted to the
    samples E1*S(E1) and E2*S(E2). Zero saturation factors remove the nonlinear
    branch structurally. Most structures expose field memory directly; the
    externally limited type-1 structure instead clips delivered voltage while
    rate feedback samples internal memory and field losses sample delivered
    voltage. Regulator limits act on the regulator state, before the
    exciter field integrator, with directional non-windup recovery.

    The optional rheostat calibration is frozen at initialization: the regulator
    supplies one tenth of its upper capability at the initial field voltage.
    The resulting field coefficient remains constant during disturbances.
    Automatic capability uses the second saturation sample and
    any specified positive field coefficient. It produces symmetric limits.

    Bounded rotating circuits append a sixth maximum-excitation port. Both
    limiter signals can sum before compensation or take over through sequential
    high/low gates after compensation. Their field memory has explicit lower
    and upper travel stops. Capability can be independently supplied or follow
    actual terminal voltage. Inspection outputs expose pre-gate demand so absent
    takeover controllers can be bypassed exactly. Saturation samples may be
    provided in either voltage order when capability is explicit.

    Zero sensing/regulator/phase-compensation lags become exact algebraic
    equations; positive lags own one state each. Neither the field circuit nor
    rate feedback is approximated by an arbitrarily small time constant.

    :param vf: Shared native symbolic variable factory.
    :param name: Unique instance label.
    :param kind: Explicit physical regulator/limiter structure.
    :param parameters: Coefficients, or physical construction defaults.
    :param minimum_location: Additive or high-value takeover location for bounded rotating circuits.
    :param maximum_location: Additive or low-value takeover location for bounded rotating circuits.
    :return: Native controller with a square internal equation system.
    :raises ValueError: Invalid coefficient domain or undefined calibration.
    """
    p: DcExciterParameters = DcExciterParameters() if parameters is None else parameters
    bounded_field: bool = kind in (DcExciterKind.BOUNDED_FIXED_SUPPLY,DcExciterKind.BOUNDED_TERMINAL_SUPPLY)
    samples_ordered: bool = (p.e1 > 0 and p.e2 > 0 and (p.e2-p.e1)*(p.se2*p.e2-p.se1*p.e1) > 0) if bounded_field else (p.e2 > p.e1 > 0 and p.se2*p.e2 > p.se1*p.e1)
    coefficients: tuple[float, ...] = (p.tr,p.ka,p.ta,p.tb,p.tc,p.vrmin,p.te,p.kf,
        p.tf,p.e1,p.se1,p.e2,p.se2,p.initial_field_voltage,p.tf2,p.tf3,p.field_min,p.field_max)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('DC excitation coefficients must be finite')
    elif min(p.tr,p.ta,p.tb,p.tc,p.kf,p.e1,p.se1,p.e2,p.se2) < 0 or min(p.ka,p.te,p.tf) <= 0:
        raise ValueError('DC excitation gains/times/saturation samples have invalid domains')
    elif p.ke is not None and not math.isfinite(p.ke):
        raise ValueError('Field coefficient must be finite')
    elif p.tb == 0 and p.tc != 0 and kind not in (DcExciterKind.TYPE1,DcExciterKind.TYPE2,DcExciterKind.LIMITED_TYPE1):
        raise ValueError('An instantaneous phase compensator requires zero lead')
    elif kind in (DcExciterKind.TYPE2,DcExciterKind.COMPENSATED_TYPE2) and p.tf2 <= 0:
        raise ValueError('Regulator-feedback filtering requires a positive second time constant')
    elif kind == DcExciterKind.BRUSHLESS and min(p.tf2,p.tf3) < 0:
        raise ValueError('Brushless feedback requires nonnegative secondary time constants')
    elif kind == DcExciterKind.LIMITED_TYPE1 and p.field_min >= p.e2:
        raise ValueError('External field-output upper limit must exceed its lower limit')
    elif bounded_field and (p.field_max <= p.field_min or not isinstance(minimum_location,RotatingLimiterLocation) or not isinstance(maximum_location,RotatingLimiterLocation)):
        raise ValueError('Bounded rotating field requires ordered stops and explicit limiter locations')
    elif bounded_field and p.vrmax is None and p.e2 <= p.e1:
        raise ValueError('Automatic bounded-field capability requires increasing voltage samples')
    elif (p.se1 != 0 or p.se2 != 0) and not samples_ordered:
        raise ValueError('Enabled saturation requires increasing voltage and excess-field samples')
    else:
        pass
    upper: float = p.e2*(p.se2+max(0.0,0.0 if p.ke is None else p.ke)) if p.vrmax is None else p.vrmax
    lower: float = -upper if p.vrmax is None else p.vrmin
    if not math.isfinite(upper) or upper <= lower:
        raise ValueError('DC excitation upper capability must exceed lower capability')
    elif p.ke is None and p.initial_field_voltage == 0:
        raise ValueError('Rheostat calibration requires a nonzero initial field voltage')
    elif kind in (DcExciterKind.DC1A,DcExciterKind.COMPENSATED_TYPE2,DcExciterKind.TYPE2A,DcExciterKind.BRUSHLESS) and p.initial_field_voltage < 0:
        raise ValueError('This field circuit does not permit negative field voltage')
    else:
        pass
    control: ControlRealization = ControlRealization(vf,name)
    sensing_time: float = 0.0 if kind == DcExciterKind.LIMITED_TYPE1 else p.tr
    tr: Var = control.parameter('TR',sensing_time)
    ka: Var = control.parameter('KA',p.ka)
    ta: Var = control.parameter('TA',p.ta)
    tb: Var = control.parameter('TB',p.tb)
    tc: Var = control.parameter('TC',p.tc)
    vmax: Var = control.parameter('VRMAX',upper)
    vmin: Var = control.parameter('VRMIN',lower)
    te: Var = control.parameter('TE',p.te)
    kf: Var = control.parameter('KF',p.kf)
    tf: Var = control.parameter('TF1',p.tf)
    e1: Var = control.parameter('E1',p.e1)
    s1: Var = control.parameter('SE1',p.se1)
    e2: Var = control.parameter('E2',p.e2)
    s2: Var = control.parameter('SE2',p.se2)
    initial_field: Var = control.parameter('Efd0Pu',p.initial_field_voltage)
    initial_voltage: Var = control.parameter('Us0Pu',1.0)
    field: Var = vf.add_var(('FieldInternalPu_' if kind == DcExciterKind.LIMITED_TYPE1 else 'EfdPu_')+name)
    field_voltage: Var
    if kind == DcExciterKind.LIMITED_TYPE1:
        field_min: Var = control.parameter('EFDMIN',p.field_min)
        field_voltage = control.algebraic('EfdPu',sym.hard_sat(field,field_min,e2),initial_field)
    else:
        field_voltage = field
    loss: Expr
    initial_loss: Expr
    if p.se1 == 0 and p.se2 == 0:
        loss = Const(0.0)
        initial_loss = Const(0.0)
    else:
        threshold: Expr
        gain: Expr
        if bounded_field and p.e1 > p.e2:
            # The physical fit accepts either sample order while retaining named coefficients.
            threshold,gain = _quadratic_saturation_coefficients(e2,s2,e1,s1)
        else:
            threshold,gain = _quadratic_saturation_coefficients(e1,s1,e2,s2)
        loss = gain*sym.max(field_voltage-threshold,Const(0.0))**2
        initial_loss = gain*sym.max(initial_field-threshold,Const(0.0))**2
    ke: Var = vf.add_var('KE_'+name)
    if p.ke is None:
        # The rheostat is adjusted once at the operating point, not continuously.
        control.block.event_dict[ke] = vf.add_const(value=None)
        control.block.init_eqs[ke] = (vmax/Const(10.0)-initial_loss)/initial_field
    else:
        control.block.event_dict[ke] = Const(p.ke)
    initial_regulator: Expr = ke*initial_field+initial_loss
    initial_demand: Expr = initial_regulator/ka
    sensed: Var = control.input('UsPu',initial_voltage)
    reference: Var = control.input('UsRefPu',initial_voltage+initial_demand)
    supplementary: Var = control.input('VsPu',Const(0.0))
    gated: bool = kind in (DcExciterKind.DC1A,DcExciterKind.DC2A) or (bounded_field and minimum_location == RotatingLimiterLocation.TAKEOVER_GATE)
    underexcitation: Var = control.input('UelPu',initial_demand if gated else Const(0.0))
    terminal: Var = control.input('VtPu',initial_voltage)
    maximum_input: Var | None = control.input('OelPu',initial_demand if maximum_location == RotatingLimiterLocation.TAKEOVER_GATE else Const(0.)) if bounded_field else None
    measured: Var = control.lag('MeasuredPu',sensed,tr,sensing_time,initial_voltage)
    feedback_source: Var
    feedback_initial: Expr
    regulator_feedback: bool = kind in (DcExciterKind.TYPE2,DcExciterKind.COMPENSATED_TYPE2)
    if regulator_feedback or kind in (DcExciterKind.TYPE2A,DcExciterKind.BRUSHLESS):
        feedback_source = vf.add_var('FeedbackSourcePu_'+name)
        feedback_initial = initial_regulator
    else:
        feedback_source = field
        feedback_initial = initial_field
    rate: Var = control.washout('RatePu',feedback_source,tf,p.tf,kf/tf,feedback_initial)
    feedback: Var
    if regulator_feedback:
        tf2: Var = control.parameter('TF2',p.tf2)
        feedback = control.lag('FeedbackPu',rate,tf2,p.tf2,Const(0.0))
    elif kind == DcExciterKind.BRUSHLESS:
        tf2 = control.parameter('TF2',p.tf2)
        tf3: Var = control.parameter('TF3',p.tf3)
        # Disabling the second lag also disables its numerator, irrespective of
        # the stored lead setting; it never creates an improper differentiator.
        feedback = control.lead_lag('FeedbackPu',rate,tf3,tf2,0.0 if p.tf2 == 0 else p.tf3,p.tf2,Const(0.0))
    else:
        feedback = rate
    error: Expr = reference+supplementary-measured-feedback
    if gated:
        pass
    else:
        error = error+underexcitation
    if maximum_input is not None and maximum_location == RotatingLimiterLocation.SUMMATION:
        error = error+maximum_input
    else:
        pass
    lead: Var
    if kind in (DcExciterKind.TYPE1,DcExciterKind.TYPE2,DcExciterKind.BRUSHLESS,DcExciterKind.LIMITED_TYPE1):
        lead = control.algebraic('LeadPu',error,initial_demand)
    else:
        lead = control.lead_lag('LeadPu',error,tc,tb,p.tc,p.tb,initial_demand)
    demand: Expr = sym.max(lead,underexcitation) if gated else lead
    minimum_gate: Var | None = None
    if bounded_field:
        minimum_gate = control.algebraic('MinimumGatePu',demand,initial_demand)
        demand = sym.min(minimum_gate,maximum_input) if maximum_input is not None and maximum_location == RotatingLimiterLocation.TAKEOVER_GATE else minimum_gate
    else:
        pass
    scaled: bool = kind in (DcExciterKind.DC2,DcExciterKind.DC2A,DcExciterKind.BOUNDED_TERMINAL_SUPPLY)
    lower_limit: Expr = vmin*terminal if scaled else vmin
    upper_limit: Expr = vmax*terminal if scaled else vmax
    regulator_state: Var = control.lag('RegulatorStatePu',ka*demand,ta,p.ta,initial_regulator,
        lower_limit,upper_limit)
    # Network events can move a voltage-dependent bound across a continuous
    # state instantly. The bridge must respect the new capability immediately.
    regulator: Var = control.algebraic('RegulatorPu',
        sym.hard_sat(regulator_state,lower_limit,upper_limit),initial_regulator)
    if regulator_feedback or kind in (DcExciterKind.TYPE2A,DcExciterKind.BRUSHLESS):
        # Feedback senses the bounded regulator for type 2, and the excitation
        # machine's field-current equivalent for type 2A.
        control.block.algebraic_vars.append(feedback_source)
        control.block.algebraic_eqs.append(feedback_source-(regulator if regulator_feedback else ke*field+loss))
        control.block.init_eqs[feedback_source] = initial_regulator
    else:
        pass
    derivative: Expr = (regulator-ke*field_voltage-loss)/te
    if kind in (DcExciterKind.DC1A,DcExciterKind.COMPENSATED_TYPE2,DcExciterKind.TYPE2A,DcExciterKind.BRUSHLESS):
        # This field circuit has a lower stop only, not a symmetric saturation.
        derivative = (Const(1.0)-(Const(1.0)-sym.heaviside(field))*sym.heaviside(-derivative))*derivative
    else:
        pass
    if bounded_field:
        field_lower: Var = control.parameter('VEMIN',p.field_min)
        field_upper: Var = control.parameter('VEMAX',p.field_max)
        control.differential(field,derivative,initial_field,field_lower,field_upper)
    else:
        control.differential(field,derivative,initial_field)
    outputs: tuple[Var,...] = (field_voltage,lead,minimum_gate) if minimum_gate is not None else (field_voltage,lead)
    return control.finish(outputs,'Field-controlled rotating exciter with quadratic saturation and rate feedback')
