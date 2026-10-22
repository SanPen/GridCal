# SPDX-License-Identifier: MPL-2.0
"""Dual-input oscillation damping with an explicitly ordered ramp-tracking filter."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class RampStabilizerKind(Enum):
    """Two-phase stabilization or input-limited three-phase stabilization."""

    TWO_PHASE = 1
    LIMITED_THREE_PHASE = 2
    LIMITED_FOUR_PHASE = 3


class StabilizerInterface(Enum):
    """Host-owned selected measurements or the established shaft-speed/power interface."""

    SELECTED_SIGNALS = 1
    SHAFT_SPEED_POWER = 2


class RampStabilizerParameters:
    """Physical washout, transducer, ramp-tracking, phase and limiter settings."""

    __slots__ = ('washout_times', 'transducer_times', 'ks1', 'ks2', 'ks3', 't8', 't9',
                 'ramp_m', 'ramp_n', 'phase_times', 'upper', 'lower', 'input_limits', 'fourth_phase')

    def __init__(self, washout_times: tuple[float, float, float, float] = (10.0, 10.0, 10.0, 10.0),
                 transducer_times: tuple[float, float] = (.02, .02), ks1: float = 10.0,
                 ks2: float = 1.0, ks3: float = 1.0, t8: float = .1, t9: float = .2,
                 ramp_m: int = 1, ramp_n: int = 1,
                 phase_times: tuple[tuple[float, float], tuple[float, float], tuple[float, float]] =
                 ((.2, .05), (.2, .05), (.1, .05)), upper: float = .1, lower: float = -.1,
                 input_limits: tuple[tuple[float, float], tuple[float, float]] = ((-10.0, 10.0), (-10.0, 10.0)),
                 fourth_phase: tuple[float,float] = (.1,.05)) -> None:
        """Store one dual-input damping controller's construction settings.

        :param washout_times: First/second washout times on each path, in seconds; zero second times bypass.
        :param transducer_times: Nonnegative first/second measurement lag times, in seconds.
        :param ks1: Supplementary output gain.
        :param ks2: Gain of the second measurement before the mixing/difference paths.
        :param ks3: Second-path gain entering the ramp-tracking summation.
        :param t8: Nonnegative ramp numerator time, in seconds.
        :param t9: Positive ramp denominator time, in seconds.
        :param ramp_m: Nonnegative denominator order per repeated ramp stage.
        :param ramp_n: Nonnegative number of repeated stages; M*N must not exceed eight.
        :param phase_times: Three lead/lag pairs, in seconds; only the first two apply to two-phase control.
        :param upper: Supplementary-voltage upper bound.
        :param lower: Supplementary-voltage lower bound.
        :param input_limits: Lower/upper bounds on both raw selected measurements in the limited variant.
        :param fourth_phase: Additional lead/lag pair for the four-phase structure.
        """
        self.washout_times: tuple[float, float, float, float] = washout_times
        self.transducer_times: tuple[float, float] = transducer_times
        self.ks1: float = ks1
        self.ks2: float = ks2
        self.ks3: float = ks3
        self.t8: float = t8
        self.t9: float = t9
        self.ramp_m: int = ramp_m
        self.ramp_n: int = ramp_n
        self.phase_times: tuple[tuple[float, float], tuple[float, float], tuple[float, float]] = phase_times
        self.upper: float = upper
        self.lower: float = lower
        self.input_limits: tuple[tuple[float, float], tuple[float, float]] = input_limits
        self.fourth_phase: tuple[float,float] = fourth_phase


def build_ramp_tracking_stabilizer(vf: VarFactory, name: str, kind: RampStabilizerKind,
                                    parameters: RampStabilizerParameters | None = None,
                                    interface: StabilizerInterface = StabilizerInterface.SELECTED_SIGNALS) -> RmsModelTemplate:
    """Realize both measured paths and the requested ramp-filter order explicitly.

    Each measurement passes through one required washout, an optional second
    washout and an optional transducer. The second path includes KS2. If their
    outputs are A and B, the signal before output gain is R*(A+KS3*B)-B, where
    R=[(1+s*T8)/(1+s*T9)^M]^N. Each repeated section has one numerator lead
    and M denominator memories; no unrequested padded states are constructed.
    M=0 forces a bypass, as does N=0. Output gain precedes two, three or four phase
    compensators and supplementary-voltage clipping. The input-limited variants
    also clip each raw selected measurement before its washouts.

    Zero second-washout times, zero transducer times and zero phase pairs are
    exact bypasses. First washout times and the ramp denominator time are
    positive. Each washout memory initializes from its steady input; subsequent
    memories and the output initialize to zero, including for nonzero power or
    voltage measurements. Limits do not freeze the washout/filter memories.

    Selected-signal inputs are two host-scaled per-unit measurements. The shaft
    interface exposes absolute speed, speed reference and per-unit electrical
    power; its first internal measurement is speed minus reference. Output is
    per-unit supplementary excitation voltage. Time constants are seconds,
    gains are dimensionless, and the host owns signal selection and power bases.

    :param vf: Shared native symbolic factory.
    :param name: Unique instance label.
    :param kind: Explicit phase-count and input-limiter structure.
    :param parameters: Physical coefficients or None for construction defaults.
    :param interface: Selected measurements or the established shaft/power ports.
    :return: Native initialized dual-input stabilizer with one voltage output.
    :raises ValueError: Invalid time constants, filter order, limits or nonfinite coefficients.
    """
    p: RampStabilizerParameters = RampStabilizerParameters() if parameters is None else parameters
    groups: tuple[tuple[float, ...], ...] = (p.washout_times, p.transducer_times,
        (p.ks1, p.ks2, p.ks3, p.t8, p.t9, p.upper, p.lower), p.phase_times[0],
        p.phase_times[1], p.phase_times[2], p.input_limits[0], p.input_limits[1], p.fourth_phase)
    if not all(math.isfinite(value) for group in groups for value in group):
        raise ValueError('Ramp-tracking stabilizer coefficients must be finite')
    elif (not isinstance(p.ramp_m, int) or not isinstance(p.ramp_n, int) or
          min(p.ramp_m, p.ramp_n) < 0 or p.ramp_m*p.ramp_n > 8):
        raise ValueError('Ramp-tracking orders must be nonnegative integers with M*N <= 8')
    elif min(p.washout_times[0], p.washout_times[2], p.t9) <= 0 or min(p.washout_times[1], p.washout_times[3], p.t8) < 0:
        raise ValueError('First washout/ramp denominator times must be positive; optional times must be nonnegative')
    elif min(p.transducer_times) < 0 or p.lower >= p.upper:
        raise ValueError('Transducer times or output limits are invalid')
    elif kind != RampStabilizerKind.TWO_PHASE and any(low >= high for low, high in p.input_limits):
        raise ValueError('Each stabilizer input upper bound must exceed its lower bound')
    else:
        pass
    control: ControlRealization = ControlRealization(vf, name)
    washouts: tuple[Var, ...] = tuple(control.parameter('TW'+str(index+1), value) for index, value in enumerate(p.washout_times))
    transducers: tuple[Var, ...] = tuple(control.parameter('T'+str(index+6), value) for index, value in enumerate(p.transducer_times))
    ks1: Var = control.parameter('KS1', p.ks1)
    ks2: Var = control.parameter('KS2', p.ks2)
    ks3: Var = control.parameter('KS3', p.ks3)
    t8: Var = control.parameter('T8', p.t8)
    t9: Var = control.parameter('T9', p.t9)
    maximum: Var = control.parameter('VSTMAX', p.upper)
    minimum: Var = control.parameter('VSTMIN', p.lower)
    signal1: Var
    signal2: Var
    if interface == StabilizerInterface.SHAFT_SPEED_POWER:
        omega: Var = control.input('OmegaPu', Const(1.0))
        reference: Var = control.input('OmegaRefPu', Const(1.0))
        signal2 = control.input('ElectricalPowerPu', Const(0.0))
        signal1 = control.algebraic('Signal1Pu', omega-reference, Const(0.0))
    else:
        signal1 = control.input('Signal1Pu', Const(0.0))
        signal2 = control.input('Signal2Pu', Const(0.0))
    paths: list[Var] = list()
    index: int
    signal: Var
    for index, signal in enumerate((signal1, signal2)):
        measured: Expr = signal
        if kind != RampStabilizerKind.TWO_PHASE:
            low: Var = control.parameter('VS'+str(index+1)+'MIN', p.input_limits[index][0])
            high: Var = control.parameter('VS'+str(index+1)+'MAX', p.input_limits[index][1])
            measured = control.algebraic('ClippedSignal'+str(index+1)+'Pu', sym.hard_sat(signal, low, high),
                sym.hard_sat(signal, low, high))
        else:
            pass
        first: Var = control.washout('Washout'+str(2*index+1)+'Pu', measured, washouts[2*index],
                                    p.washout_times[2*index], Const(1.0), measured)
        if p.washout_times[2*index+1] > 0:
            second: Var = control.washout('Washout'+str(2*index+2)+'Pu', first, washouts[2*index+1],
                                         p.washout_times[2*index+1], Const(1.0), Const(0.0))
        else:
            second = first
        gain: Expr = ks2 if index == 1 else Const(1.0)
        paths.append(control.lag('Transducer'+str(index+1)+'Pu', gain*second, transducers[index],
                                 p.transducer_times[index], Const(0.0)))
    tracked: Var = control.algebraic('CombinedPu', paths[0]+ks3*paths[1], Const(0.0))
    repeat: int
    order: int
    for repeat in range(0 if p.ramp_m == 0 else p.ramp_n):
        tracked = control.lead_lag('Ramp'+str(repeat+1)+'LeadPu', tracked, t8, t9, p.t8, p.t9, Const(0.0))
        for order in range(1, p.ramp_m):
            tracked = control.lag('Ramp'+str(repeat+1)+'Lag'+str(order)+'Pu', tracked, t9, p.t9, Const(0.0))
    phase: Var = control.algebraic('DampingDemandPu', ks1*(tracked-paths[1]), Const(0.0))
    phase_count: int = 4 if kind == RampStabilizerKind.LIMITED_FOUR_PHASE else (3 if kind == RampStabilizerKind.LIMITED_THREE_PHASE else 2)
    for index in range(phase_count):
        lead_name: str = ('T1', 'T3', 'T10', 'T12')[index]
        lag_name: str = ('T2', 'T4', 'T11', 'T13')[index]
        phase_pair: tuple[float,float] = p.phase_times[index] if index < 3 else p.fourth_phase
        lead: Var = control.parameter(lead_name, phase_pair[0])
        lag: Var = control.parameter(lag_name, phase_pair[1])
        phase = control.lead_lag('Phase'+str(index+1)+'Pu', phase, lead, lag,
                                phase_pair[0], phase_pair[1], Const(0.0))
    output: Var = control.algebraic('VsPu', sym.hard_sat(phase, minimum, maximum), Const(0.0))
    return control.finish((output,), 'Dual-input stabilizer with explicitly ordered ramp tracking')
