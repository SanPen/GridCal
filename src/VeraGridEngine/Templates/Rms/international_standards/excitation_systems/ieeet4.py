# SPDX-License-Identifier: MPL-2.0
"""Deadband relay reset with parallel rapid forcing."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.electromechanical_exciter import (
    ElectromechanicalExciterKind, ElectromechanicalExciterParameters, build_electromechanical_exciter)


def build_ieeet4_template(vf: VarFactory, name: str | None = None,
                           parameters: ElectromechanicalExciterParameters | None = None) -> RmsModelTemplate:
    """Build deadband relay reset with parallel rapid forcing.

    The slow path integrates a unit relay outside a symmetric voltage deadband KR.
    Its reset rate is one over TRH; inside the deadband the reset memory holds.
    A separate rapid path selects the regulator ceiling or floor when voltage
    error exceeds KV. The reset memory remains bounded and can recover inward.

    Selected regulator forcing drives rotating-field dynamics with linear
    resistance and quadratic excess-field saturation. Initial forcing balances
    both losses; optional resistance and capability calibration is frozen at the
    operating point. There are two states, plus a sensing state only when the
    selected mechanism includes a positive sensing time. Voltages are per-unit
    on connected bases, time constants are seconds and saturation factors are
    dimensionless. Inputs are sensed voltage, reference, supplementary voltage,
    additive minimum-excitation voltage and unused terminal voltage. Outputs
    are delivered field voltage and selected regulator forcing.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical reset, forcing, field and saturation coefficients.
    :return: Native electromechanical excitation controller.
    :raises ValueError: Invalid physical domains or undefined calibration.
    """
    return build_electromechanical_exciter(vf, 'IEEET4' if name is None else name,
                                          ElectromechanicalExciterKind.DEADBAND_RESET, parameters)
