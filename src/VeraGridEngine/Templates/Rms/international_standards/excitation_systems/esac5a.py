# SPDX-License-Identifier: MPL-2.0
"""Brushless rotating excitation with independently supplied regulator power."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, build_dc_exciter


def build_esac5a_template(vf: VarFactory, name: str | None = None,
                           parameters: DcExciterParameters | None = None) -> RmsModelTemplate:
    """Build a simplified brushless excitation system with loaded saturation data.

    A sensed-voltage lag feeds a limited first-order voltage regulator. Regulator
    power comes from an independent source, so its upper and lower capabilities
    remain fixed during a terminal-voltage disturbance. The rotating exciter's
    field circuit integrates regulator forcing minus resistive and saturation
    losses. A zero lower field-voltage stop represents the unidirectional output
    of the rotating rectifier. Loaded saturation samples include the aggregate
    rectifier/loading effects; no additional commutation term is introduced.

    Stabilizing feedback senses the internal exciter field-current equivalent
    ``KE*Efd + Efd*SE(Efd)`` and applies
    ``KF*s*(1+s*TF3)/((1+s*TF1)*(1+s*TF2))``. It does not sense the main
    generator field current or the regulator output. Zero TF2 disables the TF3
    numerator and removes that feedback stage exactly. Zero sensing and regulator lags
    also select exact algebraic stages; the field and primary feedback times
    remain positive. There are five states when all permitted lags are active.

    The five open inputs are sensed voltage, reference voltage, supplementary
    voltage, additive minimum-excitation voltage, and terminal voltage. Terminal
    voltage is retained as an assembly-compatible port and does not scale the
    independent supply. Outputs are field voltage and the pre-regulator demand.
    Initialization balances field losses against regulator forcing, initializes
    zero rate feedback, and derives a consistent voltage reference. Optional
    operating-point field-coefficient and capability calibration is frozen after
    initialization. All voltages and currents use their connected field bases;
    all time constants are in seconds.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique instance label.
    :param parameters: Field/regulator coefficients and loaded saturation samples.
    :return: Native brushless excitation controller.
    :raises ValueError: Invalid coefficients, calibration or feedback structure.
    """
    label: str = 'ESAC5A' if name is None else name
    return build_dc_exciter(vf, label, DcExciterKind.BRUSHLESS, parameters)
