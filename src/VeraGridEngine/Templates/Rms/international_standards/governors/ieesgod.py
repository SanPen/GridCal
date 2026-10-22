# SPDX-License-Identifier: MPL-2.0
"""Staged steam-turbine regulation with asymmetric speed insensitivity."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.ieesgo import (
    SteamGovernorParameters, build_ieesgo_template)


def build_ieesgod_template(vf: VarFactory, name: str | None = None,
                         parameters: SteamGovernorParameters | None = None) -> RmsModelTemplate:
    """Staged steam-turbine regulation with asymmetric speed insensitivity.

    Separate pickup thresholds precede controller lead/lag and governor lag.
    Bounded valve demand drives chest, reheater and crossover memories with
    independent power fractions. Supported zero-time stages remain algebraic.
    Inputs are absolute shaft speed and turbine-power reference; outputs are
    total mechanical power and bounded valve demand. All power signals share
    one turbine base and memories initialize from the same operating point.

    :param vf: Shared symbolic variable factory.
    :param name: Optional native instance label.
    :param parameters: Physical coefficients and asymmetric speed thresholds.
    :return: Native controller preserving the shared physical kernel and units.
    """
    settings: SteamGovernorParameters = (SteamGovernorParameters(deadband_low=-.0005,deadband_high=.0005)
        if parameters is None else parameters)
    return build_ieesgo_template(vf,'IEESGOD' if name is None else name,settings)
