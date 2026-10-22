# SPDX-License-Identifier: MPL-2.0
"""Gas-turbine speed regulation with separate underspeed and overspeed pickup."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.gast import (
    GasGovernorParameters, build_gast_template)


def build_gastd_template(vf: VarFactory, name: str | None = None,
                         parameters: GasGovernorParameters | None = None) -> RmsModelTemplate:
    """Gas-turbine speed regulation with separate underspeed and overspeed pickup.

    The continuous deadband acts before inverse droop; exhaust-temperature
    limiting retains the independent thermal low-value gate and three memories.
    Turbine damping senses raw speed deviation and therefore remains active
    within the control deadband. Ports are shaft speed and turbine-power
    reference; outputs are mechanical power and valve opening. Initialization
    follows the shared thermal equilibrium and directional valve stops.

    :param vf: Shared symbolic variable factory.
    :param name: Optional native instance label.
    :param parameters: Physical coefficients and asymmetric speed thresholds.
    :return: Native controller preserving the shared physical kernel and units.
    """
    settings: GasGovernorParameters = (GasGovernorParameters(deadband_low=-.0005,deadband_high=.0005)
        if parameters is None else parameters)
    return build_gast_template(vf,'GASTD' if name is None else name,settings)
