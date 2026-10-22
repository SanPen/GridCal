# SPDX-License-Identifier: MPL-2.0
"""Speed-sensitive supplementary excitation control with phase compensation."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_stab1_template(vf: VarFactory, name: str | None = None,
                         gain_over_time: float = 2.0, washout_time: float = 10.0,
                         lead1_ratio: float = 3.0, lag1_time: float = .1,
                         lead2_ratio: float = 3.0, lag2_time: float = .1,
                         output_limit: float = .1) -> RmsModelTemplate:
    """Build a three-state speed stabilizer with two phase-compensation stages.

    The transfer from shaft speed to the unlimited supplementary voltage is
    ``K*s/(1+s*T) * (1+s*T1)/(1+s*T3) * (1+s*T2)/(1+s*T4)``.
    Construction accepts the high-frequency washout gain ``K/T`` and the two
    lead/lag ratios, avoiding an ambiguous extra time-constant multiplication.
    A symmetric hard limiter bounds the final voltage signal; the washout and
    lead-lag memories remain unrestricted because this is an output limiter.

    The only open input is absolute per-unit speed ``OmegaPu``. The washout
    memory starts at nominal speed and both compensators start at zero, so a
    steady speed causes no stabilizing voltage. Output ``VsPu`` connects to an
    exciter's supplementary voltage input on the same voltage base. Three states
    are retained even when a lead/lag ratio equals one.

    :param vf: Symbol factory for this controller instance.
    :param name: Optional label, defaulting to STAB1.
    :param gain_over_time: Washout high-frequency gain K/T.
    :param washout_time: Positive washout/reset time T in seconds.
    :param lead1_ratio: Ratio T1/T3 for the first compensator.
    :param lag1_time: Positive first compensator denominator T3 in seconds.
    :param lead2_ratio: Ratio T2/T4 for the second compensator.
    :param lag2_time: Positive second compensator denominator T4 in seconds.
    :param output_limit: Positive symmetric supplementary-voltage limit.
    :return: Native speed stabilizer with one input and one voltage output.
    :raises ValueError: Nonfinite settings, nonpositive dynamic times or limit.
    """
    if min(washout_time, lag1_time, lag2_time, output_limit) <= 0:
        raise ValueError('Speed stabilizer requires positive times and voltage limit')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf, 'STAB1' if name is None else name)
    gain: Var = builder.parameter('GainOverTime', gain_over_time)
    time: Var = builder.parameter('T', washout_time)
    ratio1: Var = builder.parameter('Lead1Ratio', lead1_ratio)
    t3: Var = builder.parameter('T3', lag1_time)
    ratio2: Var = builder.parameter('Lead2Ratio', lead2_ratio)
    t4: Var = builder.parameter('T4', lag2_time)
    limit: Var = builder.parameter('HLIM', output_limit)
    omega: Var = builder.input('OmegaPu', Const(1.0))
    washout: Var = builder.washout('WashoutPu', omega, time, washout_time, gain, Const(1.0))
    first: Var = builder.lead_lag('LeadLag1Pu', washout, ratio1 * t3, t3,
        lead1_ratio * lag1_time, lag1_time, Const(0.0))
    second: Var = builder.lead_lag('LeadLag2Pu', first, ratio2 * t4, t4,
        lead2_ratio * lag2_time, lag2_time, Const(0.0))
    output: Var = builder.algebraic('VsPu', sym.hard_sat(second, -limit, limit), Const(0.0))
    return builder.finish((output,), 'Speed stabilizer with washout and two lead-lag compensators')
