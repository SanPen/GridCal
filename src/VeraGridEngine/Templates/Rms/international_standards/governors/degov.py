# SPDX-License-Identifier: MPL-2.0
"""Isochronous engine-speed regulation with delayed fuel combustion."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.degov1 import DieselGovernorParameters, build_degov1_template


def build_degov_template(vf: VarFactory, name: str | None = None,
                         parameters: DieselGovernorParameters | None = None) -> RmsModelTemplate:
    """Build isochronous regulation with electronic control and a fuel actuator.

    Speed error drives a second-order electronic control box and a three-memory
    integrating actuator. Static fuel limits precede combustion transport delay.
    With zero permanent droop, the actuator integral sustains the loaded operating
    point at nominal speed without a steady speed error. No throttle or electrical
    power feedback is subtracted from the speed reference in this variant.

    Inputs are absolute shaft speed, electrical power and reference. Outputs are
    mechanical power, mechanical torque and bounded throttle. Power equals delayed
    torque times absolute speed; each uses the declared machine base. Times are
    seconds. Initialization stores initial torque in the actuator integral and
    uses equilibrium prehistory for the delay. Accepted-boundary history determines
    delay resolution. Zero delay is algebraic and allocates no retained mode.

    :param vf: Shared symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical coefficients with permanent droop explicitly zero.
    :return: Native isochronous engine governor.
    :raises ValueError: Nonzero permanent droop or invalid physical coefficients.
    """
    settings: DieselGovernorParameters = DieselGovernorParameters(droop=0.) if parameters is None else parameters
    if settings.droop != 0:
        raise ValueError('Isochronous engine regulation requires zero permanent droop')
    else:
        return build_degov1_template(vf, 'DEGOV' if name is None else name, settings)
