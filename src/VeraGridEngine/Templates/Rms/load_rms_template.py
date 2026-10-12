# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType, VarPowerFlowReferenceType, DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from VeraGridEngine.enumerations import VoltageDependentPowerModel

class LoadRmsTemplate(TemplateDefinition):
    """Definition of the editable RMS constant-power load."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create the editable RMS load template definition.

        :param vf: Variable factory used to build the model.
        :return: None.
        """
        properties: list[TemplateProp] = list([
            TemplateProp(name="pl0_init", units="pu", descr="Initial active power at nominal voltage.",
                         tpe=float | None, value=None),
            TemplateProp(name="ql0_init", units="pu", descr="Initial reactive power at nominal voltage.",
                         tpe=float | None, value=None),
            TemplateProp(name="name", units="", descr="Name of the rms model.", tpe=str,
                         value="Load rms template"),
        ])
        TemplateDefinition.__init__(self, vf, properties)

    def eval(self) -> RmsModelTemplate:
        """Build the RMS load with optional user-provided initial powers.

        :return: Constructed RMS load template.
        """
        return get_load_rms_template(
            vfactory=self.vf,
            name=str(self.get_value("name")),
            pl0_init=self.get_value("pl0_init"),
            ql0_init=self.get_value("ql0_init"),
        )


def get_load_rms_template(
        vfactory: VarFactory,
        name: str = "Load rms template",
        pl0_init: float | None = None,
        ql0_init: float | None = None,
) -> RmsModelTemplate:
    """Build the RMS constant-power load model.

    ``Pl0`` and ``Ql0`` remain runtime event parameters. When an optional value
    is unset, the associated Load device supplies its P/Q value through
    ``api_obj_mapping`` and the stored expression is ``Const(None)``. A numeric
    General option omits that mapping and becomes the authoritative baseline
    while preserving event support.

    :param vfactory: Variable factory used by the symbolic model.
    :param name: Model name.
    :param pl0_init: Optional active-power override in p.u.
    :param ql0_init: Optional reactive-power override in p.u.
    :return: RMS load template.
    """
    templ: RmsModelTemplate = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    inputs: list[Var] = list([
        vfactory.add_var("Vm", reference=VarPowerFlowReferenceType.Vm),
        vfactory.add_var("Va", reference=VarPowerFlowReferenceType.Va)
    ])

    Pl0: Var = vfactory.add_var("Pl0")
    Ql0: Var = vfactory.add_var("Ql0")
    Pl: Var = vfactory.add_var("Pl", reference=VarPowerFlowReferenceType.P)
    Ql: Var = vfactory.add_var("Ql", reference=VarPowerFlowReferenceType.Q)

    block: Block = Block()

    # Each event parameter has exactly one initial source. Without an explicit
    # option the Load device supplies it through api_obj_mapping; otherwise the
    # selected numeric literal is stored directly.
    pl0_expression: Expr
    ql0_expression: Expr
    if pl0_init is None:
        pl0_expression = vfactory.add_const(None)
    else:
        pl0_expression = vfactory.add_const(pl0_init)
    if ql0_init is None:
        ql0_expression = vfactory.add_const(None)
    else:
        ql0_expression = vfactory.add_const(ql0_init)
    block.event_dict[Pl0] = pl0_expression
    block.event_dict[Ql0] = ql0_expression

    block.algebraic_vars = list([Pl, Ql])
    block.algebraic_eqs = list([Pl - Pl0, Ql - Ql0])

    block.in_vars = inputs
    block.out_vars = list([Pl, Ql])

    block.name = name

    templ.block.children.append(block)

    templ.block.external_mapping = dict({
        VarPowerFlowReferenceType.Va: inputs[1],
        VarPowerFlowReferenceType.Vm: inputs[0],
        VarPowerFlowReferenceType.P: Pl,
        VarPowerFlowReferenceType.Q: Ql
    })

    # The static Load.P/Q values establish the default baseline, while the
    # event_dict ownership above keeps both references mutable. An explicit
    # template option remains authoritative and therefore omits only that
    # variable's device mapping.
    block.api_obj_mapping = dict()
    if pl0_init is None:
        block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0] = Pl0
    else:
        pass
    if ql0_init is None:
        block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0] = Ql0
    else:
        pass
    templ.block.in_vars = inputs
    templ.block.out_vars = list([Pl, Ql])

    return templ


