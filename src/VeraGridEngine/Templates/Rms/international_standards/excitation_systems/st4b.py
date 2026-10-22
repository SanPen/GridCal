# SPDX-License-Identifier: MPL-2.0
"""Compound-source excitation with cascaded bounded voltage and field regulators."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class CompoundPiExciterParameters:
    """Physical sensing, cascaded PI, bridge and transformer coefficients."""
    __slots__ = ('tr','kpr','kir','vrmax','vrmin','ta','kpm','kim','vmmax','vmmin','kg','kp','ki','vbmax','kc','xl','thetap')

    def __init__(self, tr: float = .02, kpr: float = 2., kir: float = 1.,
                 vrmax: float = 5., vrmin: float = -5., ta: float = .05,
                 kpm: float = 1., kim: float = 1., vmmax: float = 1., vmmin: float = 0.,
                 kg: float = 1., kp: float = 2., ki: float = .1, vbmax: float = 5.,
                 kc: float = .1, xl: float = .1, thetap: float = 0.) -> None:
        """Store coefficients in compatible per-unit field bases.

        :param tr: Nonnegative compensated-voltage sensing time, seconds.
        :param kpr: Nonnegative voltage-loop proportional gain.
        :param kir: Nonnegative voltage-loop integral gain, inverse seconds.
        :param vrmax: Upper total voltage-regulator capability.
        :param vrmin: Lower total voltage-regulator capability.
        :param ta: Nonnegative regulator output lag, seconds.
        :param kpm: Nonnegative inner field-loop proportional gain.
        :param kim: Nonnegative inner field-loop integral gain, inverse seconds.
        :param vmmax: Upper total bridge-control capability.
        :param vmmin: Lower total bridge-control capability.
        :param kg: Nonnegative delivered-field feedback gain.
        :param kp: Nonnegative potential-transformer ratio.
        :param ki: Nonnegative current-compounding ratio.
        :param vbmax: Positive rectified-supply capability.
        :param kc: Nonnegative commutation loading coefficient.
        :param xl: Nonnegative transformer leakage reactance.
        :param thetap: Potential-transformer phase angle, degrees.
        """
        self.tr: float = tr
        self.kpr: float = kpr
        self.kir: float = kir
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.ta: float = ta
        self.kpm: float = kpm
        self.kim: float = kim
        self.vmmax: float = vmmax
        self.vmmin: float = vmmin
        self.kg: float = kg
        self.kp: float = kp
        self.ki: float = ki
        self.vbmax: float = vbmax
        self.kc: float = kc
        self.xl: float = xl
        self.thetap: float = thetap


def build_st4b_template(vf: VarFactory, name: str | None = None,
                       parameters: CompoundPiExciterParameters | None = None) -> RmsModelTemplate:
    """Build cascaded PI excitation fed by a loaded compound-transformer source.

    Compensated-voltage sensing feeds a bounded parallel PI regulator followed
    by an optional output lag. Its output opposes KG times delivered field
    voltage in a second bounded PI loop. Each integral memory stops only when
    its derivative would drive total proportional-plus-integral demand farther
    outside its capability; inward recovery remains active. A final low-value
    excitation gate follows the inner PI. Delivered field is bridge demand
    multiplied by the actual loaded and capped transformer supply.

    The complex source is KP*exp(j*THETAP)*(V+j*XL*I)+j*KI*I. Its magnitude,
    live field current and the piecewise diode commutation law determine supply
    before VBMAX clipping. The inner proportional feedback is solved explicitly
    through a positive denominator 1+KPM*KG*VB, preserving both PI bounds and the
    final low gate without an iterative algebraic feedback approximation.
    Collapsed supply therefore gives zero delivered field and finite dynamics.

    Ten inputs are sensed voltage, reference, stabilizer, real/imaginary terminal
    voltage, real/imaginary outgoing stator current, field current, additive
    minimum-excitation signal and low-gate maximum-excitation demand. Outputs
    are delivered field and bounded inner demand before the maximum gate.
    An absent maximum limiter connects to that exact preceding demand. Voltages
    and currents use compatible per-unit bases; times are seconds and transformer
    phase is degrees.

    With active integrals and positive lags there are four states. Zero integral
    gain removes its memory and initializes a proportional bias; zero sensing
    or output lag reduces algebraically. Initialization balances actual field
    voltage and loaded supply, then determines both regulator demands and the
    matching voltage reference including auxiliary biases. A nonzero initial
    field requires a positive initial rectified supply and feasible capabilities.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Physical coefficients and capability settings.
    :return: Native cascaded-PI compound-source excitation controller.
    :raises ValueError: Invalid physical gains, times or capability ordering.
    """
    p: CompoundPiExciterParameters = CompoundPiExciterParameters() if parameters is None else parameters
    if min(p.tr,p.kpr,p.kir,p.ta,p.kpm,p.kim,p.kg,p.kp,p.ki,p.kc,p.xl) < 0 or p.vbmax <= 0:
        raise ValueError('Compound PI excitation coefficients have invalid physical domains')
    elif p.kp+p.ki == 0:
        raise ValueError('Compound excitation requires a potential or current source')
    elif p.kpr+p.kir == 0 or p.kpm+p.kim == 0:
        raise ValueError('Each compound regulator requires proportional or integral action')
    elif p.vrmax <= p.vrmin or p.vmmax <= p.vmmin:
        raise ValueError('Compound PI regulator capabilities must be ordered')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'ST4B' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    kpr: Var = c.parameter('KPR',p.kpr)
    kir: Var = c.parameter('KIR',p.kir)
    vrmax: Var = c.parameter('VRMAX',p.vrmax)
    vrmin: Var = c.parameter('VRMIN',p.vrmin)
    ta: Var = c.parameter('TA',p.ta)
    kpm: Var = c.parameter('KPM',p.kpm)
    kim: Var = c.parameter('KIM',p.kim)
    vmmax: Var = c.parameter('VMMAX',p.vmmax)
    vmmin: Var = c.parameter('VMMIN',p.vmmin)
    kg: Var = c.parameter('KG',p.kg)
    kp: Var = c.parameter('KP',p.kp)
    ki: Var = c.parameter('KI',p.ki)
    vbmax: Var = c.parameter('VBMAX',p.vbmax)
    kc: Var = c.parameter('KC',p.kc)
    xl: Var = c.parameter('XL',p.xl)
    theta: Var = c.parameter('THETAP',p.thetap)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    supplement0: Var = c.parameter('Vs0Pu',0.)
    minimum0: Var = c.parameter('Uel0Pu',0.)
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0)
    supplement: Var = c.input('VsPu',supplement0)
    vr: Var = c.input('VrPu',Const(1.))
    vi: Var = c.input('ViPu',Const(0.))
    ir: Var = c.input('IrPu',Const(.5))
    ii: Var = c.input('IiPu',Const(0.))
    current: Var = c.input('IfdPu',Const(1.))
    minimum: Var = c.input('UelPu',minimum0)
    maximum: Var = c.input('OelPu',Const(1.))
    cosine: Expr = sym.cos(theta*Const(math.pi/180.))
    sine: Expr = sym.sin(theta*Const(math.pi/180.))
    source_real: Expr = kp*(cosine*(vr-xl*ii)-sine*(vi+xl*ir))-ki*ii
    source_imag: Expr = kp*(sine*(vr-xl*ii)+cosine*(vi+xl*ir))+ki*ir
    potential: Var = c.algebraic('PotentialPu',sym.sqrt(source_real**2+source_imag**2),sym.sqrt(source_real**2+source_imag**2))
    loading: Expr = sym.safe_divide(kc*current,potential,1.)
    supply: Var = c.algebraic('SupplyPu',sym.min(vbmax,potential*_esst3a_fex(loading)),sym.min(vbmax,potential*_esst3a_fex(loading)))
    inner0: Expr = field0/supply
    inner_error0: Expr = Const(0.) if p.kim > 0 else inner0/kpm
    regulator0: Expr = kg*field0+inner_error0
    error0: Expr = Const(0.) if p.kir > 0 else regulator0/kpr
    c.block.init_eqs[reference] = voltage0+error0-supplement0-minimum0
    c.block.init_eqs[maximum] = inner0
    field: Var = vf.add_var('EfdPu_'+c.name)
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    error: Expr = reference+supplement+minimum-measured
    integral: Var = c.differential(vf.add_var('VoltageIntegralPu_'+c.name),kir*error,regulator0,
        vrmin-kpr*error,vrmax-kpr*error) if p.kir > 0 else c.algebraic('VoltageIntegralPu',Const(0.),Const(0.))
    demand: Var = c.algebraic('VoltageDemandPu',sym.hard_sat(kpr*error+integral,vrmin,vrmax),regulator0)
    regulator: Var = c.lag('RegulatorPu',demand,ta,p.ta,regulator0)
    inner_error: Expr = regulator-kg*field
    inner_integral: Var = c.differential(vf.add_var('FieldIntegralPu_'+c.name),kim*inner_error,inner0,
        vmmin-kpm*inner_error,vmmax-kpm*inner_error) if p.kim > 0 else c.algebraic('FieldIntegralPu',Const(0.),Const(0.))
    pre_maximum: Var = c.algebraic('PreMaximumPu',sym.hard_sat(kpm*inner_error+inner_integral,vmmin,vmmax),inner0)
    # Solve the monotone inner feedback before clipping, avoiding iterative proportional feedback.
    unconstrained: Expr = (kpm*regulator+inner_integral)/(Const(1.)+kpm*kg*supply)
    delivered: Expr = supply*sym.min(sym.hard_sat(unconstrained,vmmin,vmmax),maximum)
    c.block.algebraic_vars.append(field)
    c.block.algebraic_eqs.append(field-delivered)
    c.block.init_eqs[field] = field0
    return c.finish((field,pre_maximum),'Cascaded bounded PI excitation with loaded compound-transformer supply')
