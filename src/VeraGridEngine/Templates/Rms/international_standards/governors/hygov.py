# SPDX-License-Identifier: MPL-2.0
"""Filtered PI gate regulation with nonlinear rigid-water-column energy conversion."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class NonlinearHydroGovernorParameters:
    """Gate-regulator and hydraulic coefficients on one declared turbine base."""

    __slots__ = ('permanent_droop','temporary_droop','reset_time','filter_time','gate_time',
                 'velocity','maximum','minimum','water_time','gain','damping','no_load_flow',
                 'deadband_low','deadband_high')

    def __init__(self, permanent_droop: float = .05, temporary_droop: float = .3,
                 reset_time: float = 5., filter_time: float = .05, gate_time: float = .5,
                 velocity: float = .2, maximum: float = 1., minimum: float = 0.,
                 water_time: float = 1., gain: float = 1., damping: float = 0.,
                 no_load_flow: float = .08, deadband_low: float = 0., deadband_high: float = 0.) -> None:
        """Store turbine-base hydraulic and governor settings.

        :param permanent_droop: Positive speed droop from actual gate position.
        :param temporary_droop: Positive normalization of PI action.
        :param reset_time: Positive PI reset time in seconds.
        :param filter_time: Positive error measurement time in seconds.
        :param gate_time: Positive gate actuator lag in seconds.
        :param velocity: Positive bound on total PI gate-demand velocity.
        :param maximum: Maximum gate-demand position.
        :param minimum: Nonnegative minimum gate-demand position.
        :param water_time: Positive rigid-water-column time in seconds.
        :param gain: Positive hydraulic power gain.
        :param damping: Nonnegative speed damping multiplied by actual gate.
        :param no_load_flow: Nonnegative flow at nominal head and zero output.
        :param deadband_low: Nonpositive underspeed deadband threshold.
        :param deadband_high: Nonnegative overspeed deadband threshold.
        """
        self.permanent_droop: float = permanent_droop
        self.temporary_droop: float = temporary_droop
        self.reset_time: float = reset_time
        self.filter_time: float = filter_time
        self.gate_time: float = gate_time
        self.velocity: float = velocity
        self.maximum: float = maximum
        self.minimum: float = minimum
        self.water_time: float = water_time
        self.gain: float = gain
        self.damping: float = damping
        self.no_load_flow: float = no_load_flow
        self.deadband_low: float = deadband_low
        self.deadband_high: float = deadband_high


def build_hygov_template(vf: VarFactory, name: str | None = None,
                         parameters: NonlinearHydroGovernorParameters | None = None) -> RmsModelTemplate:
    """Build filtered PI gate regulation coupled to a rigid hydraulic column.

    Speed/load reference minus controlled speed deviation minus permanent droop
    times actual gate position feeds the error transducer. Its output e drives
    the PI transfer ``(1+s*Tr)/(r*Tr*s)``. The desired-gate state therefore has
    derivative ``(e_dot+e/Tr)/r``. Velocity clipping and directional position
    stops apply to this total PI output, preserving both proportional and
    integral action. A separate gate servo follows desired gate through Tg.
    Limiting only the actual gate velocity or replacing this PI with a reset
    lag would change the governor transfer function and transient response.

    Hydraulic head is exactly ``h=(q/g)**2``. Column acceleration is
    ``q_dot=(1-h)/Tw`` and power is ``At*(q-qNL)*h-Dturb*g*(omega-1)``.
    This nonlinear relation preserves inverse hydraulic response and uses
    unmodified shaft-speed deviation for damping even when control deadband
    is enabled. The domain requires positive actual gate; with positive initial
    gate and bounded nonnegative demand the actuator approaches closure
    asymptotically. No arbitrary denominator floor changes the water equations.

    Four states are filtered error, desired gate, actual gate and water flow.
    Inputs are absolute per-unit shaft speed and a speed/load reference. Outputs
    are mechanical power, actual gate and flow. Nominal-head initialization has
    gate=flow=reference/R and zero filtered error. The reference is in speed
    units; the host obtains it from mechanical power as
    ``R*(initial_power/At+qNL)``. Powers and flows use the declared turbine base;
    times are seconds. The host must initialize a positive gate within limits.

    :param vf: Shared native symbolic factory.
    :param name: Optional controller label.
    :param parameters: Physical hydraulic and regulator coefficients.
    :return: Native four-state, two-input hydro governor.
    :raises ValueError: Nonfinite or physically invalid settings.
    """
    p: NonlinearHydroGovernorParameters = NonlinearHydroGovernorParameters() if parameters is None else parameters
    positive: tuple[float,...] = (p.permanent_droop,p.temporary_droop,p.reset_time,p.filter_time,
        p.gate_time,p.velocity,p.water_time,p.gain)
    values: tuple[float,...] = (p.minimum,p.maximum,p.damping,p.no_load_flow,p.deadband_low,p.deadband_high)
    if not all(math.isfinite(value) for group in (positive,values) for value in group):
        raise ValueError('Hydro-governor coefficients must be finite')
    elif min(positive) <= 0 or min(p.minimum,p.damping,p.no_load_flow) < 0 or p.maximum <= p.minimum:
        raise ValueError('Hydro-governor times/droops/gain must be positive and limits ordered/nonnegative')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'HYGOV' if name is None else name)
    r: Var = c.parameter('Rperm',p.permanent_droop)
    temporary: Var = c.parameter('Rtemp',p.temporary_droop)
    tr: Var = c.parameter('Tr',p.reset_time)
    tf: Var = c.parameter('Tf',p.filter_time)
    tg: Var = c.parameter('Tg',p.gate_time)
    velocity: Var = c.parameter('Velm',p.velocity)
    gmax: Var = c.parameter('Gmax',p.maximum)
    gmin: Var = c.parameter('Gmin',p.minimum)
    tw: Var = c.parameter('Tw',p.water_time)
    gain: Var = c.parameter('At',p.gain)
    damping: Var = c.parameter('Dturb',p.damping)
    qnl: Var = c.parameter('Qnl',p.no_load_flow)
    omega: Var = c.input('OmegaPu',Const(1.))
    pref: Var = c.input('PRefPu',r*(Const(.5)/gain+qnl))
    initial_gate: Expr = pref/r
    speed: Var = c.speed_deviation(omega,p.deadband_low,p.deadband_high)
    gate: Var = vf.add_var('GatePu_'+c.name)
    desired: Var = vf.add_var('DesiredGatePu_'+c.name)
    error: Var = vf.add_var('FilterOutputPu_'+c.name)
    error_rate: Expr = (pref-speed-r*gate-error)/tf
    c.differential(error,error_rate,Const(0.))
    total_rate: Expr = sym.hard_sat((error_rate+error/tr)/temporary,-velocity,velocity)
    c.differential(desired,total_rate,initial_gate,gmin,gmax)
    c.differential(gate,(desired-gate)/tg,initial_gate)
    flow: Var = vf.add_var('TurbineFlowPu_'+c.name)
    head: Var = c.algebraic('HeadPu',(flow/gate)**Const(2.),Const(1.))
    c.differential(flow,(Const(1.)-head)/tw,initial_gate)
    pm: Var = c.algebraic('PmPu',gain*(flow-qnl)*head-damping*gate*(omega-Const(1.)),gain*(initial_gate-qnl))
    return c.finish((pm,gate,flow),'Filtered PI gate regulator and nonlinear rigid hydraulic column')
