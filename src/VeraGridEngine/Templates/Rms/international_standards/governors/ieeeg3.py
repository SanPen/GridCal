# SPDX-License-Identifier: MPL-2.0
"""Hydraulic speed regulation with pilot-valve dynamics and a linearized water column."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class HydraulicGovernorParameters:
    """Pilot, gate, droop and linearized turbine settings on one turbine power base."""

    __slots__ = ('gate_time', 'pilot_time', 'opening_rate', 'closing_rate', 'gate_max',
                 'gate_min', 'permanent_droop', 'transient_droop', 'reset_time',
                 'water_time', 'a11', 'a13', 'a21', 'a23', 'deadband_high', 'deadband_low')

    def __init__(self, gate_time: float = .2, pilot_time: float = .05,
                 opening_rate: float = .1, closing_rate: float = -.1,
                 gate_max: float = 1.2, gate_min: float = 0.0,
                 permanent_droop: float = .05, transient_droop: float = .4,
                 reset_time: float = 5.0, water_time: float = 1.0,
                 a11: float = .5, a13: float = 1.0, a21: float = 1.5, a23: float = 1.0,
                 deadband_high: float = 0.0, deadband_low: float = 0.0) -> None:
        """Store physical governor and water-column coefficients.

        :param gate_time: Positive gate servomotor gain normalization time, in seconds.
        :param pilot_time: Positive pilot-valve lag time in seconds.
        :param opening_rate: Positive gate-opening speed limit, in per-unit gate per second.
        :param closing_rate: Negative gate-closing speed limit, in per-unit gate per second.
        :param gate_max: Upper gate-position limit.
        :param gate_min: Lower gate-position limit.
        :param permanent_droop: Positive speed droop per per-unit gate position.
        :param transient_droop: Nonnegative transient speed-droop coefficient.
        :param reset_time: Positive transient-droop reset time in seconds.
        :param water_time: Positive water starting time in seconds.
        :param a11: Positive linearized flow/head coefficient.
        :param a13: Linearized flow/gate coefficient.
        :param a21: Linearized power/head coefficient.
        :param a23: Positive steady gate-to-power gain.
        :param deadband_high: Nonnegative overspeed deadband threshold.
        :param deadband_low: Nonpositive underspeed deadband threshold.
        """
        self.gate_time: float = gate_time
        self.pilot_time: float = pilot_time
        self.opening_rate: float = opening_rate
        self.closing_rate: float = closing_rate
        self.gate_max: float = gate_max
        self.gate_min: float = gate_min
        self.permanent_droop: float = permanent_droop
        self.transient_droop: float = transient_droop
        self.reset_time: float = reset_time
        self.water_time: float = water_time
        self.a11: float = a11
        self.a13: float = a13
        self.a21: float = a21
        self.a23: float = a23
        self.deadband_high: float = deadband_high
        self.deadband_low: float = deadband_low


def build_ieeeg3_template(vf: VarFactory, name: str | None = None,
                          parameters: HydraulicGovernorParameters | None = None) -> RmsModelTemplate:
    """Build hydraulic speed regulation with permanent and transient gate droop.

    Absolute shaft speed is reduced by nominal speed, optionally passed through
    a continuous asymmetric deadband, and subtracted from a load reference.
    Permanent feedback is sigma times gate position; transient feedback is
    ``delta*s*Tr/(1+s*Tr)`` times gate position. Pilot-valve dynamics
    ``1/(Tg*(1+s*Tp))`` produce bounded gate velocity. The gate integrates this
    velocity with directional position stops. Both velocity and position limits
    block outward derivatives while permitting inward recovery.

    The linearized hydraulic turbine transfer from gate position to power is
    ``a23*(1+(a11-a13*a21/a23)*Tw*s)/(1+a11*Tw*s)``. A negative numerator
    coefficient preserves the water column's initial inverse power response.
    Four states store pilot-valve velocity, gate position, transient-droop memory
    and turbine memory. At nominal speed, the load-power reference determines
    gate position as PRef/a23, pilot velocity is zero, and both other memories
    follow that gate position. The gate must lie inside its configured limits.

    Inputs are absolute per-unit shaft speed and mechanical load-power reference.
    Outputs are mechanical power, gate position and deadband-adjusted speed
    deviation. Powers and gate limits use the turbine's own power base; a host
    performs base conversion. Times are seconds, rate limits are per second,
    and droop is per-unit speed per per-unit gate. Two zero deadband thresholds
    remove its switching expression structurally and preserve the equilibrium
    speed Jacobian; enabling deadband afterward requires rebuilding the graph.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical pilot, gate, droop and turbine settings.
    :return: Native four-state hydraulic governor with open host-owned inputs.
    :raises ValueError: Nonfinite settings, invalid limits or nonpositive required dynamics.
    """
    p: HydraulicGovernorParameters = HydraulicGovernorParameters() if parameters is None else parameters
    values: tuple[float, ...] = (p.gate_time, p.pilot_time, p.opening_rate, p.closing_rate,
        p.gate_max, p.gate_min, p.permanent_droop, p.transient_droop, p.reset_time,
        p.water_time, p.a11, p.a13, p.a21, p.a23, p.deadband_high, p.deadband_low)
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Hydraulic governor coefficients must be finite')
    elif min(p.gate_time, p.pilot_time, p.permanent_droop, p.reset_time, p.water_time, p.a11, p.a23) <= 0:
        raise ValueError('Hydraulic governor dynamics, permanent droop and steady turbine gains must be positive')
    elif p.opening_rate <= 0 or p.closing_rate >= 0 or p.gate_max <= p.gate_min:
        raise ValueError('Hydraulic governor requires signed travel rates and ordered gate limits')
    elif p.transient_droop < 0 or p.deadband_high < 0 or p.deadband_low > 0:
        raise ValueError('Hydraulic governor transient droop or deadband has an invalid sign')
    else:
        pass
    control: ControlRealization = ControlRealization(vf, 'IEEEG3' if name is None else name)
    tg: Var = control.parameter('TG', p.gate_time)
    tp: Var = control.parameter('TP', p.pilot_time)
    opening: Var = control.parameter('UO', p.opening_rate)
    closing: Var = control.parameter('UC', p.closing_rate)
    maximum: Var = control.parameter('PMAX', p.gate_max)
    minimum: Var = control.parameter('PMIN', p.gate_min)
    sigma: Var = control.parameter('SIGMA', p.permanent_droop)
    delta: Var = control.parameter('DELTA', p.transient_droop)
    tr: Var = control.parameter('TR', p.reset_time)
    tw: Var = control.parameter('TW', p.water_time)
    a11: Var = control.parameter('A11', p.a11)
    a13: Var = control.parameter('A13', p.a13)
    a21: Var = control.parameter('A21', p.a21)
    a23: Var = control.parameter('A23', p.a23)
    high: Var = control.parameter('DBH', p.deadband_high)
    low: Var = control.parameter('DBL', p.deadband_low)
    omega: Var = control.input('OmegaPu', Const(1.0))
    reference: Var = control.input('PRefPu', Const(.5))
    initial_gate: Expr = reference/a23
    speed_deviation: Expr = omega-Const(1.0)
    if p.deadband_high != 0 or p.deadband_low != 0:
        speed_deviation = sym.max(speed_deviation-high, Const(0.0))+sym.min(speed_deviation-low, Const(0.0))
    else:
        pass
    speed: Var = control.algebraic('SpeedDeviationPu', speed_deviation, Const(0.0))
    gate: Var = vf.add_var('GatePu_'+control.name)
    reset: Var = control.lag('DroopMemoryPu', gate, tr, p.reset_time, initial_gate)
    demand: Expr = sigma*initial_gate-speed-sigma*gate-delta*(gate-reset)
    pilot: Var = control.lag('PilotVelocityPu', demand/tg, tp, p.pilot_time, Const(0.0), closing, opening)
    control.differential(gate, pilot, initial_gate, minimum, maximum)
    lead: Expr = (a11-a13*a21/a23)*tw
    lag: Expr = a11*tw
    # The helper accepts the symbolic lag expression while construction values
    # select its single-state realization and preserve a negative hydraulic lead.
    water: Var = control.lead_lag('WaterColumnPu', gate, lead, lag,
        (p.a11-p.a13*p.a21/p.a23)*p.water_time, p.a11*p.water_time, initial_gate)
    power: Var = control.algebraic('PmPu', a23*water, reference)
    return control.finish((power, gate, speed), 'Hydraulic governor with pilot-valve dynamics and linearized water-column response')
