# SPDX-License-Identifier: MPL-2.0
"""DC excitation with a high-value minimum-excitation gate and nonnegative field voltage."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, build_dc_exciter


def build_esdc1a_template(vf: VarFactory, name: str | None = None,
                           parameters: DcExciterParameters | None = None) -> RmsModelTemplate:
    """Build dC excitation with a high-value minimum-excitation gate and nonnegative field voltage.

    The minimum-excitation input competes with the phase-compensated voltage demand before regulator gain. Regulator capability has fixed bounds. The field circuit has a lower stop at zero, so negative forcing can discharge the field without driving its voltage state below that stop.

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
    label: str = 'ESDC1A' if name is None else name
    return build_dc_exciter(vf,label,DcExciterKind.DC1A,parameters)
