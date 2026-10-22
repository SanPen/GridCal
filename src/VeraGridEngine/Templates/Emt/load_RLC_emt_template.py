# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Phase-selective EMT templates for shunt R/L/C devices."""

import uuid
import numpy as np

from typing import Dict, List, Tuple

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic.block import Block, Expr, Var
from VeraGridEngine.Utils.Symbolic.symbolic import max
from VeraGridEngine.enumerations import (BlockType, DeviceType, ParamPowerFlowReferenceType,
                                         ShuntConnectionType, VarPowerFlowReferenceType)


def _get_power_conversion_voltage_squared(vf: VarFactory, pf_vm_var: Var) -> Expr:
    """Return the voltage square used to convert shunt power into R/L/C.

    An energized power-flow solution supplies the operating voltage required to
    preserve the solved shunt power. A deliberately dead island instead reports
    zero voltage, although the static power fields still describe the component
    at nominal voltage. In that case, use the nominal one-per-unit voltage so a
    finite physical component is created before the island is energized.

    :param vf: Variable factory owning the symbolic constants.
    :param pf_vm_var: Power-flow voltage magnitude in per unit.
    :return: Squared effective voltage magnitude for the power conversion.
    """
    voltage_threshold: Expr = vf.add_const(1.0e-9)
    nominal_voltage: Expr = vf.add_const(1.0)

    # The comparison is converted to a numerical selector because the symbolic
    # runtime must evaluate the same expression in interpreted and JIT modes.
    energized_selector: Expr = (pf_vm_var > voltage_threshold).to_expression()
    effective_voltage: Expr = (
        energized_selector * pf_vm_var
        + (nominal_voltage - energized_selector) * nominal_voltage
    )
    return effective_voltage * effective_voltage


def _get_active_phases(phA: bool, phB: bool, phC: bool) -> List[str]:
    """Return the enabled phase labels in strict A-B-C order.

    :param phA: True when phase A is active.
    :param phB: True when phase B is active.
    :param phC: True when phase C is active.
    :return: Ordered list with the active phase labels.
    :raises ValueError: If no phase is enabled.
    """
    # The EMT assembler expects deterministic ordering because all variable,
    # equation, and mapping indices are consumed positionally downstream.
    active_phases: List[str] = list()

    if phA:
        active_phases.append("A")
    else:
        active_phases = active_phases

    if phB:
        active_phases.append("B")
    else:
        active_phases = active_phases

    if phC:
        active_phases.append("C")
    else:
        active_phases = active_phases

    # An empty phase set cannot be assembled into a coherent EMT block because
    # there would be no unknowns or equations to bind to a bus.
    if len(active_phases) == 0:
        raise ValueError("At least one phase must be enabled for an EMT shunt template")
    else:
        return active_phases


def _get_phase_count_name(base_name: str, phase_count: int, requested_name: str | None) -> str:
    """Resolve a template name whose suffix matches the active phase count.

    :param base_name: Base prefix without the phase-count suffix.
    :param phase_count: Number of active phases.
    :param requested_name: Optional caller-provided name.
    :return: Name with a ``1ph``, ``2ph`` or ``3ph`` suffix.
    """
    # The template name is part of the broader EMT workflow because it feeds the
    # generated symbolic variable names and device-level metadata.
    suffix: str = f"_{phase_count}ph"

    if requested_name is None:
        resolved_name: str = base_name + suffix
    else:
        resolved_name = requested_name

        if resolved_name.endswith("_1ph"):
            resolved_name = resolved_name[:-4] + suffix
        else:
            if resolved_name.endswith("_2ph"):
                resolved_name = resolved_name[:-4] + suffix
            else:
                if resolved_name.endswith("_3ph"):
                    resolved_name = resolved_name[:-4] + suffix
                else:
                    resolved_name = resolved_name + suffix

    return resolved_name


def _get_voltage_reference(phase_label: str) -> VarPowerFlowReferenceType:
    """Return the EMT voltage reference enum for one phase.

    :param phase_label: Phase label ``A``, ``B`` or ``C``.
    :return: Matching external voltage reference enum.
    """
    if phase_label == "A":
        reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.v_A
    else:
        if phase_label == "B":
            reference = VarPowerFlowReferenceType.v_B
        else:
            if phase_label == "C":
                reference = VarPowerFlowReferenceType.v_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")

    return reference


def _get_current_reference(phase_label: str) -> VarPowerFlowReferenceType:
    """Return the EMT injected-current reference enum for one phase.

    :param phase_label: Phase label ``A``, ``B`` or ``C``.
    :return: Matching external current reference enum.
    """
    if phase_label == "A":
        reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.i_A
    elif phase_label == "B":
        reference = VarPowerFlowReferenceType.i_B
    elif phase_label == "C":
        reference = VarPowerFlowReferenceType.i_C
    else:
        raise ValueError(f"Unsupported phase label '{phase_label}'")

    return reference


RESISTANCE_REFERENCES = {
    "A": VarPowerFlowReferenceType.R_A,
    "B": VarPowerFlowReferenceType.R_B,
    "C": VarPowerFlowReferenceType.R_C,
}

INDUCTANCE_REFERENCES = {
    "A": VarPowerFlowReferenceType.L_A,
    "B": VarPowerFlowReferenceType.L_B,
    "C": VarPowerFlowReferenceType.L_C,
}

CAPACITANCE_REFERENCES = {
    "A": VarPowerFlowReferenceType.C_A,
    "B": VarPowerFlowReferenceType.C_B,
    "C": VarPowerFlowReferenceType.C_C,
}


def _get_pl0_reference(phase_label: str) -> ParamPowerFlowReferenceType:
    """Return the active-power parameter reference for one phase.

    :param phase_label: Phase label ``A``, ``B`` or ``C``.
    :return: Matching API parameter enum.
    """
    if phase_label == "A":
        reference: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Pl0_A
    else:
        if phase_label == "B":
            reference = ParamPowerFlowReferenceType.Pl0_B
        else:
            if phase_label == "C":
                reference = ParamPowerFlowReferenceType.Pl0_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")

    return reference


def _get_ql0_reference(phase_label: str) -> ParamPowerFlowReferenceType:
    """Return the reactive-power parameter reference for one phase.

    :param phase_label: Phase label ``A``, ``B`` or ``C``.
    :return: Matching API parameter enum.
    """
    if phase_label == "A":
        reference: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Ql0_A
    else:
        if phase_label == "B":
            reference = ParamPowerFlowReferenceType.Ql0_B
        else:
            if phase_label == "C":
                reference = ParamPowerFlowReferenceType.Ql0_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")

    return reference


def _build_external_mapping(
    voltage_vars: Dict[str, Var],
    current_vars: Dict[str, Var],
    neutral_voltage_var: Var | None = None,
    neutral_current_var: Var | None = None,
    voltage_derivative_vars: Dict[str, Var] | None = None,
    neutral_voltage_derivative_var: Var | None = None,
) -> Dict[VarPowerFlowReferenceType, Var | None]:
    """Build a full external mapping with inactive phases set to ``None``.

    :param voltage_vars: Active terminal voltages keyed by phase label.
    :param current_vars: Active injected currents keyed by phase label.
    :param neutral_voltage_var: Optional neutral terminal voltage.
    :param neutral_current_var: Optional neutral injected current.
    :param voltage_derivative_vars: Optional active voltage-derivative vars keyed by phase label.
    :param neutral_voltage_derivative_var: Optional neutral voltage-derivative var.
    :return: Full EMT external mapping for the shunt template.
    """
    derivative_vars = dict() if voltage_derivative_vars is None else voltage_derivative_vars

    # The EMT connection workflow uses a fixed enum contract, so inactive phases
    # must still appear explicitly with ``None`` entries.
    mapping: Dict[VarPowerFlowReferenceType, Var | None] = dict({
        VarPowerFlowReferenceType.v_N: neutral_voltage_var,
        VarPowerFlowReferenceType.v_A: voltage_vars.get("A", None),
        VarPowerFlowReferenceType.v_B: voltage_vars.get("B", None),
        VarPowerFlowReferenceType.v_C: voltage_vars.get("C", None),
        VarPowerFlowReferenceType.P: None,
        VarPowerFlowReferenceType.Q: None,
        VarPowerFlowReferenceType.P_N: None,
        VarPowerFlowReferenceType.Q_N: None,
        VarPowerFlowReferenceType.P_A: None,
        VarPowerFlowReferenceType.Q_A: None,
        VarPowerFlowReferenceType.P_B: None,
        VarPowerFlowReferenceType.Q_B: None,
        VarPowerFlowReferenceType.P_C: None,
        VarPowerFlowReferenceType.Q_C: None,
        VarPowerFlowReferenceType.i_N: neutral_current_var,
        VarPowerFlowReferenceType.i_A: current_vars.get("A", None),
        VarPowerFlowReferenceType.i_B: current_vars.get("B", None),
        VarPowerFlowReferenceType.i_C: current_vars.get("C", None),
        VarPowerFlowReferenceType.phi_v: None,
        VarPowerFlowReferenceType.phi: None,
        VarPowerFlowReferenceType.Vpk: None,
        VarPowerFlowReferenceType.Ipk: None,
        VarPowerFlowReferenceType.d_v_N: neutral_voltage_derivative_var,
        VarPowerFlowReferenceType.d_v_A: derivative_vars.get("A", None),
        VarPowerFlowReferenceType.d_v_B: derivative_vars.get("B", None),
        VarPowerFlowReferenceType.d_v_C: derivative_vars.get("C", None),
    })

    return mapping


