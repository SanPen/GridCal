# SPDX-License-Identifier: MPL-2.0
"""Controlled-bridge excitation with independently selected minimum and maximum gates."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.alternator_rectifier import (
    AlternatorRectifierKind, AlternatorRectifierParameters, RectifierLimiterLocation,
    build_alternator_rectifier,
)


def build_ac4c_template(vf: VarFactory, name: str | None = None,
                       parameters: AlternatorRectifierParameters | None = None,
                       minimum_location: RectifierLimiterLocation = RectifierLimiterLocation.SUMMATION,
                       maximum_location: RectifierLimiterLocation = RectifierLimiterLocation.SUMMATION) -> RmsModelTemplate:
    """Build a separately supplied controlled bridge with selectable excitation limits.

    A voltage transducer feeds the reference-error summation. Supplementary
    damping and selected additive limiter signals enter before voltage-error
    clipping and phase compensation. A minimum-excitation high-value gate and
    a maximum-excitation low-value gate, when selected, follow compensation in
    that order. The amplifier has non-windup bounds ``VRMIN`` and
    ``VRMAX-KC*Ifd``. A separate output clip enforces a moving commutation
    capability immediately while amplifier memory remains continuous.

    Inputs are sensed voltage, voltage reference, supplementary voltage,
    minimum-excitation signal, field current and maximum-excitation signal.
    Outputs are delivered field voltage, phase demand before both gates and
    demand before the maximum gate. An absent takeover limiter connects to
    its corresponding inspection output for an exact identity. An absent
    additive limiter supplies zero. Signals use compatible per-unit field
    bases; time constants are in seconds. The bridge supply is independent
    of terminal voltage.

    Positive transducer, phase and amplifier lags produce up to three states;
    supported zero-time stages reduce algebraically. Initialization freezes
    actual host voltage and field forcing and derives the matching reference.
    A compatible initial state must lie inside the declared bridge capability.

    :param vf: Shared symbolic variable factory.
    :param name: Optional unique controller label.
    :param parameters: Physical coefficients and capability settings.
    :param minimum_location: Additive or high-value minimum limiter insertion.
    :param maximum_location: Additive or low-value maximum limiter insertion.
    :return: Six-input, three-output native bridge controller.
    :raises ValueError: Invalid coefficients, bounds or improper phase stage.
    """
    return build_alternator_rectifier(vf, 'AC4C' if name is None else name,
        AlternatorRectifierKind.SELECTABLE_GATES, parameters, minimum_location, maximum_location)
