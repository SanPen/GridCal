# SPDX-License-Identifier: MPL-2.0
"""Terminal-powered static excitation with independently selected limiter insertion."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esst1a import (
    TerminalFedExciterParameters, StaticMaximumExcitationLocation, build_esst1a_template,
)


def build_st1c_template(vf: VarFactory, name: str | None = None,
                       parameters: TerminalFedExciterParameters | None = None,
                       maximum_location: StaticMaximumExcitationLocation = StaticMaximumExcitationLocation.ERROR_SUM) -> RmsModelTemplate:
    """Build terminal-fed field forcing with independent minimum and maximum limiters.

    Filtered voltage error and delivered-field rate feedback feed error clipping,
    two phase compensators and a non-windup amplifier. Minimum and maximum
    excitation signals each select signed addition at the error sum, takeover
    after error clipping, or takeover after the regulator-output sum. High gates
    precede low gates at either location. Stabilizing voltage separately selects
    the error sum or regulator-output sum. Excess field current subtracts
    KLR*max(Ifd-ILR,0) after amplification.

    Delivered excitation is bounded by actual terminal-powered bridge capability:
    VT*VRMIN below and VT*VRMAX-KC*Ifd above. If extreme loading crosses those
    bounds, the commutation ceiling is applied last. Delivered forcing after all
    gates and capabilities supplies rate feedback. Amplifier memory retains its
    independent fixed bounds. There is no rotating-field integrator.

    Seven inputs are sensed voltage, reference, stabilizer, minimum limiter,
    actual terminal voltage, field current and maximum limiter. Outputs are
    field voltage, clipped error, demand before the output high gate, demand
    before the output low gate and demand before the input low gate. Absent
    takeover inputs connect to their exact pre-gate output; additive absence
    supplies zero. Signals use compatible per-unit bases and time constants
    in seconds. Up to five states store sensing, two phase memories, amplifier
    and field-feedback memory. Supported zero lags reduce algebraically.

    Initialization freezes actual field, current and auxiliary biases and
    balances both chosen summations. A feasible equilibrium must respect all
    active gates and capabilities. Source-runtime priority for crossed terminal
    bounds is not inferred from the explicit native numerical convention.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Physical stages and minimum/stabilizer insertion choices.
    :param maximum_location: Additive, input low gate or output low gate insertion.
    :return: Native seven-input, five-output static excitation controller.
    :raises ValueError: Invalid physical coefficients or insertion selections.
    """
    return build_esst1a_template(vf,'ST1C' if name is None else name,parameters,maximum_location)
