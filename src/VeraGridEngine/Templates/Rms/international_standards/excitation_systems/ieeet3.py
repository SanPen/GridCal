# SPDX-License-Identifier: MPL-2.0
"""Field excitation with compound-transformer loading and an explicit forcing-capability location."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.thevenin_exciter import CompoundCapabilityLocation, TheveninExciterParameters, build_thevenin_exciter


def build_ieeet3_template(vf: VarFactory, name: str | None = None,
                           parameters: TheveninExciterParameters | None = None) -> RmsModelTemplate:
    """Build loaded compound-transformer excitation with separately regulated field forcing.

    Total regulator-plus-transformer forcing is bounded before the field circuit.
    The transformer combines terminal voltage and quadrature-scaled outgoing
    stator current as a phasor. Available rectified voltage follows the square
    root of potential squared minus squared normalized field-current loading,
    falling exactly to zero when loading exceeds available potential. The direct
    radicand expression remains finite during a terminal/supply collapse.

    A limited voltage regulator acts on compensated-voltage error plus additive
    supplementary excitation, opposed by delivered-field washout. A distinct
    field circuit integrates total forcing minus linear field loss and prevents
    negative field voltage. There is no magnetic-saturation curve, transport
    delay or inferred automatic transformer design calibration in this model.

    Inputs are sensed voltage, voltage reference, supplementary voltage,
    terminal phasor real/imaginary components, outgoing stator-current
    real/imaginary components and normalized field current. Output is field
    voltage; the host owns current/field bases. Four dynamic memories exist
    with positive sensing/regulator lags; zero permitted lags are algebraic.
    Initialization uses actual transformer loading and required field forcing
    to determine a consistent regulator output/reference. Times use seconds.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical transformer, regulator and field coefficients.
    :return: Native compound-transformer excitation controller.
    :raises ValueError: Invalid physical domains or forcing capabilities.
    """
    label: str = 'IEEET3' if name is None else name
    return build_thevenin_exciter(vf,label,CompoundCapabilityLocation.TOTAL_FORCING,parameters)
