# SPDX-License-Identifier: MPL-2.0
"""Static excitation with three continuously evolving bounded compensation channels."""
from __future__ import annotations

import math
from VeraGridEngine.Templates.Rms.self_feedback_exciter import ExcitationLimiterLocation
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class ParallelChannelExciterParameters:
    """Sensing, three compensation channels and terminal-dependent field capabilities."""
    __slots__ = ('tr','tc1','tb1','tc2','tb2','kr','vrmax','vrmin','t1','kc','tuc1','tub1','tuc2','tub2','toc1','tob1','toc2','tob2','minimum_location','maximum_location')

    def __init__(self, tr: float = 0.02, tc1: float = 0.1, tb1: float = 0.2, tc2: float = 0.05,
                 tb2: float = 0.1, kr: float = 20.0, vrmax: float = 5.0, vrmin: float = -5.0,
                 t1: float = 0.05, kc: float = 0.1, tuc1: float = 0.2, tub1: float = 0.3,
                 tuc2: float = 0.1, tub2: float = 0.2, toc1: float = 0.05, tob1: float = 0.15,
                 toc2: float = 0.04, tob2: float = 0.08,
                 minimum_location: ExcitationLimiterLocation = ExcitationLimiterLocation.REFERENCE_GATE,
                 maximum_location: ExcitationLimiterLocation = ExcitationLimiterLocation.REFERENCE_GATE) -> None:
        """Store independent channel times and physical field-output capabilities.

        :param minimum_location: Minimum signal summation or takeover gate.
        :param maximum_location: Maximum signal summation or takeover gate.
        :param tr: Physical TR coefficient; channel/sensing/output times are seconds.
        :param tc1: Physical TC1 coefficient; channel/sensing/output times are seconds.
        :param tb1: Physical TB1 coefficient; channel/sensing/output times are seconds.
        :param tc2: Physical TC2 coefficient; channel/sensing/output times are seconds.
        :param tb2: Physical TB2 coefficient; channel/sensing/output times are seconds.
        :param kr: Physical KR coefficient; channel/sensing/output times are seconds.
        :param vrmax: Physical VRMAX coefficient; channel/sensing/output times are seconds.
        :param vrmin: Physical VRMIN coefficient; channel/sensing/output times are seconds.
        :param t1: Physical T1 coefficient; channel/sensing/output times are seconds.
        :param kc: Physical KC coefficient; channel/sensing/output times are seconds.
        :param tuc1: Physical TUC1 coefficient; channel/sensing/output times are seconds.
        :param tub1: Physical TUB1 coefficient; channel/sensing/output times are seconds.
        :param tuc2: Physical TUC2 coefficient; channel/sensing/output times are seconds.
        :param tub2: Physical TUB2 coefficient; channel/sensing/output times are seconds.
        :param toc1: Physical TOC1 coefficient; channel/sensing/output times are seconds.
        :param tob1: Physical TOB1 coefficient; channel/sensing/output times are seconds.
        :param toc2: Physical TOC2 coefficient; channel/sensing/output times are seconds.
        :param tob2: Physical TOB2 coefficient; channel/sensing/output times are seconds.
        """
        self.minimum_location: ExcitationLimiterLocation = minimum_location
        self.maximum_location: ExcitationLimiterLocation = maximum_location
        self.tr: float = tr
        self.tc1: float = tc1
        self.tb1: float = tb1
        self.tc2: float = tc2
        self.tb2: float = tb2
        self.kr: float = kr
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.t1: float = t1
        self.kc: float = kc
        self.tuc1: float = tuc1
        self.tub1: float = tub1
        self.tuc2: float = tuc2
        self.tub2: float = tub2
        self.toc1: float = toc1
        self.tob1: float = tob1
        self.toc2: float = toc2
        self.tob2: float = tob2


