from __future__ import annotations

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.load_exponential_emt_template import get_exponential_load_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import (
    ShuntCComboEmtTemplate,
    ShuntLComboEmtTemplate,
    ShuntRComboEmtTemplate,
    get_grounding_link_emt_template,
    get_shunt_c_emt_template,
    get_shunt_l_emt_template,
    get_shunt_r_emt_template,
    get_shunt_rlc_combo_emt_template,
)
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block, Expr, Var
from VeraGridEngine.enumerations import BlockType, ShuntConnectionType, VarPowerFlowReferenceType


def test_individual_shunt_builders_keep_matching_names_and_topologies() -> None:
    """Require the R, L and C builders to materialize their declared component.

    :return: None.
    """
    # Build each public modal definition independently so variable names from
    # one template cannot affect the identity checks for another template.
    r_template: EmtModelTemplate = ShuntRComboEmtTemplate(VarFactory()).eval()
    l_template: EmtModelTemplate = ShuntLComboEmtTemplate(VarFactory()).eval()
    c_template: EmtModelTemplate = ShuntCComboEmtTemplate(VarFactory()).eval()

    r_event_names: set[str] = set(variable.name for variable in r_template.block.event_dict)
    l_event_names: set[str] = set(variable.name for variable in l_template.block.event_dict)
    c_event_names: set[str] = set(variable.name for variable in c_template.block.event_dict)

    assert r_template.name == "R_combo_emt"
    assert l_template.name == "L_combo_emt"
    assert c_template.name == "C_combo_emt"
    assert "R_A" in r_event_names
    assert "L_A" in l_event_names
    assert "C_A" in c_event_names
    assert "L_A" not in r_event_names and "C_A" not in r_event_names
    assert "R_A" not in l_event_names and "C_A" not in l_event_names
    assert "R_A" not in c_event_names and "L_A" not in c_event_names

    # The three catalogue builders default to GroundedStar. Their grounded
    # neutral must remain inside the model instead of requiring a fourth bus
    # conductor that an ordinary ABC network does not provide.
    grounded_template: EmtModelTemplate
    for grounded_template in (r_template, l_template, c_template):
        assert [var.name for var in grounded_template.block.in_vars] == ["v_A", "v_B", "v_C"]
        assert [var.name for var in grounded_template.block.out_vars] == ["i_A", "i_B", "i_C"]
        assert grounded_template.block.external_mapping[VarPowerFlowReferenceType.v_N] is None
        assert grounded_template.block.external_mapping[VarPowerFlowReferenceType.i_N] is None


def test_rlc_combo_emt_template_builds_r_plus_l_star_case() -> None:
    vf = VarFactory()
    templ = get_shunt_rlc_combo_emt_template(
        vf=vf,
        include_r=True,
        include_l=True,
        include_c=False,
        phA=True,
        phB=False,
        phC=False,
        connection_type=ShuntConnectionType.GroundedStar,
        name="rlc_combo_case",
    )

    assert templ.tpe.name == "LoadDevice"
    # GroundedStar owns an internal grounded neutral. Only the selected phase
    # voltage and current are public network terminals.
    assert [var.name for var in templ.block.in_vars] == ["v_A"]
    assert [var.name for var in templ.block.out_vars] == ["i_A"]
    assert len(templ.block.algebraic_vars) == 2
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_N] is None
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_N] is None
    assert any(var.name == "v_N_internal" for var in templ.block.algebraic_vars)
    assert any(child.name.endswith("_grounding_link") for child in templ.block.children)
    assert any(node.tpe == BlockType.GROUNDING_LINK_EMT.name for node in templ.block.diagram.node_data.values())


def test_rlc_combo_uses_total_three_phase_power_base() -> None:
    vf = VarFactory()
    templ = get_shunt_rlc_combo_emt_template(
        vf=vf,
        include_r=True,
        include_l=True,
        include_c=False,
        phA=True,
        phB=False,
        phC=False,
        connection_type=ShuntConnectionType.FloatingStar,
    )

    expressions = {variable.name: str(expression)
                   for variable, expression in templ.block.event_dict.items()}
    assert "(3.0) * (Pl0_A)" in expressions["R_A"]
    assert "(3.0) * (Ql0_A)" in expressions["L_A"]


