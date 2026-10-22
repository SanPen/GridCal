from __future__ import annotations
import numpy as np
import pytest
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
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import assign_static_api_object_mapping_for_device
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var


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
    r_pf_vm_var: Var | None = r_block.external_mapping[VarPowerFlowReferenceType.VmSizing]
    assert isinstance(r_pf_vm_var, Var)
    r_power_var: Var = next(
        variable for variable in r_block.parameters if variable.name == "Pl0_A"
    )
    l_pf_vm_var: Var | None = l_block.external_mapping[VarPowerFlowReferenceType.VmSizing]
    assert isinstance(l_pf_vm_var, Var)
    l_power_var: Var = next(
        variable for variable in l_block.parameters if variable.name == "Ql0_A"
    )
    l_omega_var: Var = next(
        variable for variable in l_block.parameters if variable.name.startswith("w_base_")
    )
    c_pf_vm_var: Var | None = c_block.external_mapping[VarPowerFlowReferenceType.VmSizing]
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
    pf_voltage_magnitude_var: Var | None = template.block.external_mapping[VarPowerFlowReferenceType.VmSizing]
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


@pytest.mark.parametrize("mask", range(1, 8))
@pytest.mark.parametrize("vm", (0.9, 1.0, 1.03))
@pytest.mark.parametrize("resistive,power", ((True, 30.0), (True, 0.0), (True, 1e-8), (False, 12.0)))
def test_standalone_shunts_preserve_pf_phase_power(mask: int, vm: float, resistive: bool, power: float) -> None:
    """Recover signed phase power from independent sinusoidal terminal currents.

    :param mask: Nonempty ABC phase bit mask.
    :param vm: Shared balanced PF voltage magnitude in per unit.
    :param resistive: Select the existing resistor or inductor owner.
    :param power: Total MW/MVAr; small values exercise the inherited R guard.
    :return: None; base, ordering, current law or runtime reference errors fail.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    bus: Bus = grid.add_bus(Bus(Vnom=10.0))
    # Inductors require positive Q; only the resistor has a near-zero guard.
    source_power: float = power if resistive else 12.0
    load: Load = grid.add_load(bus, Load(P=source_power if resistive else 0.0,
                                       Q=0.0 if resistive else source_power))
    phases: tuple[bool, bool, bool] = (bool(mask & 1), bool(mask & 2), bool(mask & 4))
    standalone: EmtModelTemplate
    if resistive:
        standalone = get_shunt_r_emt_template(grid.var_factory, phases[0], phases[1], phases[2])
    else:
        standalone = get_shunt_l_emt_template(grid.var_factory, phases[0], phases[1], phases[2])
    mapped: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, load, standalone.block, mapped, None)
    bindings: dict[int, float] = dict((variable.uid, float(value.value)) for variable, value in mapped.items())
    owner: Block = standalone.block.children[0]
    vnom: Var = standalone.block.external_mapping[VarPowerFlowReferenceType.VmSizing]
    assert owner.external_mapping[VarPowerFlowReferenceType.VmSizing].uid == vnom.uid
    bindings[vnom.uid] = vm
    parameter: Var
    equation: Expr
    for parameter, equation in owner.event_dict.items():
        if parameter is vnom:
            pass
        else:
            bindings[parameter.uid] = float(equation.eval_uid(bindings))
    omega: float = 2.0 * np.pi * grid.fBase
    phase_count: int = sum(phases)
    assert len(owner.in_vars) == len(owner.out_vars) == phase_count
    phase_index: int
    voltage: Var
    for phase_index, voltage in enumerate(owner.in_vars):
        # Component names retain phase order; evaluate the equation for that phase.
        component: Var = tuple(owner.event_dict)[phase_index + 1]
        component_value: float = bindings[component.uid]
        assert np.isfinite(component_value) and component_value > 0.0
        current_phasor: complex = vm / component_value if resistive else vm / (1j * omega * component_value)
        recovered: complex = vm * np.conj(current_phasor) * grid.Sbase / 3.0
        expected_power: float = max(source_power / (3.0 * grid.Sbase), 1.0e-9) * grid.Sbase if resistive else source_power / 3.0
        assert np.isclose(recovered.real if resistive else recovered.imag, expected_power, rtol=1e-12, atol=1e-12)
        # An exact sine current must satisfy the declared injection equation.
        time: float
        for time in (0.0, 0.001, 0.0037):
            bindings[voltage.uid] = np.sqrt(2.0) * vm * np.sin(omega * time)
            current: Var = owner.out_vars[phase_index]
            bindings[current.uid] = -np.sqrt(2.0) * np.imag(current_phasor * np.exp(1j * omega * time))
            if resistive:
                assert abs(owner.algebraic_eqs[phase_index].eval_uid(bindings)) < 1e-12
            else:
                derivative: float = -np.sqrt(2.0) * omega * np.real(current_phasor * np.exp(1j * omega * time))
                assert abs(owner.state_eqs[phase_index].eval_uid(bindings) - derivative) < 1e-10
    if source_power > 1.0e-6:
        combined: EmtModelTemplate = get_shunt_rlc_combo_emt_template(
            grid.var_factory, include_r=resistive, include_l=not resistive, include_c=False,
            phA=phases[0], phB=phases[1], phC=phases[2], connection_type=ShuntConnectionType.FloatingStar)
        combo_mapped: dict[Var, Const] = dict()
        assign_static_api_object_mapping_for_device(grid, load, combined.block, combo_mapped, None)
        combo_bindings: dict[int, float] = dict((variable.uid, float(value.value)) for variable, value in combo_mapped.items())
        combo_bindings[combined.block.external_mapping[VarPowerFlowReferenceType.VmSizing].uid] = vm
        component_values: np.ndarray = np.empty(phase_count)
        combo_values: np.ndarray = np.empty(phase_count)
        component_values[:] = tuple(bindings[variable.uid] for variable in owner.event_dict if variable is not vnom)
        combo_values[:] = tuple(float(expression.eval_uid(combo_bindings)) for variable, expression in combined.block.event_dict.items()
                                if variable.name.startswith("R_" if resistive else "L_"))
        np.testing.assert_allclose(component_values, combo_values, rtol=1e-12)
    else:
        # An explicit later R override remains independent of its guarded startup.
        override: float = 25.0
        bindings[component.uid] = override
        bindings[voltage.uid] = vm
        bindings[owner.out_vars[-1].uid] = -vm / override
        assert abs(owner.algebraic_eqs[-1].eval_uid(bindings)) < 1e-12


@pytest.mark.parametrize("mask", range(1, 8))
@pytest.mark.parametrize("vm", (0.9, 1.0, 1.03))
@pytest.mark.parametrize("combined", (False, True))
@pytest.mark.parametrize("reactive_power", (-12.0, 12.0))
def test_mapped_capacitor_preserves_signed_reactive_power(mask: int, vm: float, combined: bool, reactive_power: float) -> None:
    """Check mapped consumption sign through sinusoidal capacitor currents.

    :param mask: Nonempty phase bit mask.
    :param vm: Balanced runtime voltage reference.
    :param combined: Select the existing combined or standalone capacitor.
    :param reactive_power: Signed total MVAr; positive Q must not be coerced.
    :return: None; capacitor sign, base or phase law errors fail.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    bus: Bus = grid.add_bus(Bus(Vnom=10.0))
    load: Load = grid.add_load(bus, Load(Q=reactive_power))
    phases: tuple[bool, bool, bool] = (bool(mask & 1), bool(mask & 2), bool(mask & 4))
    template: EmtModelTemplate
    if combined:
        template = get_shunt_rlc_combo_emt_template(grid.var_factory, include_r=False, include_l=False, include_c=True,
            phA=phases[0], phB=phases[1], phC=phases[2], connection_type=ShuntConnectionType.FloatingStar)
    else:
        template = get_shunt_c_emt_template(grid.var_factory, phases[0], phases[1], phases[2])
    owner: Block = template.block if combined else template.block.children[0]
    mapped: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, load, template.block, mapped, None)
    bindings: dict[int, float] = dict((variable.uid, float(value.value)) for variable, value in mapped.items())
    bindings[template.block.external_mapping[VarPowerFlowReferenceType.VmSizing].uid] = vm
    omega: float = 2.0 * np.pi * grid.fBase
    variable: Var
    expression: Expr
    phase_index: int = 0
    for variable, expression in owner.event_dict.items():
        if variable.name.startswith("C_"):
            capacitance: float = float(expression.eval_uid(bindings))
            current: complex = 1j * omega * capacitance * vm
            consumed: complex = vm * np.conj(current) * grid.Sbase / 3.0
            assert np.isclose(consumed.imag, reactive_power / 3.0, atol=1e-12)
            assert (capacitance > 0.0) == (reactive_power < 0.0)
            bindings[variable.uid] = capacitance
            # Validate the actual declared phase law, independently of its C formula.
            capacitor_voltage: Var = owner.state_vars[phase_index]
            capacitor_derivative: Var = owner.diff_vars[phase_index]
            terminal_current: Var = owner.out_vars[phase_index]
            terminal_voltage: Var = owner.external_mapping[(VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C)["ABC".index(variable.name[-1])]]
            time: float
            for time in (0.0, 0.001, 0.0037):
                bindings[terminal_voltage.uid] = np.sqrt(2.0) * vm * np.sin(omega * time)
                bindings[capacitor_voltage.uid] = bindings[terminal_voltage.uid]
                bindings[capacitor_derivative.uid] = np.sqrt(2.0) * omega * vm * np.cos(omega * time)
                bindings[terminal_current.uid] = -capacitance * bindings[capacitor_derivative.uid]
                # Bind the current declared by the state law independently of
                # the terminal-output layout; combined C has an internal current.
                rhs_variables: list[Var] = owner.state_eqs[phase_index].get_vars()
                assert len(rhs_variables) == 2
                current_variable_count: int = 0
                rhs_variable: Var
                for rhs_variable in rhs_variables:
                    if rhs_variable.uid == variable.uid:
                        pass
                    else:
                        bindings[rhs_variable.uid] = bindings[terminal_current.uid]
                        current_variable_count += 1
                assert current_variable_count == 1
                if combined:
                    neutral: Var = owner.algebraic_vars[0]
                    bindings[neutral.uid] = 0.0
                else:
                    pass
                # The native model now owns capacitor voltage as a state and
                # expresses its derivative as an RHS, with injection sign intact.
                assert abs(owner.state_eqs[phase_index].eval_uid(bindings)
                    - bindings[capacitor_derivative.uid]) < 1e-10
                if combined:
                    assert abs(owner.algebraic_eqs[2 * phase_index].eval_uid(bindings)) < 1e-10
                    assert abs(owner.algebraic_eqs[2 * phase_index + 1].eval_uid(bindings)) < 1e-10
                else:
                    assert abs(owner.algebraic_eqs[phase_index].eval_uid(bindings)) < 1e-10
            phase_index += 1
        else:
            pass
    assert load.Q == reactive_power
    # Authored direct C follows its own positive physical-value path unchanged.
    direct: EmtModelTemplate = get_shunt_rlc_combo_emt_template(grid.var_factory, include_r=False,
        include_l=False, include_c=True, phA=True, phB=False, phC=False, direct_c_value=4e-6)
    assert next(expression for variable, expression in direct.block.event_dict.items() if variable.name == "C_A").value == 4e-6


