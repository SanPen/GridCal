# SPDX-License-Identifier: MPL-2.0
"""Uncompensated voltage regulator driving a field-controlled DC exciter."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, build_dc_exciter


def build_ieeet1_template(vf: VarFactory, name: str | None = None,
                           parameters: DcExciterParameters | None = None) -> RmsModelTemplate:
    """Build uncompensated voltage regulator driving a field-controlled DC exciter.

    A sensing lag feeds the regulator directly. Supplementary and minimum-excitation voltages enter the same error summation. Regulator limits are fixed; field voltage can have either sign. Four states represent sensing, regulator, field and rate-feedback memory.

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
    label: str = 'IEEET1' if name is None else name
    return build_dc_exciter(vf,label,DcExciterKind.TYPE1,parameters)