def test_individual_shunts_use_total_three_phase_power_base() -> None:
    """Require individual R, L and C shunts to use the system power base.

    :return: None.
    """
    # Use independent factories so identically named variables cannot mask a
    # formula difference between the three public standalone constructors.
    r_template: EmtModelTemplate = get_shunt_r_emt_template(
        vf=VarFactory(), phA=True, phB=False, phC=False
    )
    l_template: EmtModelTemplate = get_shunt_l_emt_template(
        vf=VarFactory(), phA=True, phB=False, phC=False
    )
    c_template: EmtModelTemplate = get_shunt_c_emt_template(
        vf=VarFactory(), phA=True, phB=False, phC=False
    )

    # The standalone templates expose network terminals at the root but retain
    # their parameters and equations in one component child block.
    assert len(r_template.block.children) == 1
    assert len(l_template.block.children) == 1
    assert len(c_template.block.children) == 1
    r_block: Block = r_template.block.children[0]
    l_block: Block = l_template.block.children[0]
    c_block: Block = c_template.block.children[0]

    # Select the derived component expressions by their public variable names.
    # Evaluating the expressions is more robust than matching their formatted
    # text because the resistor expands its lower-bound ``max`` symbolically.
    r_expression: Expr = next(
        expression
        for variable, expression in r_block.event_dict.items()
        if variable.name.startswith("R_A_")
    )
    l_expression: Expr = next(
        expression
        for variable, expression in l_block.event_dict.items()
        if variable.name == "L_A"
    )
    c_expression: Expr = next(
        expression
        for variable, expression in c_block.event_dict.items()
        if variable.name == "C_A"
    )

    # Bind the expressions through their symbolic identities so the numerical
    # convention test remains independent from phase-count naming conventions.
    r_pf_vm_var: Var | None = r_block.external_mapping[VarPowerFlowReferenceType.Vm]
    assert isinstance(r_pf_vm_var, Var)
    r_power_var: Var = next(
        variable for variable in r_block.parameters if variable.name == "Pl0_A"
    )
    l_pf_vm_var: Var | None = l_block.external_mapping[VarPowerFlowReferenceType.Vm]
    assert isinstance(l_pf_vm_var, Var)
    l_power_var: Var = next(
        variable for variable in l_block.parameters if variable.name == "Ql0_A"
    )
    l_omega_var: Var = next(
        variable for variable in l_block.parameters if variable.name.startswith("w_base_")
    )
    c_pf_vm_var: Var | None = c_block.external_mapping[VarPowerFlowReferenceType.Vm]
    assert isinstance(c_pf_vm_var, Var)
    c_power_var: Var = next(
        variable for variable in c_block.parameters if variable.name == "Ql0_A"
    )
    c_omega_var: Var = next(
        variable for variable in c_block.parameters if variable.name.startswith("w_base_")
    )

    r_bindings: dict[int, float] = dict()
    r_bindings[r_pf_vm_var.uid] = 1.0
    r_bindings[r_power_var.uid] = 0.25
    l_bindings: dict[int, float] = dict()
    l_bindings[l_pf_vm_var.uid] = 1.0
    l_bindings[l_power_var.uid] = 0.25
    l_bindings[l_omega_var.uid] = 2.0
    c_bindings: dict[int, float] = dict()
    c_bindings[c_pf_vm_var.uid] = 1.0
    c_bindings[c_power_var.uid] = -0.25
    c_bindings[c_omega_var.uid] = 2.0

    # A phase power is stored on the total three-phase Sbase, while EMT phase
    # voltage and current use Sbase/3. Inductive Q is positive for the inductor,
    # whereas capacitive Load Q is negative and must still produce C > 0.
    r_value: float = float(r_expression.eval_uid(r_bindings))
    l_value: float = float(l_expression.eval_uid(l_bindings))
    c_value: float = float(c_expression.eval_uid(c_bindings))

    assert np.isclose(r_value, 1.0 / (3.0 * 0.25))
    assert np.isclose(l_value, 1.0 / (3.0 * 0.25 * 2.0))
    assert np.isclose(c_value, 3.0 * 0.25 / 2.0)

    # A dead island legitimately has Vm=0 in the initialization power flow.
    # Static P/Q still describes finite components at nominal voltage, so the
    # derived R/L/C values must remain physical instead of becoming zero or
    # evaluating a division by zero before the island is energized.
    r_bindings[r_pf_vm_var.uid] = 0.0
    l_bindings[l_pf_vm_var.uid] = 0.0
    c_bindings[c_pf_vm_var.uid] = 0.0
    dead_bus_r_value: float = float(r_expression.eval_uid(r_bindings))
    dead_bus_l_value: float = float(l_expression.eval_uid(l_bindings))
    dead_bus_c_value: float = float(c_expression.eval_uid(c_bindings))

    assert np.isclose(dead_bus_r_value, 1.0 / (3.0 * 0.25))
    assert np.isclose(dead_bus_l_value, 1.0 / (3.0 * 0.25 * 2.0))
    assert np.isclose(dead_bus_c_value, 3.0 * 0.25 / 2.0)