@pytest.mark.parametrize("resistive,capacitive,combined", ((True, False, False), (False, False, False), (False, True, False), (False, True, True)))
def test_corrected_shunt_block_roundtrip_preserves_physical_contract(resistive: bool, capacitive: bool, combined: bool) -> None:
    """Round-trip canonical declared formulas and reference identity without migration.

    :param resistive: Select standalone R.
    :param capacitive: Select standalone C when not resistive; otherwise L.
    :param combined: Also cover the changed combined C owner.
    :return: None; any symbolic, mapping or UID change fails.
    """
    vf: VarFactory = VarFactory()
    template: EmtModelTemplate
    if combined:
        template = get_shunt_rlc_combo_emt_template(vf, include_r=False, include_l=False, include_c=True)
    elif resistive:
        template = get_shunt_r_emt_template(vf, True, True, True)
    elif capacitive:
        template = get_shunt_c_emt_template(vf, True, True, True)
    else:
        template = get_shunt_l_emt_template(vf, True, True, True)
    restored: Block = Block.parse(template.block.to_dict())
    assert restored.to_dict() == template.block.to_dict()
    vnom: Var = restored.external_mapping[VarPowerFlowReferenceType.VmSizing]
    assert vnom.uid == template.block.external_mapping[VarPowerFlowReferenceType.VmSizing].uid
    owner: Block = restored if combined else restored.children[0]
    assert owner.external_mapping[VarPowerFlowReferenceType.VmSizing].uid == vnom.uid
    bindings: dict[int, float] = dict()
    sizing_voltage_uids: set[int] = {vnom.uid}
    for reference in (VarPowerFlowReferenceType.Vm_A, VarPowerFlowReferenceType.Vm_B, VarPowerFlowReferenceType.Vm_C):
        phase_voltage: Var | None = owner.external_mapping.get(reference)
        if phase_voltage is not None:
            sizing_voltage_uids.add(phase_voltage.uid)
        else:
            pass
    for voltage_uid in sizing_voltage_uids:
        bindings[voltage_uid] = 1.03
    parameter: Var
    for parameter in owner.parameters:
        bindings[parameter.uid] = 2.0 * np.pi * 50.0 if parameter.name.startswith("w_base_") else (-0.04 if capacitive else 0.1)
    component: Var
    expression: Expr
    for component, expression in owner.event_dict.items():
        if component.uid in sizing_voltage_uids:
            pass
        else:
            value: float = float(expression.eval_uid(bindings))
            expected: float = 1.03 ** 2 / 0.3 if resistive else (
                0.12 / (2.0 * np.pi * 50.0 * 1.03 ** 2) if capacitive else 1.03 ** 2 / (0.3 * 2.0 * np.pi * 50.0))
            assert np.isclose(value, expected, rtol=1e-12)
    # Persistence retains a declared legacy expression; parsing never regenerates it.
    legacy_owner: Block = template.block if combined else template.block.children[0]
    legacy_vnom: Var = template.block.external_mapping[VarPowerFlowReferenceType.VmSizing]
    legacy_parameter: Var = next(variable for variable in legacy_owner.parameters if not variable.name.startswith("w_base_"))
    for component in tuple(legacy_owner.event_dict):
        if component.uid in sizing_voltage_uids:
            pass
        elif resistive:
            legacy_owner.event_dict[component] = legacy_vnom ** 2 / max(legacy_parameter, 1e-9)
        else:
            frequency: Var = next(variable for variable in legacy_owner.parameters if variable.name.startswith("w_base_"))
            if capacitive:
                if combined:
                    legacy_owner.event_dict[component] = 3.0 * legacy_parameter / (legacy_vnom ** 2 * frequency)
                else:
                    legacy_owner.event_dict[component] = legacy_parameter / (legacy_vnom ** 2 * frequency)
            else:
                legacy_owner.event_dict[component] = legacy_vnom ** 2 / (legacy_parameter * frequency)
    legacy: Block = Block.parse(template.block.to_dict())
    assert legacy.to_dict() == template.block.to_dict()


