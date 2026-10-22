# SPDX-License-Identifier: MPL-2.0
"""Minimum-excitation limiting from active-current and field-current balance."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_mnlex1_template(vf: VarFactory, name: str | None = None,
                          feedback_gain: float = .1, feedback_time: float = 1.0,
                          limiter_gain: float = 1.0, limiter_time: float = .1,
                          maximum: float = .2, slope: float = 1.0) -> RmsModelTemplate:
    """Build an active-current/field-current minimum-excitation limiter.

    The capability signal is ``IRealPu - XadIfdPu/K``. A first-order amplifier
    with gain KM and time TM limits its state between zero and MELMAX. A field-
    voltage rate signal ``KF2*s/(1+s*TF2)`` is subtracted after that amplifier.
    The lower zero limit therefore applies to the amplifier state, not to the
    final supplementary-voltage output: a rising field voltage can legitimately
    produce a temporary negative damping contribution even while the limiter
    itself is inactive.

    Open inputs are active terminal current ``IRealPu``, normalized field-current
    signal ``XadIfdPu`` and field voltage ``EfdPu``. Currents use the machine's
    declared current base and the field signals use its excitation normalization.
    Output ``UelPu`` is an additive exciter voltage. Two states represent the
    limited amplifier and field-feedback memory; zero TM makes only the
    amplifier algebraic. Initialization stores the actual field voltage in the
    feedback memory and places the amplifier at its bounded capability demand.

    :param vf: Symbol factory owning this limiter instance.
    :param name: Optional label, defaulting to MNLEX1.
    :param feedback_gain: Nonnegative field-voltage rate-feedback gain KF2.
    :param feedback_time: Positive feedback denominator TF2 in seconds.
    :param limiter_gain: Positive capability-error gain KM.
    :param limiter_time: Nonnegative amplifier lag TM in seconds.
    :param maximum: Positive amplifier-state upper limit MELMAX.
    :param slope: Positive field-current capability slope K.
    :return: Native minimum-excitation limiter with explicit post-limit damping.
    :raises ValueError: Nonfinite parameters or invalid gains, times or bounds.
    """
    if min(feedback_time,limiter_gain,maximum,slope) <= 0 or min(feedback_gain,limiter_time) < 0:
        raise ValueError('Current-based minimum-excitation settings are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf,'MNLEX1' if name is None else name)
    kf: Var = builder.parameter('KF2',feedback_gain)
    tf: Var = builder.parameter('TF2',feedback_time)
    km: Var = builder.parameter('KM',limiter_gain)
    tm: Var = builder.parameter('TM',limiter_time)
    ceiling: Var = builder.parameter('MELMAX',maximum)
    k: Var = builder.parameter('K',slope)
    active: Var = builder.input('IRealPu',Const(.5))
    field: Var = builder.input('XadIfdPu',Const(1.0))
    voltage: Var = builder.input('EfdPu',Const(1.0))
    demand: Expr = km*(active-field/k)
    amplifier: Var = builder.lag('LimiterPu',demand,tm,limiter_time,
        sym.hard_sat(demand,Const(0.0),ceiling),Const(0.0),ceiling)
    feedback: Var = builder.washout('FieldFeedbackPu',voltage,tf,feedback_time,kf/tf,voltage)
    output: Var = builder.algebraic('UelPu',amplifier-feedback,sym.hard_sat(demand,Const(0.0),ceiling))
    return builder.finish((output,), 'Minimum-excitation limiter with field-current slope and post-limit rate feedback')
