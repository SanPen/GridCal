"""Tests for contextual EMT parameter diagnostics."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pytest

from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    resolve_constant_parameter_initial_value,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_governor_emt
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template_with_ref,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import (
    DynamicSimulationMode,
    EmtInitializationMethod,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)


def _build_runtime_seed_test_problem() -> EmtProblemDae:
    """Build the minimum problem-local storage required by runtime seed helpers.

    The object deliberately bypasses full electrical construction so these unit
    tests exercise only ownership and mutation semantics.

    :return: Uninitialized EMT problem with empty runtime storage.
    """
    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem._temp_init_guess = dict()
    problem._temp_post_init_guess = dict()
    problem._uid2idx_event_params = dict()
    problem._event_params_values = np.zeros(0, dtype=np.float64)
    problem._event_parameters_eqs = list()
    problem._runtime_parameter_eqs0 = list()
    problem._runtime_all_parameters_source = list()
    problem._runtime_all_eqs_source = list()
    problem._local_external_mapping_by_block_uid = dict()
    return problem


def _assert_mapping_target_is_required_runtime_parameter(
        block: Block,
        key: ParamPowerFlowReferenceType,
) -> None:
    """Verify that one PF-derived API target is owned by runtime storage.

    Generator-sharing values are calculated after static parameter assembly.
    Requiring an unresolved event placeholder protects that ordering and ensures
    the value cannot be accepted as a static fallback.

    :param block: Block that owns both the API mapping and runtime declaration.
    :param key: PF-derived generator-sharing mapping key to inspect.
    :return: None.
    """
    target: Var | None = block.api_obj_mapping.get(key, None)

    assert isinstance(target, Var)
    assert target in block.event_dict
    assert block.event_dict[target].value is None
    assert target not in block.parameters


def test_pf_derived_generator_sharing_targets_are_runtime_parameters() -> None:
    """Keep all predefined generator-sharing targets outside static parameters.

    The power-flow seed is only available after the EMT device model has passed
    static validation. Each predefined template must therefore expose sharing
    targets through ``event_dict`` while retaining its local API mapping.

    :return: None.
    """
    governor_factory: VarFactory = VarFactory()
    governor_block: Block = get_governor_emt(vf=governor_factory).block
    _assert_mapping_target_is_required_runtime_parameter(
        block=governor_block,
        key=ParamPowerFlowReferenceType.generator_share_p_ref,
    )

    simple_generator_factory: VarFactory = VarFactory()
    simple_generator_block: Block = get_simple_generator_emt_template(
        vf=simple_generator_factory,
    ).block
    _assert_mapping_target_is_required_runtime_parameter(
        block=simple_generator_block,
        key=ParamPowerFlowReferenceType.generator_share_p_ref,
    )
    _assert_mapping_target_is_required_runtime_parameter(
        block=simple_generator_block,
        key=ParamPowerFlowReferenceType.generator_share_q_ref,
    )

    thevenin_factory: VarFactory = VarFactory()
    thevenin_root: Block = get_generator_thevenin_rl_emt_template_with_ref(
        vf=thevenin_factory,
    ).block
    thevenin_block: Block = thevenin_root.children[0]
    _assert_mapping_target_is_required_runtime_parameter(
        block=thevenin_block,
        key=ParamPowerFlowReferenceType.generator_share_enable,
    )
    _assert_mapping_target_is_required_runtime_parameter(
        block=thevenin_block,
        key=ParamPowerFlowReferenceType.generator_share_p_ref,
    )
    _assert_mapping_target_is_required_runtime_parameter(
        block=thevenin_block,
        key=ParamPowerFlowReferenceType.generator_share_q_ref,
    )


def test_unresolved_emt_constant_reports_device_block_and_mapping() -> None:
    """Report the complete model ownership of a null EMT constant.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("r_dc")
    owner_block: Block = Block(
        name="R-L equations",
        parameters=dict(((parameter, Const(None)),)),
    )
    root_block: Block = Block(name="DC line", children=list((owner_block,)))
    static_parameter_values: Dict[Var, Const] = dict()

    with pytest.raises(ValueError) as exception_info:
        resolve_constant_parameter_initial_value(
            device=device,
            simulation_mode=DynamicSimulationMode.EMT,
            root_block=root_block,
            owner_block=owner_block,
            parameter=parameter,
            declared_value=Const(None),
            problem_mapping=static_parameter_values,
        )

    message: str = str(exception_info.value)
    assert "Unresolved EMT constant parameter" in message
    assert "r_dc" in message
    assert "R-L equations" in message
    assert "DC link" in message
    assert "not targeted by any api_obj_mapping" in message


