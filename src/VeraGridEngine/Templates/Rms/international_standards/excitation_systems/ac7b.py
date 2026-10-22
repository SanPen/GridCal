# SPDX-License-Identifier: MPL-2.0
"""Cascaded PID/PI regulation of a brushless field with mixed voltage/current feedback."""
from __future__ import annotations
import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.cascaded_brushless_circuit import CascadedBrushlessCircuit, CascadedLimiterLocation, CascadedPowerSupply
from VeraGridEngine.Templates.Rms.compound_excitation_supply import CompoundSupplyParameters, build_compound_supply
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import CompoundExcitationSource, CompoundSupplementLocation
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import _quadratic_saturation_coefficients
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac8b import initial_internal_exciter_voltage
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class CascadedBrushlessParameters:
    """Voltage PID, field PI, mixed feedback, supply and rotating-field coefficients."""
    __slots__ = ('tr','kpr','kir','kdr','tdr','vrmax','vrmin','kpa','kia','vamax','vamin','kp','kl',
                 'kf1','kf2','kf3','tf3','kc','kd','ke','te','vfemax','vemin','e1','se1','e2','se2')

    def __init__(self, tr: float = .02, kpr: float = 20., kir: float = 10., kdr: float = .05,
                 tdr: float = .05, vrmax: float = 5., vrmin: float = -5., kpa: float = 2.,
                 kia: float = 5., vamax: float = 5., vamin: float = -5., kp: float = 1., kl: float = .2,
                 kf1: float = .2, kf2: float = .1, kf3: float = .05, tf3: float = .1,
                 kc: float = .1, kd: float = .1, ke: float = 1., te: float = .5,
                 vfemax: float = 5., vemin: float = 0., e1: float = 3., se1: float = .1,
                 e2: float = 4., se2: float = .3) -> None:
        """Store independent gains, physical limits and saturation samples.

        :param tr: Nonnegative voltage sensing time, seconds.
        :param kpr: Nonnegative voltage proportional gain.
        :param kir: Nonnegative voltage integral gain, inverse seconds.
        :param kdr: Nonnegative voltage derivative gain, seconds.
        :param tdr: Derivative filter time, seconds; positive when enabled.
        :param vrmax: Outer PID upper capability.
        :param vrmin: Outer PID lower capability.
        :param kpa: Nonnegative inner proportional gain.
        :param kia: Nonnegative inner integral gain, inverse seconds.
        :param vamax: Inner PI upper capability.
        :param vamin: Inner PI lower capability.
        :param kp: Nonnegative terminal supply gain; exact zero selects independent unity supply.
        :param kl: Nonnegative negative-forcing floor coefficient.
        :param kf1: Nonnegative delivered-field voltage feedback gain.
        :param kf2: Nonnegative winding-current-equivalent feedback gain.
        :param kf3: Nonnegative winding-current rate feedback gain, seconds.
        :param tf3: Rate feedback filter time, seconds; positive when enabled.
        :param kc: Nonnegative output diode commutation loading.
        :param kd: Nonnegative generator-current demagnetization gain.
        :param ke: Positive rotating-field resistance coefficient.
        :param te: Positive rotating-field time, seconds.
        :param vfemax: Positive winding-current-equivalent ceiling.
        :param vemin: Nonnegative internal field-voltage lower stop.
        :param e1: First positive voltage saturation sample.
        :param se1: First nonnegative saturation factor.
        :param e2: Second positive voltage saturation sample, in either order.
        :param se2: Second nonnegative saturation factor.
        """
        self.tr: float = tr
        self.kpr: float = kpr
        self.kir: float = kir
        self.kdr: float = kdr
        self.tdr: float = tdr
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.kpa: float = kpa
        self.kia: float = kia
        self.vamax: float = vamax
        self.vamin: float = vamin
        self.kp: float = kp
        self.kl: float = kl
        self.kf1: float = kf1
        self.kf2: float = kf2
        self.kf3: float = kf3
        self.tf3: float = tf3
        self.kc: float = kc
        self.kd: float = kd
        self.ke: float = ke
        self.te: float = te
        self.vfemax: float = vfemax
        self.vemin: float = vemin
        self.e1: float = e1
        self.se1: float = se1
        self.e2: float = e2
        self.se2: float = se2


