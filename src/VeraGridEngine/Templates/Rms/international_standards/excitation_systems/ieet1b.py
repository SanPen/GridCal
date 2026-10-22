# SPDX-License-Identifier: MPL-2.0
"""Biased rotating excitation with clipped voltage error and selectable rate feedback."""
from __future__ import annotations

from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import _quadratic_saturation_coefficients
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class RotatingRateFeedbackSignal(Enum):
    """Physical voltage sensed by the excitation rate-feedback filter."""
    REGULATOR_OUTPUT = 0
    FIELD_VOLTAGE = 1


def build_ieet1b_template(vf: VarFactory, name: str | None = None,
                         parameters: DcExciterParameters | None = None,
                         second_time: float = .05, error_max: float = .5, error_min: float = -.5,
                         compensation: float = 0., feedback_signal: RotatingRateFeedbackSignal = RotatingRateFeedbackSignal.REGULATOR_OUTPUT) -> RmsModelTemplate:
    """Build a biased two-stage voltage regulator driving a saturated rotating field.

    Stator-current magnitude times compensation reactance adds to sensed
    voltage before its transducer. Reference error is clipped independently
    before additive supplementary/minimum-excitation voltage and frozen bias.
    A rate-feedback filter subtracts from that sum. The first amplifier has
    gain KA, time TA1 and independent non-windup limits; an unbounded unity-gain
    TA2 lag follows. Field forcing integrates its output minus resistance and
    quadratic magnetic saturation losses. There is no invented field-voltage
    lower stop or terminal-supply multiplier.

    Rate feedback senses either the second regulator's output or delivered
    field voltage, according to its explicit physical selector. It never senses
    net accelerating field forcing. The bias is initial regulator forcing
    divided by KA and remains frozen thereafter. Initial reference includes
    actual compensated sensing and subtracts steady auxiliary voltage before
    error clipping, preserving that bias's declared initialization rule.

    Six inputs are compensated voltage, reference, supplementary voltage,
    additive minimum-excitation voltage, unused terminal supply and actual
    stator-current magnitude on the connected machine base. Outputs are field
    voltage and second-stage regulator output. Frozen field, current-magnitude
    and auxiliary operating-point quantities determine all initial states.
    With positive sensing/amplifier lags there are five states; permitted zero
    lags reduce exactly. Active rate and field times are positive. Voltages and
    currents are per unit, reactance is per unit and times are seconds. Only
    sensing, first amplifier, field, saturation and rate coefficients are used
    from the shared parameter object. Calibration selectors are not substituted
    for explicitly supplied native resistance and regulator capability.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Physical field, sensing, first-amplifier and rate settings.
    :param second_time: Nonnegative second regulator lag, seconds.
    :param error_max: Upper voltage-error capability before auxiliary addition.
    :param error_min: Lower voltage-error capability before auxiliary addition.
    :param compensation: Nonnegative current-magnitude compensation reactance.
    :param feedback_signal: Second regulator voltage or delivered field voltage.
    :return: Native six-input rotating excitation controller.
    :raises ValueError: Invalid physical settings, undefined calibration or selector.
    """
    p: DcExciterParameters = DcExciterParameters() if parameters is None else parameters
    if min(p.tr,p.ta,second_time,p.kf,compensation,p.e1,p.se1,p.e2,p.se2) < 0 or min(p.ka,p.te,p.tf) <= 0:
        raise ValueError('Biased excitation coefficients have invalid physical domains')
    elif p.ke is None or p.vrmax is None:
        raise ValueError('Biased excitation requires explicit field resistance and amplifier capability')
    elif p.vrmax <= p.vrmin or error_max <= error_min:
        raise ValueError('Biased excitation capabilities must be ordered')
    elif (p.se1 != 0 or p.se2 != 0) and (p.e1 <= 0 or p.e2 <= p.e1 or p.e2*p.se2 <= p.e1*p.se1):
        raise ValueError('Enabled saturation requires increasing voltage and loss samples')
    elif not isinstance(feedback_signal,RotatingRateFeedbackSignal):
        raise ValueError('Biased excitation requires an explicit rate-feedback signal')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'IEET1B' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    ka: Var = c.parameter('KA',p.ka)
    ta1: Var = c.parameter('TA1',p.ta)
    ta2: Var = c.parameter('TA2',second_time)
    upper: Var = c.parameter('VRMAX',p.vrmax)
    lower: Var = c.parameter('VRMIN',p.vrmin)
    ke: Var = c.parameter('KE',p.ke)
    te: Var = c.parameter('TE',p.te)
    kf: Var = c.parameter('KF1',p.kf)
    tf: Var = c.parameter('TF1',p.tf)
    error_upper: Var = c.parameter('VSMAX',error_max)
    error_lower: Var = c.parameter('VSMIN',error_min)
    xe: Var = c.parameter('XE',compensation)
    field0: Var = c.parameter('Efd0Pu',p.initial_field_voltage)
    voltage0: Var = c.parameter('Us0Pu',1.)
    magnitude0: Var = c.parameter('Imag0Pu',0.)
    auxiliary0: Var = c.parameter('Aux0Pu',0.)
    field: Var = vf.add_var('EfdPu_'+c.name)
    regulator_output: Var = vf.add_var('SecondRegulatorPu_'+c.name)
    loss: Expr
    loss0: Expr
    if p.se1 == 0 and p.se2 == 0:
        loss = Const(0.)
        loss0 = Const(0.)
    else:
        e1: Var = c.parameter('E1',p.e1)
        se1: Var = c.parameter('SE1',p.se1)
        e2: Var = c.parameter('E2',p.e2)
        se2: Var = c.parameter('SE2',p.se2)
        threshold: Expr
        saturation_gain: Expr
        threshold,saturation_gain = _quadratic_saturation_coefficients(e1,se1,e2,se2)
        loss = saturation_gain*sym.max(field-threshold,Const(0.))**2
        loss0 = saturation_gain*sym.max(field0-threshold,Const(0.))**2
    regulator0: Expr = ke*field0+loss0
    bias: Var = vf.add_var('BiasPu_'+c.name)
    c.block.event_dict[bias] = Const(None)
    c.block.init_eqs[bias] = regulator0/ka
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0+xe*magnitude0-auxiliary0)
    supplement: Var = c.input('VsPu',Const(0.))
    minimum: Var = c.input('UelPu',auxiliary0)
    c.input('VtPu',voltage0)
    magnitude: Var = c.input('ImagPu',magnitude0)
    measured0: Expr = voltage0+xe*magnitude0
    measured: Var = c.lag('MeasuredPu',sensed+xe*magnitude,tr,p.tr,measured0)
    rate_source: Var = regulator_output if feedback_signal == RotatingRateFeedbackSignal.REGULATOR_OUTPUT else field
    rate_initial: Expr = regulator0 if feedback_signal == RotatingRateFeedbackSignal.REGULATOR_OUTPUT else field0
    rate: Var = c.washout('FeedbackPu',rate_source,tf,p.tf,kf/tf,rate_initial)
    clipped: Var = c.algebraic('ClippedErrorPu',sym.hard_sat(reference-measured,error_lower,error_upper),-auxiliary0)
    demand: Expr = clipped+bias+supplement+minimum-rate
    regulator: Var = c.lag('FirstRegulatorPu',ka*demand,ta1,p.ta,regulator0,lower,upper)
    c.lag('SecondRegulatorPu',regulator,ta2,second_time,regulator0,output=regulator_output)
    c.differential(field,(regulator_output-ke*field-loss)/te,field0)
    return c.finish((field,regulator_output),'Biased rotating excitation with selected rate feedback and clipped voltage error')
