# SPDX-License-Identifier: MPL-2.0
"""Electrohydraulic PID gate control with selectable droop feedback and a calibrated turbine characteristic."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class HydroDroopFeedback(Enum):
    """Physical quantity used by the permanent-droop reference loop."""
    ELECTRICAL_POWER = 0
    GATE_POSITION = 1


class PidHydroGovernorParameters:
    """Physical PID, servo, gate-characteristic, water-column and damping coefficients."""
    __slots__ = ('droop','detector_time','kp','ki','kd','controller_time','servo_time','damping',
                 'g0','g1','p1','g2','p2','p3','gate_max','gate_min','water_factor','water_time',
                 'opening_rate','closing_rate','feedback','deadband_low','deadband_high')

    def __init__(self, droop: float = .05, detector_time: float = .02,
                 kp: float = 2., ki: float = 1., kd: float = .1,
                 controller_time: float = .1, servo_time: float = .2, damping: float = .5,
                 g0: float = .08, g1: float = .4, p1: float = .3,
                 g2: float = .7, p2: float = .65, p3: float = 1.,
                 gate_max: float = 1., gate_min: float = 0.,
                 water_factor: float = 1., water_time: float = 1.,
                 opening_rate: float = .2, closing_rate: float = -.15,
                 feedback: HydroDroopFeedback = HydroDroopFeedback.GATE_POSITION,
                 deadband_low: float = 0., deadband_high: float = 0.) -> None:
        """Store the physical controller and turbine settings.

        :param droop: Nonnegative permanent droop gain.
        :param detector_time: Nonnegative droop-error measurement lag in seconds.
        :param kp: Nonnegative proportional gain.
        :param ki: Nonnegative integral gain in inverse seconds.
        :param kd: Nonnegative derivative gain in seconds.
        :param controller_time: Positive shared controller-filter time in seconds.
        :param servo_time: Positive gate-servo time in seconds.
        :param damping: Nonnegative raw-speed turbine damping.
        :param g0: Nonnegative no-load gate opening at zero turbine power.
        :param g1: First intermediate gate coordinate.
        :param p1: Positive power at the first intermediate gate coordinate.
        :param g2: Second intermediate gate coordinate.
        :param p2: Increasing power at the second intermediate gate coordinate.
        :param p3: Increasing power at full gate, whose coordinate is one.
        :param gate_max: Upper gate travel stop.
        :param gate_min: Nonnegative lower gate travel stop.
        :param water_factor: Positive multiplier of water inertia time.
        :param water_time: Positive water inertia time in seconds.
        :param opening_rate: Positive gate opening capability in per unit per second.
        :param closing_rate: Negative gate closing capability in per unit per second.
        :param feedback: Electrical-power or actual-gate permanent-droop feedback.
        :param deadband_low: Nonpositive continuous underspeed threshold.
        :param deadband_high: Nonnegative continuous overspeed threshold.
        """
        self.droop: float = droop
        self.detector_time: float = detector_time
        self.kp: float = kp
        self.ki: float = ki
        self.kd: float = kd
        self.controller_time: float = controller_time
        self.servo_time: float = servo_time
        self.damping: float = damping
        self.g0: float = g0
        self.g1: float = g1
        self.p1: float = p1
        self.g2: float = g2
        self.p2: float = p2
        self.p3: float = p3
        self.gate_max: float = gate_max
        self.gate_min: float = gate_min
        self.water_factor: float = water_factor
        self.water_time: float = water_time
        self.opening_rate: float = opening_rate
        self.closing_rate: float = closing_rate
        self.feedback: HydroDroopFeedback = feedback
        self.deadband_low: float = deadband_low
        self.deadband_high: float = deadband_high


def build_pidgov_template(vf: VarFactory, name: str | None = None,
                          parameters: PidHydroGovernorParameters | None = None) -> RmsModelTemplate:
    """Build PID hydraulic regulation with distinct droop sensing, controller and gate memories.

    Permanent droop filters reference minus selected electrical power or actual
    gate position; shaft-speed deviation opposes that filtered droop error.
    Parallel PI and derivative channels form the regulator: the PI channel is
    filtered once, derivative action has its own identical filter, and their
    sum is filtered again. The controller transfer is therefore
    ``(KP+KI/s+KD*s)/(1+TA*s)**2``. The measurement time TREG belongs to the
    droop-error path, not the raw shaft-speed path.

    A gate-position servo applies separate opening/closing rate capabilities
    before integrating into gate position, with directional travel stops.
    Upstream PI memory has no invented antiwindup path. The gate/power
    characteristic interpolates the four physical points ``(G0,0)``,
    ``(G1,P1)``, ``(G2,P2)`` and ``(1,P3)``. Its outer linear segments extend
    beyond the first/last point, including negative power below no-load gate.
    The monotone inverse initializes gate from actual initial turbine power.
    Water dynamics follow ``(1-TZ*s)/(1+TZ*s/2)`` with ``TZ=ATW*TW``. Raw-speed
    mechanical damping remains outside any control deadband. This fixed water
    model does not vary inertia with operating gate/head.

    Inputs are absolute per-unit shaft speed, droop reference and electrical
    power on the declared turbine base. Reference units are electrical power
    or gate position according to the explicit feedback selection. Outputs are
    turbine-base mechanical power, actual gate and bounded gate velocity.
    Initialization independently freezes initial mechanical and electrical
    power, derives gate from the characteristic, sets zero droop error and
    initializes all actuator/filter memories consistently. Seven states exist
    with positive measurement time; zero TREG removes that state exactly.
    Controller, servo and water times remain positive. All times use seconds.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical control, gate-characteristic and water coefficients.
    :return: Native hydraulic governor with explicit feedback selection and bases.
    :raises ValueError: Invalid coefficients, nonmonotone characteristic or feedback selection.
    """
    p: PidHydroGovernorParameters = PidHydroGovernorParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.droop,p.detector_time,p.kp,p.ki,p.kd,p.controller_time,
        p.servo_time,p.damping,p.g0,p.g1,p.p1,p.g2,p.p2,p.p3,p.gate_max,p.gate_min,
        p.water_factor,p.water_time,p.opening_rate,p.closing_rate)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('PID hydraulic governor coefficients must be finite')
    elif min(p.controller_time,p.servo_time,p.water_factor,p.water_time,p.opening_rate) <= 0 or p.closing_rate >= 0:
        raise ValueError('PID hydraulic governor times and signed motion rates are invalid')
    elif min(p.droop,p.detector_time,p.kp,p.ki,p.kd,p.damping,p.g0,p.gate_min) < 0:
        raise ValueError('PID hydraulic governor gains and minimum gate must be nonnegative')
    elif not (p.g0 < p.g1 < p.g2 < 1. and 0 < p.p1 < p.p2 < p.p3) or p.gate_max <= p.gate_min:
        raise ValueError('Hydraulic gate/power characteristic and travel limits must be strictly ordered')
    elif not isinstance(p.feedback,HydroDroopFeedback):
        raise ValueError('Hydraulic droop feedback requires an explicit physical selection')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'PIDGOV' if name is None else name)
    droop: Var = c.parameter('RPERM',p.droop)
    detector_time: Var = c.parameter('TREG',p.detector_time)
    kp: Var = c.parameter('KP',p.kp)
    ki: Var = c.parameter('KI',p.ki)
    kd: Var = c.parameter('KD',p.kd)
    ta: Var = c.parameter('TA',p.controller_time)
    tb: Var = c.parameter('TB',p.servo_time)
    damping: Var = c.parameter('DTURB',p.damping)
    g0: Var = c.parameter('G0',p.g0)
    g1: Var = c.parameter('G1',p.g1)
    p1: Var = c.parameter('P1',p.p1)
    g2: Var = c.parameter('G2',p.g2)
    p2: Var = c.parameter('P2',p.p2)
    p3: Var = c.parameter('P3',p.p3)
    gate_upper: Var = c.parameter('GMAX',p.gate_max)
    gate_lower: Var = c.parameter('GMIN',p.gate_min)
    water_factor: Var = c.parameter('ATW',p.water_factor)
    water_time: Var = c.parameter('TW',p.water_time)
    opening: Var = c.parameter('VELMAX',p.opening_rate)
    closing: Var = c.parameter('VELMIN',p.closing_rate)
    initial_power: Var = c.parameter('Pm0Pu',.5)
    initial_electrical: Var = c.parameter('Pe0Pu',.5)
    slope1: Expr = p1/(g1-g0)
    slope2: Expr = (p2-p1)/(g2-g1)
    slope3: Expr = (p3-p2)/(Const(1.)-g2)
    # The same piecewise-linear characteristic supplies an exact monotone inverse.
    gate0: Expr = g0+initial_power/slope1+(Const(1.)/slope2-Const(1.)/slope1)*sym.max(initial_power-p1,Const(0.))+(Const(1.)/slope3-Const(1.)/slope2)*sym.max(initial_power-p2,Const(0.))
    speed: Var = c.input('OmegaPu',Const(1.))
    reference: Var = c.input('ReferencePu',gate0 if p.feedback == HydroDroopFeedback.GATE_POSITION else initial_electrical)
    electrical: Var = c.input('ElectricalPowerPu',initial_electrical)
    gate: Var = vf.add_var('GatePu_'+c.name)
    selected: Var = gate if p.feedback == HydroDroopFeedback.GATE_POSITION else electrical
    droop_error: Var = c.lag('DroopErrorPu',droop*(reference-selected),detector_time,p.detector_time,Const(0.))
    deviation: Var = c.speed_deviation(speed,p.deadband_low,p.deadband_high)
    error: Expr = droop_error-deviation
    integral: Var = c.differential(vf.add_var('IntegralPu_'+c.name),ki*error,gate0)
    first: Var = c.lag('FirstRegulatorPu',kp*error+integral,ta,p.controller_time,gate0)
    derivative: Var = c.washout('DerivativePu',error,ta,p.controller_time,kd/ta,Const(0.))
    second: Var = c.lag('SecondRegulatorPu',first+derivative,ta,p.controller_time,gate0)
    velocity: Var = c.algebraic('GateVelocityPu',sym.hard_sat((second-gate)/tb,closing,opening),Const(0.))
    c.differential(gate,velocity,gate0,gate_lower,gate_upper)
    turbine: Var = c.algebraic('StaticPowerPu',slope1*(gate-g0)+(slope2-slope1)*sym.max(gate-g1,Const(0.))+(slope3-slope2)*sym.max(gate-g2,Const(0.)),initial_power)
    tz: Expr = water_factor*water_time
    water: Var = c.lead_lag('WaterPowerPu',turbine,-tz,tz/Const(2.),-p.water_factor*p.water_time,p.water_factor*p.water_time/2.,initial_power)
    power: Var = c.algebraic('PmPu',water-damping*(speed-Const(1.)),initial_power)
    return c.finish((power,gate,velocity),'Electrohydraulic PID gate regulation with selectable droop feedback and calibrated turbine characteristic')
