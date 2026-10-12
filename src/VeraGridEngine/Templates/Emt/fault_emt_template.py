# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import math
import uuid

from typing import Dict, List

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp, Comparison, Const, Expr, Var
from VeraGridEngine.enumerations import BlockType, DeviceType, EmtFaultPlacementSide, FaultType


class FaultEmtTemplate(TemplateDefinition):
    """Configurable builder for one internal EMT fault insertion block."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create one valid single-line-to-ground default definition.

        :param vf: EMT variable factory used to create the symbolic model.
        :return: None.
        """
        super().__init__(vf, params=[
            TemplateProp(name="fault_type", units="", descr="Requested short-circuit topology.", tpe=FaultType | str, value=FaultType.LG),
            TemplateProp(name="placement_side", units="", descr="Semantic placement side inside the composed branch.", tpe=EmtFaultPlacementSide | str, value=EmtFaultPlacementSide.FromSide),
            TemplateProp(name="phA", units="", descr="Enable phase A.", tpe=bool, value=True),
            TemplateProp(name="phB", units="", descr="Enable phase B.", tpe=bool, value=False),
            TemplateProp(name="phC", units="", descr="Enable phase C.", tpe=bool, value=False),
            TemplateProp(name="signal_controlled", units="", descr="If True, expose one control input and procedural logic.", tpe=bool, value=False),
            TemplateProp(name="initial_closed", units="", descr="Initial fault status.", tpe=bool, value=False),
            TemplateProp(name="fault_resistance", units="p.u.", descr="Closed phase-path resistance on the parent EMT base.", tpe=float, value=1.0e-2),
            TemplateProp(name="ground_resistance", units="p.u.", descr="Closed common-node-to-ground resistance on the parent EMT base.", tpe=float, value=1.0e-2),
            TemplateProp(name="open_conductance", units="p.u.", descr="Open-state leakage conductance on the parent EMT base.", tpe=float, value=1.0e-8),
            TemplateProp(name="fault_time_constant", units="s", descr="Unused regularization compatibility parameter.", tpe=float, value=1.0e-4),
            TemplateProp(name="command_threshold", units="", descr="Control threshold for the external command.", tpe=float, value=0.5),
            TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str, value="fault_emt_template"),
        ])

    def eval(self) -> EmtModelTemplate:
        """Build the EMT model from the current typed property values.

        :return: Configured EMT fault model template.
        """
        return get_fault_emt_template(
            self.vf,
            self.get_value("fault_type"),
            self.get_value("placement_side"),
            self.get_value("phA"),
            self.get_value("phB"),
            self.get_value("phC"),
            self.get_value("signal_controlled"),
            self.get_value("initial_closed"),
            self.get_value("fault_resistance"),
            self.get_value("ground_resistance"),
            self.get_value("open_conductance"),
            self.get_value("fault_time_constant"),
            self.get_value("command_threshold"),
            self.get_value("name"),
        )


def _get_active_phases(phA: bool, phB: bool, phC: bool) -> List[str]:
    """
    Return the enabled phase labels in deterministic A-B-C order.

    :param phA: True when phase A is active.
    :param phB: True when phase B is active.
    :param phC: True when phase C is active.
    :return: Ordered list of active phase labels.
    """
    active_phases: List[str] = list()

    if phA:
        active_phases.append("A")
    else:
        pass

    if phB:
        active_phases.append("B")
    else:
        pass

    if phC:
        active_phases.append("C")
    else:
        pass

    if len(active_phases) == 0:
        raise ValueError("At least one phase must be enabled for an EMT fault template")
    else:
        return active_phases


def _coerce_fault_type(fault_type: FaultType | str) -> FaultType:
    """
    Coerce one incoming fault selector into the project fault enum.

    :param fault_type: Enum instance or textual fault selector.
    :return: Coerced fault enum.
    """
    if isinstance(fault_type, FaultType):
        return fault_type
    else:
        return FaultType.argparse(str(fault_type))


