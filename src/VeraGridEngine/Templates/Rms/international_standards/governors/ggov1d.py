# SPDX-License-Identifier: MPL-2.0
"""Tracked fuel-valve governor with asymmetric shaft-speed insensitivity."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.ggov1 import (
    TrackedGovernorParameters, build_ggov1_template)


def build_ggov1d_template(vf: VarFactory, name: str | None = None,
                          parameters: TrackedGovernorParameters | None = None) -> RmsModelTemplate:
    """Build a tracked fuel-valve governor with an additional speed deadband.

    Independent underspeed and overspeed thresholds act on shaft-speed deviation
    before droop feedback and the combined regulation-error deadband. Outside
    each threshold the excess deviation passes continuously, avoiding a jump
    at pickup. The two deadbands serve different roles and are not merged.
    Fuel-flow selection, tracked PI memories, valve travel limits, turbine
    conversion and operating-point initialization follow the shared physical
    governor kernel. Power uses one declared turbine base and time is seconds.
    Port order is speed, electrical power, speed/load reference, supervisory
    power setpoint; outputs are mechanical power, valve
    stroke and selected command. Acceleration limiting and nonzero fuel transport delay are outside this continuous realization.

    :param vf: Shared symbolic factory.
    :param name: Optional governor instance label.
    :param parameters: Coefficients including separate asymmetric speed thresholds.
    :return: Native four-input, three-output governor.
    """
    settings: TrackedGovernorParameters = (TrackedGovernorParameters(speed_deadband=(-.0005, .0005))
        if parameters is None else parameters)
    return build_ggov1_template(vf, 'GGOV1D' if name is None else name, settings)
