# SPDX-License-Identifier: MPL-2.0
"""Power stabilizer with derivative reset, phase compensation and output filtering."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_stab4_template(vf: VarFactory, name: str | None = None,
                         gain: float = 1.0, transducer_time: float = .02,
                         first_lag_time: float = .1, reset_time: float = 1.0,
                         lead1_time: float = .2, lead2_time: float = .2,
                         second_lag_time: float = .1, output_lag1_time: float = .05,
                         output_lag2_time: float = .05, lower_limit: float = -.1,
                         upper_limit: float = .1) -> RmsModelTemplate:
    """Build a six-stage power stabilizer with asymmetric voltage limits.

    Measured electrical power minus an independent reference drives a negative
    derivative/reset element ``-KX*s/(1+s*TX2)``. Two compensators provide
    ``(1+s*Ta)/(1+s*TX1)`` and ``(1+s*Tb)/(1+s*Tc)`` phase shaping, followed by
    two low-pass output filters with times Td and Te. Final supplementary
    voltage is hard-limited between L1 and L2 without freezing internal states.

    Open inputs ``PePu`` and ``PRefPu`` use the machine MVA base; ``VsPu`` is the
    exciter voltage-base output. With all denominator times positive the graph
    has six states. The transducer and final two filters permit zero-time
    algebraic forms. The power-reference offset initializes the reset memory;
    all phase/output states initialize to zero, rejecting constant power offsets.

    :param vf: Symbol factory owning this graph.
    :param name: Optional label, defaulting to STAB4.
    :param gain: Derivative numerator KX.
    :param transducer_time: Nonnegative watt-transducer time TT in seconds.
    :param first_lag_time: Positive first phase-compensator denominator TX1.
    :param reset_time: Positive washout/reset denominator TX2.
    :param lead1_time: First phase-compensator numerator Ta in seconds.
    :param lead2_time: Second phase-compensator numerator Tb in seconds.
    :param second_lag_time: Positive second phase-compensator denominator Tc.
    :param output_lag1_time: Nonnegative first output-filter time Td.
    :param output_lag2_time: Nonnegative second output-filter time Te.
    :param lower_limit: Nonpositive supplementary-voltage lower bound L1.
    :param upper_limit: Nonnegative supplementary-voltage upper bound L2.
    :return: Native phase-compensated electrical-power stabilizer.
    :raises ValueError: Invalid dynamics or bounds that exclude zero equilibrium.
    """
    if min(first_lag_time, reset_time, second_lag_time) <= 0 or min(transducer_time, output_lag1_time, output_lag2_time) < 0:
        raise ValueError('Phase-compensated stabilizer time constants are invalid')
    elif lower_limit > 0 or upper_limit < 0 or upper_limit <= lower_limit:
        raise ValueError('Stabilizer voltage limits must include zero and have positive width')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf, 'STAB4' if name is None else name)
    kx: Var = builder.parameter('KX', gain)
    tt: Var = builder.parameter('TT', transducer_time)
    tx1: Var = builder.parameter('TX1', first_lag_time)
    tx2: Var = builder.parameter('TX2', reset_time)
    ta: Var = builder.parameter('Ta', lead1_time)
    tb: Var = builder.parameter('Tb', lead2_time)
    tc: Var = builder.parameter('Tc', second_lag_time)
    td: Var = builder.parameter('Td', output_lag1_time)
    te: Var = builder.parameter('Te', output_lag2_time)
    lower: Var = builder.parameter('L1', lower_limit)
    upper: Var = builder.parameter('L2', upper_limit)
    power: Var = builder.input('PePu', Const(.5))
    reference: Var = builder.input('PRefPu', Const(.5))
    measured: Var = builder.lag('MeasuredPowerPu', power, tt, transducer_time, power)
    derivative: Var = builder.washout('DerivativePu', measured - reference, tx2, reset_time, -kx / tx2, power - reference)
    first: Var = builder.lead_lag('Phase1Pu', derivative, ta, tx1, lead1_time, first_lag_time, Const(0.0))
    second: Var = builder.lead_lag('Phase2Pu', first, tb, tc, lead2_time, second_lag_time, Const(0.0))
    filtered1: Var = builder.lag('OutputFilter1Pu', second, td, output_lag1_time, Const(0.0))
    filtered2: Var = builder.lag('OutputFilter2Pu', filtered1, te, output_lag2_time, Const(0.0))
    output: Var = builder.algebraic('VsPu', sym.hard_sat(filtered2, lower, upper), Const(0.0))
    return builder.finish((output,), 'Electrical-power stabilizer with derivative reset and two phase compensators')
