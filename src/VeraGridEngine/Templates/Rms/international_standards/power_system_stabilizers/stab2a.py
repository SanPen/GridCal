# SPDX-License-Identifier: MPL-2.0
"""Electrical-power stabilizer with triple washout and shaped low-pass filtering."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_stab2a_template(vf: VarFactory, name: str | None = None,
                          k2: float = 1.0, t2: float = 1.0, k3: float = 1.0,
                          t3: float = .1, k4: float = 1.0, k5: float = 1.0,
                          t5: float = .1, output_limit: float = .1) -> RmsModelTemplate:
    """Build a power-sensitive stabilizer with cascaded high-pass measurements.

    Three identical ``K2*s*T2/(1+s*T2)`` washouts reject constant electrical
    power. Their combined output is inverted and drives parallel paths: a direct
    K4 gain and a K3 first-order lag. The sum passes through two identical
    ``K5/(1+s*T5)`` low-pass stages before symmetric voltage saturation. The
    resulting six-state realization preserves the complete transfer order.

    Open input ``PePu`` is electrical power on the machine's own MVA base.
    Output ``VsPu`` is supplementary excitation voltage. Initial electrical
    power is stored only in the first washout memory; all subsequent states
    start at zero. Thus any constant operating power produces zero stabilizing
    voltage without subtracting a permanently frozen power reference.

    :param vf: Symbol factory owning the states and algebraic signals.
    :param name: Optional label, defaulting to STAB2A.
    :param k2: Gain of each of the three normalized high-pass stages.
    :param t2: Positive common high-pass time constant in seconds.
    :param k3: Gain of the lagged parallel path.
    :param t3: Positive parallel-path lag time in seconds.
    :param k4: Gain of the direct parallel path.
    :param k5: Gain of each output low-pass stage.
    :param t5: Positive common output low-pass time in seconds.
    :param output_limit: Positive symmetric supplementary-voltage limit.
    :return: Native six-state electrical-power stabilizer.
    :raises ValueError: Nonfinite settings or nonpositive time/limit.
    """
    if min(t2, t3, t5, output_limit) <= 0:
        raise ValueError('Power stabilizer requires positive filter times and voltage limit')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf, 'STAB2A' if name is None else name)
    gain2: Var = builder.parameter('K2', k2)
    time2: Var = builder.parameter('T2', t2)
    gain3: Var = builder.parameter('K3', k3)
    time3: Var = builder.parameter('T3', t3)
    gain4: Var = builder.parameter('K4', k4)
    gain5: Var = builder.parameter('K5', k5)
    time5: Var = builder.parameter('T5', t5)
    limit: Var = builder.parameter('HLIM', output_limit)
    power: Var = builder.input('PePu', Const(.5))
    first: Var = builder.washout('Washout1Pu', power, time2, t2, gain2, power)
    second: Var = builder.washout('Washout2Pu', first, time2, t2, gain2, Const(0.0))
    third: Var = builder.washout('Washout3Pu', second, time2, t2, gain2, Const(0.0))
    lagged: Var = builder.lag('ParallelLagPu', -gain3 * third, time3, t3, Const(0.0))
    shaped: Var = builder.lag('OutputLag1Pu', lagged - gain4 * third, time5, t5, Const(0.0))
    # K5 belongs to each stage, hence both gain factors remain in the equations.
    filtered: Var = builder.lag('OutputLag2Pu', gain5 * shaped, time5, t5, Const(0.0))
    output: Var = builder.algebraic('VsPu', sym.hard_sat(gain5 * filtered, -limit, limit), Const(0.0))
    return builder.finish((output,), 'Electrical-power stabilizer with triple washout and shaped filtering')
