# SPDX-License-Identifier: MPL-2.0
"""Compound-transformer excitation with an explicit rectifier-loading law and selectable capability location."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class CompoundCapabilityLocation(Enum):
    """Physical placement of the compound-transformer forcing capability."""
    TOTAL_FORCING = 1
    COMPOUND_SUPPLY = 2


class TheveninExciterParameters:
    """Physical regulator, transformer-compounding, field and feedback coefficients."""
    __slots__ = ('tr','ka','ta','regulator_max','regulator_min','te','kf','tf','kp','ki','supply_max','ke')

    def __init__(self, tr: float = .02, ka: float = 20., ta: float = .05,
                 regulator_max: float = 5., regulator_min: float = -5.,
                 te: float = .5, kf: float = .05, tf: float = 1.,
                 kp: float = 1., ki: float = .5, supply_max: float = 2., ke: float = 1.) -> None:
        """Store physical coefficients; graph construction validates their domains.

        :param tr: Nonnegative sensing lag in seconds.
        :param ka: Positive regulator gain.
        :param ta: Nonnegative regulator lag in seconds.
        :param regulator_max: Upper fixed non-windup regulator capability.
        :param regulator_min: Lower fixed non-windup regulator capability.
        :param te: Positive field time in seconds.
        :param kf: Nonnegative field-voltage feedback numerator gain.
        :param tf: Positive field-feedback filter time in seconds.
        :param kp: Positive potential-source compounding gain.
        :param ki: Nonnegative current-source compounding gain on the declared stator-current base.
        :param supply_max: Positive capability at the selected forcing location.
        :param ke: Nonnegative field-circuit resistance coefficient.
        """
        self.tr: float = tr
        self.ka: float = ka
        self.ta: float = ta
        self.regulator_max: float = regulator_max
        self.regulator_min: float = regulator_min
        self.te: float = te
        self.kf: float = kf
        self.tf: float = tf
        self.kp: float = kp
        self.ki: float = ki
        self.supply_max: float = supply_max
        self.ke: float = ke


def build_thevenin_exciter(vf: VarFactory, name: str, location: CompoundCapabilityLocation,
                            parameters: TheveninExciterParameters | None = None) -> RmsModelTemplate:
    """Build field regulation supplied by a current-compounded excitation transformer.

    The transformer potential is the phasor magnitude
    ``abs(KP*Vt+j*KI*It)``. Rectifier loading gives available voltage
    ``sqrt(max(potential**2-(0.78*Ifd)**2,0))``. This direct radicand expression
    is equivalent to the normalized loading law while remaining finite at zero
    potential; no artificial denominator floor or residual fault supply exists.

    In the total-forcing structure, regulator and transformer voltages are summed
    before clipping to zero and the declared forcing capability. In the compound-
    supply structure, only available transformer voltage is upper-clipped before
    adding regulator voltage. These placements yield different initialization
    and disturbance response and are not interchangeable field-output limits.
    A non-windup regulator acts on reference plus supplementary voltage minus
    measured voltage and delivered-field washout. The field equation is
    ``TE*dEfd/dt=forcing-KE*Efd``, with a directional zero lower field stop.

    Eight inputs are sensed voltage, reference, supplementary voltage, terminal
    phasor real/imaginary components, outgoing stator-current real/imaginary
    components and normalized field current. Output is field voltage. The host
    owns all stator-current and field bases. All times use seconds. Four states
    represent sensing, regulator, field-feedback memory and field voltage when
    sensing/regulator times are positive; zero permitted lags become algebraic.
    Initialization balances actual transformer forcing against field losses and
    derives the voltage reference from the required regulator operating point.
    Physical construction uses explicit compounding gains and capability; no
    operating-point design calibration is inferred from a zero gain.

    :param vf: Shared native symbolic variable factory.
    :param name: Unique instance label.
    :param location: Physical capability location in the forcing path.
    :param parameters: Physical regulator, transformer and field coefficients.
    :return: Native compound-transformer excitation controller.
    :raises ValueError: Invalid coefficient domains, limits or capability selection.
    """
    p: TheveninExciterParameters = TheveninExciterParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.tr,p.ka,p.ta,p.regulator_max,p.regulator_min,p.te,p.kf,p.tf,p.kp,p.ki,p.supply_max,p.ke)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Compound-transformer excitation coefficients must be finite')
    elif min(p.ka,p.te,p.tf,p.kp,p.supply_max) <= 0 or min(p.tr,p.ta,p.kf,p.ki,p.ke) < 0:
        raise ValueError('Compound-transformer excitation gains and times have invalid domains')
    elif p.regulator_max <= p.regulator_min:
        raise ValueError('Compound-transformer regulator limits must be ordered')
    elif not isinstance(location,CompoundCapabilityLocation):
        raise ValueError('Compound forcing capability requires an explicit physical location')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,name)
    tr: Var = c.parameter('TR',p.tr)
    ka: Var = c.parameter('KA',p.ka)
    ta: Var = c.parameter('TA',p.ta)
    upper: Var = c.parameter('VRMAX',p.regulator_max)
    lower: Var = c.parameter('VRMIN',p.regulator_min)
    te: Var = c.parameter('TE',p.te)
    kf: Var = c.parameter('KF',p.kf)
    tf: Var = c.parameter('TF',p.tf)
    kp: Var = c.parameter('KP',p.kp)
    ki: Var = c.parameter('KI',p.ki)
    capability: Var = c.parameter('VBMAX',p.supply_max)
    ke: Var = c.parameter('KE',p.ke)
    field0: Var = c.parameter('Efd0Pu',1.)
    sensed: Var = c.input('VmPu',Const(1.))
    reference: Var = c.input('VRefPu',Const(1.))
    supplementary: Var = c.input('VsPu',Const(0.))
    vr: Var = c.input('VrPu',Const(1.))
    vi: Var = c.input('ViPu',Const(0.))
    ir: Var = c.input('IrPu',Const(.5))
    ii: Var = c.input('IiPu',Const(0.))
    current: Var = c.input('IfdPu',Const(1.))
    potential_squared: Expr = (kp*vr-ki*ii)**2+(kp*vi+ki*ir)**2
    loaded: Var = c.algebraic('LoadedSupplyPu',sym.sqrt(sym.max(potential_squared-(Const(.78)*current)**2,Const(0.))),
        sym.sqrt(sym.max(potential_squared-(Const(.78)*current)**2,Const(0.))))
    supply: Var
    if location == CompoundCapabilityLocation.COMPOUND_SUPPLY:
        supply = c.algebraic('SupplyPu',sym.min(loaded,capability),sym.min(loaded,capability))
    else:
        supply = c.algebraic('SupplyPu',loaded,loaded)
    regulator0: Expr = ke*field0-supply
    c.block.init_eqs[reference] = sensed+regulator0/ka
    field: Var = vf.add_var('EfdPu_'+name)
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,sensed)
    feedback: Var = c.washout('FeedbackPu',field,tf,p.tf,kf/tf,field0)
    regulator: Var = c.lag('RegulatorPu',ka*(reference+supplementary-measured-feedback),ta,p.ta,regulator0,lower,upper)
    forcing: Expr = sym.hard_sat(regulator+supply,Const(0.),capability) if location == CompoundCapabilityLocation.TOTAL_FORCING else regulator+supply
    derivative: Expr = (forcing-ke*field)/te
    stopped: Expr = (Const(1.)-(Const(1.)-sym.heaviside(field))*sym.heaviside(-derivative))*derivative
    c.differential(field,stopped,field0)
    return c.finish((field,),'Compound-transformer excitation with loaded voltage and explicitly placed forcing capability')
