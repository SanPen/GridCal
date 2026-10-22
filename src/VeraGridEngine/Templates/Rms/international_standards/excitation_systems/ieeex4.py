# SPDX-License-Identifier: MPL-2.0
"""Range-normalized reset with parallel rapid forcing."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.electromechanical_exciter import (
    ElectromechanicalExciterKind, ElectromechanicalExciterParameters, build_electromechanical_exciter)


def build_ieeex4_template(vf: VarFactory, name: str | None = None,
                           parameters: ElectromechanicalExciterParameters | None = None) -> RmsModelTemplate:
    """Build range-normalized reset with parallel rapid forcing.

    A first-order sensing lag feeds a reset integrator whose slope is the
    regulator range times clipped voltage error divided by KV and TRH. Rapid
    forcing selects the ceiling at error greater than or equal to KV and the
    floor at error less than or equal to negative KV. Zero sensing time gives
    exact instantaneous sensing, removing that state.

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
    return build_electromechanical_exciter(vf, 'IEEEX4' if name is None else name,
                                          ElectromechanicalExciterKind.NORMALIZED_RESET, parameters)
