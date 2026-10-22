# SPDX-License-Identifier: MPL-2.0
"""Lag or integral regulation with rapid forcing and an external field clip."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.electromechanical_exciter import (
    ElectromechanicalExciterKind, ElectromechanicalExciterParameters, build_electromechanical_exciter)


def build_ieet5a_template(vf: VarFactory, name: str | None = None,
                           parameters: ElectromechanicalExciterParameters | None = None) -> RmsModelTemplate:
    """Build lag or integral regulation with rapid forcing and an external field clip.

    The normal regulator is KA divided by one plus s times TRH. When TRH is
    zero it becomes KA divided by s, retaining regulator memory. A parallel
    quick-action relay compares sensed voltage with frozen initial voltage,
    independently of the biased normal reference. Delivered field voltage is
    clipped externally; resistive and saturation feedback use internal field
    voltage before this clip, so internal memory may move behind the limit.

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
    return build_electromechanical_exciter(vf, 'IEET5A' if name is None else name,
                                          ElectromechanicalExciterKind.LAG_OR_INTEGRAL, parameters)
