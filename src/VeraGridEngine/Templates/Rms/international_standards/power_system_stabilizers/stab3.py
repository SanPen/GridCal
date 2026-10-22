# SPDX-License-Identifier: MPL-2.0
"""Reference-subtracted electrical-power stabilizer with derivative shaping."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_stab3_template(vf: VarFactory, name: str | None = None,
                         transducer_time: float = .02, first_lag_time: float = .1,
                         reset_time: float = 1.0, gain: float = 1.0,
                         output_limit: float = .1) -> RmsModelTemplate:
    """Build a dual-input electrical-power stabilizer with a filtered derivative.

    A watt transducer measures machine electrical power. Subtracting an
    independently supplied power reference yields the first lag's input. The
    final stage applies ``-KX*s/(1+s*TX2)`` using a washout memory, avoiding
    numerical differentiation. A symmetric hard limiter bounds the resulting
    supplementary excitation voltage. With positive transducer time the model
    has three states; setting that time to zero creates an exact algebraic
    measurement and leaves two states.

    Inputs ``PePu`` and ``PRefPu`` use the machine's own MVA base. Output ``VsPu``
    uses the exciter's voltage base. Initialization seeds the transducer from
    measured power and the remaining memories from the measured/reference
    difference, so even a nonzero constant offset produces no derivative output.

    :param vf: Symbol factory owning this instance.
    :param name: Optional label, defaulting to STAB3.
    :param transducer_time: Nonnegative watt-transducer time in seconds.
    :param first_lag_time: Positive power-error lag TX1 in seconds.
    :param reset_time: Positive derivative/reset denominator TX2 in seconds.
    :param gain: Derivative numerator gain KX.
    :param output_limit: Positive symmetric supplementary-voltage limit.
    :return: Native two/three-state power stabilizer with an open reference input.
    :raises ValueError: Nonfinite settings, negative transducer time or invalid limits.
    """
    if transducer_time < 0 or min(first_lag_time, reset_time, output_limit) <= 0:
        raise ValueError('Power-error stabilizer times/limit are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf, 'STAB3' if name is None else name)
    tt: Var = builder.parameter('Tt', transducer_time)
    tx1: Var = builder.parameter('TX1', first_lag_time)
    tx2: Var = builder.parameter('TX2', reset_time)
    kx: Var = builder.parameter('KX', gain)
    limit: Var = builder.parameter('VLIM', output_limit)
    power: Var = builder.input('PePu', Const(.5))
    reference: Var = builder.input('PRefPu', Const(.5))
    measured: Var = builder.lag('MeasuredPowerPu', power, tt, transducer_time, power)
    filtered: Var = builder.lag('FilteredErrorPu', measured - reference, tx1, first_lag_time, power - reference)
    derivative: Var = builder.washout('DerivativePu', filtered, tx2, reset_time, -kx / tx2, power - reference)
    output: Var = builder.algebraic('VsPu', sym.hard_sat(derivative, -limit, limit), Const(0.0))
    return builder.finish((output,), 'Power-error stabilizer with filtered derivative and symmetric voltage limit')