def test_emt_constant_accepts_a_uid_equivalent_static_mapping() -> None:
    """Resolve an EMT constant from a cloned variable with the same UID.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("r_dc")
    mapped_parameter: Var = Var(
        "r_dc",
        uid=parameter.uid,
        non_mutable_uid=parameter.non_mutable_uid,
    )
    owner_block: Block = Block(
        name="R-L equations",
        parameters=dict(((parameter, Const(None)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.dc_line_r_pu, parameter),)),
    )
    root_block: Block = Block(
        name="DC line",
        children=list((owner_block,)),
    )
    static_parameter_values: Dict[Var, Const] = dict(((mapped_parameter, Const(0.02)),))

    resolved_value: Const = resolve_constant_parameter_initial_value(
        device=device,
        simulation_mode=DynamicSimulationMode.EMT,
        root_block=root_block,
        owner_block=owner_block,
        parameter=parameter,
        declared_value=Const(None),
        problem_mapping=static_parameter_values,
    )

    assert resolved_value.value == pytest.approx(0.02)


def test_emt_problem_ignores_mapping_only_static_target() -> None:
    """Do not register one EMT static value unless ``parameters`` declares it.

    :return: None.
    """
    parameter: Var = Var("mapping_only")
    block: Block = Block(
        name="legacy mapping-only block",
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.dc_line_r_pu, parameter),)),
    )
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=block,
        static_parameter_values_mapping=dict(((parameter, Const(0.25)),)),
        glob_time=Var("time"),
    )

    assert problem.get_constant_parameters() == list()
    assert problem.get_parameters_values() == list()


def test_emt_problem_maps_declared_child_static_parameter() -> None:
    """Apply one mapped value to the child block that owns the declaration.

    :return: None.
    """
    parameter: Var = Var("declared_parameter")
    child_block: Block = Block(
        name="parameter owner",
        parameters=dict(((parameter, Const(None)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.dc_line_r_pu, parameter),)),
    )
    root_block: Block = Block(name="wrapper", children=list((child_block,)))
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=root_block,
        static_parameter_values_mapping=dict(((parameter, Const(0.25)),)),
        glob_time=Var("time"),
    )

    assert problem.get_constant_parameters() == list((parameter,))
    assert problem.get_parameters_values()[0].value == pytest.approx(0.25)


def test_emt_problem_maps_declared_child_event_parameter() -> None:
    """Use a mapped device value as an event parameter's initial baseline.

    :return: None.
    """
    parameter: Var = Var("event_parameter")
    mapped_parameter: Var = Var(
        "event_parameter",
        uid=parameter.uid,
        non_mutable_uid=parameter.non_mutable_uid,
    )
    child_block: Block = Block(
        name="event parameter owner",
        event_dict=dict(((parameter, Const(0.1)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, parameter),)),
    )
    root_block: Block = Block(name="wrapper", children=list((child_block,)))
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=root_block,
        static_parameter_values_mapping=dict(((mapped_parameter, Const(0.25)),)),
        glob_time=Var("time"),
    )

    assert problem.get_constant_parameters() == list()
    assert problem.get_variable_parameters() == list((parameter,))
    assert problem.get_event_parameter_equations()[0].value == pytest.approx(0.25)
    assert problem.event_params_init_dict[parameter.uid] == pytest.approx(0.25)
    assert child_block.event_dict[parameter].value == pytest.approx(0.1)


def test_emt_problem_maps_mode_parameter_without_changing_its_role() -> None:
    """Apply a mapped baseline while preserving a discrete mode declaration.

    :return: None.
    """
    parameter: Var = Var("mode_parameter")
    fallback: Const = Const(0.0)
    block: Block = Block(
        name="mode owner",
        mode_dict=dict(((parameter, fallback),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.converter_control_mode_1, parameter),)),
    )
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=block,
        static_parameter_values_mapping=dict(((parameter, Const(1.0)),)),
        glob_time=Var("time"),
    )

    assert problem.get_variable_parameters() == list((parameter,))
    assert problem.get_event_parameter_equations()[0].value == pytest.approx(1.0)
    assert parameter in block.mode_dict
    assert parameter not in block.event_dict
    assert block.mode_dict[parameter] is fallback


def test_emt_api_runtime_seed_does_not_mutate_event_dict() -> None:
    """Keep an API-derived runtime value in problem-local seed storage.

    :return: None.
    """
    parameter: Var = Var("event_parameter")
    fallback: Const = Const(0.1)
    block: Block = Block(
        name="runtime owner",
        event_dict=dict(((parameter, fallback),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, parameter),)),
    )
    problem: EmtProblemDae = _build_runtime_seed_test_problem()

    problem._assign_event_mapping_value_if_present(
        mdl=block,
        key=ParamPowerFlowReferenceType.Pl0,
        value=0.25,
    )

    assert block.event_dict[parameter] is fallback
    assert problem._temp_init_guess[parameter.uid] == pytest.approx(0.25)
    assert parameter.uid not in problem._temp_post_init_guess


def test_emt_internal_runtime_seed_does_not_mutate_event_dict() -> None:
    """Keep an internal device-derived runtime value outside the source Block.

    :return: None.
    """
    parameter: Var = Var("sbase")
    fallback: Const = Const(1.0)
    block: Block = Block(
        name="runtime owner",
        event_dict=dict(((parameter, fallback),)),
    )
    problem: EmtProblemDae = _build_runtime_seed_test_problem()

    problem.set_internal_runtime_if_exists(
        mdl=block,
        var_name="sbase",
        value=100.0,
    )

    assert block.event_dict[parameter] is fallback
    assert problem._temp_init_guess[parameter.uid] == pytest.approx(100.0)
    assert parameter.uid not in problem._temp_post_init_guess


def test_emt_external_runtime_seed_does_not_mutate_event_dict() -> None:
    """Keep a PF-derived external runtime value outside the source Block.

    :return: None.
    """
    parameter: Var = Var("v_peak")
    fallback: Const = Const(1.0)
    block: Block = Block(
        name="runtime owner",
        event_dict=dict(((parameter, fallback),)),
        external_mapping=dict(((VarPowerFlowReferenceType.Vpk, parameter),)),
    )
    problem: EmtProblemDae = _build_runtime_seed_test_problem()

    problem.set_external_param(
        mdl=block,
        key=VarPowerFlowReferenceType.Vpk,
        value=1.25,
    )

    assert block.event_dict[parameter] is fallback
    assert problem._temp_init_guess[parameter.uid] == pytest.approx(1.25)
    assert problem._temp_post_init_guess[parameter.uid] == pytest.approx(1.25)


def test_emt_problem_rejects_duplicate_static_parameter_ownership() -> None:
    """Reject one parameter UID declared by both a wrapper and its child.

    :return: None.
    """
    parameter: Var = Var("duplicated_parameter")
    child_block: Block = Block(
        name="parameter owner",
        parameters=dict(((parameter, Const(1.0)),)),
    )
    root_block: Block = Block(
        name="invalid wrapper",
        parameters=dict(((parameter, Const(1.0)),)),
        children=list((child_block,)),
    )

    with pytest.raises(ValueError, match="declared more than once"):
        EmtProblemTemplate(
            sys_block=root_block,
            static_parameter_values_mapping=dict(),
            glob_time=Var("time"),
        )


def test_unresolved_emt_runtime_parameter_reports_required_source() -> None:
    """Reject a null runtime parameter even if init_eqs contains a duplicate.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("l_dc")
    owner_block: Block = Block(
        name="R-L equations",
        event_dict=dict(((parameter, Const(None)),)),
    )

    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem.options = EmtOptions(initialization_method=EmtInitializationMethod.Explicit)
    problem._variable_parameters = list((parameter,))
    problem._event_parameters_eqs = list((Const(None),))
    # Initialization equations belong to algebraic/state variables and must not
    # become a second parameter-value channel.
    problem._init_eqs_flat = dict(((parameter, Const(0.1)),))
    problem._runtime_parameter_owner_blocks = dict(((parameter.uid, owner_block),))
    problem._runtime_parameter_devices = dict(((parameter.uid, device),))
    problem._temp_init_guess = dict()
    problem._temp_post_init_guess = dict()
    problem.event_params_init_dict = dict()
    problem._runtime_mode_uids = set()

    with pytest.raises(ValueError, match="Unresolved EMT dynamic parameter 'l_dc'"):
        problem._validate_runtime_parameter_sources_after_power_flow()


def test_emt_runtime_parameter_accepts_power_flow_seed() -> None:
    """A PF-owned EMT placeholder is valid after its seed was recorded.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("i_dc_0")
    owner_block: Block = Block(
        name="R-L equations",
        event_dict=dict(((parameter, Const(None)),)),
    )

    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem.options = EmtOptions(initialization_method=EmtInitializationMethod.Explicit)
    problem._variable_parameters = list((parameter,))
    problem._event_parameters_eqs = list((Const(None),))
    problem._init_eqs_flat = dict()
    problem._runtime_parameter_owner_blocks = dict(((parameter.uid, owner_block),))
    problem._runtime_parameter_devices = dict(((parameter.uid, device),))
    problem._temp_init_guess = dict(((parameter.uid, 0.0),))
    problem._temp_post_init_guess = dict()
    problem.event_params_init_dict = dict()
    problem._runtime_mode_uids = set()

    problem._validate_runtime_parameter_sources_after_power_flow()
