# SPDX-License-Identifier: MPL-2.0
"""Steam governor with speed compensation and three turbine power stages."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class SteamGovernorParameters:
    """Speed-controller dynamics, turbine delays and mechanical-power fractions."""

    __slots__ = ('t1', 't2', 't3', 't4', 't5', 't6', 'gain', 'reheat_fraction',
                 'low_pressure_fraction', 'power_max', 'power_min', 'deadband_low', 'deadband_high')

    def __init__(self, t1: float = 0.1, t2: float = 0.0, t3: float = 0.2,
                 t4: float = 0.3, t5: float = 5.0, t6: float = 0.5,
                 gain: float = 20.0, reheat_fraction: float = 0.6,
                 low_pressure_fraction: float = 0.5, power_max: float = 1.2,
                 power_min: float = 0.0, deadband_low: float = 0.0,
                 deadband_high: float = 0.0) -> None:
        """Store the settings for one steam turbine and speed controller.

        :param t1: Nonnegative controller denominator time constant in seconds.
        :param t2: Nonnegative controller lead time; zero if t1 is zero.
        :param t3: Positive governor lag time constant in seconds.
        :param t4: Nonnegative steam-chest delay in seconds.
        :param t5: Nonnegative reheater delay in seconds.
        :param t6: Nonnegative crossover/low-pressure delay in seconds.
        :param gain: Nonnegative inverse speed droop on turbine power base.
        :param reheat_fraction: Fraction of steam-chest output sent through reheat.
        :param low_pressure_fraction: Fraction of reheated power sent through the final stage.
        :param power_max: Upper valve-demand power limit in per unit.
        :param power_min: Lower valve-demand power limit in per unit.
        :param deadband_low: Nonpositive underspeed deadband threshold.
        :param deadband_high: Nonnegative overspeed deadband threshold.
        """
        self.t1: float = t1
        self.t2: float = t2
        self.t3: float = t3
        self.t4: float = t4
        self.t5: float = t5
        self.t6: float = t6
        self.gain: float = gain
        self.reheat_fraction: float = reheat_fraction
        self.low_pressure_fraction: float = low_pressure_fraction
        self.power_max: float = power_max
        self.power_min: float = power_min
        self.deadband_low: float = deadband_low
        self.deadband_high: float = deadband_high


def build_ieesgo_template(vf: VarFactory, name: str | None = None,
                          parameters: SteamGovernorParameters | None = None) -> RmsModelTemplate:
    """Build a speed-compensated steam governor with staged turbine power.

    Shaft-speed deviation passes through a lead-lag compensator and governor
    lag, with inverse droop gain K1. This correction is subtracted from the
    independent load reference and hard-limited before entering the steam chest.
    A fraction ``1-K2`` contributes high-pressure power immediately after that
    chest lag. The remaining fraction passes through the reheater; ``1-K3`` of
    reheater output contributes intermediate-pressure power and the rest passes
    through the crossover lag before contributing low-pressure power.

    The open inputs are absolute per-unit speed ``OmegaPu`` and turbine-base
    ``PRefPu``. Outputs are total mechanical power ``PmPu`` and limited valve
    demand ``ValvePu``. Five states are present with positive controller/chest/
    reheat/crossover time constants. Zero-time stages become exact algebraic
    equations; the positive governor lag remains dynamic. Nominal-speed initial
    conditions allocate the load reference among stages using the same fractions
    as the running equations, so the assembled turbine starts in equilibrium.

    :param vf: Symbol factory owning this controller graph.
    :param name: Optional unique label, defaulting to IEESGO.
    :param parameters: Physical settings and structural zero-time choices.
    :return: Native governor with explicit turbine-stage states and power output.
    :raises ValueError: Nonfinite parameters, invalid time constants, fractions or limits.
    """
    settings: SteamGovernorParameters = SteamGovernorParameters() if parameters is None else parameters
    if settings.t3 <= 0 or min(settings.t1, settings.t2, settings.t4, settings.t5, settings.t6) < 0:
        raise ValueError('Steam governor time constants are invalid')
    elif not 0 <= settings.reheat_fraction <= 1 or not 0 <= settings.low_pressure_fraction <= 1 or settings.gain < 0:
        raise ValueError('Steam governor fractions/gain are invalid')
    elif settings.power_max <= settings.power_min:
        raise ValueError('Steam governor upper power limit must exceed lower limit')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf, 'IEESGO' if name is None else name)
    t1: Var = builder.parameter('T1', settings.t1)
    t2: Var = builder.parameter('T2', settings.t2)
    t3: Var = builder.parameter('T3', settings.t3)
    t4: Var = builder.parameter('T4', settings.t4)
    t5: Var = builder.parameter('T5', settings.t5)
    t6: Var = builder.parameter('T6', settings.t6)
    gain: Var = builder.parameter('K1', settings.gain)
    k2: Var = builder.parameter('K2', settings.reheat_fraction)
    k3: Var = builder.parameter('K3', settings.low_pressure_fraction)
    pmax: Var = builder.parameter('PMAX', settings.power_max)
    pmin: Var = builder.parameter('PMIN', settings.power_min)
    omega: Var = builder.input('OmegaPu', Const(1.0))
    pref: Var = builder.input('PRefPu', Const(0.5))
    controlled_speed: Var = builder.speed_deviation(omega,settings.deadband_low,settings.deadband_high)
    speed: Var = builder.lead_lag('SpeedCompensatedPu', gain * controlled_speed,
        t2, t1, settings.t2, settings.t1, Const(0.0))
    correction: Var = builder.lag('GovernorCorrectionPu', speed, t3, settings.t3, Const(0.0))
    valve_initial: Expr = sym.hard_sat(pref, pmin, pmax)
    valve: Var = builder.algebraic('ValvePu', sym.hard_sat(pref - correction, pmin, pmax), valve_initial)
    chest: Var = builder.lag('SteamChestPu', valve, t4, settings.t4, valve_initial)
    reheat: Var = builder.lag('ReheatPu', k2 * chest, t5, settings.t5, k2 * valve_initial)
    crossover: Var = builder.lag('CrossoverPu', k3 * reheat, t6, settings.t6, k3 * k2 * valve_initial)
    pm: Var = builder.algebraic('PmPu', (Const(1.0) - k2) * chest + (Const(1.0) - k3) * reheat + crossover, valve_initial)
    return builder.finish((pm, valve), 'Speed-compensated governor with high/intermediate/low-pressure steam stages')
