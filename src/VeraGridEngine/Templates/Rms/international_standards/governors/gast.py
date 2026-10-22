# SPDX-License-Identifier: MPL-2.0
"""Gas-turbine speed governor with exhaust-temperature load limiting."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class GasGovernorParameters:
    """Construction parameters on the turbine's own power base.

    Time constants are in seconds. Droop is per-unit speed per per-unit power;
    valve limits and ambient load limit are per-unit power. Damping converts
    per-unit speed deviation into per-unit mechanical-power reduction.
    """

    __slots__ = ('r', 't1', 't2', 't3', 'ambient_limit', 'temperature_gain',
                 'valve_max', 'valve_min', 'damping', 'deadband_low', 'deadband_high')

    def __init__(self, r: float = 0.05, t1: float = 0.1, t2: float = 0.4,
                 t3: float = 3.0, ambient_limit: float = 1.0,
                 temperature_gain: float = 2.0, valve_max: float = 1.2,
                 valve_min: float = 0.0, damping: float = 0.0,
                 deadband_low: float = 0.0, deadband_high: float = 0.0) -> None:
        """Store physical settings for one gas-turbine governor.

        :param r: Positive permanent speed droop.
        :param t1: Positive fuel-valve actuator time constant.
        :param t2: Positive fuel-flow/turbine time constant.
        :param t3: Positive exhaust-temperature sensor time constant.
        :param ambient_limit: Available loading at the ambient operating condition.
        :param temperature_gain: Nonnegative exhaust-temperature limiting gain.
        :param valve_max: Upper non-windup fuel-valve limit.
        :param valve_min: Lower non-windup fuel-valve limit.
        :param damping: Nonnegative speed-dependent mechanical damping.
        :param deadband_low: Nonpositive underspeed deadband threshold.
        :param deadband_high: Nonnegative overspeed deadband threshold.
        """
        self.r: float = r
        self.t1: float = t1
        self.t2: float = t2
        self.t3: float = t3
        self.ambient_limit: float = ambient_limit
        self.temperature_gain: float = temperature_gain
        self.valve_max: float = valve_max
        self.valve_min: float = valve_min
        self.damping: float = damping
        self.deadband_low: float = deadband_low
        self.deadband_high: float = deadband_high


def build_gast_template(vf: VarFactory, name: str | None = None,
                        parameters: GasGovernorParameters | None = None) -> RmsModelTemplate:
    """Build a gas-turbine governor with a temperature-limited fuel demand.

    A speed-droop controller requests fuel from a load reference. A low-value
    gate compares that request with the thermal demand
    ``AT + KT * (AT - exhaust_temperature)``. The selected demand drives a
    non-windup fuel-valve actuator, followed by fuel-flow and exhaust-temperature
    lags. Mechanical output is fuel flow less speed-dependent turbine damping.

    The three states are fuel-valve position, fuel flow and exhaust temperature.
    The open inputs are absolute per-unit shaft speed ``OmegaPu`` and load
    reference ``PRefPu``. Outputs are ``PmPu`` and ``ValvePu``. All powers and
    droop use the turbine's own MVA base; the host must perform any base change.
    Initial conditions use nominal speed and a reference-derived thermal
    equilibrium. Limits act on the valve state and allow immediate inward motion.

    :param vf: Symbol factory owning this instance.
    :param name: Optional unique instance label, defaulting to GAST.
    :param parameters: Physical settings; omitted settings use native defaults.
    :return: Native three-state governor with two open inputs.
    :raises ValueError: Nonfinite settings, nonpositive dynamics or invalid limits.
    """
    settings: GasGovernorParameters = GasGovernorParameters() if parameters is None else parameters
    if min(settings.r, settings.t1, settings.t2, settings.t3) <= 0:
        raise ValueError('Gas governor requires positive droop and time constants')
    elif settings.valve_max <= settings.valve_min or settings.temperature_gain < 0 or settings.damping < 0:
        raise ValueError('Gas governor limits/gains are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf, 'GAST' if name is None else name)
    r: Var = builder.parameter('R', settings.r)
    t1: Var = builder.parameter('T1', settings.t1)
    t2: Var = builder.parameter('T2', settings.t2)
    t3: Var = builder.parameter('T3', settings.t3)
    ambient: Var = builder.parameter('AT', settings.ambient_limit)
    gain: Var = builder.parameter('KT', settings.temperature_gain)
    vmax: Var = builder.parameter('VMAX', settings.valve_max)
    vmin: Var = builder.parameter('VMIN', settings.valve_min)
    damping: Var = builder.parameter('Dturb', settings.damping)
    omega: Var = builder.input('OmegaPu', Const(1.0))
    pref: Var = builder.input('PRefPu', Const(0.5))
    controlled_speed: Var = builder.speed_deviation(omega,settings.deadband_low,settings.deadband_high)
    equilibrium: Expr = sym.hard_sat(sym.min(pref, ambient), vmin, vmax)
    # Declare the thermal feedback before constructing the closed actuator loop.
    temperature: Var = vf.add_var(name=f'ExhaustTemperaturePu_{builder.name}')
    thermal: Expr = ambient + gain * (ambient - temperature)
    command_initial: Expr = sym.min(pref, ambient + gain * (ambient - equilibrium))
    command: Var = builder.algebraic('FuelDemandPu', sym.min(pref - controlled_speed / r, thermal), command_initial)
    valve: Var = builder.lag('ValvePu', command, t1, settings.t1, equilibrium, vmin, vmax)
    fuel: Var = builder.lag('FuelFlowPu', valve, t2, settings.t2, equilibrium)
    builder.block.state_vars.append(temperature)
    builder.block.diff_vars.append(vf.add_diff_var(name=f'd_ExhaustTemperaturePu_{builder.name}', base_var=temperature))
    builder.block.state_eqs.append((fuel - temperature) / t3)
    builder.block.init_eqs[temperature] = equilibrium
    pm: Var = builder.algebraic('PmPu', fuel - damping * (omega - Const(1.0)), equilibrium)
    return builder.finish((pm, valve), 'Gas-turbine speed governor with exhaust-temperature limiting')
