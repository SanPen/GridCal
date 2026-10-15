from __future__ import annotations

import json
import math
from typing import Any, Dict, List

import numpy as np
import pytest

import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory, build_persisted_identity_lookup
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import (
    BlockParser,
    BlockSaver,
    expr_to_dict,
    parse_expr,
    parse_expr_list,
    symbolic_objects_to_dict,
)
from VeraGridEngine.enumerations import LogSeverity, ParamPowerFlowReferenceType


def test_symbolic_object_serialization_does_not_mutate_source_registry() -> None:
    """Keep symbolic serialization read-only even for a noncanonical lookup key.

    Factory registries normally use the object's UID as their key, but a saver
    must not modify its input while iterating if a historical or reconstructed
    registry uses another valid lookup key.

    :return: None.
    """
    source_constant: sym.Const = sym.Const(value=3.0)
    source_registry: Dict[int | str, sym.Const] = dict((("legacy-key", source_constant),))
    original_keys: tuple[int | str, ...] = tuple(source_registry.keys())

    serialized_objects: List[Dict[str, Any]] = symbolic_objects_to_dict(
        obj_dict=source_registry,
    )

    assert tuple(source_registry.keys()) == original_keys
    assert source_registry["legacy-key"] is source_constant
    assert serialized_objects == list((dict(
        type="Const",
        value=3.0,
        uid=source_constant.uid,
    ),))


def test_shared_expression_roundtrip_preserves_expr_ref_identity() -> None:
    """
    Verify that repeated composite expressions keep one shared object after roundtrip.

    :return: None.
    """
    variable: sym.Var = sym.Var("x")
    shared_expression: sym.Expr = variable + sym.Const(1.0)
    expression: sym.Expr = shared_expression * shared_expression + sym.sin(shared_expression)
    const_dict: Dict[int, sym.Const] = dict()
    var_dict: Dict[int, sym.Var] = dict(((variable.non_mutable_uid, variable),))
    diff_var_dict: Dict[int, sym.Var] = dict()

    payload: Dict[str, Any] = expr_to_dict(
        expr=expression,
        const_dict=const_dict,
        var_dict=var_dict,
        diff_var_dict=diff_var_dict,
    )
    restored: sym.Expr = parse_expr(
        data=payload,
        const_dict=const_dict,
        var_dict=var_dict,
        diff_var_dict=diff_var_dict,
    )
    restored_payload: Dict[str, Any] = expr_to_dict(
        expr=restored,
        const_dict=const_dict,
        var_dict=var_dict,
        diff_var_dict=diff_var_dict,
    )

    assert '"ExprRef"' in json.dumps(payload)
    assert isinstance(restored, sym.BinOp)
    assert isinstance(restored.left, sym.BinOp)
    assert isinstance(restored.right, sym.Func)
    assert restored.left.left is restored.left.right
    assert restored.left.left is restored.right.arg
    assert restored_payload == payload
    assert math.isclose(restored.eval(x=2.0), expression.eval(x=2.0), rel_tol=1.0e-12)


def test_legacy_expr_ref_resolves_across_expression_list_entries() -> None:
    """
    Verify the historical backward-reference layout used by legacy archives.

    :return: None.
    """
    variable: sym.Var = sym.Var("x")
    constant: sym.Const = sym.Const(1.0)
    full_expression: Dict[str, Any] = dict(
        type="BinOp",
        op="+",
        left=dict(type="Var", uid=variable.non_mutable_uid),
        right=dict(type="Const", uid=constant.uid),
        uid=101,
        graph_id=7,
    )
    referencing_expression: Dict[str, Any] = dict(
        type="BinOp",
        op="*",
        left=dict(type="ExprRef", graph_id=7),
        right=dict(type="Const", uid=constant.uid),
        uid=102,
        graph_id=8,
    )
    payload: List[Dict[str, Any]] = list((full_expression, referencing_expression))
    parsed_expressions: List[sym.Expr] = parse_expr_list(
        lst=payload,
        const_dict=dict(((constant.uid, constant),)),
        var_dict=dict(((variable.non_mutable_uid, variable),)),
        diff_var_dict=dict(),
    )

    referenced_bin_op: sym.BinOp = parsed_expressions[1]
    assert isinstance(referenced_bin_op, sym.BinOp)
    assert referenced_bin_op.left is parsed_expressions[0]
    assert referenced_bin_op.eval(x=2.0) == 3.0


