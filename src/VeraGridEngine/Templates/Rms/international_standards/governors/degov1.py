# SPDX-License-Identifier: MPL-2.0
"""Delayed combustion with electronic speed control and a fuel actuator."""
from __future__ import annotations

import math
from enum import Enum

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.procedural_logic import delay
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class EngineDroopFeedback(Enum):
    """Physical measurement closing the permanent-droop loop."""

    THROTTLE = 0
    ELECTRICAL_POWER = 1


class DieselGovernorParameters:
    """Electronic controller, fuel actuator and combustion coefficients."""

    __slots__ = ('t1', 't2', 't3', 'gain', 't4', 't5', 't6', 'delay',
                 'maximum', 'minimum', 'droop', 'power_time', 'feedback', 'deadband_high', 'deadband_low')

    def __init__(self, t1: float = .01, t2: float = .02, t3: float = .2,
                 gain: float = 20., t4: float = .25, t5: float = .009,
                 t6: float = .0384, combustion_delay: float = .01,
                 maximum: float = 1.1, minimum: float = 0., droop: float = .05,
                 power_time: float = .1,
                 feedback: EngineDroopFeedback = EngineDroopFeedback.THROTTLE,
                 deadband_high: float = 0., deadband_low: float = 0.) -> None:
        """Store physical constants without converting parameter or machine bases.

        :param t1: Positive control-box denominator time in seconds.
        :param t2: Positive second denominator time in seconds.
        :param t3: Nonnegative control-box numerator time in seconds.
        :param gain: Positive actuator gain.
        :param t4: Nonnegative actuator numerator time in seconds.
        :param t5: Positive actuator denominator time in seconds.
        :param t6: Positive second actuator denominator time in seconds.
        :param combustion_delay: Nonnegative fuel-to-torque transport delay in seconds.
        :param maximum: Upper fuel-throttle limit on the declared machine base.
        :param minimum: Lower fuel-throttle limit on that same base.
        :param droop: Nonnegative permanent-droop coefficient; zero is isochronous.
        :param power_time: Nonnegative electrical-power measurement time in seconds.
        :param feedback: Explicit physical droop measurement.
        :param deadband_high: Nonnegative overspeed deadband threshold.
        :param deadband_low: Nonpositive underspeed deadband threshold.
        """
        self.t1: float = t1
        self.t2: float = t2
        self.t3: float = t3
        self.gain: float = gain
        self.t4: float = t4
        self.t5: float = t5
        self.t6: float = t6
        self.delay: float = combustion_delay
        self.maximum: float = maximum
        self.minimum: float = minimum
        self.droop: float = droop
        self.power_time: float = power_time
        self.feedback: EngineDroopFeedback = feedback
        self.deadband_high: float = deadband_high
        self.deadband_low: float = deadband_low


