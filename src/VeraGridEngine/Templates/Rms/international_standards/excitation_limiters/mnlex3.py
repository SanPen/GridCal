# SPDX-License-Identifier: MPL-2.0
"""Linear reactive-current capability limiter with field-voltage rate feedback."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_mnlex3_template(vf: VarFactory, name: str | None = None,
                          feedback_gain: float = .1, feedback_time: float = 1.0,
                          limiter_gain: float = 1.0, limiter_time: float = .1,
                          maximum: float = .2, reactive_intercept: float = -.2,
                          slope: float = .1) -> RmsModelTemplate:
    """Build a straight-line under-excitation characteristic in current coordinates.

    The capability signal is ``Q0 + B*IActivePu - IReactivePu``, equivalent to
    ``Q0 + B*(P/V) - Q/V`` at nonzero terminal voltage. Using live terminal-frame
    current components makes the controller well-defined through a voltage zero
    without dividing zero power by zero voltage. Reactive current is positive
    for reactive injection; it is not the signed imaginary part of outgoing
    current, which has the opposite sign in the voltage-aligned frame.

    A field-voltage washout ``KF2*s/(1+s*TF2)`` is subtracted before the KM
    amplifier. A non-windup limiter bounds the amplifier output between zero and
    MELMAX. Inputs are ``IActivePu``, ``IReactivePu`` and ``EfdPu``; currents and
    Q0 use the machine base at nominal voltage. Output ``UelPu`` is supplementary
    excitation voltage. Two states are present with positive TM; zero TM removes
    the amplifier state exactly. Equilibrium feedback is zero because its memory
    is initialized from the actual field voltage.

    :param vf: Symbol factory owning this limiter.
    :param name: Optional label, defaulting to MNLEX3.
    :param feedback_gain: Nonnegative field-voltage washout numerator KF2.
    :param feedback_time: Positive washout denominator TF2 in seconds.
    :param limiter_gain: Positive capability-error gain KM.
    :param limiter_time: Nonnegative amplifier lag TM in seconds.
    :param maximum: Positive non-windup output limit MELMAX.
    :param reactive_intercept: Negative reactive-current intercept Q0.
    :param slope: Signed straight-line current slope B.
    :return: Native linear-current minimum-excitation limiter.
    :raises ValueError: Nonfinite settings or invalid dynamics, intercept or limit.
    """
    if min(feedback_time,limiter_gain,maximum) <= 0 or min(feedback_gain,limiter_time) < 0 or reactive_intercept >= 0:
        raise ValueError('Linear-current minimum-excitation settings are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf,'MNLEX3' if name is None else name)
    kf: Var = builder.parameter('KF2',feedback_gain)
    tf: Var = builder.parameter('TF2',feedback_time)
    km: Var = builder.parameter('KM',limiter_gain)
    tm: Var = builder.parameter('TM',limiter_time)
    ceiling: Var = builder.parameter('MELMAX',maximum)
    intercept: Var = builder.parameter('Q0',reactive_intercept)
    gain: Var = builder.parameter('B',slope)
    active: Var = builder.input('IActivePu',Const(.5))
    reactive: Var = builder.input('IReactivePu',Const(0.0))
    voltage: Var = builder.input('EfdPu',Const(1.0))
    signal: Expr = intercept+gain*active-reactive
    feedback: Var = builder.washout('FieldFeedbackPu',voltage,tf,feedback_time,kf/tf,voltage)
    initial: Expr = sym.hard_sat(km*signal,Const(0.0),ceiling)
    output: Var = builder.lag('UelPu',km*(signal-feedback),tm,limiter_time,initial,Const(0.0),ceiling)
    return builder.finish((output,), 'Linear current-capability limiter with field-voltage rate feedback')
