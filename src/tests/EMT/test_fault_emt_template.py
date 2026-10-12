# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Set

import pytest

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.fault_emt_template import (
    FaultEmtTemplate,
    get_fault_emt_template,
    validate_fault_electrical_parameters,
    validate_fault_phase_selection,
)
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicCodec
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var, get_expression_vars
from VeraGridEngine.enumerations import EmtFaultPlacementSide, FaultType


def _find_equation_with_exact_variables(equations: List[Expr],
                                        expected_names: Set[str]) -> Expr:
    """Find the unique residual that references exactly the requested names.

    :param equations: Algebraic residuals to inspect.
    :param expected_names: Exact set of referenced symbolic variable names.
    :return: Matching residual expression.
    :raises AssertionError: If the match is absent or ambiguous.
    """
    matches: List[Expr] = list()
    equation: Expr
    for equation in equations:
        expression_variables: List[Var] = get_expression_vars(expr=equation)
        actual_names: Set[str] = set(variable.name for variable in expression_variables)
        if actual_names == expected_names:
            matches.append(equation)
        else:
            pass
    assert len(matches) == 1
    return matches[0]


def test_fault_builder_default_is_directly_evaluable() -> None:
    """Keep the template definition valid without GUI-supplied enum defaults.

    :return: None.
    """
    template: EmtModelTemplate = FaultEmtTemplate(vf=VarFactory()).eval()
    input_names: Set[str] = set(variable.name for variable in template.block.in_vars)
    output_names: Set[str] = set(variable.name for variable in template.block.out_vars)

    assert input_names == set(("v_outer_A", "i_inner_A"))
    assert output_names == set(("v_inner_A", "i_outer_A"))


@pytest.mark.parametrize(
    "fault_type,ph_a,ph_b,ph_c,expected_equation_count",
    (
        (FaultType.LG, True, False, False, 3),
        (FaultType.LL, True, True, False, 5),
        (FaultType.LLG, True, True, False, 7),
        (FaultType.LLL, True, True, True, 10),
        (FaultType.LLLG, True, True, True, 9),
    ),
)
def test_fault_topologies_are_square_and_own_voltage_continuity(
        fault_type: FaultType,
        ph_a: bool,
        ph_b: bool,
        ph_c: bool,
        expected_equation_count: int) -> None:
    """Require a complete square algebraic system for every supported topology.

    :param fault_type: Fault topology under test.
    :param ph_a: Whether phase A is enabled.
    :param ph_b: Whether phase B is enabled.
    :param ph_c: Whether phase C is enabled.
    :param expected_equation_count: Expected number of algebraic unknowns and residuals.
    :return: None.
    """
    model: Block = get_fault_emt_template(
        vf=VarFactory(),
        fault_type=fault_type,
        phA=ph_a,
        phB=ph_b,
        phC=ph_c,
    ).block

    assert len(model.algebraic_vars) == expected_equation_count
    assert len(model.algebraic_eqs) == expected_equation_count

    phase_name: str
    phase_enabled: bool
    for phase_name, phase_enabled in (("A", ph_a), ("B", ph_b), ("C", ph_c)):
        if phase_enabled:
            continuity_equation: Expr = _find_equation_with_exact_variables(
                equations=model.algebraic_eqs,
                expected_names=set((f"v_inner_{phase_name}", f"v_outer_{phase_name}")),
            )
            continuity_variables: List[Var] = get_expression_vars(expr=continuity_equation)
            continuity_bindings: dict[int, float] = dict()
            continuity_variable: Var
            for continuity_variable in continuity_variables:
                continuity_bindings[continuity_variable.uid] = 0.37
            assert continuity_equation.eval_uid(continuity_bindings) == pytest.approx(0.0)
        else:
            pass