def _coerce_fault_placement_side(placement_side: EmtFaultPlacementSide | str) -> EmtFaultPlacementSide:
    """
    Coerce one incoming placement selector into the placement-side enum.

    :param placement_side: Enum instance or textual selector.
    :return: Coerced placement-side enum.
    """
    if isinstance(placement_side, EmtFaultPlacementSide):
        return placement_side
    else:
        return EmtFaultPlacementSide.argparse(str(placement_side))


def validate_fault_phase_selection(fault_type: FaultType | str,
                                   phA: bool,
                                   phB: bool,
                                   phC: bool) -> FaultType:
    """
    Validate that the selected active phases match one supported EMT fault topology.

    :param fault_type: Requested short-circuit topology.
    :param phA: Enable phase A.
    :param phB: Enable phase B.
    :param phC: Enable phase C.
    :return: Resolved fault type.
    :raises ValueError: If the phase mask is inconsistent with the topology.
    """
    resolved_fault_type: FaultType = _coerce_fault_type(fault_type)
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)

    if resolved_fault_type == FaultType.LG:
        if len(active_phases) != 1:
            raise ValueError("EMT LG faults require exactly one active phase")
    elif resolved_fault_type == FaultType.LL:
        if len(active_phases) != 2:
            raise ValueError("EMT LL faults require exactly two active phases")
    elif resolved_fault_type == FaultType.LLG:
        if len(active_phases) != 2:
            raise ValueError("EMT LLG faults require exactly two active phases")
    elif resolved_fault_type == FaultType.LLL:
        if active_phases != list(["A", "B", "C"]):
            raise ValueError("EMT LLL faults require phases A, B and C")
    elif resolved_fault_type == FaultType.LLLG:
        if active_phases != list(["A", "B", "C"]):
            raise ValueError("EMT LLLG faults require phases A, B and C")
    else:
        raise ValueError(f"Unsupported EMT fault type '{resolved_fault_type}'")

    return resolved_fault_type


def validate_fault_electrical_parameters(fault_resistance: float,
                                         ground_resistance: float,
                                         open_conductance: float,
                                         fault_time_constant: float,
                                         command_threshold: float) -> None:
    """Validate the finite scalar parameters used by one EMT fault block.

    Resistances must be strictly positive because their reciprocals enter the
    algebraic equations. The open-state leakage may be zero, while the retained
    compatibility time constant must remain positive for old saved settings.

    :param fault_resistance: Closed phase-path resistance in p.u.
    :param ground_resistance: Closed common-node-to-ground resistance in p.u.
    :param open_conductance: Open-state leakage conductance in p.u.
    :param fault_time_constant: Legacy compatibility time constant in seconds.
    :param command_threshold: External command comparison threshold.
    :return: None.
    :raises ValueError: If one value is non-finite or outside its valid range.
    """
    if math.isfinite(fault_resistance) and fault_resistance > 0.0:
        pass
    else:
        raise ValueError("EMT fault resistance must be finite and strictly positive")

    if math.isfinite(ground_resistance) and ground_resistance > 0.0:
        pass
    else:
        raise ValueError("EMT fault ground resistance must be finite and strictly positive")

    if math.isfinite(open_conductance) and open_conductance >= 0.0:
        pass
    else:
        raise ValueError("EMT fault open conductance must be finite and non-negative")

    if math.isfinite(fault_time_constant) and fault_time_constant > 0.0:
        pass
    else:
        raise ValueError("EMT fault compatibility time constant must be finite and strictly positive")

    if math.isfinite(command_threshold):
        pass
    else:
        raise ValueError("EMT fault command threshold must be finite")


def _create_editor_connection_child(var: Var, is_input: bool, name: str) -> Block:
    """
    Build one visual-only connection child used by the hierarchy editor.

    :param var: Shared root-port variable.
    :param is_input: True for one input connector.
    :param name: Child block name.
    :return: Lightweight block exposing the shared variable.
    """
    child_block: Block = Block(name=name)

    if is_input:
        child_block.out_vars.append(var)
    else:
        child_block.in_vars.append(var)

    return child_block


