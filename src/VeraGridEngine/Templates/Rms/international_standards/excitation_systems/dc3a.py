# SPDX-License-Identifier: MPL-2.0
"""Motor-driven rheostat excitation with rapid contacts and a bounded field circuit."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.electromechanical_exciter import (
    ElectromechanicalExciterKind, ElectromechanicalExciterParameters, build_electromechanical_exciter,
)


def build_dc3a_template(vf: VarFactory, name: str | None = None,
                       parameters: ElectromechanicalExciterParameters | None = None) -> RmsModelTemplate:
    """Build motor-operated voltage regulation with parallel fast forcing contacts.

    Filtered voltage error drives a bounded rheostat integrator at a rate
    proportional to the forcing range, normalized by contact threshold and
    motor travel time. Beyond the positive or negative contact threshold,
    a parallel fast path immediately selects the corresponding forcing limit.
    At either threshold exactly, the rheostat setting remains selected.

    Selected forcing supplies a rotating field circuit with linear resistance
    and quadratic saturation losses. Its lower voltage stop blocks outward
    motion while allowing immediate recovery under positive net forcing.
    Rheostat memory continues to follow its own error and travel stops while
    the rapid path acts. The field stop does not clamp that separate memory.

    Inputs are sensed voltage, voltage reference, supplementary voltage,
    additive minimum-excitation voltage and an unused terminal-voltage supply
    port. Outputs are field voltage and selected regulator forcing. Voltages
    use compatible per-unit bases, time constants are seconds and saturation
    factors are dimensionless. Two physical states store rheostat position and
    field voltage; positive sensing time adds a third. Zero sensing time is an
    exact algebraic reduction. Initialization balances field losses at the
    actual initial field voltage and places that forcing in rheostat memory.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Explicit rheostat, contact, field and saturation settings.
    :return: Native bounded rheostat excitation controller.
    :raises ValueError: Invalid physical coefficients or undefined calibration.
    """
    return build_electromechanical_exciter(vf, 'DC3A' if name is None else name,
        ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET, parameters)
