# SPDX-License-Identifier: MPL-2.0
"""Hydraulic speed regulation with continuous asymmetric speed deadband."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.ieeeg3 import (
    HydraulicGovernorParameters, build_ieeeg3_template)


def build_ieeeg3d_template(vf: VarFactory, name: str | None = None,
                           parameters: HydraulicGovernorParameters | None = None) -> RmsModelTemplate:
    """Build a deadband hydraulic governor with an inverse-response water column.

    Shaft-speed deviation passes through a continuous deadband with independent
    over- and underspeed thresholds. Outside the band its output is deviation
    minus the corresponding threshold; inside it the output is zero. Permanent
    and filtered transient gate droop close the pilot-valve/servomotor loop.
    Signed velocity limits and bounded gate integration retain separate physical
    stops. The linearized turbine preserves the water column's inverse initial
    response through its potentially negative numerator time coefficient.

    Four states store pilot velocity, gate position, transient-droop memory and
    turbine memory. Nominal-speed initialization uses gate=PRef/a23 and zero
    pilot velocity. Inputs are absolute per-unit speed and mechanical load-power
    reference; outputs are mechanical power, gate position and adjusted speed
    deviation. Signals use the turbine's own power base, with host-owned base
    conversion, and times are seconds. Zero thresholds remove deadband exactly.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical settings; defaults include symmetric 0.0005 speed deadband.
    :return: Native four-state hydraulic governor with asymmetric speed deadband.
    :raises ValueError: Invalid physical parameter domains.
    """
    settings: HydraulicGovernorParameters = (HydraulicGovernorParameters(deadband_high=.0005, deadband_low=-.0005)
        if parameters is None else parameters)
    return build_ieeeg3_template(vf, 'IEEEG3D' if name is None else name, settings)
