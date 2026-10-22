# SPDX-License-Identifier: MPL-2.0
"""Small explicit state realizations shared by native continuous controllers."""
from __future__ import annotations

import math

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _anti_windup_state_derivative
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DeviceType


class ControlRealization:
    """Assemble named controller stages with explicit equilibrium initialization.

    Zero-time stages are algebraic constraints. Positive-time stages own exactly
    one state and derivative, so disabling a lag never introduces an artificial
    small time constant. Inputs remain open ports owned by the connecting host.
    """

    __slots__ = ('vf', 'block', 'name')

    def __init__(self, vf: VarFactory, name: str) -> None:
        """Create a fresh controller graph.

        :param vf: Symbol factory owning all variables and derivatives.
        :param name: Unique instance label appended to public symbol names.
        """
        self.vf: VarFactory = vf
        self.name: str = name
        self.block: Block = Block(name=name)

    def parameter(self, name: str, value: float) -> Var:
        """Declare a finite runtime parameter with its construction default.

        :param name: Parameter identifier local to the instance.
        :param value: Finite scalar default in the controller's declared units.
        :return: Symbol consumed directly by the equations.
        :raises ValueError: Nonfinite parameter value.
        """
        if not math.isfinite(value):
            raise ValueError('Controller parameter must be finite: ' + name)
        else:
            parameter: Var = self.vf.add_var(name=f'{name}_{self.name}')
            self.block.event_dict[parameter] = self.vf.add_const(value=value)
            return parameter

    def input(self, name: str, initial: Expr | Const) -> Var:
        """Expose a host-owned input and a stand-alone initialization guess.

        :param name: Input signal identifier.
        :param initial: Equilibrium seed, replaced by the host on connection.
        :return: Open input port; no equation fixes it during simulation.
        """
        port: Var = self.vf.add_var(name=f'{name}_{self.name}')
        self.block.in_vars.append(port)
        self.block.init_eqs[port] = initial
        return port

    def algebraic(self, name: str, expression: Expr, initial: Expr | Const) -> Var:
        """Declare an explicitly calculated signal and its equilibrium seed.

        :param name: Signal identifier.
        :param expression: Runtime signal expression.
        :param initial: Operating-point expression.
        :return: Signal governed by one algebraic equation.
        """
        signal: Var = self.vf.add_var(name=f'{name}_{self.name}')
        self.block.algebraic_vars.append(signal)
        self.block.algebraic_eqs.append(signal - expression)
        self.block.init_eqs[signal] = initial
        return signal

    def lag(self, name: str, signal: Expr, time: Expr, time_value: float,
            initial: Expr | Const, lower: Expr | None = None,
            upper: Expr | None = None, output: Var | None = None) -> Var:
        """Realize a lag with optional non-windup output limits.

        :param name: Stage output identifier.
        :param signal: Unconstrained demanded output.
        :param time: Time-constant symbol, measured in seconds.
        :param time_value: Construction value selecting dynamic/algebraic structure.
        :param initial: Equilibrium output, already respecting configured bounds.
        :param lower: Optional lower output bound, supplied together with upper.
        :param upper: Optional upper output bound.
        :param output: Optional predeclared output closing a controller feedback loop.
        :return: Dynamic state or exact algebraic output for a zero-time stage.
        :raises ValueError: Negative/nonfinite time or incomplete bounds.
        """
        if not math.isfinite(time_value) or time_value < 0:
            raise ValueError('Lag time must be finite and nonnegative: ' + name)
        elif (lower is None) != (upper is None):
            raise ValueError('Both lag output bounds must be supplied together')
        elif time_value == 0:
            expression: Expr = sym.hard_sat(signal, lower, upper) if lower is not None and upper is not None else signal
            if output is None:
                return self.algebraic(name, expression, initial)
            else:
                self.block.algebraic_vars.append(output)
                self.block.algebraic_eqs.append(output-expression)
                self.block.init_eqs[output] = initial
                return output
        else:
            state: Var = self.vf.add_var(name=f'{name}_{self.name}') if output is None else output
            derivative: Expr = (signal - state) / time
            return self.differential(state,derivative,initial,lower,upper)

    def differential(self, state: Var, derivative: Expr, initial: Expr | Const,
                      lower: Expr | None = None, upper: Expr | None = None) -> Var:
        """Own one explicit state equation with optional directional stop limits.

        :param state: Predeclared state symbol, permitting feedback-loop references.
        :param derivative: Unconstrained physical time derivative.
        :param initial: Operating-point state expression.
        :param lower: Optional lower state bound, paired with upper.
        :param upper: Optional upper state bound.
        :return: State with one owned derivative and initialization equation.
        :raises ValueError: Only one state bound was supplied.
        """
        if (lower is None) != (upper is None):
            raise ValueError('Both differential-state bounds must be supplied together')
        elif lower is not None and upper is not None:
            # Suppress outward motion at a stop while allowing immediate recovery.
            derivative = _anti_windup_state_derivative(state,derivative,lower,upper)
        else:
            pass
        self.block.state_vars.append(state)
        self.block.diff_vars.append(self.vf.add_diff_var(name=f'd_{state.name}',base_var=state))
        self.block.state_eqs.append(derivative)
        self.block.init_eqs[state] = initial
        return state

    def lead_lag(self, name: str, signal: Expr, lead: Expr, lag: Expr,
                 lead_value: float, lag_value: float, initial: Expr | Const) -> Var:
        """Realize ``(1+s*lead)/(1+s*lag)`` without differentiating the input.

        :param name: Stage output identifier.
        :param signal: Input signal.
        :param lead: Numerator time-constant symbol.
        :param lag: Denominator time-constant symbol.
        :param lead_value: Construction value used to validate the zero-lag case.
        :param lag_value: Construction value selecting the state structure.
        :param initial: Constant-input equilibrium output.
        :return: Lead-lag output with a low-pass internal state when needed.
        :raises ValueError: Nonfinite lead, negative lag or improper zero-lag transfer.
        """
        if not math.isfinite(lead_value):
            raise ValueError('Lead time must be finite: ' + name)
        elif lag_value == 0 and lead_value != 0:
            raise ValueError('Zero lag requires zero lead: ' + name)
        elif lag_value == 0:
            return self.algebraic(name, signal, initial)
        else:
            state: Var = self.lag(name + 'State', signal, lag, lag_value, initial)
            return self.algebraic(name, state + lead / lag * (signal - state), initial)

    def bounded_lead_lag(self, name: str, signal: Expr, lead: Expr, lag: Expr,
                         lead_value: float, lag_value: float, initial: Expr | Const,
                         lower: Expr, upper: Expr) -> Var:
        """Realize a lead-lag whose memory tracks its bounded output.

        For positive numerator time, ``y=clip(d*u+(1-d)*x)`` and
        ``dx/dt=(y-x)/Tlead``, with ``d=Tlead/Tlag``. Removing the
        limits recovers ``(1+s*Tlead)/(1+s*Tlag)``. During clipping the
        memory follows the bounded output; simply clipping an ordinary
        lead-lag output would retain a different windup trajectory.
        Zero numerator time becomes a directionally bounded first-order lag.
        Both zero times give an exact static limiter.

        :param name: Stage output identifier.
        :param signal: Unit-DC-gain input signal.
        :param lead: Nonnegative numerator time in seconds.
        :param lag: Nonnegative denominator time in seconds.
        :param lead_value: Construction value selecting the tracking realization.
        :param lag_value: Construction value selecting the algebraic reduction.
        :param initial: Feasible constant-input equilibrium output and memory.
        :param lower: Lower output capability.
        :param upper: Upper output capability.
        :return: Bounded lead-lag output with explicit tracking memory when needed.
        :raises ValueError: Invalid times or an improper zero-denominator stage.
        """
        if not math.isfinite(lead_value) or not math.isfinite(lag_value) or min(lead_value,lag_value) < 0:
            raise ValueError('Bounded lead-lag times must be finite and nonnegative: '+name)
        elif lag_value == 0 and lead_value != 0:
            raise ValueError('Zero bounded lead-lag denominator requires zero numerator time: '+name)
        elif lead_value == 0:
            return self.lag(name,signal,lag,lag_value,initial,lower,upper)
        else:
            memory: Var = self.vf.add_var(name=name+'Memory_'+self.name)
            ratio: Expr = lead/lag
            output: Var = self.algebraic(name,sym.hard_sat(ratio*signal+(Const(1.)-ratio)*memory,lower,upper),initial)
            self.differential(memory,(output-memory)/lead,initial)
            return output

    def washout(self, name: str, signal: Expr, time: Expr, time_value: float,
                high_frequency_gain: Expr, initial_input: Expr | Const) -> Var:
        """Reject steady input using a strictly proper low-pass memory state.

        :param name: Output signal identifier.
        :param signal: Measured input signal.
        :param time: Positive washout time-constant symbol in seconds.
        :param time_value: Positive construction time constant.
        :param high_frequency_gain: Gain of the transfer ``s*T/(1+s*T)``.
        :param initial_input: Equilibrium input stored in the memory state.
        :return: Output with zero equilibrium value and no numerical differentiation.
        :raises ValueError: Nonpositive or nonfinite washout time.
        """
        if not math.isfinite(time_value) or time_value <= 0:
            raise ValueError('Washout time must be finite and positive: ' + name)
        else:
            memory: Var = self.lag(name + 'Memory', signal, time, time_value, initial_input)
            return self.algebraic(name, high_frequency_gain * (signal - memory), Const(0.0))

    def speed_deviation(self, speed: Expr, lower: float = 0.0, upper: float = 0.0) -> Var:
        """Measure shaft-speed deviation through an optional continuous asymmetric deadband.

        :param speed: Absolute per-unit shaft speed, nominally one.
        :param lower: Nonpositive underspeed pickup threshold.
        :param upper: Nonnegative overspeed pickup threshold.
        :return: Excess deviation outside each threshold, zero inside the band.
        :raises ValueError: Nonfinite thresholds or a band not containing nominal speed.
        """
        if not math.isfinite(lower) or not math.isfinite(upper) or not lower <= 0 <= upper:
            raise ValueError('Speed deadband requires finite thresholds containing zero')
        else:
            low: Var = self.parameter('DBL', lower)
            high: Var = self.parameter('DBH', upper)
            deviation: Expr = speed-Const(1.)
            if lower == 0 and upper == 0:
                return self.algebraic('ControlledSpeedDeviationPu', deviation, Const(0.))
            else:
                return self.algebraic('ControlledSpeedDeviationPu',
                    sym.max(deviation-high,Const(0.))+sym.min(deviation-low,Const(0.)),Const(0.))

    def finish(self, outputs: tuple[Var, ...], description: str) -> RmsModelTemplate:
        """Close the public output surface without fixing the open input ports.

        :param outputs: Ordered externally connected output signals.
        :param description: Human-readable physical description.
        :return: Native controller template with a generic attachment role.
        """
        self.block.out_vars = list(outputs)
        template: RmsModelTemplate = RmsModelTemplate(name=self.name)
        template.tpe = DeviceType.NoDevice
        template.block = self.block
        template.comment = description
        return template