def test_rlc_combo_capacitance_uses_capacitive_load_sign() -> None:
    """Require negative static Load Q to produce positive capacitance.

    :return: None.
    """
    # Build a single derived capacitor so the test checks the combined-template
    # conversion independently from the standalone capacitor constructor.
    template: EmtModelTemplate = get_shunt_rlc_combo_emt_template(
        vf=VarFactory(),
        include_r=False,
        include_l=False,
        include_c=True,
        phA=True,
        phB=False,
        phC=False,
        connection_type=ShuntConnectionType.FloatingStar,
    )
    capacitance_expression: Expr = next(
        expression
        for variable, expression in template.block.event_dict.items()
        if variable.name == "C_A"
    )
    pf_voltage_magnitude_var: Var | None = template.block.external_mapping[VarPowerFlowReferenceType.Vm]
    assert isinstance(pf_voltage_magnitude_var, Var)
    reactive_power_var: Var = next(
        variable
        for variable in template.block.parameters
        if variable.name == "Ql0_A"
    )
    omega_var: Var = next(
        variable
        for variable in template.block.parameters
        if variable.name.startswith("w_base_")
    )
    bindings: dict[int, float] = dict()
    bindings[pf_voltage_magnitude_var.uid] = 1.0
    bindings[reactive_power_var.uid] = -0.25
    bindings[omega_var.uid] = 2.0

    capacitance_value: float = float(capacitance_expression.eval_uid(bindings))

    assert np.isclose(capacitance_value, 3.0 * 0.25 / 2.0)


def test_rlc_combo_rejects_l_and_c_derived_from_one_reactive_power() -> None:
    """Require direct data when both reactive branches are requested.

    :return: None.
    """
    # One net Q cannot determine two independent positive component values, so
    # the constructor must diagnose the underdetermined configuration.
    try:
        get_shunt_rlc_combo_emt_template(
            vf=VarFactory(),
            include_r=False,
            include_l=True,
            include_c=True,
            phA=True,
            phB=False,
            phC=False,
            connection_type=ShuntConnectionType.GroundedStar,
        )
    except ValueError as exception:
        assert "cannot split one reactive-power reference" in str(exception)
    else:
        raise AssertionError("Derived L+C must require independent direct component data")


def test_rlc_combo_emt_template_builds_neutralstar_with_explicit_neutral_port() -> None:
    vf = VarFactory()
    templ = get_shunt_rlc_combo_emt_template(
        vf=vf,
        include_r=True,
        include_l=False,
        include_c=False,
        phA=True,
        phB=False,
        phC=False,
        connection_type=ShuntConnectionType.NeutralStar,
        direct_r_value=25.0,
        name="rlc_combo_neutral",
    )

    input_names = [var.name for var in templ.block.in_vars]
    output_names = [var.name for var in templ.block.out_vars]

    assert input_names == ["v_N", "v_A"]
    assert output_names == ["i_N", "i_A"]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_N] is templ.block.in_vars[0]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_N] is templ.block.out_vars[0]
    assert not any(node.tpe == BlockType.GROUNDING_LINK_EMT.name for node in templ.block.diagram.node_data.values())


def test_rlc_combo_emt_template_builds_delta_with_direct_values() -> None:
    vf = VarFactory()
    templ = get_shunt_rlc_combo_emt_template(
        vf=vf,
        include_r=True,
        include_l=False,
        include_c=False,
        phA=True,
        phB=True,
        phC=True,
        connection_type=ShuntConnectionType.Delta,
        direct_r_value=25.0,
        name="rlc_combo_delta",
    )

    event_values_by_name: dict[str, float] = dict()
    parameter_var = None
    parameter_expr = None
    for parameter_var, parameter_expr in templ.block.event_dict.items():
        if parameter_var.name.startswith("R_"):
            assert parameter_expr.value is not None
            event_values_by_name[parameter_var.name] = float(parameter_expr.value)
        else:
            pass

    assert len(templ.block.in_vars) == 3
    assert len(templ.block.out_vars) == 3
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_N] is None
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_N] is None
    assert not any(node.tpe == BlockType.GROUNDING_LINK_EMT.name for node in templ.block.diagram.node_data.values())
    assert event_values_by_name["R_AB"] == 25.0
    assert event_values_by_name["R_BC"] == 25.0
    assert event_values_by_name["R_CA"] == 25.0


def test_rlc_combo_emt_template_rejects_delta_single_phase_case() -> None:
    vf = VarFactory()

    try:
        get_shunt_rlc_combo_emt_template(
            vf=vf,
            include_r=True,
            include_l=False,
            include_c=False,
            phA=True,
            phB=False,
            phC=False,
            connection_type=ShuntConnectionType.Delta,
            direct_r_value=25.0,
            name="rlc_combo_delta",
        )
    except ValueError as exc:
        assert "at least two active phases" in str(exc)
    else:
        raise AssertionError("Single-phase delta should be rejected")


