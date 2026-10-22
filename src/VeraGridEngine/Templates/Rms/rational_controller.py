# SPDX-License-Identifier: MPL-2.0
"""First-order rational compensation with explicit tracking or external output limits."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class RationalStageLimiting(Enum):
    """Distinguish bounded-memory recovery from clipping an unrestricted transfer."""
    OUTPUT_TRACKING = 1
    OUTPUT_ONLY = 2


class RationalStageParameters:
    """Coefficients of K*(A+s*L)/(B+s*T), with independent output capability."""
    __slots__ = ('gain','numerator','denominator','lead','lag','maximum','minimum')

    def __init__(self, gain: float = 1., numerator: float = 1., denominator: float = 1.,
                 lead: float = .1, lag: float = .2, maximum: float = 1., minimum: float = -1.) -> None:
        """Store one rational stage's physical coefficient and limit settings.

        :param gain: Signed finite multiplier K.
        :param numerator: Nonnegative constant numerator coefficient A.
        :param denominator: Nonnegative constant denominator coefficient B.
        :param lead: Nonnegative numerator time coefficient L, in seconds.
        :param lag: Nonnegative denominator time coefficient T, in seconds.
        :param maximum: Upper output capability; nonnegative in this realization.
        :param minimum: Lower output capability; nonpositive in this realization.
        """
        self.gain: float = gain
        self.numerator: float = numerator
        self.denominator: float = denominator
        self.lead: float = lead
        self.lag: float = lag
        self.maximum: float = maximum
        self.minimum: float = minimum


def build_rational_stage(c: ControlRealization, stage_index: int, signal: Expr,
                          input_initial: Expr, input_is_zero: bool,
                          p: RationalStageParameters,
                          limiting: RationalStageLimiting,
                          integral_initial: Expr | None = None) -> tuple[Var,Expr,bool]:
    """Assemble a proper rational filter and propagate its steady initialization.

    Positive A/B normalize to an ordinary lead-lag with gain K*A/B and times
    L/A, T/B. Output tracking uses the bounded lead-lag realization. A=0 is a
    washout: ``y=clip(K*L/T*u+z)``, ``dz/dt=-B*y/T`` for bounded tracking;
    an unrestricted washout instead feeds back its unbounded internal output.
    B=0 gives integral action and requires a structurally zero steady input.
    With L>0, tracking PI recovery is ``dz/dt=A*(y-z)/L``; with L=0, it is
    a directionally stopped pure integrator. External clipping never invents
    an integral stop. Exact constant/zero transfers allocate no artificial pole.

    :param c: Native realization owning all stage variables and equations.
    :param stage_index: First coefficient index; the paired index is one larger.
    :param signal: Live stage input.
    :param input_initial: Actual steady input expression.
    :param input_is_zero: Whether the preceding structure guarantees zero DC input.
    :param p: Physical rational coefficients and capability.
    :param limiting: Explicit tracking or external-only output limiting.
    :param integral_initial: Optional balanced integral output, otherwise zero.
    :return: Output, its steady initialization, and structural zero-DC status.
    :raises ValueError: Invalid coefficients, improper transfer or unbalanced integrator input.
    """
    values: tuple[float,...] = (p.gain,p.numerator,p.denominator,p.lead,p.lag,p.maximum,p.minimum)
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Rational compensation coefficients must be finite')
    elif min(p.numerator,p.denominator,p.lead,p.lag) < 0 or p.maximum <= p.minimum or p.maximum < 0 or p.minimum > 0:
        raise ValueError('Rational compensation requires nonnegative coefficients and limits straddling zero')
    elif p.denominator == 0 and p.lag == 0:
        raise ValueError('Rational compensation denominator cannot vanish identically')
    elif p.lag == 0 and p.lead != 0:
        raise ValueError('Rational compensation cannot retain a numerator derivative without its denominator pole')
    elif not isinstance(limiting,RationalStageLimiting):
        raise ValueError('Rational compensation requires an explicit limiting realization')
    else:
        pass
    label: str = 'Stage'+str(stage_index)
    k: Var = c.parameter('K'+str(stage_index),p.gain)
    a: Var = c.parameter('A'+str(stage_index),p.numerator)
    b: Var = c.parameter('A'+str(stage_index+1),p.denominator)
    lead: Var = c.parameter('T'+str(stage_index),p.lead)
    lag: Var = c.parameter('T'+str(stage_index+1),p.lag)
    maximum: Var = c.parameter('MAX'+str(stage_index),p.maximum)
    minimum: Var = c.parameter('MIN'+str(stage_index),p.minimum)
    if (p.gain == 0 and not (p.denominator == 0 and p.numerator > 0 and integral_initial is not None)) or (p.numerator == 0 and p.lead == 0):
        zero: Var = c.algebraic(label+'OutputPu',Const(0.),Const(0.))
        return zero,Const(0.),True
    elif p.denominator > 0 and p.numerator > 0:
        gain: Expr = k*a/b
        initial_raw: Expr = gain*input_initial
        initial_output: Expr = sym.hard_sat(initial_raw,minimum,maximum)
        if limiting == RationalStageLimiting.OUTPUT_TRACKING:
            output: Var = c.bounded_lead_lag(label+'OutputPu',gain*signal,lead/a,lag/b,
                p.lead/p.numerator,p.lag/p.denominator,initial_output,minimum,maximum)
        else:
            raw: Var = c.lead_lag(label+'UnboundedPu',gain*signal,lead/a,lag/b,
                p.lead/p.numerator,p.lag/p.denominator,initial_raw)
            output = c.algebraic(label+'OutputPu',sym.hard_sat(raw,minimum,maximum),initial_output)
        return output,initial_output,input_is_zero
    elif p.denominator == 0 and p.numerator == 0:
        direct: Expr = k*lead/lag*signal
        initial_direct: Expr = sym.hard_sat(k*lead/lag*input_initial,minimum,maximum)
        output = c.algebraic(label+'OutputPu',sym.hard_sat(direct,minimum,maximum),initial_direct)
        return output,initial_direct,input_is_zero
    elif p.denominator == 0 and not input_is_zero:
        raise ValueError('An integrating rational stage needs a guaranteed zero steady input, such as preceding washout')
    elif p.denominator == 0 and p.lead == 0:
        state: Var = c.vf.add_var(label+'IntegralPu_'+c.name)
        derivative: Expr = k*a/lag*signal
        seed: Expr = Const(0.) if integral_initial is None else integral_initial
        if limiting == RationalStageLimiting.OUTPUT_TRACKING:
            c.differential(state,derivative,seed,minimum,maximum)
        else:
            c.differential(state,derivative,seed)
        initial_limited: Expr = sym.hard_sat(seed,minimum,maximum)
        output = c.algebraic(label+'OutputPu',sym.hard_sat(state,minimum,maximum),initial_limited)
        return output,initial_limited,integral_initial is None
    else:
        # This coordinate remains finite for washout A=0 and integral denominator B=0.
        feedthrough: Expr = k*lead/lag
        initial_unbounded: Expr = (integral_initial if p.denominator == 0 and integral_initial is not None else Const(0.))
        memory: Var = c.vf.add_var(label+'MemoryPu_'+c.name)
        unbounded: Expr = feedthrough*signal+memory
        initial_limited = sym.hard_sat(initial_unbounded,minimum,maximum)
        output = c.algebraic(label+'OutputPu',sym.hard_sat(unbounded,minimum,maximum),initial_limited)
        if limiting == RationalStageLimiting.OUTPUT_TRACKING:
            derivative = (a/lead-b/lag)*output-a/lead*memory
        else:
            derivative = (k*a*signal-b*unbounded)/lag
        c.differential(memory,derivative,initial_unbounded-feedthrough*input_initial)
        return output,initial_limited,p.denominator > 0 or integral_initial is None