def _attach_fault_editor_diagram(root_block: Block,
                                 input_vars: List[Var],
                                 output_vars: List[Var],
                                 active_phases: List[str],
                                 fault_type: FaultType,
                                 placement_side: EmtFaultPlacementSide) -> None:
    """
    Attach one persisted hierarchy diagram for one internal EMT fault block.

    :param root_block: Root fault block.
    :param input_vars: Public input variables.
    :param output_vars: Public output variables.
    :param active_phases: Ordered active phases.
    :param fault_type: Electrical topology represented by the internal projection.
    :param placement_side: Whether the block sits at the branch from or to side.
    :return: None.
    """
    input_blocks_by_name: Dict[str, Block] = dict()
    output_blocks_by_name: Dict[str, Block] = dict()
    phase_node_blocks: Dict[str, Block] = dict()
    input_index: int
    output_index: int
    phase_index: int
    input_var: Var
    output_var: Var
    placement_label: str = "From" if placement_side == EmtFaultPlacementSide.FromSide else "To"

    for input_index, input_var in enumerate(input_vars):
        input_block: Block = _create_editor_connection_child(var=input_var, is_input=True, name=input_var.name)
        root_block.add(input_block)
        root_block.diagram.add_node(
            name=input_block.name,
            x=40.0,
            y=70.0 + 60.0 * float(input_index),
            tpe=BlockType.INPUT_CONN.name,
            device_uid=input_block.uid,
        )
        input_blocks_by_name[input_var.name] = input_block

    for output_index, output_var in enumerate(output_vars):
        output_block: Block = _create_editor_connection_child(var=output_var, is_input=False, name=output_var.name)
        root_block.add(output_block)
        root_block.diagram.add_node(
            name=output_block.name,
            x=690.0,
            y=70.0 + 60.0 * float(output_index),
            tpe=BlockType.OUTPUT_CONN.name,
            device_uid=output_block.uid,
        )
        output_blocks_by_name[output_var.name] = output_block

    for phase_index, phase_label in enumerate(active_phases):
        phase_node_block: Block = Block(name=f"{placement_label} Phase {phase_label} Node")
        root_block.add(phase_node_block)
        root_block.diagram.add_node(
            name=phase_node_block.name,
            x=330.0,
            y=130.0 + 110.0 * float(phase_index),
            tpe=BlockType.GROUNDING_LINK_EMT.name,
            device_uid=phase_node_block.uid,
        )
        phase_node_blocks[phase_label] = phase_node_block

        # The projection shows the actual series insertion contract. Voltage
        # propagates outer-to-inner, while the current ports share the same
        # physical split node and use their equation-defined orientation.
        root_block.diagram.add_branch(
            connectionitem_uid=uuid.uuid4().int,
            device_uid_from=input_blocks_by_name[f"v_outer_{phase_label}"].uid,
            device_uid_to=phase_node_block.uid,
            port_number_from=0,
            port_number_to=0,
            color="#587291",
        )
        root_block.diagram.add_branch(
            connectionitem_uid=uuid.uuid4().int,
            device_uid_from=phase_node_block.uid,
            device_uid_to=output_blocks_by_name[f"v_inner_{phase_label}"].uid,
            port_number_from=0,
            port_number_to=0,
            color="#587291",
        )
        root_block.diagram.add_branch(
            connectionitem_uid=uuid.uuid4().int,
            device_uid_from=input_blocks_by_name[f"i_inner_{phase_label}"].uid,
            device_uid_to=phase_node_block.uid,
            port_number_from=0,
            port_number_to=0,
            color="#9b6a3c",
        )
        root_block.diagram.add_branch(
            connectionitem_uid=uuid.uuid4().int,
            device_uid_from=phase_node_block.uid,
            device_uid_to=output_blocks_by_name[f"i_outer_{phase_label}"].uid,
            port_number_from=0,
            port_number_to=0,
            color="#9b6a3c",
        )

    if fault_type == FaultType.LG or fault_type == FaultType.LLLG:
        ground_block: Block = Block(name="Fault Ground")
        root_block.add(ground_block)
        root_block.diagram.add_node(
            name=ground_block.name,
            x=500.0,
            y=90.0 + 110.0 * float(len(active_phases)),
            tpe=BlockType.GROUND_EMT.name,
            device_uid=ground_block.uid,
        )

        for phase_label in active_phases:
            root_block.diagram.add_branch(
                connectionitem_uid=uuid.uuid4().int,
                device_uid_from=phase_node_blocks[phase_label].uid,
                device_uid_to=ground_block.uid,
                port_number_from=0,
                port_number_to=0,
                color="#587291",
            )
    elif fault_type == FaultType.LL:
        root_block.diagram.add_branch(
            connectionitem_uid=uuid.uuid4().int,
            device_uid_from=phase_node_blocks[active_phases[0]].uid,
            device_uid_to=phase_node_blocks[active_phases[1]].uid,
            port_number_from=0,
            port_number_to=0,
            color="#b33a3a",
        )
    elif fault_type == FaultType.LLG or fault_type == FaultType.LLL:
        common_node_block: Block = Block(name="Fault Common Node")
        root_block.add(common_node_block)
        root_block.diagram.add_node(
            name=common_node_block.name,
            x=500.0,
            y=130.0 + 55.0 * float(len(active_phases)),
            tpe=BlockType.GROUNDING_LINK_EMT.name,
            device_uid=common_node_block.uid,
        )

        for phase_label in active_phases:
            root_block.diagram.add_branch(
                connectionitem_uid=uuid.uuid4().int,
                device_uid_from=phase_node_blocks[phase_label].uid,
                device_uid_to=common_node_block.uid,
                port_number_from=0,
                port_number_to=0,
                color="#b33a3a",
            )

        if fault_type == FaultType.LLG:
            common_ground_block: Block = Block(name="Fault Ground")
            root_block.add(common_ground_block)
            root_block.diagram.add_node(
                name=common_ground_block.name,
                x=620.0,
                y=130.0 + 55.0 * float(len(active_phases)),
                tpe=BlockType.GROUND_EMT.name,
                device_uid=common_ground_block.uid,
            )
            root_block.diagram.add_branch(
                connectionitem_uid=uuid.uuid4().int,
                device_uid_from=common_node_block.uid,
                device_uid_to=common_ground_block.uid,
                port_number_from=0,
                port_number_to=0,
                color="#587291",
            )
        else:
            pass
    else:
        raise ValueError(f"Unsupported EMT fault type '{fault_type}'")


