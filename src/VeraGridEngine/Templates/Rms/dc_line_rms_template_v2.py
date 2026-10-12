# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""RMS DC-line model with an explicit current state."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from VeraGridEngine.enumerations import (
    DeviceType,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)


class DcLineRmsTemplateV2(TemplateDefinition):
    """Editable definition of the explicit-state R-L DC-line model."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Define the structural options exposed by the dynamic editor.

        The static :class:`DcLine` device provides the resistance through
        ``dc_line_r_pu`` when the template is assigned. Inductance belongs to
        ``event_dict`` and is edited as a dynamic parameter after construction,
        rather than being passed as a structural builder option.

        :param vf: Variable factory that owns the generated RMS variables.
        :return: None.
        """
        super().__init__(
            vf,
            params=list((
                TemplateProp(
                    name="name",
                    units="",
                    descr="Name of the RMS DC-line model.",
                    tpe=str,
                    value="DC line",
                ),
            )),
        )

    def eval(self) -> RmsModelTemplate:
        """Build the DC-line model from the current editor property values.

        :return: Configured explicit-state RMS DC-line template.
        """
        name: str = self.get_value("name")
        return build_dc_line_rms_v2(
            vfactory=self.vf,
            name=name,
        )


def build_dc_line_rms_v2(
        vfactory: VarFactory,
        name: str = "DC line",
) -> RmsModelTemplate:
    """Build a series R-L DC line with current as an ordinary RMS state.

    The state equation is
    ``dI_dc/dt = (Vdc_f - Vdc_t - R_dc I_dc) / L_dc``. Terminal
    powers follow the branch sign convention ``Pf = Vdc_f I_dc`` and
    ``Pt = -Vdc_t I_dc``.

    The root block owns the device interface. A child block owns the equations,
    parameter declarations and static-parameter mapping so every mapping target
    belongs to the same block that declares it. This keeps the model visible and
    editable in the Dynamic Editor without requiring equation decomposition on
    open.

    :param vfactory: Variable factory used to construct the symbolic model.
    :param name: Root block and template display name.
    :return: Reusable RMS template for a static DC-line device.
    """
    # Create every interface variable with its authoritative power-flow
    # reference. These references drive network coupling, plotting and root
    # interface reconstruction after serialization.
    vdc_from: Var = vfactory.add_var("Vdcf", reference=VarPowerFlowReferenceType.Vmf)
    vdc_to: Var = vfactory.add_var("Vdct", reference=VarPowerFlowReferenceType.Vmt)
    current_from: Var = vfactory.add_var("If_dc", reference=VarPowerFlowReferenceType.If_dc)
    power_from: Var = vfactory.add_var("Pf", reference=VarPowerFlowReferenceType.Pf)
    power_to: Var = vfactory.add_var("Pt", reference=VarPowerFlowReferenceType.Pt)

    resistance_parameter: Var = vfactory.add_var("r_dc")
    inductance_parameter: Var = vfactory.add_var("l_dc")
    current_rhs: Expr = (
        vdc_from - vdc_to - resistance_parameter * current_from
    ) / inductance_parameter

    # Keep all physical equations in one visible child while exposing its
    # electrical terminals at the root level for device-to-bus connections.
    equations_block: Block = Block(
        name="R-L DC line equations",
        # Resistance has no template fallback: the RMS assembler must provide
        # the static DcLine.R_corrected value through api_obj_mapping. A null
        # constant registers the required compile-time parameter without
        # inventing an independent dynamic-model value.
        parameters=dict(((resistance_parameter, vfactory.add_const(None)),)),
        # Keep the static-device source beside its parameter declaration. The
        # recursive RMS mapper visits this child and injects DcLine.R_corrected
        # without requiring the root to duplicate a child-owned mapping.
        api_obj_mapping=dict((
            (ParamPowerFlowReferenceType.dc_line_r_pu, resistance_parameter),
        )),
        # Inductance has no static-device counterpart. Keep it as an editable
        # runtime parameter whose default belongs exclusively to this model.
        event_dict=dict(((inductance_parameter, vfactory.add_const(0.05)),)),
        state_vars=list((current_from,)),
        state_eqs=list((current_rhs,)),
        algebraic_vars=list((power_from, power_to)),
        algebraic_eqs=list((
            power_from - vdc_from * current_from,
            # Keep the residual in ``defined variable - expression`` form so
            # the graphical equation decomposer identifies Pt as an output.
            power_to - ((-vdc_to) * current_from),
        )),
        # If_dc, Pf and Pt are seeded directly from the solved power flow.
        # Explicit initialization equations would overwrite those authoritative
        # values and therefore must remain empty for this device model.
        init_eqs=dict(),
        in_vars=list((vdc_from, vdc_to)),
        # The current remains an explicit state and a power-flow mapping, but
        # no other RMS device consumes it as a block signal. Only terminal
        # powers therefore belong to the visible output contract.
        out_vars=list((power_from, power_to)),
    )
    root_block: Block = Block(
        name=name,
        children=list((equations_block,)),
        in_vars=list((vdc_from, vdc_to)),
        out_vars=list((power_from, power_to)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Vmf, vdc_from),
            (VarPowerFlowReferenceType.Vmt, vdc_to),
            (VarPowerFlowReferenceType.If_dc, current_from),
            (VarPowerFlowReferenceType.Pf, power_from),
            (VarPowerFlowReferenceType.Pt, power_to),
        )),
    )

    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.DCLineDevice
    template.block = root_block
    return template
