# SPDX-License-Identifier: MPL-2.0
"""Bounded PID voltage regulation of a rotating exciter with loaded diode rectification."""
from __future__ import annotations

import math
from VeraGridEngine.Templates.Rms.self_feedback_exciter import ExcitationLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import CompoundExcitationSource, CompoundSupplementLocation
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.compound_excitation_supply import CompoundSupplyParameters, build_compound_supply
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import _quadratic_saturation_coefficients
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class PidBrushlessExciterParameters:
    """Physical PID, amplifier, winding, saturation and commutation coefficients."""
    __slots__ = ('tr','kpr','kir','kdr','tdr','vpidmax','vpidmin','ka','ta','vrmax','vrmin','kc','kd','ke','te','vfemax','vemin','e1','se1','e2','se2')

    def __init__(self, tr: float = 0.02, kpr: float = 20.0, kir: float = 10.0, kdr: float = 0.05,
                 tdr: float = 0.05, vpidmax: float = 5.0, vpidmin: float = -5.0, ka: float = 20.0,
                 ta: float = 0.05, vrmax: float = 5.0, vrmin: float = -5.0, kc: float = 0.1,
                 kd: float = 0.1, ke: float = 1.0, te: float = 0.5, vfemax: float = 5.0,
                 vemin: float = 0.0, e1: float = 3.0, se1: float = 0.1, e2: float = 4.0,
                 se2: float = 0.3) -> None:
        """Store independent regulator, winding and magnetic calibration constants.

        :param tr: Nonnegative sensing time, in seconds.
        :param kpr: Nonnegative proportional gain.
        :param kir: Nonnegative integral gain, per second.
        :param kdr: Nonnegative derivative gain, in seconds.
        :param tdr: Positive derivative filter time when derivative action is enabled.
        :param vpidmax: Upper total PID demand.
        :param vpidmin: Lower total PID demand.
        :param ka: Positive amplifier gain.
        :param ta: Nonnegative amplifier time in seconds.
        :param vrmax: Upper non-windup amplifier output.
        :param vrmin: Lower non-windup amplifier output.
        :param kc: Nonnegative diode commutation loading coefficient.
        :param kd: Nonnegative current demagnetization coefficient.
        :param ke: Positive rotating-field resistance coefficient.
        :param te: Positive rotating-field time in seconds.
        :param vfemax: Positive current-equivalent field ceiling.
        :param vemin: Nonnegative lower internal field-voltage stop.
        :param e1: First internal-voltage saturation sample.
        :param se1: Saturation factor at the first voltage.
        :param e2: Second internal-voltage saturation sample.
        :param se2: Saturation factor at the second voltage.
        """
        self.tr: float = tr
        self.kpr: float = kpr
        self.kir: float = kir
        self.kdr: float = kdr
        self.tdr: float = tdr
        self.vpidmax: float = vpidmax
        self.vpidmin: float = vpidmin
        self.ka: float = ka
        self.ta: float = ta
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
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


def initial_internal_exciter_voltage(field: Expr, loading: Expr) -> Expr:
    """Invert the three conducting branches of the diode commutation law.

    Each candidate solves ``Efd=VE*FEX(loading/VE)`` analytically in its own
    open interval. Nonpositive current loading selects the unloaded branch.
    Published rounded transition coefficients are retained, so their narrow
    transition gaps are not smoothed into an invented commutation law.

    :param field: Nonnegative delivered field voltage at equilibrium.
    :param loading: Commutating reactance times initial field current.
    :return: Internal-voltage candidate for equilibrium initialization.
    """
    first: Expr = field+Const(.577)*loading
    middle: Expr = sym.sqrt((field**2+loading**2)/Const(.75))
    last: Expr = field/Const(1.732)+loading
    first_region: Expr = sym.heaviside(first-loading/Const(.433))
    middle_region: Expr = sym.heaviside(middle-loading/Const(.75))
    conducting: Expr = first_region*first+(Const(1.)-first_region)*(
        middle_region*middle+(Const(1.)-middle_region)*last)
    positive: Expr = sym.heaviside(loading)
    return positive*conducting+(Const(1.)-positive)*field


