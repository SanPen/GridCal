# SPDX-License-Identifier: MPL-2.0
"""Hydraulic gate control with cascaded PI stages, transient droop and inverse-response water dynamics."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class CascadedHydroGovernorParameters:
    """Physical coefficients for cascaded speed/governor PI, gate motion and linear water response."""
    __slots__ = ('kp','ki','ka','t1','t2','t3','t4','t5','t6','reset_time',
                 'temporary_droop','permanent_droop','gate_velocity','gate_max','gate_min',
                 'power_gain','deadband_low','deadband_high')

    def __init__(self, kp: float = 1., ki: float = .1, ka: float = 1.,
                 t1: float = .1, t2: float = .05, t3: float = 1.,
                 t4: float = .1, t5: float = 1., t6: float = .5,
                 reset_time: float = 5., temporary_droop: float = .3,
                 permanent_droop: float = .05, gate_velocity: float = .2,
                 gate_max: float = 1., gate_min: float = 0., power_gain: float = 1.,
                 deadband_low: float = 0., deadband_high: float = 0.) -> None:
        """Store physical settings; construction validates their domains.

        :param kp: Nonnegative proportional speed gain.
        :param ki: Nonnegative integral speed gain in inverse seconds.
        :param ka: Positive governor gain.
        :param t1: Nonnegative governor-PI numerator time in seconds.
        :param t2: Nonnegative gate-velocity compensation lead in seconds.
        :param t3: Positive governor-PI denominator time in seconds.
        :param t4: Positive gate-velocity compensation lag in seconds.
        :param t5: Nonnegative water-column inverse-response lead magnitude in seconds.
        :param t6: Positive water-column lag in seconds.
        :param reset_time: Positive transient-droop washout time in seconds.
        :param temporary_droop: Nonnegative transient gate feedback.
        :param permanent_droop: Nonnegative permanent gate feedback.
        :param gate_velocity: Positive symmetric gate opening/closing rate capability.
        :param gate_max: Upper gate-position stop.
        :param gate_min: Lower gate-position stop.
        :param power_gain: Positive gate-to-power gain on the declared turbine base.
        :param deadband_low: Nonpositive continuous underspeed deadband threshold.
        :param deadband_high: Nonnegative continuous overspeed deadband threshold.
        """
        self.kp: float = kp
        self.ki: float = ki
        self.ka: float = ka
        self.t1: float = t1
        self.t2: float = t2
        self.t3: float = t3
        self.t4: float = t4
        self.t5: float = t5
        self.t6: float = t6
        self.reset_time: float = reset_time
        self.temporary_droop: float = temporary_droop
        self.permanent_droop: float = permanent_droop
        self.gate_velocity: float = gate_velocity
        self.gate_max: float = gate_max
        self.gate_min: float = gate_min
        self.power_gain: float = power_gain
        self.deadband_low: float = deadband_low
        self.deadband_high: float = deadband_high


def build_hygov2_template(vf: VarFactory, name: str | None = None,
                          parameters: CascadedHydroGovernorParameters | None = None) -> RmsModelTemplate:
    """Build cascaded PI hydraulic control with explicit gate motion and penstock dynamics.

    Absolute shaft speed becomes nominal-speed deviation through an optional
    continuous asymmetric deadband. A speed channel ``KP+KI/s`` opposes the
    governor reference. Permanent gate droop and a temporary gate-feedback
    washout ``r*TR*s/(1+TR*s)`` oppose that same reference. Their summed error
    drives ``KA*(1+T1*s)/(T3*s)``, followed by gate-velocity compensation
    ``(1+T2*s)/(1+T4*s)``. A symmetric velocity limiter precedes integration
    into actual gate position, with directional non-windup travel stops.

    Only gate velocity and gate position have the specified motion limits;
    the upstream PI memories do not acquire invented tracking feedback. They
    can continue accumulating when gate motion is limited. The linear water
    column converts actual gate to power through
    ``PMAX*(1-T5*s)/(1+T6*s)``. The negative numerator represents the initial
    inverse hydraulic response. No nonlinear head/flow law or extra speed
    damping is added to this explicitly linear turbine representation.

    Inputs are absolute per-unit shaft speed and a governor reference in the
    speed-control channel's units. Outputs are turbine-base mechanical power,
    gate position and bounded gate velocity. With nominal speed, initialization
    sets both PI memories to zero, the gate and water memory to ``0.5/PMAX``,
    and the reference to permanent droop times that gate. A host freezes initial power and reference from its actual operating point;
    this also supports zero permanent droop without dividing by that gain. There are six states when
    speed integral gain is positive; zero KI removes that memory exactly.
    All time constants use seconds, and gate velocity uses per unit per second.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical cascade, droop, gate and water coefficients.
    :return: Native hydraulic governor with explicit reference and turbine bases.
    :raises ValueError: Invalid dynamics, gains, capability or deadband domains.
    """
    p: CascadedHydroGovernorParameters = CascadedHydroGovernorParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.kp,p.ki,p.ka,p.t1,p.t2,p.t3,p.t4,p.t5,p.t6,
        p.reset_time,p.temporary_droop,p.permanent_droop,p.gate_velocity,p.gate_max,p.gate_min,p.power_gain)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Cascaded hydraulic governor coefficients must be finite')
    elif min(p.ka,p.t3,p.t4,p.t6,p.reset_time,p.gate_velocity,p.power_gain) <= 0:
        raise ValueError('Hydraulic governor dynamic times and motion/power capabilities must be positive')
    elif min(p.kp,p.ki,p.t1,p.t2,p.t5,p.temporary_droop,p.permanent_droop,p.gate_min) < 0:
        raise ValueError('Hydraulic governor gains, lead times and minimum gate must be nonnegative')
    elif p.kp == 0 and p.ki == 0:
        raise ValueError('Hydraulic speed control requires a proportional or integral path')
    elif p.gate_max <= p.gate_min:
        raise ValueError('Hydraulic gate travel limits must be ordered')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'HYGOV2' if name is None else name)
    kp: Var = c.parameter('KP',p.kp)
    ki: Var = c.parameter('KI',p.ki)
    ka: Var = c.parameter('KA',p.ka)
    t1: Var = c.parameter('T1',p.t1)
    t2: Var = c.parameter('T2',p.t2)
    t3: Var = c.parameter('T3',p.t3)
    t4: Var = c.parameter('T4',p.t4)
    t5: Var = c.parameter('T5',p.t5)
    t6: Var = c.parameter('T6',p.t6)
    reset: Var = c.parameter('TR',p.reset_time)
    temporary: Var = c.parameter('r',p.temporary_droop)
    permanent: Var = c.parameter('R',p.permanent_droop)
    velocity_limit: Var = c.parameter('VGMAX',p.gate_velocity)
    gate_upper: Var = c.parameter('GMAX',p.gate_max)
    gate_lower: Var = c.parameter('GMIN',p.gate_min)
    power_gain: Var = c.parameter('PMAX',p.power_gain)
    initial_power: Var = c.parameter('Pm0Pu',.5)
    gate0: Expr = initial_power/power_gain
    speed: Var = c.input('OmegaPu',Const(1.))
    reference: Var = c.input('ReferencePu',permanent*gate0)
    gate: Var = vf.add_var('GatePu_'+c.name)
    deviation: Var = c.speed_deviation(speed,p.deadband_low,p.deadband_high)
    speed_memory: Var
    if p.ki > 0:
        speed_memory = c.differential(vf.add_var('SpeedIntegralPu_'+c.name),ki*deviation,Const(0.))
    else:
        speed_memory = c.algebraic('SpeedIntegralPu',Const(0.),Const(0.))
    transient: Var = c.washout('TransientDroopPu',gate,reset,p.reset_time,temporary,gate0)
    error: Var = c.algebraic('ErrorPu',reference-kp*deviation-speed_memory-permanent*gate-transient,Const(0.))
    governor_memory: Var = c.differential(vf.add_var('GovernorIntegralPu_'+c.name),ka/t3*error,Const(0.))
    demanded_velocity: Var = c.algebraic('DemandedVelocityPu',governor_memory+ka*t1/t3*error,Const(0.))
    velocity: Var = c.lead_lag('VelocityPu',demanded_velocity,t2,t4,p.t2,p.t4,Const(0.))
    bounded_velocity: Var = c.algebraic('BoundedVelocityPu',sym.hard_sat(velocity,-velocity_limit,velocity_limit),Const(0.))
    c.differential(gate,bounded_velocity,gate0,gate_lower,gate_upper)
    water: Var = c.lead_lag('WaterPowerPu',gate,-t5,t6,-p.t5,p.t6,gate0)
    power: Var = c.algebraic('PmPu',power_gain*water,power_gain*gate0)
    return c.finish((power,gate,bounded_velocity),'Cascaded PI hydraulic gate control with transient droop and inverse-response water dynamics')