def _build_lg_fault_equations(active_phases: List[str],
                              phase_inner_voltage_vars: Dict[str, Var],
                              phase_fault_current_exprs: Dict[str, Expr],
                              g_fault_eff: Expr,
                              algebraic_vars: List[Var],
                              algebraic_eqs: List[Expr],
                              vf: VarFactory) -> None:
    """
    Build one single-line-to-ground fault topology.

    :param active_phases: Ordered active phases.
    :param phase_inner_voltage_vars: Inner phase voltages.
    :param phase_fault_current_exprs: Fault current accumulators by phase.
    :param g_fault_eff: Effective grounding conductance.
    :param algebraic_vars: Root algebraic variable list to extend.
    :param algebraic_eqs: Root algebraic equation list to extend.
    :param vf: EMT variable factory.
    :return: None.
    """
    phase_label: str = active_phases[0]
    i_fault_var: Var = vf.add_var(f"i_fault_{phase_label}G")
    algebraic_vars.append(i_fault_var)
    algebraic_eqs.append(i_fault_var - g_fault_eff * phase_inner_voltage_vars[phase_label])
    phase_fault_current_exprs[phase_label] = phase_fault_current_exprs[phase_label] + i_fault_var


def _build_ll_fault_equations(active_phases: List[str],
                              phase_inner_voltage_vars: Dict[str, Var],
                              phase_fault_current_exprs: Dict[str, Expr],
                              g_fault_eff: Expr,
                              algebraic_vars: List[Var],
                              algebraic_eqs: List[Expr],
                              vf: VarFactory) -> None:
    """
    Build one line-to-line fault topology with one algebraic branch current.

    :param active_phases: Ordered active phases.
    :param phase_inner_voltage_vars: Inner phase voltages.
    :param phase_fault_current_exprs: Fault current accumulators by phase.
    :param g_fault_eff: Effective line-to-line conductance.
    :param algebraic_vars: Root algebraic variable list to extend.
    :param algebraic_eqs: Root algebraic equation list to extend.
    :param vf: EMT variable factory.
    :return: None.
    """
    phase_a: str = active_phases[0]
    phase_b: str = active_phases[1]
    i_fault_var: Var = vf.add_var(f"i_fault_{phase_a}{phase_b}")
    algebraic_vars.append(i_fault_var)
    algebraic_eqs.append(i_fault_var - g_fault_eff * (phase_inner_voltage_vars[phase_a] - phase_inner_voltage_vars[phase_b]))
    phase_fault_current_exprs[phase_a] = phase_fault_current_exprs[phase_a] + i_fault_var
    phase_fault_current_exprs[phase_b] = phase_fault_current_exprs[phase_b] - i_fault_var