def get_voltage_dependent_power_rms_template(
        vfactory: VarFactory,
        voltage_model: VoltageDependentPowerModel,
        name: str = "Voltage-dependent power RMS template",
) -> RmsModelTemplate:
    """Build a static injection initialized from its load-flow power.

    Retaining ``P0``, ``Q0`` and ``V0`` reproduces either a voltage-aligned
    constant-current source, where terminal power scales with ``Vm/V0``, or a
    constant shunt admittance, where it scales with ``(Vm/V0)^2``.  The model
    therefore remains completely determined by the exported DGS operating
    point and does not require PowerFactory at run time.

    :param vfactory: Variable factory owned by the imported circuit.
    :param voltage_model: Physical voltage dependency to reproduce.
    :param name: Human-readable model name shown in the dynamic editor.
    :return: RMS template implementing the selected initialized power law.
    """
    template: RmsModelTemplate = RmsModelTemplate()
    template.tpe = DeviceType.LoadDevice
    template.name = name

    # The bus voltage is supplied by the normal RMS network connection path.
    voltage_magnitude: Var = vfactory.add_var(
        "Vm",
        reference=VarPowerFlowReferenceType.Vm,
    )
    voltage_angle: Var = vfactory.add_var(
        "Va",
        reference=VarPowerFlowReferenceType.Va,
    )

    # These retained references are sampled after the load-flow operating
    # point is closed, matching PowerFactory's Yload = I(ldf) / U(ldf).
    initial_active_power: Var = vfactory.add_var("P0")
    initial_reactive_power: Var = vfactory.add_var("Q0")
    initial_voltage_magnitude: Var = vfactory.add_var("V0")
    active_power: Var = vfactory.add_var(
        "P",
        reference=VarPowerFlowReferenceType.P,
    )
    reactive_power: Var = vfactory.add_var(
        "Q",
        reference=VarPowerFlowReferenceType.Q,
    )
    normalized_voltage: Expr = voltage_magnitude / initial_voltage_magnitude
    voltage_power_factor: Expr
    if voltage_model == VoltageDependentPowerModel.ConstantCurrent:
        # With a current vector aligned to the terminal-voltage angle, both P
        # and Q scale linearly with voltage magnitude while their ratio stays
        # fixed at the solved operating point.
        voltage_power_factor = normalized_voltage
    else:
        # A constant admittance produces complex power proportional to the
        # squared terminal-voltage magnitude.
        voltage_power_factor = normalized_voltage * normalized_voltage

    # Event parameters retain the initialized operating point while still
    # allowing the standard RMS event machinery to alter load references.
    load_block: Block = Block(
        name=name,
        in_vars=list([voltage_magnitude, voltage_angle]),
        out_vars=list([active_power, reactive_power]),
        algebraic_vars=list([active_power, reactive_power]),
        algebraic_eqs=list([
            active_power - initial_active_power * voltage_power_factor,
            reactive_power - initial_reactive_power * voltage_power_factor,
        ]),
        event_dict=dict([
            (initial_active_power, active_power),
            (initial_reactive_power, reactive_power),
            (initial_voltage_magnitude, voltage_magnitude),
        ]),
        external_mapping=dict([
            (VarPowerFlowReferenceType.Va, voltage_angle),
            (VarPowerFlowReferenceType.Vm, voltage_magnitude),
            (VarPowerFlowReferenceType.P, active_power),
            (VarPowerFlowReferenceType.Q, reactive_power),
        ]),
    )
    template.block = load_block
    return template
