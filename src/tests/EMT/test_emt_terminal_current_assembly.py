# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Callable, Dict, List

import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Simulations.EMT.problems.emt_terminal_current_assembly import (
    assemble_emt_mapped_current_references,
)
from VeraGridEngine.Templates.Emt.dc_load_emt_template import (
    get_dc_load_emt_template,
)
from VeraGridEngine.Templates.Emt.converter_emt_template import (
    get_emt_ideal_converter,
    get_full_pseudo_emt_converter,
)
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import (
    get_grounding_link_emt_template,
)
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    EmtTerminalConductor,
    EmtTerminalCurrentContribution,
    EmtTerminalSide,
    has_emt_internal_grounding_link,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, get_expression_vars
from VeraGridEngine.enumerations import BlockType, VarPowerFlowReferenceType


def _serialize_grounding_contract_as_version_three(block: Block) -> dict[str, object]:
    """Downgrade one grounding block fixture to its pre-typed contract shape.

    :param block: Canonical grounding block used by the migration test.
    :return: Declarative version-three record for the parent and ideal-ground child.
    """
    legacy_data: dict[str, object] = block.to_dict()
    legacy_contract: object = legacy_data["dynamic_model_contract"]
    assert isinstance(legacy_contract, dict)
    legacy_contract["version"] = 3
    legacy_contract["rms_terminal_power_contributions"] = []
    legacy_contract.pop("emt_internal_grounding_link")
    legacy_contract.pop("rms_physical_measurement_point")

    # The child is parsed first, so its own contract must also match the legacy
    # schema before the parent migration inspects their shared symbolic UIDs.
    legacy_children_data: object = legacy_data["children"]
    assert isinstance(legacy_children_data, list)
    legacy_child_data: object
    for legacy_child_data in legacy_children_data:
        assert isinstance(legacy_child_data, dict)
        legacy_child_contract: object = legacy_child_data["dynamic_model_contract"]
        assert isinstance(legacy_child_contract, dict)
        legacy_child_contract["version"] = 3
        legacy_child_contract["rms_terminal_power_contributions"] = []
        legacy_child_contract.pop("emt_internal_grounding_link")
        legacy_child_contract.pop("rms_physical_measurement_point")
    else:
        pass
    return legacy_data


def test_emt_grounding_uses_canonical_blocks_not_diagram_projection() -> None:
    """Keep editor layout from becoming an electrical grounding authority.

    :return: None.
    """
    projected_model: Block = Block(name="projected_model")
    projected_model.diagram.add_node(
        name="drawn_ground",
        x=0.0,
        y=0.0,
        tpe=BlockType.GROUNDING_LINK_EMT.name,
        device_uid=1,
    )
    grounding_block: Block = get_grounding_link_emt_template(
        vf=VarFactory(),
        include_r=True,
        include_l=False,
        include_c=False,
        nested=True,
        direct_r_value=1.0,
        name="renamed_without_magic_suffix",
    ).block
    grounding_block.diagram.node_data.clear()
    grounding_block.diagram.con_data.clear()
    canonical_model: Block = Block(
        name="canonical_model",
        children=list((grounding_block,)),
    )
    restored_model: Block = Block.parse(data=canonical_model.to_dict())
    decoy_grounding_block: Block = Block.parse(data=grounding_block.to_dict())
    decoy_grounding_block.dynamic_model_contract.emt_internal_grounding_link = False
    isolated_voltage: Var = Var(name="isolated_voltage")
    decoy_ground_block: Block = decoy_grounding_block.children[0]
    decoy_ground_block.in_vars[0] = isolated_voltage
    decoy_ground_block.algebraic_eqs[0] = isolated_voltage
    legacy_grounding_data: dict[str, object] = (
        _serialize_grounding_contract_as_version_three(block=grounding_block)
    )
    legacy_restored_grounding: Block = Block.parse(data=legacy_grounding_data)
    legacy_decoy_data: dict[str, object] = (
        _serialize_grounding_contract_as_version_three(block=decoy_grounding_block)
    )
    legacy_restored_decoy: Block = Block.parse(data=legacy_decoy_data)

    assert not has_emt_internal_grounding_link(block=projected_model)
    assert not has_emt_internal_grounding_link(block=legacy_restored_decoy)
    assert canonical_model.diagram.empty()
    assert has_emt_internal_grounding_link(block=canonical_model)
    assert has_emt_internal_grounding_link(block=restored_model)
    assert legacy_restored_grounding.dynamic_model_contract.emt_internal_grounding_link
    assert legacy_restored_grounding.in_vars[0].ref is VarPowerFlowReferenceType.v_N
    assert legacy_restored_grounding.out_vars[0].ref is VarPowerFlowReferenceType.i_N
    assert has_emt_internal_grounding_link(block=legacy_restored_grounding)