def test_sizing_reference_preserves_legacy_roundtrip() -> None:
    """Preserve a legacy Vm declaration without reinterpreting its saved equations.

    :return: None; source/reference/default identity must survive declarative parsing.
    """
    factory: VarFactory = VarFactory()
    template: EmtModelTemplate = get_shunt_rlc_combo_emt_template(
        factory, include_r=True, include_l=True, include_c=False,
    )
    block: Block = template.block
    sizing: Var = block.external_mapping.pop(VarPowerFlowReferenceType.VmSizing)
    # This fixture deliberately declares the old contract; parsing must retain
    # it rather than migrating by variable name, device type or component formula.
    block.external_mapping[VarPowerFlowReferenceType.Vm] = sizing
    block.set_parameter_in_model(sizing.name, 1.17)
    restored: Block = Block.parse(block.to_dict())
    assert restored.to_dict() == block.to_dict()
    assert VarPowerFlowReferenceType.VmSizing not in restored.external_mapping
    assert restored.external_mapping[VarPowerFlowReferenceType.Vm].uid == sizing.uid
    variable: Var
    expression: Expr
    for variable, expression in restored.event_dict.items():
        if variable.uid == sizing.uid:
            assert isinstance(expression, Const) and expression.value == 1.17
        else:
            pass


