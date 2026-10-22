# SPDX-License-Identifier: MPL-2.0
"""Dual-measurement oscillation damping with independent raw-input clipping and three phase-compensation stages."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.ramp_tracking_stabilizer import (
    RampStabilizerKind, RampStabilizerParameters, StabilizerInterface, build_ramp_tracking_stabilizer)


def build_pss2b_template(vf: VarFactory, name: str | None = None,
                          parameters: RampStabilizerParameters | None = None,
                          interface: StabilizerInterface = StabilizerInterface.SHAFT_SPEED_POWER) -> RmsModelTemplate:
    """Build dual-input damping with independent raw-input clipping and three phase-compensation stages.

    Both measured signals pass through washouts and optional transducers. With
    path outputs A and B, including KS2 in B, ramp tracking produces
    R*(A+KS3*B)-B, where R=[(1+s*T8)/(1+s*T9)^M]^N. Output gain and phase
    compensation precede supplementary-voltage clipping. Filter order determines
    the actual number of memories: M*N denominator states, without padding.
    M=0 or N=0 bypasses ramp tracking; zero optional washout/transducer times
    and zero phase pairs are exact bypasses. Washout memories initialize from
    steady measurements and subsequent memories initialize to zero, yielding
    zero supplementary output at any admissible constant operating point.

    The default public ports preserve absolute shaft speed, its reference and
    electrical power. The selected-signal interface instead exposes two host-
    scaled measurements. Output is per-unit supplementary excitation voltage;
    all times are seconds and the connecting host owns measurement power bases.
    Limits do not freeze the washout, ramp or phase memories. Physical stages
    are shared with the other dual-input realization, while their distinct
    input-limiting and phase structures remain explicit.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical washout, ramp, phase, gain and limit settings.
    :param interface: Shaft/reference/power ports or two selected measurements.
    :return: Native supplementary excitation controller.
    :raises ValueError: Invalid times, orders, limits or nonfinite coefficients.
    """
    return build_ramp_tracking_stabilizer(vf, 'PSS2B' if name is None else name,
        RampStabilizerKind.LIMITED_THREE_PHASE, parameters, interface)
