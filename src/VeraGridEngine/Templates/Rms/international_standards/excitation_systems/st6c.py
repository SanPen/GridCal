# SPDX-License-Identifier: MPL-2.0
"""Static field regulation with current-dependent PID capability and compound supply."""
from __future__ import annotations
import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.compound_excitation_supply import CompoundSupplyParameters, build_compound_supply
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class FieldRegulatorLimiterLocation(Enum):
    """Limiter addition at error, input takeover, post-gate addition or output takeover."""
    ERROR_SUM = 1
    ERROR_GATE = 2
    POST_GATE_SUM = 3
    OUTPUT_GATE = 4


class CurrentLimitedFieldParameters:
    """Outer PID, inner feedforward/feedback, live current capability and bridge settings."""
    __slots__ = ('tr','kpa','kia','kda','tda','vamax','vamin','kff','km','kci','klr','ilr','vrmax','vrmin',
                 'kg','tg','vmmax','vmmin','ta','supply','minimum_location','maximum_location')

    def __init__(self, tr: float = .02, kpa: float = 20., kia: float = 10., kda: float = .05,
                 tda: float = .05, vamax: float = 5., vamin: float = -5., kff: float = 1.,
                 km: float = 2., kci: float = 1., klr: float = 10., ilr: float = 5.,
                 vrmax: float = 5., vrmin: float = -5., kg: float = .1, tg: float = .1,
                 vmmax: float = 5., vmmin: float = -5., ta: float = .05,
                 supply: CompoundSupplyParameters | None = None,
                 minimum_location: FieldRegulatorLimiterLocation = FieldRegulatorLimiterLocation.ERROR_SUM,
                 maximum_location: FieldRegulatorLimiterLocation = FieldRegulatorLimiterLocation.ERROR_SUM) -> None:
        """Store physical loops and four-way limiter connections.

        :param tr: Sensing time, seconds.
        :param kpa: Positive regulator proportional gain.
        :param kia: Integral gain, inverse seconds.
        :param kda: Derivative gain, seconds.
        :param tda: Derivative filter time, seconds.
        :param vamax: Fixed regulator upper capability.
        :param vamin: Regulator lower capability, no greater than VRMIN.
        :param kff: Inner-loop feedforward gain.
        :param km: Inner-loop forward gain; KM plus KFF must be positive.
        :param kci: Current reference conversion factor.
        :param klr: Field-current limiter gain.
        :param ilr: Field-current limit reference.
        :param vrmax: Inner command upper limit.
        :param vrmin: Inner command lower limit and current-limiter floor.
        :param kg: Bridge-command feedback gain.
        :param tg: Positive bridge-command feedback time, seconds.
        :param vmmax: Firing output upper capability.
        :param vmmin: Firing output lower capability.
        :param ta: Firing lag time, seconds.
        :param supply: Potential circuit and loaded bridge settings.
        :param minimum_location: Minimum-excitation insertion.
        :param maximum_location: Maximum-excitation insertion.
        """
        self.tr: float = tr
        self.kpa: float = kpa
        self.kia: float = kia
        self.kda: float = kda
        self.tda: float = tda
        self.vamax: float = vamax
        self.vamin: float = vamin
        self.kff: float = kff
        self.km: float = km
        self.kci: float = kci
        self.klr: float = klr
        self.ilr: float = ilr
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.kg: float = kg
        self.tg: float = tg
        self.vmmax: float = vmmax
        self.vmmin: float = vmmin
        self.ta: float = ta
        self.supply: CompoundSupplyParameters = CompoundSupplyParameters() if supply is None else supply
        self.minimum_location: FieldRegulatorLimiterLocation = minimum_location
        self.maximum_location: FieldRegulatorLimiterLocation = maximum_location


