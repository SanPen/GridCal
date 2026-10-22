# SPDX-License-Identifier: MPL-2.0
"""Continuous error reset with parallel rapid forcing."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.electromechanical_exciter import (
    ElectromechanicalExciterKind, ElectromechanicalExciterParameters, build_electromechanical_exciter)


def build_ieeet5_template(vf: VarFactory, name: str | None = None,
                           parameters: ElectromechanicalExciterParameters | None = None) -> RmsModelTemplate:
    """Build continuous error reset with parallel rapid forcing.

    The slow path integrates voltage error divided by TRH, without a reset
    deadband. A parallel rapid-action relay selects the forcing limits outside
    the KV voltage band. Bounded reset memory evolves behind that selection.

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
    return build_electromechanical_exciter(vf, 'IEEET5' if name is None else name,
                                          ElectromechanicalExciterKind.INTEGRAL_RESET, parameters)
