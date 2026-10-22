# SPDX-License-Identifier: MPL-2.0
"""Static excitation with output feedback, reference takeover and moving capability."""
from __future__ import annotations

from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class ExcitationLimiterLocation(Enum):
    """Signed reference addition, reference takeover or final forcing takeover."""
    REFERENCE_SUM = 1
    REFERENCE_GATE = 2
    OUTPUT_GATE = 3


class ExcitationBridgeDynamics(Enum):
    """Instantaneous bridge or a bounded firing-control lag."""
    INSTANTANEOUS = 1
    FIRING_LAG = 2


class SelfFeedbackExciterParameters:
    """Voltage measurement, regulator, excitation-feedback and bridge coefficients."""
    __slots__ = ('tr','tg','tf','vmax','vmin','kpa','vrmax','vrmin','kh','kl','tc','tb','kia','tia','ta','minimum_location','maximum_location')

    def __init__(self, tr: float = .02, tg: float = .1, tf: float = .2,
                 vmax: float = 1.2, vmin: float = .8, kpa: float = 20.,
                 vrmax: float = 5., vrmin: float = -5., kh: float = 1., kl: float = 1.,
                 tc: float = .1, tb: float = .2, kia: float = 1., tia: float = .5, ta: float = .02,
                 minimum_location: ExcitationLimiterLocation = ExcitationLimiterLocation.REFERENCE_SUM,
                 maximum_location: ExcitationLimiterLocation = ExcitationLimiterLocation.REFERENCE_SUM) -> None:
        """Store explicit physical coefficients and signal selections.

        :param tr: Nonnegative sensing lag, seconds.
        :param tg: Nonnegative measurement lead time, seconds.
        :param tf: Nonnegative measurement lag time, seconds.
        :param vmax: Upper selected-reference capability.
        :param vmin: Lower selected-reference capability.
        :param kpa: Positive proportional regulator gain.
        :param vrmax: Upper terminal-scaled field capability.
        :param vrmin: Lower terminal-scaled field capability.
        :param kh: Nonnegative lower-limit output-feedback coefficient.
        :param kl: Nonnegative upper-limit output-feedback coefficient.
        :param tc: Nonnegative regulator lead time, seconds.
        :param tb: Nonnegative regulator lag time, seconds.
        :param kia: Positive delivered-field feedback gain.
        :param tia: Positive delivered-field feedback lag, seconds.
        :param ta: Positive firing-control lag when present, seconds.
        :param minimum_location: Minimum-excitation insertion.
        :param maximum_location: Maximum-excitation insertion.
        """
        self.tr: float = tr
        self.tg: float = tg
        self.tf: float = tf
        self.vmax: float = vmax
        self.vmin: float = vmin
        self.kpa: float = kpa
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.kh: float = kh
        self.kl: float = kl
        self.tc: float = tc
        self.tb: float = tb
        self.kia: float = kia
        self.tia: float = tia
        self.ta: float = ta
        self.minimum_location: ExcitationLimiterLocation = minimum_location
        self.maximum_location: ExcitationLimiterLocation = maximum_location