def get_ground_emt_template(vf: VarFactory, name: str = "ground_emt") -> EmtModelTemplate:
    """Build one ideal EMT ground block for an internal neutral node.

    The block clamps its input node voltage to zero and exposes the corresponding
    grounding current as one output so a parent template can close the neutral KCL.

    :param vf: EMT variable factory.
    :param name: Symbolic model name.
    :return: Ideal ground EMT template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name

    neutral_voltage_var: Var = vf.add_var(f"v_N")
    ground_current_var: Var = vf.add_var(f"i_N")

    templ.block.in_vars = [neutral_voltage_var]
    templ.block.algebraic_vars = [ground_current_var]
    templ.block.algebraic_eqs = [neutral_voltage_var]
    templ.block.init_eqs[ground_current_var] = vf.add_const(0.0)
    templ.block.out_vars = [ground_current_var]
    return templ


# ---
class GroundingLinkEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="include_r", units="", descr="Include the resistor branch.", tpe=bool, value=False),
                TemplateProp(name="include_l", units="", descr="Include the inductor branch.", tpe=bool, value=False),
                TemplateProp(name="include_c", units="", descr="Include the capacitor branch.", tpe=bool, value=False),
                TemplateProp(name="solid_connection", units="", descr="Solid (direct) grounding connection.", tpe=bool, value=False),
                TemplateProp(name="nested", units="", descr="Whether the template is nested inside another template.", tpe=bool, value=False),
                TemplateProp(name="direct_r_value", units="Ohm", descr="Direct resistance value.", tpe=float, value=None),
                TemplateProp(name="direct_l_value", units="H", descr="Direct inductance value.", tpe=float, value=None),
                TemplateProp(name="direct_c_value", units="F", descr="Direct capacitance value.", tpe=float, value=None),
                TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str, value="grounding_link_emt"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        include_r: bool = self.get_value("include_r")
        include_l: bool = self.get_value("include_l")
        include_c: bool = self.get_value("include_c")
        solid_connection: bool = self.get_value("solid_connection")
        nested: bool = self.get_value("nested")
        direct_r_value: float | None = self.get_value("direct_r_value")
        direct_l_value: float | None = self.get_value("direct_l_value")
        direct_c_value: float | None = self.get_value("direct_c_value")
        name: str = self.get_value("name")

        return get_grounding_link_emt_template(
            self.vf, include_r, include_l, include_c, solid_connection, nested,
            direct_r_value, direct_l_value, direct_c_value, name,
        )


def get_grounding_link_emt_template(
    vf: VarFactory,
    include_r: bool,
    include_l: bool,
    include_c: bool,
    solid_connection: bool = False,
    nested: bool = False,
    direct_r_value: float | None = None,
    direct_l_value: float | None = None,
    direct_c_value: float | None = None,
    name: str = "grounding_link_emt",
) -> EmtModelTemplate:
    """Build one configurable one-terminal EMT grounding-link block.

    The block exposes one node-voltage input and one injected-current output,
    while grounding the opposite terminal internally through ``Ground EMT``.

    :param vf: EMT variable factory.
    :param include_r: Include the resistor branch.
    :param include_l: Include the inductor branch.
    :param include_c: Include the capacitor branch.
    :param solid_connection: Enforce a zero-voltage grounding connection.
    :param nested: Omit external network mappings for an internal child block.
    :param direct_r_value: Optional direct resistor value in ohms.
    :param direct_l_value: Optional direct inductance value in henries.
    :param direct_c_value: Optional direct capacitance value in farads.
    :param name: Symbolic model name.
    :return: Grounding-link EMT template.
    """
    if solid_connection:
        pass
    elif include_r or include_l or include_c:
        pass
    else:
        raise ValueError("Select at least one of R, L, or C for the EMT grounding link")

    if not solid_connection and include_r and direct_r_value is None:
        raise ValueError("The EMT grounding link requires one direct resistance value when the resistor branch is enabled")
    else:
        pass

    if not solid_connection and include_l and direct_l_value is None:
        raise ValueError("The EMT grounding link requires one direct inductance value when the inductor branch is enabled")
    else:
        pass

    if not solid_connection and include_c and direct_c_value is None:
        raise ValueError("The EMT grounding link requires one direct capacitance value when the capacitor branch is enabled")
    else:
        pass

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name
    # Runtime topology reads this typed declaration from the canonical block;
    # the diagram remains a removable editor projection.
    templ.block.dynamic_model_contract.emt_internal_grounding_link = True

    # Internal grounding ports must not declare a public bus-neutral terminal.
    voltage_reference: VarPowerFlowReferenceType | None = None if nested else VarPowerFlowReferenceType.v_N
    current_reference: VarPowerFlowReferenceType | None = None if nested else VarPowerFlowReferenceType.i_N
    node_voltage_var: Var = vf.add_var(name="v_N", reference=voltage_reference)
    current_var: Var = vf.add_var(name="i_N", reference=current_reference)
    ground_node_var: Var = vf.add_var(name=f"v_gnd")
    ground_template: EmtModelTemplate = get_ground_emt_template(vf=vf, name=name + "_ground")
    vf.add_connections(ground_template.block.in_vars, [ground_node_var])
    ground_current_var: Var = ground_template.block.out_vars[0]
    voltage_drop: Expr = node_voltage_var - ground_node_var
    current_expr: Expr = current_var

    templ.block.in_vars = [node_voltage_var]
    templ.block.out_vars = [current_var]
    templ.block.algebraic_vars = [current_var, ground_node_var]
    templ.block.algebraic_eqs = list()
    templ.block.state_vars = list()
    templ.block.state_eqs = list()
    templ.block.diff_vars = list()
    templ.block.init_eqs[current_var] = vf.add_const(0.0)
    templ.block.init_eqs[ground_node_var] = vf.add_const(0.0)
    templ.block.add(ground_template.block)

    if solid_connection:
        templ.block.algebraic_eqs.append(voltage_drop)
    else:
        pass

    if include_r:
        resistance_var: Var = vf.add_var(f"R")
        templ.block.event_dict[resistance_var] = vf.add_const(float(direct_r_value), name=resistance_var.name)
        current_expr = current_expr + voltage_drop / resistance_var
    else:
        pass

    if include_l:
        inductance_var: Var = vf.add_var(f"L")
        inductive_current_var: Var = vf.add_var(f"iL")
        inductive_diff_var: Var = vf.add_diff_var(name=f"d_iL", base_var=inductive_current_var)
        templ.block.event_dict[inductance_var] = vf.add_const(float(direct_l_value), name=inductance_var.name)
        templ.block.state_vars.append(inductive_current_var)
        templ.block.diff_vars.append(inductive_diff_var)
        templ.block.diff_init_eqs[inductive_diff_var] = vf.add_const(0.0)
        templ.block.state_eqs.append(-voltage_drop / inductance_var)
        current_expr = current_expr - inductive_current_var
    else:
        pass

    if include_c:
        capacitance_var: Var = vf.add_var(f"C")
        capacitor_current_var: Var = vf.add_var(f"iC")
        capacitor_voltage_var: Var = vf.add_var(f"vCap")
        capacitor_voltage_diff_var: Var = vf.add_diff_var(name=f"dvCap", base_var=capacitor_voltage_var)
        templ.block.event_dict[capacitance_var] = vf.add_const(float(direct_c_value), name=capacitance_var.name)
        templ.block.algebraic_vars.append(capacitor_current_var)
        templ.block.state_vars.append(capacitor_voltage_var)
        templ.block.diff_vars.append(capacitor_voltage_diff_var)
        templ.block.init_eqs[capacitor_voltage_var] = voltage_drop
        templ.block.diff_init_eqs[capacitor_voltage_diff_var] = capacitor_current_var / capacitance_var
        templ.block.state_eqs.append(capacitor_current_var / capacitance_var)
        templ.block.algebraic_eqs.append(capacitor_voltage_var - voltage_drop)
        current_expr = current_expr + capacitor_current_var
    else:
        pass

    if solid_connection:
        pass
    else:
        templ.block.algebraic_eqs.append(current_expr)
    templ.block.algebraic_eqs.append(ground_current_var + current_var)
    if nested:
        templ.block.external_mapping = dict()
    else:
        templ.block.external_mapping = _build_external_mapping(
            voltage_vars=dict(),
            current_vars=dict(),
            neutral_voltage_var=node_voltage_var,
            neutral_current_var=current_var,
        )

    _attach_combo_editor_diagram(
        root_block=templ.block,
        input_vars=[node_voltage_var],
        output_vars=[current_var],
        ground_block=ground_template.block,
        neutral_input_var=node_voltage_var,
    )
    return templ


def _create_editor_connection_child(var: Var, is_input: bool, name: str) -> Block:
    """Build one visual-only connection child used by ``Edit Hierarchy``.

    :param var: Shared root-port variable.
    :param is_input: True for one source-like input connector.
    :param name: Child block name.
    :return: Lightweight block exposing the shared port variable.
    """
    child_block: Block = Block(name=name)

    if is_input:
        child_block.out_vars.append(var)
    else:
        child_block.in_vars.append(var)

    return child_block


def _attach_combo_editor_diagram(root_block: Block,
                                 input_vars: List[Var],
                                 output_vars: List[Var],
                                 ground_block: Block | None = None,
                                 neutral_input_var: Var | None = None,
                                 grounding_link_block: Block | None = None) -> None:
    """Attach one minimal persisted editor diagram for the combined RLC block.

    The dynamic subeditor renders only the persisted ``BlockDiagram``. This
    helper materializes lightweight connection blocks so the user can reopen the
    hierarchy and see at least the neutral/ground topology instead of an empty
    canvas.

    :param root_block: Combined RLC root block.
    :param input_vars: Public input port variables.
    :param output_vars: Public output port variables.
    :param ground_block: Optional internal ground block.
    :param neutral_input_var: Optional explicit neutral input variable.
    :param grounding_link_block: Optional grounding-link child block.
    :return: None.
    """
    input_blocks_by_name: Dict[str, Block] = dict()
    output_block: Block
    input_index: int
    output_index: int
    input_var: Var
    output_var: Var

    for input_index, input_var in enumerate(input_vars):
        input_block: Block = _create_editor_connection_child(
            var=input_var,
            is_input=True,
            name=input_var.name,
        )
        root_block.add(input_block)
        root_block.diagram.add_node(
            name=input_block.name,
            x=40.0,
            y=80.0 + 100.0 * float(input_index),
            tpe=BlockType.INPUT_CONN.name,
            device_uid=input_block.uid,
        )
        input_blocks_by_name[input_var.name] = input_block

    for output_index, output_var in enumerate(output_vars):
        output_block = _create_editor_connection_child(
            var=output_var,
            is_input=False,
            name=output_var.name,
        )
        root_block.add(output_block)
        root_block.diagram.add_node(
            name=output_block.name,
            x=640.0,
            y=80.0 + 100.0 * float(output_index),
            tpe=BlockType.OUTPUT_CONN.name,
            device_uid=output_block.uid,
        )

    if grounding_link_block is not None:
        root_block.diagram.add_node(
            name=grounding_link_block.name,
            x=340.0,
            y=180.0,
            tpe=BlockType.GROUNDING_LINK_EMT.name,
            device_uid=grounding_link_block.uid,
        )

        if neutral_input_var is not None:
            neutral_input_block: Block | None = input_blocks_by_name.get(neutral_input_var.name, None)
            if neutral_input_block is not None:
                root_block.diagram.add_branch(
                    connectionitem_uid=uuid.uuid4().int,
                    device_uid_from=neutral_input_block.uid,
                    device_uid_to=grounding_link_block.uid,
                    port_number_from=0,
                    port_number_to=0,
                    color="#587291",
                )
            else:
                pass
        else:
            pass
    elif ground_block is not None:
        root_block.diagram.add_node(
            name=ground_block.name,
            x=340.0,
            y=180.0,
            tpe=BlockType.GROUND_EMT.name,
            device_uid=ground_block.uid,
        )

        if neutral_input_var is not None:
            neutral_input_block: Block | None = input_blocks_by_name.get(neutral_input_var.name, None)
            if neutral_input_block is not None:
                root_block.diagram.add_branch(
                    connectionitem_uid=uuid.uuid4().int,
                    device_uid_from=neutral_input_block.uid,
                    device_uid_to=ground_block.uid,
                    port_number_from=0,
                    port_number_to=0,
                    color="#587291",
                )
            else:
                pass
        else:
            pass
    else:
        pass


def wrap_ground_referenced_load_emt_template(
    vf: VarFactory,
    core_template: EmtModelTemplate,
    active_phases: List[str],
    connection_type: ShuntConnectionType,
    name: str,
) -> EmtModelTemplate:
    """Wrap one phase-selective EMT load template with explicit neutral/ground topology.

    The wrapped child keeps its original electrical equations and API mappings,
    while the outer block adds one neutral node, optional auto-grounding link,
    and per-phase phase-to-neutral voltage drops.

    :param vf: EMT variable factory.
    :param core_template: Existing phase-selective child template.
    :param active_phases: Ordered active phase labels.
    :param connection_type: ``FloatingStar``, ``NeutralStar`` or ``GroundedStar``.
    :param name: Symbolic wrapper name.
    :return: Wrapped EMT template.
    """
    if connection_type in {
        ShuntConnectionType.GroundedStar,
        ShuntConnectionType.NeutralStar,
        ShuntConnectionType.FloatingStar,
    }:
        pass
    else:
        raise ValueError("This EMT load topology wrapper supports only star-connected variants")

    wrapped_template: EmtModelTemplate = EmtModelTemplate()
    wrapped_template.tpe = core_template.tpe
    wrapped_template.name = name
    wrapped_template.block.name = name

    child_block: Block = core_template.block
    child_block.name = name + "_core"
    child_external_mapping: Dict[VarPowerFlowReferenceType, Var | None] = dict(child_block.external_mapping)
    child_block.external_mapping = dict()

    phase_voltage_vars: Dict[str, Var] = dict()
    phase_voltage_derivative_vars: Dict[str, Var] = dict()
    phase_drop_vars: Dict[str, Var] = dict()
    total_current_vars: Dict[str, Var] = dict()
    in_vars: List[Var] = list()
    out_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    phase_label: str

    neutral_voltage_var: Var | None = None
    neutral_current_var: Var | None = None
    neutral_voltage_derivative_var: Var | None = None
    ground_current_var: Var | None = None
    grounding_link_block: Block | None = None

    # Only NeutralStar owns a public neutral conductor. GroundedStar closes its
    # star point through the internal grounding link below, while FloatingStar
    # keeps the same point internal without grounding it. Keeping the grounded
    # neutral out of ``in_vars`` is essential on three-wire ABC buses: there is
    # no bus-side ``v_N`` variable to which such a terminal could be connected.
    if connection_type == ShuntConnectionType.NeutralStar:
        neutral_voltage_var = vf.add_var(name=f"v_N", reference=VarPowerFlowReferenceType.v_N)
        in_vars.append(neutral_voltage_var)
        neutral_voltage_derivative_var = vf.add_var(name=f"d_v_N")
        wrapped_template.block.event_dict[neutral_voltage_derivative_var] = vf.add_const(None)
    elif connection_type in {ShuntConnectionType.GroundedStar, ShuntConnectionType.FloatingStar}:
        neutral_voltage_var = vf.add_var(name=f"v_N_internal")
        algebraic_vars.append(neutral_voltage_var)
    else:
        raise ValueError("This EMT load topology wrapper supports only star-connected variants")

    if connection_type == ShuntConnectionType.GroundedStar:
        grounding_link_template: EmtModelTemplate = get_grounding_link_emt_template(
            vf=vf,
            include_r=False,
            include_l=False,
            include_c=False,
            solid_connection=True,
            nested=True,
            name=name + "_grounding_link",
        )
        vf.add_connections(grounding_link_template.block.in_vars, [neutral_voltage_var])
        ground_current_var = grounding_link_template.block.out_vars[0]
        grounding_link_block = grounding_link_template.block
        wrapped_template.block.add(grounding_link_block)
    else:
        pass

    for phase_label in active_phases:
        voltage_var: Var = vf.add_var(
            name=f"v_{phase_label}",
            reference=_get_voltage_reference(phase_label),
        )
        voltage_derivative_var: Var = vf.add_var(name=f"d_v_{phase_label}")
        phase_drop_var: Var = vf.add_var(name=f"v_drop_{phase_label}")
        current_var: Var = vf.add_var(
            name=f"i_{phase_label}",
            reference=_get_current_reference(phase_label),
        )

        phase_voltage_vars[phase_label] = voltage_var
        phase_voltage_derivative_vars[phase_label] = voltage_derivative_var
        phase_drop_vars[phase_label] = phase_drop_var
        total_current_vars[phase_label] = current_var
        in_vars.append(voltage_var)
        wrapped_template.block.event_dict[voltage_derivative_var] = vf.add_const(None)
        algebraic_vars.append(phase_drop_var)
        algebraic_vars.append(current_var)
        out_vars.append(current_var)
        algebraic_eqs.append(phase_drop_var - (voltage_var - neutral_voltage_var))

    child_inputs: List[Var] = list(child_block.in_vars)
    child_block.connect(child_inputs, list(phase_drop_vars[phase_label] for phase_label in active_phases))
    child_block.in_vars = list(phase_drop_vars[phase_label] for phase_label in active_phases)

    child_phase_label: str
    for child_phase_label in active_phases:
        derivative_key: VarPowerFlowReferenceType = VarPowerFlowReferenceType[f"d_v_{child_phase_label}"]
        child_derivative_var = child_external_mapping.get(derivative_key, None)

        if child_derivative_var is not None:
            if neutral_voltage_derivative_var is not None:
                child_block.event_dict[child_derivative_var] = phase_voltage_derivative_vars[child_phase_label] - neutral_voltage_derivative_var
            else:
                child_block.event_dict[child_derivative_var] = phase_voltage_derivative_vars[child_phase_label]
        else:
            pass

    wrapped_template.block.add(child_block)

    for phase_index, phase_label in enumerate(active_phases):
        algebraic_eqs.append(total_current_vars[phase_label] - child_block.out_vars[phase_index])

    # NeutralStar exchanges neutral current with the external conductor. A
    # grounded star instead closes KCL exclusively through its internal ground
    # branch, and a floating star closes KCL without either external or ground
    # current. These are different electrical topologies and must not share the
    # same public ``v_N``/``i_N`` interface.
    if connection_type == ShuntConnectionType.NeutralStar:
        neutral_current_var = vf.add_var(name=f"i_N", reference=VarPowerFlowReferenceType.i_N)
        algebraic_vars.append(neutral_current_var)
        out_vars.insert(0, neutral_current_var)

        neutral_kcl: Expr = neutral_current_var
        for phase_label in active_phases:
            neutral_kcl = neutral_kcl + total_current_vars[phase_label]

        algebraic_eqs.append(neutral_kcl)
    elif connection_type == ShuntConnectionType.GroundedStar:
        if ground_current_var is None:
            raise ValueError("Grounded-star EMT load requires one internal ground subblock")
        else:
            pass

        neutral_kcl = ground_current_var
        for phase_label in active_phases:
            neutral_kcl = neutral_kcl + total_current_vars[phase_label]

        algebraic_eqs.append(neutral_kcl)
        if grounding_link_block is not None:
            grounding_link_block.init_eqs[ground_current_var] = -(
                sum(total_current_vars.values(), vf.add_const(0.0))
            )
            ground_block = grounding_link_block.children[0]
            ground_block.init_eqs[ground_block.out_vars[0]] = -ground_current_var
    elif connection_type == ShuntConnectionType.FloatingStar:
        neutral_kcl = vf.add_const(0.0)
        for phase_label in active_phases:
            neutral_kcl = neutral_kcl + total_current_vars[phase_label]
        algebraic_eqs.append(neutral_kcl)
    else:
        raise ValueError("This EMT load topology wrapper supports only star-connected variants")

    wrapped_template.block.in_vars = in_vars
    wrapped_template.block.out_vars = out_vars
    wrapped_template.block.algebraic_vars = algebraic_vars
    wrapped_template.block.algebraic_eqs = algebraic_eqs
    wrapped_template.block.external_mapping = _build_external_mapping(
        voltage_vars=phase_voltage_vars,
        current_vars=total_current_vars,
        neutral_voltage_var=neutral_voltage_var if connection_type == ShuntConnectionType.NeutralStar else None,
        neutral_current_var=neutral_current_var,
        voltage_derivative_vars=phase_voltage_derivative_vars,
        neutral_voltage_derivative_var=neutral_voltage_derivative_var,
    )

    mapping_key: VarPowerFlowReferenceType
    mapping_var: Var | None
    for mapping_key, mapping_var in child_external_mapping.items():
        if mapping_key in {
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
            VarPowerFlowReferenceType.i_N,
            VarPowerFlowReferenceType.i_A,
            VarPowerFlowReferenceType.i_B,
            VarPowerFlowReferenceType.i_C,
        }:
            pass
        else:
            wrapped_template.block.external_mapping[mapping_key] = mapping_var

    _attach_combo_editor_diagram(
        root_block=wrapped_template.block,
        input_vars=in_vars,
        output_vars=out_vars,
        neutral_input_var=neutral_voltage_var if connection_type == ShuntConnectionType.NeutralStar else None,
        grounding_link_block=grounding_link_block,
    )
    return wrapped_template


def wrap_delta_referenced_load_emt_template(
    vf: VarFactory,
    core_template: EmtModelTemplate,
    active_phases: List[str],
    name: str,
) -> EmtModelTemplate:
    """Wrap one phase-selective EMT load template with explicit delta topology.

    The child template is interpreted as branch-based with the mapping
    ``A -> AB``, ``B -> BC`` and ``C -> CA``.

    :param vf: EMT variable factory.
    :param core_template: Existing phase-selective child template built for delta branches.
    :param active_phases: Active bus-phase labels.
    :param name: Symbolic wrapper name.
    :return: Wrapped delta EMT template.
    """
    branch_specs: List[tuple[str, str, str]] = _get_delta_branch_specs(active_phases)
    if len(branch_specs) == 0:
        raise ValueError("Delta EMT loads require at least one active delta branch")
    else:
        pass

    wrapped_template: EmtModelTemplate = EmtModelTemplate()
    wrapped_template.tpe = core_template.tpe
    wrapped_template.name = name
    wrapped_template.block.name = name

    child_block: Block = core_template.block
    child_block.name = name + "_core"
    child_external_mapping: Dict[VarPowerFlowReferenceType, Var | None] = dict(child_block.external_mapping)
    child_block.external_mapping = dict()

    phase_voltage_vars: Dict[str, Var] = dict()
    phase_voltage_derivative_vars: Dict[str, Var] = dict()
    branch_voltage_vars: Dict[str, Var] = dict()
    total_current_vars: Dict[str, Var] = dict()
    phase_current_exprs: Dict[str, Expr] = dict()
    in_vars: List[Var] = list()
    out_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    phase_label: str
    branch_index: int
    branch_label: str
    phase_from: str
    phase_to: str

    for phase_label in active_phases:
        voltage_var: Var = vf.add_var(
            name=f"v_{phase_label}",
            reference=_get_voltage_reference(phase_label),
        )
        voltage_derivative_var: Var = vf.add_var(name=f"d_v_{phase_label}")
        current_var: Var = vf.add_var(
            name=f"i_{phase_label}",
            reference=_get_current_reference(phase_label),
        )
        phase_voltage_vars[phase_label] = voltage_var
        phase_voltage_derivative_vars[phase_label] = voltage_derivative_var
        total_current_vars[phase_label] = current_var
        phase_current_exprs[phase_label] = current_var
        in_vars.append(voltage_var)
        wrapped_template.block.event_dict[voltage_derivative_var] = vf.add_const(None)
        algebraic_vars.append(current_var)
        out_vars.append(current_var)

    for branch_label, phase_from, phase_to in branch_specs:
        branch_voltage_var: Var = vf.add_var(name=f"v_delta_{branch_label}")
        branch_voltage_vars[branch_label] = branch_voltage_var
        algebraic_vars.append(branch_voltage_var)
        algebraic_eqs.append(branch_voltage_var - (phase_voltage_vars[phase_from] - phase_voltage_vars[phase_to]))

    child_inputs: List[Var] = list(child_block.in_vars)
    child_block.connect(child_inputs, list(branch_voltage_vars[branch_label] for branch_label, _, _ in branch_specs))
    child_block.in_vars = list(branch_voltage_vars[branch_label] for branch_label, _, _ in branch_specs)

    for branch_index, (branch_label, phase_from, phase_to) in enumerate(branch_specs):
        child_current_var = child_block.out_vars[branch_index]
        phase_current_exprs[phase_from] = phase_current_exprs[phase_from] - child_current_var
        phase_current_exprs[phase_to] = phase_current_exprs[phase_to] + child_current_var

        derivative_key = VarPowerFlowReferenceType[f"d_v_{branch_label[0]}"]
        child_derivative_var = child_external_mapping.get(derivative_key, None)
        if child_derivative_var is not None:
            child_block.event_dict[child_derivative_var] = phase_voltage_derivative_vars[phase_from] - phase_voltage_derivative_vars[phase_to]
        else:
            pass

    wrapped_template.block.add(child_block)

    for phase_label in active_phases:
        algebraic_eqs.append(phase_current_exprs[phase_label])

    wrapped_template.block.in_vars = in_vars
    wrapped_template.block.out_vars = out_vars
    wrapped_template.block.algebraic_vars = algebraic_vars
    wrapped_template.block.algebraic_eqs = algebraic_eqs
    wrapped_template.block.external_mapping = _build_external_mapping(
        voltage_vars=phase_voltage_vars,
        current_vars=total_current_vars,
        voltage_derivative_vars=phase_voltage_derivative_vars,
    )

    mapping_key: VarPowerFlowReferenceType
    mapping_var: Var | None
    for mapping_key, mapping_var in child_external_mapping.items():
        if mapping_key in {
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
            VarPowerFlowReferenceType.i_N,
            VarPowerFlowReferenceType.i_A,
            VarPowerFlowReferenceType.i_B,
            VarPowerFlowReferenceType.i_C,
            VarPowerFlowReferenceType.d_v_N,
            VarPowerFlowReferenceType.d_v_A,
            VarPowerFlowReferenceType.d_v_B,
            VarPowerFlowReferenceType.d_v_C,
        }:
            pass
        else:
            wrapped_template.block.external_mapping[mapping_key] = mapping_var

    _attach_combo_editor_diagram(
        root_block=wrapped_template.block,
        input_vars=in_vars,
        output_vars=out_vars,
    )
    return wrapped_template


def _get_delta_branch_specs(active_phases: List[str]) -> List[tuple[str, str, str]]:
    """Return the active delta branches for one phase subset.

    The mapping keeps the existing load API convention:
    ``A -> AB``, ``B -> BC``, ``C -> CA``.

    :param active_phases: Active phase labels.
    :return: Ordered ``(branch_label, from_phase, to_phase)`` tuples.
    """
    phase_set = set(active_phases)
    branch_specs: List[tuple[str, str, str]] = list()

    if "A" in phase_set and "B" in phase_set:
        branch_specs.append(("AB", "A", "B"))
    else:
        pass

    if "B" in phase_set and "C" in phase_set:
        branch_specs.append(("BC", "B", "C"))
    else:
        pass

    if "C" in phase_set and "A" in phase_set:
        branch_specs.append(("CA", "C", "A"))
    else:
        pass

    return branch_specs


def _get_delta_shunt_rlc_combo_emt_template(
    vf: VarFactory,
    include_r: bool,
    include_l: bool,
    include_c: bool,
    phA: bool,
    phB: bool,
    phC: bool,
    direct_r_value: float | None,
    direct_l_value: float | None,
    direct_c_value: float | None,
    name: str,
) -> EmtModelTemplate:
    """Build one direct-value delta EMT shunt.

    This first delta cut focuses on the modal/editor workflow, which already
    resolves physical values before reaching the template builder.

    :param vf: EMT variable factory.
    :param include_r: Include the resistor branch.
    :param include_l: Include the inductor branch.
    :param include_c: Include the capacitor branch.
    :param phA: Enable phase A.
    :param phB: Enable phase B.
    :param phC: Enable phase C.
    :param direct_r_value: Direct resistor value in ohms.
    :param direct_l_value: Direct inductance value in henries.
    :param direct_c_value: Direct capacitance value in farads.
    :param name: Symbolic block name.
    :return: Delta EMT shunt template.
    """
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    branch_specs: List[tuple[str, str, str]] = _get_delta_branch_specs(active_phases)
    phase_voltage_vars: Dict[str, Var] = dict()
    total_current_vars: Dict[str, Var] = dict()
    phase_current_exprs: Dict[str, Expr] = dict()
    in_vars: List[Var] = list()
    out_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    state_vars: List[Var] = list()
    state_eqs: List[Expr] = list()
    diff_vars: List[Var] = list()
    phase_label: str
    branch_label: str
    phase_from: str
    phase_to: str

    if len(active_phases) < 2:
        raise ValueError("Delta EMT shunts require at least two active phases")
    else:
        pass

    if len(branch_specs) == 0:
        raise ValueError("Delta EMT shunts require at least one active delta branch")
    else:
        pass

    if include_r and direct_r_value is None:
        raise ValueError("Delta EMT resistor branches currently require direct resistance values")
    else:
        pass

    if include_l and direct_l_value is None:
        raise ValueError("Delta EMT inductor branches currently require direct inductance values")
    else:
        pass

    if include_c and direct_c_value is None:
        raise ValueError("Delta EMT capacitor branches currently require direct capacitance values")
    else:
        pass

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    block = Block()

    for phase_label in active_phases:
        voltage_var: Var = vf.add_var(
            name=f"v_{phase_label}",
            reference=_get_voltage_reference(phase_label),
        )
        current_var: Var = vf.add_var(
            name=f"i_{phase_label}",
            reference=_get_current_reference(phase_label),
        )
        phase_voltage_vars[phase_label] = voltage_var
        total_current_vars[phase_label] = current_var
        phase_current_exprs[phase_label] = current_var
        in_vars.append(voltage_var)
        out_vars.append(current_var)
        algebraic_vars.append(current_var)

    for branch_label, phase_from, phase_to in branch_specs:
        voltage_drop: Expr = phase_voltage_vars[phase_from] - phase_voltage_vars[phase_to]

        if include_r:
            resistance_var: Var = vf.add_var(f"R_{branch_label}")
            block.event_dict[resistance_var] = vf.add_const(float(direct_r_value), name=resistance_var.name)
            branch_current_expr: Expr = voltage_drop / resistance_var
            phase_current_exprs[phase_from] = phase_current_exprs[phase_from] + branch_current_expr
            phase_current_exprs[phase_to] = phase_current_exprs[phase_to] - branch_current_expr
        else:
            pass

        if include_l:
            inductance_var: Var = vf.add_var(f"L_{branch_label}")
            inductive_current_var: Var = vf.add_var(f"iL_{branch_label}")
            inductive_diff_var: Var = vf.add_diff_var(name=f"d_iL_{branch_label}", base_var=inductive_current_var)
            block.event_dict[inductance_var] = vf.add_const(float(direct_l_value), name=inductance_var.name)
            state_vars.append(inductive_current_var)
            diff_vars.append(inductive_diff_var)
            block.diff_init_eqs[inductive_diff_var] = vf.add_const(0.0)
            state_eqs.append(voltage_drop / inductance_var)
            phase_current_exprs[phase_from] = phase_current_exprs[phase_from] + inductive_current_var
            phase_current_exprs[phase_to] = phase_current_exprs[phase_to] - inductive_current_var
        else:
            pass

        if include_c:
            capacitance_var: Var = vf.add_var(f"C_{branch_label}")
            capacitor_current_var: Var = vf.add_var(f"iC_{branch_label}")
            capacitor_voltage_var: Var = vf.add_var(f"vCap{branch_label}")
            capacitor_voltage_diff_var: Var = vf.add_diff_var(
                name=f"dvCap{branch_label}",
                base_var=capacitor_voltage_var,
            )
            block.event_dict[capacitance_var] = vf.add_const(float(direct_c_value), name=capacitance_var.name)
            algebraic_vars.append(capacitor_current_var)
            state_vars.append(capacitor_voltage_var)
            diff_vars.append(capacitor_voltage_diff_var)
            block.init_eqs[capacitor_voltage_var] = voltage_drop
            block.diff_init_eqs[capacitor_voltage_diff_var] = capacitor_current_var / capacitance_var
            state_eqs.append(capacitor_current_var / capacitance_var)
            algebraic_eqs.append(capacitor_voltage_var - voltage_drop)
            phase_current_exprs[phase_from] = phase_current_exprs[phase_from] + capacitor_current_var
            phase_current_exprs[phase_to] = phase_current_exprs[phase_to] - capacitor_current_var
        else:
            pass

    for phase_label in active_phases:
        algebraic_eqs.append(phase_current_exprs[phase_label])

    block.in_vars = in_vars
    block.out_vars = out_vars
    block.algebraic_vars = algebraic_vars
    block.algebraic_eqs = algebraic_eqs
    block.state_vars = state_vars
    block.state_eqs = state_eqs
    block.diff_vars = diff_vars
    block.external_mapping = _build_external_mapping(
        voltage_vars=phase_voltage_vars,
        current_vars=total_current_vars,
    )
    _attach_combo_editor_diagram(
        root_block=block,
        input_vars=in_vars,
        output_vars=out_vars,
    )

    templ.block = block

    return templ


def _build_resistor_api_mapping(pl0_vars: Dict[str, Var]) -> Dict[ParamPowerFlowReferenceType, Var]:
    """Build the API mapping for an EMT shunt resistor.

    :param pl0_vars: Active per-phase active-power variables.
    :return: API mapping dictionary.
    """
    # Only active phases publish mapping entries. A missing physical phase is
    # represented by an absent key, never by an API key with a ``None`` target.
    mapping: Dict[ParamPowerFlowReferenceType, Var] = dict()
    phase_label: str
    pl0_var: Var
    for phase_label, pl0_var in pl0_vars.items():
        mapping[_get_pl0_reference(phase_label=phase_label)] = pl0_var

    return mapping


def _build_reactive_api_mapping(
    omega_base_var: Var,
    ql0_vars: Dict[str, Var],
) -> Dict[ParamPowerFlowReferenceType, Var]:
    """Build the API mapping for an EMT shunt inductor or capacitor.

    :param omega_base_var: Shared base-frequency variable.
    :param ql0_vars: Active per-phase reactive-power variables.
    :return: API mapping dictionary.
    """
    # The EMT initializer writes base frequency and active-phase reactive power
    # through concrete owner-local targets. Inactive and unrelated references
    # stay absent instead of publishing placeholder mappings.
    mapping: Dict[ParamPowerFlowReferenceType, Var] = dict({
        ParamPowerFlowReferenceType.omega_base: omega_base_var,
    })
    phase_label: str
    ql0_var: Var
    for phase_label, ql0_var in ql0_vars.items():
        mapping[_get_ql0_reference(phase_label=phase_label)] = ql0_var

    return mapping


def get_shunt_r_emt_template(
    vf: VarFactory,
    phA: bool = True,
    phB: bool = True,
    phC: bool = True,
    name: str = "R_shunt",
) -> EmtModelTemplate:
    """Build a phase-selective shunt resistor EMT template.

    :param vf: EMT variable factory.
    :param phA: Bool. True if the load has phase A, else False.
    :param phB: Bool. True if the load has phase B, else False.
    :param phC: Bool. True if the load has phase C, else False.
    :param name: Optional symbolic model name.
    :return: EMT shunt resistor template sized to the active phases.
    """
    # The template must derive every symbolic structure from the active phase set
    # so EmtProblem can remain unchanged and consume a coherent block directly.
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    phase_count: int = len(active_phases)
    resolved_name: str = _get_phase_count_name("Shunt_R", phase_count, name)
    if name == "R_shunt":
        event_name: str = _get_phase_count_name("Shunt_R", phase_count, None)
    else:
        event_name = resolved_name

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = resolved_name

    block = Block()

    # Create only the active terminal voltage variables because inactive phases
    # must not produce extra equations or unused symbolic dimensions.
    in_vars: List[Var] = list()
    voltage_vars: Dict[str, Var] = dict()
    resistance_vars: Dict[str, Var] = dict()
    pl0_vars: Dict[str, Var] = dict()
    current_vars: Dict[str, Var] = dict()
    algebraic_eqs: List[Expr] = list()

    # Component sizing is distinct from the terminal operating voltage. The
    # declared nominal remains available when a zero operating point is supplied.
    pf_vm_var: Var = vf.add_var("Vm_pf_" + event_name)
    block.event_dict[pf_vm_var] = vf.add_const(1.0)
    power_conversion_voltage_squared: Expr = _get_power_conversion_voltage_squared(
        vf=vf,
        pf_vm_var=pf_vm_var,
    )

    for phase_label in active_phases:
        # Each active phase gets its own voltage input and electrical parameters.
        voltage_var: Var = vf.add_var(
            name=f"v_{phase_label}",
            reference=_get_voltage_reference(phase_label),
        )
        in_vars.append(voltage_var)
        voltage_vars[phase_label] = voltage_var

        resistance_var: Var = vf.add_var(f"R_{phase_label}_{event_name}")
        resistance_vars[phase_label] = resistance_var

        pl0_var: Var = vf.add_var(f"Pl0_{phase_label}")
        block.parameters[pl0_var] = vf.add_const(None)
        pl0_vars[phase_label] = pl0_var

        # The event dictionary holds the algebraic resistance definition so EMT
        # events can still alter the effective resistor without core changes.
        # Some EMT workflows intentionally map conductance-backed PF data into
        # this shunt-R template, which can leave ``Pl0`` at zero until one later
        # explicit override or scheduled event writes the intended resistance.
        # Clamp the denominator so the runtime parameter vector stays finite.
        # AC phase voltage and current use RMS phase-voltage and Sbase/3
        # current bases. Therefore one physical per-phase power expressed on
        # the system Sbase becomes three times larger on the phase V-I base.
        # Without this factor a balanced shunt consumes exactly one third of
        # the P1+P2+P3 power declared by the static Load device.
        block.event_dict[resistance_var] = (
            power_conversion_voltage_squared
            / (vf.add_const(3.0) * max(pl0_var, 1.0e-9))
        )

        current_var: Var = vf.add_var(
            name=f"i_{phase_label}",
            reference=_get_current_reference(phase_label),
        )
        current_vars[phase_label] = current_var
        algebraic_eqs.append(current_var + voltage_var / resistance_var)

    # Publish the size-consistent symbolic structures in active-phase order.
    algebraic_vars: List[Var] = list(current_vars[phase_label] for phase_label in active_phases)
    block.in_vars = in_vars
    block.algebraic_vars = algebraic_vars
    block.algebraic_eqs = algebraic_eqs
    block.out_vars = list(current_vars[phase_label] for phase_label in active_phases)
    block.external_mapping = _build_external_mapping(voltage_vars=voltage_vars, current_vars=current_vars)
    block.external_mapping[VarPowerFlowReferenceType.VmSizing] = pf_vm_var
    for phase_label, component_var in resistance_vars.items():
        block.external_mapping[RESISTANCE_REFERENCES[phase_label]] = component_var
    block.api_obj_mapping = _build_resistor_api_mapping(pl0_vars=pl0_vars)

    templ.block.children.append(block)
    templ.block.name = resolved_name
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars

    return templ


def get_shunt_l_emt_template(
    vf: VarFactory,
    phA: bool,
    phB: bool,
    phC: bool,
    name: str = "L_shunt",
) -> EmtModelTemplate:
    """Build a phase-selective shunt inductor EMT template.

    :param vf: EMT variable factory.
    :param phA: True when phase A is active.
    :param phB: True when phase B is active.
    :param phC: True when phase C is active.
    :param name: Optional symbolic model name.
    :return: Configured inductor EMT template.
    """
    # The inductor state dimension must follow the filtered phase list so the
    # derivative vectors assembled by the solver stay compact and ordered.
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    phase_count: int = len(active_phases)
    resolved_name: str = _get_phase_count_name("Shunt_L", phase_count, name)

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = resolved_name

    in_vars: List[Var] = list()
    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    state_eqs: List[Expr] = list()
    voltage_vars: Dict[str, Var] = dict()
    current_vars: Dict[str, Var] = dict()
    inductance_vars: Dict[str, Var] = dict()
    ql0_vars: Dict[str, Var] = dict()

    # Base frequency and the explicit sizing reference are shared across phases;
    # a cold operating state must not turn the physical inductance into zero.
    omega_base_var: Var = vf.add_var("w_base_" + resolved_name)
    pf_vm_var: Var = vf.add_var("Vm_pf_" + resolved_name)
    block = Block()
    block.event_dict[pf_vm_var] = vf.add_const(1.0)
    block.parameters[omega_base_var] = vf.add_const(None)
    power_conversion_voltage_squared: Expr = _get_power_conversion_voltage_squared(
        vf=vf,
        pf_vm_var=pf_vm_var,
    )

    for phase_label in active_phases:
        # Each active phase gets one terminal input, one current state, and one
        # inductance computed from the same API-level reactive-power contract.
        voltage_var: Var = vf.add_var(
            name=f"v_{phase_label}",
            reference=_get_voltage_reference(phase_label),
        )
        in_vars.append(voltage_var)
        voltage_vars[phase_label] = voltage_var

        inductance_var: Var = vf.add_var(f"L_{phase_label}")
        inductance_vars[phase_label] = inductance_var

        ql0_var: Var = vf.add_var(f"Ql0_{phase_label}")
        ql0_vars[phase_label] = ql0_var
        block.parameters[ql0_var] = vf.add_const(None)
        block.event_dict[inductance_var] = (
            power_conversion_voltage_squared
            / (vf.add_const(3.0) * ql0_var * omega_base_var)
        )

        current_var: Var = vf.add_var(
            name=f"i_{phase_label}",
            reference=_get_current_reference(phase_label),
        )
        current_vars[phase_label] = current_var
        state_vars.append(current_var)

        diff_var: Var = vf.add_diff_var(name=f"d_i_{phase_label}", base_var=current_var)
        diff_vars.append(diff_var)
        block.diff_init_eqs[diff_var] = -voltage_var / inductance_var

        # The differential law is unchanged per phase; only the number and order
        # of replicated phase equations now depend on the active phase mask.
        state_eqs.append(-voltage_var / inductance_var)

    block.in_vars = in_vars
    block.state_vars = state_vars
    block.diff_vars = diff_vars
    block.state_eqs = state_eqs
    block.out_vars = list(current_vars[phase_label] for phase_label in active_phases)
    block.external_mapping = _build_external_mapping(voltage_vars=voltage_vars, current_vars=current_vars)
    block.external_mapping[VarPowerFlowReferenceType.VmSizing] = pf_vm_var
    for phase_label, component_var in inductance_vars.items():
        block.external_mapping[INDUCTANCE_REFERENCES[phase_label]] = component_var
    block.api_obj_mapping = _build_reactive_api_mapping(omega_base_var=omega_base_var, ql0_vars=ql0_vars)

    templ.block.children.append(block)
    templ.block.name = resolved_name
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars

    return templ


def get_shunt_c_emt_template(
    vf: VarFactory,
    phA: bool,
    phB: bool,
    phC: bool,
    name: str = "C_shunt",
) -> EmtModelTemplate:
    """Build a phase-selective shunt capacitor EMT template.

    :param vf: EMT variable factory.
    :param phA: True when phase A is active.
    :param phB: True when phase B is active.
    :param phC: True when phase C is active.
    :param name: Optional symbolic model name.
    :return: Configured capacitor EMT template.
    """
    # Each capacitor voltage is a state constrained to its terminal voltage.
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    phase_count: int = len(active_phases)
    resolved_name: str = _get_phase_count_name("Shunt_C", phase_count, name)

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = resolved_name

    in_vars: List[Var] = list()
    state_vars: List[Var] = list()
    state_eqs: List[Expr] = list()
    diff_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    voltage_vars: Dict[str, Var] = dict()
    current_vars: Dict[str, Var] = dict()
    capacitance_vars: Dict[str, Var] = dict()
    ql0_vars: Dict[str, Var] = dict()

    # Base frequency and the explicit sizing reference are shared across phases;
    # zero terminal voltage does not define a capacitor's dimensioning voltage.
    omega_base_var: Var = vf.add_var("w_base_" + resolved_name)
    pf_vm_var: Var = vf.add_var("Vm_pf_" + resolved_name)

    block = Block()
    block.event_dict[pf_vm_var] = vf.add_const(1.0)
    block.parameters[omega_base_var] = vf.add_const(None)
    power_conversion_voltage_squared: Expr = _get_power_conversion_voltage_squared(
        vf=vf,
        pf_vm_var=pf_vm_var,
    )

    for phase_label in active_phases:
        # Each active phase gets one bus voltage input, one implicit capacitor
        # voltage derivative, and one injected current algebraic output.
        voltage_var: Var = vf.add_var(
            name=f"v_{phase_label}",
            reference=_get_voltage_reference(phase_label),
        )
        in_vars.append(voltage_var)
        voltage_vars[phase_label] = voltage_var

        capacitance_var: Var = vf.add_var(f"C_{phase_label}")
        capacitance_vars[phase_label] = capacitance_var

        ql0_var: Var = vf.add_var(f"Ql0_{phase_label}")
        ql0_vars[phase_label] = ql0_var
        block.parameters[ql0_var] = vf.add_const(None)
        # Ql0_* follows the static Load convention: positive reactive power is
        # inductive consumption and negative reactive power is capacitive. The
        # EMT capacitor needs a positive physical capacitance for the latter,
        # so negate Ql0_* while converting from the system three-phase Sbase to
        # the phase V-I base.
        block.event_dict[capacitance_var] = (
            -vf.add_const(3.0) * ql0_var
            / (power_conversion_voltage_squared * omega_base_var)
        )

        current_var: Var = vf.add_var(
            name=f"i_{phase_label}",
            reference=_get_current_reference(phase_label),
        )
        current_vars[phase_label] = current_var
        algebraic_vars.append(current_var)

        capacitor_voltage_var: Var = vf.add_var(f"vCap{phase_label}")
        state_vars.append(capacitor_voltage_var)

        capacitor_voltage_diff_var: Var = vf.add_diff_var(
            name=f"dvCap{phase_label}",
            base_var=capacitor_voltage_var,
        )
        diff_vars.append(capacitor_voltage_diff_var)
        block.init_eqs[capacitor_voltage_var] = voltage_var
        block.diff_init_eqs[capacitor_voltage_diff_var] = -current_var / capacitance_var

        # Bind the implicit capacitor voltage to the bus voltage and derive
        # current from its differential variable.
        algebraic_eqs.append(capacitor_voltage_var - voltage_var)
        state_eqs.append(-current_var / capacitance_var)

    block.in_vars = in_vars
    block.state_vars = state_vars
    block.state_eqs = state_eqs
    block.diff_vars = diff_vars
    block.algebraic_vars = algebraic_vars
    block.algebraic_eqs = algebraic_eqs
    block.out_vars = list(current_vars[phase_label] for phase_label in active_phases)
    block.external_mapping = _build_external_mapping(voltage_vars=voltage_vars, current_vars=current_vars)
    block.external_mapping[VarPowerFlowReferenceType.VmSizing] = pf_vm_var
    for phase_label, component_var in capacitance_vars.items():
        block.external_mapping[CAPACITANCE_REFERENCES[phase_label]] = component_var
    block.api_obj_mapping = _build_reactive_api_mapping(omega_base_var=omega_base_var, ql0_vars=ql0_vars)

    templ.block.children.append(block)
    templ.block.name = resolved_name
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars

    return templ


class ShuntRComboEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Configure a phase-selective resistive EMT shunt builder.

        :param vf: Variable factory used to allocate the symbolic model variables.
        :return: None.
        """
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="connection_type", units="", descr="Shunt connection topology.",
                             tpe=ShuntConnectionType, value=ShuntConnectionType.GroundedStar),
                TemplateProp(name="direct_r_value", units="ohm", descr="Direct resistance value.",
                             tpe=float, value=None),
                TemplateProp(name="name", units="", descr="Name of the EMT model.",
                             tpe=str, value="R_combo_emt"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        """Build the configured resistive EMT shunt.

        :return: Resistive EMT shunt template for the selected phases.
        """
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        connection_type: ShuntConnectionType | None = self.get_value("connection_type")
        direct_r_value: float | None = self.get_value("direct_r_value")
        name: str = self.get_value("name")

        return get_shunt_rlc_combo_emt_template(
            self.vf, include_r=True, include_l=False, include_c=False, phA=phA, phB=phB, phC=phC,
            connection_type=connection_type,
            direct_r_value=direct_r_value, direct_l_value=None, direct_c_value=None, name=name,
        )


class ShuntLComboEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Configure a phase-selective inductive EMT shunt builder.

        :param vf: Variable factory used to allocate the symbolic model variables.
        :return: None.
        """
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="connection_type", units="", descr="Shunt connection topology.",
                             tpe=ShuntConnectionType, value=ShuntConnectionType.GroundedStar),
                TemplateProp(name="direct_l_value", units="H", descr="Direct inductance value.", tpe=float, value=None),
                TemplateProp(name="name", units="", descr="Name of the EMT model.",
                             tpe=str, value="L_combo_emt"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        """Build the configured inductive EMT shunt.

        :return: Inductive EMT shunt template for the selected phases.
        """
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        connection_type: ShuntConnectionType | None = self.get_value("connection_type")
        direct_l_value: float | None = self.get_value("direct_l_value")
        name: str = self.get_value("name")

        return get_shunt_rlc_combo_emt_template(
            self.vf, include_r=False, include_l=True, include_c=False, phA=phA, phB=phB, phC=phC,
            connection_type=connection_type,
            direct_r_value=None, direct_l_value=direct_l_value, direct_c_value=None, name=name,
        )


class ShuntCComboEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Configure a phase-selective capacitive EMT shunt builder.

        :param vf: Variable factory used to allocate the symbolic model variables.
        :return: None.
        """
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="connection_type", units="", descr="Shunt connection topology.",
                             tpe=ShuntConnectionType, value=ShuntConnectionType.GroundedStar),
                TemplateProp(name="direct_c_value", units="F", descr="Direct capacitance value.", tpe=float, value=None),
                TemplateProp(name="name", units="", descr="Name of the EMT model.",
                             tpe=str, value="C_combo_emt"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        """Build the configured capacitive EMT shunt.

        :return: Capacitive EMT shunt template for the selected phases.
        """
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        connection_type: ShuntConnectionType | None = self.get_value("connection_type")
        direct_c_value: float | None = self.get_value("direct_c_value")
        name: str = self.get_value("name")

        return get_shunt_rlc_combo_emt_template(
            self.vf, include_r=False, include_l=False, include_c=True, phA=phA, phB=phB, phC=phC,
            connection_type=connection_type,
            direct_r_value=None, direct_l_value=None, direct_c_value=direct_c_value, name=name,
        )


def get_shunt_rlc_combo_emt_template(
    vf: VarFactory,
    include_r: bool,
    include_l: bool,
    include_c: bool,
    phA: bool = True,
    phB: bool = True,
    phC: bool = True,
    connection_type: ShuntConnectionType = ShuntConnectionType.GroundedStar,
    direct_r_value: float | None = None,
    direct_l_value: float | None = None,
    direct_c_value: float | None = None,
    name: str = "RLC_combo_emt",
) -> EmtModelTemplate:
    """Build one star-connected combined EMT shunt with explicit neutral handling.

    ``FloatingStar`` keeps an internal floating neutral node, ``NeutralStar``
    exposes one external neutral port, and ``GroundedStar`` instantiates one
    internal ideal-ground subblock connected to the same neutral node.

    :param vf: EMT variable factory.
    :param include_r: Include the resistor branch.
    :param include_l: Include the inductor branch.
    :param include_c: Include the capacitor branch.
    :param phA: Enable phase A.
    :param phB: Enable phase B.
    :param phC: Enable phase C.
    :param connection_type: Requested star connection type.
    :param name: Symbolic model name.
    :return: Combined EMT shunt template.
    """
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    phase_voltage_vars: Dict[str, Var] = dict()
    phase_derivative_vars: Dict[str, Var] = dict()
    phase_vm_vars: Dict[str, Var] = dict()
    total_current_vars: Dict[str, Var] = dict()
    inductive_current_vars: Dict[str, Var] = dict()
    inductance_vars: Dict[str, Var] = dict()
    component_vars: Dict[VarPowerFlowReferenceType, Var] = dict()
    in_vars: List[Var] = list()
    out_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    state_vars: List[Var] = list()
    state_eqs: List[Expr] = list()
    diff_vars: List[Var] = list()
    phase_label: str

    if include_r or include_l or include_c:
        pass
    else:
        raise ValueError("Select at least one of R, L, or C for the EMT combined shunt")

    if include_l and include_c and (direct_l_value is None or direct_c_value is None):
        raise ValueError(
            "The EMT combined RLC block cannot split one reactive-power reference into both L and C branches without direct values"
        )
    else:
        pass

    if connection_type in {
        ShuntConnectionType.GroundedStar,
        ShuntConnectionType.NeutralStar,
        ShuntConnectionType.FloatingStar,
        ShuntConnectionType.Delta,
    }:
        pass
    else:
        raise ValueError("The EMT combined RLC implementation supports only star-connected or delta variants")

    if connection_type == ShuntConnectionType.Delta:
        return _get_delta_shunt_rlc_combo_emt_template(
            vf=vf,
            include_r=include_r,
            include_l=include_l,
            include_c=include_c,
            phA=phA,
            phB=phB,
            phC=phC,
            direct_r_value=direct_r_value,
            direct_l_value=direct_l_value,
            direct_c_value=direct_c_value,
            name=name,
        )
    else:
        pass

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name

    neutral_voltage_var: Var | None = None
    neutral_current_var: Var | None = None
    ground_current_var: Var | None = None
    ground_block: Block | None = None
    grounding_link_block: Block | None = None

    # A grounded star point belongs to the device and is clamped by the
    # grounding-link child. It is not a fourth public terminal. NeutralStar is
    # the only topology that exposes the neutral conductor to the network.
    if connection_type == ShuntConnectionType.NeutralStar:
        neutral_voltage_var = vf.add_var(name=f"v_N", reference=VarPowerFlowReferenceType.v_N)
        in_vars.append(neutral_voltage_var)
    elif connection_type in {ShuntConnectionType.GroundedStar, ShuntConnectionType.FloatingStar}:
        neutral_voltage_var = vf.add_var(name=f"v_N_internal")
        algebraic_vars.append(neutral_voltage_var)
    else:
        raise ValueError("The EMT combined RLC implementation supports only star-connected or delta variants")

    if connection_type == ShuntConnectionType.GroundedStar:
        grounding_link_template: EmtModelTemplate = get_grounding_link_emt_template(
            vf=vf,
            include_r=False,
            include_l=False,
            include_c=False,
            solid_connection=True,
            nested=True,
            name=name + "_grounding_link",
        )
        vf.add_connections(grounding_link_template.block.in_vars, [neutral_voltage_var])
        ground_current_var = grounding_link_template.block.out_vars[0]
        grounding_link_block = grounding_link_template.block
        templ.block.add(grounding_link_block)
    else:
        pass

    for phase_label in active_phases:
        voltage_var: Var = vf.add_var(
            name=f"v_{phase_label}",
            reference=_get_voltage_reference(phase_label),
        )
        phase_voltage_vars[phase_label] = voltage_var
        in_vars.append(voltage_var)
        if include_l and direct_l_value is None and connection_type == ShuntConnectionType.GroundedStar:
            derivative_var = vf.add_var(name=f"d_v_{phase_label}")
            phase_derivative_vars[phase_label] = derivative_var
            templ.block.event_dict[derivative_var] = vf.add_const(0.0)

    pf_vm_var: Var | None = None
    omega_base_var: Var | None = None
    if direct_r_value is None and include_r:
        pf_vm_var = vf.add_var("Vm_pf_" + name)
        templ.block.event_dict[pf_vm_var] = vf.add_const(1.0)
    else:
        pass

    if (direct_l_value is None and include_l) or (direct_c_value is None and include_c):
        if pf_vm_var is None:
            pf_vm_var = vf.add_var("Vm_pf_" + name)
            templ.block.event_dict[pf_vm_var] = vf.add_const(1.0)
        else:
            pass

        omega_base_var = vf.add_var("w_base_" + name)
        templ.block.api_obj_mapping[ParamPowerFlowReferenceType.omega_base] = omega_base_var
        templ.block.parameters[omega_base_var] = vf.add_const(None)
    else:
        pass

    if connection_type == ShuntConnectionType.GroundedStar and pf_vm_var is not None:
        for phase_label in active_phases:
            phase_vm_var = vf.add_var(f"Vm_pf_{phase_label}_{name}")
            phase_vm_vars[phase_label] = phase_vm_var
            templ.block.event_dict[phase_vm_var] = vf.add_const(1.0)

    for phase_label in active_phases:
        total_current_var: Var = vf.add_var(
            name=f"i_{phase_label}",
            reference=_get_current_reference(phase_label),
        )
        total_current_vars[phase_label] = total_current_var
        algebraic_vars.append(total_current_var)
        out_vars.append(total_current_var)

        voltage_drop: Expr = phase_voltage_vars[phase_label] - neutral_voltage_var
        phase_vm_var = phase_vm_vars.get(phase_label, pf_vm_var)
        phase_current_expr: Expr = total_current_var

        if include_r:
            resistance_var: Var = vf.add_var(f"R_{phase_label}")
            component_vars[RESISTANCE_REFERENCES[phase_label]] = resistance_var
            if direct_r_value is None:
                pl0_var: Var = vf.add_var(f"Pl0_{phase_label}")
                templ.block.api_obj_mapping[_get_pl0_reference(phase_label)] = pl0_var
                templ.block.parameters[pl0_var] = vf.add_const(None)
                if pf_vm_var is None:
                    raise ValueError("Missing power-flow voltage magnitude for EMT RLC resistor initialization")
                else:
                    pass
                # Pl0_* is one-third of total power on the system three-phase
                # Sbase.  Convert it to the conventional phase-current base.
                templ.block.event_dict[resistance_var] = _get_power_conversion_voltage_squared(vf, phase_vm_var) / (vf.add_const(3.0) * pl0_var)
            else:
                templ.block.event_dict[resistance_var] = vf.add_const(float(direct_r_value), name=resistance_var.name)

            phase_current_expr = phase_current_expr + voltage_drop / resistance_var
        else:
            pass

        if include_l:
            inductance_var: Var = vf.add_var(f"L_{phase_label}")
            component_vars[INDUCTANCE_REFERENCES[phase_label]] = inductance_var
            if direct_l_value is None:
                ql0_var: Var = vf.add_var(f"Ql0_{phase_label}")
                templ.block.api_obj_mapping[_get_ql0_reference(phase_label)] = ql0_var
                templ.block.parameters[ql0_var] = vf.add_const(None)
                if pf_vm_var is None or omega_base_var is None:
                    raise ValueError("Missing base variables for EMT RLC inductive initialization")
                else:
                    pass
                templ.block.event_dict[inductance_var] = _get_power_conversion_voltage_squared(vf, phase_vm_var) / (
                    vf.add_const(3.0) * ql0_var * omega_base_var)
            else:
                templ.block.event_dict[inductance_var] = vf.add_const(float(direct_l_value), name=inductance_var.name)

            inductive_current_var: Var = vf.add_var(f"iL_{phase_label}")
            inductive_diff_var: Var = vf.add_diff_var(name=f"d_iL_{phase_label}", base_var=inductive_current_var)
            state_vars.append(inductive_current_var)
            inductive_current_vars[phase_label] = inductive_current_var
            inductance_vars[phase_label] = inductance_var
            diff_vars.append(inductive_diff_var)
            templ.block.diff_init_eqs[inductive_diff_var] = -voltage_drop / inductance_var
            state_eqs.append(-voltage_drop / inductance_var)
            phase_current_expr = phase_current_expr - inductive_current_var
        else:
            pass

        if include_c:
            capacitance_var: Var = vf.add_var(f"C_{phase_label}")
            component_vars[CAPACITANCE_REFERENCES[phase_label]] = capacitance_var
            if direct_c_value is None:
                ql0_var = vf.add_var(f"Ql0_{phase_label}")
                templ.block.api_obj_mapping[_get_ql0_reference(phase_label)] = ql0_var
                templ.block.parameters[ql0_var] = vf.add_const(None)
                if pf_vm_var is None or omega_base_var is None:
                    raise ValueError("Missing base variables for EMT RLC capacitive initialization")
                else:
                    pass
                templ.block.event_dict[capacitance_var] = (
                    -vf.add_const(3.0) * ql0_var
                    / (_get_power_conversion_voltage_squared(vf, phase_vm_var) * omega_base_var))
            else:
                templ.block.event_dict[capacitance_var] = vf.add_const(float(direct_c_value), name=capacitance_var.name)

            capacitor_current_var: Var = vf.add_var(f"iC_{phase_label}")
            capacitor_voltage_var: Var = vf.add_var(f"vCap{phase_label}")
            capacitor_voltage_diff_var: Var = vf.add_diff_var(
                name=f"dvCap{phase_label}",
                base_var=capacitor_voltage_var,
            )
            algebraic_vars.append(capacitor_current_var)
            state_vars.append(capacitor_voltage_var)
            diff_vars.append(capacitor_voltage_diff_var)
            templ.block.init_eqs[capacitor_voltage_var] = voltage_drop
            templ.block.diff_init_eqs[capacitor_voltage_diff_var] = -capacitor_current_var / capacitance_var
            state_eqs.append(-capacitor_current_var / capacitance_var)
            algebraic_eqs.append(capacitor_voltage_var - voltage_drop)
            phase_current_expr = phase_current_expr - capacitor_current_var
        else:
            pass

        algebraic_eqs.append(phase_current_expr)

    if (
            include_l
            and set(active_phases) == {"A", "B", "C"}
            and omega_base_var is not None
            and connection_type != ShuntConnectionType.GroundedStar
    ):
        sqrt_three = vf.add_const(np.sqrt(3.0))
        rotating_voltage = {
            "A": phase_voltage_vars["C"] - phase_voltage_vars["B"],
            "B": phase_voltage_vars["A"] - phase_voltage_vars["C"],
            "C": phase_voltage_vars["B"] - phase_voltage_vars["A"],
        }
        for phase_label in active_phases:
            templ.block.init_eqs[inductive_current_vars[phase_label]] = (
                rotating_voltage[phase_label]
                / (sqrt_three * omega_base_var * inductance_vars[phase_label])
            )
    elif include_l:
        for phase_label in active_phases:
            if phase_label in phase_derivative_vars:
                templ.block.init_eqs[inductive_current_vars[phase_label]] = (
                    phase_derivative_vars[phase_label]
                    / (omega_base_var ** 2 * inductance_vars[phase_label])
                )
            else:
                templ.block.init_eqs[inductive_current_vars[phase_label]] = vf.add_const(0.0)

    # Close the star-point KCL according to the selected physical connection.
    # Only NeutralStar exchanges a neutral current with the bus; GroundedStar
    # uses the current supplied by its internal grounding link.
    if connection_type == ShuntConnectionType.FloatingStar:
        neutral_kcl: Expr = vf.add_const(0.0)
        for phase_label in active_phases:
            neutral_kcl = neutral_kcl + total_current_vars[phase_label]
        algebraic_eqs.append(neutral_kcl)
    elif connection_type == ShuntConnectionType.NeutralStar:
        neutral_current_var = vf.add_var(name=f"i_N", reference=VarPowerFlowReferenceType.i_N)
        algebraic_vars.append(neutral_current_var)
        out_vars.insert(0, neutral_current_var)

        neutral_kcl = neutral_current_var
        for phase_label in active_phases:
            neutral_kcl = neutral_kcl + total_current_vars[phase_label]

        algebraic_eqs.append(neutral_kcl)
    elif connection_type == ShuntConnectionType.GroundedStar:
        if ground_current_var is None:
            raise ValueError("Grounded-star EMT RLC block requires one internal ground subblock")
        else:
            pass

        neutral_kcl = ground_current_var
        for phase_label in active_phases:
            neutral_kcl = neutral_kcl + total_current_vars[phase_label]

        algebraic_eqs.append(neutral_kcl)
        if grounding_link_block is not None:
            grounding_link_block.init_eqs[ground_current_var] = -sum(total_current_vars.values(), vf.add_const(0.0))
            ground_block = grounding_link_block.children[0]
            ground_block.init_eqs[ground_block.out_vars[0]] = -ground_current_var
        else:
            pass
    else:
        raise ValueError("The EMT combined RLC implementation supports only star-connected or delta variants")

    templ.block.in_vars = in_vars
    templ.block.out_vars = out_vars
    templ.block.algebraic_vars = algebraic_vars
    templ.block.algebraic_eqs = algebraic_eqs
    templ.block.state_vars = state_vars
    templ.block.state_eqs = state_eqs
    templ.block.diff_vars = diff_vars
    templ.block.external_mapping = _build_external_mapping(
        voltage_vars=phase_voltage_vars,
        current_vars=total_current_vars,
        neutral_voltage_var=neutral_voltage_var if connection_type == ShuntConnectionType.NeutralStar else None,
        neutral_current_var=neutral_current_var,
    )
    templ.block.external_mapping.update(component_vars)
    if pf_vm_var is not None:
        templ.block.external_mapping[VarPowerFlowReferenceType.VmSizing] = pf_vm_var
    for phase_label, derivative_var in phase_derivative_vars.items():
        templ.block.external_mapping[VarPowerFlowReferenceType[f"d_v_{phase_label}"]] = derivative_var
    for phase_label, phase_vm_var in phase_vm_vars.items():
        templ.block.external_mapping[VarPowerFlowReferenceType[f"Vm_{phase_label}"]] = phase_vm_var
    _attach_combo_editor_diagram(
        root_block=templ.block,
        input_vars=in_vars,
        output_vars=out_vars,
        ground_block=ground_block,
        neutral_input_var=neutral_voltage_var if connection_type == ShuntConnectionType.NeutralStar else None,
        grounding_link_block=grounding_link_block,
    )
    return templ
