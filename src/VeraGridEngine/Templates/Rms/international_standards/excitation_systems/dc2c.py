# SPDX-License-Identifier: MPL-2.0
"""Bounded rotating excitation with selectable limiter takeover and explicit field-memory stops."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, RotatingLimiterLocation, build_dc_exciter


def build_dc2c_template(vf: VarFactory, name: str | None = None,
                           parameters: DcExciterParameters | None = None,
                           minimum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                           maximum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION) -> RmsModelTemplate:
    """Build bounded rotating excitation with terminal-voltage-scaled regulator capability.

    Sensed-voltage error, supplementary excitation and selected additive
    limiter outputs pass through phase compensation. A high-value minimum-
    excitation gate and low-value maximum-excitation gate can instead take
    over after compensation, before the non-windup amplifier. The rotating
    field circuit integrates regulator forcing minus resistive and quadratic
    magnetic-saturation losses. Lower/upper field-memory stops are independent
    of the amplifier limits and permit immediate inward recovery.

    Field-voltage rate feedback senses the field memory. Explicit positive-
    voltage saturation samples can be supplied in either order; their excess
    field losses determine the same physical quadratic fit. Near-unbounded
    field capability uses explicit finite travel stops, without reinterpreting
    a saturation sample as an output limit. All voltages use their connected
    per-unit terminal/field bases and all time constants use seconds.

    Six inputs are compensated voltage, voltage reference, supplementary
    voltage, minimum-excitation signal, actual terminal voltage and maximum-
    excitation signal. Outputs are field voltage, pre-minimum-gate demand and
    pre-maximum-gate demand. These inspection signals permit exact bypass of
    absent takeover controllers. Five states exist with positive lags; zero
    permitted sensing/amplifier/compensation times are exact algebraic stages.
    Initialization balances actual field loss and regulator forcing, with zero
    field-rate feedback and consistent limiter bypass signals.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Regulator, field, saturation and independent field-stop coefficients.
    :param minimum_location: Additive error or high-value takeover selection.
    :param maximum_location: Additive error or low-value takeover selection.
    :return: Native bounded rotating excitation controller.
    :raises ValueError: Invalid physical domains, saturation fit, limits or selections.
    """
    label: str = 'DC2C' if name is None else name
    p: DcExciterParameters = DcExciterParameters(field_min=-999.,field_max=999.) if parameters is None else parameters
    return build_dc_exciter(vf,label,DcExciterKind.BOUNDED_TERMINAL_SUPPLY,p,minimum_location,maximum_location)
