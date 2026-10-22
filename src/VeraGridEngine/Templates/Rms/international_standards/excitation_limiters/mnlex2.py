# SPDX-License-Identifier: MPL-2.0
"""Circular power-capability minimum-excitation limiter with voltage scaling."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_mnlex2_template(vf: VarFactory, name: str | None = None,
                          feedback_gain: float = .1, feedback_time: float = 1.0,
                          limiter_gain: float = 1.0, limiter_time: float = .1,
                          maximum: float = .2, reactive_center: float = 0.0,
                          radius: float = 1.0) -> RmsModelTemplate:
    """Build a circular P/Q capability limiter with internal output-rate feedback.

    The capability error is ``P^2 + (Q-Q0*V^2)^2 - (Radius*V^2)^2``. Scaling the
    circle center and radius by squared terminal voltage is essential: applying
    a fixed nominal-voltage circle during a voltage dip changes the limiting
    characteristic. Output-rate feedback ``KF2*s/(1+s*TF2)`` is subtracted from
    this error before the KM amplifier. Its non-windup output is bounded between
    zero and MELMAX, so the rate feedback remains inside the limiting loop.

    Inputs ``PPu``, ``QPu`` and ``VmPu`` are machine-base powers and terminal
    voltage magnitude. Output ``UelPu`` is an additive excitation-voltage signal.
    Positive TM gives two states: limiter output and its washout memory. Zero TM
    gives one memory state plus an algebraic bounded feedback equation. At a
    constant operating point the memory equals the initialized limiter output,
    feedback is zero, and the initial output is the bounded static demand.

    :param vf: Symbol factory owning this capability limiter.
    :param name: Optional label, defaulting to MNLEX2.
    :param feedback_gain: Nonnegative output-rate feedback gain KF2.
    :param feedback_time: Positive feedback time TF2 in seconds.
    :param limiter_gain: Positive capability-error gain KM.
    :param limiter_time: Nonnegative limiter lag TM in seconds.
    :param maximum: Positive output upper limit MELMAX.
    :param reactive_center: Circle-center reactive power Q0 at unit voltage.
    :param radius: Positive capability-circle radius at unit voltage.
    :return: Native voltage-scaled circular minimum-excitation limiter.
    :raises ValueError: Nonfinite parameters or invalid dynamics, radius or limits.
    """
    if min(feedback_time,limiter_gain,maximum,radius) <= 0 or min(feedback_gain,limiter_time) < 0:
        raise ValueError('Circular minimum-excitation settings are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf,'MNLEX2' if name is None else name)
    kf: Var = builder.parameter('KF2',feedback_gain)
    tf: Var = builder.parameter('TF2',feedback_time)
    km: Var = builder.parameter('KM',limiter_gain)
    tm: Var = builder.parameter('TM',limiter_time)
    ceiling: Var = builder.parameter('MELMAX',maximum)
    center: Var = builder.parameter('Q0',reactive_center)
    width: Var = builder.parameter('Radius',radius)
    power: Var = builder.input('PPu',Const(.5))
    reactive: Var = builder.input('QPu',Const(0.0))
    voltage: Var = builder.input('VmPu',Const(1.0))
    signal: Expr = power*power+(reactive-center*voltage*voltage)**2-(width*voltage*voltage)**2
    initial: Expr = sym.hard_sat(km*signal,Const(0.0),ceiling)
    output: Var = vf.add_var(name=f'UelPu_{builder.name}')
    # Predeclare the output so the feedback memory reads the actual limited state.
    feedback: Var = builder.washout('OutputFeedbackPu',output,tf,feedback_time,kf/tf,initial)
    builder.lag('UelPu',km*(signal-feedback),tm,limiter_time,initial,Const(0.0),ceiling,output)
    return builder.finish((output,), 'Voltage-scaled circular capability limiter with internal rate feedback')