class CompoundPidPowerCircuit:
    """Potential circuit and physical limiter insertion choices for rotating excitation."""
    __slots__ = ('kp','ki','xl','theta','kc1','vbmax','source','minimum_location','maximum_location','supplement_location')

    def __init__(self, kp: float = 1., ki: float = 0., xl: float = 0., theta: float = 0.,
                 kc1: float = 0., vbmax: float = 5.,
                 source: CompoundExcitationSource = CompoundExcitationSource.INDEPENDENT,
                 minimum_location: ExcitationLimiterLocation = ExcitationLimiterLocation.REFERENCE_SUM,
                 maximum_location: ExcitationLimiterLocation = ExcitationLimiterLocation.REFERENCE_SUM,
                 supplement_location: CompoundSupplementLocation = CompoundSupplementLocation.ERROR_SUM) -> None:
        """Store explicit supply and insertion settings.

        :param kp: Potential voltage gain, positive for independent operation.
        :param ki: Nonnegative compound current gain.
        :param xl: Nonnegative potential-circuit reactance.
        :param theta: Potential phase angle, degrees.
        :param kc1: Nonnegative source-bridge commutation loading coefficient.
        :param vbmax: Positive available exciter-field supply ceiling.
        :param source: Terminal compound or independent potential.
        :param minimum_location: Sum, input gate or post-PID gate.
        :param maximum_location: Sum, input gate or post-PID gate.
        :param supplement_location: Supplement before or after input minimum gate.
        """
        self.kp: float = kp
        self.ki: float = ki
        self.xl: float = xl
        self.theta: float = theta
        self.kc1: float = kc1
        self.vbmax: float = vbmax
        self.source: CompoundExcitationSource = source
        self.minimum_location: ExcitationLimiterLocation = minimum_location
        self.maximum_location: ExcitationLimiterLocation = maximum_location
        self.supplement_location: CompoundSupplementLocation = supplement_location


