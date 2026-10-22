# SPDX-License-Identifier: MPL-2.0
"""Cascaded PI excitation with bounded firing dynamics and filtered bridge feedback."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
from VeraGridEngine.Templates.Rms.self_feedback_exciter import ExcitationLimiterLocation
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class CompoundExcitationSource(Enum):
    """Physical potential-source configuration feeding the diode bridge."""
    TERMINAL = 1
    INDEPENDENT = 2


class CompoundSupplementLocation(Enum):
    """Supplementary-voltage addition relative to the minimum-excitation gate."""
    ERROR_SUM = 1
    AFTER_MINIMUM_GATE = 2


class FilteredCompoundPiParameters:
    """Two regulators, firing dynamics, feedback and loaded potential-source coefficients."""
    __slots__ = ('tr','kpr','kir','vrmax','vrmin','kpm','kim','vmmax','vmmin','ta','vamax','vamin','kg','tg','vgmax','kp','ki','xl','thetap','kc','vbmax',
                 'minimum_location','maximum_location','supplement_location','source')

    def __init__(self, tr: float = 0.02, kpr: float = 20.0, kir: float = 10.0, vrmax: float = 5.0,
                 vrmin: float = -5.0, kpm: float = 1.0, kim: float = 1.0, vmmax: float = 5.0,
                 vmmin: float = -5.0, ta: float = 0.02, vamax: float = 5.0, vamin: float = -5.0,
                 kg: float = 1.0, tg: float = 0.1, vgmax: float = 5.0, kp: float = 2.0,
                 ki: float = 0.1, xl: float = 0.1, thetap: float = 0.0, kc: float = 0.1,
                 vbmax: float = 5.0,
                 minimum_location: ExcitationLimiterLocation = ExcitationLimiterLocation.REFERENCE_SUM,
                 maximum_location: ExcitationLimiterLocation = ExcitationLimiterLocation.REFERENCE_SUM,
                 supplement_location: CompoundSupplementLocation = CompoundSupplementLocation.ERROR_SUM,
                 source: CompoundExcitationSource = CompoundExcitationSource.TERMINAL) -> None:
        """Store physical parameters on compatible voltage and current bases.

        :param tr: Physical TR coefficient; time constants in seconds and phase in degrees.
        :param kpr: Physical KPR coefficient; time constants in seconds and phase in degrees.
        :param kir: Physical KIR coefficient; time constants in seconds and phase in degrees.
        :param vrmax: Physical VRMAX coefficient; time constants in seconds and phase in degrees.
        :param vrmin: Physical VRMIN coefficient; time constants in seconds and phase in degrees.
        :param kpm: Physical KPM coefficient; time constants in seconds and phase in degrees.
        :param kim: Physical KIM coefficient; time constants in seconds and phase in degrees.
        :param vmmax: Physical VMMAX coefficient; time constants in seconds and phase in degrees.
        :param vmmin: Physical VMMIN coefficient; time constants in seconds and phase in degrees.
        :param ta: Physical TA coefficient; time constants in seconds and phase in degrees.
        :param vamax: Physical VAMAX coefficient; time constants in seconds and phase in degrees.
        :param vamin: Physical VAMIN coefficient; time constants in seconds and phase in degrees.
        :param kg: Physical KG coefficient; time constants in seconds and phase in degrees.
        :param tg: Physical TG coefficient; time constants in seconds and phase in degrees.
        :param vgmax: Physical VGMAX coefficient; time constants in seconds and phase in degrees.
        :param kp: Physical KP coefficient; time constants in seconds and phase in degrees.
        :param ki: Physical KI coefficient; time constants in seconds and phase in degrees.
        :param xl: Physical XL coefficient; time constants in seconds and phase in degrees.
        :param thetap: Physical THETAP coefficient; time constants in seconds and phase in degrees.
        :param kc: Physical KC coefficient; time constants in seconds and phase in degrees.
        :param vbmax: Physical VBMAX coefficient; time constants in seconds and phase in degrees.
        :param minimum_location: Additive, regulator-input or inner-output minimum limiter.
        :param maximum_location: Additive, regulator-input or inner-output maximum limiter.
        :param supplement_location: Supplement before or after the input minimum gate.
        :param source: Terminal compound potential or independent potential equal to KP.
        """
        self.tr: float = tr
        self.kpr: float = kpr
        self.kir: float = kir
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.kpm: float = kpm
        self.kim: float = kim
        self.vmmax: float = vmmax
        self.vmmin: float = vmmin
        self.ta: float = ta
        self.vamax: float = vamax
        self.vamin: float = vamin
        self.kg: float = kg
        self.tg: float = tg
        self.vgmax: float = vgmax
        self.kp: float = kp
        self.ki: float = ki
        self.xl: float = xl
        self.thetap: float = thetap
        self.kc: float = kc
        self.vbmax: float = vbmax
        self.minimum_location: ExcitationLimiterLocation = minimum_location
        self.maximum_location: ExcitationLimiterLocation = maximum_location
        self.supplement_location: CompoundSupplementLocation = supplement_location
        self.source: CompoundExcitationSource = source


def build_st4c_template(vf: VarFactory, name: str | None = None,
                        parameters: FilteredCompoundPiParameters | None = None) -> RmsModelTemplate:
    """Build cascaded voltage/bridge PI regulation with filtered bridge feedback.

    Sensed terminal voltage opposes reference and supplementary excitation.
    A bounded parallel voltage PI feeds a second bounded parallel PI after
    subtraction of filtered bridge feedback. Each integral stops only when
    its motion would push total proportional-plus-integral demand farther
    outside its own limits. The second PI drives a separately bounded firing
    lag. Its output VA is multiplied by the actual loaded rectifier supply.

    Feedback is KG*VA/(1+s*TG), externally capped at VGMAX. It senses VA
    before the field-supply multiplier, preserving controller behavior as
    terminal supply changes. The source is the magnitude of
    KP*exp(j*theta)*(V+j*XL*I)+j*KI*I, or independent potential KP. Diode
    commutation depends on live field current and source magnitude. VBMAX
    caps the resulting available field voltage. Phase is specified in degrees.

    Minimum and maximum excitation signals can add at the error sum, take over
    at voltage-regulator input or take over after the inner PI. High gates
    precede low gates. Supplementary voltage can add before the input minimum
    gate or between the input minimum and maximum gates. Gate selections are
    explicit physical enums. An absent takeover controller must connect to
    its corresponding exposed pre-gate output, giving exact moving bypass.

    Ten inputs are sensed voltage, reference, supplement, rectangular terminal
    voltage, rectangular outgoing stator current, field current, minimum and
    maximum excitation. Five outputs are field voltage, pre-input minimum,
    pre-input maximum, pre-output minimum and pre-output maximum demands.
    Voltage/current bases must be compatible; all times are seconds. Five
    continuous states are present with active integrals and positive sensing
    and firing times. Zero sensing/firing times and integral gains remove the
    corresponding memories exactly. Feedback time remains positive.

    Initialization balances actual field voltage and loaded supply, then seeds
    bridge, feedback and both PI memories consistently. The reference includes
    actual auxiliary biases. Initial field requires positive available supply
    and capabilities admitting both regulator demands and bridge output.
    External feedback clipping does not invent a feedback-memory stop.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Physical regulator, bridge, source and insertion settings.
    :return: Native static excitation with explicit source and feedback dynamics.
    :raises ValueError: Invalid domains, selections or capability ordering.
    """
    p: FilteredCompoundPiParameters = FilteredCompoundPiParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.tr,p.kpr,p.kir,p.vrmax,p.vrmin,p.kpm,p.kim,p.vmmax,p.vmmin,
        p.ta,p.vamax,p.vamin,p.kg,p.tg,p.vgmax,p.kp,p.ki,p.xl,p.thetap,p.kc,p.vbmax)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Filtered compound excitation coefficients must be finite')
    elif min(p.tr,p.kir,p.kpm,p.kim,p.ta,p.kg,p.kp,p.ki,p.xl,p.kc) < 0 or min(p.kpr,p.tg,p.vbmax) <= 0:
        raise ValueError('Filtered compound excitation times/gains have invalid domains')
    elif p.kpm+p.kim == 0 or p.vgmax < 0:
        raise ValueError('Inner regulation requires positive combined action and nonnegative feedback ceiling')
    elif p.vrmax <= p.vrmin or p.vmmax <= p.vmmin or p.vamax <= p.vamin:
        raise ValueError('Voltage, inner and firing capabilities must be independently ordered')
    elif p.kp == 0 and (p.source == CompoundExcitationSource.INDEPENDENT or p.ki == 0):
        raise ValueError('Selected compound excitation source has no physical potential')
    elif not isinstance(p.minimum_location,ExcitationLimiterLocation) or not isinstance(p.maximum_location,ExcitationLimiterLocation):
        raise ValueError('Excitation limiter locations require explicit physical selections')
    elif not isinstance(p.source,CompoundExcitationSource) or not isinstance(p.supplement_location,CompoundSupplementLocation):
        raise ValueError('Excitation source and supplementary location require explicit selections')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'ST4C' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    kpr: Var = c.parameter('KPR',p.kpr)
    kir: Var = c.parameter('KIR',p.kir)
    vrmax: Var = c.parameter('VRMAX',p.vrmax)
    vrmin: Var = c.parameter('VRMIN',p.vrmin)
    kpm: Var = c.parameter('KPM',p.kpm)
    kim: Var = c.parameter('KIM',p.kim)
    vmmax: Var = c.parameter('VMMAX',p.vmmax)
    vmmin: Var = c.parameter('VMMIN',p.vmmin)
    ta: Var = c.parameter('TA',p.ta)
    vamax: Var = c.parameter('VAMAX',p.vamax)
    vamin: Var = c.parameter('VAMIN',p.vamin)
    kg: Var = c.parameter('KG',p.kg)
    tg: Var = c.parameter('TG',p.tg)
    vgmax: Var = c.parameter('VGMAX',p.vgmax)
    kp: Var = c.parameter('KP',p.kp)
    ki: Var = c.parameter('KI',p.ki)
    xl: Var = c.parameter('XL',p.xl)
    theta: Var = c.parameter('THETAP',p.thetap)
    kc: Var = c.parameter('KC',p.kc)
    vbmax: Var = c.parameter('VBMAX',p.vbmax)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
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
    current: Var = c.input('IfdPu',Const(1.))
    minimum: Var = c.input('UelPu',minimum0)
    maximum: Var = c.input('OelPu',maximum0)
    cosine: Expr = sym.cos(theta*Const(math.pi/180.))
    sine: Expr = sym.sin(theta*Const(math.pi/180.))
    real: Expr = kp*(cosine*(vr-xl*ii)-sine*(vi+xl*ir))-ki*ii
    imag: Expr = kp*(sine*(vr-xl*ii)+cosine*(vi+xl*ir))+ki*ir
    potential_expression: Expr = sym.sqrt(real**2+imag**2) if p.source == CompoundExcitationSource.TERMINAL else kp
    potential: Var = c.algebraic('PotentialPu',potential_expression,potential_expression)
    supply_expression: Expr = sym.min(vbmax,potential*_esst3a_fex(sym.safe_divide(kc*current,potential,1.)))
    supply: Var = c.algebraic('SupplyPu',supply_expression,supply_expression)
    bridge0: Expr = field0/supply
    feedback0: Expr = sym.min(vgmax,kg*bridge0)
    inner_error0: Expr = Const(0.) if p.kim > 0 else bridge0/kpm
    regulator0: Expr = feedback0+inner_error0
    error0: Expr = Const(0.) if p.kir > 0 else regulator0/kpr
    c.block.init_eqs[reference] = (voltage0+error0-supplement0-
        (minimum0 if p.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))-
        (maximum0 if p.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.)))
    before_minimum0: Expr = error0-(supplement0 if p.supplement_location == CompoundSupplementLocation.AFTER_MINIMUM_GATE else Const(0.))
    c.block.init_eqs[minimum] = (before_minimum0 if p.minimum_location == ExcitationLimiterLocation.REFERENCE_GATE else
        bridge0 if p.minimum_location == ExcitationLimiterLocation.OUTPUT_GATE else minimum0)
    c.block.init_eqs[maximum] = (error0 if p.maximum_location == ExcitationLimiterLocation.REFERENCE_GATE else
        bridge0 if p.maximum_location == ExcitationLimiterLocation.OUTPUT_GATE else maximum0)
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    firing: Var = vf.add_var('FiringPu_'+c.name)
    feedback_memory: Var = c.lag('FeedbackMemoryPu',kg*firing,tg,p.tg,kg*bridge0)
    feedback: Var = c.algebraic('FeedbackPu',sym.min(vgmax,feedback_memory),feedback0)
    error: Expr = reference-measured
    if p.supplement_location == CompoundSupplementLocation.ERROR_SUM:
        error = error+supplement
    else:
        pass
    if p.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM:
        error = error+minimum
    else:
        pass
    if p.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM:
        error = error+maximum
    else:
        pass
    pre_minimum_input: Var = c.algebraic('PreMinimumInputPu',error,before_minimum0)
    if p.minimum_location == ExcitationLimiterLocation.REFERENCE_GATE:
        error = sym.max(error,minimum)
    else:
        pass
    if p.supplement_location == CompoundSupplementLocation.AFTER_MINIMUM_GATE:
        error = error+supplement
    else:
        pass
    pre_maximum_input: Var = c.algebraic('PreMaximumInputPu',error,error0)
    if p.maximum_location == ExcitationLimiterLocation.REFERENCE_GATE:
        error = sym.min(error,maximum)
    else:
        pass
    voltage_integral: Var = (c.differential(vf.add_var('VoltageIntegralPu_'+c.name),kir*error,
        regulator0,vrmin-kpr*error,vrmax-kpr*error) if p.kir > 0 else c.algebraic('VoltageIntegralPu',Const(0.),Const(0.)))
    regulator: Var = c.algebraic('VoltageDemandPu',sym.hard_sat(kpr*error+voltage_integral,vrmin,vrmax),regulator0)
    inner_error: Expr = regulator-feedback
    inner_integral: Var = (c.differential(vf.add_var('FieldIntegralPu_'+c.name),kim*inner_error,
        bridge0,vmmin-kpm*inner_error,vmmax-kpm*inner_error) if p.kim > 0 else c.algebraic('FieldIntegralPu',Const(0.),Const(0.)))
    pre_minimum_output: Var = c.algebraic('PreMinimumOutputPu',sym.hard_sat(kpm*inner_error+inner_integral,vmmin,vmmax),bridge0)
    bridge_demand: Expr = sym.max(pre_minimum_output,minimum) if p.minimum_location == ExcitationLimiterLocation.OUTPUT_GATE else pre_minimum_output
    pre_maximum_output: Var = c.algebraic('PreMaximumOutputPu',bridge_demand,bridge0)
    if p.maximum_location == ExcitationLimiterLocation.OUTPUT_GATE:
        bridge_demand = sym.min(bridge_demand,maximum)
    else:
        pass
    c.lag('FiringPu',bridge_demand,ta,p.ta,bridge0,vamin,vamax,output=firing)
    field: Var = c.algebraic('EfdPu',supply*firing,field0)
    return c.finish((field,pre_minimum_input,pre_maximum_input,pre_minimum_output,pre_maximum_output),
        'Cascaded bounded PI excitation with loaded supply, firing lag and capped bridge feedback')
