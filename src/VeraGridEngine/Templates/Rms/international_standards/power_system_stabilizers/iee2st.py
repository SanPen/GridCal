# SPDX-License-Identifier: MPL-2.0
"""Dual-measurement oscillation damping with additive transducers and three phase stages."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class Iee2stParameters:
    """Physical transducer gains, shaping times and voltage supervision settings."""

    __slots__ = ('gains', 'transducer_times', 'reset_numerator', 'reset_denominator',
                 'phase_times', 'upper', 'lower', 'voltage_upper', 'voltage_lower')

    def __init__(self, gains: tuple[float, float] = (1.0, -1.0),
                 transducer_times: tuple[float, float] = (.02, .02),
                 reset_numerator: float = 5.0, reset_denominator: float = 5.0,
                 phase_times: tuple[tuple[float, float], tuple[float, float], tuple[float, float]] =
                 ((.2, .05), (.2, .05), (.1, .05)), upper: float = .1, lower: float = -.1,
                 voltage_upper: float = 0.0, voltage_lower: float = 0.0) -> None:
        """Store both independently scaled measurement paths.

        :param gains: Signed gains K1 and K2 before the additive summation.
        :param transducer_times: Nonnegative measurement lags T1 and T2 in seconds.
        :param reset_numerator: Reset numerator T3; zero selects a unity numerator.
        :param reset_denominator: Positive reset denominator T4 in seconds.
        :param phase_times: Three (lead, lag) pairs T5/T6, T7/T8, T9/T10 in seconds.
        :param upper: Supplementary-voltage upper limit.
        :param lower: Supplementary-voltage lower limit.
        :param voltage_upper: Upper supervisory-voltage threshold; zero disables it.
        :param voltage_lower: Lower supervisory-voltage threshold; zero disables it.
        """
        self.gains: tuple[float, float] = gains
        self.transducer_times: tuple[float, float] = transducer_times
        self.reset_numerator: float = reset_numerator
        self.reset_denominator: float = reset_denominator
        self.phase_times: tuple[tuple[float, float], tuple[float, float], tuple[float, float]] = phase_times
        self.upper: float = upper
        self.lower: float = lower
        self.voltage_upper: float = voltage_upper
        self.voltage_lower: float = voltage_lower


def build_iee2st_template(vf: VarFactory, name: str | None = None,
                           parameters: Iee2stParameters | None = None) -> RmsModelTemplate:
    """Build a dual-input supplementary excitation controller with six possible states.

    Two independently selected per-unit measurements pass through signed-gain
    first-order transducers and add. The combined signal passes through
    ``s*T3/(1+s*T4)`` and three successive phase lead-lag stages. T3 equal to
    zero selects ``1/(1+s*T4)`` instead, preserving steady measurement offsets.
    Zero transducer times and zero lead/lag pairs become exact algebraic stages.
    Both input paths remain live; neither is replaced by an operating-point
    constant or combined with a differently based power quantity implicitly.

    Inputs, in order, are measurement one, measurement two and supervisory
    voltage magnitude. The output is per-unit supplementary exciter voltage.
    Output saturation precedes independent lower/upper voltage blocking. Zero
    voltage thresholds disable their respective gates; blocking does not freeze
    any filter state. The connecting device owns signal selection and bases.

    Initialization stores each constant measurement in its transducer. The
    reset state stores their scaled sum. Washout operation initializes all phase
    outputs to zero; unity-numerator operation initializes them to that sum.
    These choices preserve a consistent operating point even for nonzero power
    or voltage inputs and unequal, signed measurement gains.

    :param vf: Shared symbolic factory.
    :param name: Optional native instance label.
    :param parameters: Explicit coefficients or None for construction defaults.
    :return: Native three-input, single-output controller graph.
    :raises ValueError: Nonfinite parameters, invalid time constants, gates or limits.
    """
    settings: Iee2stParameters = Iee2stParameters() if parameters is None else parameters
    if (min(settings.transducer_times) < 0 or settings.reset_numerator < 0 or
            settings.reset_denominator <= 0 or settings.lower >= settings.upper or
            min(settings.voltage_lower, settings.voltage_upper) < 0 or
            (settings.voltage_lower != 0 and settings.voltage_upper != 0 and
             settings.voltage_lower >= settings.voltage_upper)):
        raise ValueError('Dual-input stabilizer settings are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf, 'IEE2ST' if name is None else name)
    gains: tuple[Var, ...] = tuple(builder.parameter('K'+str(index+1), value)
                                  for index, value in enumerate(settings.gains))
    times: tuple[Var, ...] = tuple(builder.parameter('T'+str(index+1), value)
                                  for index, value in enumerate(settings.transducer_times))
    t3: Var = builder.parameter('T3', settings.reset_numerator)
    t4: Var = builder.parameter('T4', settings.reset_denominator)
    upper: Var = builder.parameter('LSMAX', settings.upper)
    lower: Var = builder.parameter('LSMIN', settings.lower)
    voltage_upper: Var = builder.parameter('VCU', settings.voltage_upper)
    voltage_lower: Var = builder.parameter('VCL', settings.voltage_lower)
    signal1: Var = builder.input('Signal1Pu', Const(0.0))
    signal2: Var = builder.input('Signal2Pu', Const(0.0))
    voltage: Var = builder.input('SupervisoryVoltagePu', Const(1.0))
    measured1: Var = builder.lag('Transducer1Pu', gains[0]*signal1, times[0], settings.transducer_times[0], gains[0]*signal1)
    measured2: Var = builder.lag('Transducer2Pu', gains[1]*signal2, times[1], settings.transducer_times[1], gains[1]*signal2)
    combined: Var = builder.algebraic('CombinedPu', measured1+measured2, gains[0]*signal1+gains[1]*signal2)
    initial: Expr
    if settings.reset_numerator == 0:
        phase: Var = builder.lag('ResetPu', combined, t4, settings.reset_denominator, combined)
        initial = combined
    else:
        phase = builder.washout('ResetPu', combined, t4, settings.reset_denominator, t3/t4, combined)
        initial = Const(0.0)
    for index, (lead_value, lag_value) in enumerate(settings.phase_times):
        if min(lead_value, lag_value) < 0:
            raise ValueError('Phase-compensation times must be nonnegative')
        else:
            pass
        lead: Var = builder.parameter('T'+str(5+2*index), lead_value)
        lag: Var = builder.parameter('T'+str(6+2*index), lag_value)
        phase = builder.lead_lag('Phase'+str(index+1)+'Pu', phase, lead, lag, lead_value, lag_value, initial)
    enabled: Expr = Const(1.0)
    if settings.voltage_lower != 0:
        enabled = enabled*sym.heaviside(voltage-voltage_lower)
    else:
        pass
    if settings.voltage_upper != 0:
        enabled = enabled*sym.heaviside(voltage_upper-voltage)
    else:
        pass
    output: Var = builder.algebraic('VsPu', enabled*sym.hard_sat(phase, lower, upper),
                                     enabled*sym.hard_sat(initial, lower, upper))
    return builder.finish((output,), 'Dual-input stabilizer with independent transducers and three phase-compensation stages')