def build_parallel_channel_exciter(vf: VarFactory, name: str | None = None,
                        parameters: ParallelChannelExciterParameters | None = None) -> RmsModelTemplate:
    """Build parallel-channel static excitation with explicit take-over selection.

    Each limiter independently selects signed addition at voltage error or
    takeover. Summed signals never select a dedicated channel. Reference minus
    sensed voltage and any summed biases first enter a minimum-excitation high gate
    and then a maximum-excitation low gate. Supplementary voltage adds after
    both gates. This common signal continuously drives three distinct cascades
    of two bounded lead-lags: ordinary voltage regulation, minimum-excitation
    operation and maximum-excitation operation. Inactive channels retain their
    own evolving memories; they are not frozen or collapsed into one filter.

    Each positive-lead stage tracks its clipped output through its numerator
    time, preserving non-windup recovery. A zero lead is a bounded ordinary lag;
    zero lead and lag are an exact static limiter. Each stage's bounds are
    VRMIN/KR and VRMAX/KR. Ordinary operation selects the first channel. A
    strict high-gate takeover selects the second; a strict low-gate takeover
    selects the third and has priority when both gates request takeover.
    Exact gate ties retain the upstream channel.

    Selected demand times KR is clipped separately at VRMIN/VRMAX. Field-current
    commutation subtracts KC*IFD before the final field lag. Its capability is
    terminal magnitude times VRMIN/VRMAX. A moving final output clip preserves
    immediately available terminal-dependent capability while continuous lag
    memory can recover inward after a voltage collapse.

    Seven inputs are sensed voltage, reference, supplement, field current,
    actual terminal magnitude, minimum and maximum excitation. Outputs are field
    voltage, pre-minimum demand, pre-maximum demand and the three channel outputs.
    Absent takeover limiters connect to their moving pre-gate outputs; absent
    summed signals are zero. Summed initial biases are subtracted from the
    reference. Times are seconds;
    voltage/current bases must be compatible with KC. Sensing and terminal
    magnitude remain separate when an external voltage compensator is present.

    Eight states are present with positive stage times: sensing, six channel
    memories and final field memory. All channel memories initialize to
    (EFD0+KC*IFD0)/KR. Reference includes actual supplementary bias. Positive
    KR, proper lead/lag pairs and feasible channel/output capabilities are
    required. No arbitrary large bypass threshold or limiter-activity latch
    substitutes for the actual gate comparisons.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Independent regulator, limiter-channel and field settings.
    :return: Native three-channel excitation with explicit bounded tracking stages.
    :raises ValueError: Invalid domains, improper filters or unordered capabilities.
    """
    p: ParallelChannelExciterParameters = ParallelChannelExciterParameters() if parameters is None else parameters
    times: tuple[float,...] = (p.tr,p.tc1,p.tb1,p.tc2,p.tb2,p.t1,p.tuc1,p.tub1,p.tuc2,p.tub2,p.toc1,p.tob1,p.toc2,p.tob2)
    if not all(math.isfinite(value) for value in times) or not all(math.isfinite(value) for value in (p.kr,p.vrmax,p.vrmin,p.kc)):
        raise ValueError('Parallel-channel excitation coefficients must be finite')
    elif min(times) < 0 or p.kr <= 0 or p.kc < 0 or p.vrmax <= p.vrmin:
        raise ValueError('Parallel-channel excitation requires nonnegative times/loading, positive gain and ordered limits')
    else:
        pass
    if p.minimum_location not in (ExcitationLimiterLocation.REFERENCE_SUM,ExcitationLimiterLocation.REFERENCE_GATE) or p.maximum_location not in (ExcitationLimiterLocation.REFERENCE_SUM,ExcitationLimiterLocation.REFERENCE_GATE):
        raise ValueError('Parallel-channel limiters require reference summation or reference takeover')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'ST5B' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    tc1: Var = c.parameter('TC1',p.tc1)
    tb1: Var = c.parameter('TB1',p.tb1)
    tc2: Var = c.parameter('TC2',p.tc2)
    tb2: Var = c.parameter('TB2',p.tb2)
    kr: Var = c.parameter('KR',p.kr)
    vrmax: Var = c.parameter('VRMAX',p.vrmax)
    vrmin: Var = c.parameter('VRMIN',p.vrmin)
    t1: Var = c.parameter('T1',p.t1)
    kc: Var = c.parameter('KC',p.kc)
    tuc1: Var = c.parameter('TUC1',p.tuc1)
    tub1: Var = c.parameter('TUB1',p.tub1)
    tuc2: Var = c.parameter('TUC2',p.tuc2)
    tub2: Var = c.parameter('TUB2',p.tub2)
    toc1: Var = c.parameter('TOC1',p.toc1)
    tob1: Var = c.parameter('TOB1',p.tob1)
    toc2: Var = c.parameter('TOC2',p.toc2)
    tob2: Var = c.parameter('TOB2',p.tob2)
    field0: Var = c.parameter('Efd0Pu',1.)
    current0: Var = c.parameter('Ifd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    terminal0: Var = c.parameter('Vt0Pu',1.)
    supplement0: Var = c.parameter('Vs0Pu',0.)
    minimum0: Expr = c.parameter('Uel0Pu',0.) if p.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.)
    maximum0: Expr = c.parameter('Oel0Pu',0.) if p.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.)
    channel0: Expr = (field0+kc*current0)/kr
    raw0: Expr = channel0-supplement0
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0+raw0-minimum0-maximum0)
    supplement: Var = c.input('VsPu',supplement0)
    current: Var = c.input('IfdPu',current0)
    terminal: Var = c.input('VtPu',terminal0)
    minimum: Var = c.input('UelPu',minimum0 if p.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM else raw0)
    maximum: Var = c.input('OelPu',maximum0 if p.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM else raw0)
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    # Summed limiter signals alter common demand without selecting their dedicated channel.
    summed: Expr = reference-measured
    if p.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM:
        summed = summed+minimum
    else:
        pass
    if p.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM:
        summed = summed+maximum
    else:
        pass
    pre_minimum: Var = c.algebraic('PreMinimumPu',summed,raw0)
    pre_maximum: Var = c.algebraic('PreMaximumPu',sym.max(pre_minimum,minimum) if p.minimum_location == ExcitationLimiterLocation.REFERENCE_GATE else pre_minimum,raw0)
    common: Var = c.algebraic('CommonDemandPu',(sym.min(pre_maximum,maximum) if p.maximum_location == ExcitationLimiterLocation.REFERENCE_GATE else pre_maximum)+supplement,channel0)
    lower: Expr = vrmin/kr
    upper: Expr = vrmax/kr
    normal_first: Var = c.bounded_lead_lag('NormalFirstPu',common,tc1,tb1,p.tc1,p.tb1,channel0,lower,upper)
    normal: Var = c.bounded_lead_lag('NormalChannelPu',normal_first,tc2,tb2,p.tc2,p.tb2,channel0,lower,upper)
    minimum_first: Var = c.bounded_lead_lag('MinimumFirstPu',common,tuc1,tub1,p.tuc1,p.tub1,channel0,lower,upper)
    minimum_channel: Var = c.bounded_lead_lag('MinimumChannelPu',minimum_first,tuc2,tub2,p.tuc2,p.tub2,channel0,lower,upper)
    maximum_first: Var = c.bounded_lead_lag('MaximumFirstPu',common,toc1,tob1,p.toc1,p.tob1,channel0,lower,upper)
    maximum_channel: Var = c.bounded_lead_lag('MaximumChannelPu',maximum_first,toc2,tob2,p.toc2,p.tob2,channel0,lower,upper)
    minimum_active: Var = c.algebraic('MinimumActive',sym.heaviside(minimum-pre_minimum) if p.minimum_location == ExcitationLimiterLocation.REFERENCE_GATE else Const(0.),Const(0.))
    maximum_active: Var = c.algebraic('MaximumActive',sym.heaviside(pre_maximum-maximum) if p.maximum_location == ExcitationLimiterLocation.REFERENCE_GATE else Const(0.),Const(0.))
    selected: Var = c.algebraic('SelectedDemandPu',(Const(1.)-maximum_active)*(
        (Const(1.)-minimum_active)*normal+minimum_active*minimum_channel)+maximum_active*maximum_channel,channel0)
    forcing: Var = c.algebraic('FieldForcingPu',sym.hard_sat(kr*selected,vrmin,vrmax)-kc*current,field0)
    minimum_field: Expr = terminal*vrmin
    maximum_field: Expr = terminal*vrmax
    memory: Var = c.lag('FieldMemoryPu',forcing,t1,p.t1,field0,minimum_field,maximum_field)
    field: Var = c.algebraic('EfdPu',sym.hard_sat(memory,minimum_field,maximum_field),field0)
    return c.finish((field,pre_minimum,pre_maximum,normal,minimum_channel,maximum_channel),
        'Three bounded compensation channels with active take-over selection and terminal-dependent field capability')


def build_st5b_template(vf: VarFactory, name: str | None = None,
                        parameters: ParallelChannelExciterParameters | None = None) -> RmsModelTemplate:
    """Build fixed-gate three-channel excitation.

    Both limiter signals use takeover gates. All six bounded compensation
    memories evolve continuously; field capability follows actual terminal
    magnitude. See :func:`build_parallel_channel_exciter` for equations, units,
    initialization and the seven-input, six-output interface.

    :param vf: Shared symbolic factory.
    :param name: Optional controller label.
    :param parameters: Physical channel settings with both takeover selections.
    :return: Native fixed-gate excitation controller.
    :raises ValueError: A summation selection is requested for this fixed topology.
    """
    p: ParallelChannelExciterParameters = ParallelChannelExciterParameters() if parameters is None else parameters
    if p.minimum_location != ExcitationLimiterLocation.REFERENCE_GATE or p.maximum_location != ExcitationLimiterLocation.REFERENCE_GATE:
        raise ValueError('Fixed-gate excitation requires both takeover selections')
    else:
        return build_parallel_channel_exciter(vf,'ST5B' if name is None else name,p)
