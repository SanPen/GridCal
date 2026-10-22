# SPDX-License-Identifier: MPL-2.0
"""Alternator-fed controlled bridge with gated minimum excitation and non-windup regulation."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.alternator_rectifier import (
    AlternatorRectifierKind, AlternatorRectifierParameters, build_alternator_rectifier,
)


def build_esac4a_template(vf: VarFactory, name: str | None = None,
                           parameters: AlternatorRectifierParameters | None = None) -> RmsModelTemplate:
    """Build an alternator-fed controlled bridge with a limited amplifier state.

    Sensed-voltage filtering and voltage-error clipping precede a phase lead-lag.
    A high-value minimum-excitation gate follows phase compensation. The bounded
    first-order amplifier suppresses outward state motion at either limit and
    releases immediately when the demanded derivative points inward. Its upper
    capability is ``VRMAX-KC*Ifd``; its lower capability is the fixed ``VRMIN``.
    An explicit output clip also enforces a moving upper capability immediately
    when field current changes while the amplifier memory remains continuous.

    Inputs are sensed voltage, reference voltage, additive supplementary voltage,
    high-value minimum-excitation demand and generator field current. Outputs are
    field voltage and pre-gate phase demand. An absent minimum-excitation limiter
    connects to that second output to bypass the gate without a large constant.
    All voltages/currents are per unit on their connected field bases. The supply
    is a separately regulated alternator and does not collapse with bus voltage.

    Up to three lag states store sensed voltage, phase memory and amplifier
    output. Zero sensing/amplifier lags and zero lead/lag pairs become algebraic
    exactly. Initialization stores the host voltage and field forcing and derives
    the matching reference; the connecting assembly accounts for steady additive
    signals. A compatible equilibrium requires the limiter to permit the host's
    requested field forcing. Time constants are in seconds.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical coefficients and unloaded capability limits.
    :return: Native non-windup controlled-bridge excitation controller.
    :raises ValueError: Invalid coefficients or improper phase compensation.
    """
    return build_alternator_rectifier(vf, 'ESAC4A' if name is None else name,
        AlternatorRectifierKind.NONWINDUP_GATE, parameters)
