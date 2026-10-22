# SPDX-License-Identifier: MPL-2.0
"""Alternator-fed controlled rectification with explicit commutation-dependent capability."""
from __future__ import annotations

from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class AlternatorRectifierKind(Enum):
    """Physical placement of output clipping and regulator anti-windup."""

    OUTPUT_CLIP = 1
    NONWINDUP_GATE = 2
    SELECTABLE_GATES = 3


class RectifierLimiterLocation(Enum):
    """Insert a supplementary limiter at the error sum or its takeover gate."""

    SUMMATION = 1
    TAKEOVER_GATE = 2


class AlternatorRectifierParameters:
    """Voltage sensing, phase compensation, amplifier and bridge capability settings."""

    __slots__ = ('tr', 'vi_max', 'vi_min', 'tc', 'tb', 'ka', 'ta', 'vr_max', 'vr_min', 'kc')

    def __init__(self, tr: float = .02, vi_max: float = .2, vi_min: float = -.2,
                 tc: float = .1, tb: float = .2, ka: float = 100.0, ta: float = .05,
                 vr_max: float = 5.0, vr_min: float = -5.0, kc: float = .1) -> None:
        """Store native physical coefficients.

        :param tr: Nonnegative voltage sensing time in seconds.
        :param vi_max: Voltage-error upper clipping bound.
        :param vi_min: Voltage-error lower clipping bound.
        :param tc: Nonnegative phase-compensation lead time in seconds.
        :param tb: Nonnegative phase-compensation lag time in seconds.
        :param ka: Positive amplifier gain.
        :param ta: Nonnegative amplifier lag in seconds.
        :param vr_max: Unloaded bridge upper field-voltage capability.
        :param vr_min: Unloaded lower field-voltage capability.
        :param kc: Nonnegative field-current commutation loading coefficient.
        """
        self.tr: float = tr
        self.vi_max: float = vi_max
        self.vi_min: float = vi_min
        self.tc: float = tc
        self.tb: float = tb
        self.ka: float = ka
        self.ta: float = ta
        self.vr_max: float = vr_max
        self.vr_min: float = vr_min
        self.kc: float = kc


def build_alternator_rectifier(vf: VarFactory, name: str, kind: AlternatorRectifierKind,
                                parameters: AlternatorRectifierParameters | None = None,
                                minimum_location: RectifierLimiterLocation = RectifierLimiterLocation.SUMMATION,
                                maximum_location: RectifierLimiterLocation = RectifierLimiterLocation.SUMMATION) -> RmsModelTemplate:
    """Assemble an alternator-fed voltage regulator and controlled bridge.

    :param vf: Shared native symbolic factory.
    :param name: Unique instance label.
    :param kind: Explicit limiter placement and anti-windup structure.
    :param parameters: Physical coefficients or None for construction defaults.
    :param minimum_location: Minimum-excitation insertion for selectable gates.
    :param maximum_location: Maximum-excitation insertion for selectable gates.
    :return: Five- or six-input controller with field-voltage and pre-gate-demand outputs.
    :raises ValueError: Nonfinite coefficients, invalid bounds, gain or time constants.
    """
    p: AlternatorRectifierParameters = AlternatorRectifierParameters() if parameters is None else parameters
    if (min(p.tr, p.tc, p.tb, p.ta, p.kc) < 0 or p.ka <= 0 or
            p.vi_max <= p.vi_min or p.vr_max <= p.vr_min):
        raise ValueError('Alternator-fed rectifier settings are invalid')
    else:
        pass
    control: ControlRealization = ControlRealization(vf, name)
    tr: Var = control.parameter('TR', p.tr)
    vi_max: Var = control.parameter('VIMAX', p.vi_max)
    vi_min: Var = control.parameter('VIMIN', p.vi_min)
    tc: Var = control.parameter('TC', p.tc)
    tb: Var = control.parameter('TB', p.tb)
    ka: Var = control.parameter('KA', p.ka)
    ta: Var = control.parameter('TA', p.ta)
    vr_max: Var = control.parameter('VRMAX', p.vr_max)
    vr_min: Var = control.parameter('VRMIN', p.vr_min)
    kc: Var = control.parameter('KC', p.kc)
    field_initial: Var = control.parameter('Efd0Pu', 1.0)
    voltage_initial: Var = control.parameter('Us0Pu', 1.0)
    sensed: Var = control.input('UsPu', voltage_initial)
    reference: Var = control.input('UsRefPu', voltage_initial+field_initial/ka)
    supplementary: Var = control.input('VsPu', Const(0.0))
    selectable: bool = kind == AlternatorRectifierKind.SELECTABLE_GATES
    nonwindup: bool = kind != AlternatorRectifierKind.OUTPUT_CLIP
    gated: bool = kind == AlternatorRectifierKind.NONWINDUP_GATE or (selectable and minimum_location == RectifierLimiterLocation.TAKEOVER_GATE)
    underexcitation: Var = control.input('UelPu', field_initial/ka if gated else Const(0.0))
    field_current: Var = control.input('IfdPu', Const(1.0))
    maximum_input: Var | None = control.input('OelPu', field_initial/ka if maximum_location == RectifierLimiterLocation.TAKEOVER_GATE else Const(0.0)) if selectable else None
    measured: Var = control.lag('MeasuredPu', sensed, tr, p.tr, voltage_initial)
    error: Expr = reference+supplementary-measured
    if gated:
        pass
    else:
        error = error+underexcitation
    if maximum_input is not None and maximum_location == RectifierLimiterLocation.SUMMATION:
        error = error+maximum_input
    else:
        pass
    clipped: Var = control.algebraic('LimitedErrorPu', sym.hard_sat(error, vi_min, vi_max), field_initial/ka)
    phase: Var = control.lead_lag('PhasePu', clipped, tc, tb, p.tc, p.tb, field_initial/ka)
    upper: Expr = vr_max-kc*field_current
    lower: Expr = vr_min if nonwindup else vr_min-kc*field_current
    demand: Expr = sym.max(phase, underexcitation) if gated else phase
    minimum_gate: Var | None = control.algebraic('MinimumGatePu', demand, field_initial/ka) if selectable else None
    if maximum_input is not None and maximum_location == RectifierLimiterLocation.TAKEOVER_GATE:
        demand = sym.min(demand, maximum_input)
    else:
        pass
    if nonwindup:
        regulator: Var = control.lag('RegulatorPu', ka*demand, ta, p.ta, field_initial, lower, upper)
    else:
        # An external bridge clip does not stop the internal regulator memory.
        regulator = control.lag('RegulatorPu', ka*demand, ta, p.ta, field_initial)
    field: Var = control.algebraic('EfdPu', sym.hard_sat(regulator, lower, upper), field_initial)
    outputs: tuple[Var, ...] = (field, phase, minimum_gate) if minimum_gate is not None else (field, phase)
    return control.finish(outputs, 'Alternator-fed controlled bridge with field-current-dependent voltage capability')