def _build_llg_fault_equations(active_phases: List[str],
                               phase_inner_voltage_vars: Dict[str, Var],
                               phase_fault_current_exprs: Dict[str, Expr],
                               g_phase_eff: Expr,
                               g_ground_eff: Expr,
                               algebraic_vars: List[Var],
                               algebraic_eqs: List[Expr],
                               vf: VarFactory) -> None:
    """
    Build one line-line-ground fault topology using a grounded common node.

    :param active_phases: Ordered active phases.
    :param phase_inner_voltage_vars: Inner phase voltages.
    :param phase_fault_current_exprs: Fault current accumulators by phase.
    :param g_phase_eff: Effective phase-to-common-node conductance.
    :param g_ground_eff: Effective common-node-to-ground conductance.
    :param algebraic_vars: Root algebraic variable list to extend.
    :param algebraic_eqs: Root algebraic equation list to extend.
    :param vf: EMT variable factory.
    :return: None.
    """
    fault_node_voltage_var: Var = vf.add_var(f"v_fault_node")
    i_fault_a_var: Var = vf.add_var(f"i_fault_{active_phases[0]}N")
    i_fault_b_var: Var = vf.add_var(f"i_fault_{active_phases[1]}N")

    algebraic_vars.append(fault_node_voltage_var)
    algebraic_vars.append(i_fault_a_var)
    algebraic_vars.append(i_fault_b_var)

    algebraic_eqs.append(i_fault_a_var - g_phase_eff * (phase_inner_voltage_vars[active_phases[0]] - fault_node_voltage_var))
    algebraic_eqs.append(i_fault_b_var - g_phase_eff * (phase_inner_voltage_vars[active_phases[1]] - fault_node_voltage_var))
    algebraic_eqs.append(i_fault_a_var + i_fault_b_var - g_ground_eff * fault_node_voltage_var)

    phase_fault_current_exprs[active_phases[0]] = phase_fault_current_exprs[active_phases[0]] + i_fault_a_var
    phase_fault_current_exprs[active_phases[1]] = phase_fault_current_exprs[active_phases[1]] + i_fault_b_var


