# SPDX-License-Identifier: MPL-2.0
"""Terminal-fed static excitation with selectable limiter and stabilizing-signal insertion points."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class StaticMinimumExcitationLocation(Enum):
    """Physical insertion point of the minimum-excitation controller."""
    ERROR_SUM = 1
    INPUT_GATE = 2
    OUTPUT_GATE = 3


class StaticMaximumExcitationLocation(Enum):
    """Physical insertion point of the maximum-excitation controller."""
    ERROR_SUM = 1
    INPUT_GATE = 2
    OUTPUT_GATE = 3


class StaticStabilizerLocation(Enum):
    """Physical summation point of the supplementary stabilizing voltage."""
    ERROR_SUM = 1
    REGULATOR_OUTPUT = 2


class TerminalFedExciterParameters:
    """Physical sensing, dual phase compensation, regulator and field-capability coefficients."""
    __slots__ = ('tr','vi_max','vi_min','tc','tb','tc1','tb1','ka','ta','va_max','va_min',
                 'vr_max','vr_min','kc','kf','tf','klr','ilr','minimum_location','stabilizer_location')

    def __init__(self, tr: float = .02, vi_max: float = .5, vi_min: float = -.5,
                 tc: float = .05, tb: float = .2, tc1: float = .03, tb1: float = .1,
                 ka: float = 20., ta: float = .05, va_max: float = 5., va_min: float = -5.,
                 vr_max: float = 5., vr_min: float = -5., kc: float = .1,
                 kf: float = .05, tf: float = 1., klr: float = 1., ilr: float = 2.,
                 minimum_location: StaticMinimumExcitationLocation = StaticMinimumExcitationLocation.ERROR_SUM,
                 stabilizer_location: StaticStabilizerLocation = StaticStabilizerLocation.ERROR_SUM) -> None:
        """Store the physical stages and explicit signal selections.

        :param tr: Nonnegative sensed-voltage lag in seconds.
        :param vi_max: Upper voltage-error limit.
        :param vi_min: Lower voltage-error limit.
        :param tc: First compensation lead in seconds.
        :param tb: First compensation lag in seconds.
        :param tc1: Second compensation lead in seconds.
        :param tb1: Second compensation lag in seconds.
        :param ka: Positive regulator gain.
        :param ta: Nonnegative regulator lag in seconds.
        :param va_max: Upper non-windup regulator limit.
        :param va_min: Lower non-windup regulator limit.
        :param vr_max: Upper field capability per unit terminal voltage before current loading.
        :param vr_min: Lower field capability per unit terminal voltage.
        :param kc: Nonnegative field-current commutation drop coefficient.
        :param kf: Nonnegative delivered-field rate-feedback numerator.
        :param tf: Positive field-rate feedback filter time in seconds.
        :param klr: Nonnegative excess-field-current limiter gain.
        :param ilr: Nonnegative field-current limiter pickup.
        :param minimum_location: Additive, pre-compensation gate or post-regulator gate.
        :param stabilizer_location: Voltage-error or post-regulator summation.
        """
        self.tr: float = tr
        self.vi_max: float = vi_max
        self.vi_min: float = vi_min
        self.tc: float = tc
        self.tb: float = tb
        self.tc1: float = tc1
        self.tb1: float = tb1
        self.ka: float = ka
        self.ta: float = ta
        self.va_max: float = va_max
        self.va_min: float = va_min
        self.vr_max: float = vr_max
        self.vr_min: float = vr_min
        self.kc: float = kc
        self.kf: float = kf
        self.tf: float = tf
        self.klr: float = klr
        self.ilr: float = ilr
        self.minimum_location: StaticMinimumExcitationLocation = minimum_location
        self.stabilizer_location: StaticStabilizerLocation = stabilizer_location


def build_esst1a_template(vf: VarFactory, name: str | None = None,
                          parameters: TerminalFedExciterParameters | None = None,
                          maximum_location: StaticMaximumExcitationLocation | None = None) -> RmsModelTemplate:
    """Build terminal-fed static excitation with explicit control-signal topology.

    Filtered compensated voltage opposes reference and selected additive signals.
    Delivered-field rate feedback is subtracted before voltage-error clipping.
    Two independent phase compensators drive a bounded non-windup regulator.
    A proportional excess-field-current limiter subtracts
    ``KLR*max(Ifd-ILR,0)`` after that regulator. Supplementary stabilization acts
    either at the error sum or at the regulator-output sum. Minimum excitation
    acts additively at the error sum, through a high-value gate after error
    clipping, or through a high-value gate after the regulator-output sum.
    Maximum excitation uses a final low-value gate before field capability.

    Delivered field voltage has terminal-dependent capabilities
    ``VT*VRMIN`` and ``VT*VRMAX-KC*Ifd``. The current-dependent upper capability is applied last if
    severe current loading crosses those bounds; that explicit numerical
    convention does not imply an externally verified limiter priority. There is no rotating field
    integrator. The washout senses actual delivered excitation after every gate
    and capability limit, so voltage collapse and current loading feed back into
    the control loop. Regulator memory keeps its own fixed limits.

    Seven inputs are compensated voltage, reference voltage, supplementary
    voltage, minimum-excitation voltage, actual terminal-voltage magnitude,
    normalized field current and maximum-excitation voltage. The first output
    is field voltage. Three inspection/bypass outputs expose clipped error,
    the pre-minimum-gate output sum and the pre-maximum-gate demand. An absent
    gated limiter connects its input to the corresponding bypass output,
    providing an exact identity without artificial capability constants.

    Initialization balances field voltage, current-limiter forcing and the
    chosen auxiliary insertion points. Initial field current and auxiliary
    biases are frozen operating-point parameters, not live control feedback.
    With positive lags, five states represent voltage sensing, two phase
    compensators, regulator and field-feedback memory. Zero permitted lags
    become exact algebraic stages; the washout time remains positive. Voltages
    and current use their connected per-unit bases, with times in seconds.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical stage coefficients and explicit topology selections.
    :param maximum_location: Optional selected maximum-limiter insertion; None preserves the original output-gate contract.
    :return: Native terminal-fed excitation controller.
    :raises ValueError: Invalid coefficient domains, improper compensation or selections.
    """
    p: TerminalFedExciterParameters = TerminalFedExciterParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.tr,p.vi_max,p.vi_min,p.tc,p.tb,p.tc1,p.tb1,
        p.ka,p.ta,p.va_max,p.va_min,p.vr_max,p.vr_min,p.kc,p.kf,p.tf,p.klr,p.ilr)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Terminal-fed excitation coefficients must be finite')
    elif min(p.ka,p.tf) <= 0 or min(p.tr,p.tc,p.tb,p.tc1,p.tb1,p.ta,p.kc,p.kf,p.klr,p.ilr) < 0:
        raise ValueError('Terminal-fed excitation gains and times have invalid domains')
    elif p.vi_max <= p.vi_min or p.va_max <= p.va_min or p.vr_max <= p.vr_min:
        raise ValueError('Terminal-fed excitation capabilities must be ordered')
    elif (p.tb == 0 and p.tc != 0) or (p.tb1 == 0 and p.tc1 != 0):
        raise ValueError('An instantaneous compensator requires zero lead')
    elif not isinstance(p.minimum_location,StaticMinimumExcitationLocation) or not isinstance(p.stabilizer_location,StaticStabilizerLocation):
        raise ValueError('Static excitation requires explicit physical insertion selections')
    else:
        pass
    if maximum_location is not None and not isinstance(maximum_location,StaticMaximumExcitationLocation):
        raise ValueError('Static excitation requires an explicit maximum-limiter selection')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'ESST1A' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    vi_upper: Var = c.parameter('VIMAX',p.vi_max)
    vi_lower: Var = c.parameter('VIMIN',p.vi_min)
    tc: Var = c.parameter('TC',p.tc)
    tb: Var = c.parameter('TB',p.tb)
    tc1: Var = c.parameter('TC1',p.tc1)
    tb1: Var = c.parameter('TB1',p.tb1)
    ka: Var = c.parameter('KA',p.ka)
    ta: Var = c.parameter('TA',p.ta)
    va_upper: Var = c.parameter('VAMAX',p.va_max)
    va_lower: Var = c.parameter('VAMIN',p.va_min)
    vr_upper: Var = c.parameter('VRMAX',p.vr_max)
    vr_lower: Var = c.parameter('VRMIN',p.vr_min)
    kc: Var = c.parameter('KC',p.kc)
    kf: Var = c.parameter('KF',p.kf)
    tf: Var = c.parameter('TF',p.tf)
    klr: Var = c.parameter('KLR',p.klr)
    ilr: Var = c.parameter('ILR',p.ilr)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    current0: Var = c.parameter('Ifd0Pu',1.)
    supplement0: Var = c.parameter('Vs0Pu',0.)
    minimum0: Var = c.parameter('Uel0Pu',0.)
    maximum0: Var | None = c.parameter('Oel0Pu',0.) if maximum_location is not None else None
    maximum_at_error: bool = maximum_location == StaticMaximumExcitationLocation.ERROR_SUM
    supplement_at_error: bool = p.stabilizer_location == StaticStabilizerLocation.ERROR_SUM
    minimum_at_error: bool = p.minimum_location == StaticMinimumExcitationLocation.ERROR_SUM
    current_limit0: Expr = klr*sym.max(current0-ilr,Const(0.))
    regulator0: Expr = field0+current_limit0-(Const(0.) if supplement_at_error else supplement0)
    error0: Expr = regulator0/ka
    reference0: Expr = voltage0+error0-(supplement0 if supplement_at_error else Const(0.))-(minimum0 if minimum_at_error else Const(0.))
    if maximum0 is not None and maximum_at_error:
        reference0 = reference0-maximum0
    else:
        pass
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',reference0)
    supplementary: Var = c.input('VsPu',Const(0.))
    minimum: Var = c.input('UelPu',Const(0.) if minimum_at_error else (error0 if p.minimum_location == StaticMinimumExcitationLocation.INPUT_GATE else field0))
    terminal: Var = c.input('VtPu',voltage0)
    current: Var = c.input('IfdPu',current0)
    maximum: Var = c.input('OelPu',maximum0 if maximum_at_error and maximum0 is not None else (error0 if maximum_location == StaticMaximumExcitationLocation.INPUT_GATE else field0))
    field: Var = vf.add_var('EfdPu_'+c.name)
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    feedback: Var = c.washout('FeedbackPu',field,tf,p.tf,kf/tf,field0)
    raw_error: Expr = reference-measured-feedback+(supplementary if supplement_at_error else Const(0.))+(minimum if minimum_at_error else Const(0.))
    if maximum_at_error:
        raw_error = raw_error+maximum
    else:
        pass
    clipped: Var = c.algebraic('ClippedErrorPu',sym.hard_sat(raw_error,vi_lower,vi_upper),error0)
    error: Expr = sym.max(clipped,minimum) if p.minimum_location == StaticMinimumExcitationLocation.INPUT_GATE else clipped
    pre_maximum_input: Var | None = c.algebraic('PreMaximumInputPu',error,error0) if maximum_location is not None else None
    if maximum_location == StaticMaximumExcitationLocation.INPUT_GATE:
        error = sym.min(error,maximum)
    else:
        pass
    lead: Var = c.lead_lag('FirstLeadPu',error,tc,tb,p.tc,p.tb,error0)
    second: Var = c.lead_lag('SecondLeadPu',lead,tc1,tb1,p.tc1,p.tb1,error0)
    regulator: Var = c.lag('RegulatorPu',ka*second,ta,p.ta,regulator0,va_lower,va_upper)
    current_limit: Expr = klr*sym.max(current-ilr,Const(0.))
    summed: Var = c.algebraic('PreMinimumPu',regulator-current_limit+(Const(0.) if supplement_at_error else supplementary),field0)
    selected: Var = c.algebraic('PreMaximumPu',sym.max(summed,minimum) if p.minimum_location == StaticMinimumExcitationLocation.OUTPUT_GATE else summed,field0)
    # Apply the commutation-dependent ceiling after the terminal-fed floor.
    maximum_selected: Expr = sym.min(selected,maximum) if maximum_location is None or maximum_location == StaticMaximumExcitationLocation.OUTPUT_GATE else selected
    delivered: Expr = sym.min(terminal*vr_upper-kc*current,sym.max(terminal*vr_lower,maximum_selected))
    c.block.algebraic_vars.append(field)
    c.block.algebraic_eqs.append(field-delivered)
    c.block.init_eqs[field] = field0
    outputs: tuple[Var,...] = (field,clipped,summed,selected,pre_maximum_input) if pre_maximum_input is not None else (field,clipped,summed,selected)
    return c.finish(outputs,'Terminal-fed excitation with selectable minimum/stabilizer gates and field-current limiting')
