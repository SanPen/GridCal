# SPDX-License-Identifier: MPL-2.0
"""Electromechanical voltage regulation with slow reset memory and rapid field forcing."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import _quadratic_saturation_coefficients
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class ElectromechanicalExciterKind(Enum):
    """Physical slow-reset mechanisms and their distinct rapid-forcing logic."""

    DEADBAND_RESET = 1
    INTEGRAL_RESET = 2
    NORMALIZED_RESET = 3
    LAG_OR_INTEGRAL = 4
    BOUNDED_NORMALIZED_RESET = 5


class ElectromechanicalExciterParameters:
    """Regulator mechanics, rapid-action thresholds and rotating-field coefficients."""

    __slots__ = ('tr', 'reset_time', 'reset_deadband', 'fast_band', 'regulator_max',
                 'regulator_min', 'field_gain', 'field_time', 'e1', 'se1', 'e2', 'se2',
                 'gain', 'field_min', 'field_max', 'initial_field_voltage')

    def __init__(self, tr: float = .02, reset_time: float = 2.0,
                 reset_deadband: float = .01, fast_band: float = .05,
                 regulator_max: float | None = 5.0, regulator_min: float = -5.0,
                 field_gain: float | None = 1.0, field_time: float = .5,
                 e1: float = 3.0, se1: float = .1, e2: float = 4.0, se2: float = .3,
                 gain: float = 100.0, field_min: float = 0.0, field_max: float = 5.0,
                 initial_field_voltage: float = 1.0) -> None:
        """Store explicit physical coefficients without selecting a regulator mechanism.

        :param tr: Nonnegative sensing time for normalized reset, in seconds.
        :param reset_time: Reset normalization time; zero selects integration in lag-or-integral mode.
        :param reset_deadband: Nonnegative relay reset deadband in per-unit voltage.
        :param fast_band: Positive rapid-forcing voltage threshold.
        :param regulator_max: Upper forcing capability, or None for saturation-based calibration.
        :param regulator_min: Lower forcing capability; calibrated limits are symmetric.
        :param field_gain: Field resistance coefficient, or None for frozen rheostat calibration.
        :param field_time: Positive rotating-field time constant in seconds.
        :param e1: First field-voltage saturation sample.
        :param se1: Saturation factor at e1.
        :param e2: Second field-voltage saturation sample.
        :param se2: Saturation factor at e2.
        :param gain: Positive gain for lag-or-integral regulation.
        :param field_min: External output lower bound for lag-or-integral regulation.
        :param field_max: External output upper bound for lag-or-integral regulation.
        :param initial_field_voltage: Initial field-voltage seed, replaced by a connected host.
        """
        self.tr: float = tr
        self.reset_time: float = reset_time
        self.reset_deadband: float = reset_deadband
        self.fast_band: float = fast_band
        self.regulator_max: float | None = regulator_max
        self.regulator_min: float = regulator_min
        self.field_gain: float | None = field_gain
        self.field_time: float = field_time
        self.e1: float = e1
        self.se1: float = se1
        self.e2: float = e2
        self.se2: float = se2
        self.gain: float = gain
        self.field_min: float = field_min
        self.field_max: float = field_max
        self.initial_field_voltage: float = initial_field_voltage


def build_electromechanical_exciter(vf: VarFactory, name: str, kind: ElectromechanicalExciterKind,
                                    parameters: ElectromechanicalExciterParameters | None = None) -> RmsModelTemplate:
    """Build slow reset, rapid forcing and nonlinear rotating-field dynamics.

    Sensed voltage, reference and additive supplementary signals determine normal
    regulation. Slow reset is either a deadband relay, a voltage-error integrator,
    a range-normalized clipped-error integrator, or a proportional lag that becomes
    an integrator when its reset time is zero. A parallel rapid-action path selects
    forcing limits outside its voltage band. The lag-or-integral variant detects
    rapid voltage changes against frozen initial sensed voltage independently of
    its biased normal reference, and clips delivered field voltage externally.

    Inputs are sensed voltage, reference, supplementary voltage, additive minimum-
    excitation voltage and terminal voltage. The fixed supply does not use the last
    port. Outputs are delivered field voltage and selected regulator forcing.
    Field losses use internal rotating-field voltage, including when an external
    output clip is present. Calibration is frozen at the operating point. There
    are two states, plus a sensing state when normalized reset has positive TR.

    :param vf: Shared native symbolic factory.
    :param name: Unique instance label.
    :param kind: Explicit slow-reset mechanism and forcing-threshold convention.
    :param parameters: Physical coefficients or None for construction defaults.
    :return: Native electromechanical excitation controller.
    :raises ValueError: Invalid coefficient domains or undefined calibration.
    """
    p: ElectromechanicalExciterParameters = ElectromechanicalExciterParameters() if parameters is None else parameters
    values: tuple[float, ...] = (p.tr, p.reset_time, p.reset_deadband, p.fast_band,
        p.regulator_min, p.field_time, p.e1, p.se1, p.e2, p.se2, p.gain,
        p.field_min, p.field_max, p.initial_field_voltage)
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Electromechanical excitation coefficients must be finite')
    elif min(p.tr, p.reset_time, p.reset_deadband, p.e1, p.se1, p.e2, p.se2) < 0 or min(p.fast_band, p.field_time, p.gain) <= 0:
        raise ValueError('Regulator thresholds, times and field samples have invalid domains')
    elif kind != ElectromechanicalExciterKind.LAG_OR_INTEGRAL and p.reset_time == 0:
        raise ValueError('This reset mechanism requires a positive reset time')
    elif p.field_gain is not None and not math.isfinite(p.field_gain):
        raise ValueError('Field resistance coefficient must be finite')
    elif (p.se1 != 0 or p.se2 != 0) and (p.e2 <= p.e1 or p.e2*p.se2 <= p.e1*p.se1):
        raise ValueError('Enabled saturation requires increasing voltage and excess-field samples')
    elif kind == ElectromechanicalExciterKind.LAG_OR_INTEGRAL and p.field_max <= p.field_min:
        raise ValueError('Field-output upper limit must exceed the lower limit')
    else:
        pass
    upper: float = p.e2*(p.se2+max(0.0,0.0 if p.field_gain is None else p.field_gain)) if p.regulator_max is None else p.regulator_max
    lower: float = -upper if p.regulator_max is None else p.regulator_min
    if not math.isfinite(upper) or upper <= lower:
        raise ValueError('Regulator upper forcing capability must exceed lower capability')
    elif p.field_gain is None and p.initial_field_voltage == 0:
        raise ValueError('Rheostat calibration requires a nonzero initial field voltage')
    else:
        pass
    control: ControlRealization = ControlRealization(vf, name)
    sensing_time: float = p.tr if kind in (ElectromechanicalExciterKind.NORMALIZED_RESET, ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET) else 0.0
    tr: Var = control.parameter('TR', sensing_time)
    reset_time: Var = control.parameter('TRH', p.reset_time)
    deadband: Var = control.parameter('KR', p.reset_deadband)
    fast_band: Var = control.parameter('KV', p.fast_band)
    maximum: Var = control.parameter('VRMAX', upper)
    minimum: Var = control.parameter('VRMIN', lower)
    te: Var = control.parameter('TE', p.field_time)
    gain: Var = control.parameter('KA', p.gain)
    e1: Var = control.parameter('E1', p.e1)
    se1: Var = control.parameter('SE1', p.se1)
    e2: Var = control.parameter('E2', p.e2)
    se2: Var = control.parameter('SE2', p.se2)
    initial_field: Var = control.parameter('Efd0Pu', p.initial_field_voltage)
    initial_voltage: Var = control.parameter('Us0Pu', 1.0)
    field: Var = vf.add_var(('FieldInternalPu_' if kind == ElectromechanicalExciterKind.LAG_OR_INTEGRAL else 'EfdPu_')+name)
    loss: Expr
    initial_loss: Expr
    if p.se1 == 0 and p.se2 == 0:
        loss = Const(0.0)
        initial_loss = Const(0.0)
    else:
        threshold: Expr
        saturation_gain: Expr
        threshold, saturation_gain = _quadratic_saturation_coefficients(e1, se1, e2, se2)
        loss = saturation_gain*sym.max(field-threshold, Const(0.0))**2
        initial_loss = saturation_gain*sym.max(initial_field-threshold, Const(0.0))**2
    ke: Var = vf.add_var('KE_'+name)
    if p.field_gain is None:
        control.block.event_dict[ke] = vf.add_const(value=None)
        control.block.init_eqs[ke] = (maximum/Const(10.0)-initial_loss)/initial_field
    else:
        control.block.event_dict[ke] = Const(p.field_gain)
    initial_regulator: Expr = ke*initial_field+initial_loss
    initial_error: Expr = initial_regulator/gain if kind == ElectromechanicalExciterKind.LAG_OR_INTEGRAL and p.reset_time > 0 else Const(0.0)
    sensed: Var = control.input('UsPu', initial_voltage)
    reference: Var = control.input('UsRefPu', initial_voltage+initial_error)
    supplementary: Var = control.input('VsPu', Const(0.0))
    underexcitation: Var = control.input('UelPu', Const(0.0))
    control.input('VtPu', initial_voltage)
    measured: Var = control.lag('MeasuredPu', sensed, tr, sensing_time, initial_voltage)
    error: Var = control.algebraic('VoltageErrorPu', reference+supplementary+underexcitation-measured, initial_error)
    memory: Var = vf.add_var('ResetMemoryPu_'+name)
    reset_derivative: Expr
    if kind == ElectromechanicalExciterKind.DEADBAND_RESET:
        reset_derivative = (sym.heaviside(error-deadband)-sym.heaviside(-error-deadband))/reset_time
    elif kind == ElectromechanicalExciterKind.INTEGRAL_RESET:
        reset_derivative = error/reset_time
    elif kind in (ElectromechanicalExciterKind.NORMALIZED_RESET, ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET):
        reset_derivative = (maximum-minimum)*sym.hard_sat(error,-fast_band,fast_band)/(fast_band*reset_time)
    elif p.reset_time == 0:
        reset_derivative = gain*error
    else:
        reset_derivative = (gain*error-memory)/reset_time
    control.differential(memory, reset_derivative, initial_regulator, minimum, maximum)
    rapid_error: Expr = initial_voltage-measured if kind == ElectromechanicalExciterKind.LAG_OR_INTEGRAL else error
    if kind == ElectromechanicalExciterKind.NORMALIZED_RESET:
        # This mechanism's sheet includes the threshold in its rapid-action branch.
        high_gate: Expr = Const(1.0)-sym.heaviside(fast_band-rapid_error)
        low_gate: Expr = Const(1.0)-sym.heaviside(fast_band+rapid_error)
    else:
        high_gate = sym.heaviside(rapid_error-fast_band)
        low_gate = sym.heaviside(-rapid_error-fast_band)
    slow_forcing: Expr = sym.hard_sat(memory, minimum, maximum)
    regulator: Var = control.algebraic('RegulatorPu', slow_forcing+high_gate*(maximum-slow_forcing)
        +low_gate*(minimum-slow_forcing), initial_regulator)
    if kind == ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET:
        # The lower field stop belongs to the field memory, rather than an external clip.
        lower_field: Var = control.parameter('VEMIN', p.field_min)
        field_derivative: Expr = (regulator-ke*field-loss)/te
        field_derivative = (Const(1.0)-(Const(1.0)-sym.heaviside(field-lower_field))*sym.heaviside(-field_derivative))*field_derivative
        control.differential(field, field_derivative, initial_field)
    else:
        control.differential(field, (regulator-ke*field-loss)/te, initial_field)
    delivered: Var
    if kind == ElectromechanicalExciterKind.LAG_OR_INTEGRAL:
        field_minimum: Var = control.parameter('EFDMIN', p.field_min)
        field_maximum: Var = control.parameter('EFDMAX', p.field_max)
        delivered = control.algebraic('EfdPu', sym.hard_sat(field, field_minimum, field_maximum), initial_field)
    else:
        delivered = field
    return control.finish((delivered, regulator), 'Electromechanical voltage regulation with slow reset and rapid field forcing')