def test_llg_uses_distinct_phase_and_ground_resistances_with_passive_kcl() -> None:
    """Protect the LLG common-node signs and its two independent impedances.

    :return: None.
    """
    model: Block = get_fault_emt_template(
        vf=VarFactory(),
        fault_type=FaultType.LLG,
        phA=True,
        phB=True,
        phC=False,
        initial_closed=True,
        fault_resistance=0.2,
        ground_resistance=0.1,
        open_conductance=0.0,
    ).block
    phase_a_equation: Expr = _find_equation_with_exact_variables(
        equations=model.algebraic_eqs,
        expected_names=set((
            "i_fault_AN",
            "fault_closed_mode",
            "fault_r",
            "fault_open_g",
            "v_inner_A",
            "v_fault_node",
        )),
    )
    node_equation: Expr = _find_equation_with_exact_variables(
        equations=model.algebraic_eqs,
        expected_names=set((
            "i_fault_AN",
            "i_fault_BN",
            "fault_closed_mode",
            "fault_rg",
            "fault_open_g",
            "v_fault_node",
        )),
    )

    assert phase_a_equation.eval(
        i_fault_AN=1.0,
        fault_closed_mode=1.0,
        fault_r=0.2,
        fault_open_g=0.0,
        v_inner_A=0.4,
        v_fault_node=0.2,
    ) == pytest.approx(0.0)
    assert node_equation.eval(
        i_fault_AN=1.0,
        i_fault_BN=2.0,
        fault_closed_mode=1.0,
        fault_rg=0.1,
        fault_open_g=0.0,
        v_fault_node=0.3,
    ) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "fault_type,ph_a,ph_b,ph_c",
    (
        (FaultType.LG, True, True, False),
        (FaultType.LL, True, False, False),
        (FaultType.LLG, True, True, True),
        (FaultType.LLL, True, True, False),
        (FaultType.LLLG, False, True, True),
    ),
)
def test_fault_rejects_inconsistent_phase_masks(fault_type: FaultType,
                                                ph_a: bool,
                                                ph_b: bool,
                                                ph_c: bool) -> None:
    """Reject phase masks that cannot represent the selected topology.

    :param fault_type: Fault topology under test.
    :param ph_a: Whether phase A is enabled.
    :param ph_b: Whether phase B is enabled.
    :param ph_c: Whether phase C is enabled.
    :return: None.
    """
    with pytest.raises(ValueError):
        validate_fault_phase_selection(
            fault_type=fault_type,
            phA=ph_a,
            phB=ph_b,
            phC=ph_c,
        )


@pytest.mark.parametrize(
    "fault_resistance,ground_resistance,open_conductance,fault_time_constant,command_threshold",
    (
        (0.0, 0.1, 0.0, 1.0e-4, 0.5),
        (0.1, -0.1, 0.0, 1.0e-4, 0.5),
        (0.1, 0.1, -1.0e-8, 1.0e-4, 0.5),
        (0.1, 0.1, 0.0, 0.0, 0.5),
        (0.1, 0.1, 0.0, 1.0e-4, float("nan")),
    ),
)
def test_fault_rejects_invalid_electrical_parameters(
        fault_resistance: float,
        ground_resistance: float,
        open_conductance: float,
        fault_time_constant: float,
        command_threshold: float) -> None:
    """Reject singular or non-finite electrical settings before model creation.

    :param fault_resistance: Candidate phase-path resistance.
    :param ground_resistance: Candidate ground-path resistance.
    :param open_conductance: Candidate open-state conductance.
    :param fault_time_constant: Candidate legacy time constant.
    :param command_threshold: Candidate signal threshold.
    :return: None.
    """
    with pytest.raises(ValueError):
        validate_fault_electrical_parameters(
            fault_resistance=fault_resistance,
            ground_resistance=ground_resistance,
            open_conductance=open_conductance,
            fault_time_constant=fault_time_constant,
            command_threshold=command_threshold,
        )


def test_fault_structure_and_placement_survive_block_roundtrip() -> None:
    """Keep the persisted symbolic and diagram markers needed by GUI recovery.

    :return: None.
    """
    source: Block = get_fault_emt_template(
        vf=VarFactory(),
        fault_type=FaultType.LLG,
        placement_side=EmtFaultPlacementSide.ToSide,
        phA=False,
        phB=True,
        phC=True,
        signal_controlled=True,
        initial_closed=True,
        name="saved_fault",
    ).block
    restored: Block = Block.parse(
        data=source.to_dict(),
        procedural_logic_codec=ProceduralLogicCodec(),
    )
    restored_algebraic_names: Set[str] = set(variable.name for variable in restored.algebraic_vars)
    restored_child_names: Set[str] = set(child.name for child in restored.children)
    restored_input_names: Set[str] = set(variable.name for variable in restored.in_vars)

    assert "i_fault_BN" in restored_algebraic_names
    assert "i_fault_CN" in restored_algebraic_names
    assert "To Phase B Node" in restored_child_names
    assert "To Phase C Node" in restored_child_names
    assert "Fault Common Node" in restored_child_names
    assert "Fault Ground" in restored_child_names
    assert "fault_cmd" in restored_input_names