def build_cascaded_brushless_exciter(vf: VarFactory, name: str | None = None,
                        parameters: CascadedBrushlessParameters | None = None,
                        circuit: CascadedBrushlessCircuit | None = None) -> RmsModelTemplate:
    """Build cascaded voltage PID and field PI control with mixed feedback.

    Reference, supplement and signed excitation-limit additions oppose filtered
    voltage and winding-current washout feedback. Outer PID demand is bounded
    independently at VRMIN/VRMAX. Delivered field times KF1 and winding current
    equivalent times KF2 subtract before the separately bounded inner PI. Both
    integrators stop only when they drive total controller demand farther outside
    their own capabilities. Proportional and derivative paths remain responsive.

    Inner PI times KP and actual terminal magnitude drives the rotating field;
    exact zero KP bypasses that multiplier with independent unity supply. A
    separate instantaneous lower forcing bound is -KL*VFE, not a damping term
    subtracted from every operating point. Winding balance subtracts VFE through
    TE. VFE comprises KE*VE, quadratic magnetic loss and KD*IFD. Directional
    winding stops enforce VEMIN and the current-equivalent VFEMAX ceiling.
    A loaded diode bridge converts internal VE into delivered EFD.

    Seven inputs are sensed voltage, reference, supplement, generator field
    current, actual terminal magnitude and minimum/maximum excitation additions.
    Outputs are delivered field, bounded voltage PID and bounded field PI.
    Voltages/currents use compatible per-unit bases; times are seconds. Six
    memories exist with active integral, derivative, sensing and rate feedback.
    Disabled paths and zero sensing time reduce exactly without small constants.

    Initialization inverts the loaded diode bridge, balances winding loss and
    divides forcing by actual supply. Each active integral stores its required
    demand; a proportional offset supplies it when that integral is disabled.
    Actual auxiliary biases determine reference. Both voltage saturation samples
    may appear in either order, provided voltage and excess magnetic loss are
    strictly monotonic. Two zero factors disable saturation. Initial supply and
    all controller/winding capabilities must admit the operating point. Changing
    a structurally disabled gain to active requires rebuilding the template.

    :param vf: Shared native symbolic factory.
    :param name: Optional controller label.
    :param parameters: Independent cascaded-control and physical field settings.
    :param circuit: Optional compound/self-excited supply and explicit takeover topology.
    :return: Native cascaded brushless excitation with explicit mixed feedback.
    :raises ValueError: Invalid domains, improper filters or magnetic calibration.
    """
    p: CascadedBrushlessParameters = CascadedBrushlessParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.tr,p.kpr,p.kir,p.kdr,p.tdr,p.vrmax,p.vrmin,p.kpa,p.kia,p.vamax,p.vamin,
        p.kp,p.kl,p.kf1,p.kf2,p.kf3,p.tf3,p.kc,p.kd,p.ke,p.te,p.vfemax,p.vemin,p.e1,p.se1,p.e2,p.se2)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Cascaded brushless coefficients must be finite')
    elif min(p.tr,p.kpr,p.kir,p.kdr,p.tdr,p.kpa,p.kia,p.kp,p.kl,p.kf1,p.kf2,p.kf3,p.tf3,p.kc,p.kd,p.vemin,p.e1,p.se1,p.e2,p.se2) < 0 or min(p.ke,p.te,p.vfemax,p.kpr+p.kir,p.kpa+p.kia) <= 0:
        raise ValueError('Cascaded brushless gains, times, field or steady control have invalid domains')
    elif p.kdr > 0 and p.tdr == 0 or p.kf3 > 0 and p.tf3 == 0:
        raise ValueError('Enabled derivative and rate feedback require positive filter times')
    elif p.vrmax <= p.vrmin or p.vamax <= p.vamin:
        raise ValueError('Cascaded controller capabilities must be independently ordered')
    elif (p.se1 == 0) != (p.se2 == 0):
        raise ValueError('Magnetic saturation requires two positive samples or two disabled samples')
    elif p.se1 > 0 and (min(p.e1,p.e2) <= 0 or p.e1 == p.e2 or (p.e2-p.e1)*(p.e2*p.se2-p.e1*p.se1) <= 0):
        raise ValueError('Saturation voltage and excess-field samples must be strictly monotonic')
    else:
        pass
    if circuit is not None:
        if not all(math.isfinite(value) for value in (circuit.ki,circuit.xl,circuit.theta,circuit.kc1,circuit.vbmax,circuit.kr)) or min(circuit.ki,circuit.xl,circuit.kc1,circuit.kr) < 0:
            raise ValueError('Extended cascaded circuit coefficients must be finite and physically ordered')
        elif not isinstance(circuit.source,CompoundExcitationSource) or not isinstance(circuit.power_supply,CascadedPowerSupply) or not isinstance(circuit.supplement_location,CompoundSupplementLocation):
            raise ValueError('Cascaded supply or supplementary selection is invalid')
        elif not isinstance(circuit.minimum_location,CascadedLimiterLocation) or circuit.minimum_location == CascadedLimiterLocation.FIELD_OUTPUT_GATE or not isinstance(circuit.maximum_location,CascadedLimiterLocation):
            raise ValueError('Cascaded limiter selection is invalid')
        elif circuit.power_supply == CascadedPowerSupply.SELF_EXCITED and circuit.kr <= 0:
            raise ValueError('Self-excitation requires positive delivered-field power gain')
        else:
            pass
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'AC7B' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    kpr: Var = c.parameter('KPR',p.kpr)
    kir: Var = c.parameter('KIR',p.kir)
    kdr: Var = c.parameter('KDR',p.kdr)
    tdr: Var = c.parameter('TDR',p.tdr)
    vrmax: Var = c.parameter('VRMAX',p.vrmax)
    vrmin: Var = c.parameter('VRMIN',p.vrmin)
    kpa: Var = c.parameter('KPA',p.kpa)
    kia: Var = c.parameter('KIA',p.kia)
    vamax: Var = c.parameter('VAMAX',p.vamax)
    vamin: Var = c.parameter('VAMIN',p.vamin)
    kp: Var = c.parameter('KP',p.kp)
    kl: Var = c.parameter('KL',p.kl)
    kf1: Var = c.parameter('KF1',p.kf1)
    kf2: Var = c.parameter('KF2',p.kf2)
    kf3: Var = c.parameter('KF3',p.kf3)
    tf3: Var = c.parameter('TF3',p.tf3)
    kc: Var = c.parameter('KC',p.kc)
    kd: Var = c.parameter('KD',p.kd)
    ke: Var = c.parameter('KE',p.ke)
    te: Var = c.parameter('TE',p.te)
    vfemax: Var = c.parameter('VFEMAX',p.vfemax)
    vemin: Var = c.parameter('VEMIN',p.vemin)
    field0: Var = c.parameter('Efd0Pu',1.)
    current0: Var = c.parameter('Ifd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    terminal0: Var = c.parameter('Vt0Pu',1.)
    auxiliary0: Expr = c.parameter('Aux0Pu',0.) if circuit is None else Const(0.)
    supplement0: Expr = c.parameter('Vs0Pu',0.) if circuit is not None else Const(0.)
    minimum0: Expr = c.parameter('Uel0Pu',0.) if circuit is not None else Const(0.)
    maximum0: Expr = c.parameter('Oel0Pu',0.) if circuit is not None else Const(0.)
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0)
    supplement: Var = c.input('VsPu',supplement0)
    vr: Var | None = None
    vi: Var | None = None
    ir: Var | None = None
    ii: Var | None = None
    if circuit is not None:
        vr = c.input('VrPu',Const(1.))
        vi = c.input('ViPu',Const(0.))
        ir = c.input('IrPu',Const(.5))
        ii = c.input('IiPu',Const(0.))
    else:
        pass
    current: Var = c.input('IfdPu',current0)
    terminal: Expr = c.input('VtPu',terminal0) if circuit is None else Const(1.)
    minimum: Var = c.input('UelPu',minimum0)
    maximum: Var = c.input('OelPu',maximum0)
    winding0: Expr = initial_internal_exciter_voltage(field0,kc*current0)
    winding: Var = vf.add_var('InternalVoltagePu_'+c.name)
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
        coefficient: Expr
        threshold,coefficient = _quadratic_saturation_coefficients(e1,se1,e2,se2)
        loss = coefficient*sym.max(winding-threshold,Const(0.))**2
        loss0 = coefficient*sym.max(winding0-threshold,Const(0.))**2
    equivalent0: Expr = ke*winding0+loss0+kd*current0
    equivalent: Var = c.algebraic('CurrentEquivalentPu',ke*winding+loss+kd*current,equivalent0)
    delivered: Expr = winding*_esst3a_fex(sym.safe_divide(kc*current,winding,1.))
    field: Var = c.algebraic('EfdPu',delivered,field0)
    supply0: Expr
    supply: Expr
    if circuit is None:
        supply0 = Const(1.) if p.kp == 0 else kp*terminal0
        supply = Const(1.) if p.kp == 0 else kp*terminal
    elif circuit.power_supply == CascadedPowerSupply.SELF_EXCITED:
        self_gain: Var = c.parameter('KR',circuit.kr)
        supply = self_gain*field
        supply0 = self_gain*field0
    else:
        assert vr is not None and vi is not None and ir is not None and ii is not None
        supply = build_compound_supply(c,vr,vi,ir,ii,equivalent,CompoundSupplyParameters(
            kp=p.kp,ki=circuit.ki,xl=circuit.xl,theta=circuit.theta,kc=circuit.kc1,
            vbmax=circuit.vbmax,source=circuit.source),voltage_gain=kp)
        supply0 = supply
    inner0: Expr = equivalent0/supply0
    inner_error0: Expr = Const(0.) if p.kia > 0 else inner0/kpa
    outer0: Expr = kf1*field0+kf2*equivalent0+inner_error0
    error0: Expr = Const(0.) if p.kir > 0 else outer0/kpr
    if circuit is None:
        c.block.init_eqs[reference] = voltage0+error0-auxiliary0
    else:
        c.block.init_eqs[reference] = voltage0+error0-supplement0-(minimum0 if circuit.minimum_location == CascadedLimiterLocation.ERROR_SUM else Const(0.))-(maximum0 if circuit.maximum_location == CascadedLimiterLocation.ERROR_SUM else Const(0.))
        c.block.init_eqs[minimum] = error0-(supplement0 if circuit.supplement_location == CompoundSupplementLocation.AFTER_MINIMUM_GATE else Const(0.)) if circuit.minimum_location == CascadedLimiterLocation.ERROR_GATE else outer0 if circuit.minimum_location == CascadedLimiterLocation.VOLTAGE_OUTPUT_GATE else minimum0
        c.block.init_eqs[maximum] = error0 if circuit.maximum_location == CascadedLimiterLocation.ERROR_GATE else outer0 if circuit.maximum_location == CascadedLimiterLocation.VOLTAGE_OUTPUT_GATE else inner0 if circuit.maximum_location == CascadedLimiterLocation.FIELD_OUTPUT_GATE else maximum0
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    rate: Expr = c.washout('RateFeedbackPu',equivalent,tf3,p.tf3,kf3/tf3,equivalent0) if p.kf3 > 0 else Const(0.)
    error: Expr = reference-measured-rate
    if circuit is None:
        error = error+supplement+minimum+maximum
    else:
        error = error+(supplement if circuit.supplement_location == CompoundSupplementLocation.ERROR_SUM else Const(0.))+(minimum if circuit.minimum_location == CascadedLimiterLocation.ERROR_SUM else Const(0.))+(maximum if circuit.maximum_location == CascadedLimiterLocation.ERROR_SUM else Const(0.))
    pre_minimum: Var = c.algebraic('PreMinimumInputPu',error,error0-(supplement0 if circuit is not None and circuit.supplement_location == CompoundSupplementLocation.AFTER_MINIMUM_GATE else Const(0.)))
    if circuit is not None and circuit.minimum_location == CascadedLimiterLocation.ERROR_GATE:
        error = sym.max(error,minimum)
    else:
        pass
    if circuit is not None and circuit.supplement_location == CompoundSupplementLocation.AFTER_MINIMUM_GATE:
        error = error+supplement
    else:
        pass
    pre_maximum: Var = c.algebraic('PreMaximumInputPu',error,error0)
    if circuit is not None and circuit.maximum_location == CascadedLimiterLocation.ERROR_GATE:
        error = sym.min(error,maximum)
    else:
        pass
    derivative: Expr = c.washout('DerivativePu',error,tdr,p.tdr,kdr/tdr,error0) if p.kdr > 0 else Const(0.)
    outer_nonintegral: Expr = kpr*error+derivative
    outer_integral: Expr = c.differential(vf.add_var('VoltageIntegralPu_'+c.name),kir*error,outer0,vrmin-outer_nonintegral,vrmax-outer_nonintegral) if p.kir > 0 else Const(0.)
    outer: Var = c.algebraic('VoltageDemandPu',sym.hard_sat(outer_nonintegral+outer_integral,vrmin,vrmax),outer0)
    selected_outer: Expr = sym.max(outer,minimum) if circuit is not None and circuit.minimum_location == CascadedLimiterLocation.VOLTAGE_OUTPUT_GATE else outer
    pre_maximum_voltage: Var = c.algebraic('PreMaximumVoltagePu',selected_outer,outer0)
    if circuit is not None and circuit.maximum_location == CascadedLimiterLocation.VOLTAGE_OUTPUT_GATE:
        selected_outer = sym.min(selected_outer,maximum)
    else:
        pass
    inner_error: Expr = selected_outer-kf1*field-kf2*equivalent
    inner_nonintegral: Expr = kpa*inner_error
    inner_integral: Expr = c.differential(vf.add_var('FieldIntegralPu_'+c.name),kia*inner_error,inner0,vamin-inner_nonintegral,vamax-inner_nonintegral) if p.kia > 0 else Const(0.)
    inner: Var = c.algebraic('FieldDemandPu',sym.hard_sat(inner_nonintegral+inner_integral,vamin,vamax),inner0)
    # Negative forcing is a separate capability floor, not an extra steady damping loss.
    selected_inner: Expr = sym.min(inner,maximum) if circuit is not None and circuit.maximum_location == CascadedLimiterLocation.FIELD_OUTPUT_GATE else inner
    forcing: Var = c.algebraic('FieldForcingPu',sym.max(supply*selected_inner,-kl*equivalent),equivalent0)
    winding_upper: Expr = (vfemax-kd*current-loss)/ke
    c.differential(winding,(forcing-equivalent)/te,winding0,vemin,winding_upper)
    outputs: tuple[Var,...] = (field,outer,inner) if circuit is None else (field,pre_minimum,pre_maximum,outer,pre_maximum_voltage,inner)
    return c.finish(outputs,'Cascaded voltage PID and field PI with mixed feedback and bounded brushless field')


def build_ac7b_template(vf: VarFactory, name: str | None = None,
                        parameters: CascadedBrushlessParameters | None = None) -> RmsModelTemplate:
    """Build terminal-fed cascaded voltage PID and field PI excitation.

    Seven inputs provide sensing, reference, supplement, field current, terminal
    magnitude and signed minimum/maximum additions. Outputs are field voltage,
    voltage PID and field PI demands. Six full-order memories balance mixed
    field/current feedback and winding-current washout. KP=0 explicitly bypasses
    terminal multiplication with unity supply. A -KL*VFE floor limits negative
    forcing. See :func:`build_cascaded_brushless_exciter` for equations, per-unit
    bases, initialization, structural reductions and operating-point constraints.

    :param vf: Shared native symbolic factory.
    :param name: Optional controller label.
    :param parameters: Cascaded regulation and rotating-field coefficients.
    :return: Native seven-input, three-output cascaded excitation controller.
    :raises ValueError: Invalid domains or magnetic calibration.
    """
    return build_cascaded_brushless_exciter(vf,name,parameters)
