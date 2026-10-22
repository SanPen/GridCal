"""Tests for contextual RMS parameter diagnostics."""

from __future__ import annotations

from typing import Dict

import pytest

from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    resolve_constant_parameter_initial_value,
    resolve_runtime_parameter_initial_expression,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import DynamicSimulationMode, ParamPowerFlowReferenceType


@pytest.mark.parametrize("mapped", [False, True])
def test_unresolved_constant_parameter_reports_device_block_and_mapping(mapped: bool) -> None:
    """Fail a null constant with its complete RMS model context.

    :param mapped: Whether a nested UID-equivalent target declares the missing source.
    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("r_dc")
    owner_block: Block = Block(
        name="R-L equations",
        parameters=dict(((parameter, Const(None)),)),
    )
    mapped_parameter: Var = Var("r_dc", uid=parameter.uid)
    owner_block.api_obj_mapping[ParamPowerFlowReferenceType.dc_line_r_pu] = mapped_parameter if mapped else None
    root_block: Block = Block(name="DC line", children=list((owner_block,)),
                              api_obj_mapping=dict(((ParamPowerFlowReferenceType.omega_base, None),)))
    static_parameter_values: Dict[Var, Const] = dict()

    with pytest.raises(ValueError) as exception_info:
        resolve_constant_parameter_initial_value(
            device=device,
            simulation_mode=DynamicSimulationMode.RMS,
            root_block=root_block,
            owner_block=owner_block,
            parameter=parameter,
            declared_value=Const(None),
            problem_mapping=static_parameter_values,
        )

    message: str = str(exception_info.value)
    assert "r_dc" in message
    assert "R-L equations" in message
    assert "DC link" in message
    if mapped:
        assert "dc_line_r_pu" in message
    else:
        assert "not targeted by any api_obj_mapping" in message


def test_resolved_static_parameter_accepts_uid_equivalent_mapping() -> None:
    """A cloned mapped variable with the same UID must resolve the constant.

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
    )
    root_block: Block = Block(
        name="DC line",
        children=list((owner_block,)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.dc_line_r_pu, parameter),)),
    )
    static_parameter_values: Dict[Var, Const] = dict(((mapped_parameter, Const(0.015)),))

    resolved_value: Const = resolve_constant_parameter_initial_value(
        device=device,
        simulation_mode=DynamicSimulationMode.RMS,
        root_block=root_block,
        owner_block=owner_block,
        parameter=parameter,
        declared_value=Const(None),
        problem_mapping=static_parameter_values,
    )

    assert resolved_value.value == pytest.approx(0.015)


def test_unresolved_dynamic_parameter_reports_required_initialization_source() -> None:
    """Reject a null event parameter even if init_eqs has a late duplicate.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("l_dc")
    owner_block: Block = Block(
        name="R-L equations",
        event_dict=dict(((parameter, Const(None)),)),
    )
    # Simulate invalid post-construction mutation. The runtime resolver must not
    # revive init_eqs as a second parameter-value channel.
    owner_block.init_eqs[parameter] = Const(0.05)

    with pytest.raises(ValueError, match="Unresolved RMS dynamic parameter 'l_dc'"):
        resolve_runtime_parameter_initial_expression(
            device=device,
            simulation_mode=DynamicSimulationMode.RMS,
            root_block=owner_block,
            owner_block=owner_block,
            parameter=parameter,
            declared_expression=Const(None),
            problem_mapping=dict(),
            allow_deferred_initialization=False,
        )


def test_legacy_runtime_init_equation_is_normalized_into_event_dict() -> None:
    """Move an old parameter initializer to its authoritative event storage.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("l_dc")
    initialization_expression: Expr | Const = Const(0.05)
    owner_block: Block = Block(
        name="R-L equations",
        event_dict=dict(((parameter, Const(None)),)),
        init_eqs=dict(((parameter, initialization_expression),)),
    )

    # Block construction migrates legacy event-parameter initialization from
    # init_eqs to event_dict, which is the authoritative runtime representation.
    normalized_expression: Expr | Const = owner_block.event_dict[parameter]
    resolved_expression: Expr | Const = resolve_runtime_parameter_initial_expression(
        device=device,
        simulation_mode=DynamicSimulationMode.RMS,
        root_block=owner_block,
        owner_block=owner_block,
        parameter=parameter,
        declared_expression=normalized_expression,
        problem_mapping=dict(),
        allow_deferred_initialization=False,
    )

    assert parameter not in owner_block.init_eqs
    assert isinstance(resolved_expression, Const)
    assert resolved_expression.value == pytest.approx(0.05)


def test_rms_and_emt_runtime_mapping_share_precedence_without_mutation() -> None:
    """Resolve one runtime mapping identically without changing its Block role.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("runtime_parameter")
    mapped_parameter: Var = Var(
        "runtime_parameter",
        uid=parameter.uid,
        non_mutable_uid=parameter.non_mutable_uid,
    )
    fallback: Const = Const(0.1)
    owner_block: Block = Block(
        name="runtime owner",
        event_dict=dict(((parameter, fallback),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, parameter),)),
    )
    problem_mapping: Dict[Var, Const] = dict(((mapped_parameter, Const(0.25)),))
    simulation_modes: list[DynamicSimulationMode] = list((
        DynamicSimulationMode.RMS,
        DynamicSimulationMode.EMT,
    ))
    resolved_values: list[float] = list()

    for simulation_mode in simulation_modes:
        resolved_expression: Expr | Const = resolve_runtime_parameter_initial_expression(
            device=device,
            simulation_mode=simulation_mode,
            root_block=owner_block,
            owner_block=owner_block,
            parameter=parameter,
            declared_expression=fallback,
            problem_mapping=problem_mapping,
            allow_deferred_initialization=False,
        )
        assert isinstance(resolved_expression, Const)
        resolved_values.append(float(resolved_expression.value))

    assert resolved_values == pytest.approx(list((0.25, 0.25)))
    assert parameter in owner_block.event_dict
    assert parameter not in owner_block.parameters
    assert owner_block.event_dict[parameter] is fallback
