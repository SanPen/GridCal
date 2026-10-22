# SPDX-License-Identifier: MPL-2.0
"""Alternator-fed controlled bridge with external output limiting."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.alternator_rectifier import (
    AlternatorRectifierKind, AlternatorRectifierParameters, build_alternator_rectifier,
)


def build_exac4_template(vf: VarFactory, name: str | None = None,
                          parameters: AlternatorRectifierParameters | None = None) -> RmsModelTemplate:
    """Build a controlled-rectifier exciter supplied by a regulated alternator.

    A voltage-sensing lag, clipped voltage error, phase lead-lag and first-order
    amplifier drive the controlled bridge. Alternator voltage regulation is
    represented as a constant supply. Main field current reduces both unloaded
    bridge voltage bounds by ``KC*Ifd``; terminal voltage does not scale them.
    Clipping acts on the bridge output, outside the amplifier lag, whose memory
    can wind up while field voltage remains bounded. Additive stabilizing and
    minimum-excitation signals enter before voltage-error clipping.

    Inputs are sensed voltage, voltage reference, supplementary voltage,
    minimum-excitation voltage and main-generator field current, all per unit on
    their connected bases. Outputs are field voltage and phase-compensator
    demand. Positive sensing, phase and amplifier lags give three states; exact
    zero-time reductions remove the corresponding states. A zero phase lag
    requires a zero phase lead. Initialization stores the host operating voltage
    and field demand, with reference ``Us0+Efd0/KA`` before external bias correction.
    All time constants are measured in seconds.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical coefficients and unloaded capability limits.
    :return: Native alternator-fed controlled-bridge excitation controller.
    :raises ValueError: Invalid coefficients or improper phase compensation.
    """
    return build_alternator_rectifier(vf, 'EXAC4' if name is None else name,
        AlternatorRectifierKind.OUTPUT_CLIP, parameters)