def test_rlc_combo_emt_template_overrides_r_l_c_values_directly() -> None:
    vf = VarFactory()
    templ = get_shunt_rlc_combo_emt_template(
        vf=vf,
        include_r=True,
        include_l=True,
        include_c=True,
        phA=True,
        phB=False,
        phC=False,
        connection_type=ShuntConnectionType.GroundedStar,
        direct_r_value=25.0,
        direct_l_value=0.02,
        direct_c_value=4.0e-6,
        name="rlc_combo_direct_values",
    )

    event_values_by_prefix: dict[str, float] = dict()
    parameter_var = None
    parameter_expr = None
    for parameter_var, parameter_expr in templ.block.event_dict.items():
        if parameter_var.name.startswith(("R_", "L_", "C_")):
            assert parameter_expr.value is not None
            event_values_by_prefix[parameter_var.name[:2]] = float(parameter_expr.value)
        else:
            pass

    assert event_values_by_prefix["R_"] == 25.0
    assert event_values_by_prefix["L_"] == 0.02
    assert event_values_by_prefix["C_"] == 4.0e-6


def test_grounding_link_emt_template_builds_direct_r_plus_c_case() -> None:
    vf = VarFactory()
    templ = get_grounding_link_emt_template(
        vf=vf,
        include_r=True,
        include_l=False,
        include_c=True,
        direct_r_value=15.0,
        direct_c_value=3.0e-6,
        name="grounding_link_case",
    )

    assert len(templ.block.in_vars) == 1
    assert len(templ.block.out_vars) == 1
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_N] is templ.block.in_vars[0]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_N] is templ.block.out_vars[0]
    assert any(child.name.endswith("_ground") for child in templ.block.children)


def test_exponential_load_emt_template_builds_neutralstar_topology() -> None:
    vf = VarFactory()
    templ = get_exponential_load_emt(
        vf=vf,
        phA=True,
        phB=False,
        phC=False,
        connection_type=ShuntConnectionType.NeutralStar,
        name="exp_load_neutral",
    )

    input_names = [var.name for var in templ.block.in_vars]
    output_names = [var.name for var in templ.block.out_vars]

    assert input_names == ["v_N", "v_A"]
    assert output_names == ["i_N", "i_A"]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_N] is templ.block.in_vars[0]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_N] is templ.block.out_vars[0]
    assert not any(node.tpe == BlockType.GROUNDING_LINK_EMT.name for node in templ.block.diagram.node_data.values())


def test_exponential_load_emt_template_keeps_grounded_neutral_internal() -> None:
    """Require a grounded-star wrapper to expose only its phase terminals.

    :return: None.
    """
    vf: VarFactory = VarFactory()
    templ: EmtModelTemplate = get_exponential_load_emt(
        vf=vf,
        phA=True,
        phB=False,
        phC=False,
        connection_type=ShuntConnectionType.GroundedStar,
        name="exp_load_grounded",
    )

    # The grounding-link child owns the neutral connection, so an ABC bus does
    # not need to provide a compiler variable for an external ``v_N`` terminal.
    assert [var.name for var in templ.block.in_vars] == ["v_A"]
    assert [var.name for var in templ.block.out_vars] == ["i_A"]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_N] is None
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_N] is None
    assert any(var.name == "v_N_internal" for var in templ.block.algebraic_vars)
    assert any(child.name.endswith("_grounding_link") for child in templ.block.children)


def test_exponential_load_emt_template_builds_delta_topology() -> None:
    vf = VarFactory()
    templ = get_exponential_load_emt(
        vf=vf,
        phA=True,
        phB=True,
        phC=True,
        connection_type=ShuntConnectionType.Delta,
        name="exp_load_delta",
    )

    input_names = [var.name for var in templ.block.in_vars]
    output_names = [var.name for var in templ.block.out_vars]

    assert input_names == ["v_A", "v_B", "v_C"]
    assert output_names == ["i_A", "i_B", "i_C"]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_N] is None
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_N] is None


def test_zip_load_emt_template_builds_delta_topology() -> None:
    vf = VarFactory()
    templ = get_load_ZIP_emt_template(
        vf=vf,
        phA=True,
        phB=True,
        phC=True,
        connection_type=ShuntConnectionType.Delta,
        name="zip_load_delta",
    )

    input_names = [var.name for var in templ.block.in_vars]
    output_names = [var.name for var in templ.block.out_vars]

    assert input_names == ["v_A", "v_B", "v_C"]
    assert output_names == ["i_A", "i_B", "i_C"]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_N] is None
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_N] is None
