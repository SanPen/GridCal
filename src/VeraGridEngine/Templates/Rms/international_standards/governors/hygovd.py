# SPDX-License-Identifier: MPL-2.0
"""Hydraulic PI gate regulation with asymmetric speed pickup."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.hygov import (
    NonlinearHydroGovernorParameters, build_hygov_template)


def build_hygovd_template(vf: VarFactory, name: str | None = None,
                         parameters: NonlinearHydroGovernorParameters | None = None) -> RmsModelTemplate:
    """Hydraulic PI gate regulation with asymmetric speed pickup.

    The deadband acts on control speed only; gate-scaled turbine damping uses
    raw speed deviation. Total PI output velocity and travel are limited before
    the actual gate servo. Head, flow acceleration and hydraulic power retain
    the nonlinear rigid-column equations. Four states and nominal-head
    initialization follow the shared hydraulic kernel. Ports are speed and a
    speed/load reference; outputs are mechanical power, gate opening and flow.

    :param vf: Shared symbolic variable factory.
    :param name: Optional native instance label.
    :param parameters: Physical coefficients and asymmetric speed thresholds.
    :return: Native controller preserving the shared physical kernel and units.
    """
    settings: NonlinearHydroGovernorParameters = (NonlinearHydroGovernorParameters(deadband_low=-.0005,deadband_high=.0005)
        if parameters is None else parameters)
    return build_hygov_template(vf,'HYGOVD' if name is None else name,settings)