def build_pid_brushless_exciter(vf: VarFactory, name: str | None = None,
                        parameters: PidBrushlessExciterParameters | None = None,
                        circuit: CompoundPidPowerCircuit | None = None) -> RmsModelTemplate:
    """Build bounded PID regulation of a brushless rotating excitation machine.

    Sensed voltage opposes reference and additive stabilizing/minimum/maximum
    excitation signals. The parallel PID transfer is KPR+KIR/s+s*KDR/(1+s*TDR).
    Its total demand is clipped at VPIDMIN/VPIDMAX, with conditional integral
    stops based on proportional, integral and derivative contributions together.
    A separate KA/(1+s*TA) amplifier has its own directional VRMIN/VRMAX stops.

    Amplifier forcing drives the rotating field through TE. Losses comprise
    linear resistance KE*VE, quadratic excess magnetic field and KD times live
    generator field current. The lower stop is VEMIN. The independent upper
    stop is detected by total current-equivalent field VFE reaching VFEMAX;
    it stops outward motion while preserving inward recovery when current moves
    the ceiling past continuous winding memory. No state reset is invented.

    A loaded diode bridge gives EFD=VE*FEX(KC*IFD/VE). The standard unloaded,
    linear, square-root, final-linear and blocked commutation branches are
    retained. Safe division defines the zero-voltage boundary. Initial VE is
    recovered analytically from the appropriate conducting branch, rather than
    treating delivered EFD as internal VE. Rounded commutation transition gaps
    retain their original piecewise behavior and require operating-point checks.

    Six inputs are sensed voltage, reference, supplement, field current,
    minimum-excitation addition and maximum-excitation addition. Outputs are
    delivered field, total current-equivalent field and bounded PID demand.
    Voltages and currents use compatible machine/field bases; time constants
    are seconds. Five memories are present with active integral/derivative
    action and positive sensing/amplifier times. Disabled PID channels and zero
    sensing/amplifier times remove their memories exactly. TE remains positive.

    Initial winding losses seed amplifier and PID demand. Active integral
    action stores that demand at zero voltage error; proportional-only control
    uses the required initial error instead. The reference includes actual
    auxiliary biases. Two zero saturation factors remove magnetic saturation;
    otherwise increasing voltage/excess-field samples determine the quadratic
    threshold and coefficient. Initial capabilities must admit the operating
    point, including the current-dependent ceiling and diode commutation branch.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Physical PID, winding, bridge and capability coefficients.
    :param circuit: Optional compound supply and selectable limiter topology.
    :return: Native PID brushless excitation with explicit winding and diode bridge.
    :raises ValueError: Invalid coefficient domains or magnetic calibration.
    """
    p: PidBrushlessExciterParameters = PidBrushlessExciterParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.tr,p.kpr,p.kir,p.kdr,p.tdr,p.vpidmax,p.vpidmin,p.ka,p.ta,
        p.vrmax,p.vrmin,p.kc,p.kd,p.ke,p.te,p.vfemax,p.vemin,p.e1,p.se1,p.e2,p.se2)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('PID brushless excitation coefficients must be finite')
    elif min(p.tr,p.kpr,p.kir,p.kdr,p.tdr,p.ta,p.kc,p.kd,p.vemin,p.e1,p.se1,p.e2,p.se2) < 0:
        raise ValueError('PID brushless gains, times, stops and saturation samples must be nonnegative')
    elif min(p.ka,p.ke,p.te,p.vfemax) <= 0 or p.kpr+p.kir == 0:
        raise ValueError('Brushless excitation requires positive amplifier, resistance, field time and steady regulator action')
    elif p.kdr > 0 and p.tdr == 0:
        raise ValueError('Enabled PID derivative action requires positive filter time')
    elif p.vpidmax <= p.vpidmin or p.vrmax <= p.vrmin:
        raise ValueError('PID and amplifier bounds must be independently ordered')
    elif (p.se1 == 0) != (p.se2 == 0):
        raise ValueError('Magnetic saturation requires two positive samples or two disabled samples')
    elif p.se1 > 0 and (p.e1 <= 0 or p.e2 <= p.e1 or p.e2*p.se2 <= p.e1*p.se1):
        raise ValueError('Enabled magnetic saturation requires increasing voltage and excess-field samples')
    else:
        pass
    if circuit is not None:
        if not all(math.isfinite(value) for value in (circuit.kp,circuit.ki,circuit.xl,circuit.theta,circuit.kc1,circuit.vbmax)) or min(circuit.kp,circuit.ki,circuit.xl,circuit.kc1) < 0 or circuit.vbmax <= 0:
            raise ValueError('Compound PID supply coefficients have invalid domains')
        elif circuit.kp+circuit.ki == 0:
            raise ValueError('Compound rotating-exciter supply cannot have identically zero potential')
        elif circuit.source == CompoundExcitationSource.INDEPENDENT and circuit.kp <= 0:
            raise ValueError('Independent rotating-exciter supply requires positive potential')
        elif circuit.minimum_location not in tuple(ExcitationLimiterLocation) or circuit.maximum_location not in tuple(ExcitationLimiterLocation) or circuit.source not in tuple(CompoundExcitationSource) or circuit.supplement_location not in tuple(CompoundSupplementLocation):
            raise ValueError('Compound PID circuit selections are invalid')
        else:
            pass
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'AC8B' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    kpr: Var = c.parameter('KPR',p.kpr)
    kir: Var = c.parameter('KIR',p.kir)
    kdr: Var = c.parameter('KDR',p.kdr)
    tdr: Var = c.parameter('TDR',p.tdr)
    pidmax: Var = c.parameter('VPIDMAX',p.vpidmax)
    pidmin: Var = c.parameter('VPIDMIN',p.vpidmin)
    ka: Var = c.parameter('KA',p.ka)
    ta: Var = c.parameter('TA',p.ta)
    vrmax: Var = c.parameter('VRMAX',p.vrmax)
    vrmin: Var = c.parameter('VRMIN',p.vrmin)
    kc: Var = c.parameter('KC',p.kc)
    kd: Var = c.parameter('KD',p.kd)
    ke: Var = c.parameter('KE',p.ke)
    te: Var = c.parameter('TE',p.te)
    vfemax: Var = c.parameter('VFEMAX',p.vfemax)
    vemin: Var = c.parameter('VEMIN',p.vemin)
    e1: Var = c.parameter('E1',p.e1)
    se1: Var = c.parameter('SE1',p.se1)
    e2: Var = c.parameter('E2',p.e2)
    se2: Var = c.parameter('SE2',p.se2)
    field0: Var = c.parameter('Efd0Pu',1.)
    current0: Var = c.parameter('Ifd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    auxiliary0: Var = c.parameter('Aux0Pu',0.)
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0)
    supplement: Var = c.input('VsPu',Const(0.))
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
    minimum0: Expr = c.parameter('Uel0Pu',0.) if circuit is not None else Const(0.)
    maximum0: Expr = c.parameter('Oel0Pu',0.) if circuit is not None else Const(0.)
    supplement0: Expr = c.parameter('Vs0Pu',0.) if circuit is not None else Const(0.)
    minimum: Var = c.input('UelPu',minimum0)
    maximum: Var = c.input('OelPu',maximum0)
    winding0: Expr = initial_internal_exciter_voltage(field0,kc*current0)
    winding: Var = vf.add_var('InternalVoltagePu_'+c.name)
    loss: Expr
    initial_loss: Expr
    if p.se1 == 0 and p.se2 == 0:
        loss = Const(0.)
        initial_loss = Const(0.)
    else:
        threshold: Expr
        coefficient: Expr
        threshold,coefficient = _quadratic_saturation_coefficients(e1,se1,e2,se2)
        loss = coefficient*sym.max(winding-threshold,Const(0.))**2
        initial_loss = coefficient*sym.max(winding0-threshold,Const(0.))**2
    forcing0: Expr = ke*winding0+initial_loss+kd*current0
    equivalent: Var = c.algebraic('CurrentEquivalentPu',ke*winding+loss+kd*current,forcing0)
    supply: Expr = Const(1.)
    if circuit is not None:
        assert vr is not None and vi is not None and ir is not None and ii is not None
        # Source commutation loads the exciter winding, distinct from the output bridge's IFD.
        supply = build_compound_supply(c,vr,vi,ir,ii,equivalent,CompoundSupplyParameters(
            kp=circuit.kp,ki=circuit.ki,xl=circuit.xl,theta=circuit.theta,kc=circuit.kc1,
            vbmax=circuit.vbmax,source=circuit.source))
    else:
        pass
    regulator0: Expr = forcing0/supply
    pid0: Expr = regulator0/ka
    error0: Expr = Const(0.) if p.kir > 0 else pid0/kpr
    if circuit is None:
        c.block.init_eqs[reference] = voltage0+error0-auxiliary0
    else:
        c.block.init_eqs[reference] = voltage0+error0-supplement0-(minimum0 if circuit.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))-(maximum0 if circuit.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))
        c.block.init_eqs[supplement] = supplement0
        c.block.init_eqs[minimum] = (error0-(supplement0 if circuit.supplement_location == CompoundSupplementLocation.AFTER_MINIMUM_GATE else Const(0.)) if circuit.minimum_location == ExcitationLimiterLocation.REFERENCE_GATE else pid0 if circuit.minimum_location == ExcitationLimiterLocation.OUTPUT_GATE else minimum0)
        c.block.init_eqs[maximum] = error0 if circuit.maximum_location == ExcitationLimiterLocation.REFERENCE_GATE else pid0 if circuit.maximum_location == ExcitationLimiterLocation.OUTPUT_GATE else maximum0
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    error: Expr = reference-measured
    if circuit is None:
        error = error+supplement+minimum+maximum
    else:
        error = error+(supplement if circuit.supplement_location == CompoundSupplementLocation.ERROR_SUM else Const(0.))+(minimum if circuit.minimum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))+(maximum if circuit.maximum_location == ExcitationLimiterLocation.REFERENCE_SUM else Const(0.))
    pre_minimum: Var = c.algebraic('PreMinimumInputPu',error,error0-(supplement0 if circuit is not None and circuit.supplement_location == CompoundSupplementLocation.AFTER_MINIMUM_GATE else Const(0.)))
    if circuit is not None and circuit.minimum_location == ExcitationLimiterLocation.REFERENCE_GATE:
        error = sym.max(error,minimum)
    else:
        pass
    if circuit is not None and circuit.supplement_location == CompoundSupplementLocation.AFTER_MINIMUM_GATE:
        error = error+supplement
    else:
        pass
    pre_maximum: Var = c.algebraic('PreMaximumInputPu',error,error0)
    if circuit is not None and circuit.maximum_location == ExcitationLimiterLocation.REFERENCE_GATE:
        error = sym.min(error,maximum)
    else:
        pass
    derivative: Var = (c.washout('DerivativePu',error,tdr,p.tdr,kdr/tdr,error0)
        if p.kdr > 0 else c.algebraic('DerivativePu',Const(0.),Const(0.)))
    nonintegral: Expr = kpr*error+derivative
    integral: Var = (c.differential(vf.add_var('IntegralPu_'+c.name),kir*error,pid0,
        pidmin-nonintegral,pidmax-nonintegral) if p.kir > 0 else c.algebraic('IntegralPu',Const(0.),Const(0.)))
    pid: Var = c.algebraic('PidDemandPu',sym.hard_sat(nonintegral+integral,pidmin,pidmax),pid0)
    demand: Expr = pid
    if circuit is not None and circuit.minimum_location == ExcitationLimiterLocation.OUTPUT_GATE:
        demand = sym.max(demand,minimum)
    else:
        pass
    pre_maximum_output: Var = c.algebraic('PreMaximumOutputPu',demand,pid0)
    if circuit is not None and circuit.maximum_location == ExcitationLimiterLocation.OUTPUT_GATE:
        demand = sym.min(demand,maximum)
    else:
        pass
    regulator: Var = c.lag('RegulatorPu',ka*demand,ta,p.ta,regulator0,vrmin,vrmax)
    # This positive-resistance bound is exactly the VFE ceiling without dividing by VE or saturation.
    upper: Expr = (vfemax-kd*current-loss)/ke
    c.differential(winding,(regulator*supply-equivalent)/te,winding0,vemin,upper)
    delivered: Expr = winding*_esst3a_fex(sym.safe_divide(kc*current,winding,1.))
    field: Var = c.algebraic('EfdPu',delivered,field0)
    outputs: tuple[Var,...] = (field,equivalent,pid) if circuit is None else (field,pre_minimum,pre_maximum,pid,pre_maximum_output)
    return c.finish(outputs,'Bounded PID excitation with saturated rotating field and loaded diode rectification')


def build_ac8b_template(vf: VarFactory, name: str | None = None,
                        parameters: PidBrushlessExciterParameters | None = None) -> RmsModelTemplate:
    """Build bounded PID regulation with a fixed independent exciter-field supply.

    Six inputs are sensed voltage, reference, supplement, field current and
    additive minimum/maximum excitation. Outputs are field voltage, winding
    current equivalent and PID demand. Five positive-time memories balance
    actual winding losses at initialization; times are seconds and voltage/
    current use compatible field bases. Directional integral and amplifier
    stops preserve inward recovery. Loaded diode rectification and magnetic
    saturation remain explicit. See :func:`build_pid_brushless_exciter`.

    :param vf: Shared symbolic factory.
    :param name: Optional controller label.
    :param parameters: Physical PID, amplifier, winding and diode coefficients.
    :return: Native fixed-supply rotating excitation controller.
    :raises ValueError: Invalid coefficients or magnetic calibration.
    """
    return build_pid_brushless_exciter(vf,name,parameters)