def build_st6c_template(vf: VarFactory, name: str | None = None,
                        parameters: CurrentLimitedFieldParameters | None = None) -> RmsModelTemplate:
    """Build static excitation with a live current-dependent outer PID ceiling.

    Reference minus sensed voltage enters optional minimum high and maximum low
    input gates. Supplementary voltage and selected post-gate limiter sums enter
    after those gates. Parallel PID action has fixed lower VAMIN and live upper
    min(VAMAX,max(VRMIN,KLR*(KCI*ILR-IFD))). Integral motion stops only when it
    drives the total PID farther outside those bounds. KCI scales the current
    reference, not a terminal-voltage commutation drop.

    Inner demand is KM*(VA-VG)+KFF*VA, bounded at VRMIN/VRMAX. Optional minimum
    high and maximum low output takeover gates precede a separately bounded
    firing lag with VMMIN/VMMAX. Feedback VG is KG times that lag output filtered
    through TG, before multiplication by available supply. A terminal compound
    or independent potential supplies a loaded diode bridge; its load is the
    generator field current. Delivered field is supply times firing command.

    Ten inputs are sensed voltage, reference, supplement, rectangular terminal
    voltage, rectangular outgoing stator current, field current and two limiter
    signals. Five outputs are delivered field and four pre-gate demands. All
    voltages/currents use compatible per-unit bases; times are seconds and
    potential phase is degrees. Full order is five memories: sensing, integral,
    derivative, feedback and firing. Disabled PID paths and zero sensing/firing
    times remove memories exactly; feedback time remains positive.

    Initial firing command is EFD0 divided by loaded supply. Its filtered
    feedback balances inner demand, giving VA0=VM0*(1+KM*KG)/(KM+KFF).
    PID memory or proportional reference offset supplies VA0. Actual summed
    limiter and supplementary biases determine reference. Absent takeover
    limiters follow exposed pre-gate demand; absent sums are zero. Initial
    supply must be positive and current-dependent, PID, inner and firing
    capabilities must all admit the operating point. No limiter reset or
    automatic enlargement of capability is introduced.

    :param vf: Shared native symbolic factory.
    :param name: Optional controller label.
    :param parameters: Physical PID, field-loop, supply and limiter settings.
    :return: Native current-limited, compound-fed field regulator.
    :raises ValueError: Invalid domains, locations or capability ordering.
    """
    p: CurrentLimitedFieldParameters = CurrentLimitedFieldParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.tr,p.kpa,p.kia,p.kda,p.tda,p.vamax,p.vamin,p.kff,p.km,p.kci,p.klr,p.ilr,
        p.vrmax,p.vrmin,p.kg,p.tg,p.vmmax,p.vmmin,p.ta)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Current-limited field coefficients must be finite')
    elif min(p.tr,p.kia,p.kda,p.tda,p.kff,p.km,p.kci,p.klr,p.ilr,p.kg,p.ta) < 0 or min(p.kpa,p.tg,p.kff+p.km) <= 0:
        raise ValueError('Current-limited field gains/times have invalid domains')
    elif p.kda > 0 and p.tda == 0:
        raise ValueError('Enabled field regulator derivative requires positive filter time')
    elif p.vamax <= p.vamin or p.vrmax <= p.vrmin or p.vmmax <= p.vmmin or p.vamin > p.vrmin:
        raise ValueError('Current-limited field capabilities must be ordered and VAMIN no greater than VRMIN')
    elif not isinstance(p.minimum_location,FieldRegulatorLimiterLocation) or not isinstance(p.maximum_location,FieldRegulatorLimiterLocation):
        raise ValueError('Current-limited field limiter locations are invalid')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'ST6C' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    kpa: Var = c.parameter('KPA',p.kpa)
    kia: Var = c.parameter('KIA',p.kia)
    kda: Var = c.parameter('KDA',p.kda)
    tda: Var = c.parameter('TDA',p.tda)
    vamax: Var = c.parameter('VAMAX',p.vamax)
    vamin: Var = c.parameter('VAMIN',p.vamin)
    kff: Var = c.parameter('KFF',p.kff)
    km: Var = c.parameter('KM',p.km)
    kci: Var = c.parameter('KCI',p.kci)
    klr: Var = c.parameter('KLR',p.klr)
    ilr: Var = c.parameter('ILR',p.ilr)
    vrmax: Var = c.parameter('VRMAX',p.vrmax)
    vrmin: Var = c.parameter('VRMIN',p.vrmin)
    kg: Var = c.parameter('KG',p.kg)
    tg: Var = c.parameter('TG',p.tg)
    vmmax: Var = c.parameter('VMMAX',p.vmmax)
    vmmin: Var = c.parameter('VMMIN',p.vmmin)
    ta: Var = c.parameter('TA',p.ta)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    current0: Var = c.parameter('Ifd0Pu',1.)
    supplement0: Var = c.parameter('Vs0Pu',0.)
    minimum0: Var = c.parameter('Uel0Pu',0.)
    maximum0: Var = c.parameter('Oel0Pu',0.)
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0)
    supplement: Var = c.input('VsPu',supplement0)
    vr: Var = c.input('VrPu',Const(1.))
    vi: Var = c.input('ViPu',Const(0.))
    ir: Var = c.input('IrPu',Const(.5))
    ii: Var = c.input('IiPu',Const(0.))
    current: Var = c.input('IfdPu',current0)
    minimum: Var = c.input('UelPu',minimum0)
    maximum: Var = c.input('OelPu',maximum0)
    supply: Var = build_compound_supply(c,vr,vi,ir,ii,current,p.supply)
    firing0: Expr = field0/supply
    regulator0: Expr = firing0*(Const(1.)+km*kg)/(km+kff)
    error0: Expr = Const(0.) if p.kia > 0 else regulator0/kpa
    post_sum0: Expr = supplement0+(minimum0 if p.minimum_location == FieldRegulatorLimiterLocation.POST_GATE_SUM else Const(0.))+(maximum0 if p.maximum_location == FieldRegulatorLimiterLocation.POST_GATE_SUM else Const(0.))
    input0: Expr = error0-post_sum0
    c.block.init_eqs[reference] = voltage0+input0-(minimum0 if p.minimum_location == FieldRegulatorLimiterLocation.ERROR_SUM else Const(0.))-(maximum0 if p.maximum_location == FieldRegulatorLimiterLocation.ERROR_SUM else Const(0.))
    c.block.init_eqs[minimum] = input0 if p.minimum_location == FieldRegulatorLimiterLocation.ERROR_GATE else firing0 if p.minimum_location == FieldRegulatorLimiterLocation.OUTPUT_GATE else minimum0
    c.block.init_eqs[maximum] = input0 if p.maximum_location == FieldRegulatorLimiterLocation.ERROR_GATE else firing0 if p.maximum_location == FieldRegulatorLimiterLocation.OUTPUT_GATE else maximum0
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    firing: Var = vf.add_var('FiringPu_'+c.name)
    feedback: Var = c.lag('FeedbackPu',kg*firing,tg,p.tg,kg*firing0)
    error: Expr = reference-measured+(minimum if p.minimum_location == FieldRegulatorLimiterLocation.ERROR_SUM else Const(0.))+(maximum if p.maximum_location == FieldRegulatorLimiterLocation.ERROR_SUM else Const(0.))
    pre_minimum: Var = c.algebraic('PreMinimumInputPu',error,input0)
    if p.minimum_location == FieldRegulatorLimiterLocation.ERROR_GATE:
        error = sym.max(error,minimum)
    else:
        pass
    pre_maximum: Var = c.algebraic('PreMaximumInputPu',error,input0)
    if p.maximum_location == FieldRegulatorLimiterLocation.ERROR_GATE:
        error = sym.min(error,maximum)
    else:
        pass
    error = error+supplement+(minimum if p.minimum_location == FieldRegulatorLimiterLocation.POST_GATE_SUM else Const(0.))+(maximum if p.maximum_location == FieldRegulatorLimiterLocation.POST_GATE_SUM else Const(0.))
    current_ceiling: Var = c.algebraic('CurrentCeilingPu',sym.min(vamax,sym.max(vrmin,klr*(kci*ilr-current))),sym.min(vamax,sym.max(vrmin,klr*(kci*ilr-current0))))
    derivative: Var = c.washout('DerivativePu',error,tda,p.tda,kda/tda,error0) if p.kda > 0 else c.algebraic('DerivativePu',Const(0.),Const(0.))
    nonintegral: Expr = kpa*error+derivative
    integral: Var = c.differential(vf.add_var('IntegralPu_'+c.name),kia*error,regulator0,vamin-nonintegral,current_ceiling-nonintegral) if p.kia > 0 else c.algebraic('IntegralPu',Const(0.),Const(0.))
    regulator: Var = c.algebraic('RegulatorPu',sym.hard_sat(nonintegral+integral,vamin,current_ceiling),regulator0)
    pre_minimum_output: Var = c.algebraic('PreMinimumOutputPu',sym.hard_sat(km*(regulator-feedback)+kff*regulator,vrmin,vrmax),firing0)
    demand: Expr = sym.max(pre_minimum_output,minimum) if p.minimum_location == FieldRegulatorLimiterLocation.OUTPUT_GATE else pre_minimum_output
    pre_maximum_output: Var = c.algebraic('PreMaximumOutputPu',demand,firing0)
    demand = sym.min(demand,maximum) if p.maximum_location == FieldRegulatorLimiterLocation.OUTPUT_GATE else demand
    c.lag('FiringPu',demand,ta,p.ta,firing0,vmmin,vmmax,output=firing)
    field: Var = c.algebraic('EfdPu',firing*supply,field0)
    return c.finish((field,pre_minimum,pre_maximum,pre_minimum_output,pre_maximum_output),
        'Current-limited PID field regulation with inner feedforward/feedback and compound rectifier supply')
