# SPDX-License-Identifier: MPL-2.0
"""Tracked speed/power regulation, fuel-valve motion and turbine energy conversion."""
from __future__ import annotations

import math
from enum import IntEnum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class GovernorDroopFeedback(IntEnum):
    """Physical measurement closing the permanent-droop loop."""

    REQUESTED_STROKE = -2
    VALVE_STROKE = -1
    ISOCHRONOUS = 0
    ELECTRICAL_POWER = 1


class FuelFlowCharacteristic(IntEnum):
    """Dependence of delivered fuel on valve stroke and shaft speed."""

    INDEPENDENT = 0
    SHAFT_DRIVEN = 1


class TrackedGovernorParameters:
    """Speed regulation, continuous fuel-load limiting and turbine coefficients."""

    __slots__ = ('feedback', 'fuel_characteristic', 'droop', 'power_time', 'error_limits',
                 'governor_gains', 'derivative_time', 'valve_limits', 'actuator_time',
                 'valve_rates', 'turbine_gain', 'no_load_fuel', 'turbine_times',
                 'load_time', 'load_gains', 'load_reference', 'damping', 'reset_gain',
                 'deadband', 'temperature_times', 'speed_deadband', 'load_rates')

    def __init__(self, feedback: GovernorDroopFeedback = GovernorDroopFeedback.ELECTRICAL_POWER,
                 fuel_characteristic: FuelFlowCharacteristic = FuelFlowCharacteristic.INDEPENDENT,
                 droop: float = .05, power_time: float = .1,
                 error_limits: tuple[float, float] = (-.1, .1),
                 governor_gains: tuple[float, float, float] = (10., 2., 0.),
                 derivative_time: float = .1, valve_limits: tuple[float, float] = (0., 1.),
                 actuator_time: float = .2, valve_rates: tuple[float, float] = (-.1, .1),
                 turbine_gain: float = 1., no_load_fuel: float = .1,
                 turbine_times: tuple[float, float] = (0., .5), load_time: float = 3.,
                 load_gains: tuple[float, float] = (1., 1.), load_reference: float = 1.,
                 damping: float = 0., reset_gain: float = 0., deadband: float = 0.,
                 temperature_times: tuple[float, float] = (0., 1.),
                 speed_deadband: tuple[float, float] = (0., 0.),
                 load_rates: tuple[float, float] = (-99., 99.)) -> None:
        """Store one governor's settings on a declared turbine power base.

        :param feedback: Selected permanent-droop measurement.
        :param fuel_characteristic: Independent or shaft-driven fuel delivery.
        :param droop: Nonnegative permanent droop in per-unit speed per feedback unit.
        :param power_time: Nonnegative electrical-power measurement time in seconds.
        :param error_limits: Negative/positive shaped speed-error limits.
        :param governor_gains: Positive P, nonnegative I and D speed-regulator gains.
        :param derivative_time: Positive derivative-filter time when D is enabled.
        :param valve_limits: Minimum/maximum stroke, within zero and one.
        :param actuator_time: Positive valve-servo time in seconds.
        :param valve_rates: Negative closing and positive opening velocities.
        :param turbine_gain: Positive fuel-to-power gain.
        :param no_load_fuel: Nonnegative fuel required at synchronous no-load speed.
        :param turbine_times: Nonnegative lead/lag times in seconds.
        :param load_time: Nonnegative fuel-load measurement time in seconds.
        :param load_gains: Positive P/I tracked load-regulator gains, or both zero to bypass.
        :param load_reference: Maximum steady mechanical power on the turbine base.
        :param damping: Positive output speed damping; negative fuel-capability exponent.
        :param reset_gain: Nonnegative unbounded supervisory electrical-power integral gain.
        :param deadband: Nonnegative continuous deadband on combined regulation error.
        :param temperature_times: Nonnegative fuel-measurement lead/lag times in seconds.
        :param speed_deadband: Nonpositive underspeed/nonnegative overspeed thresholds.
        :param load_rates: Negative/positive continuous load-demand slew limits.
        """
        self.feedback: GovernorDroopFeedback = feedback
        self.fuel_characteristic: FuelFlowCharacteristic = fuel_characteristic
        self.droop: float = droop
        self.power_time: float = power_time
        self.error_limits: tuple[float, float] = error_limits
        self.governor_gains: tuple[float, float, float] = governor_gains
        self.derivative_time: float = derivative_time
        self.valve_limits: tuple[float, float] = valve_limits
        self.actuator_time: float = actuator_time
        self.valve_rates: tuple[float, float] = valve_rates
        self.turbine_gain: float = turbine_gain
        self.no_load_fuel: float = no_load_fuel
        self.turbine_times: tuple[float, float] = turbine_times
        self.load_time: float = load_time
        self.load_gains: tuple[float, float] = load_gains
        self.load_reference: float = load_reference
        self.damping: float = damping
        self.reset_gain: float = reset_gain
        self.deadband: float = deadband
        self.temperature_times: tuple[float, float] = temperature_times
        self.speed_deadband: tuple[float, float] = speed_deadband
        self.load_rates: tuple[float, float] = load_rates


