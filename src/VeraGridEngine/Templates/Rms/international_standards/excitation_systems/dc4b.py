# SPDX-License-Identifier: MPL-2.0
"""Terminal-fed PID excitation with bounded regulation and rotating-field feedback."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters, RotatingLimiterLocation
from VeraGridEngine.Templates.Rms.pid_rotating_exciter import PidRotatingExciterKind, build_pid_rotating_exciter


def build_dc4b_template(vf: VarFactory, name: str | None = None,
                       parameters: DcExciterParameters | None = None,
                       kp: float = 1., ki: float = 1., kd: float = .1, td: float = .05,
                       minimum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                       maximum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION) -> RmsModelTemplate:
    """Build bounded parallel PID regulation with terminal-powered amplification.

    Filtered voltage error, supplementary voltage and selected additive limiter
    inputs feed parallel proportional, integral and filtered-derivative paths.
    Delivered-field washout feedback subtracts from the same error. The total
    PID demand is bounded by regulator limits divided by amplifier gain. Integral
    motion stops only when it would drive that total demand farther outside its
    limits; proportional and derivative paths remain responsive. A selected
    minimum high gate and maximum low gate follow PID limiting in that order.

    Actual terminal voltage scales the selected forcing before the amplifier,
    whose independent non-windup memory also has terminal-scaled bounds. The
    rotating field integrates forcing minus resistance and quadratic saturation
    losses, with a directional lower field stop. An absent takeover limiter uses
    its exact pre-gate demand; an absent additive signal supplies zero.

    Inputs are sensed voltage, voltage reference, supplementary voltage,
    minimum-excitation demand, actual terminal voltage and maximum-excitation
    demand. Outputs are delivered field voltage, bounded PID demand and demand
    before the maximum gate. Signals are per unit on compatible connected bases;
    time constants are seconds. There are up to six states. Zero sensing or
    amplifier time removes that memory exactly; zero integral, derivative or
    rate-feedback gain removes its corresponding state.

    Initialization balances field losses, divides required amplifier forcing
    by its actual initial terminal supply, and stores that demand in integral
    memory. With zero integral gain a proportional reference offset supplies it.
    Initial compensated sensing and actual terminal voltage are stored separately.
    Zero initial terminal supply cannot support a nonzero field equilibrium.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Sensing, amplifier, field, saturation and feedback settings.
    :param kp: Positive proportional gain.
    :param ki: Nonnegative integral gain in inverse seconds.
    :param kd: Nonnegative derivative gain in seconds.
    :param td: Positive derivative-filter time when derivative action is enabled.
    :param minimum_location: Additive or high-gate minimum limiter insertion.
    :param maximum_location: Additive or low-gate maximum limiter insertion.
    :return: Native six-input, three-output terminal-fed excitation controller.
    :raises ValueError: Invalid coefficients or unspecified calibration.
    """
    return build_pid_rotating_exciter(vf, 'DC4B' if name is None else name,
        PidRotatingExciterKind.BOUNDED_TERMINAL_SUPPLY, parameters, kp, ki, kd, td,
        minimum_location, maximum_location)
