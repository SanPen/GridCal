# SPDX-License-Identifier: MPL-2.0
"""Continuous PID voltage regulation of a saturated rotating excitation machine."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters
from VeraGridEngine.Templates.Rms.pid_rotating_exciter import PidRotatingExciterKind, build_pid_rotating_exciter


def build_esac8b_template(vf: VarFactory, name: str | None = None,
                          parameters: DcExciterParameters | None = None,
                          kp: float = 1., ki: float = 1., kd: float = .1,
                          td: float = .05) -> RmsModelTemplate:
    """Build continuous PID regulation with an independently supplied rotating exciter.

    The voltage error drives parallel proportional, integral and filtered
    derivative paths: ``KP + KI/s + KD*s/(1+TD*s)``. An independently supplied
    amplifier follows their sum, with directional non-windup limits on its
    output state. The PID integrator itself has no limiting or tracking feedback;
    it can wind up while the amplifier is saturated. Field forcing integrates
    amplifier voltage minus resistive and magnetic saturation losses. A lower
    field stop prevents negative delivered excitation while permitting immediate
    recovery. Saturation loss is ``B*max(Efd-A,0)**2``, fitted to the two supplied
    voltage-times-saturation samples. No separate commutation loss is assumed.

    Inputs are compensated voltage, voltage reference, supplementary voltage,
    additive minimum-excitation voltage and actual terminal voltage. The last
    port preserves the common rotating-exciter assembly contract; terminal
    voltage does not scale the independent supply. Outputs are field voltage
    and amplifier input demand. Voltages are per unit on their connected field
    or terminal bases; times are seconds. Only the relevant sensing, amplifier,
    field and saturation coefficients of the shared field parameter object are
    consumed. Phase compensation and field-rate feedback are absent.

    With positive integral gain, initialization sets zero voltage error and
    stores the required field forcing in the integral memory. With zero integral
    gain, a positive proportional gain supplies the necessary reference offset.
    Zero derivative gain removes its memory; zero sensing and amplifier times
    produce exact algebraic stages. The field time is strictly positive.
    Explicit field resistance and amplifier capabilities are required; automatic
    capability or rheostat calibration is outside this construction contract.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique instance label.
    :param parameters: Sensing, amplifier, field and saturation coefficients.
    :param kp: Nonnegative proportional gain.
    :param ki: Nonnegative integral gain in inverse seconds.
    :param kd: Nonnegative derivative gain in seconds.
    :param td: Positive derivative-filter time when derivative action is enabled.
    :return: Native excitation controller, with five states when all stages act.
    :raises ValueError: Invalid physical domains or unspecified calibration.
    """
    return build_pid_rotating_exciter(vf, 'ESAC8B' if name is None else name,
        PidRotatingExciterKind.INDEPENDENT_SUPPLY, parameters, kp, ki, kd, td)
