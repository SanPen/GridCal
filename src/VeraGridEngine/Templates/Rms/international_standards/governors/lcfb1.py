# SPDX-License-Identifier: MPL-2.0
"""Outer-loop measured-power regulation and frequency bias for a turbine-governor reference."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class TurbineLoadControllerParameters:
    """Power measurement, error shaping and bounded PI correction settings."""

    __slots__ = ('frequency_bias', 'power_time', 'deadband', 'error_limit',
                 'proportional_gain', 'integral_gain', 'correction_limit')

    def __init__(self, frequency_bias: float = 0.0, power_time: float = 2.0,
                 deadband: float = 0.0, error_limit: float = .1,
                 proportional_gain: float = 0.0, integral_gain: float = .05,
                 correction_limit: float = .05) -> None:
        """Store one enabled measured-power controller's physical coefficients.

        :param frequency_bias: Nonnegative speed-deviation bias gain; zero disables frequency bias.
        :param power_time: Nonnegative electrical-power transducer time in seconds.
        :param deadband: Nonnegative continuous error deadband width.
        :param error_limit: Positive magnitude bound on deadband-adjusted error.
        :param proportional_gain: Nonnegative proportional gain to governor-reference units.
        :param integral_gain: Nonnegative integral gain to reference units per second.
        :param correction_limit: Positive magnitude bound for integral memory and total correction.
        """
        self.frequency_bias: float = frequency_bias
        self.power_time: float = power_time
        self.deadband: float = deadband
        self.error_limit: float = error_limit
        self.proportional_gain: float = proportional_gain
        self.integral_gain: float = integral_gain
        self.correction_limit: float = correction_limit


def build_lcfb1_template(vf: VarFactory, name: str | None = None,
                         parameters: TurbineLoadControllerParameters | None = None) -> RmsModelTemplate:
    """Build an enabled outer power controller that adjusts a governor reference.

    A first-order transducer measures electrical power. The error is power
    setpoint minus measured power minus frequency bias times speed deviation.
    A continuous deadband subtracts its directional threshold outside the band;
    a separate symmetric limiter bounds the resulting error. Proportional and
    integral paths then add. Integral memory has directional non-windup stops,
    while an independent output limiter bounds their combined correction.
    Adding the frozen initial governor reference gives the live governor command.

    There are two states: measured power and integral memory. Zero transducer
    time removes the measurement state exactly. Zero deadband removes its
    switching expression, preserving the equilibrium error Jacobian. Zero
    integral gain retains a constant initialized memory rather than inventing
    an inverse-time coefficient. Electrical power and its setpoint use the same
    declared power base; gains convert their error to the governor's reference
    units. Time constants are seconds and shaft speed is per unit.

    Inputs are absolute shaft speed, electrical power, initial governor reference
    and power setpoint. Outputs are corrected reference and the bounded additive
    correction. At nominal speed, power setpoint equals initial electrical power,
    the measurement stores that power, and integral memory/correction start at
    zero. The reference offset is distinct from the power setpoint, allowing
    initial mechanical losses and valve-to-power gain to remain represented.
    The host owns these initial values and the governor connection.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical power-feedback and reference-correction settings.
    :return: Native outer load controller with four open inputs.
    :raises ValueError: Invalid or nonfinite physical settings.
    """
    p: TurbineLoadControllerParameters = TurbineLoadControllerParameters() if parameters is None else parameters
    values: tuple[float, ...] = (p.frequency_bias, p.power_time, p.deadband, p.error_limit,
                               p.proportional_gain, p.integral_gain, p.correction_limit)
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Turbine load-control coefficients must be finite')
    elif min(p.frequency_bias, p.power_time, p.deadband, p.proportional_gain, p.integral_gain) < 0 or min(p.error_limit, p.correction_limit) <= 0:
        raise ValueError('Turbine load-control times/gains must be nonnegative and limits positive')
    else:
        pass
    control: ControlRealization = ControlRealization(vf, 'LCFB1' if name is None else name)
    bias: Var = control.parameter('FB', p.frequency_bias)
    time: Var = control.parameter('TPELEC', p.power_time)
    deadband: Var = control.parameter('DB', p.deadband)
    error_max: Var = control.parameter('EMAX', p.error_limit)
    kp: Var = control.parameter('KP', p.proportional_gain)
    ki: Var = control.parameter('KI', p.integral_gain)
    limit: Var = control.parameter('LRMAX', p.correction_limit)
    omega: Var = control.input('OmegaPu', Const(1.0))
    power: Var = control.input('ElectricalPowerPu', Const(.5))
    reference: Var = control.input('InitialReferencePu', Const(.5))
    setpoint: Var = control.input('PowerSetpointPu', power)
    measured: Var = control.lag('MeasuredPowerPu', power, time, p.power_time, power)
    error: Var = control.algebraic('PowerErrorPu', setpoint-measured-bias*(omega-Const(1.0)), Const(0.0))
    shaped: Expr
    if p.deadband == 0:
        shaped = error
    else:
        shaped = sym.max(error-deadband, Const(0.0))+sym.min(error+deadband, Const(0.0))
    bounded: Var = control.algebraic('LimitedErrorPu', sym.hard_sat(shaped, -error_max, error_max), Const(0.0))
    memory: Var = vf.add_var('IntegralMemoryPu_'+control.name)
    control.differential(memory, ki*bounded, Const(0.0), -limit, limit)
    correction: Var = control.algebraic('ReferenceCorrectionPu', sym.hard_sat(kp*bounded+memory, -limit, limit), Const(0.0))
    command: Var = control.algebraic('ReferencePu', reference+correction, reference)
    return control.finish((command, correction), 'Measured-power outer controller with optional frequency bias and bounded reference correction')