def test_standard_dc_load_uses_mapped_emt_terminal_current() -> None:
    """Keep a native one-terminal EMT device on mapped KCL assembly.

    :return: None.
    """
    model: Block = get_dc_load_emt_template(vf=VarFactory()).block
    contributions: List[EmtTerminalCurrentContribution] = (
        model.dynamic_model_contract.emt_terminal_current_contributions
    )

    assert contributions == list()
    assert VarPowerFlowReferenceType.Idc in model.external_mapping


@pytest.mark.parametrize(
    "builder",
    (get_emt_ideal_converter, get_full_pseudo_emt_converter),
)
def test_converter_templates_use_side_specific_mapped_currents(
        builder: Callable[[VarFactory], EmtModelTemplate],
) -> None:
    """Assemble converter DC/from and AC/to currents without terminal metadata.

    :param builder: Converter template builder under test.
    :return: None.
    """
    model: Block = builder(vf=VarFactory()).block
    current_balance: Dict[int, List[Expr | Var | Const]] = {
        0: [Const(0.0)],
        1: [Const(0.0), Const(0.0), Const(0.0), Const(0.0)],
    }

    assert model.dynamic_model_contract.emt_terminal_current_contributions == list()
    assert VarPowerFlowReferenceType.If_dc in model.external_mapping
    assert VarPowerFlowReferenceType.it_A in model.external_mapping
    assert VarPowerFlowReferenceType.it_B in model.external_mapping
    assert VarPowerFlowReferenceType.it_C in model.external_mapping
    assert assemble_emt_mapped_current_references(
        model=model,
        current_balance=current_balance,
        bus_from_index=0,
        bus_to_index=1,
        bus_from_is_dc=True,
        bus_to_is_dc=False,
    )
    assert model.E(VarPowerFlowReferenceType.If_dc) in get_expression_vars(current_balance[0][0])
    assert model.E(VarPowerFlowReferenceType.it_A) in get_expression_vars(current_balance[1][1])
    assert model.E(VarPowerFlowReferenceType.it_B) in get_expression_vars(current_balance[1][2])
    assert model.E(VarPowerFlowReferenceType.it_C) in get_expression_vars(current_balance[1][3])


def test_single_bus_emt_contract_assembles_selected_current_without_ports() -> None:
    """Assemble one selected EMT current independently of visible ports.

    :return: None.
    """
    selected_current: Var = Var(name="selected_current")
    model: Block = Block(
        algebraic_vars=list((selected_current,)),
        algebraic_eqs=list((selected_current,)),
        out_vars=list(),
        external_mapping=dict(((VarPowerFlowReferenceType.i_A, selected_current),)),
    )
    model.dynamic_model_contract.emt_terminal_current_contributions = list((
        EmtTerminalCurrentContribution(
            terminal_side=EmtTerminalSide.BUS,
            conductor=EmtTerminalConductor.PHASE_A,
            current_reference=VarPowerFlowReferenceType.i_A,
        ),
    ))
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0), Const(0.0), Const(0.0), Const(0.0))),
    })

    assemble_emt_mapped_current_references(
        model=model,
        current_balance=current_balance,
        bus_index=0,
        bus_is_dc=False,
    )
    restored_model: Block = Block.parse(data=model.to_dict())
    restored_contribution: EmtTerminalCurrentContribution = (
        restored_model.dynamic_model_contract.emt_terminal_current_contributions[0]
    )

    assert len(model.out_vars) == 0
    assert current_balance[0][1].eval(selected_current=0.3) == pytest.approx(0.3)
    assert restored_contribution.get_terminal_side() is EmtTerminalSide.BUS
    assert restored_contribution.get_conductor() is EmtTerminalConductor.PHASE_A