def build_degov1_template(vf: VarFactory, name: str | None = None,
                          parameters: DieselGovernorParameters | None = None) -> RmsModelTemplate:
    """Build electronic engine-speed regulation with delayed fuel combustion.

    The control-box transfer is ``(1+s*T3)/(1+s*T1+s*s*T1*T2)``.
    It drives a fuel actuator with transfer
    ``K*(1+s*T4)/(s*(1+s*T5)*(1+s*T6))``. A separate static
    saturation bounds the resulting throttle between its physical limits.
    This realization preserves the actuator's internal memories during output
    saturation; it does not add an undocumented tracking or reset mechanism.

    The throttle passes through a transport delay before becoming shaft torque.
    Mechanical power is delayed torque times absolute shaft speed. Inputs are
    absolute speed, electrical active power and speed/load reference, in that
    order. Outputs are mechanical power, mechanical torque and bounded throttle.
    Power and torque use the same declared machine base at nominal speed.
    The host must connect the torque output to a torque-consuming machine.

    Permanent droop senses either the undelayed bounded throttle or filtered
    electrical power. With zero droop the loop is isochronous. Separate initial
    torque and electrical-power parameters preserve steady machine losses.
    At nominal speed, the actuator integral stores initial torque while the
    control-box and actuator rate memories are zero. The initial reference is
    droop times the selected steady feedback. No iterative startup ramp is used.
    Independent optional speed deadband thresholds remove only deviation outside
    the band, continuously, before the droop sum. They default to zero here.

    Positive combustion delay uses accepted-boundary sample history with a
    zero-order hold and equilibrium prehistory. Resolution therefore depends
    on solver step size. Zero delay is an exact algebraic connection and owns
    no history. The control box and actuator own five continuous states; an
    electrical-power feedback lag adds one when its time is positive.

    :param vf: Shared native symbolic factory.
    :param name: Optional controller instance label.
    :param parameters: Explicit physical coefficients and droop selection.
    :return: Native engine controller with separate power and torque outputs.
    :raises ValueError: Nonfinite coefficients, invalid times or unordered limits.
    """
    p: DieselGovernorParameters = DieselGovernorParameters() if parameters is None else parameters
    values: tuple[float, ...] = (p.t1, p.t2, p.t3, p.gain, p.t4, p.t5, p.t6,
        p.delay, p.maximum, p.minimum, p.droop, p.power_time, p.deadband_high, p.deadband_low)
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Engine governor coefficients must be finite')
    elif min(p.t1, p.t2, p.t5, p.t6, p.gain) <= 0:
        raise ValueError('Control-box and actuator denominator times and gain must be positive')
    elif min(p.t3, p.t4, p.delay, p.droop, p.power_time) < 0 or p.maximum <= p.minimum:
        raise ValueError('Engine governor requires nonnegative times/droop and ordered throttle limits')
    elif p.deadband_high < 0 or p.deadband_low > 0:
        raise ValueError('Engine speed deadband thresholds must straddle zero')
    elif not isinstance(p.feedback, EngineDroopFeedback):
        raise ValueError('Engine droop feedback must be an explicit physical selection')
    else:
        pass
    control: ControlRealization = ControlRealization(vf, 'DEGOV1' if name is None else name)
    t1: Var = control.parameter('T1', p.t1)
    t2: Var = control.parameter('T2', p.t2)
    t3: Var = control.parameter('T3', p.t3)
    gain: Var = control.parameter('K', p.gain)
    t4: Var = control.parameter('T4', p.t4)
    t5: Var = control.parameter('T5', p.t5)
    t6: Var = control.parameter('T6', p.t6)
    td: Var = control.parameter('TD', p.delay)
    maximum: Var = control.parameter('TMAX', p.maximum)
    minimum: Var = control.parameter('TMIN', p.minimum)
    droop: Var = control.parameter('DROOP', p.droop)
    power_time: Var = control.parameter('TE', p.power_time)
    torque0: Var = control.parameter('InitialMechanicalTorquePu', .5)
    electrical0: Var = control.parameter('InitialElectricalPowerPu', .5)
    speed: Var = control.input('OmegaPu', Const(1.))
    electrical: Var = control.input('ElectricalPowerPu', electrical0)
    feedback0: Var = torque0 if p.feedback == EngineDroopFeedback.THROTTLE else electrical0
    reference: Var = control.input('ReferencePu', droop*feedback0)
    throttle: Var = vf.add_var(name='ThrottlePu_'+control.name)
    if p.feedback == EngineDroopFeedback.ELECTRICAL_POWER and p.droop > 0:
        feedback: Var = control.lag('MeasuredElectricalPowerPu', electrical, power_time, p.power_time, electrical0)
    else:
        feedback = throttle
    deviation: Var = control.speed_deviation(speed, p.deadband_low, p.deadband_high)
    error: Expr = reference-deviation-droop*feedback
    # A derivative chain realizes complex denominator poles without factoring them.
    box: Var = vf.add_var(name='ControlBoxMemory_'+control.name)
    box_rate: Var = vf.add_var(name='ControlBoxRate_'+control.name)
    control.differential(box, box_rate, Const(0.))
    control.differential(box_rate, (error-box-t1*box_rate)/(t1*t2), Const(0.))
    demand: Var = control.algebraic('ControlBoxOutputPu', box+t3*box_rate, Const(0.))
    # The actuator has one integral and two strictly proper denominator memories.
    position: Var = vf.add_var(name='ActuatorPositionPu_'+control.name)
    rate: Var = vf.add_var(name='ActuatorRate_'+control.name)
    acceleration: Var = vf.add_var(name='ActuatorAcceleration_'+control.name)
    control.differential(position, rate, torque0)
    control.differential(rate, acceleration, Const(0.))
    control.differential(acceleration, (gain*demand-rate-(t5+t6)*acceleration)/(t5*t6), Const(0.))
    control.block.algebraic_vars.append(throttle)
    control.block.algebraic_eqs.append(throttle-sym.hard_sat(position+t4*rate, minimum, maximum))
    control.block.init_eqs[throttle] = torque0
    if p.delay == 0:
        torque: Var = control.algebraic('MechanicalTorquePu', throttle, torque0)
    else:
        torque = vf.add_var(name='MechanicalTorquePu_'+control.name)
        control.block.mode_dict[torque] = torque0
        control.block.init_eqs[torque] = torque0
        control.block.procedural_logic.append(delay(throttle, td, torque, name='CombustionDelay'))
    power: Var = control.algebraic('MechanicalPowerPu', torque*speed, torque0)
    return control.finish((power, torque, throttle), 'Electronic speed control, bounded fuel flow and delayed combustion')
