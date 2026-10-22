# SPDX-License-Identifier: MPL-2.0
"""PID control of a saturated commutator exciter with loaded compound supply."""
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters, RotatingLimiterLocation
from VeraGridEngine.Templates.Rms.compound_excitation_supply import CompoundSupplyParameters
from VeraGridEngine.Templates.Rms.pid_rotating_exciter import PidRotatingExciterKind, build_pid_rotating_exciter


def build_dc4c_template(vf: VarFactory, name: str | None = None,
                       parameters: DcExciterParameters | None = None,
                       kp: float = 1., ki: float = 1., kd: float = .1, td: float = .05,
                       minimum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                       maximum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                       supply_parameters: CompoundSupplyParameters | None = None) -> RmsModelTemplate:
    """Build bounded PID control of a compound-fed rotating commutator field.

    Sensed voltage and delivered-field washout oppose reference and supplement.
    An additive minimum limiter raises error; an additive maximum limiter lowers
    error. Parallel proportional, integral and filtered derivative action is
    bounded at VRMIN/KA and VRMAX/KA. Integral motion stops only when it pushes
    total PID farther outside those limits. Optional minimum high and maximum
    low takeover gates follow PID, in that order. The bounded KA/(1+s*TA)
    amplifier then multiplies the available supply; its own limits remain fixed.

    The potential circuit uses terminal voltage/current phasors or independent
    potential KP. Its rectifier load is the commutator winding current equivalent
    KE*EFD plus quadratic magnetic loss, distinct from generator field current.
    Loaded supply is capped at VBMAX. Field memory integrates forcing minus
    winding loss through TE, with a directional lower stop VEMIN and no invented
    upper field ceiling. Zero supply preserves field and amplifier memories.

    Nine inputs are sensed voltage, reference, supplement, rectangular terminal
    voltage and outgoing current, minimum and maximum limiter demand. Outputs
    are delivered field, bounded PID and demand before the maximum gate.
    Signals use compatible per-unit bases; times are seconds and phase degrees.
    Up to six memories retain sensing, integral, derivative, amplifier, field
    and feedback. Disabled channels and zero sensing/amplifier times reduce
    exactly. Initial winding loss divided by loaded supply and KA seeds PID;
    the actual auxiliary bias sets reference at connection. Positive initial
    supply and feasible field/amplifier/PID/gate capabilities are required.

    :param vf: Shared symbolic factory.
    :param name: Optional controller label.
    :param parameters: Sensing, amplifier, winding, saturation and feedback.
    :param kp: Positive regulator proportional gain.
    :param ki: Nonnegative integral gain, inverse seconds.
    :param kd: Nonnegative derivative gain, seconds.
    :param td: Derivative filter time, seconds.
    :param minimum_location: Summed minimum or post-PID high takeover gate.
    :param maximum_location: Subtracted maximum or post-PID low takeover gate.
    :param supply_parameters: Physical potential source and loaded bridge.
    :return: Native nine-input, three-output rotating excitation controller.
    :raises ValueError: Invalid domains, supply or unspecified calibration.
    """
    supply: CompoundSupplyParameters = CompoundSupplyParameters() if supply_parameters is None else supply_parameters
    return build_pid_rotating_exciter(vf,'DC4C' if name is None else name,
        PidRotatingExciterKind.BOUNDED_COMPOUND_SUPPLY,parameters,kp,ki,kd,td,
        minimum_location,maximum_location,supply)