def build_ggov1_template(vf: VarFactory, name: str | None = None,
                         parameters: TrackedGovernorParameters | None = None) -> RmsModelTemplate:
    """Build tracked speed/power regulation and a continuous fuel-load limiter.

    Permanent droop can sense electrical power, true valve stroke, requested
    stroke or no feedback. A continuous deadband shapes the combined speed/load
    error. Filtered derivative and proportional action add to an integral memory.
    The integral memory tracks the selected, travel-limited fuel demand through
    ``(Ki/Kp)*(selected-memory)``. This preserves controller tracking during
    takeover, instead of allowing an inactive regulator to wind up independently.
    With zero I gain the speed regulator is proportional/derivative only; its
    initial reference supplies the required steady proportional offset.

    The fuel-load limiter senses actual fuel flow through temperature lead/lag
    and measurement lag stages. Its PI memory tracks the same selected demand;
    its output competes with the speed regulator through a low-value gate.
    Both zero load gains bypass this limiter with the maximum admissible stroke.
    The load-demand output is realized as a state. Its derivative is the sum
    of proportional error rate and tracked integral rate, clipped to the load
    closing/opening slew limits. The load power reference is a fixed construction
    coefficient; its derivative is exactly zero. Positive measurement time is
    required for enabled load control, so its error derivative is explicit even
    when the measured fuel changes rapidly. There is no acceleration override
    or fuel transport delay.

    Valve travel velocity is clipped before integration. Independent position
    stops block outward travel and permit immediate inward recovery. Fuel flow
    is either valve stroke or stroke times absolute speed. Turbine gain applies
    after subtracting no-load fuel, followed by the turbine lead/lag. Positive
    damping subtracts speed-deviation power; negative damping instead scales the
    measured fuel by absolute speed raised to that negative exponent.

    Inputs, in order, are absolute speed, electrical power, speed/load reference,
    and supervisory power setpoint. Outputs are
    mechanical power, valve stroke and selected fuel demand. All powers use the
    declared turbine base; speed/stroke/fuel are per unit and times are seconds.
    ``InitialMechanicalPowerPu`` is a frozen operating-point parameter, distinct
    from measured electrical power when machine losses are nonzero. Valve,
    turbine and tracking memories initialize from that mechanical operating
    point. The power setpoint initializes from electrical power. Zero supported
    measurement/lead-lag times remove states exactly; no small replacement times
    are introduced. The host must initialize within physical valve and load limits.

    :param vf: Shared symbolic variable factory.
    :param name: Optional instance label.
    :param parameters: Physical coefficients and structural feedback selections.
    :return: Four-input, three-output native controller.
    :raises ValueError: Nonfinite, physically invalid or unreviewed gain combinations.
    """
    p: TrackedGovernorParameters = TrackedGovernorParameters() if parameters is None else parameters
    scalar_values: tuple[float, ...] = (p.droop, p.power_time, p.derivative_time, p.actuator_time,
        p.turbine_gain, p.no_load_fuel, p.load_time, p.load_reference, p.damping, p.reset_gain, p.deadband)
    groups: tuple[tuple[float, ...], ...] = (scalar_values, p.error_limits, p.governor_gains,
        p.valve_limits, p.valve_rates, p.turbine_times, p.load_gains, p.temperature_times, p.speed_deadband, p.load_rates)
    if not all(math.isfinite(value) for group in groups for value in group):
        raise ValueError('Governor coefficients must be finite')
    elif not isinstance(p.feedback, GovernorDroopFeedback) or not isinstance(p.fuel_characteristic, FuelFlowCharacteristic):
        raise ValueError('Governor feedback and fuel characteristic require explicit enum selections')
    elif min(p.droop, p.power_time, p.no_load_fuel, p.load_time, p.load_reference, p.reset_gain, p.deadband,
             p.derivative_time, p.governor_gains[1], p.governor_gains[2], *p.turbine_times, *p.temperature_times) < 0:
        raise ValueError('Governor times, gains and fuel quantities must be nonnegative')
    elif min(p.actuator_time, p.turbine_gain, p.governor_gains[0]) <= 0:
        raise ValueError('Governor proportional gain, actuator time and turbine gain must be positive')
    elif not 0 <= p.valve_limits[0] < p.valve_limits[1] <= 1 or not p.valve_rates[0] < 0 < p.valve_rates[1]:
        raise ValueError('Governor valve limits and opening/closing rates are invalid')
    elif not p.error_limits[0] < 0 < p.error_limits[1] or not p.speed_deadband[0] <= 0 <= p.speed_deadband[1]:
        raise ValueError('Governor error/deadband limits must straddle zero')
    elif p.governor_gains[2] > 0 and p.derivative_time <= 0:
        raise ValueError('Enabled derivative control requires a positive filter time')
    elif not p.load_rates[0] < 0 < p.load_rates[1]:
        raise ValueError('Load-demand slew limits must straddle zero')
    elif p.load_gains != (0., 0.) and p.load_time <= 0:
        raise ValueError('Enabled rate-limited load control requires positive measurement time')
    elif p.load_gains != (0., 0.) and min(p.load_gains) <= 0:
        raise ValueError('Tracked load control requires positive P/I gains or both zero')
    else:
        pass
    c: ControlRealization = ControlRealization(vf, 'GGOV1' if name is None else name)
    r: Var = c.parameter('R', p.droop)
    tp: Var = c.parameter('Tpelec', p.power_time)
    emin: Var = c.parameter('Minerr', p.error_limits[0])
    emax: Var = c.parameter('Maxerr', p.error_limits[1])
    kp: Var = c.parameter('Kpgov', p.governor_gains[0])
    ki: Var = c.parameter('Kigov', p.governor_gains[1])
    kd: Var = c.parameter('Kdgov', p.governor_gains[2])
    td: Var = c.parameter('Tdgov', p.derivative_time)
    vmin: Var = c.parameter('Vmin', p.valve_limits[0])
    vmax: Var = c.parameter('Vmax', p.valve_limits[1])
    tact: Var = c.parameter('Tact', p.actuator_time)
    close: Var = c.parameter('Rclose', p.valve_rates[0])
    opening: Var = c.parameter('Ropen', p.valve_rates[1])
    kt: Var = c.parameter('Kturb', p.turbine_gain)
    wfnl: Var = c.parameter('Wfnl', p.no_load_fuel)
    tc: Var = c.parameter('Tc', p.turbine_times[0])
    tb: Var = c.parameter('Tb', p.turbine_times[1])
    tf: Var = c.parameter('Tfload', p.load_time)
    klp: Var = c.parameter('Kpload', p.load_gains[0])
    kli: Var = c.parameter('Kiload', p.load_gains[1])
    ldref: Const = Const(p.load_reference)
    load_down: Var = c.parameter('Rdown', p.load_rates[0])
    load_up: Var = c.parameter('Rup', p.load_rates[1])
    dm: Var = c.parameter('Dm', p.damping)
    kmw: Var = c.parameter('Kimw', p.reset_gain)
    db: Var = c.parameter('Db', p.deadband)
    tsa: Var = c.parameter('Tsa', p.temperature_times[0])
    tsb: Var = c.parameter('Tsb', p.temperature_times[1])
    dbl: Var = c.parameter('SpeedDeadbandLow', p.speed_deadband[0])
    dbh: Var = c.parameter('SpeedDeadbandHigh', p.speed_deadband[1])
    pm0: Var = c.parameter('InitialMechanicalPowerPu', .5)
    fuel0: Expr = pm0 / kt + wfnl
    omega: Var = c.input('OmegaPu', Const(1.))
    pe: Var = c.input('PePu', Const(.5))
    # Declare the servo and selected command before closing their feedback loops.
    valve: Var = vf.add_var('ActuatorPu_'+c.name)
    selected: Var = vf.add_var('LowValueSelectPu_'+c.name)
    feedback0: Expr = pe if p.feedback == GovernorDroopFeedback.ELECTRICAL_POWER else (
        Const(0.) if p.feedback == GovernorDroopFeedback.ISOCHRONOUS else fuel0)
    error0: Expr = fuel0/kp if p.governor_gains[1] == 0 else Const(0.)
    reference0: Expr = r*feedback0+error0+(db if p.governor_gains[1] == 0 else Const(0.))
    pref: Var = c.input('PRefPu', reference0)
    pset: Var = c.input('PmwSetPu', pe)
    measured: Var = c.lag('PeMeasuredPu', pe, tp, p.power_time, pe)
    feedback: Expr
    if p.feedback == GovernorDroopFeedback.ELECTRICAL_POWER:
        feedback = measured
    elif p.feedback == GovernorDroopFeedback.VALVE_STROKE:
        feedback = valve
    elif p.feedback == GovernorDroopFeedback.REQUESTED_STROKE:
        feedback = selected
    else:
        feedback = Const(0.)
    reset: Var = vf.add_var('MwIntegralPu_'+c.name)
    c.differential(reset, kmw*(pset-measured), Const(0.))
    speed: Expr = omega-Const(1.)
    if p.speed_deadband != (0., 0.):
        speed = sym.max(speed-dbh, Const(0.))+sym.min(speed-dbl, Const(0.))
    else:
        pass
    raw_error: Expr = pref+reset-speed-r*feedback
    if p.deadband > 0:
        raw_error = sym.max(raw_error-db, Const(0.))+sym.min(raw_error+db, Const(0.))
    else:
        pass
    error: Var = c.algebraic('SpeedErrorPu', sym.hard_sat(raw_error, emin, emax), error0)
    derivative: Expr
    if p.governor_gains[2] > 0:
        derivative = c.washout('DerivativePu', error, td, p.derivative_time, kd/td, error0)
    else:
        derivative = Const(0.)
    memory: Var = vf.add_var('GovernorIntegralPu_'+c.name)
    c.differential(memory, ki/kp*(selected-memory), fuel0 if p.governor_gains[1] > 0 else Const(0.), vmin, vmax)
    demand: Var = c.algebraic('GovernorDemandPu', kp*error+derivative+memory, fuel0)
    flow: Var = c.algebraic('FuelFlowPu', valve*omega if p.fuel_characteristic == FuelFlowCharacteristic.SHAFT_DRIVEN else valve, fuel0)
    fuel_measurement: Expr = flow*omega**dm if p.damping < 0 else flow
    temperature: Var = c.lead_lag('TemperaturePu', fuel_measurement, tsa, tsb,
                                 p.temperature_times[0], p.temperature_times[1], fuel0)
    load_measured: Var = c.lag('LoadMeasuredPu', temperature, tf, p.load_time, fuel0)
    load_error: Var = c.algebraic('LoadErrorPu', ldref/kt+wfnl-load_measured, ldref/kt+wfnl-fuel0)
    load_limit: Expr
    if p.load_gains == (0., 0.):
        load_limit = Const(1.)
    else:
        load_demand: Var = vf.add_var('LoadDemandPu_'+c.name)
        load_memory: Var = c.algebraic('LoadIntegralPu', load_demand-klp*load_error, fuel0)
        # Constant load reference makes the error rate the negative transducer rate.
        load_error_rate: Expr = -(temperature-load_measured)/tf
        load_rate: Expr = sym.hard_sat(klp*load_error_rate+kli/klp*(selected-load_memory), load_down, load_up)
        c.differential(load_demand, load_rate, klp*(ldref/kt+wfnl-fuel0)+fuel0)
        load_limit = c.algebraic('LimitedLoadDemandPu', sym.hard_sat(load_demand, vmin, Const(1.)),
            sym.hard_sat(klp*(ldref/kt+wfnl-fuel0)+fuel0, vmin, Const(1.)))
    # The same bounded selection drives both controller tracking and the actuator.
    c.block.algebraic_vars.append(selected)
    c.block.algebraic_eqs.append(selected-sym.hard_sat(sym.min(demand, load_limit), vmin, vmax))
    c.block.init_eqs[selected] = fuel0
    velocity: Expr = sym.hard_sat((selected-valve)/tact, close, opening)
    c.differential(valve, velocity, fuel0, vmin, vmax)
    turbine: Var = c.lead_lag('TurbinePowerPu', kt*(flow-wfnl), tc, tb,
                            p.turbine_times[0], p.turbine_times[1], pm0)
    pm: Var = c.algebraic('PmPu', turbine-dm*(omega-Const(1.)) if p.damping > 0 else turbine, pm0)
    return c.finish((pm, valve, selected), 'Tracked fuel-valve speed/power governor and turbine')