def test_sizing_reference_copy_rebind_default() -> None:
    """Keep the sizing role connected to the copied/rebound current nominal owner.

    :return: None; edits to a copy must not alter its source default or lose the role.
    """
    factory: VarFactory = VarFactory()
    template: EmtModelTemplate = get_shunt_rlc_combo_emt_template(
        factory, include_r=True, include_l=True, include_c=False,
    )
    original: Block = template.block
    sizing: Var = original.external_mapping[VarPowerFlowReferenceType.VmSizing]
    copied: Block = original.copy()
    copied.set_parameter_in_model(sizing.name, 1.21)
    rebound: Var = Var(sizing.name)
    # Use the canonical bulk update so formulas and the explicit reference follow
    # the same identity after rebinding; no parallel lookup state is retained.
    copied.update_model_bulk(dict(((sizing, rebound),)))
    assert copied.external_mapping[VarPowerFlowReferenceType.VmSizing].uid == rebound.uid
    restored: Block = Block.parse(copied.to_dict())
    assert restored.to_dict() == copied.to_dict()
    assert isinstance(original.event_dict[sizing], Const)
    assert original.event_dict[sizing].value == 1.0
    parameter: Var
    expression: Expr
    found: bool = False
    for parameter, expression in restored.event_dict.items():
        if parameter.uid == rebound.uid:
            assert isinstance(expression, Const) and expression.value == 1.21
            found = True
        else:
            pass
    assert found
