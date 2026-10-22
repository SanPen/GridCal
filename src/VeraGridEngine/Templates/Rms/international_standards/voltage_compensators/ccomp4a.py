# SPDX-License-Identifier: MPL-2.0
"""Four-unit reactive-current sharing correction for a local voltage regulator."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_ccomp4a_template(vf: VarFactory, name: str | None = None,
                           gains: tuple[float,float,float,float] = (1.0,-1.0,0.0,0.0),
                           overall_gain: float = 1.0, lower_limit: float = -.1,
                           upper_limit: float = .1) -> RmsModelTemplate:
    """Build a bounded cross-current correction from up to four generating units.

    The signed reactive-current measurements are individually weighted and
    summed. Overall gain Kc converts that imbalance into a voltage correction,
    bounded between Vmin and Vmax. The bounded correction is added to the local
    terminal-voltage magnitude; the limits apply to the correction, not the
    final measured voltage. Opposite-signed weights can balance reactive sharing,
    while a single negative weight provides line-drop compensation.

    Inputs are local ``VtPu`` followed by ``Iq1Pu`` through ``Iq4Pu``. Each Iq is
    the signed imaginary/reactive component in the applicable terminal-current
    reference frame, not the rotor q-axis current merely because its name is
    similar. Currents from differently rated machines must first be expressed
    on the common base used by the gain coefficients. Unused units supply zero.
    The stateless graph exposes measured voltage ``VcPu`` and the bounded
    ``CorrectionPu``; equilibrium uses the same live current-weighting equations.

    :param vf: Symbol factory owning this instance.
    :param name: Optional label, defaulting to CCOMP4A.
    :param gains: Four signed current weights K1 through K4 on a common base.
    :param overall_gain: Overall imbalance-to-voltage gain Kc.
    :param lower_limit: Lower bound on the voltage correction.
    :param upper_limit: Upper bound on the voltage correction.
    :return: Native four-unit sharing compensator without dynamic states.
    :raises ValueError: Nonfinite settings, wrong weight count or reversed limits.
    """
    if len(gains) != 4 or upper_limit <= lower_limit:
        raise ValueError('Sharing compensator needs four weights and ordered limits')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf,'CCOMP4A' if name is None else name)
    weights: tuple[Var,...] = tuple(builder.parameter(f'K{index+1}',value) for index,value in enumerate(gains))
    gain: Var = builder.parameter('Kc',overall_gain)
    lower: Var = builder.parameter('Vmin',lower_limit)
    upper: Var = builder.parameter('Vmax',upper_limit)
    voltage: Var = builder.input('VtPu',Const(1.0))
    currents: tuple[Var,...] = tuple(builder.input(f'Iq{index+1}Pu',Const(0.0)) for index in range(4))
    imbalance: Expr = weights[0]*currents[0]+weights[1]*currents[1]+weights[2]*currents[2]+weights[3]*currents[3]
    correction: Var = builder.algebraic('CorrectionPu',sym.hard_sat(gain*imbalance,lower,upper),sym.hard_sat(gain*imbalance,lower,upper))
    measured: Var = builder.algebraic('VcPu',voltage+correction,voltage+correction)
    return builder.finish((measured,correction),'Four-unit reactive-current sharing voltage compensation')
