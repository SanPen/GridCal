# SPDX-License-Identifier: MPL-2.0
"""Field-controlled excitation with external output-voltage limits and internal rate feedback."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, build_dc_exciter


def build_ieet1a_template(vf: VarFactory, name: str | None = None,
                           parameters: DcExciterParameters | None = None) -> RmsModelTemplate:
    """Build field-controlled rotating excitation with a separately limited output.

    Instantaneous sensed-voltage error and additive supplementary signals feed a
    bounded first-order regulator. Its output drives an internal field integrator.
    An external limiter clips the delivered field voltage between EFDMIN and E2;
    E2 also defines the upper saturation sample. Resistive and quadratic excess-
    field losses consume the delivered, limited voltage. The stabilizing loop
    senses internal integrator memory before that output limiter and applies
    ``KF*s/(1+s*TF)``. Internal memory and delivered voltage remain distinct when
    an output bound is active; the external clip does not freeze internal memory.

    Positive regulator time gives three states: regulator output, internal field
    memory and rate-feedback memory. A zero regulator time produces an exact
    algebraic regulator and leaves two states. There is no sensing lag or phase
    compensator. A consistent initial point has internal and delivered field
    voltage equal and within the output limits, balanced regulator forcing and
    zero rate feedback. Optional field-resistance/capability calibration is frozen
    at initialization.

    Inputs are sensed voltage, reference voltage, supplementary voltage, additive
    minimum-excitation voltage and terminal voltage. The fixed regulator supply
    does not use the last port. Outputs are delivered field voltage and pre-
    regulator voltage demand. Voltages use connected per-unit bases, time
    constants are seconds, and saturation samples describe excess field voltage.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Regulator, field and saturation coefficients; field_min and e2 set output limits.
    :return: Native field-limited rotating-exciter controller.
    :raises ValueError: Invalid coefficient domains or undefined calibration.
    """
    return build_dc_exciter(vf, 'IEET1A' if name is None else name, DcExciterKind.LIMITED_TYPE1, parameters)