def _build_lll_fault_equations(active_phases: List[str],
                               phase_inner_voltage_vars: Dict[str, Var],
                               phase_fault_current_exprs: Dict[str, Expr],
                               g_fault_eff: Expr,
                               algebraic_vars: List[Var],
                               algebraic_eqs: List[Expr],
                               vf: VarFactory) -> None:
    """
    Build one balanced three-phase line-to-line fault using a floating common node.

    This is the symmetric representation required for an ungrounded ``LLL`` fault.
    All three phases connect with equal conductance to one floating fault node,
    which ensures balanced phase currents and ``i_A + i_B + i_C = 0``.

    :param active_phases: Ordered active phases.
    :param phase_inner_voltage_vars: Inner phase voltages.
    :param phase_fault_current_exprs: Fault current accumulators by phase.
    :param g_fault_eff: Effective fault conductance.
    :param algebraic_vars: Root algebraic variable list to extend.
    :param algebraic_eqs: Root algebraic equation list to extend.
    :param vf: EMT variable factory.
    :return: None.
    """
    fault_node_voltage_var: Var = vf.add_var(f"v_fault_node")
    i_fault_a_var: Var = vf.add_var(f"i_fault_AN")
    i_fault_b_var: Var = vf.add_var(f"i_fault_BN")
    i_fault_c_var: Var = vf.add_var(f"i_fault_CN")

    algebraic_vars.append(fault_node_voltage_var)
    algebraic_vars.append(i_fault_a_var)
    algebraic_vars.append(i_fault_b_var)
    algebraic_vars.append(i_fault_c_var)

    algebraic_eqs.append(i_fault_a_var - g_fault_eff * (phase_inner_voltage_vars["A"] - fault_node_voltage_var))
    algebraic_eqs.append(i_fault_b_var - g_fault_eff * (phase_inner_voltage_vars["B"] - fault_node_voltage_var))
    algebraic_eqs.append(i_fault_c_var - g_fault_eff * (phase_inner_voltage_vars["C"] - fault_node_voltage_var))
    algebraic_eqs.append(i_fault_a_var + i_fault_b_var + i_fault_c_var)

    phase_fault_current_exprs["A"] = phase_fault_current_exprs["A"] + i_fault_a_var
    phase_fault_current_exprs["B"] = phase_fault_current_exprs["B"] + i_fault_b_var
    phase_fault_current_exprs["C"] = phase_fault_current_exprs["C"] + i_fault_c_var


def _build_lllg_fault_equations(active_phases: List[str],
                                phase_inner_voltage_vars: Dict[str, Var],
                                phase_fault_current_exprs: Dict[str, Expr],
                                g_fault_eff: Expr,
                                algebraic_vars: List[Var],
                                algebraic_eqs: List[Expr],
                                vf: VarFactory) -> None:
    """
    Build one balanced three-phase-to-ground fault using a grounded common node.

    :param active_phases: Ordered active phases.
    :param phase_inner_voltage_vars: Inner phase voltages.
    :param phase_fault_current_exprs: Fault current accumulators by phase.
    :param g_fault_eff: Effective phase-to-ground conductance.
    :param algebraic_vars: Root algebraic variable list to extend.
    :param algebraic_eqs: Root algebraic equation list to extend.
    :param vf: EMT variable factory.
    :return: None.
    """
    phase_label: str

    for phase_label in active_phases:
        i_fault_var: Var = vf.add_var(f"i_fault_{phase_label}G")
        algebraic_vars.append(i_fault_var)
        algebraic_eqs.append(i_fault_var - g_fault_eff * phase_inner_voltage_vars[phase_label])
        phase_fault_current_exprs[phase_label] = phase_fault_current_exprs[phase_label] + i_fault_var


