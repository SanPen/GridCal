# SPDX-License-Identifier: MPL-2.0
"""Continuous PID voltage regulation of a saturated rotating excitation machine."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.compound_excitation_supply import CompoundSupplyParameters, build_compound_supply
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters, RotatingLimiterLocation
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import _quadratic_saturation_coefficients
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class PidRotatingExciterKind(Enum):
    """Physical PID limiting and amplifier-supply arrangements."""

    INDEPENDENT_SUPPLY = 1
    BOUNDED_TERMINAL_SUPPLY = 2
    BOUNDED_COMPOUND_SUPPLY = 3


def build_pid_rotating_exciter(vf: VarFactory, name: str, kind: PidRotatingExciterKind,
                               parameters: DcExciterParameters | None = None,
                               kp: float = 1., ki: float = 1., kd: float = .1, td: float = .05,
                               minimum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                               maximum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                               supply_parameters: CompoundSupplyParameters | None = None) -> RmsModelTemplate:
    """Assemble parallel PID, amplifier supply and saturated rotating field stages.

    :param vf: Shared native symbolic factory.
    :param name: Unique instance label.
    :param kind: Explicit PID limiting and power-supply structure.
    :param parameters: Physical sensing, amplifier, feedback and field coefficients.
    :param kp: Proportional gain.
    :param ki: Integral gain in inverse seconds.
    :param kd: Derivative gain in seconds.
    :param td: Derivative filtering time in seconds.
    :param minimum_location: Additive or takeover minimum-excitation insertion.
    :param maximum_location: Additive or takeover maximum-excitation insertion.
    :param supply_parameters: Explicit potential circuit for compound-fed operation.
    :return: Five-, six- or nine-input native excitation controller.
    :raises ValueError: Invalid coefficients, limiter selections or undefined calibration.
    """
    p: DcExciterParameters = DcExciterParameters() if parameters is None else parameters
    label: str = name
    terminal_fed: bool = kind == PidRotatingExciterKind.BOUNDED_TERMINAL_SUPPLY
    compound_fed: bool = kind == PidRotatingExciterKind.BOUNDED_COMPOUND_SUPPLY
    bounded: bool = terminal_fed or compound_fed
    coefficients: tuple[float, ...] = (p.tr,p.ka,p.ta,p.vrmin,p.te,p.e1,p.se1,p.e2,p.se2,
        p.initial_field_voltage,kp,ki,kd,td)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('PID excitation coefficients must be finite')
    elif min(p.tr,p.ta,p.e1,p.se1,p.e2,p.se2,p.initial_field_voltage,kp,ki,kd,td) < 0 or min(p.ka,p.te) <= 0:
        raise ValueError('PID excitation gains, times and samples have invalid domains')
    elif kp == 0 and ki == 0:
        raise ValueError('A steady field requires proportional or integral regulation')
    elif kd > 0 and td <= 0:
        raise ValueError('Enabled derivative regulation requires a positive filter time')
    elif p.ke is None or p.vrmax is None:
        raise ValueError('Explicit field resistance and regulator capability are required')
    elif not math.isfinite(p.ke) or not math.isfinite(p.vrmax) or p.vrmax <= p.vrmin:
        raise ValueError('Field resistance must be finite and regulator capabilities ordered')
    elif (p.se1 != 0 or p.se2 != 0) and (p.e1 <= 0 or p.e2 <= p.e1 or p.e2*p.se2 <= p.e1*p.se1):
        raise ValueError('Enabled saturation requires increasing voltage and loss samples')
    else:
        pass
    if bounded and not all(math.isfinite(value) for value in (p.kf,p.tf,p.field_min)):
        raise ValueError('Bounded rotating feedback and field stop must be finite')
    elif bounded and (kp <= 0 or min(p.kf,p.tf) < 0 or p.kf > 0 and p.tf == 0 or
            not isinstance(minimum_location,RotatingLimiterLocation) or not isinstance(maximum_location,RotatingLimiterLocation)):
        raise ValueError('Terminal-fed PID requires positive proportional gain and valid feedback/limiter settings')
    elif compound_fed and supply_parameters is None:
        raise ValueError('Compound-fed rotating excitation requires an explicit supply circuit')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,label)
    tr: Var = c.parameter('TR',p.tr)
    ka: Var = c.parameter('KA',p.ka)
    ta: Var = c.parameter('TA',p.ta)
    te: Var = c.parameter('TE',p.te)
    ke: Var = c.parameter('KE',p.ke)
    upper: Var = c.parameter('VRMAX',p.vrmax)
    lower: Var = c.parameter('VRMIN',p.vrmin)
    proportional: Var = c.parameter('KPR' if compound_fed else 'KP',kp)
    integral: Var = c.parameter('KIR' if compound_fed else 'KI',ki)
    derivative_gain: Var = c.parameter('KDR' if compound_fed else 'KD',kd)
    derivative_time: Var = c.parameter('TDR' if compound_fed else 'TD',td)
    field0: Var = c.parameter('Efd0Pu',p.initial_field_voltage)
    voltage0: Var = c.parameter('Us0Pu',1.)
    terminal0: Var | None = c.parameter('Vt0Pu',1.) if terminal_fed else None
    field: Var = vf.add_var('EfdPu_'+label)
    loss: Expr
    loss0: Expr
    if p.se1 == 0 and p.se2 == 0:
        loss = Const(0.)
        loss0 = Const(0.)
    else:
        e1: Var = c.parameter('E1',p.e1)
        s1: Var = c.parameter('SE1',p.se1)
        e2: Var = c.parameter('E2',p.e2)
        s2: Var = c.parameter('SE2',p.se2)
        threshold: Expr
        gain: Expr
        threshold,gain = _quadratic_saturation_coefficients(e1,s1,e2,s2)
        loss = gain*sym.max(field-threshold,Const(0.))**2
        loss0 = gain*sym.max(field0-threshold,Const(0.))**2
    regulator0: Expr = ke*field0+loss0
    supply: Expr = Const(1.)
    vr: Var | None = None
    vi: Var | None = None
    ir: Var | None = None
    ii: Var | None = None
    if compound_fed:
        # Allocate phasors here, then publish them after the common voltage-reference ports below.
        vr = vf.add_var('VrPu_'+label)
        vi = vf.add_var('ViPu_'+label)
        ir = vf.add_var('IrPu_'+label)
        ii = vf.add_var('IiPu_'+label)
        assert supply_parameters is not None
        equivalent: Var = c.algebraic('CurrentEquivalentPu',ke*field+loss,regulator0)
        supply = build_compound_supply(c,vr,vi,ir,ii,equivalent,supply_parameters)
    else:
        pass
    demand0: Expr = regulator0/(ka*terminal0) if terminal0 is not None else regulator0/(ka*supply)
    error0: Expr = Const(0.) if ki > 0 else demand0/proportional
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0+error0)
    supplementary: Var = c.input('VsPu',Const(0.))
    if compound_fed:
        assert vr is not None and vi is not None and ir is not None and ii is not None
        for port,initial in ((vr,Const(1.)),(vi,Const(0.)),(ir,Const(.5)),(ii,Const(0.))):
            c.block.in_vars.append(port)
            c.block.init_eqs[port] = initial
    else:
        pass
    gated_minimum: bool = bounded and minimum_location == RotatingLimiterLocation.TAKEOVER_GATE
    minimum: Var = c.input('UelPu',demand0 if gated_minimum else Const(0.))
    terminal: Var | None = None if compound_fed else c.input('VtPu',terminal0 if terminal0 is not None else voltage0)
    maximum: Var | None = c.input('OelPu',demand0 if maximum_location == RotatingLimiterLocation.TAKEOVER_GATE else Const(0.)) if bounded else None
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    feedback: Expr = Const(0.)
    if bounded:
        feedback_time: Var = c.parameter('TF',p.tf)
        feedback_gain: Var = c.parameter('KF',p.kf)
        feedback = c.washout('FeedbackPu',field,feedback_time,p.tf,feedback_gain/feedback_time,field0) if p.kf > 0 else Const(0.)
    else:
        pass
    error_expression: Expr = reference+supplementary-measured-feedback
    if not gated_minimum:
        error_expression = error_expression+minimum
    else:
        pass
    if maximum is not None and maximum_location == RotatingLimiterLocation.SUMMATION:
        error_expression = error_expression-maximum if compound_fed else error_expression+maximum
    else:
        pass
    error: Var = c.algebraic('ErrorPu',error_expression,error0)
    derivative_output: Var
    if kd > 0:
        derivative_output = c.washout('DerivativePu',error,derivative_time,td,derivative_gain/derivative_time,error0)
    else:
        derivative_output = c.algebraic('DerivativePu',Const(0.),Const(0.))
    nonintegral: Expr = proportional*error+derivative_output
    integral_output: Var
    if ki > 0:
        if bounded:
            # Stop only integral motion that drives the total PID further outside its bounds.
            integral_output = c.differential(vf.add_var('IntegralPu_'+label),integral*error,demand0,
                lower/ka-nonintegral,upper/ka-nonintegral)
        else:
            integral_output = c.differential(vf.add_var('IntegralPu_'+label),integral*error,demand0)
    else:
        integral_output = c.algebraic('IntegralPu',Const(0.),Const(0.))
    raw_demand: Expr = nonintegral+integral_output
    demand: Var = c.algebraic('DemandPu',sym.hard_sat(raw_demand,lower/ka,upper/ka) if bounded else raw_demand,demand0)
    minimum_gate: Var | None = None
    if bounded:
        minimum_gate = c.algebraic('MinimumGatePu',sym.max(demand,minimum) if gated_minimum else demand,demand0)
        selected: Expr = sym.min(minimum_gate,maximum) if maximum is not None and maximum_location == RotatingLimiterLocation.TAKEOVER_GATE else minimum_gate
        if compound_fed:
            amplifier: Var = c.lag('RegulatorPu',ka*selected,ta,p.ta,regulator0/supply,lower,upper)
            regulator: Var = c.algebraic('ForcingPu',amplifier*supply,regulator0)
        else:
            assert terminal is not None
            amplifier = c.lag('RegulatorPu',ka*terminal*selected,ta,p.ta,regulator0,terminal*lower,terminal*upper)
            regulator = c.algebraic('ForcingPu',sym.hard_sat(amplifier,terminal*lower,terminal*upper),regulator0)
    else:
        regulator = c.lag('RegulatorPu',ka*demand,ta,p.ta,regulator0,lower,upper)
    field_rate: Expr = (regulator-ke*field-loss)/te
    field_minimum: Expr = c.parameter('VEMIN',p.field_min) if bounded else Const(0.)
    # Field-memory stops suppress outward motion while always permitting recovery.
    stopped_rate: Expr = (Const(1.)-(Const(1.)-sym.heaviside(field-field_minimum))*sym.heaviside(-field_rate))*field_rate
    c.differential(field,stopped_rate,field0)
    outputs: tuple[Var,...] = (field,demand,minimum_gate) if minimum_gate is not None else (field,demand)
    return c.finish(outputs,'PID voltage regulation with saturated rotating excitation')