def test_block_roundtrip_shares_expression_registry_across_fields() -> None:
    """
    Verify that one block registry spans equations, events, modes and discrete equations.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    variable: sym.Var = source_factory.add_var("x")
    event_variable: sym.Var = source_factory.add_var("event")
    mode_variable: sym.Var = source_factory.add_var("mode")
    discrete_variable: sym.Var = source_factory.add_var("discrete")
    shared_expression: sym.Expr = variable + sym.Const(1.0)
    source_block: Block = Block(
        algebraic_vars=list((variable, event_variable, mode_variable, discrete_variable)),
        algebraic_eqs=list((shared_expression,)),
        event_dict=dict(((event_variable, shared_expression),)),
        mode_dict=dict(((mode_variable, shared_expression),)),
        discrete_eqs=dict(((discrete_variable, shared_expression),)),
        name="legacy_expr_ref_block",
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    serialized_block: Dict[str, Any] = saver.get_blocks()[source_block.uid]

    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())
    restored_block: Block = parser.parse_block(saver.get_blocks(), source_block.uid)
    restored_expression: sym.Expr = restored_block.algebraic_eqs[0]
    restored_event_expression: sym.Expr = next(iter(restored_block.event_dict.values()))
    restored_mode_expression: sym.Expr = next(iter(restored_block.mode_dict.values()))
    restored_discrete_expression: sym.Expr = next(iter(restored_block.discrete_eqs.values()))

    assert serialized_block["event_dict"][0]["expr"]["type"] == "ExprRef"
    assert serialized_block["mode_dict"][0]["expr"]["type"] == "ExprRef"
    assert serialized_block["discrete_eqs"][0]["expr"]["type"] == "ExprRef"
    assert restored_event_expression is restored_expression
    assert restored_mode_expression is restored_expression
    assert restored_discrete_expression is restored_expression


def test_legacy_mapping_only_static_target_is_restored_as_parameter() -> None:
    """Backfill one historical mapping-only static target and report an info entry.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    parameter: sym.Var = source_factory.add_var("legacy_static_parameter")
    source_block: Block = Block(
        name="legacy static block",
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.dc_line_r_pu, parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_blocks: List[Block] = parser.parse_blocks(
        blocks_data=saver.get_blocks(),
        main_block_uids=list((source_block.uid,)),
    )
    restored_block: Block = restored_blocks[0]
    restored_parameter: sym.Var | None = restored_block.api_obj_mapping.get(
        ParamPowerFlowReferenceType.dc_line_r_pu,
        None,
    )

    assert restored_parameter is not None
    assert restored_parameter in restored_block.parameters
    assert restored_block.parameters[restored_parameter].value is None
    assert logger.entries[-1].msg == "Migrated legacy dynamic parameter declarations"
    assert logger.entries[-1].value == "1"
    assert logger.entries[-1].severity == LogSeverity.Information


def test_legacy_parent_child_static_parameter_copy_keeps_only_child_owner() -> None:
    """Repair the wrapper copy written by historical EMT editor save paths.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    parameter: sym.Var = source_factory.add_var("Rnn")
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Rnn
    child_block: Block = Block(
        name="pi_line_equations",
        parameters=dict(((parameter, sym.Const(None)),)),
        api_obj_mapping=dict(((mapping_key, parameter),)),
    )
    root_block: Block = Block(
        name="pi_line_wrapper",
        children=list((child_block,)),
        parameters=dict(((parameter, sym.Const(None)),)),
        api_obj_mapping=dict(((mapping_key, parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(root_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_root: Block = parser.parse_block(saver.get_blocks(), root_block.uid)
    restored_child: Block = restored_root.children[0]
    restored_parameter: sym.Var | None = restored_child.api_obj_mapping.get(mapping_key, None)

    assert restored_parameter is not None
    assert restored_root.parameters == dict()
    assert restored_root.api_obj_mapping == dict()
    assert restored_parameter in restored_child.parameters
    assert logger.entries[-1].msg == "Migrated legacy dynamic parameter declarations"
    assert logger.entries[-1].severity == LogSeverity.Information


def test_legacy_equivalent_sibling_parameter_owners_are_not_rewritten() -> None:
    """Leave an ambiguous sibling ownership conflict unchanged and report it.

    Equal-depth siblings provide no structural evidence for selecting one owner.
    The loader must not depend on child traversal order and silently delete the
    other declaration.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    parameter: sym.Var = source_factory.add_var("Rnn")
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Rnn
    first_child: Block = Block(
        name="first line equations",
        parameters=dict(((parameter, sym.Const(1.0)),)),
        api_obj_mapping=dict(((mapping_key, parameter),)),
    )
    second_child: Block = Block(
        name="second line equations",
        parameters=dict(((parameter, sym.Const(2.0)),)),
        api_obj_mapping=dict(((mapping_key, parameter),)),
    )
    root_block: Block = Block(
        name="ambiguous line wrapper",
        children=list((first_child, second_child)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(root_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_root: Block = parser.parse_block(saver.get_blocks(), root_block.uid)
    restored_first_child: Block = restored_root.children[0]
    restored_second_child: Block = restored_root.children[1]

    assert len(restored_first_child.parameters) == 1
    assert len(restored_second_child.parameters) == 1
    assert mapping_key in restored_first_child.api_obj_mapping
    assert mapping_key in restored_second_child.api_obj_mapping
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == (
        "Legacy static parameter has multiple equivalent owners; migration was skipped"
    )
    assert logger.entries[0].severity == LogSeverity.Warning


def test_legacy_ambiguous_owner_does_not_block_independent_migration() -> None:
    """Migrate an unambiguous UID while preserving an ambiguous sibling UID.

    A conflict belonging to one stable identity must not disable safe repairs
    elsewhere in the same root. The ambiguous declarations remain byte-for-byte
    equivalent at the block-contract level, while the independent wrapper
    mapping is localized on its unique child owner.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    ambiguous_parameter: sym.Var = source_factory.add_var("Rnn")
    independent_parameter: sym.Var = source_factory.add_var("Linv_aa")
    ambiguous_mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Rnn
    independent_mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Linv_aa
    first_ambiguous_child: Block = Block(
        name="first ambiguous line equations",
        parameters=dict(((ambiguous_parameter, sym.Const(1.0)),)),
        api_obj_mapping=dict(((ambiguous_mapping_key, ambiguous_parameter),)),
    )
    second_ambiguous_child: Block = Block(
        name="second ambiguous line equations",
        parameters=dict(((ambiguous_parameter, sym.Const(2.0)),)),
        api_obj_mapping=dict(((ambiguous_mapping_key, ambiguous_parameter),)),
    )
    independent_child: Block = Block(
        name="independent line equations",
        parameters=dict(((independent_parameter, sym.Const(None)),)),
    )
    root_block: Block = Block(
        name="partially ambiguous line wrapper",
        children=list((first_ambiguous_child, second_ambiguous_child, independent_child)),
        api_obj_mapping=dict(((independent_mapping_key, independent_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(root_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_root: Block = parser.parse_block(saver.get_blocks(), root_block.uid)
    restored_first_ambiguous_child: Block = restored_root.children[0]
    restored_second_ambiguous_child: Block = restored_root.children[1]
    restored_independent_child: Block = restored_root.children[2]
    restored_independent_parameter: sym.Var | None = restored_independent_child.api_obj_mapping.get(
        independent_mapping_key,
        None,
    )

    assert ambiguous_mapping_key in restored_first_ambiguous_child.api_obj_mapping
    assert ambiguous_mapping_key in restored_second_ambiguous_child.api_obj_mapping
    assert len(restored_first_ambiguous_child.parameters) == 1
    assert len(restored_second_ambiguous_child.parameters) == 1
    assert independent_mapping_key not in restored_root.api_obj_mapping
    assert restored_independent_parameter is not None
    assert restored_independent_parameter in restored_independent_child.parameters
    assert len(logger.entries) == 2
    assert logger.entries[0].msg == (
        "Legacy static parameter has multiple equivalent owners; migration was skipped"
    )
    assert logger.entries[0].severity == LogSeverity.Warning
    assert logger.entries[1].msg == "Migrated legacy dynamic parameter declarations"
    assert logger.entries[1].severity == LogSeverity.Information


def test_legacy_parent_mapping_is_moved_to_child_parameter_owner() -> None:
    """Move a required wrapper-only mapping to its descendant declaration.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    parameter: sym.Var = source_factory.add_var("Linv_aa")
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Linv_aa
    child_block: Block = Block(
        name="pi_line_equations",
        parameters=dict(((parameter, sym.Const(None)),)),
    )
    root_block: Block = Block(
        name="pi_line_wrapper",
        children=list((child_block,)),
        api_obj_mapping=dict(((mapping_key, parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(root_block, main=True)
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_root: Block = parser.parse_block(saver.get_blocks(), root_block.uid)
    restored_child: Block = restored_root.children[0]
    restored_parameter: sym.Var | None = restored_child.api_obj_mapping.get(mapping_key, None)

    assert restored_parameter is not None
    assert restored_root.api_obj_mapping == dict()
    assert restored_parameter in restored_child.parameters


def test_legacy_parent_mapping_localizes_beside_concrete_child_parameter() -> None:
    """Move a wrapper mapping beside a concrete child fallback to its owner.

    Historical RMS line files stored ``g``, ``b`` and ``bsh`` mappings on a
    wrapper while their child equation block contained concrete parameter
    fallbacks. The mapping must become owner-local so problem construction can
    replace the generic fallback with the physical static-device value.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    parameter: sym.Var = source_factory.add_var("g")
    fallback_value: float = 5.0
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.g
    child_block: Block = Block(
        name="legacy line equations",
        parameters=dict(((parameter, sym.Const(fallback_value)),)),
    )
    root_block: Block = Block(
        name="legacy line wrapper",
        children=list((child_block,)),
        api_obj_mapping=dict(((mapping_key, parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(root_block, main=True)
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_root: Block = parser.parse_block(saver.get_blocks(), root_block.uid)
    restored_child: Block = restored_root.children[0]
    restored_parameters: List[sym.Var] = list(restored_child.parameters)
    restored_parameter: sym.Var = restored_parameters[0]
    restored_mapping_target: sym.Var | None = restored_child.api_obj_mapping.get(
        mapping_key,
        None,
    )

    assert restored_root.api_obj_mapping == dict()
    assert restored_mapping_target is restored_parameter
    assert restored_child.parameters[restored_parameter].value == fallback_value


@pytest.mark.parametrize(
    "fallback_value",
    tuple((None, -0.1)),
)
def test_legacy_parent_runtime_mapping_moves_to_declaration_owner(
        fallback_value: float | None,
) -> None:
    """Localize a wrapper runtime mapping without changing its declaration.

    Null and concrete event fallbacks retain their runtime role. In both cases
    the mapping is moved to the real owner so the physical operating point can
    initialize the declaration through the recursive contract.

    :param fallback_value: Child event value stored by the legacy file.
    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    runtime_parameter: sym.Var = source_factory.add_var("Pl0")
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Pl0
    child_block: Block = Block(
        name="legacy RMS load equations",
        event_dict=dict(((runtime_parameter, sym.Const(fallback_value)),)),
    )
    root_block: Block = Block(
        name="legacy RMS load wrapper",
        children=list((child_block,)),
        api_obj_mapping=dict(((mapping_key, runtime_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(root_block, main=True)
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_root: Block = parser.parse_block(saver.get_blocks(), root_block.uid)
    restored_child: Block = restored_root.children[0]
    restored_runtime_parameters: List[sym.Var] = list(restored_child.event_dict)
    restored_runtime_parameter: sym.Var = restored_runtime_parameters[0]
    restored_mapping_target: sym.Var | None = restored_child.api_obj_mapping.get(
        mapping_key,
        None,
    )

    assert restored_root.api_obj_mapping == dict()
    assert restored_child.event_dict[restored_runtime_parameter].value == fallback_value
    assert restored_mapping_target is restored_runtime_parameter


def test_legacy_parent_event_mapping_is_localized_without_changing_role() -> None:
    """Move a copied wrapper mapping onto its runtime child declaration.

    Old non-recursive initialization stored a child's API mapping on its parent.
    The recursive contract must retain the child as owner without changing the
    storage role declared by ``event_dict``.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    parameter: sym.Var = source_factory.add_var("Pmin")
    fallback_value: float = -1.0
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Pmin
    child_block: Block = Block(
        name="legacy governor equations",
        event_dict=dict(((parameter, sym.Const(fallback_value)),)),
    )
    root_block: Block = Block(
        name="legacy governor wrapper",
        children=list((child_block,)),
        api_obj_mapping=dict(((mapping_key, parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(root_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_root: Block = parser.parse_block(saver.get_blocks(), root_block.uid)
    restored_child: Block = restored_root.children[0]
    restored_parameter: sym.Var | None = restored_child.api_obj_mapping.get(mapping_key, None)

    assert restored_parameter is not None
    assert restored_root.api_obj_mapping == dict()
    assert restored_parameter in restored_child.event_dict
    assert restored_parameter not in restored_child.parameters
    assert restored_child.event_dict[restored_parameter].value == fallback_value
    assert logger.entries[-1].msg == "Migrated legacy dynamic parameter declarations"
    assert logger.entries[-1].value == "1"
    assert logger.entries[-1].severity == LogSeverity.Information


@pytest.mark.parametrize(
    "mapping_key",
    tuple((ParamPowerFlowReferenceType.Pmin, ParamPowerFlowReferenceType.R1)),
)
def test_mapped_event_target_preserves_runtime_storage(
        mapping_key: ParamPowerFlowReferenceType,
) -> None:
    """Keep a mapped event target runtime regardless of its enum key.

    The target collection declares mutability. A constant fallback inside
    ``event_dict`` remains event-capable even when its initial value can be
    supplied by a static-device property.

    :param mapping_key: Static reference to exercise outside the governor signature.
    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    parameter: sym.Var = source_factory.add_var(mapping_key.value)
    fallback_value: float = -1.0
    source_block: Block = Block(
        name="legacy governor",
        event_dict=dict(((parameter, sym.Const(fallback_value)),)),
        api_obj_mapping=dict(((mapping_key, parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_blocks: List[Block] = parser.parse_blocks(
        blocks_data=saver.get_blocks(),
        main_block_uids=list((source_block.uid,)),
    )
    restored_block: Block = restored_blocks[0]
    restored_parameter: sym.Var | None = restored_block.api_obj_mapping.get(
        mapping_key,
        None,
    )

    assert restored_parameter is not None
    assert restored_parameter in restored_block.event_dict
    assert restored_block.event_dict[restored_parameter].value == fallback_value
    assert restored_parameter not in restored_block.parameters
    assert len(logger.entries) == 0


def test_partial_governor_like_mapping_is_not_migrated() -> None:
    """Keep an unrelated ``K/Pmin/Pmax`` controller exactly as serialized.

    The former three-key heuristic classified this partial mapping as a Kundur
    governor and removed valid runtime mappings. Only the complete historical
    eleven-key signature is sufficient evidence for that compatibility repair.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    mapping_references: tuple[ParamPowerFlowReferenceType, ...] = (
        ParamPowerFlowReferenceType.K,
        ParamPowerFlowReferenceType.Pmin,
        ParamPowerFlowReferenceType.Pmax,
    )
    event_values: Dict[sym.Var, sym.Expr] = dict()
    api_obj_mapping: Dict[ParamPowerFlowReferenceType, sym.Var] = dict()
    mapping_reference: ParamPowerFlowReferenceType
    for mapping_reference in mapping_references:
        mapped_variable: sym.Var = source_factory.add_var(mapping_reference.value)
        event_values[mapped_variable] = sym.Const(2.0)
        api_obj_mapping[mapping_reference] = mapped_variable

    source_block: Block = Block(
        name="unrelated limited controller",
        event_dict=event_values,
        api_obj_mapping=api_obj_mapping,
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_blocks: List[Block] = parser.parse_blocks(
        blocks_data=saver.get_blocks(),
        main_block_uids=list((source_block.uid,)),
    )
    restored_block: Block = restored_blocks[0]

    assert set(restored_block.api_obj_mapping) == set(mapping_references)
    assert len(restored_block.event_dict) == len(mapping_references)
    assert len(restored_block.parameters) == 0
    assert len(logger.entries) == 0


@pytest.mark.parametrize(
    "block_name",
    tuple(("governor", "governor_v2", "complete_generator_rms_template")),
)
def test_legacy_governor_mapping_preserves_runtime_parameters(
        block_name: str,
) -> None:
    """Restore the runtime parameter ownership used by old Kundur governors.

    The historical files mapped all eleven governor settings through
    ``api_obj_mapping`` while storing their values in ``event_dict``. Every
    obsolete mapping must be removed so current device defaults cannot overwrite
    the saved values. The storage role is retained for all eleven settings,
    including ``Pmin`` and ``Pmax``, because changing that role changes the RMS
    parameter-vector contract of existing files.

    :param block_name: Historical owner name used by one archived Kundur variant.
    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    dynamic_references: tuple[ParamPowerFlowReferenceType, ...] = (
        ParamPowerFlowReferenceType.K,
        ParamPowerFlowReferenceType.Uc,
        ParamPowerFlowReferenceType.Uo,
        ParamPowerFlowReferenceType.T_aux,
        ParamPowerFlowReferenceType.Kp,
        ParamPowerFlowReferenceType.Ki,
        ParamPowerFlowReferenceType.omega_ref,
        ParamPowerFlowReferenceType.p0,
        ParamPowerFlowReferenceType.P0,
    )
    dynamic_variables: Dict[ParamPowerFlowReferenceType, sym.Var] = dict()
    dynamic_values: Dict[ParamPowerFlowReferenceType, sym.Const] = dict()
    event_values: Dict[sym.Var, sym.Expr] = dict()
    api_obj_mapping: Dict[ParamPowerFlowReferenceType, sym.Var] = dict()
    reference_index: int
    dynamic_reference: ParamPowerFlowReferenceType
    for reference_index, dynamic_reference in enumerate(dynamic_references):
        dynamic_variable: sym.Var = source_factory.add_var(dynamic_reference.value)
        dynamic_value: sym.Const = sym.Const(float(reference_index + 1))
        dynamic_variables[dynamic_reference] = dynamic_variable
        dynamic_values[dynamic_reference] = dynamic_value
        event_values[dynamic_variable] = dynamic_value
        api_obj_mapping[dynamic_reference] = dynamic_variable

    # Also cover files saved after the incomplete migration: they can already
    # contain one of these model-owned values in the static collection.
    misclassified_parameters: Dict[sym.Var, sym.Const] = dict()
    misclassified_variable: sym.Var = dynamic_variables[ParamPowerFlowReferenceType.K]
    misclassified_parameters[misclassified_variable] = dynamic_values[ParamPowerFlowReferenceType.K]
    del event_values[misclassified_variable]

    pmin_variable: sym.Var = source_factory.add_var("Pmin")
    pmax_variable: sym.Var = source_factory.add_var("Pmax")
    pmin_fallback: float = -1.0
    pmax_fallback: float = 12.0
    event_values[pmin_variable] = sym.Const(pmin_fallback)
    event_values[pmax_variable] = sym.Const(pmax_fallback)
    # Also represent an intermediate compatibility save which duplicated a
    # mapped limit into parameters as Const(None) without removing event_dict.
    misclassified_parameters[pmin_variable] = sym.Const(None)
    api_obj_mapping[ParamPowerFlowReferenceType.Pmin] = pmin_variable
    api_obj_mapping[ParamPowerFlowReferenceType.Pmax] = pmax_variable
    source_block: Block = Block(
        name=block_name,
        event_dict=event_values,
        parameters=misclassified_parameters,
        api_obj_mapping=api_obj_mapping,
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_blocks: List[Block] = parser.parse_blocks(
        blocks_data=saver.get_blocks(),
        main_block_uids=list((source_block.uid,)),
    )
    restored_block: Block = restored_blocks[0]
    restored_event_variables: Dict[int, sym.Var] = dict()
    restored_event_variable: sym.Var
    for restored_event_variable in restored_block.event_dict:
        restored_event_variables[restored_event_variable.non_mutable_uid] = restored_event_variable
    for dynamic_reference in dynamic_references:
        source_dynamic_variable: sym.Var = dynamic_variables[dynamic_reference]
        restored_dynamic_variable: sym.Var | None = restored_event_variables.get(
            source_dynamic_variable.non_mutable_uid,
            None,
        )
        assert restored_dynamic_variable is not None
        assert dynamic_reference not in restored_block.api_obj_mapping
        assert restored_dynamic_variable not in restored_block.parameters
        assert (
            restored_block.event_dict[restored_dynamic_variable].eval()
            == dynamic_values[dynamic_reference].eval()
        )

    restored_pmin: sym.Var | None = restored_event_variables.get(
        pmin_variable.non_mutable_uid,
        None,
    )
    restored_pmax: sym.Var | None = restored_event_variables.get(
        pmax_variable.non_mutable_uid,
        None,
    )
    assert restored_pmin is not None
    assert restored_pmax is not None
    assert ParamPowerFlowReferenceType.Pmin not in restored_block.api_obj_mapping
    assert ParamPowerFlowReferenceType.Pmax not in restored_block.api_obj_mapping
    assert restored_block.event_dict[restored_pmin].value == pmin_fallback
    assert restored_block.event_dict[restored_pmax].value == pmax_fallback
    assert restored_pmin not in restored_block.parameters
    assert restored_pmax not in restored_block.parameters
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == "Migrated legacy dynamic parameter declarations"
    assert logger.entries[0].value == "11"
    assert logger.entries[0].severity == LogSeverity.Information


def test_legacy_governor_migration_is_idempotent_after_save() -> None:
    """Verify that a migrated governor needs no second compatibility rewrite.

    The first load converts the obsolete eleven-key layout. Saving that current
    representation and opening it again must preserve the same serialized block
    structure and must not report another migration.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    legacy_references: tuple[ParamPowerFlowReferenceType, ...] = (
        ParamPowerFlowReferenceType.K,
        ParamPowerFlowReferenceType.Uc,
        ParamPowerFlowReferenceType.Uo,
        ParamPowerFlowReferenceType.T_aux,
        ParamPowerFlowReferenceType.Kp,
        ParamPowerFlowReferenceType.Ki,
        ParamPowerFlowReferenceType.omega_ref,
        ParamPowerFlowReferenceType.p0,
        ParamPowerFlowReferenceType.P0,
        ParamPowerFlowReferenceType.Pmin,
        ParamPowerFlowReferenceType.Pmax,
    )
    event_values: Dict[sym.Var, sym.Expr] = dict()
    api_obj_mapping: Dict[ParamPowerFlowReferenceType, sym.Var] = dict()
    reference_index: int
    legacy_reference: ParamPowerFlowReferenceType
    for reference_index, legacy_reference in enumerate(legacy_references):
        legacy_variable: sym.Var = source_factory.add_var(legacy_reference.value)
        event_values[legacy_variable] = sym.Const(float(reference_index + 1))
        api_obj_mapping[legacy_reference] = legacy_variable

    source_block: Block = Block(
        name="governor",
        event_dict=event_values,
        api_obj_mapping=api_obj_mapping,
    )
    source_saver: BlockSaver = BlockSaver(source_factory)
    source_saver.save_block(source_block, main=True)

    first_factory: VarFactory = VarFactory()
    first_logger: Logger = Logger()
    first_parser: BlockParser = BlockParser(first_factory, logger=first_logger)
    first_parser.parse_consts(source_saver.get_const_to_save())
    first_parser.parse_vars(source_saver.get_vars_to_save())
    first_parser.parse_diff_vars(source_saver.get_diff_vars_to_save())
    first_roots: List[Block] = first_parser.parse_blocks(
        blocks_data=source_saver.get_blocks(),
        main_block_uids=list((source_block.uid,)),
    )
    first_root: Block = first_roots[0]
    first_saver: BlockSaver = BlockSaver(first_factory)
    first_saver.save_block(first_root, main=True)

    second_factory: VarFactory = VarFactory()
    second_logger: Logger = Logger()
    second_parser: BlockParser = BlockParser(second_factory, logger=second_logger)
    second_parser.parse_consts(first_saver.get_const_to_save())
    second_parser.parse_vars(first_saver.get_vars_to_save())
    second_parser.parse_diff_vars(first_saver.get_diff_vars_to_save())
    second_roots: List[Block] = second_parser.parse_blocks(
        blocks_data=first_saver.get_blocks(),
        main_block_uids=list((first_root.uid,)),
    )
    second_root: Block = second_roots[0]
    second_saver: BlockSaver = BlockSaver(second_factory)
    second_saver.save_block(second_root, main=True)

    assert first_saver.get_blocks() == second_saver.get_blocks()
    assert len(first_logger.entries) == 1
    assert first_logger.entries[0].msg == "Migrated legacy dynamic parameter declarations"
    assert len(second_logger.entries) == 0


def test_current_static_parameter_contract_requires_no_migration() -> None:
    """Leave a current owner-local static parameter byte-for-byte equivalent.

    A current block stores both the constant declaration and its API mapping on
    the same owner. Parsing, saving and parsing this layout must neither invoke
    legacy repair nor change the persisted symbolic contract.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    source_parameter: sym.Var = source_factory.add_var("g")
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.g
    source_child: Block = Block(
        name="current line equations",
        parameters=dict(((source_parameter, sym.Const(5.0)),)),
        api_obj_mapping=dict(((mapping_key, source_parameter),)),
    )
    source_root: Block = Block(
        name="current line wrapper",
        children=list((source_child,)),
    )
    source_saver: BlockSaver = BlockSaver(source_factory)
    source_saver.save_block(source_root, main=True)

    restored_factory: VarFactory = VarFactory()
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(restored_factory, logger=logger)
    parser.parse_consts(source_saver.get_const_to_save())
    parser.parse_vars(source_saver.get_vars_to_save())
    parser.parse_diff_vars(source_saver.get_diff_vars_to_save())
    restored_root: Block = parser.parse_block(
        blocks_data=source_saver.get_blocks(),
        main_block_uid=source_root.uid,
    )
    restored_saver: BlockSaver = BlockSaver(restored_factory)
    restored_saver.save_block(restored_root, main=True)

    assert logger.entries == list()
    assert restored_saver.get_blocks() == source_saver.get_blocks()


def test_legacy_static_owner_migration_is_idempotent_after_save() -> None:
    """Apply wrapper-to-child ownership repair exactly once.

    Historical RMS line wrappers stored the API mapping above the child which
    declared the constant. The first load must localize that mapping; a save and
    second load must then produce no further migration or structural change.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    source_parameter: sym.Var = source_factory.add_var("g")
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.g
    source_child: Block = Block(
        name="legacy line equations",
        parameters=dict(((source_parameter, sym.Const(5.0)),)),
    )
    source_root: Block = Block(
        name="legacy line wrapper",
        children=list((source_child,)),
        api_obj_mapping=dict(((mapping_key, source_parameter),)),
    )
    source_saver: BlockSaver = BlockSaver(source_factory)
    source_saver.save_block(source_root, main=True)

    first_factory: VarFactory = VarFactory()
    first_logger: Logger = Logger()
    first_parser: BlockParser = BlockParser(first_factory, logger=first_logger)
    first_parser.parse_consts(source_saver.get_const_to_save())
    first_parser.parse_vars(source_saver.get_vars_to_save())
    first_parser.parse_diff_vars(source_saver.get_diff_vars_to_save())
    first_root: Block = first_parser.parse_block(
        blocks_data=source_saver.get_blocks(),
        main_block_uid=source_root.uid,
    )
    first_saver: BlockSaver = BlockSaver(first_factory)
    first_saver.save_block(first_root, main=True)

    second_factory: VarFactory = VarFactory()
    second_logger: Logger = Logger()
    second_parser: BlockParser = BlockParser(second_factory, logger=second_logger)
    second_parser.parse_consts(first_saver.get_const_to_save())
    second_parser.parse_vars(first_saver.get_vars_to_save())
    second_parser.parse_diff_vars(first_saver.get_diff_vars_to_save())
    second_root: Block = second_parser.parse_block(
        blocks_data=first_saver.get_blocks(),
        main_block_uid=first_root.uid,
    )
    second_saver: BlockSaver = BlockSaver(second_factory)
    second_saver.save_block(second_root, main=True)

    assert len(first_logger.entries) == 1
    assert first_logger.entries[0].msg == "Migrated legacy dynamic parameter declarations"
    assert second_logger.entries == list()
    assert second_saver.get_blocks() == first_saver.get_blocks()


@pytest.mark.parametrize(
    "mapping_key",
    tuple((
        ParamPowerFlowReferenceType.generator_share_p_ref,
        ParamPowerFlowReferenceType.P0,
        ParamPowerFlowReferenceType.converter_control_mode_1,
        ParamPowerFlowReferenceType.converter_control_mode_2,
        ParamPowerFlowReferenceType.converter_control_target_1,
        ParamPowerFlowReferenceType.converter_control_target_2,
    )),
)
def test_legacy_runtime_mapping_target_is_not_promoted_to_static(
        mapping_key: ParamPowerFlowReferenceType,
) -> None:
    """Keep a mapped event target in runtime storage during legacy loading.

    :param mapping_key: Persisted runtime reference being round-tripped.
    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    runtime_parameter: sym.Var = source_factory.add_var("legacy_runtime_parameter")
    source_block: Block = Block(
        name="legacy runtime block",
        event_dict=dict(((runtime_parameter, sym.Const(1.0)),)),
        api_obj_mapping=dict(((mapping_key, runtime_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_block: Block = parser.parse_block(saver.get_blocks(), source_block.uid)
    restored_runtime_parameter: sym.Var | None = restored_block.api_obj_mapping.get(
        mapping_key,
        None,
    )

    assert restored_runtime_parameter is not None
    assert restored_runtime_parameter in restored_block.event_dict
    assert restored_runtime_parameter not in restored_block.parameters


@pytest.mark.parametrize(
    "mapping_key",
    tuple((
        ParamPowerFlowReferenceType.P0,
        ParamPowerFlowReferenceType.converter_control_target_1,
    )),
)
def test_intermediate_converter_static_migration_is_restored_to_runtime(
        mapping_key: ParamPowerFlowReferenceType,
) -> None:
    """Repair converter runtime values misclassified by an older migration.

    :param mapping_key: Converter runtime reference being repaired.
    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    runtime_parameter: sym.Var = source_factory.add_var(mapping_key.value)
    source_block: Block = Block(
        name="intermediate converter migration",
        parameters=dict(((runtime_parameter, sym.Const(2.0)),)),
        api_obj_mapping=dict(((mapping_key, runtime_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_block: Block = parser.parse_block(saver.get_blocks(), source_block.uid)
    restored_runtime_parameter: sym.Var | None = restored_block.api_obj_mapping.get(
        mapping_key,
        None,
    )

    assert restored_runtime_parameter is not None
    assert restored_runtime_parameter in restored_block.event_dict
    assert restored_block.event_dict[restored_runtime_parameter].value == 2.0
    assert restored_runtime_parameter not in restored_block.parameters


def test_legacy_converter_loss_parameter_uses_static_alpha1_mapping() -> None:
    """Translate the old no-load loss alias without changing its static owner.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    loss_parameter: sym.Var = source_factory.add_var("P_loss0")
    source_block: Block = Block(
        name="legacy converter loss parameter",
        parameters=dict(((loss_parameter, sym.Const(0.01)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.converter_loss_power_0, loss_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_block: Block = parser.parse_block(saver.get_blocks(), source_block.uid)
    restored_loss_parameter: sym.Var | None = restored_block.api_obj_mapping.get(
        ParamPowerFlowReferenceType.alpha1,
        None,
    )

    assert (
        ParamPowerFlowReferenceType.converter_loss_power_0
        not in restored_block.api_obj_mapping
    )
    assert restored_loss_parameter is not None
    assert restored_loss_parameter in restored_block.parameters
    assert restored_block.parameters[restored_loss_parameter].value == 0.01
    assert restored_loss_parameter not in restored_block.event_dict


def test_legacy_converter_operating_loss_mapping_is_removed() -> None:
    """Keep calculated converter loss as runtime data without an obsolete mapping.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    loss_parameter: sym.Var = source_factory.add_var("P_loss")
    source_block: Block = Block(
        name="legacy converter operating loss",
        event_dict=dict(((loss_parameter, sym.Const(0.0)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.converter_loss_power_0, loss_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_block: Block = parser.parse_block(saver.get_blocks(), source_block.uid)
    restored_runtime_parameters: List[sym.Var] = list(restored_block.event_dict.keys())

    assert (
        ParamPowerFlowReferenceType.converter_loss_power_0
        not in restored_block.api_obj_mapping
    )
    assert len(restored_runtime_parameters) == 1
    assert restored_runtime_parameters[0].name == "P_loss"
    assert restored_runtime_parameters[0] not in restored_block.parameters


def test_legacy_parent_converter_runtime_mapping_moves_to_event_owner() -> None:
    """Move a wrapper converter mapping to the child that declares the event.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    runtime_parameter: sym.Var = source_factory.add_var("control1")
    child_block: Block = Block(
        name="converter equations",
        event_dict=dict(((runtime_parameter, sym.Const(1.0)),)),
    )
    source_block: Block = Block(
        name="legacy converter wrapper",
        children=list((child_block,)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.converter_control_mode_1, runtime_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_root: Block = parser.parse_block(saver.get_blocks(), source_block.uid)
    restored_child: Block = restored_root.children[0]
    restored_runtime_parameter: sym.Var | None = restored_child.api_obj_mapping.get(
        ParamPowerFlowReferenceType.converter_control_mode_1,
        None,
    )

    assert restored_root.api_obj_mapping == dict()
    assert restored_runtime_parameter is not None
    assert restored_runtime_parameter in restored_child.event_dict
    assert restored_runtime_parameter not in restored_child.parameters


def test_legacy_parent_mapping_to_child_runtime_parameter_is_removed() -> None:
    """Remove a wrapper mapping that would override a child event expression.

    Historical RMS load models stored ``Pl0`` and ``Ql0`` in a child
    ``event_dict`` while mapping the same identities from the wrapper. The
    current recursive ownership contract keeps the event expression and removes
    that redundant static mapping when the file is opened.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    operating_point: sym.Var = source_factory.add_var("Ql")
    runtime_parameter: sym.Var = source_factory.add_var("Ql0")
    child_block: Block = Block(
        name="legacy RMS load equations",
        algebraic_vars=list((operating_point,)),
        event_dict=dict(((runtime_parameter, operating_point),)),
    )
    source_block: Block = Block(
        name="legacy RMS load wrapper",
        children=list((child_block,)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Ql0, runtime_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_block: Block = parser.parse_block(saver.get_blocks(), source_block.uid)
    restored_child: Block = restored_block.children[0]
    restored_parameters: List[sym.Var] = list(restored_child.event_dict.keys())
    restored_runtime_parameter: sym.Var = restored_parameters[0]
    restored_expression: sym.Expr = restored_child.event_dict[restored_runtime_parameter]

    assert restored_block.api_obj_mapping == dict()
    assert restored_runtime_parameter.name == "Ql0"
    assert isinstance(restored_expression, sym.Var)
    assert restored_expression.name == "Ql"
    assert restored_runtime_parameter not in restored_child.parameters
    assert logger.entries[-1].msg == "Migrated legacy dynamic parameter declarations"
    assert logger.entries[-1].value == "1"
    assert logger.entries[-1].severity == LogSeverity.Information


@pytest.mark.parametrize(
    "mapping_key",
    tuple((
        ParamPowerFlowReferenceType.generator_share_p_ref,
        ParamPowerFlowReferenceType.P0,
        ParamPowerFlowReferenceType.converter_control_mode_1,
        ParamPowerFlowReferenceType.converter_control_mode_2,
        ParamPowerFlowReferenceType.converter_control_target_1,
        ParamPowerFlowReferenceType.converter_control_target_2,
    )),
)
def test_legacy_mapping_only_runtime_target_is_restored_as_runtime(
        mapping_key: ParamPowerFlowReferenceType,
) -> None:
    """Restore an old mapping-only operating reference to runtime storage.

    Historical predefined EMT generators persisted sharing references without an
    explicit parameter owner, and old converter files did the same for controls
    and operating values. Their value comes from runtime initialization, so file
    loading must not reinterpret them as required static device properties.

    :param mapping_key: Persisted runtime reference being repaired.
    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    runtime_parameter: sym.Var = source_factory.add_var("legacy_mapping_only_share_reference")
    source_block: Block = Block(
        name="legacy mapping-only runtime block",
        api_obj_mapping=dict(((mapping_key, runtime_parameter),)),
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())

    restored_block: Block = parser.parse_block(saver.get_blocks(), source_block.uid)
    restored_runtime_parameter: sym.Var | None = restored_block.api_obj_mapping.get(
        mapping_key,
        None,
    )

    assert restored_runtime_parameter is not None
    assert restored_runtime_parameter in restored_block.event_dict
    assert restored_block.event_dict[restored_runtime_parameter].value is None
    assert restored_runtime_parameter not in restored_block.parameters
    assert logger.entries[-1].msg == "Migrated legacy dynamic parameter declarations"
    assert logger.entries[-1].value == "1"
    assert logger.entries[-1].severity == LogSeverity.Information


def test_legacy_block_instance_without_model_family_name_uses_empty_default() -> None:
    """Verify constructor-bypassing legacy instances expose the optional label.

    Historical ``.veragrid`` loaders may restore an instance dictionary without
    calling the current constructor. Removing the backing value reproduces that
    state and protects every normal property read and declarative serialization.

    :return: None.
    """
    legacy_block: Block = Block(name="legacy_without_model_family")
    del legacy_block._model_family_name

    assert legacy_block.model_family_name == ""
    assert legacy_block.to_dict()["model_family_name"] == ""


def test_symbolic_block_model_family_roundtrip_accepts_legacy_absence() -> None:
    """Verify new family labels persist while legacy symbolic records stay valid.

    :return: None.
    """
    source_factory: VarFactory = VarFactory()
    source_block: Block = Block(
        name="family_roundtrip_block",
        model_family_name="generator_family",
    )
    copied_block: Block = source_block.copy()
    assert copied_block.model_family_name == "generator_family"

    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    saved_blocks: Dict[int, Dict[str, Any]] = saver.get_blocks()

    current_parser: BlockParser = BlockParser(VarFactory())
    current_block: Block = current_parser.parse_block(saved_blocks, source_block.uid)
    assert current_block.model_family_name == "generator_family"

    # Removing the optional field reproduces every archive written before the
    # model comparator existed; opening it must not require a migration step.
    del saved_blocks[source_block.uid]["model_family_name"]
    legacy_parser: BlockParser = BlockParser(VarFactory())
    legacy_block: Block = legacy_parser.parse_block(saved_blocks, source_block.uid)
    assert legacy_block.model_family_name == ""

    saved_blocks[source_block.uid]["model_family_name"] = None
    null_parser: BlockParser = BlockParser(VarFactory())
    null_block: Block = null_parser.parse_block(saved_blocks, source_block.uid)
    assert null_block.model_family_name == ""


def test_tree_payload_without_graph_ids_remains_supported() -> None:
    """
    Verify that older tree-only symbolic payloads still deserialize unchanged.

    :return: None.
    """
    variable: sym.Var = sym.Var("x")
    constant: sym.Const = sym.Const(2.0)
    payload: Dict[str, Any] = dict(
        type="BinOp",
        op="+",
        left=dict(type="Var", uid=variable.non_mutable_uid),
        right=dict(type="Const", uid=constant.uid),
        uid=201,
    )

    restored: sym.Expr = parse_expr(
        data=payload,
        const_dict=dict(((constant.uid, constant),)),
        var_dict=dict(((variable.non_mutable_uid, variable),)),
        diff_var_dict=dict(),
    )

    assert restored.eval(x=3.0) == 5.0


def test_dangling_expr_ref_reports_graph_identifier() -> None:
    """
    Verify that broken graph references fail with a diagnostic identifier.

    :return: None.
    """
    payload: Dict[str, Any] = dict(type="ExprRef", graph_id=999)

    with pytest.raises(ValueError, match="999"):
        parse_expr(
            data=payload,
            const_dict=dict(),
            var_dict=dict(),
            diff_var_dict=dict(),
        )


def test_persisted_identity_lookup_keeps_stable_identity_authoritative() -> None:
    """
    Verify that a mutable UID alias never replaces an existing stable identity.

    :return: None.
    """
    stable_variable: sym.Var = sym.Var("stable", uid=99, non_mutable_uid=99)
    aliased_variable: sym.Var = sym.Var("aliased", uid=99, non_mutable_uid=20)
    var_dict: Dict[int, sym.Var] = dict(((20, aliased_variable), (99, stable_variable)))

    identity_lookup: Dict[int, sym.Var] = build_persisted_identity_lookup(var_dict=var_dict)

    assert identity_lookup[20] is aliased_variable
    assert identity_lookup[99] is stable_variable


def test_block_parser_rebuilds_legacy_uid_lookup_after_connections() -> None:
    """
    Verify that connection-propagated legacy UIDs resolve without repeated scans.

    :return: None.
    """
    parser: BlockParser = BlockParser(VarFactory())
    parser.parse_vars(
        data=list((
            dict(type="Var", name="source", uid=99, non_mutable_uid=10, shared_ref=None, ref=None),
            dict(type="Var", name="target", uid=20, non_mutable_uid=20, shared_ref=None, ref=None),
        ))
    )
    parser.parse_diff_vars(data=list())
    parser.parse_connections(
        data=dict({
            10: list((
                dict(type="Connection", non_mutable_uid=20, name="target", uid=20),
            )),
        })
    )
    block_data: Dict[str, Any] = dict(
        uid=1,
        name="legacy_uid_block",
        state_vars=list(),
        state_eqs=list(),
        algebraic_vars=list((20,)),
        algebraic_eqs=list((dict(type="Var", uid=99),)),
        diff_vars=list(),
        differential_eqs=list(),
        inequalities=list(),
        children=list(),
    )
    blocks_data: Dict[int, Dict[str, Any]] = dict(((1, block_data),))

    restored_block: Block = parser.parse_block(blocks_data=blocks_data, main_block_uid=1)
    restored_source: sym.Var | None = parser.var_factory.get_vars_dict().get(10, None)
    restored_target: sym.Var | None = parser.var_factory.get_vars_dict().get(20, None)

    assert restored_source is not None
    assert restored_target is not None
    assert restored_target.uid == restored_source.uid == 99
    assert restored_block.algebraic_vars[0] is restored_target
    assert restored_block.algebraic_eqs[0] is restored_source


def test_legacy_func2_min_max_codegen_uses_elementwise_numpy_operations() -> None:
    """
    Verify legacy binary min/max nodes keep two-operand semantics in generated code.

    :return: None.
    """
    variable: sym.Var = sym.Var("x")
    compiler_names: Dict[int, str] = dict(((variable.uid, "vrs[0]"),))
    legacy_maximum: sym.Func2 = sym.Func2("max", variable, sym.Const(1.0e-12))
    legacy_minimum: sym.Func2 = sym.Func2("min", variable, sym.Const(-1.0e-12))

    maximum_source: str = sym.expression2numba(legacy_maximum, compiler_names)
    minimum_source: str = sym.expression2numba(legacy_minimum, compiler_names)
    evaluation_namespace: Dict[str, Any] = dict(np=np, vrs=np.array([-2.0], dtype=float))
    maximum_value: float = float(eval(maximum_source, evaluation_namespace))
    minimum_value: float = float(eval(minimum_source, evaluation_namespace))

    assert maximum_source == "np.maximum(vrs[0], 1e-12)"
    assert minimum_source == "np.minimum(vrs[0], -1e-12)"
    assert maximum_value == 1.0e-12
    assert minimum_value == -2.0


def test_block_parser_opens_legacy_inline_child_tree_without_main_uids() -> None:
    """
    Verify the inline-child archive layout written by commit ``48bcef198``.

    :return: None.
    """
    child_data: Dict[str, Any] = dict(
        uid=202,
        name="legacy_inline_child",
        children=list(),
    )
    root_data: Dict[str, Any] = dict(
        uid=101,
        name="legacy_inline_root",
        children=list((child_data,)),
    )
    legacy_blocks: Dict[str, Any] = dict({"101": root_data})
    parser: BlockParser = BlockParser(VarFactory())

    # The old symbolic section had no main_block_uids, so the parser must infer
    # the root and flatten the nested child before rebuilding runtime blocks.
    parsed_roots: List[Block] = parser.parse_blocks(blocks_data=legacy_blocks,
                                                     main_block_uids=None)

    assert len(parsed_roots) == 1
    assert parsed_roots[0].uid == 101
    assert len(parsed_roots[0].children) == 1
    assert parsed_roots[0].children[0].uid == 202
    assert parser.block_dict[202] is parsed_roots[0].children[0]


def test_block_parser_opens_legacy_list_table_and_warns_for_missing_pointer_child() -> None:
    """
    Verify list-based pointer archives retain recoverable blocks and warn on loss.

    :return: None.
    """
    child_data: Dict[str, Any] = dict(
        uid=302,
        name="legacy_pointer_child",
        children=list(),
    )
    root_data: Dict[str, Any] = dict(
        uid=301,
        name="legacy_pointer_root",
        children=list((302, 999)),
    )
    legacy_blocks: List[Dict[str, Any]] = list((root_data, child_data))
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)

    # Pointer-format files predate main_block_uids. The valid edge is restored;
    # an absent referenced record is isolated instead of aborting file opening.
    parsed_roots: List[Block] = parser.parse_blocks(blocks_data=legacy_blocks,
                                                     main_block_uids=None)

    assert len(parsed_roots) == 1
    assert parsed_roots[0].uid == 301
    assert [child.uid for child in parsed_roots[0].children] == [302]
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == "Missing child dynamic block while parsing persisted symbolic data"
    assert logger.entries[0].value == "999"


def test_block_parser_ignores_cyclic_legacy_child_uid_without_recursing_forever() -> None:
    """
    Verify a malformed historical child graph cannot block the file loader.

    :return: None.
    """
    root_data: Dict[str, Any] = dict(
        uid="401",
        name="legacy_cyclic_root",
        children=list((401,)),
    )
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(VarFactory(), logger=logger)

    parsed_roots: List[Block] = parser.parse_blocks(blocks_data=list((root_data,)),
                                                     main_block_uids=None)

    assert len(parsed_roots) == 1
    assert parsed_roots[0].uid == 401
    assert parsed_roots[0].children == list()
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == "Cyclic child dynamic block reference ignored while parsing persisted data"