def test_two_terminal_emt_contract_uses_physical_dc_topology() -> None:
    """Assemble both DC branch terminals with the branch-current convention.

    :return: None.
    """
    from_current: Var = Var(name="from_current")
    to_current: Var = Var(name="to_current")
    model: Block = Block(
        algebraic_vars=list((from_current, to_current)),
        algebraic_eqs=list((from_current, to_current)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.If_dc, from_current),
            (VarPowerFlowReferenceType.It_dc, to_current),
        )),
    )
    model.dynamic_model_contract.emt_terminal_current_contributions = list((
        EmtTerminalCurrentContribution(
            terminal_side=EmtTerminalSide.FROM,
            conductor=EmtTerminalConductor.DC,
            current_reference=VarPowerFlowReferenceType.If_dc,
        ),
        EmtTerminalCurrentContribution(
            terminal_side=EmtTerminalSide.TO,
            conductor=EmtTerminalConductor.DC,
            current_reference=VarPowerFlowReferenceType.It_dc,
        ),
    ))
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0),)),
        1: list((Const(0.0),)),
    })

    assemble_emt_mapped_current_references(
        model=model,
        current_balance=current_balance,
        bus_from_index=0,
        bus_to_index=1,
        bus_from_is_dc=True,
        bus_to_is_dc=True,
    )

    assert current_balance[0][0].eval(from_current=0.2) == pytest.approx(-0.2)
    assert current_balance[1][0].eval(to_current=-0.19) == pytest.approx(0.19)


def test_mixed_current_mappings_use_only_the_physical_device_contract() -> None:
    """Shared seed references must not become extra branch KCL injections."""
    shared_current = Var(name="shared_current")
    from_current = Var(name="from_current")
    model = Block(
        external_mapping={
            VarPowerFlowReferenceType.Idc: shared_current,
            VarPowerFlowReferenceType.If_dc: from_current,
        },
    )
    branch_balance = {0: [Const(0.0)], 1: [Const(0.0)]}
    assert assemble_emt_mapped_current_references(
        model=model,
        current_balance=branch_balance,
        bus_from_index=0,
        bus_to_index=1,
        bus_from_is_dc=True,
        bus_to_is_dc=True,
    )
    assert branch_balance[0][0].eval(from_current=0.2) == pytest.approx(-0.2)
    assert branch_balance[1][0].eval() == pytest.approx(0.0)

    bus_balance = {0: [Const(0.0)]}
    assert assemble_emt_mapped_current_references(
        model=model,
        current_balance=bus_balance,
        bus_index=0,
        bus_is_dc=True,
    )
    assert bus_balance[0][0].eval(shared_current=0.3) == pytest.approx(0.3)


def test_emt_contract_rejects_bus_domain_mismatch_atomically() -> None:
    """Reject a DC current on an AC bus before changing any KCL entry.

    :return: None.
    """
    dc_current: Var = Var(name="dc_current")
    model: Block = Block(
        algebraic_vars=list((dc_current,)),
        algebraic_eqs=list((dc_current,)),
        external_mapping=dict(((VarPowerFlowReferenceType.Idc, dc_current),)),
    )
    model.dynamic_model_contract.emt_terminal_current_contributions = list((
        EmtTerminalCurrentContribution(
            terminal_side=EmtTerminalSide.BUS,
            conductor=EmtTerminalConductor.DC,
            current_reference=VarPowerFlowReferenceType.Idc,
        ),
    ))
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0), Const(0.0), Const(0.0), Const(0.0))),
    })

    with pytest.raises(ValueError, match="connected bus domain"):
        assemble_emt_mapped_current_references(
            model=model,
            current_balance=current_balance,
            bus_index=0,
            bus_is_dc=False,
        )

    assert current_balance[0][0].eval() == pytest.approx(0.0)
    assert current_balance[0][1].eval() == pytest.approx(0.0)


