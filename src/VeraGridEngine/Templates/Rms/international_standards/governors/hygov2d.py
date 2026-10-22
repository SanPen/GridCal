# SPDX-License-Identifier: MPL-2.0
"""Asymmetric-deadband cascaded PI hydraulic control with explicit gate and penstock memories."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.hygov2 import CascadedHydroGovernorParameters, build_hygov2_template


def build_hygov2d_template(vf: VarFactory, name: str | None = None,
                           parameters: CascadedHydroGovernorParameters | None = None) -> RmsModelTemplate:
    """Build cascaded hydraulic control with continuous excess-speed deadband.

    Absolute shaft speed is converted to deviation from nominal and only excess
    deviation outside the lower/upper thresholds enters the speed PI controller.
    Inside the band, both the proportional correction and speed-integral rate
    are zero. Gate-motion limits, governor integral memory, permanent/transient
    gate droop and the inverse-response linear water column retain their own
    dynamics. No mechanical damping or nonlinear head law is inferred.

    Inputs are absolute per-unit speed and a reference in speed-control units.
    Outputs are mechanical power on the declared turbine base, actual gate
    position and bounded gate velocity. Six states exist with enabled speed
    integral action; zero integral gain removes its memory exactly. All times
    use seconds. Initialization balances actual initial power against the
    gate-to-power gain and freezes reference from permanent gate droop, including
    isochronous operation with zero permanent droop. Zero deadband thresholds
    recover the parent's exact symbolic speed-deviation path.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical coefficients and asymmetric thresholds.
    :return: Native hydraulic governor with explicit control deadband.
    :raises ValueError: Invalid physical coefficients or deadband domain.
    """
    label: str = 'HYGOV2D' if name is None else name
    p: CascadedHydroGovernorParameters = CascadedHydroGovernorParameters(deadband_low=-.0005,deadband_high=.0005) if parameters is None else parameters
    return build_hygov2_template(vf,label,p)
