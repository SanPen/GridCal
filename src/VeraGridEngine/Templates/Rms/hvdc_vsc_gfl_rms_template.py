# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Standalone grid-following VSC models for RMS HVDC studies."""

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.vsc_gfl import VscGflBuild
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic.block import Block, Var
from VeraGridEngine.enumerations import ConverterControlType, VarPowerFlowReferenceType


class HvdcVscGflRmsTemplate(TemplateDefinition):
    """Editable template definition for the standalone HVDC GFL VSC model."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Define the structural inputs exposed by the dynamic editor.

        :param vf: Variable factory that will own the generated RMS variables.
        :return: None.
        """
        super().__init__(
            vf,
            params=list((
                TemplateProp(
                    name="control1",
                    units="",
                    descr="Active-axis control mode (Vm_dc, Pdc, or Pac).",
                    tpe=ConverterControlType,
                    value=ConverterControlType.Vm_dc,
                    allowed_values=(
                        ConverterControlType.Vm_dc,
                        ConverterControlType.Pdc,
                        ConverterControlType.Pac,
                    ),
                ),
                TemplateProp(
                    name="control2",
                    units="",
                    descr="Reactive-axis control mode (Qac or Vm_ac).",
                    tpe=ConverterControlType,
                    value=ConverterControlType.Qac,
                    allowed_values=(
                        ConverterControlType.Qac,
                        ConverterControlType.Vm_ac,
                    ),
                ),
                TemplateProp(
                    name="cdc",
                    units="p.u.",
                    descr="DC-link capacitance used by the RMS voltage state.",
                    tpe=float,
                    value=0.40,
                ),
                TemplateProp(
                    name="name",
                    units="",
                    descr="Name of the RMS model.",
                    tpe=str,
                    value="HVDC GFL VSC",
                ),
            )),
        )

    def eval(self) -> RmsModelTemplate:
        """Build the HVDC VSC using the current editor property values.

        :return: Configured standalone HVDC GFL VSC RMS template.
        """
        control1: ConverterControlType = self.get_value("control1")
        control2: ConverterControlType = self.get_value("control2")
        cdc: float = self.get_value("cdc")
        name: str = self.get_value("name")

        return build_hvdc_vsc_gfl_rms(
            vfactory=self.vf,
            name=name,
            control1=control1,
            control2=control2,
            cdc=cdc,
        )


def _set_parameter_value(block: Block, variable_name: str, value: float, vf: VarFactory) -> None:
    """Set a static or event parameter without changing its ownership.

    :param block: Root of the symbolic block tree to update.
    :param variable_name: Exact parameter name to update.
    :param value: Real numeric default assigned to the parameter.
    :param vf: Factory used to create the symbolic constant.
    :return: None.
    :raises KeyError: If the block has no matching parameter.
    """
    for owner in block.get_all_blocks():
        for destination in (owner.parameters, owner.event_dict):
            for variable in destination:
                if variable.name == variable_name:
                    destination[variable] = vf.add_const(value)
                    return
    raise KeyError(f"The VSC GFL model has no parameter named '{variable_name}'")


def build_hvdc_vsc_gfl_rms(
        vfactory: VarFactory,
        name: str = "HVDC GFL VSC",
        control1: ConverterControlType = ConverterControlType.Vm_dc,
        control2: ConverterControlType = ConverterControlType.Qac,
        cdc: float = 0.40,
) -> RmsModelTemplate:
    """Build a complete controlled VSC with an RMS DC-link capacitor.

    The model belongs directly to a :class:`VSC` device. Its AC terminal uses
    ``Vm/Va`` and its DC terminal uses ``Vdc``. A physical coupling transformer
    must use the ordinary transformer RMS template rather than hosting converter
    controls.

    :param vfactory: Variable factory used to construct the symbolic model.
    :param name: Catalog and block display name.
    :param control1: Active-axis control mode (``Vm_dc``, ``Pdc``, or ``Pac``).
    :param control2: Reactive-axis control mode (``Qac`` or ``Vm_ac``).
    :param cdc: DC-link capacitance in p.u.
    :return: Complete reusable RMS VSC template.
    """
    template: RmsModelTemplate = VscGflBuild(
        vfactory=vfactory,
        name=name,
        control1=control1,
        control2=control2,
    )
    template.name = name
    template.block.name = name

    vdc: Var | None = template.block.external_mapping.get(VarPowerFlowReferenceType.Vdc, None)
    if vdc is None:
        raise ValueError("The HVDC GFL VSC template must expose its Vdc variable")
    else:
        pass

    # Internal symbols must remain valid identifiers independently of the
    # user-facing block name, which may legitimately contain spaces.
    dvdc_dt: Var = vfactory.add_diff_var("dVdc_dt", base_var=vdc)
    cdc_parameter: Var = vfactory.add_var("Cdc")

    # Pf_dc + Pt_ac - Ploss - Cdc*Vdc*dVdc/dt = 0.
    template.block.algebraic_eqs[0] -= cdc_parameter * vdc * dvdc_dt
    template.block.diff_vars.append(dvdc_dt)
    template.block.diff_init_eqs[dvdc_dt] = vfactory.add_const(0.0)
    template.block.event_dict[cdc_parameter] = vfactory.add_const(float(cdc))

    # Defaults validated by the point-to-point HVDC RMS example. The physical
    # transformer carries station resistance, so the converter interface is
    # lossless and does not duplicate that network loss.
    defaults: tuple[tuple[str, float], ...] = (
        ("Kp_vdc", 0.20),
        ("Ki_vdc", 1.00),
        ("Kp_icl", 0.20),
        ("Ki_icl", 5.00),
        ("Kp_pol", 0.02),
        ("Ki_pol", 0.10),
        ("R", 0.0),
    )
    variable_name: str
    value: float
    for variable_name, value in defaults:
        _set_parameter_value(template.block, variable_name, value, vfactory)

    return template


def get_hvdc_vdc_q_vsc_rms(
        vfactory: VarFactory,
        name: str = "HVDC GFL VSC - Vdc/Q",
) -> RmsModelTemplate:
    """Build the DC-voltage/reactive-power controlling HVDC terminal."""
    return build_hvdc_vsc_gfl_rms(
        vfactory=vfactory,
        name=name,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
    )


def get_hvdc_pdc_q_vsc_rms(
        vfactory: VarFactory,
        name: str = "HVDC GFL VSC - Pdc/Q",
) -> RmsModelTemplate:
    """Build the DC-power/reactive-power controlling HVDC terminal."""
    return build_hvdc_vsc_gfl_rms(
        vfactory=vfactory,
        name=name,
        control1=ConverterControlType.Pdc,
        control2=ConverterControlType.Qac,
    )
