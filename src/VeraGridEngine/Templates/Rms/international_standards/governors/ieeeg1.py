# SPDX-License-Identifier: MPL-2.0
"""Rate-limited steam-valve regulation with four cascaded turbine stages and two shaft outputs."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class MultiStageSteamGovernorParameters:
    """Steam-valve and turbine coefficients on one declared power base."""

    __slots__ = ('gain', 'speed_lag', 'speed_lead', 'servo_time', 'opening_rate', 'closing_rate',
                 'maximum', 'minimum', 'turbine_times', 'fractions', 'deadband_high', 'deadband_low')

    def __init__(self, gain: float = 20.0, speed_lag: float = .1, speed_lead: float = 0.0,
                 servo_time: float = .2, opening_rate: float = .1, closing_rate: float = -.1,
                 maximum: float = 1.2, minimum: float = 0.0,
                 turbine_times: tuple[float, float, float, float] = (.3, 5.0, .5, .1),
                 fractions: tuple[float, float, float, float, float, float, float, float] =
                 (.3, 0.0, .3, 0.0, .2, 0.0, .2, 0.0),
                 deadband_high: float = 0.0, deadband_low: float = 0.0) -> None:
        """Store speed compensation, valve capabilities and both turbine-shaft fractions.

        :param gain: Nonnegative reciprocal permanent droop on the governor power base.
        :param speed_lag: Nonnegative speed-compensator denominator time, in seconds.
        :param speed_lead: Nonnegative speed-compensator numerator time, in seconds.
        :param servo_time: Positive valve-servomotor normalization time, in seconds.
        :param opening_rate: Positive valve opening rate, in per-unit position per second.
        :param closing_rate: Negative valve closing rate, in per-unit position per second.
        :param maximum: Upper valve-position limit.
        :param minimum: Lower valve-position limit.
        :param turbine_times: Four nonnegative cascaded steam-volume times, in seconds.
        :param fractions: Alternating first/second shaft weights at each of four stages.
        :param deadband_high: Nonnegative overspeed deadband threshold.
        :param deadband_low: Nonpositive underspeed deadband threshold.
        """
        self.gain: float = gain
        self.speed_lag: float = speed_lag
        self.speed_lead: float = speed_lead
        self.servo_time: float = servo_time
        self.opening_rate: float = opening_rate
        self.closing_rate: float = closing_rate
        self.maximum: float = maximum
        self.minimum: float = minimum
        self.turbine_times: tuple[float, float, float, float] = turbine_times
        self.fractions: tuple[float, float, float, float, float, float, float, float] = fractions
        self.deadband_high: float = deadband_high
        self.deadband_low: float = deadband_low


def build_ieeeg1_template(vf: VarFactory, name: str | None = None,
                          parameters: MultiStageSteamGovernorParameters | None = None) -> RmsModelTemplate:
    """Build steam-turbine speed regulation with separate valve and stage dynamics.

    Shaft-speed deviation, optionally passed through a continuous asymmetric
    deadband, enters ``K*(1+s*T2)/(1+s*T1)``. The compensated speed demand
    subtracts from a valve reference. Valve velocity is clipped independently
    between closing/opening rates before integration. Position stops suppress
    outward motion and permit inward recovery. A clipped speed demand alone
    would not reproduce these rate and position constraints.

    Four cascaded lags represent steam volumes, reheating and crossover delays.
    Alternating stage fractions feed two distinct shaft-power sums; their sum
    is also exposed. Zero steam times are exact algebraic stages. The speed
    compensator can be bypassed by setting both its times to zero. A negative
    closing rate and positive opening rate retain direction-dependent travel.

    Inputs preserve absolute shaft speed, speed reference and total mechanical
    load-power reference. Outputs, in order, are first-shaft power, second-shaft
    power and total power. At nominal speed, valve position and all turbine
    memories initialize to the load-power reference divided by the sum of all
    fractions; the speed-compensator memory is zero. The valve reference uses
    that same normalization. Power and valve position use the declared turbine
    power base; the connecting host owns any machine/network base conversion.
    Time constants are seconds and travel rates are per second. There are up to
    six states: speed compensation, valve position and four turbine memories.
    Initial valve position must be inside its limits. Nonzero shaft fractions
    remain separate outputs rather than being silently assigned to one shaft.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical valve, stage, droop and optional deadband settings.
    :return: Native steam governor preserving three public inputs and outputs.
    :raises ValueError: Invalid domains, nonfinite settings or zero total turbine gain.
    """
    p: MultiStageSteamGovernorParameters = MultiStageSteamGovernorParameters() if parameters is None else parameters
    groups: tuple[tuple[float, ...], ...] = ((p.gain, p.speed_lag, p.speed_lead, p.servo_time,
        p.opening_rate, p.closing_rate, p.maximum, p.minimum, p.deadband_high, p.deadband_low),
        p.turbine_times, p.fractions)
    if not all(math.isfinite(value) for group in groups for value in group):
        raise ValueError('Steam governor coefficients must be finite')
    elif min(p.gain, p.speed_lag, p.speed_lead, p.deadband_high) < 0 or p.deadband_low > 0 or min(p.turbine_times) < 0:
        raise ValueError('Steam governor gains/times or deadband signs are invalid')
    elif p.servo_time <= 0 or p.opening_rate <= 0 or p.closing_rate >= 0 or p.maximum <= p.minimum:
        raise ValueError('Steam valve requires positive servo time, signed travel rates and ordered position limits')
    elif min(p.fractions) < 0 or sum(p.fractions) <= 0:
        raise ValueError('Turbine fractions must be nonnegative with positive total gain')
    else:
        pass
    control: ControlRealization = ControlRealization(vf, 'IEEEG1' if name is None else name)
    gain: Var = control.parameter('K', p.gain)
    lag: Var = control.parameter('T1', p.speed_lag)
    lead: Var = control.parameter('T2', p.speed_lead)
    servo: Var = control.parameter('T3', p.servo_time)
    opening: Var = control.parameter('UO', p.opening_rate)
    closing: Var = control.parameter('UC', p.closing_rate)
    maximum: Var = control.parameter('PMAX', p.maximum)
    minimum: Var = control.parameter('PMIN', p.minimum)
    high: Var = control.parameter('DBH', p.deadband_high)
    low: Var = control.parameter('DBL', p.deadband_low)
    times: tuple[Var, ...] = tuple(control.parameter('T'+str(index+4), value) for index, value in enumerate(p.turbine_times))
    weights: tuple[Var, ...] = tuple(control.parameter('K'+str(index+1), value) for index, value in enumerate(p.fractions))
    omega: Var = control.input('OmegaPu', Const(1.0))
    reference: Var = control.input('OmegaRefPu', Const(1.0))
    load: Var = control.input('PmRefPu', Const(.5))
    speed: Expr = omega-reference
    if p.deadband_high != 0 or p.deadband_low != 0:
        speed = sym.max(speed-high, Const(0.0))+sym.min(speed-low, Const(0.0))
    else:
        pass
    speed_error: Var = control.algebraic('SpeedErrorPu', speed, Const(0.0))
    compensated: Var = control.lead_lag('SpeedCompensatedPu', speed_error, lead, lag,
                                      p.speed_lead, p.speed_lag, Const(0.0))
    total_gain: Expr = sum(weights, Const(0.0))
    initial_valve: Expr = load/total_gain
    valve: Var = vf.add_var('ValvePu_'+control.name)
    velocity: Var = control.algebraic('ValveVelocityPu',
        sym.hard_sat((initial_valve-gain*compensated-valve)/servo, closing, opening), Const(0.0))
    control.differential(valve, velocity, initial_valve, minimum, maximum)
    stage: Var = valve
    shaft1: Expr = Const(0.0)
    shaft2: Expr = Const(0.0)
    index: int
    for index in range(4):
        stage = control.lag('SteamStage'+str(index+1)+'Pu', stage, times[index], p.turbine_times[index], initial_valve)
        shaft1 = shaft1+weights[2*index]*stage
        shaft2 = shaft2+weights[2*index+1]*stage
    first: Var = control.algebraic('Pm1Pu', shaft1, initial_valve*sum(weights[0::2], Const(0.0)))
    second: Var = control.algebraic('Pm2Pu', shaft2, initial_valve*sum(weights[1::2], Const(0.0)))
    total: Var = control.algebraic('PmPu', first+second, load)
    return control.finish((first, second, total), 'Steam governor with rate-limited valve and four cascaded turbine stages')
