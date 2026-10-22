# SPDX-License-Identifier: MPL-2.0
"""Single-input oscillation damping with polynomial filtering and voltage supervision."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class IeeestParameters:
    """Physical coefficients of the measurement, phase and reset transfer functions."""

    __slots__ = ('filter_coefficients', 'lead1', 'lag1', 'lead2', 'lag2',
                 'reset_numerator', 'reset_denominator', 'gain', 'upper', 'lower',
                 'voltage_upper', 'voltage_lower')

    def __init__(self, filter_coefficients: tuple[float, float, float, float, float, float] =
                 (.1, .01, .1, .01, 0.0, 0.0), lead1: float = .2, lag1: float = .05,
                 lead2: float = .2, lag2: float = .05, reset_numerator: float = 5.0,
                 reset_denominator: float = 5.0, gain: float = 1.0,
                 upper: float = .1, lower: float = -.1,
                 voltage_upper: float = 0.0, voltage_lower: float = 0.0) -> None:
        """Store coefficients without choosing a measured quantity.

        :param filter_coefficients: A1 through A6 of the polynomial input filter.
        :param lead1: First phase numerator time in seconds.
        :param lag1: First phase denominator time in seconds.
        :param lead2: Second phase numerator time in seconds.
        :param lag2: Second phase denominator time in seconds.
        :param reset_numerator: Reset numerator time; zero selects a unity numerator.
        :param reset_denominator: Positive reset denominator time in seconds.
        :param gain: Supplementary-voltage gain.
        :param upper: Upper output limit in per unit.
        :param lower: Lower output limit in per unit.
        :param voltage_upper: Upper supervisory-voltage gate; zero disables this gate.
        :param voltage_lower: Lower supervisory-voltage gate; zero disables this gate.
        """
        self.filter_coefficients: tuple[float, float, float, float, float, float] = filter_coefficients
        self.lead1: float = lead1
        self.lag1: float = lag1
        self.lead2: float = lead2
        self.lag2: float = lag2
        self.reset_numerator: float = reset_numerator
        self.reset_denominator: float = reset_denominator
        self.gain: float = gain
        self.upper: float = upper
        self.lower: float = lower
        self.voltage_upper: float = voltage_upper
        self.voltage_lower: float = voltage_lower


def polynomial_measurement_filter(builder: ControlRealization, signal: Var,
                                  coefficients: tuple[float, float, float, float, float, float],
                                  prefix: str = '') -> Var:
    """Realize a proper fourth-order rational measurement filter exactly.

    :param builder: Owning controller graph and symbol factory.
    :param signal: Measured operating signal and equilibrium value.
    :param coefficients: A1..A6 for (1+A5*s+A6*s²)/((1+A1*s+A2*s²)*(1+A3*s+A4*s²)).
    :param prefix: Optional physical-stage namespace for multiple filters in one controller.
    :return: Filter output, with zero coefficients removing states structurally.
    :raises ValueError: Negative denominator coefficients or an improper transfer.
    """
    a1: float = coefficients[0]
    a2: float = coefficients[1]
    a3: float = coefficients[2]
    a4: float = coefficients[3]
    a5: float = coefficients[4]
    a6: float = coefficients[5]
    if min(a1, a2, a3, a4) < 0:
        raise ValueError('Measurement-filter denominator coefficients must be nonnegative')
    else:
        pass
    symbols: tuple[Var, ...] = tuple(builder.parameter(prefix+'A'+str(index+1), value)
                                    for index, value in enumerate(coefficients))
    p1: Var = symbols[0]
    p2: Var = symbols[1]
    p3: Var = symbols[2]
    p4: Var = symbols[3]
    p5: Var = symbols[4]
    p6: Var = symbols[5]
    denominator: tuple[Expr, ...] = (Const(1.0), p1+p3, p2+p4+p1*p3, p1*p4+p2*p3, p2*p4)
    numeric: tuple[float, ...] = (1.0, a1+a3, a2+a4+a1*a3, a1*a4+a2*a3, a2*a4)
    order: int = max(index for index, value in enumerate(numeric) if value != 0)
    numerator_order: int = 2 if a6 != 0 else (1 if a5 != 0 else 0)
    if numerator_order > order:
        raise ValueError('Measurement filter must be proper; no numerical differentiator is substituted')
    elif order == 0:
        return builder.algebraic(prefix+'FilteredInputPu', signal, signal)
    else:
        # A derivative chain avoids factoring quadratic roots and works for
        # repeated poles, complex poles and exact first-order reductions.
        states: tuple[Var, ...] = tuple(builder.vf.add_var(prefix+'FilterState'+str(index)+'_'+builder.name)
                                        for index in range(order))
        forcing: Expr = signal-states[0]
        for index in range(1, order):
            forcing = forcing-denominator[index]*states[index]
        last_derivative: Expr = forcing/denominator[order]
        for index, state in enumerate(states):
            derivative: Expr = states[index+1] if index+1 < order else last_derivative
            builder.differential(state, derivative, signal if index == 0 else Const(0.0))
        output: Expr = states[0]
        if a5 != 0:
            output = output+p5*(states[1] if order > 1 else last_derivative)
        else:
            pass
        if a6 != 0:
            output = output+p6*(states[2] if order > 2 else last_derivative)
        else:
            pass
        return builder.algebraic(prefix+'FilteredInputPu', output, signal)


def build_ieeest_template(vf: VarFactory, name: str | None = None,
                           parameters: IeeestParameters | None = None) -> RmsModelTemplate:
    """Build a single-input supplementary excitation controller.

    The measured signal passes through a rational filter with two quadratic
    denominator factors and a quadratic numerator, then two phase-compensation
    stages. The final reset transfer is ``Ks*s*T5/(1+s*T6)``. A zero T5 instead
    selects ``Ks/(1+s*T6)``, retaining the steady component intentionally.
    Zero polynomial coefficients and zero phase lag/lead pairs remove states
    exactly; no small replacement time constant is introduced.

    Input ports are the selected per-unit signal and the supervisory-voltage
    magnitude. Signal selection, including any remote measurement, belongs to
    the connecting assembly. The output is supplementary exciter voltage in
    per unit. Hard output saturation precedes voltage supervision: an enabled
    lower or upper supervisory-voltage threshold blocks the output outside its
    permitted range, without freezing the filter memories. A zero threshold
    disables that side independently.

    Initialization stores the constant measured input in the filter and phase
    memories. Reset operation starts at zero output; unity-numerator operation
    starts at its limited steady gain. There are at most seven differential
    states, and the internal filter states remain continuous during blocking.

    :param vf: Shared symbolic factory.
    :param name: Optional native instance label.
    :param parameters: Coefficients and limits; None selects construction defaults.
    :return: Native controller with two open input ports and one voltage output.
    :raises ValueError: Nonfinite coefficients, improper filter, invalid times or limits.
    """
    settings: IeeestParameters = IeeestParameters() if parameters is None else parameters
    if (settings.reset_denominator <= 0 or settings.reset_numerator < 0 or
            min(settings.lead1, settings.lag1, settings.lead2, settings.lag2) < 0 or
            settings.lower >= settings.upper or
            min(settings.voltage_lower, settings.voltage_upper) < 0 or
            (settings.voltage_lower != 0 and settings.voltage_upper != 0 and
             settings.voltage_lower >= settings.voltage_upper)):
        raise ValueError('Stabilizer times, voltage thresholds or output limits are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf, 'IEEEST' if name is None else name)
    t1: Var = builder.parameter('T1', settings.lead1)
    t2: Var = builder.parameter('T2', settings.lag1)
    t3: Var = builder.parameter('T3', settings.lead2)
    t4: Var = builder.parameter('T4', settings.lag2)
    t5: Var = builder.parameter('T5', settings.reset_numerator)
    t6: Var = builder.parameter('T6', settings.reset_denominator)
    gain: Var = builder.parameter('KS', settings.gain)
    upper: Var = builder.parameter('LSMAX', settings.upper)
    lower: Var = builder.parameter('LSMIN', settings.lower)
    voltage_upper: Var = builder.parameter('VCU', settings.voltage_upper)
    voltage_lower: Var = builder.parameter('VCL', settings.voltage_lower)
    signal: Var = builder.input('SignalPu', Const(0.0))
    voltage: Var = builder.input('SupervisoryVoltagePu', Const(1.0))
    measured: Var = polynomial_measurement_filter(builder, signal, settings.filter_coefficients)
    phase1: Var = builder.lead_lag('Phase1Pu', measured, t1, t2, settings.lead1, settings.lag1, signal)
    phase2: Var = builder.lead_lag('Phase2Pu', phase1, t3, t4, settings.lead2, settings.lag2, signal)
    initial: Expr
    if settings.reset_numerator == 0:
        reset: Var = builder.lag('ResetPu', gain*phase2, t6, settings.reset_denominator, gain*signal)
        initial = gain*signal
    else:
        reset = builder.washout('ResetPu', phase2, t6, settings.reset_denominator, gain*t5/t6, signal)
        initial = Const(0.0)
    enabled: Expr = Const(1.0)
    if settings.voltage_lower != 0:
        enabled = enabled*sym.heaviside(voltage-voltage_lower)
    else:
        pass
    if settings.voltage_upper != 0:
        enabled = enabled*sym.heaviside(voltage_upper-voltage)
    else:
        pass
    output: Var = builder.algebraic('VsPu', enabled*sym.hard_sat(reset, lower, upper),
                                     enabled*sym.hard_sat(initial, lower, upper))
    return builder.finish((output,), 'Single-input polynomial-filter stabilizer with voltage supervision')
