# SPDX-License-Identifier: MPL-2.0
"""DC excitation with terminal-voltage capability and a high-value excitation gate."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, build_dc_exciter


def build_esdc2a_template(vf: VarFactory, name: str | None = None,
                           parameters: DcExciterParameters | None = None) -> RmsModelTemplate:
    """Build dC excitation with terminal-voltage capability and a high-value excitation gate.

    A high-value gate selects between the phase-compensated voltage demand and the minimum-excitation input. Live terminal voltage scales both regulator limits; the compensated sensing input stays separate. The field voltage has no additional zero floor in this structure.

    Quadratic excess-field saturation and field-voltage rate feedback close
    the exciter loop. Optional rheostat calibration is frozen at initialization;
    automatic capability uses the specified high-voltage saturation sample.
    Positive lag stages own states; zero lags become algebraic equations.

    Inputs are compensated voltage, voltage reference, stabilizing voltage,
    minimum-excitation signal and actual terminal-voltage magnitude. Outputs
    are field voltage and pre-limiter regulator demand. Voltage and field signals
    use their compatible per-unit bases; time constants use seconds.

    :param vf: Shared native symbol factory.
    :param name: Optional unique instance label.
    :param parameters: Physical coefficients and operating-point calibration.
    :return: Connected internal DAE with open host input ports.
    """
    label: str = 'ESDC2A' if name is None else name
    return build_dc_exciter(vf,label,DcExciterKind.DC2A,parameters)
