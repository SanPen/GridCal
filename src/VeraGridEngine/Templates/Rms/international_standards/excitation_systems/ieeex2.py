# SPDX-License-Identifier: MPL-2.0
"""Phase-compensated DC excitation with filtered regulator-rate feedback."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, build_dc_exciter


def build_ieeex2_template(vf: VarFactory, name: str | None = None,
                           parameters: DcExciterParameters | None = None) -> RmsModelTemplate:
    """Build phase-compensated DC excitation with filtered regulator-rate feedback.

    A lead-lag stage shapes the voltage error. The bounded regulator output drives a washout followed by a second lag, giving six states when all lags are positive. Fixed regulator limits precede a field circuit with a lower stop at zero.

    Open-circuit saturation is fitted as excess field voltage through two
    specified voltage/factor samples. Optional rheostat calibration is frozen
    at initialization. Sensing and regulator lags may be removed exactly;
    field and feedback time constants remain positive.

    Inputs are compensated voltage, reference, supplementary voltage,
    additive minimum-excitation signal and actual terminal voltage. Outputs
    are field voltage and the regulator's pre-limiter voltage demand.
    All signals use compatible per-unit voltage/field bases and seconds.

    :param vf: Shared native variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical coefficients and calibration settings.
    :return: Native excitation controller with explicit host input ports.
    """
    label: str = 'IEEEX2' if name is None else name
    return build_dc_exciter(vf,label,DcExciterKind.COMPENSATED_TYPE2,parameters)