def get_fault_emt_template(
    vf: VarFactory,
    fault_type: FaultType | str = FaultType.LG,
    placement_side: EmtFaultPlacementSide | str = EmtFaultPlacementSide.FromSide,
    phA: bool = True,
    phB: bool = False,
    phC: bool = False,
    signal_controlled: bool = False,
    initial_closed: bool = False,
    fault_resistance: float = 1.0e-2,
    ground_resistance: float = 1.0e-2,
    open_conductance: float = 1.0e-8,
    fault_time_constant: float = 1.0e-4,
    command_threshold: float = 0.5,
    name: str = "fault_emt_template",
) -> EmtModelTemplate:
    """
    Build one internal-composition EMT fault block with explicit outer/inner ports.

    The block is intended for use inside one parent branch composition built in the
    dynamic block editor. It uses one explicit pass-through interface:

    - ``v_outer_*``: incoming branch-side voltage input.
    - ``i_inner_*``: incoming downstream current input.
    - ``v_inner_*``: outgoing downstream voltage algebraic/output.
    - ``i_outer_*``: outgoing upstream current algebraic/output.

    The block enforces the zero-impedance pass-through through the explicit
    algebraic equations ``v_inner_* = v_outer_*``. The physical fault
    current itself is algebraic, not dynamic, so it is limited by the actual line
    and source impedances rather than one artificial very-fast first-order state.

    :param vf: EMT variable factory.
    :param fault_type: Requested short-circuit topology.
    :param placement_side: Placement side inside the composed branch.
    :param phA: Enable phase A.
    :param phB: Enable phase B.
    :param phC: Enable phase C.
    :param signal_controlled: If True, expose one control input and procedural logic.
    :param initial_closed: Initial fault status.
    :param fault_resistance: Closed phase-path resistance in p.u.
    :param ground_resistance: Closed common-node-to-ground resistance in p.u.
    :param open_conductance: Open-state leakage conductance in p.u.
    :param fault_time_constant: Unused regularization compatibility parameter.
    :param command_threshold: Control threshold for the external command.
    :param name: Symbolic model name.
    :return: EMT fault template.
    """
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    resolved_fault_type: FaultType = validate_fault_phase_selection(
        fault_type=fault_type,
        phA=phA,
        phB=phB,
        phC=phC,
    )
    resolved_placement_side: EmtFaultPlacementSide = _coerce_fault_placement_side(placement_side)
    validate_fault_electrical_parameters(
        fault_resistance=fault_resistance,
        ground_resistance=ground_resistance,
        open_conductance=open_conductance,
        fault_time_constant=fault_time_constant,
        command_threshold=command_threshold,
    )
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.SwitchDevice
    templ.name = name
    templ.block.name = name
    templ.block.external_mapping = dict()

    closed_mode: Var = vf.add_var(f"fault_closed_mode")
    templ.block.mode_dict[closed_mode] = Const(1.0 if initial_closed else 0.0, name="fault_closed_mode")

    fault_r_var: Var = vf.add_var(f"fault_r")
    ground_r_var: Var = vf.add_var(f"fault_rg")
    g_open_var: Var = vf.add_var(f"fault_open_g")
    tau_var: Var = vf.add_var(f"fault_tau")
    templ.block.event_dict[fault_r_var] = Const(float(fault_resistance), name="fault_r")
    templ.block.event_dict[ground_r_var] = Const(float(ground_resistance), name="fault_rg")
    templ.block.event_dict[g_open_var] = Const(float(open_conductance), name="fault_open_g")
    templ.block.event_dict[tau_var] = Const(float(fault_time_constant), name="fault_tau")

    g_fault_eff: Expr = closed_mode * (Const(1.0) / fault_r_var) + (Const(1.0) - closed_mode) * g_open_var
    g_ground_eff: Expr = closed_mode * (Const(1.0) / ground_r_var) + (Const(1.0) - closed_mode) * g_open_var

    in_vars: List[Var] = list()
    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    state_eqs: List[Expr] = list()
    out_vars: List[Var] = list()

    phase_inner_voltage_vars: Dict[str, Var] = dict()
    phase_inner_current_vars: Dict[str, Var] = dict()
    phase_outer_current_vars: Dict[str, Var] = dict()
    phase_fault_current_exprs: Dict[str, Expr] = dict()

    if signal_controlled:
        command_input: Var = vf.add_var(f"fault_cmd")
        threshold_var: Var = vf.add_var(f"fault_cmd_threshold")
        templ.block.event_dict[threshold_var] = vf.add_const(float(command_threshold), name="fault_cmd_threshold")
        templ.block.procedural_logic.append(
            sampled_value(output=closed_mode, source=Comparison(lhs=command_input, op=CmpOp.GE, rhs=threshold_var))
        )
        in_vars.append(command_input)
    else:
        pass

    phase_label: str
    for phase_label in active_phases:
        v_outer_var: Var = vf.add_var(f"v_outer_{phase_label}")
        i_inner_var: Var = vf.add_var(f"i_inner_{phase_label}")
        v_inner_var: Var = vf.add_var(f"v_inner_{phase_label}")
        i_outer_var: Var = vf.add_var(f"i_outer_{phase_label}")

        in_vars.append(v_outer_var)
        in_vars.append(i_inner_var)
        algebraic_vars.append(v_inner_var)
        algebraic_vars.append(i_outer_var)
        out_vars.append(v_inner_var)
        out_vars.append(i_outer_var)

        # A fault is a zero-impedance series insertion with one shunt path at
        # the split node. Owning continuity here makes the block complete in
        # every parent composition and avoids a free algebraic voltage.
        algebraic_eqs.append(v_inner_var - v_outer_var)
        phase_inner_voltage_vars[phase_label] = v_inner_var
        phase_inner_current_vars[phase_label] = i_inner_var
        phase_outer_current_vars[phase_label] = i_outer_var
        phase_fault_current_exprs[phase_label] = vf.add_const(0.0)

    if resolved_fault_type == FaultType.LG:
        _build_lg_fault_equations(
            active_phases=active_phases,
            phase_inner_voltage_vars=phase_inner_voltage_vars,
            phase_fault_current_exprs=phase_fault_current_exprs,
            g_fault_eff=g_ground_eff,
            algebraic_vars=algebraic_vars,
            algebraic_eqs=algebraic_eqs,
            vf=vf,
        )
    else:
        if resolved_fault_type == FaultType.LL:
            _build_ll_fault_equations(
                active_phases=active_phases,
                phase_inner_voltage_vars=phase_inner_voltage_vars,
                phase_fault_current_exprs=phase_fault_current_exprs,
                g_fault_eff=g_fault_eff,
                algebraic_vars=algebraic_vars,
                algebraic_eqs=algebraic_eqs,
                vf=vf,
            )
        else:
            if resolved_fault_type == FaultType.LLG:
                _build_llg_fault_equations(
                    active_phases=active_phases,
                    phase_inner_voltage_vars=phase_inner_voltage_vars,
                    phase_fault_current_exprs=phase_fault_current_exprs,
                    g_phase_eff=g_fault_eff,
                    g_ground_eff=g_ground_eff,
                    algebraic_vars=algebraic_vars,
                    algebraic_eqs=algebraic_eqs,
                    vf=vf,
                )
            else:
                if resolved_fault_type == FaultType.LLL:
                    _build_lll_fault_equations(
                        active_phases=active_phases,
                        phase_inner_voltage_vars=phase_inner_voltage_vars,
                        phase_fault_current_exprs=phase_fault_current_exprs,
                        g_fault_eff=g_fault_eff,
                        algebraic_vars=algebraic_vars,
                        algebraic_eqs=algebraic_eqs,
                        vf=vf,
                    )
                else:
                    if resolved_fault_type == FaultType.LLLG:
                        _build_lllg_fault_equations(
                            active_phases=active_phases,
                            phase_inner_voltage_vars=phase_inner_voltage_vars,
                            phase_fault_current_exprs=phase_fault_current_exprs,
                            g_fault_eff=g_ground_eff,
                            algebraic_vars=algebraic_vars,
                            algebraic_eqs=algebraic_eqs,
                            vf=vf,
                        )
                    else:
                        raise ValueError(f"Unsupported EMT fault type '{resolved_fault_type}'")

    for phase_label in active_phases:
        # The parent fault port returns the downstream current plus the physical
        # fault current that leaves the internal split node through the fault path.
        algebraic_eqs.append(
            phase_outer_current_vars[phase_label]
            - phase_inner_current_vars[phase_label]
            - phase_fault_current_exprs[phase_label]
        )

    templ.block.in_vars = in_vars
    templ.block.state_vars = state_vars
    templ.block.diff_vars = diff_vars
    templ.block.algebraic_vars = algebraic_vars
    templ.block.state_eqs = state_eqs
    templ.block.algebraic_eqs = algebraic_eqs
    templ.block.out_vars = out_vars
    templ.block.init_eqs = dict()
    templ.block.diff_init_eqs = dict()

    _attach_fault_editor_diagram(
        root_block=templ.block,
        input_vars=in_vars,
        output_vars=out_vars,
        active_phases=active_phases,
        fault_type=resolved_fault_type,
        placement_side=resolved_placement_side,
    )
    return templ
