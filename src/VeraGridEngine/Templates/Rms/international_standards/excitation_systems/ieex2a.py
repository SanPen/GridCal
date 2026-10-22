# SPDX-License-Identifier: MPL-2.0
"""DC excitation with rate feedback from exciter field-current demand."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, build_dc_exciter


def build_ieex2a_template(vf: VarFactory, name: str | None = None,
                           parameters: DcExciterParameters | None = None) -> RmsModelTemplate:
    """Build dC excitation with rate feedback from exciter field-current demand.

    The stabilizing feedback senses KE*Efd plus excess field voltage from saturation. This is the excitation machine's field-current equivalent; it is distinct from the main generator field current. A lead-lag stage and bounded regulator drive a field integrator with a zero lower stop.

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
    label: str = 'IEEX2A' if name is None else name
    return build_dc_exciter(vf,label,DcExciterKind.TYPE2A,parameters)