def build_self_feedback_exciter(vf: VarFactory, name: str, bridge: ExcitationBridgeDynamics,
                                parameters: SelfFeedbackExciterParameters | None = None) -> RmsModelTemplate:
    """Assemble reference gates, moving regulator limits and delivered-field feedback.

    :param vf: Shared native symbolic factory.
    :param name: Unique controller label.
    :param bridge: Explicit firing-control realization.
    :param parameters: Physical coefficients or construction defaults.
    :return: Six-input controller with field and four pre-gate inspection outputs.
    :raises ValueError: Invalid coefficients, improper phase compensation or selections.
    """
    p: SelfFeedbackExciterParameters = SelfFeedbackExciterParameters() if parameters is None else parameters
    if min(p.tr,p.tg,p.tf,p.kh,p.kl,p.tc,p.tb) < 0 or min(p.kpa,p.kia,p.tia) <= 0:
        raise ValueError('Self-feedback excitation gains and times have invalid domains')
    elif p.vmax <= p.vmin or p.vrmax <= p.vrmin:
        raise ValueError('Self-feedback excitation capabilities must be ordered')
    elif bridge == ExcitationBridgeDynamics.FIRING_LAG and p.ta <= 0:
        raise ValueError('A firing-control bridge requires positive lag time')
    elif not isinstance(p.minimum_location,ExcitationLimiterLocation) or not isinstance(p.maximum_location,ExcitationLimiterLocation):
        raise ValueError('Self-feedback excitation requires explicit limiter selections')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,name)
    tr: Var = c.parameter('TR',p.tr)
    tg: Var = c.parameter('TG',p.tg)
    tf: Var = c.parameter('TF',p.tf)
    vmax: Var = c.parameter('VMAX',p.vmax)
    vmin: Var = c.parameter('VMIN',p.vmin)
    kpa: Var = c.parameter('KPA',p.kpa)
    vrmax: Var = c.parameter('VRMAX',p.vrmax)
    vrmin: Var = c.parameter('VRMIN',p.vrmin)
    kh: Var = c.parameter('KH',p.kh)
    kl: Var = c.parameter('KL',p.kl)
    tc: Var = c.parameter('TC',p.tc)
    tb: Var = c.parameter('TB',p.tb)
    kia: Var = c.parameter('KIA',p.kia)
    tia: Var = c.parameter('TIA',p.tia)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    supplement0: Var = c.parameter('Vs0Pu',0.)
    minimum0: Var = c.parameter('Uel0Pu',0.)
    maximum0: Var = c.parameter('Oel0Pu',0.)
    feedback0: Expr = kia*field0
    regulator0: Expr = field0-feedback0
    selected_reference0: Expr = voltage0+regulator0/kpa-supplement0
    reference0: Expr = selected_reference0-(minimum0 if p.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))-(maximum0 if p.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',reference0)
    supplement: Var = c.input('VsPu',supplement0)
    minimum: Var = c.input('UelPu',minimum0 if p.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM else (selected_reference0 if p.minimum_location == ExcitationLimiterLocation.REFERENCE_GATE else field0))
    terminal: Var = c.input('VtPu',voltage0)
    maximum: Var = c.input('OelPu',maximum0 if p.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM else (selected_reference0 if p.maximum_location == ExcitationLimiterLocation.REFERENCE_GATE else field0))
    field: Var = vf.add_var('EfdPu_'+name)
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    shaped: Var = c.lead_lag('MeasuredShapePu',measured,tg,tf,p.tg,p.tf,voltage0)
    feedback: Var = c.lag('FieldFeedbackPu',kia*field,tia,p.tia,feedback0)
    summed: Expr = reference+(minimum if p.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))+(maximum if p.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))
    pre_maximum_reference: Var = c.algebraic('PreMaximumReferencePu',summed,selected_reference0)
    pre_minimum_reference: Var = c.algebraic('PreMinimumReferencePu',sym.min(summed,maximum) if p.maximum_location == ExcitationLimiterLocation.REFERENCE_GATE else summed,selected_reference0)
    selected_reference: Expr = sym.max(pre_minimum_reference,minimum) if p.minimum_location == ExcitationLimiterLocation.REFERENCE_GATE else pre_minimum_reference
    selected_reference = sym.hard_sat(selected_reference,vmin,vmax)
    error: Expr = selected_reference+supplement-shaped
    # Capability feedback uses two independent coefficients before phase compensation.
    lower: Expr = terminal*vrmin-kh*feedback
    upper: Expr = terminal*vrmax-kl*feedback
    regulator: Var = c.algebraic('LimitedRegulatorPu',sym.min(upper,sym.max(lower,kpa*error)),regulator0)
    phase: Var = c.lead_lag('RegulatorShapePu',regulator,tc,tb,p.tc,p.tb,regulator0)
    pre_maximum_output: Var = c.algebraic('PreMaximumOutputPu',phase+feedback,field0)
    pre_minimum_output: Var = c.algebraic('PreMinimumOutputPu',sym.min(pre_maximum_output,maximum) if p.maximum_location == ExcitationLimiterLocation.OUTPUT_GATE else pre_maximum_output,field0)
    demand: Expr = sym.max(pre_minimum_output,minimum) if p.minimum_location == ExcitationLimiterLocation.OUTPUT_GATE else pre_minimum_output
    if bridge == ExcitationBridgeDynamics.FIRING_LAG:
        ta: Var = c.parameter('TA',p.ta)
        memory: Var = c.lag('BridgeMemoryPu',demand,ta,p.ta,field0,terminal*vrmin,terminal*vrmax)
        delivered: Expr = sym.min(terminal*vrmax,sym.max(terminal*vrmin,memory))
    else:
        delivered = sym.min(terminal*vrmax,sym.max(terminal*vrmin,demand))
    c.block.algebraic_vars.append(field)
    c.block.algebraic_eqs.append(field-delivered)
    c.block.init_eqs[field] = field0
    return c.finish((field,pre_maximum_reference,pre_minimum_reference,pre_maximum_output,pre_minimum_output),
        'Static excitation with selected reference gates and delivered-field feedback')
