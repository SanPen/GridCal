"""Tests for contextual EMT parameter diagnostics."""

from __future__ import annotations

from typing import Dict

import pytest

from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import (
    EmtProblemDae,
    _resolve_emt_constant_parameter_value,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_governor_emt
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template_with_ref,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType


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
        _resolve_emt_constant_parameter_value(
            device=device,
            root_block=root_block,
            owner_block=owner_block,
            parameter=parameter,
            declared_value=Const(None),
            static_parameter_values=static_parameter_values,
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

    resolved_value: Const = _resolve_emt_constant_parameter_value(
        device=device,
        root_block=root_block,
        owner_block=owner_block,
        parameter=parameter,
        declared_value=Const(None),
        static_parameter_values=static_parameter_values,
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
    """A runtime placeholder without PF or explicit initialization must fail.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("l_dc")
    owner_block: Block = Block(
        name="R-L equations",
        event_dict=dict(((parameter, Const(None)),)),
    )

    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem._variable_parameters = list((parameter,))
    problem._event_parameters_eqs = list((Const(None),))
    problem._init_eqs_flat = dict()
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
