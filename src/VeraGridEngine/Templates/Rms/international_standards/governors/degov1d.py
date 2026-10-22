# SPDX-License-Identifier: MPL-2.0
"""Engine-speed regulation with asymmetric deadband and delayed combustion."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.degov1 import DieselGovernorParameters, build_degov1_template


def build_degov1d_template(vf: VarFactory, name: str | None = None,
                           parameters: DieselGovernorParameters | None = None) -> RmsModelTemplate:
    """Build delayed fuel regulation with independent speed deadband thresholds.

    The continuous deadband removes the overspeed or underspeed threshold from
    speed deviation outside the corresponding boundary. Its output enters the
    electronic control box before subtraction of throttle or filtered electrical
    power droop. Zero thresholds restore ordinary continuous speed feedback.
    Five memories preserve the control box and integrating actuator; electrical
    feedback can add a measurement memory. Fuel saturation precedes transport
    delay. The delay uses held accepted-boundary history with equilibrium startup.

    Inputs are absolute shaft speed, electrical power and reference. Outputs are
    mechanical power, delayed torque and undelayed bounded throttle. Powers and
    torque use one declared turbine base; the connecting host owns any rating
    conversion. Time constants and delay are seconds. Separate initial torque
    and electrical power preserve steady losses. The reference initializes from
    the selected steady droop feedback rather than a numerical nominal load.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical settings; defaults select a symmetric 0.001 band.
    :return: Native engine governor with continuous asymmetric speed deadband.
    :raises ValueError: Invalid coefficient domains or deadband signs.
    """
    settings: DieselGovernorParameters = (DieselGovernorParameters(deadband_high=.001,deadband_low=-.001)
        if parameters is None else parameters)
    return build_degov1_template(vf, 'DEGOV1D' if name is None else name, settings)