def test_multiple_ac_injection_currents_accumulate_on_one_bus_phase() -> None:
    """Sum two AC injection currents without replacing the first contribution.

    :return: None.
    """
    first_current: Var = Var(name="first_ac_injection_current")
    second_current: Var = Var(name="second_ac_injection_current")
    first_model: Block = Block(
        external_mapping=dict(((VarPowerFlowReferenceType.i_A, first_current),)),
    )
    second_model: Block = Block(
        external_mapping=dict(((VarPowerFlowReferenceType.i_A, second_current),)),
    )
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0), Const(0.0), Const(0.0), Const(0.0))),
    })

    first_was_assembled: bool = assemble_emt_mapped_current_references(
        model=first_model,
        current_balance=current_balance,
        bus_index=0,
        bus_is_dc=False,
    )
    second_was_assembled: bool = assemble_emt_mapped_current_references(
        model=second_model,
        current_balance=current_balance,
        bus_index=0,
        bus_is_dc=False,
    )
    mapped_variables: List[Var] = get_expression_vars(current_balance[0][1])

    assert first_was_assembled
    assert second_was_assembled
    assert first_current in mapped_variables
    assert second_current in mapped_variables
    assert current_balance[0][1].eval(
        first_ac_injection_current=0.25,
        second_ac_injection_current=-0.10,
    ) == pytest.approx(0.15)


def test_multiple_dc_injection_currents_accumulate_on_one_bus() -> None:
    """Sum two DC injection currents without replacing the first contribution.

    :return: None.
    """
    first_current: Var = Var(name="first_dc_injection_current")
    second_current: Var = Var(name="second_dc_injection_current")
    first_model: Block = Block(
        external_mapping=dict(((VarPowerFlowReferenceType.Idc, first_current),)),
    )
    second_model: Block = Block(
        external_mapping=dict(((VarPowerFlowReferenceType.Idc, second_current),)),
    )
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0),)),
    })

    first_was_assembled: bool = assemble_emt_mapped_current_references(
        model=first_model,
        current_balance=current_balance,
        bus_index=0,
        bus_is_dc=True,
    )
    second_was_assembled: bool = assemble_emt_mapped_current_references(
        model=second_model,
        current_balance=current_balance,
        bus_index=0,
        bus_is_dc=True,
    )
    mapped_variables: List[Var] = get_expression_vars(current_balance[0][0])

    assert first_was_assembled
    assert second_was_assembled
    assert first_current in mapped_variables
    assert second_current in mapped_variables
    assert current_balance[0][0].eval(
        first_dc_injection_current=0.40,
        second_dc_injection_current=-0.15,
    ) == pytest.approx(0.25)


def test_current_assembly_uses_problem_local_external_mapping() -> None:
    """Use the effective local mapping without rewriting the persistent block.

    :return: None.
    """
    local_current: Var = Var(name="local_injection_current")
    model: Block = Block(external_mapping=dict())
    effective_mapping: Dict[VarPowerFlowReferenceType, Var] = dict((
        (VarPowerFlowReferenceType.i_A, local_current),
    ))
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0), Const(0.0), Const(0.0), Const(0.0))),
    })

    was_assembled: bool = assemble_emt_mapped_current_references(
        model=model,
        current_balance=current_balance,
        effective_external_mapping=effective_mapping,
        bus_index=0,
        bus_is_dc=False,
    )

    assert was_assembled
    assert len(model.external_mapping) == 0
    assert current_balance[0][1].eval(local_injection_current=0.35) == pytest.approx(0.35)
