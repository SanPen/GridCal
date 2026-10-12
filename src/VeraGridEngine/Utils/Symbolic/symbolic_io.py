# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import copy
from typing import Dict, Any, List
from typing import Iterable, Mapping

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Dynamic.var_factory import (Connection,
                                                        VarFactory,
                                                        build_persisted_identity_lookup,
                                                        find_var_by_persisted_identity)
from VeraGridEngine.Utils.Symbolic import SharedVarReferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const, BinOp, UnOp, Func, Func2, CmpOp, Comparison
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    DynamicModelContract,
    RmsPhysicalMeasurementPoint,
    dynamic_model_contract_from_data,
    normalize_dynamic_connection_intents,
    normalize_event_parameter_initialization,
    validate_dynamic_model_contract,
)
from VeraGridEngine.Utils.procedural_logic_contract import (
    ProceduralLogicCodecContract,
    ProceduralLogicData,
    ProceduralLogicEntryContract,
)
from VeraGridEngine.Utils.Symbolic.dynamic_connection_intent import (DynamicConnectionIntent,
                                                                     DynamicConnectionIntentDirection,
                                                                     dynamic_connection_intent_from_dict,
                                                                     dynamic_connection_intent_to_dict,
                                                                     is_legacy_suppressed_connection_intent_tombstone)
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, ParamPowerFlowReferenceType


def symbolic_objects_to_dict(obj_dict: Dict[int | str, Var | Const | Var | SharedVarReferenceType]) -> List[Dict[str, Any]]:
    """
    Save all unique variables, differential variables, and constants.
    :param obj_dict: Dictionary storing the unique objects
    :return: List of dictionaries representing each object
    """
    lst: List[Dict[str, Any]] = list()

    for uuid, expr in obj_dict.items():

        if isinstance(expr, Const):

            # add it to the references dict
            obj_dict[expr.uid] = expr

            # The const didn't exist, we create it here
            if isinstance(expr.value, complex):
                lst.append({"type": "Const",
                            "value": [expr.value.real, expr.value.imag],
                            "kind": "complex",
                            "uid": expr.uid})
            else:
                lst.append({"type": "Const",
                            "value": expr.value,
                            "uid": expr.uid})

        elif isinstance(expr, Var):
            shared = expr.shared_ref
            if expr.base_var is not None:
                if type(expr.ref) == str:
                    lst.append({
                        "type": "DiffVar",
                        "name": expr.name,
                        "uid": expr.uid,
                        "non_mutable_uid": expr.non_mutable_uid,
                        "base_var": expr.base_var.non_mutable_uid,
                        "shared_ref": {"name": shared.name if shared is not None else None,
                                "uid": shared.uid if shared is not None else None},
                        "ref": expr.ref.value if expr.ref is not None else None,
                    })
                else:
                    lst.append({
                        "type": "DiffVar",
                        "name": expr.name,
                        "uid": expr.uid,
                        "non_mutable_uid": expr.non_mutable_uid,
                        "base_var": expr.base_var.non_mutable_uid,
                        "shared_ref": {"name": shared.name if shared is not None else None,
                                "uid": shared.uid if shared is not None else None},
                        "ref": expr.ref.value if expr.ref is not None else None,
                    })



            else:
                # it is a normal var
                if type(expr.ref) == str:
                    lst.append({"type": "Var",
                                "name": expr.name,
                                "uid": expr.uid,
                                "non_mutable_uid": expr.non_mutable_uid,
                                "base_var": None,
                                "shared_ref": {"name": shared.name if shared is not None else None,
                                                "uid": shared.uid if shared is not None else None},
                                "ref": expr.ref.value if expr.ref is not None else None,
                                })
                else:
                    lst.append({"type": "Var",
                                "name": expr.name,
                                "uid": expr.uid,
                                "non_mutable_uid": expr.non_mutable_uid,
                                "base_var": None,
                                "shared_ref": {"name": shared.name if shared is not None else None,
                                                "uid": shared.uid if shared is not None else None},
                                "ref": expr.ref.value if expr.ref is not None else None,
                                })

        if isinstance(expr, SharedVarReferenceType):
            lst.append({"type": "share_reference",
                        "name": expr.name,
                        "uid": expr.uid})

        if isinstance(expr, Connection):
            lst.append({"type": "Connection",
                        "non_mutable_uid": expr.non_mutable_uid,
                        "name": expr.name,
                        "uid": expr.uid})


    return lst

def connections_to_dict(obj_dict: Dict[int, List[Connection]]) -> Dict[int, List[Any]]:


    conn_dict: Dict[int, List[Any]] = dict()

    for uuid, connections_list in obj_dict.items():
        conn_list: List[Any] = list()
        for connection in connections_list:
            conn_list.append({"type": "Connection",
                        "non_mutable_uid": connection.non_mutable_uid,
                        "name": connection.name,
                        "uid": connection.uid})
        conn_dict[uuid] = conn_list
    return conn_dict


def normalize_persisted_block_uid(uid_value: Any) -> int | None:
    """
    Convert one persisted block identifier to the current integer representation.

    JSON object keys are strings while symbolic block UIDs are integers in
    memory. Historical archives can therefore contain either representation.
    Invalid identifiers are ignored by the legacy normalization layer so the
    caller can report the damaged reference without blocking the full file.

    :param uid_value: Persisted block identifier.
    :return: Integer UID or ``None`` when the value is not a valid identifier.
    """
    normalized_uid: int | None
    try:
        normalized_uid = int(uid_value)
    except (TypeError, ValueError):
        normalized_uid = None

    return normalized_uid


def register_persisted_block_tree(block_data: Dict[str, Any],
                                  normalized_blocks: Dict[int, Dict[str, Any]],
                                  fallback_uid: Any = None) -> None:
    """
    Register one block and any historically inline child block records.

    Commit ``48bcef198`` serialized ``children`` as complete nested block
    dictionaries. Later formats store only child UIDs in a flat block table.
    Flattening the old tree before parsing lets both layouts follow the same
    reconstruction path without changing the runtime ``Block`` architecture.

    :param block_data: Persisted block record.
    :param normalized_blocks: Destination table indexed by integer UID.
    :param fallback_uid: Container key used when the record omits ``uid``.
    :return: None.
    """
    block_uid: int | None = normalize_persisted_block_uid(block_data.get("uid", fallback_uid))
    if block_uid is not None:
        if block_uid not in normalized_blocks:
            normalized_blocks[block_uid] = block_data
        else:
            pass

        child_entry: Any
        for child_entry in block_data.get("children", list()):
            if isinstance(child_entry, dict):
                register_persisted_block_tree(block_data=child_entry,
                                              normalized_blocks=normalized_blocks)
            else:
                pass
    else:
        pass


def normalize_persisted_blocks(blocks_data: Dict[Any, Any] | List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    Normalize every block container written by historical dynamics branches.

    The first pointer-based format stored ``blocks`` as a list. It later became
    a JSON dictionary keyed by UID, and one intermediate revision embedded
    children recursively inside each top-level record. This function accepts
    all three shapes and produces the current flat integer-keyed table.

    :param blocks_data: Persisted list, UID mapping or single block record.
    :return: Flat block table indexed by integer UID.
    """
    normalized_blocks: Dict[int, Dict[str, Any]] = dict()

    if isinstance(blocks_data, list):
        block_data: Dict[str, Any]
        for block_data in blocks_data:
            if isinstance(block_data, dict):
                register_persisted_block_tree(block_data=block_data,
                                              normalized_blocks=normalized_blocks)
            else:
                pass
    elif isinstance(blocks_data, dict):
        # A few development snapshots passed one inline root directly instead
        # of wrapping it in the global block table.
        direct_uid: int | None = normalize_persisted_block_uid(blocks_data.get("uid", None))
        if direct_uid is not None:
            register_persisted_block_tree(block_data=blocks_data,
                                          normalized_blocks=normalized_blocks)
        else:
            persisted_key: Any
            persisted_record: Any
            for persisted_key, persisted_record in blocks_data.items():
                if isinstance(persisted_record, dict):
                    register_persisted_block_tree(block_data=persisted_record,
                                                  normalized_blocks=normalized_blocks,
                                                  fallback_uid=persisted_key)
                else:
                    pass
    else:
        pass

    return normalized_blocks


def infer_persisted_main_block_uids(blocks_data: Dict[int, Dict[str, Any]]) -> List[int]:
    """
    Infer root block UIDs for archives predating ``main_block_uids``.

    Roots are the stored blocks that are not referenced as children by any
    other stored block. If a damaged cyclic graph has no discoverable root, all
    records are returned so the parser can retain the recoverable blocks while
    its cycle guard drops only the invalid child edge.

    :param blocks_data: Normalized block table.
    :return: Deterministically ordered root block UIDs.
    """
    child_uids: set[int] = set()
    block_data: Dict[str, Any]
    child_entry: Any
    for block_data in blocks_data.values():
        for child_entry in block_data.get("children", list()):
            if isinstance(child_entry, dict):
                child_uid: int | None = normalize_persisted_block_uid(child_entry.get("uid", None))
            else:
                child_uid = normalize_persisted_block_uid(child_entry)

            if child_uid is not None:
                child_uids.add(child_uid)
            else:
                pass

    root_uids: List[int] = sorted(set(blocks_data.keys()).difference(child_uids))
    if len(root_uids) == 0 and len(blocks_data) > 0:
        root_uids = sorted(blocks_data.keys())
    else:
        pass

    return root_uids


def expr_to_dict(expr: Expr | Comparison,
                 const_dict: Dict[int, Const],
                 var_dict: Dict[int, Var],
                 diff_var_dict: Dict[int, Var],
                 composite_expression_ids: Dict[int, int] | None = None) -> Dict[str, Any]:
    """
    Serialize any ``Expr`` tree into a JSON-compatible Python dictionary.

    Each node record contains its symbolic kind, payload, stable UID, and
    recursively serialized child expressions.
    :param expr: Expression child
    :param const_dict: Dictionary that keeps a reference of the Const objects already saved
    :param var_dict: Dictionary that retains variables already saved.
    :param diff_var_dict: Dictionary that keeps a reference of the DiffVar objects already saved
    :param composite_expression_ids: Object identities already serialized in the current block
    :return: Declarative expression record suitable for JSON persistence.
    """
    active_composite_expression_ids: Dict[int, int]
    if composite_expression_ids is None:
        active_composite_expression_ids = dict()
    else:
        active_composite_expression_ids = composite_expression_ids

    if isinstance(expr, Const):

        c = const_dict.get(expr.uid, None)

        if c is None:
            # add it to the references dict
            const_dict[expr.uid] = expr

        # the const already exists
        return {
            "type": "Const",
            "uid": expr.uid
        }

    elif isinstance(expr, Var):

        if expr.base_var is not None:

            c = diff_var_dict.get(expr.non_mutable_uid, None)

            if c is None:
                # add it to the references dict
                diff_var_dict[expr.non_mutable_uid] = expr

            # the diffvar already exists
            return {
                "type": "DiffVar",
                "uid": expr.non_mutable_uid
            }

        else:
            c = var_dict.get(expr.non_mutable_uid, None)

            if c is None:
                # add it to the references dict
                var_dict[expr.non_mutable_uid] = expr

            # the var already exists
            return {
                "type": "Var",
                "uid": expr.non_mutable_uid
            }

    else:
        # Composite expressions form a directed acyclic graph because the same
        # object may be reused by several controller equations. The first
        # occurrence is serialized completely and later occurrences become
        # references, preventing exponential expansion of the expression tree.
        expression_object_id: int = id(expr)
        existing_graph_id: int | None = active_composite_expression_ids.get(expression_object_id, None)
        if existing_graph_id is None:
            graph_id: int = len(active_composite_expression_ids)
            active_composite_expression_ids[expression_object_id] = graph_id
        else:
            return {
                "type": "ExprRef",
                "graph_id": existing_graph_id,
            }

    if isinstance(expr, BinOp):
        return {
            "type": "BinOp",
            "op": expr.op,
            "left": expr_to_dict(expr=expr.left,
                                 const_dict=const_dict,
                                 var_dict=var_dict,
                                 diff_var_dict=diff_var_dict,
                                 composite_expression_ids=active_composite_expression_ids),
            "right": expr_to_dict(expr=expr.right,
                                  const_dict=const_dict,
                                  var_dict=var_dict,
                                  diff_var_dict=diff_var_dict,
                                  composite_expression_ids=active_composite_expression_ids),
            "uid": expr.uid,
            "graph_id": graph_id,
        }

    elif isinstance(expr, UnOp):
        return {
            "type": "UnOp",
            "op": expr.op,  # only \"-\" for now
            "operand": expr_to_dict(expr=expr.operand,
                                    const_dict=const_dict,
                                    var_dict=var_dict,
                                    diff_var_dict=diff_var_dict,
                                    composite_expression_ids=active_composite_expression_ids),
            "uid": expr.uid,
            "graph_id": graph_id,
        }

    elif isinstance(expr, Func):
        return {
            "type": "Func",
            "op": expr.op,  # sin, cos, log, …
            "arg": expr_to_dict(expr=expr.arg,
                                const_dict=const_dict,
                                var_dict=var_dict,
                                diff_var_dict=diff_var_dict,
                                composite_expression_ids=active_composite_expression_ids),
            "uid": expr.uid,
            "graph_id": graph_id,
        }

    elif isinstance(expr, Func2):
        return {
            "type": "Func2",
            "name": expr.name,
            "arg1": expr_to_dict(expr=expr.arg1,
                                  const_dict=const_dict,
                                  var_dict=var_dict,
                                  diff_var_dict=diff_var_dict,
                                  composite_expression_ids=active_composite_expression_ids),
            "arg2": expr_to_dict(expr=expr.arg2,
                                  const_dict=const_dict,
                                  var_dict=var_dict,
                                  diff_var_dict=diff_var_dict,
                                  composite_expression_ids=active_composite_expression_ids),
            "uid": expr.uid,
            "graph_id": graph_id,
        }

    elif isinstance(expr, Comparison):
        if isinstance(expr.rhs, Expr):
            comparison_rhs: Expr = expr.rhs
        else:
            comparison_rhs = Const(expr.rhs)
        return {
            "type": "Comparison",
            "lhs": expr_to_dict(
                expr=expr.lhs,
                const_dict=const_dict,
                var_dict=var_dict,
                diff_var_dict=diff_var_dict,
                composite_expression_ids=active_composite_expression_ids,
            ),
            "op": expr.op.value,
            "rhs": expr_to_dict(
                expr=comparison_rhs,
                const_dict=const_dict,
                var_dict=var_dict,
                diff_var_dict=diff_var_dict,
                composite_expression_ids=active_composite_expression_ids,
            ),
            "graph_id": graph_id,
        }

    else:
        raise TypeError(f"Unsupported Expr subclass: {type(expr).__name__}")


def expr_list_to_list(lst: List[Expr],
                      const_dict: Dict[int, Const],
                      var_dict: Dict[int, Var],
                      diff_var_dict: Dict[int, Var],
                      composite_expression_ids: Dict[int, int] | None = None) -> List[Dict[str, Any]]:
    """

    :param lst:
    :param const_dict:
    :param var_dict:
    :param diff_var_dict:
    :param composite_expression_ids: Object identities already serialized in the current block
    :return:
    """
    active_composite_expression_ids: Dict[int, int]
    if composite_expression_ids is None:
        active_composite_expression_ids = dict()
    else:
        active_composite_expression_ids = composite_expression_ids

    lst2: List[Dict[str, Any]] = list()

    for expr in lst:
        lst2.append(
            expr_to_dict(expr=expr,
                         const_dict=const_dict,
                         var_dict=var_dict,
                         diff_var_dict=diff_var_dict,
                         composite_expression_ids=active_composite_expression_ids)
        )
    return lst2


def parse_expr(data: Dict[str, Any],
               const_dict: Dict[int, Const],
               var_dict: Dict[int, Var],
               diff_var_dict: Dict[int, Var],
               composite_expressions: Dict[int, Expr | Comparison] | None = None) -> Expr | Comparison:
    """
    De-Serialize expression from dictionary
    :param data: Some dictionary containing the expression
    :param const_dict: Dictionary that keeps a reference of the Const objects already saved
    :param var_dict: Dictionary that retains variables already saved.
    :param diff_var_dict: Dictionary that keeps a reference of the DiffVar objects already saved
    :param composite_expressions: Composite graph nodes already parsed in the current block
    :return: Reconstructed expression node.
    """
    active_composite_expressions: Dict[int, Expr | Comparison]
    if composite_expressions is None:
        active_composite_expressions = dict()
    else:
        active_composite_expressions = composite_expressions

    t: str = data["type"]

    if t == "ExprRef":
        graph_id: int = int(data["graph_id"])
        referenced_expression: Expr | Comparison | None = active_composite_expressions.get(graph_id, None)
        if referenced_expression is None:
            raise ValueError(f"Unknown backward expression reference '{graph_id}'")
        else:
            return referenced_expression

    elif t == "Const":
        return const_dict[data["uid"]]

    elif t == "Var":
        parsed_var: Var | None = find_var_by_persisted_identity(
            var_dict=var_dict,
            persisted_uid=data["uid"],
        )
        if parsed_var is not None:
            return parsed_var
        else:
            raise KeyError(f"Var with persisted uid {data['uid']} was not found")

    elif t == "DiffVar":
        parsed_diff_var: Var | None = find_var_by_persisted_identity(
            var_dict=diff_var_dict,
            persisted_uid=data["uid"],
        )
        if parsed_diff_var is not None:
            return parsed_diff_var
        else:
            raise KeyError(f"DiffVar with persisted uid {data['uid']} was not found")

    elif t == "BinOp":
        left = parse_expr(data=data["left"],
                          const_dict=const_dict,
                          var_dict=var_dict,
                          diff_var_dict=diff_var_dict,
                          composite_expressions=active_composite_expressions)

        right = parse_expr(data=data["right"],
                           const_dict=const_dict,
                           var_dict=var_dict,
                           diff_var_dict=diff_var_dict,
                           composite_expressions=active_composite_expressions)

        obj = BinOp(left=left, op=data["op"], right=right, uid=data["uid"])

    elif t == "UnOp":
        operand = parse_expr(data=data["operand"],
                             const_dict=const_dict,
                             var_dict=var_dict,
                             diff_var_dict=diff_var_dict,
                             composite_expressions=active_composite_expressions)
        obj = UnOp(op=data["op"], operand=operand, uid=data["uid"])

    elif t == "Func":
        arg = parse_expr(data=data["arg"],
                         const_dict=const_dict,
                         var_dict=var_dict,
                         diff_var_dict=diff_var_dict,
                         composite_expressions=active_composite_expressions)

        obj = Func(arg=arg, op=data["op"], uid=data["uid"])

    elif t == "Func2":
        arg1: Expr = parse_expr(data=data["arg1"],
                                                                      const_dict=const_dict,
                                                                      var_dict=var_dict,
                                                                      diff_var_dict=diff_var_dict,
                                                                      composite_expressions=active_composite_expressions)
        arg2: Expr = parse_expr(data=data["arg2"],
                                                                      const_dict=const_dict,
                                                                      var_dict=var_dict,
                                                                      diff_var_dict=diff_var_dict,
                                                                      composite_expressions=active_composite_expressions)

        obj = Func2(name=data["name"], arg1=arg1, arg2=arg2, uid=data["uid"])

    elif t == "Comparison":
        lhs_value: Expr | Comparison = parse_expr(
            data=data["lhs"],
            const_dict=const_dict,
            var_dict=var_dict,
            diff_var_dict=diff_var_dict,
            composite_expressions=active_composite_expressions,
        )
        rhs_value: Expr | Comparison = parse_expr(
            data=data["rhs"],
            const_dict=const_dict,
            var_dict=var_dict,
            diff_var_dict=diff_var_dict,
            composite_expressions=active_composite_expressions,
        )
        if not isinstance(lhs_value, Expr) or not isinstance(rhs_value, Expr):
            raise TypeError("Comparison operands must be symbolic expressions")
        else:
            pass
        comparison_operator_value: object = data["op"]
        if comparison_operator_value == CmpOp.LE.value:
            comparison_operator: CmpOp = CmpOp.LE
        elif comparison_operator_value == CmpOp.GE.value:
            comparison_operator = CmpOp.GE
        elif comparison_operator_value == CmpOp.LT.value:
            comparison_operator = CmpOp.LT
        elif comparison_operator_value == CmpOp.GT.value:
            comparison_operator = CmpOp.GT
        elif comparison_operator_value == CmpOp.EQ.value:
            comparison_operator = CmpOp.EQ
        else:
            raise ValueError(
                f"Unknown comparison operator '{comparison_operator_value}'"
            )
        obj = Comparison(
            lhs=lhs_value,
            op=comparison_operator,
            rhs=rhs_value,
        )

    else:
        raise ValueError(f"Unknown type '{t}' in symbolic deserialization")

    # Graph-aware archives add ``graph_id`` only to composite nodes. Legacy
    # tree archives omit it and therefore keep following the same code path.
    graph_id_value: int | None = data.get("graph_id", None)
    if graph_id_value is None:
        pass
    else:
        active_composite_expressions[int(graph_id_value)] = obj

    return obj


def parse_expr_list(lst: List[Dict[str, Any]],
                    const_dict: Dict[int, Const],
                    var_dict: Dict[int, Var],
                    diff_var_dict: Dict[int, Var],
                    composite_expressions: Dict[int, Expr | Comparison] | None = None) -> List[Expr | Comparison]:
    """

    :param lst:
    :param const_dict:
    :param var_dict:
    :param diff_var_dict:
    :param composite_expressions: Composite graph nodes already parsed in the current block
    :return:
    """
    active_composite_expressions: Dict[int, Expr | Comparison]
    if composite_expressions is None:
        active_composite_expressions = dict()
    else:
        active_composite_expressions = composite_expressions

    lst2: List[Expr | Comparison] = list()
    data: Dict[str, Any]
    for data in lst:
        lst2.append(
            parse_expr(
                data=data,
                const_dict=const_dict,
                var_dict=var_dict,
                diff_var_dict=diff_var_dict,
                composite_expressions=active_composite_expressions
            )
        )
    return lst2


class BlockSaver:
    __slots__ = (
        "var_factory",
        "main_block_uids",
        "blocks",
    )

    def __init__(self, var_factory: VarFactory):
        """Create a serializer bound to one symbolic variable factory.

        :param var_factory: Factory containing the variables and shared references to serialize.
        """
        self.var_factory = var_factory
        self.main_block_uids: List[int] = list()
        self.blocks: Dict[int, Dict[str, Any]] = dict()

    def get_const_to_save(self) -> List[Dict[str, Any]]:
        """

        :return:
        """
        return symbolic_objects_to_dict(self.var_factory.get_const_dict())

    def get_vars_to_save(self) -> List[Dict[str, Any]]:
        """

        :return:
        """
        return symbolic_objects_to_dict(self.var_factory.get_vars_dict())

    def get_diff_vars_to_save(self) -> List[Dict[str, Any]]:
        """

        :return:
        """
        return symbolic_objects_to_dict(self.var_factory.get_diff_var_dict())

    def get_shared_references_to_save(self) -> List[Dict[str, Any]]:
        """

        :return:
        :rtype:
        """
        return symbolic_objects_to_dict(self.var_factory.get_references_dict())

    def get_connections_to_save(self) -> Dict[int, List[Any]]:
        """

        :return:
        :rtype:
        """
        return connections_to_dict(self.var_factory.get_connections_dict())

    def get_blocks(self) -> Dict[int, Dict[str, Any]]:
        return self.blocks

    def _ensure_var_registered(self, var: Var) -> None:
        """
        Ensure that one algebraic variable is present in the shared variable factory.

        Some blocks created through GUI/template workflows keep live variable objects
        that are not reinserted into the factory before serialization. The saver must
        register them instead of failing deep in a background thread.

        :param var: Variable to register.
        :return: None.
        """
        registered_vars: Dict[int, Var] = self.var_factory.get_vars_dict()
        found_var: Var | None = find_var_by_persisted_identity(
            var_dict=registered_vars,
            persisted_uid=var.non_mutable_uid,
        )

        if found_var is None:
            registered_vars[var.non_mutable_uid] = var
        else:
            pass

    def _ensure_diff_var_registered(self, diff_var: Var) -> None:
        """
        Ensure that one differential variable is present in the shared variable factory.

        :param diff_var: Differential variable to register.
        :return: None.
        """
        registered_diff_vars: Dict[int, Var] = self.var_factory.get_diff_var_dict()
        found_var: Var | None = find_var_by_persisted_identity(
            var_dict=registered_diff_vars,
            persisted_uid=diff_var.non_mutable_uid,
        )

        if found_var is None:
            registered_diff_vars[diff_var.non_mutable_uid] = diff_var
        else:
            pass

    def save_block(self, blk: Block, main: bool = False) -> Dict[str, Any]:
        """
        Get a dictionary representing the block
        All global constant, variable, and differential-variable references are retained for later serialization.
        :param blk: Block
        :param main: is it the main block?
        :return: Dictionary representing the block
        """
        # Deleted internal blocks cannot be restored by replaying an intent, so
        # remove those historical records at the canonical persistence boundary.
        normalize_dynamic_connection_intents(block=blk)
        normalize_event_parameter_initialization(block=blk)
        # Persistence must reject an incoherent runtime contract before any
        # partial block data is registered in the canonical serializer.
        validate_dynamic_model_contract(blk)

        # One registry is shared by every expression owned by this block. Child
        # blocks create their own registry when ``save_block`` recurses.
        composite_expression_ids: Dict[int, int] = dict()

        state_expressions: List[Dict[str, Any]] = expr_list_to_list(
            lst=blk.state_eqs,
            const_dict=self.var_factory.get_const_dict(),
            var_dict=self.var_factory.get_vars_dict(),
            diff_var_dict=self.var_factory.get_diff_var_dict(),
            composite_expression_ids=composite_expression_ids
        )

        algebraic_expressions: List[Dict[str, Any]] = expr_list_to_list(
            lst=blk.algebraic_eqs,
            const_dict=self.var_factory.get_const_dict(),
            var_dict=self.var_factory.get_vars_dict(),
            diff_var_dict=self.var_factory.get_diff_var_dict(),
            composite_expression_ids=composite_expression_ids
        )

        differential_eqs_expressions: List[Dict[str, Any]] = expr_list_to_list(
            lst=blk.differential_eqs,
            const_dict=self.var_factory.get_const_dict(),
            var_dict=self.var_factory.get_vars_dict(),
            diff_var_dict=self.var_factory.get_diff_var_dict(),
            composite_expression_ids=composite_expression_ids
        )

        inequality_expressions: List[Dict[str, Any]] = expr_list_to_list(
            lst=blk.inequalities,
            const_dict=self.var_factory.get_const_dict(),
            var_dict=self.var_factory.get_vars_dict(),
            diff_var_dict=self.var_factory.get_diff_var_dict(),
            composite_expression_ids=composite_expression_ids
        )

        init_eq_list: List[Dict[str, Any]] = list()
        diff_init_eq_list: List[Dict[str, Any]] = list()
        for var, expr in blk.init_eqs.items():
            self._ensure_var_registered(var)

            init_eq_list.append(
                {
                    "var": var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids
                    )
                }
            )

        for diff_var, expr in blk.diff_init_eqs.items():
            self._ensure_diff_var_registered(diff_var)

            diff_init_eq_list.append(
                {
                    "var": diff_var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids
                    )
                }
            )

        post_init_seed_list: List[Mapping[str, object]] = list()
        for var, expr in blk.post_init_seed_eqs.items():
            self._ensure_var_registered(var)
            post_init_seed_list.append(
                {
                    "var": var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids,
                    ),
                }
            )

        events_list: List[Dict[str, Any]] = list()
        for var, expr in blk.event_dict.items():
            self._ensure_var_registered(var)

            events_list.append(
                {
                    "var": var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids
                    )
                }
            )

        mode_list: List[Dict[str, Any]] = list()
        for var, expr in blk.mode_dict.items():
            self._ensure_var_registered(var)
            mode_list.append(
                {
                    "var": var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids
                    )
                }
            )

        discrete_list: List[Dict[str, Any]] = list()
        for var, expr in blk.discrete_eqs.items():
            self._ensure_var_registered(var)
            discrete_list.append(
                {
                    "var": var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids
                    )
                }
            )

        boolean_guard_list: List[Dict[str, Any]] = list()
        for var, expr in blk.boolean_guards.items():
            self._ensure_var_registered(var)
            boolean_guard_list.append(
                {
                    "var": var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids
                    )
                }
            )

        in_vars: List[int] = list()
        for var in blk.in_vars:
            self._ensure_var_registered(var)

            in_vars.append(var.non_mutable_uid)

        out_vars: List[int] = list()
        for var in blk.out_vars:
            self._ensure_var_registered(var)

            out_vars.append(var.non_mutable_uid)

        init_values: List[Dict[str, object]] = list()
        init_value_var: Var
        init_value_const: Const
        for init_value_var, init_value_const in blk.init_values.items():
            self._ensure_var_registered(init_value_var)

            # Persist the symbolic constant by reference so its UID survives a
            # save/load cycle. This identity is part of the block comparison
            # contract and cannot be reconstructed from the numeric value alone.
            init_values.append(
                {
                    "var": init_value_var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=init_value_const,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids,
                    ),
                }
            )

        parameters: List[Dict[str, object]] = list()
        parameter_var: Var
        parameter_const: Const
        for parameter_var, parameter_const in blk.parameters.items():
            self._ensure_var_registered(parameter_var)

            # Static-parameter fallbacks are symbolic constants as well. Their
            # full identity must therefore use the same shared constant table as
            # equation expressions instead of an inline value-only record.
            parameters.append(
                {
                    "var": parameter_var.non_mutable_uid,
                    "expr": expr_to_dict(
                        expr=parameter_const,
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self.var_factory.get_vars_dict(),
                        diff_var_dict=self.var_factory.get_diff_var_dict(),
                        composite_expression_ids=composite_expression_ids,
                    ),
                }
            )

        # diff_vars: List[DiffVar] = list()
        for diff_var in blk.diff_vars:
            self._ensure_diff_var_registered(diff_var)

        for dyn_var_type, var in blk.external_mapping.items():
            if var is not None:
                self._ensure_var_registered(var)
            else:
                pass

        dynamic_model_contract_data: Dict[str, object] = (
            blk.dynamic_model_contract.to_data()
        )
        override_expression_data: Dict[str, object] = dict()
        override_name: str
        override_expression: Expr
        for override_name, override_expression in (
                blk.dynamic_model_contract.explicit_init_override_init_exprs.items()
        ):
            override_expression_data[override_name] = expr_to_dict(
                expr=override_expression,
                const_dict=self.var_factory.get_const_dict(),
                var_dict=self.var_factory.get_vars_dict(),
                diff_var_dict=self.var_factory.get_diff_var_dict(),
                composite_expression_ids=composite_expression_ids,
            )
        dynamic_model_contract_data[
            "explicit_init_override_init_exprs"
        ] = override_expression_data

        # save diagram
        diagram = blk.diagram.to_dict()

        # save children
        for child in blk.children:
            self.save_block(child)

        d = {
            "uid": blk.uid,

            "vars_glob_name2uid": blk.vars_glob_name2uid,

            "state_vars": [v.non_mutable_uid for v in blk.state_vars],

            "state_eqs": state_expressions,

            "inequalities": inequality_expressions,

            "algebraic_vars": [v.non_mutable_uid for v in blk.algebraic_vars],

            "algebraic_eqs": algebraic_expressions,

            "diff_vars": [v.non_mutable_uid for v in blk.diff_vars],

            "differential_eqs": differential_eqs_expressions,

            "reformulated_vars": [v.non_mutable_uid for v in blk.reformulated_vars],

            "init_eqs": init_eq_list,

            "diff_init_eqs": diff_init_eq_list,

            "post_init_seed_eqs": post_init_seed_list,

            "discrete_eqs": discrete_list,

            "mode_dict": mode_list,

            "boolean_guards": boolean_guard_list,

            "procedural_logic": list(
                entry.to_data() for entry in blk.procedural_logic
            ),

            "init_values": init_values,

            "parameters": parameters,

            "external_mapping": {dyn_var_type.value: var.non_mutable_uid if var is not None else None
                                 for dyn_var_type, var in blk.external_mapping.items()},

            "api_obj_mapping": {dyn_param_type.value: param.non_mutable_uid if param is not None else None
                                for dyn_param_type, param in blk.api_obj_mapping.items()},

            "event_dict": events_list,
            "name": blk.name,
            "model_family_name": blk.model_family_name,
            "children": [child.uid for child in blk.children],
            "in_vars": in_vars,
            "out_vars": out_vars,

            # Only the current semantic state is persisted. Graphical history
            # and topology-specific materialization remain outside the model.
            "connection_intents": [dynamic_connection_intent_to_dict(intent)
                                   for intent in blk.connection_intents],

            "dynamic_model_contract": dynamic_model_contract_data,

            "diagram": diagram
        }

        self.blocks[blk.uid] = d
        if main:
            self.main_block_uids.append(blk.uid)

        return d


class BlockParser:
    __slots__ = (
        "var_factory",
        "block_dict",
        "logger",
        "_var_identity_lookup",
        "_diff_var_identity_lookup",
        "_procedural_logic_codec",
    )

    def __init__(
            self,
            var_factory: VarFactory,
            logger: Logger | None = None,
            procedural_logic_codec: ProceduralLogicCodecContract[Expr] | None = None,
    ) -> None:
        """Create a block parser bound to one symbolic variable factory.

        :param var_factory: Factory used to resolve persisted symbolic identities.
        :param logger: Optional logger receiving recoverable parsing warnings.
        :param procedural_logic_codec: Explicit declarative logic codec.
        :return: None.
        """
        self.var_factory = var_factory
        self.block_dict: Dict[int, Block] = dict()
        self.logger: Logger | None = logger
        self._var_identity_lookup: Dict[int, Var] = build_persisted_identity_lookup(
            var_dict=self.var_factory.get_vars_dict()
        )
        self._diff_var_identity_lookup: Dict[int, Var] = build_persisted_identity_lookup(
            var_dict=self.var_factory.get_diff_var_dict()
        )
        self._procedural_logic_codec: ProceduralLogicCodecContract[Expr] | None = (
            procedural_logic_codec
        )

    def _rebuild_persisted_identity_lookups(self) -> None:
        """
        Rebuild constant-time symbolic lookups after persisted data changes UIDs.

        Connection replay mutates runtime UIDs, so both lookup tables must be
        rebuilt after variables, differential variables or connections are
        parsed and before expression reconstruction begins.

        :return: None.
        """
        self._var_identity_lookup = build_persisted_identity_lookup(
            var_dict=self.var_factory.get_vars_dict()
        )
        self._diff_var_identity_lookup = build_persisted_identity_lookup(
            var_dict=self.var_factory.get_diff_var_dict()
        )

    def _add_warning(self,
                     msg: str,
                     block_name: str,
                     block_uid: int,
                     field_name: str,
                     missing_uid: int | None) -> None:
        """
        Record one non-fatal warning while rebuilding one dynamic block.

        :param msg: Warning message.
        :param block_name: Block name.
        :param block_uid: Block uid.
        :param field_name: Block field being parsed.
        :param missing_uid: Missing symbolic uid.
        :return: None.
        """
        if self.logger is not None:
            self.logger.add_warning(msg=msg,
                                    device=block_name,
                                    value=missing_uid,
                                    device_property=field_name,
                                    device_class=f"Block:{block_uid}")
        else:
            pass

    def _add_legacy_parameter_migration_info(self, migrated_parameter_count: int) -> None:
        """
        Record one informational file-open entry for successful legacy repairs.

        The parser reports compatibility changes through the file loader logger so
        users can inspect what was updated while opening an old ``.veragrid`` file.
        Successful repairs are informational because the resulting in-memory model
        already satisfies the current RMS/EMT parameter-storage contract.

        :param migrated_parameter_count: Number of parameter declarations repaired.
        :return: None.
        """
        if self.logger is not None:
            self.logger.add_info(
                msg="Migrated legacy dynamic parameter declarations",
                value=migrated_parameter_count,
                expected_value=(
                    "Static API mapping targets in Block.parameters and "
                    "runtime model values in Block.event_dict, without obsolete "
                    "dynamic API mappings and with one owner per parameter"
                ),
                device_class="Dynamic model compatibility",
                device_property="api_obj_mapping",
            )
        else:
            pass

    def _is_legacy_governor_dynamic_mapping(
            self,
            block: Block,
            mapping_key: ParamPowerFlowReferenceType,
    ) -> bool:
        """Identify one obsolete dynamic mapping from the old governor layout.

        The reference key alone is insufficient because, for example, ``P0``
        is also a valid runtime mapping for converter models. Historical governor
        blocks are identified by their joint droop and power-limit mapping
        signature before any key is treated as model-owned dynamic data. This
        also covers older governors which predate the PI-control fields.

        :param block: Block which owns the API-object mapping.
        :param mapping_key: Mapping reference to classify.
        :return: Whether the mapping belongs to the old governor dynamic layout.
        """
        if not mapping_key.is_legacy_governor_dynamic_reference():
            result: bool = False
        elif ParamPowerFlowReferenceType.Pmin not in block.api_obj_mapping:
            result = False
        elif ParamPowerFlowReferenceType.Pmax not in block.api_obj_mapping:
            result = False
        elif ParamPowerFlowReferenceType.K not in block.api_obj_mapping:
            result = False
        else:
            result = True
        return result

    def _is_static_api_parameter_mapping(
            self,
            block: Block,
            mapping_key: ParamPowerFlowReferenceType,
    ) -> bool:
        """Classify a legacy mapping whose target has a constant declaration.

        :param block: Block which owns the API-object mapping.
        :param mapping_key: Mapping reference to classify.
        :return: Whether the local mapping target belongs to ``Block.parameters``.
        """
        mapping_target: Var | None = block.api_obj_mapping.get(mapping_key, None)

        if self._is_legacy_governor_dynamic_mapping(block=block, mapping_key=mapping_key):
            result: bool = False
        elif mapping_key.is_runtime_parameter_reference():
            # These operating-point references were temporarily written to
            # ``parameters`` by an intermediate migration. They remain runtime
            # values even when that incorrect constant declaration is present.
            result = False
        elif mapping_target is None:
            result = False
        elif mapping_target in block.parameters and mapping_target not in block.event_dict:
            result = True
        else:
            # The declaration, rather than the enum key, determines whether a
            # mapped initial value is immutable or event-capable.
            result = False
        return result

    def _migrate_legacy_ancestor_static_mapping(
            self,
            hierarchy_blocks: List[Block],
            mapping_block: Block,
            mapping_key: ParamPowerFlowReferenceType,
            stable_uid: int,
    ) -> tuple[bool, bool]:
        """Localize an ancestor mapping on its child runtime owner.

        Historical non-recursive initialization copied child mappings onto a
        wrapper. The child's declaration is authoritative: a target in
        ``event_dict`` stays event-capable even when its fallback expression is a
        constant. Only the mapping ownership is repaired.

        :param hierarchy_blocks: Complete block hierarchy being migrated.
        :param mapping_block: Ancestor which currently stores the mapping.
        :param mapping_key: Static-device reference being migrated.
        :param stable_uid: Stable identity of the mapped target.
        :return: Whether to remove the ancestor mapping and whether a static
                 declaration was promoted.
        """
        runtime_owner: Block | None = None
        runtime_variable: Var | None = None
        runtime_value: Expr | Const | None = None
        candidate_block: Block
        candidate_variable: Var
        candidate_value: Expr | Const

        # Locate the actual child declaration by stable identity because legacy
        # connection replay may have changed the variable's mutable UID.
        for candidate_block in hierarchy_blocks:
            for candidate_variable, candidate_value in candidate_block.event_dict.items():
                if runtime_owner is None and candidate_variable.non_mutable_uid == stable_uid:
                    runtime_owner = candidate_block
                    runtime_variable = candidate_variable
                    runtime_value = candidate_value
                else:
                    pass

        if runtime_owner is None or runtime_variable is None or runtime_value is None:
            # Mode-dictionary parameters also have a runtime role but cannot be
            # promoted to static data. Their ancestor mapping is still obsolete.
            remove_ancestor_mapping: bool = True
            promoted_static_parameter: bool = False
        else:
            existing_mapping_target: Var | None = runtime_owner.api_obj_mapping.get(mapping_key, None)
            if existing_mapping_target is None:
                runtime_owner.api_obj_mapping[mapping_key] = runtime_variable
                mapping_localized: bool = True
            elif existing_mapping_target.non_mutable_uid == stable_uid:
                mapping_localized = True
            else:
                mapping_localized = False
                self._add_warning(
                    msg="Legacy ancestor static mapping conflicts with the child parameter owner",
                    block_name=mapping_block.name,
                    block_uid=mapping_block.uid,
                    field_name="api_obj_mapping",
                    missing_uid=stable_uid,
                )

            if mapping_localized:
                remove_ancestor_mapping = True
                promoted_static_parameter = False
            else:
                remove_ancestor_mapping = False
                promoted_static_parameter = False

        return remove_ancestor_mapping, promoted_static_parameter

    def _repair_legacy_static_parameter_ownership(
            self,
            root_block: Block,
    ) -> int:
        """Normalize historical parent/child copies of one static parameter.

        Older editor and template paths could mirror a child's ``parameters``
        and ``api_obj_mapping`` entries into a wrapper root. The recursive RMS
        and EMT contract now requires exactly one declaring block, with the API
        mapping stored on that same owner. This compatibility pass keeps the
        deepest declaration, preserves a concrete fallback when available, and
        moves or removes redundant ancestor mappings without changing symbolic
        identities.

        :param root_block: Parsed dynamic-model root to normalize.
        :return: Number of ownership records repaired.
        """
        hierarchy_blocks: List[Block] = root_block.get_all_blocks()
        block_depth_by_uid: Dict[int, int] = dict()
        parameter_owners_by_uid: Dict[int, List[Block]] = dict()
        ownership_repairs: int = 0
        pending_blocks: List[tuple[Block, int]] = list(((root_block, 0),))

        # Record hierarchy depth explicitly so a genuine child declaration wins
        # over the wrapper copy introduced by old GUI save paths.
        while len(pending_blocks) > 0:
            pending_block: Block
            pending_depth: int
            pending_block, pending_depth = pending_blocks.pop()
            previous_depth: int | None = block_depth_by_uid.get(pending_block.uid, None)
            if previous_depth is None or pending_depth > previous_depth:
                block_depth_by_uid[pending_block.uid] = pending_depth
                child_block: Block
                for child_block in pending_block.children:
                    pending_blocks.append((child_block, pending_depth + 1))
            else:
                pass

        # Group declarations by stable identity because connection replay may
        # legitimately rewrite the mutable runtime UID.
        declaration_block: Block
        declaration_parameter: Var
        for declaration_block in hierarchy_blocks:
            for declaration_parameter in declaration_block.parameters:
                optional_declaration_uid: int | None = declaration_parameter.non_mutable_uid
                if optional_declaration_uid is None:
                    self._add_warning(
                        msg="Legacy static parameter has no stable symbolic identity",
                        block_name=declaration_block.name,
                        block_uid=declaration_block.uid,
                        field_name="parameters",
                        missing_uid=None,
                    )
                else:
                    declaration_uid: int = optional_declaration_uid
                    existing_owners: List[Block] | None = parameter_owners_by_uid.get(
                        declaration_uid,
                        None,
                    )
                    resolved_owners: List[Block]
                    if existing_owners is None:
                        resolved_owners = list()
                        parameter_owners_by_uid[declaration_uid] = resolved_owners
                    else:
                        resolved_owners = existing_owners
                    resolved_owners.append(declaration_block)

        declaration_uid: int
        declaration_owners: List[Block]
        for declaration_uid, declaration_owners in parameter_owners_by_uid.items():
            # Prefer the deepest block which already has a local static mapping.
            # If no declaration has one, the deepest declaration is still the
            # least surprising owner for an old wrapper/child model.
            canonical_owner: Block = declaration_owners[0]
            canonical_depth: int = block_depth_by_uid.get(canonical_owner.uid, 0)
            canonical_has_mapping: bool = False
            candidate_owner: Block
            for candidate_owner in declaration_owners:
                candidate_has_mapping: bool = False
                candidate_key: ParamPowerFlowReferenceType
                candidate_target: Var | None
                for candidate_key, candidate_target in candidate_owner.api_obj_mapping.items():
                    if (self._is_static_api_parameter_mapping(
                            block=candidate_owner,
                            mapping_key=candidate_key,
                    )
                            and candidate_target is not None
                            and candidate_target.non_mutable_uid == declaration_uid):
                        candidate_has_mapping = True
                    else:
                        pass

                candidate_depth: int = block_depth_by_uid.get(candidate_owner.uid, 0)
                if candidate_has_mapping and not canonical_has_mapping:
                    canonical_owner = candidate_owner
                    canonical_depth = candidate_depth
                    canonical_has_mapping = True
                elif candidate_has_mapping == canonical_has_mapping and candidate_depth > canonical_depth:
                    canonical_owner = candidate_owner
                    canonical_depth = candidate_depth
                else:
                    pass

            canonical_parameter: Var | None = None
            canonical_value: Const | None = None
            declared_value: Const
            for declaration_parameter, declared_value in canonical_owner.parameters.items():
                if declaration_parameter.non_mutable_uid == declaration_uid:
                    canonical_parameter = declaration_parameter
                    canonical_value = declared_value
                else:
                    pass

            if canonical_parameter is None or canonical_value is None:
                self._add_warning(
                    msg="Legacy static parameter owner could not be resolved",
                    block_name=canonical_owner.name,
                    block_uid=canonical_owner.uid,
                    field_name="parameters",
                    missing_uid=declaration_uid,
                )
            else:
                # A numerical fallback stored by any duplicate declaration is
                # more useful than a mirrored Const(None) on the retained owner.
                if canonical_value.value is None:
                    fallback_found: bool = False
                    fallback_owner: Block
                    for fallback_owner in declaration_owners:
                        fallback_parameter: Var
                        fallback_value: Const
                        for fallback_parameter, fallback_value in fallback_owner.parameters.items():
                            if (not fallback_found
                                    and fallback_parameter.non_mutable_uid == declaration_uid
                                    and fallback_value.value is not None):
                                canonical_owner.parameters[canonical_parameter] = fallback_value
                                fallback_found = True
                                ownership_repairs += 1
                            else:
                                pass
                else:
                    pass

                # Localize every non-runtime API mapping on the retained owner.
                mapping_block: Block
                for mapping_block in hierarchy_blocks:
                    mapping_keys_to_remove: List[ParamPowerFlowReferenceType] = list()
                    mapping_key: ParamPowerFlowReferenceType
                    mapping_target: Var | None
                    for mapping_key, mapping_target in mapping_block.api_obj_mapping.items():
                        if (mapping_block is not canonical_owner
                                and self._is_static_api_parameter_mapping(
                                    block=mapping_block,
                                    mapping_key=mapping_key,
                                )
                                and mapping_target is not None
                                and mapping_target.non_mutable_uid == declaration_uid):
                            retained_target: Var | None = canonical_owner.api_obj_mapping.get(mapping_key, None)
                            if retained_target is None:
                                canonical_owner.api_obj_mapping[mapping_key] = canonical_parameter
                                mapping_keys_to_remove.append(mapping_key)
                                ownership_repairs += 1
                            elif retained_target.non_mutable_uid == declaration_uid:
                                mapping_keys_to_remove.append(mapping_key)
                                ownership_repairs += 1
                            else:
                                self._add_warning(
                                    msg="Legacy static API mapping conflicts with the retained parameter owner",
                                    block_name=mapping_block.name,
                                    block_uid=mapping_block.uid,
                                    field_name="api_obj_mapping",
                                    missing_uid=declaration_uid,
                                )
                        else:
                            pass

                    for mapping_key in mapping_keys_to_remove:
                        del mapping_block.api_obj_mapping[mapping_key]

                # Remove only declarations whose mappings were successfully
                # localized. A conflicting legacy mapping remains declared so
                # opening the file does not silently discard recoverable data.
                duplicate_owner: Block
                for duplicate_owner in declaration_owners:
                    if duplicate_owner is canonical_owner:
                        pass
                    else:
                        owner_still_maps_parameter: bool = False
                        owner_mapping_key: ParamPowerFlowReferenceType
                        owner_mapping_target: Var | None
                        for owner_mapping_key, owner_mapping_target in duplicate_owner.api_obj_mapping.items():
                            if (self._is_static_api_parameter_mapping(
                                    block=duplicate_owner,
                                    mapping_key=owner_mapping_key,
                            )
                                    and owner_mapping_target is not None
                                    and owner_mapping_target.non_mutable_uid == declaration_uid):
                                owner_still_maps_parameter = True
                            else:
                                pass

                        if owner_still_maps_parameter:
                            pass
                        else:
                            duplicate_parameter: Var | None = None
                            for declaration_parameter in duplicate_owner.parameters:
                                if declaration_parameter.non_mutable_uid == declaration_uid:
                                    duplicate_parameter = declaration_parameter
                                else:
                                    pass
                            if duplicate_parameter is not None:
                                del duplicate_owner.parameters[duplicate_parameter]
                                ownership_repairs += 1
                            else:
                                pass

        return ownership_repairs

    def _migrate_legacy_static_api_parameters(self, root_block: Block) -> int:
        """
        Restore parameter ownership omitted by historical model files.

        Older RMS and EMT files could persist a variable only in
        ``api_obj_mapping`` and rely on the problem to infer its storage. The
        current RMS/EMT contract requires every target to be declared locally in
        exactly one storage collection: immutable values in ``Block.parameters``
        and event-capable values in ``Block.event_dict``. ``api_obj_mapping``
        supplies only the initial device value and never decides that role.

        Existing declarations are therefore authoritative even when the event
        expression is a ``Const``. Only known historical signatures whose old
        semantics are unambiguous are reclassified. Wrapper mappings are moved
        to the descendant which owns the declaration, obsolete dynamic mappings
        are removed, and orphaned targets use the narrow legacy enum hint because
        no serialized storage evidence remains.

        :param root_block: Fully parsed root block whose complete hierarchy is available.
        :return: Number of parameter declarations repaired in the block hierarchy.
        """
        hierarchy_blocks: List[Block] = root_block.get_all_blocks()
        migration_blocks: List[Block] = list(reversed(hierarchy_blocks))
        parameter_uids: set[int] = set()
        runtime_parameter_uids: set[int] = set()
        non_parameter_uids: set[int] = set()
        migrated_parameter_count: int = self._repair_legacy_static_parameter_ownership(
            root_block=root_block,
        )
        block_item: Block
        parameter_var: Var
        mapping_key: ParamPowerFlowReferenceType
        mapping_target: Var | None
        runtime_expression: Expr | Const | None
        mapping_is_runtime: bool
        mapping_is_legacy_dynamic: bool
        mapping_is_static: bool

        # Classify every persisted variable before repairing mappings. Inspecting
        # the complete tree avoids copying a child-owned parameter into a wrapper.
        for block_item in hierarchy_blocks:
            for parameter_var in block_item.parameters:
                parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.event_dict:
                runtime_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.mode_dict:
                runtime_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.state_vars:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.algebraic_vars:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.diff_vars:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.reformulated_vars:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.in_vars:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.out_vars:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.init_values:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.init_eqs:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.diff_init_eqs:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.discrete_eqs:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.post_init_seed_eqs:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

            for parameter_var in block_item.boolean_guards:
                non_parameter_uids.add(parameter_var.non_mutable_uid)

        # Repair every legacy mapping primarily from its serialized owner role.
        # Sharing and converter-control references remain runtime values.
        # Obsolete governor and calculated converter-loss mappings remain
        # model-owned dynamic values but lose their obsolete API mapping. Only
        # explicitly recognized legacy governor limits are promoted because the
        # historical template contract identifies them unambiguously as fixed.
        # Process descendants before their wrappers. A historical composite can
        # expose the same mapping at both levels without declaring the target in
        # ``parameters``. The deepest mapping is the real equation owner, so it
        # must create the declaration before an ancestor observes that identity.
        for block_item in migration_blocks:
            mapping_keys_to_remove: List[ParamPowerFlowReferenceType] = list()
            mapping_entries_to_add: List[tuple[ParamPowerFlowReferenceType, Var]] = list()
            for mapping_key, mapping_target in block_item.api_obj_mapping.items():
                if mapping_target is None:
                    pass
                else:
                    stable_uid: int = mapping_target.non_mutable_uid
                    target_is_local_runtime: bool = mapping_target in block_item.event_dict
                    target_is_local_constant: bool = mapping_target in block_item.parameters
                    legacy_governor_signature: bool = self._is_legacy_governor_dynamic_mapping(
                        block=block_item,
                        mapping_key=ParamPowerFlowReferenceType.K,
                    )
                    mapping_is_known_legacy_static: bool = (
                        legacy_governor_signature
                        and mapping_key in (
                            ParamPowerFlowReferenceType.Pmin,
                            ParamPowerFlowReferenceType.Pmax,
                        )
                    )
                    if mapping_is_known_legacy_static:
                        mapping_is_runtime: bool = False
                    elif target_is_local_runtime:
                        mapping_is_runtime: bool = True
                    elif mapping_key.is_runtime_parameter_reference():
                        # An intermediate compatibility save could move special
                        # converter and sharing operating values into
                        # ``parameters``. Their dedicated runtime reference is
                        # the evidence needed to restore ``event_dict``.
                        mapping_is_runtime = True
                    elif target_is_local_constant:
                        mapping_is_runtime = False
                    elif stable_uid in runtime_parameter_uids:
                        mapping_is_runtime = True
                    elif stable_uid in parameter_uids:
                        mapping_is_runtime = False
                    else:
                        # Only an orphaned legacy target lacks a declaration from
                        # which its role can be recovered. Retain the historical
                        # key hint for that narrow compatibility case.
                        mapping_is_runtime = mapping_key.is_runtime_parameter_reference()
                    mapping_is_legacy_dynamic = self._is_legacy_governor_dynamic_mapping(
                        block=block_item,
                        mapping_key=mapping_key,
                    )
                    if (not mapping_is_legacy_dynamic
                            and mapping_key == ParamPowerFlowReferenceType.converter_loss_power_0
                            and mapping_target not in block_item.parameters
                            and stable_uid not in parameter_uids):
                        # Early converter templates exposed their calculated
                        # operating loss as though it were static device data.
                        # It is model-owned runtime state and the obsolete API
                        # mapping must be removed without moving the event value.
                        mapping_is_legacy_dynamic = True
                    else:
                        pass
                    mapping_is_static: bool = not mapping_is_runtime and not mapping_is_legacy_dynamic
                    if mapping_target in block_item.parameters:
                        if mapping_key == ParamPowerFlowReferenceType.converter_loss_power_0:
                            replacement_target: Var | None = block_item.api_obj_mapping.get(
                                ParamPowerFlowReferenceType.alpha1,
                                None,
                            )
                            if replacement_target is None:
                                mapping_entries_to_add.append((
                                    ParamPowerFlowReferenceType.alpha1,
                                    mapping_target,
                                ))
                                mapping_keys_to_remove.append(mapping_key)
                                migrated_parameter_count += 1
                            elif replacement_target.non_mutable_uid == stable_uid:
                                mapping_keys_to_remove.append(mapping_key)
                                migrated_parameter_count += 1
                            else:
                                self._add_warning(
                                    msg="Legacy converter loss mapping conflicts with alpha1",
                                    block_name=block_item.name,
                                    block_uid=block_item.uid,
                                    field_name="api_obj_mapping",
                                    missing_uid=stable_uid,
                                )
                        elif (mapping_is_known_legacy_static
                              and mapping_target in block_item.event_dict):
                            declared_parameter_value: Const = block_item.parameters[mapping_target]
                            runtime_expression: Expr | Const = block_item.event_dict[mapping_target]

                            # An intermediate compatibility save may contain both
                            # roles. The complete historical governor signature is
                            # the only case where legacy evidence unambiguously
                            # identifies Pmin/Pmax as immutable device parameters.
                            if (declared_parameter_value.value is None
                                    and isinstance(runtime_expression, Const)
                                    and runtime_expression.value is not None):
                                block_item.parameters[mapping_target] = runtime_expression
                            else:
                                pass

                            del block_item.event_dict[mapping_target]
                            runtime_parameter_uids.discard(stable_uid)
                            parameter_uids.add(stable_uid)
                            migrated_parameter_count += 1
                        elif mapping_is_legacy_dynamic:
                            declared_parameter_value: Const = block_item.parameters[mapping_target]
                            runtime_expression = block_item.event_dict.get(mapping_target, None)

                            # Files saved after the first static-parameter migration
                            # can contain a dynamic governor value in ``parameters``.
                            # Move it back so reopening such an intermediate file is
                            # as safe as opening the original historical archive.
                            if runtime_expression is None:
                                block_item.event_dict[mapping_target] = declared_parameter_value
                            elif (isinstance(runtime_expression, Const)
                                  and runtime_expression.value is None
                                  and declared_parameter_value.value is not None):
                                block_item.event_dict[mapping_target] = declared_parameter_value
                            else:
                                pass

                            del block_item.parameters[mapping_target]
                            parameter_uids.discard(stable_uid)
                            runtime_parameter_uids.add(stable_uid)
                            mapping_keys_to_remove.append(mapping_key)
                            migrated_parameter_count += 1
                        elif mapping_is_runtime:
                            declared_parameter_value = block_item.parameters[mapping_target]
                            runtime_expression = block_item.event_dict.get(mapping_target, None)

                            # An intermediate compatibility save may have moved a
                            # converter operating reference into static storage.
                            # Restore its runtime owner while retaining the API
                            # mapping used to seed the operating point.
                            if runtime_expression is None:
                                block_item.event_dict[mapping_target] = declared_parameter_value
                            elif (isinstance(runtime_expression, Const)
                                  and runtime_expression.value is None
                                  and declared_parameter_value.value is not None):
                                block_item.event_dict[mapping_target] = declared_parameter_value
                            else:
                                pass

                            del block_item.parameters[mapping_target]
                            parameter_uids.discard(stable_uid)
                            runtime_parameter_uids.add(stable_uid)
                            migrated_parameter_count += 1
                        elif mapping_is_static and mapping_target in block_item.event_dict:
                            runtime_expression = block_item.event_dict[mapping_target]
                            declared_parameter_value = block_item.parameters[mapping_target]

                            # A duplicated declaration produced by an intermediate
                            # migration must retain the event-capable role. Preserve
                            # its usable fallback and remove only the constant copy.
                            if (isinstance(runtime_expression, Const)
                                    and runtime_expression.value is None
                                    and declared_parameter_value.value is not None):
                                block_item.event_dict[mapping_target] = declared_parameter_value
                            else:
                                pass

                            del block_item.parameters[mapping_target]
                            parameter_uids.discard(stable_uid)
                            runtime_parameter_uids.add(stable_uid)
                            migrated_parameter_count += 1
                        else:
                            pass
                    elif mapping_target in block_item.event_dict:
                        if mapping_is_legacy_dynamic:
                            # The value already has the correct owner. Removing only
                            # the stale mapping prevents RMS/EMT initialization from
                            # replacing an editable model parameter with device data.
                            mapping_keys_to_remove.append(mapping_key)
                            migrated_parameter_count += 1
                        elif mapping_is_runtime:
                            # Operating-point references are intentionally initialized
                            # at runtime and must not be converted to static constants.
                            pass
                        elif mapping_is_static:
                            if mapping_is_known_legacy_static:
                                runtime_expression = block_item.event_dict[mapping_target]
                                if isinstance(runtime_expression, Const):
                                    del block_item.event_dict[mapping_target]
                                    block_item.parameters[mapping_target] = runtime_expression
                                    runtime_parameter_uids.discard(stable_uid)
                                    parameter_uids.add(stable_uid)
                                    migrated_parameter_count += 1
                                else:
                                    pass
                            else:
                                # The serialized event_dict declaration is the
                                # source of truth. A mapped initial value does not
                                # make the target immutable, even for Const.
                                pass
                        else:
                            pass
                    elif stable_uid in parameter_uids:
                        if mapping_is_legacy_dynamic:
                            legacy_parameter_owner: Block | None = None
                            legacy_parameter_var: Var | None = None
                            legacy_parameter_value: Const | None = None
                            candidate_block: Block
                            candidate_parameter: Var
                            candidate_value: Const

                            # A stale wrapper mapping can reference a dynamic value
                            # which an intermediate compatibility save placed in a
                            # descendant ``parameters`` collection. Restore that
                            # declaration at its actual equation owner.
                            for candidate_block in hierarchy_blocks:
                                for candidate_parameter, candidate_value in candidate_block.parameters.items():
                                    if (legacy_parameter_owner is None
                                            and candidate_parameter.non_mutable_uid == stable_uid):
                                        legacy_parameter_owner = candidate_block
                                        legacy_parameter_var = candidate_parameter
                                        legacy_parameter_value = candidate_value
                                    else:
                                        pass

                            if (legacy_parameter_owner is not None
                                    and legacy_parameter_var is not None
                                    and legacy_parameter_value is not None):
                                existing_runtime_value: Expr | Const | None = legacy_parameter_owner.event_dict.get(
                                    legacy_parameter_var,
                                    None,
                                )
                                if existing_runtime_value is None:
                                    legacy_parameter_owner.event_dict[legacy_parameter_var] = legacy_parameter_value
                                elif (isinstance(existing_runtime_value, Const)
                                      and existing_runtime_value.value is None
                                      and legacy_parameter_value.value is not None):
                                    legacy_parameter_owner.event_dict[legacy_parameter_var] = legacy_parameter_value
                                else:
                                    pass

                                del legacy_parameter_owner.parameters[legacy_parameter_var]
                                parameter_uids.discard(stable_uid)
                                runtime_parameter_uids.add(stable_uid)
                                mapping_keys_to_remove.append(mapping_key)
                                migrated_parameter_count += 1
                            else:
                                self._add_warning(
                                    msg="Legacy dynamic parameter owner could not be restored",
                                    block_name=block_item.name,
                                    block_uid=block_item.uid,
                                    field_name="api_obj_mapping",
                                    missing_uid=stable_uid,
                                )
                        elif mapping_is_runtime:
                            runtime_parameter_owner: Block | None = None
                            runtime_parameter_var: Var | None = None
                            runtime_parameter_value: Const | None = None
                            runtime_candidate_block: Block
                            runtime_candidate_var: Var
                            runtime_candidate_value: Const

                            # A wrapper runtime mapping can point to a child value
                            # which an earlier migration incorrectly made static.
                            # Restore the child event declaration and localize the
                            # mapping before removing the wrapper copy.
                            for runtime_candidate_block in hierarchy_blocks:
                                for runtime_candidate_var, runtime_candidate_value in (
                                        runtime_candidate_block.parameters.items()
                                ):
                                    if (runtime_parameter_owner is None
                                            and runtime_candidate_var.non_mutable_uid == stable_uid):
                                        runtime_parameter_owner = runtime_candidate_block
                                        runtime_parameter_var = runtime_candidate_var
                                        runtime_parameter_value = runtime_candidate_value
                                    else:
                                        pass

                            if (runtime_parameter_owner is not None
                                    and runtime_parameter_var is not None
                                    and runtime_parameter_value is not None):
                                retained_runtime_target: Var | None = (
                                    runtime_parameter_owner.api_obj_mapping.get(mapping_key, None)
                                )
                                if retained_runtime_target is None:
                                    runtime_parameter_owner.api_obj_mapping[mapping_key] = runtime_parameter_var
                                    runtime_mapping_localized: bool = True
                                elif retained_runtime_target.non_mutable_uid == stable_uid:
                                    runtime_mapping_localized = True
                                else:
                                    runtime_mapping_localized = False
                                    self._add_warning(
                                        msg="Legacy runtime API mapping conflicts with the child event owner",
                                        block_name=block_item.name,
                                        block_uid=block_item.uid,
                                        field_name="api_obj_mapping",
                                        missing_uid=stable_uid,
                                    )

                                if runtime_mapping_localized:
                                    runtime_parameter_owner.event_dict[runtime_parameter_var] = (
                                        runtime_parameter_value
                                    )
                                    del runtime_parameter_owner.parameters[runtime_parameter_var]
                                    parameter_uids.discard(stable_uid)
                                    runtime_parameter_uids.add(stable_uid)
                                    mapping_keys_to_remove.append(mapping_key)
                                    migrated_parameter_count += 1
                                else:
                                    pass
                            else:
                                self._add_warning(
                                    msg="Legacy runtime parameter owner could not be restored",
                                    block_name=block_item.name,
                                    block_uid=block_item.uid,
                                    field_name="api_obj_mapping",
                                    missing_uid=stable_uid,
                                )
                        else:
                            static_parameter_owner: Block | None = None
                            static_parameter_var: Var | None = None
                            static_candidate_block: Block
                            static_candidate_var: Var

                            # Historical wrapper mappings may point to a constant
                            # declared by one descendant. Localize the mapping on
                            # that declaration owner so recursive RMS and EMT
                            # initialization follow the same owner-local contract.
                            for static_candidate_block in hierarchy_blocks:
                                for static_candidate_var in static_candidate_block.parameters:
                                    if (static_parameter_owner is None
                                            and static_candidate_var.non_mutable_uid == stable_uid):
                                        static_parameter_owner = static_candidate_block
                                        static_parameter_var = static_candidate_var
                                    else:
                                        pass

                            if static_parameter_owner is None or static_parameter_var is None:
                                pass
                            elif static_parameter_owner is block_item:
                                block_item.api_obj_mapping[mapping_key] = static_parameter_var
                                migrated_parameter_count += 1
                            else:
                                retained_static_target: Var | None = (
                                    static_parameter_owner.api_obj_mapping.get(mapping_key, None)
                                )
                                if retained_static_target is None:
                                    static_parameter_owner.api_obj_mapping[mapping_key] = static_parameter_var
                                    mapping_keys_to_remove.append(mapping_key)
                                    migrated_parameter_count += 1
                                elif retained_static_target.non_mutable_uid == stable_uid:
                                    mapping_keys_to_remove.append(mapping_key)
                                    migrated_parameter_count += 1
                                else:
                                    self._add_warning(
                                        msg="Legacy static API mapping conflicts with the child parameter owner",
                                        block_name=block_item.name,
                                        block_uid=block_item.uid,
                                        field_name="api_obj_mapping",
                                        missing_uid=stable_uid,
                                    )
                    elif stable_uid in runtime_parameter_uids:
                        if mapping_is_legacy_dynamic:
                            # Old composite models exposed child-owned event
                            # parameters from their wrapper. Keeping that mapping
                            # would override the editable event expression with
                            # static-device data. The recursive runtime declaration
                            # is complete, so only the obsolete ancestor mapping
                            # needs to be discarded.
                            mapping_keys_to_remove.append(mapping_key)
                            migrated_parameter_count += 1
                        elif mapping_is_runtime:
                            runtime_owner: Block | None = None
                            runtime_owner_var: Var | None = None
                            owner_candidate: Block
                            owner_runtime_var: Var

                            # Old composite files may expose a child operating
                            # reference only from their wrapper. Move that mapping
                            # to the block which owns the event declaration so the
                            # shared recursive mapper sees one local contract.
                            for owner_candidate in hierarchy_blocks:
                                for owner_runtime_var in owner_candidate.event_dict:
                                    if (runtime_owner is None
                                            and owner_runtime_var.non_mutable_uid == stable_uid):
                                        runtime_owner = owner_candidate
                                        runtime_owner_var = owner_runtime_var
                                    else:
                                        pass

                            if runtime_owner is None or runtime_owner_var is None:
                                pass
                            elif runtime_owner is block_item:
                                block_item.api_obj_mapping[mapping_key] = runtime_owner_var
                                migrated_parameter_count += 1
                            else:
                                owner_mapping_target: Var | None = runtime_owner.api_obj_mapping.get(
                                    mapping_key,
                                    None,
                                )
                                if owner_mapping_target is None:
                                    runtime_owner.api_obj_mapping[mapping_key] = runtime_owner_var
                                else:
                                    pass
                                mapping_keys_to_remove.append(mapping_key)
                                migrated_parameter_count += 1
                        elif mapping_is_static:
                            remove_ancestor_mapping: bool
                            promoted_static_parameter: bool
                            remove_ancestor_mapping, promoted_static_parameter = (
                                self._migrate_legacy_ancestor_static_mapping(
                                    hierarchy_blocks=hierarchy_blocks,
                                    mapping_block=block_item,
                                    mapping_key=mapping_key,
                                    stable_uid=stable_uid,
                                )
                            )
                            if remove_ancestor_mapping:
                                mapping_keys_to_remove.append(mapping_key)
                                migrated_parameter_count += 1
                            else:
                                pass

                            if promoted_static_parameter:
                                runtime_parameter_uids.discard(stable_uid)
                                parameter_uids.add(stable_uid)
                            else:
                                pass
                        else:
                            pass
                    elif stable_uid in non_parameter_uids:
                        self._add_warning(
                            msg=(
                                "Legacy API-object mapping target has a non-parameter "
                                "symbolic role and was not promoted"
                            ),
                            block_name=block_item.name,
                            block_uid=block_item.uid,
                            field_name="api_obj_mapping",
                            missing_uid=stable_uid,
                        )
                    else:
                        if mapping_is_legacy_dynamic:
                            # Preserve the unresolved dynamic declaration so old
                            # equations remain editable, but discard the obsolete
                            # API mapping which has no static-device meaning.
                            block_item.event_dict[mapping_target] = Const(None)
                            runtime_parameter_uids.add(stable_uid)
                            mapping_keys_to_remove.append(mapping_key)
                            migrated_parameter_count += 1
                        elif mapping_is_runtime:
                            block_item.event_dict[mapping_target] = Const(None)
                            runtime_parameter_uids.add(stable_uid)
                            migrated_parameter_count += 1
                        elif mapping_is_static:
                            block_item.parameters[mapping_target] = Const(None)
                            parameter_uids.add(stable_uid)
                            migrated_parameter_count += 1
                        else:
                            pass

            # Mutate the mapping after iteration so every persisted entry is
            # classified exactly once and dictionary traversal stays stable.
            replacement_key: ParamPowerFlowReferenceType
            replacement_var: Var
            for replacement_key, replacement_var in mapping_entries_to_add:
                block_item.api_obj_mapping[replacement_key] = replacement_var
            for mapping_key in mapping_keys_to_remove:
                del block_item.api_obj_mapping[mapping_key]

        # Newly materialized declarations can reveal legacy wrapper mappings
        # which were impossible to classify during the initial ownership pass.
        # Normalize once more in the same load so saving and reopening cannot
        # cause a second structural migration.
        migrated_parameter_count += self._repair_legacy_static_parameter_ownership(
            root_block=root_block,
        )

        return migrated_parameter_count

    def _resolve_var_or_warn(self,
                             var_uid: int | None,
                             block_name: str,
                             block_uid: int,
                             field_name: str) -> Var | None:
        """
        Resolve one algebraic symbolic variable with legacy-tolerant fallback.

        :param var_uid: Variable uid.
        :param block_name: Block name.
        :param block_uid: Block uid.
        :param field_name: Block field being parsed.
        :return: Resolved variable or ``None``.
        """
        resolved_var: Var | None

        if var_uid is None:
            resolved_var = None
        else:
            resolved_var = self._var_identity_lookup.get(var_uid, None)

        if resolved_var is None:
            self._add_warning(msg="Missing symbolic variable while parsing dynamic block",
                              block_name=block_name,
                              block_uid=block_uid,
                              field_name=field_name,
                              missing_uid=var_uid)
        else:
            pass

        return resolved_var

    def _resolve_diff_var_or_warn(self,
                                  var_uid: int | None,
                                  block_name: str,
                                  block_uid: int,
                                  field_name: str) -> Var | None:
        """
        Resolve one differential symbolic variable with legacy-tolerant fallback.

        :param var_uid: Differential variable uid.
        :param block_name: Block name.
        :param block_uid: Block uid.
        :param field_name: Block field being parsed.
        :return: Resolved differential variable or ``None``.
        """
        resolved_var: Var | None

        if var_uid is None:
            resolved_var = None
        else:
            resolved_var = self._diff_var_identity_lookup.get(var_uid, None)

        if resolved_var is None:
            self._add_warning(msg="Missing differential symbolic variable while parsing dynamic block",
                              block_name=block_name,
                              block_uid=block_uid,
                              field_name=field_name,
                              missing_uid=var_uid)
        else:
            pass

        return resolved_var

    def _get_var_by_non_mutable_uid(self, non_mutable_uid: int) -> Var:
        """
        Recover one algebraic variable using its stable non-mutable UID.

        The symbolic connection system intentionally aliases connected
        variables by rewriting their runtime ``uid`` values. That aliasing is
        required by the solver, but block interfaces such as ``in_vars`` and
        ``out_vars`` must still be reconstructed with the original variable
        objects so metadata like ``ref`` keeps the semantic meaning assigned by
        the template author. Looking up ports by the mutable ``uid`` after
        replaying saved connections can therefore return a different connected
        variable, such as a bus variable replacing a branch terminal variable.

        :param non_mutable_uid: Stable symbolic variable identity.
        :return: Matching algebraic variable.
        :raises KeyError: If the variable is not present in the factory.
        """
        var_obj: Var | None = self._var_identity_lookup.get(non_mutable_uid, None)
        if var_obj is not None:
            return var_obj
        else:
            raise KeyError(f"Var with non_mutable_uid {non_mutable_uid} was not found in VarFactory")

    def _find_var_or_diff_var_by_non_mutable_uid(self, non_mutable_uid: int) -> Var | None:
        """
        Recover one symbolic variable or differential variable by stable identity.

        External mappings expose semantic power-flow references to specific
        symbolic variables. Saved connection replay may alias runtime ``uid``
        values across connected variables, so rebuilding external mappings by
        mutable ``uid`` can return a different connected variable and lose the
        original semantic role. This helper resolves the mapping through the
        stable dictionary keys used by the variable factory instead.

        :param non_mutable_uid: Stable symbolic identity stored in the file.
        :return: Matching variable or ``None`` when the mapping is unresolved.
        """
        var_obj: Var | None = self._var_identity_lookup.get(non_mutable_uid, None)
        if var_obj is not None:
            return var_obj
        else:
            diff_var_obj: Var | None = self._diff_var_identity_lookup.get(non_mutable_uid, None)
            if diff_var_obj is not None:
                return diff_var_obj
            else:
                return None

    def parse_consts(self, data: List[Dict[str, Any]]):
        """

        :param data:
        :return:
        """
        self.var_factory.parse_const_dict(data_list=data)

    def parse_vars(self, data: List[Dict[str, Any]]):
        """

        :param data:
        :return:
        """
        self.var_factory.parse_var_dict(data_list=data)
        self._rebuild_persisted_identity_lookups()

    def parse_diff_vars(self, data: List[Dict[str, Any]]):
        """

        :param data:
        :return:
        """
        self.var_factory.parse_diff_var_dict(data_list=data)
        self._rebuild_persisted_identity_lookups()

    def parse_references(self, data: List[Dict[str, Any]]):
        """

        :param data:
        :type data:
        :return:
        :rtype:
        """
        self.var_factory.parse_references_dict(datalist=data)

    def parse_connections(self, data: Dict[int, List[Any]]):
        """

        :param data:
        :type data:
        :return:
        :rtype:
        """
        self.var_factory.parse_connections_dict(datalist=data)
        self._rebuild_persisted_identity_lookups()

    def parse_blocks(self,
                     blocks_data: Dict[Any, Any] | List[Dict[str, Any]],
                     main_block_uids: List[Any] | None = None) -> List[Block]:
        """
        Parse a complete current or historical persisted block collection.

        Dynamics archives created before commit ``1a59bfa9b`` do not contain
        ``main_block_uids``. Their roots are inferred from the child graph after
        normalizing list-based and inline-child representations.

        :param blocks_data: Persisted block collection.
        :param main_block_uids: Explicit roots, or ``None`` for legacy inference.
        :return: Parsed root blocks.
        """
        normalized_blocks: Dict[int, Dict[str, Any]] = normalize_persisted_blocks(blocks_data=blocks_data)
        normalized_main_uids: List[int] = list()

        if main_block_uids is not None:
            persisted_main_uid: Any
            for persisted_main_uid in main_block_uids:
                normalized_main_uid: int | None = normalize_persisted_block_uid(persisted_main_uid)
                if normalized_main_uid is not None:
                    normalized_main_uids.append(normalized_main_uid)
                else:
                    self._add_warning(msg="Invalid main dynamic block UID in persisted symbolic data",
                                      block_name="",
                                      block_uid=0,
                                      field_name="main_block_uids",
                                      missing_uid=None)
        else:
            pass

        if len(normalized_main_uids) == 0:
            normalized_main_uids = infer_persisted_main_block_uids(blocks_data=normalized_blocks)
        else:
            pass

        parsed_blocks: List[Block] = list()
        migrated_parameter_count: int = 0
        main_block_uid: int
        for main_block_uid in normalized_main_uids:
            if main_block_uid in normalized_blocks:
                parsed_block: Block = self._parse_normalized_block(blocks_data=normalized_blocks,
                                                                    main_block_uid=main_block_uid,
                                                                    ancestor_uids=set())
                migrated_parameter_count += self._migrate_legacy_static_api_parameters(
                    root_block=parsed_block
                )
                parsed_blocks.append(parsed_block)
            else:
                self._add_warning(msg="Missing main dynamic block while parsing persisted symbolic data",
                                  block_name="",
                                  block_uid=main_block_uid,
                                  field_name="main_block_uids",
                                  missing_uid=main_block_uid)

        if migrated_parameter_count > 0:
            self._add_legacy_parameter_migration_info(
                migrated_parameter_count=migrated_parameter_count
            )
        else:
            pass

        return parsed_blocks

    def parse_block(self,
                    blocks_data: Dict[Any, Any] | List[Dict[str, Any]],
                    main_block_uid: int) -> Block:
        """
        Parse one current or historical persisted block tree.

        :param blocks_data: Persisted block collection.
        :param main_block_uid: Root block UID.
        :return: Parsed root block.
        """
        normalized_blocks: Dict[int, Dict[str, Any]] = normalize_persisted_blocks(blocks_data=blocks_data)
        normalized_main_uid: int | None = normalize_persisted_block_uid(main_block_uid)
        if normalized_main_uid is not None and normalized_main_uid in normalized_blocks:
            parsed_block: Block = self._parse_normalized_block(blocks_data=normalized_blocks,
                                                                main_block_uid=normalized_main_uid,
                                                                ancestor_uids=set())
            migrated_parameter_count: int = self._migrate_legacy_static_api_parameters(
                root_block=parsed_block
            )
            if migrated_parameter_count > 0:
                self._add_legacy_parameter_migration_info(
                    migrated_parameter_count=migrated_parameter_count
                )
            else:
                pass
            return parsed_block
        else:
            raise KeyError(f"Block with persisted uid {main_block_uid} was not found")

    def _parse_normalized_block(self,
                                blocks_data: Dict[int, Dict[str, Any]],
                                main_block_uid: int,
                                ancestor_uids: set[int]) -> Block:
        """
        Parse one block from an already normalized persisted block table.

        :param blocks_data: Flat integer-keyed block table.
        :param main_block_uid: Block UID to parse.
        :param ancestor_uids: Ancestors used to reject cyclic legacy child edges.
        :return: Parsed block.
        """
        existing_block: Block | None = self.block_dict.get(main_block_uid, None)
        if existing_block is not None:
            return existing_block
        else:
            pass

        data: Dict[str, Any] = blocks_data[main_block_uid]
        active_ancestor_uids: set[int] = set(ancestor_uids)
        active_ancestor_uids.add(main_block_uid)
        block_name: str = data.get("name", "")
        # Model-family labels were introduced after the existing symbolic file
        # format. Missing and explicit null values therefore mean that no
        # custom family was assigned; neither state may prevent an old project
        # from opening.
        raw_model_family_name: object = data.get("model_family_name", "")
        if isinstance(raw_model_family_name, str):
            model_family_name: str = raw_model_family_name
        else:
            model_family_name = ""
        normalized_block_uid: int | None = normalize_persisted_block_uid(data.get("uid", main_block_uid))
        if normalized_block_uid is not None:
            block_uid_value: int = normalized_block_uid
        else:
            block_uid_value = main_block_uid

        # Graph identifiers are local to one block and may be shared across
        # several equation collections. Recursive child parsing creates an
        # independent registry for each child block.
        composite_expressions: Dict[int, Expr | Comparison] = dict()

        state_vars: List[Var] = list()
        v_uid: int
        for v_uid in data.get("state_vars", list()):
            state_var: Var | None = self._resolve_var_or_warn(v_uid, block_name, block_uid_value, "state_vars")
            if state_var is not None:
                state_vars.append(state_var)
            else:
                pass

        state_eqs = parse_expr_list(lst=data.get("state_eqs", list()),
                                    const_dict=self.var_factory.get_const_dict(),
                                    var_dict=self._var_identity_lookup,
                                    diff_var_dict=self._diff_var_identity_lookup,
                                    composite_expressions=composite_expressions)

        algebraic_vars: List[Var] = list()
        for v_uid in data.get("algebraic_vars", list()):
            algebraic_var: Var | None = self._resolve_var_or_warn(v_uid,
                                                                  block_name,
                                                                  block_uid_value,
                                                                  "algebraic_vars")
            if algebraic_var is not None:
                algebraic_vars.append(algebraic_var)
            else:
                pass

        algebraic_eqs = parse_expr_list(lst=data.get("algebraic_eqs", list()),
                                        const_dict=self.var_factory.get_const_dict(),
                                        var_dict=self._var_identity_lookup,
                                        diff_var_dict=self._diff_var_identity_lookup,
                                        composite_expressions=composite_expressions)
        if data.get("diff_vars", list()):
            diff_vars: List[Var] = list()
            for v_uid in data.get("diff_vars", list()):
                diff_var: Var | None = self._resolve_diff_var_or_warn(v_uid,
                                                                      block_name,
                                                                      block_uid_value,
                                                                      "diff_vars")
                if diff_var is not None:
                    diff_vars.append(diff_var)
                else:
                    pass
        else:
            diff_vars = list()

        differential_eqs = parse_expr_list(lst=data.get("differential_eqs", list()),
                                           const_dict=self.var_factory.get_const_dict(),
                                           var_dict=self._var_identity_lookup,
                                           diff_var_dict=self._diff_var_identity_lookup,
                                           composite_expressions=composite_expressions)

        inequalities = parse_expr_list(lst=data.get("inequalities", list()),
                                       const_dict=self.var_factory.get_const_dict(),
                                       var_dict=self._var_identity_lookup,
                                       diff_var_dict=self._diff_var_identity_lookup,
                                       composite_expressions=composite_expressions)

        # Rebuild interface variables using the stable non-mutable UID stored
        # in the factory keys. This preserves the original port object and its
        # semantic reference even when runtime connections have aliased the
        # mutable ``uid`` to another connected variable.
        in_vars: List[Var] = list()
        for v_uid in data.get("in_vars", list()):
            in_var: Var | None = self._var_identity_lookup.get(v_uid, None)
            if in_var is not None:
                in_vars.append(in_var)
            else:
                self._add_warning(msg="Missing input symbolic variable while parsing dynamic block",
                                  block_name=block_name,
                                  block_uid=block_uid_value,
                                  field_name="in_vars",
                                  missing_uid=v_uid)

        # Apply the same stable lookup to outputs for consistency with inputs
        # and to avoid replacing exported branch variables with connected bus
        # variables after deserialization.
        out_vars: List[Var] = list()
        for v_uid in data.get("out_vars", list()):
            out_var: Var | None = self._var_identity_lookup.get(v_uid, None)
            if out_var is not None:
                out_vars.append(out_var)
            else:
                self._add_warning(msg="Missing output symbolic variable while parsing dynamic block",
                                  block_name=block_name,
                                  block_uid=block_uid_value,
                                  field_name="out_vars",
                                  missing_uid=v_uid)

        # Historical files may store child records inline, reference a missing
        # child from the short-lived pointer format, or contain an accidental
        # cyclic edge. Keep all valid children and report only the invalid edge.
        children: List[Block] = list()
        child_entry: Any
        for child_entry in data.get("children", list()):
            if isinstance(child_entry, dict):
                child_uid: int | None = normalize_persisted_block_uid(child_entry.get("uid", None))
            else:
                child_uid = normalize_persisted_block_uid(child_entry)

            if child_uid is None:
                self._add_warning(msg="Invalid child dynamic block UID in persisted symbolic data",
                                  block_name=block_name,
                                  block_uid=block_uid_value,
                                  field_name="children",
                                  missing_uid=None)
            elif child_uid in active_ancestor_uids:
                self._add_warning(msg="Cyclic child dynamic block reference ignored while parsing persisted data",
                                  block_name=block_name,
                                  block_uid=block_uid_value,
                                  field_name="children",
                                  missing_uid=child_uid)
            elif child_uid not in blocks_data:
                self._add_warning(msg="Missing child dynamic block while parsing persisted symbolic data",
                                  block_name=block_name,
                                  block_uid=block_uid_value,
                                  field_name="children",
                                  missing_uid=child_uid)
            else:
                child_block: Block = self._parse_normalized_block(blocks_data=blocks_data,
                                                                  main_block_uid=child_uid,
                                                                  ancestor_uids=active_ancestor_uids)
                children.append(child_block)

        init_eqs: Dict[Var, Expr] = dict()
        entry: Dict[str, Any]
        for entry in data.get("init_eqs", list()):
            var = self._resolve_var_or_warn(entry.get("var", None), block_name, block_uid_value, "init_eqs")
            if var is not None:
                init_eqs[var] = parse_expr(data=entry["expr"],
                                           const_dict=self.var_factory.get_const_dict(),
                                           var_dict=self._var_identity_lookup,
                                           diff_var_dict=self._diff_var_identity_lookup,
                                           composite_expressions=composite_expressions)
            else:
                pass

        diff_init_eqs: Dict[Var, Expr] = dict()
        for entry in data.get("diff_init_eqs", list()):
            diff_var_entry = self._resolve_diff_var_or_warn(entry.get("var", None),
                                                            block_name,
                                                            block_uid_value,
                                                            "diff_init_eqs")
            if diff_var_entry is not None:
                diff_init_eqs[diff_var_entry] = parse_expr(data=entry["expr"],
                                                           const_dict=self.var_factory.get_const_dict(),
                                                           var_dict=self._var_identity_lookup,
                                                           diff_var_dict=self._diff_var_identity_lookup,
                                                           composite_expressions=composite_expressions)
            else:
                pass

        post_init_seed_eqs: Dict[Var, Expr | Const] = dict()
        for entry in data.get("post_init_seed_eqs", list()):
            seed_var: Var | None = self._resolve_var_or_warn(
                entry.get("var", None),
                block_name,
                block_uid_value,
                "post_init_seed_eqs",
            )
            if seed_var is not None:
                post_init_seed_eqs[seed_var] = parse_expr(
                    data=entry["expr"],
                    const_dict=self.var_factory.get_const_dict(),
                    var_dict=self._var_identity_lookup,
                    diff_var_dict=self._diff_var_identity_lookup,
                    composite_expressions=composite_expressions,
                )
            else:
                pass

        event_dict: Dict[Var, Expr] = dict()
        for entry in data.get("event_dict", list()):
            var = self._resolve_var_or_warn(entry.get("var", None), block_name, block_uid_value, "event_dict")
            if var is not None:
                event_dict[var] = parse_expr(data=entry["expr"],
                                             const_dict=self.var_factory.get_const_dict(),
                                             var_dict=self._var_identity_lookup,
                                             diff_var_dict=self._diff_var_identity_lookup,
                                             composite_expressions=composite_expressions)
            else:
                pass

        mode_dict: Dict[Var, Expr] = dict()
        for entry in data.get("mode_dict", list()):
            var = self._resolve_var_or_warn(entry.get("var", None), block_name, block_uid_value, "mode_dict")
            if var is not None:
                mode_dict[var] = parse_expr(data=entry["expr"],
                                            const_dict=self.var_factory.get_const_dict(),
                                            var_dict=self._var_identity_lookup,
                                            diff_var_dict=self._diff_var_identity_lookup,
                                            composite_expressions=composite_expressions)
            else:
                pass

        discrete_eqs: Dict[Var, Expr] = dict()
        for entry in data.get("discrete_eqs", list()):
            var = self._resolve_var_or_warn(entry.get("var", None), block_name, block_uid_value, "discrete_eqs")
            if var is not None:
                discrete_eqs[var] = parse_expr(data=entry["expr"],
                                               const_dict=self.var_factory.get_const_dict(),
                                               var_dict=self._var_identity_lookup,
                                               diff_var_dict=self._diff_var_identity_lookup,
                                               composite_expressions=composite_expressions)
            else:
                pass

        boolean_guards: Dict[Var, Expr] = dict()
        for entry in data.get("boolean_guards", list()):
            var = self._resolve_var_or_warn(entry.get("var", None), block_name, block_uid_value, "boolean_guards")
            if var is not None:
                boolean_guards[var] = parse_expr(data=entry["expr"],
                                                 const_dict=self.var_factory.get_const_dict(),
                                                 var_dict=self._var_identity_lookup,
                                                 diff_var_dict=self._diff_var_identity_lookup,
                                                 composite_expressions=composite_expressions)
            else:
                pass

        parameters: Dict[Var, Const] = dict()
        for entry in data.get("parameters", list()):
            var = self._resolve_var_or_warn(entry.get("var", None), block_name, block_uid_value, "parameters")
            if var is not None:
                if "expr" in entry and isinstance(entry["expr"], dict):
                    parsed_parameter_value: Expr | Comparison = parse_expr(
                        data=entry["expr"],
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self._var_identity_lookup,
                        diff_var_dict=self._diff_var_identity_lookup,
                        composite_expressions=composite_expressions,
                    )
                    if isinstance(parsed_parameter_value, Const):
                        parameters[var] = parsed_parameter_value
                    else:
                        # A current-format parameter must reference a constant.
                        # Preserve a recoverable inline fallback while reporting
                        # the malformed symbolic record to the file-open logger.
                        parameters[var] = Const(entry.get("value", None))
                        self._add_warning(
                            msg="Dynamic block parameter does not reference a symbolic constant",
                            block_name=block_name,
                            block_uid=block_uid_value,
                            field_name="parameters",
                            missing_uid=var.non_mutable_uid,
                        )
                else:
                    # Files written before symbolic constant references stored
                    # only the inline value. Keep that representation readable
                    # forever and allocate an identity only for that legacy data.
                    parameters[var] = Const(entry.get("value", None))
            else:
                pass

        init_values: Dict[Var, Const] = dict()
        for entry in data.get("init_values", list()):
            var = self._resolve_var_or_warn(entry.get("var", None), block_name, block_uid_value, "init_values")
            if var is not None:
                if "expr" in entry and isinstance(entry["expr"], dict):
                    parsed_initial_value: Expr | Comparison = parse_expr(
                        data=entry["expr"],
                        const_dict=self.var_factory.get_const_dict(),
                        var_dict=self._var_identity_lookup,
                        diff_var_dict=self._diff_var_identity_lookup,
                        composite_expressions=composite_expressions,
                    )
                    if isinstance(parsed_initial_value, Const):
                        init_values[var] = parsed_initial_value
                    else:
                        # Initialization values share the same Const-only
                        # contract as parameters and retain the old inline value
                        # only as a recovery path for malformed mixed records.
                        init_values[var] = Const(entry.get("value", None))
                        self._add_warning(
                            msg="Dynamic block initial value does not reference a symbolic constant",
                            block_name=block_name,
                            block_uid=block_uid_value,
                            field_name="init_values",
                            missing_uid=var.non_mutable_uid,
                        )
                else:
                    # Legacy archives have no expression reference here, so the
                    # stored scalar remains the authoritative initialization.
                    init_values[var] = Const(entry.get("value", None))
            else:
                pass

        external_mapping: Dict[VarPowerFlowReferenceType, Var | None] = dict()
        key_str: str
        var_uid: int | None
        for key_str, var_uid in data.get("external_mapping", dict()).items():
            key: VarPowerFlowReferenceType = VarPowerFlowReferenceType(key_str)
            if var_uid is None:
                # Legacy files use explicit nulls for optional power-flow
                # references, so retaining the empty slot is not data loss.
                external_mapping[key] = None
            else:
                # Rebuild PF-exposed mappings using the stable symbolic
                # identity. A non-null UID that is absent from both factory
                # dictionaries is a broken persisted-data reference and matters to
                # the user even though parsing can continue without it.
                var_in_varfactory: Var | None = self._find_var_or_diff_var_by_non_mutable_uid(var_uid)
                if var_in_varfactory is not None:
                    external_mapping[key] = var_in_varfactory
                else:
                    external_mapping[key] = None
                    self._add_warning(msg="Missing symbolic variable while parsing dynamic block",
                                      block_name=block_name,
                                      block_uid=block_uid_value,
                                      field_name="external_mapping",
                                      missing_uid=var_uid)

        api_obj_mapping: Dict[ParamPowerFlowReferenceType, Var] = dict()
        for key_str, var_uid in data.get("api_obj_mapping", dict()).items():
            # Legacy dynamic-block records used ``fn`` for the same nominal
            # frequency contract now represented only by ``freq``.
            key: ParamPowerFlowReferenceType
            if key_str == "fn":
                key = ParamPowerFlowReferenceType.freq
            else:
                key = ParamPowerFlowReferenceType(key_str)
            if var_uid is None:
                # Older dynamic models persist optional API mappings as null.
                # The missing target is intentional and must not be presented
                # as a damaged symbolic reference in the open-file logger.
                pass
            else:
                # Non-null mapping UIDs are expected to identify a real
                # variable because dropping them can prevent static parameters
                # from reaching the dynamic model.
                api_var: Var | None = self._resolve_var_or_warn(var_uid,
                                                                block_name,
                                                                block_uid_value,
                                                                "api_obj_mapping")
                if api_var is not None:
                    api_obj_mapping[key] = api_var
                else:
                    pass

        reformulated_vars: List[Var] = list()
        for v_uid in data.get("reformulated_vars", list()):
            reformulated_var: Var | None = self._resolve_var_or_warn(v_uid,
                                                                     block_name,
                                                                     block_uid_value,
                                                                     "reformulated_vars")
            if reformulated_var is not None:
                reformulated_vars.append(reformulated_var)
            else:
                pass

        procedural_logic_data: List[ProceduralLogicData] = list()
        procedural_entry: object
        for procedural_entry in data.get("procedural_logic", list()):
            if isinstance(procedural_entry, dict):
                procedural_logic_data.append(procedural_entry)
            else:
                raise TypeError(
                    "Persisted procedural logic entry must be declarative data"
                )
        if len(procedural_logic_data) == 0:
            procedural_logic_entries: List[ProceduralLogicEntryContract[Expr]] = list()
        else:
            if self._procedural_logic_codec is None:
                raise ValueError(
                    "Persisted procedural logic requires an explicit codec"
                )
            else:
                procedural_logic_entries = list(
                    self._procedural_logic_codec.parse_entries(
                        entries=procedural_logic_data,
                        var_factory=self.var_factory,
                    )
                )

        block = Block(
            state_vars=state_vars,
            state_eqs=state_eqs,
            algebraic_vars=algebraic_vars,
            algebraic_eqs=algebraic_eqs,
            inequalities=inequalities,
            diff_vars=diff_vars,
            differential_eqs=differential_eqs,
            in_vars=in_vars,
            out_vars=out_vars,
            init_eqs=init_eqs,
            diff_init_eqs=diff_init_eqs,
            post_init_seed_eqs=post_init_seed_eqs,
            discrete_eqs=discrete_eqs,
            event_dict=event_dict,
            mode_dict=mode_dict,
            boolean_guards=boolean_guards,
            procedural_logic=procedural_logic_entries,
            children=children,  # TODO think about this
            parameters=parameters,
            init_values=init_values,
            external_mapping=external_mapping,
            api_obj_mapping=api_obj_mapping,
            reformulated_vars=reformulated_vars,
            name=block_name,
            uid=block_uid_value,
            model_family_name=model_family_name,
        )

        dynamic_model_contract_raw: object | None = data.get(
            "dynamic_model_contract",
            None,
        )
        if dynamic_model_contract_raw is None:
            pass
        else:
            if isinstance(dynamic_model_contract_raw, dict):
                normalized_contract_data: Dict[str, object] = dict()
                contract_key: object
                contract_value: object
                for contract_key, contract_value in dynamic_model_contract_raw.items():
                    if isinstance(contract_key, str):
                        normalized_contract_data[contract_key] = contract_value
                    else:
                        raise TypeError(
                            "Dynamic-model contract keys must be strings"
                        )

                override_expression_data_raw: object | None = (
                    normalized_contract_data.get(
                        "explicit_init_override_init_exprs",
                        dict(),
                    )
                )
                normalized_contract_data[
                    "explicit_init_override_init_exprs"
                ] = dict()
                parsed_contract: DynamicModelContract = (
                    dynamic_model_contract_from_data(normalized_contract_data)
                )
                if isinstance(override_expression_data_raw, dict):
                    override_name_raw: object
                    override_expression_raw: object
                    for override_name_raw, override_expression_raw in (
                            override_expression_data_raw.items()
                    ):
                        if (
                                isinstance(override_name_raw, str)
                                and isinstance(override_expression_raw, dict)
                        ):
                            parsed_contract.explicit_init_override_init_exprs[
                                override_name_raw
                            ] = parse_expr(
                                data=override_expression_raw,
                                const_dict=self.var_factory.get_const_dict(),
                                var_dict=self._var_identity_lookup,
                                diff_var_dict=self._diff_var_identity_lookup,
                                composite_expressions=composite_expressions,
                            )
                        else:
                            raise TypeError(
                                "Dynamic-model override expressions must be declarative mappings"
                            )
                else:
                    raise TypeError(
                        "Dynamic-model override expressions must be a mapping"
                    )
                block.dynamic_model_contract = parsed_contract
                validate_dynamic_model_contract(block)
            else:
                raise TypeError("Dynamic-model contract must be declarative data")

        # Children have already been parsed, so both current stable variable
        # UIDs and legacy positional port references can now be resolved.
        persisted_intent: object
        for persisted_intent in data.get("connection_intents", list()):
            if isinstance(persisted_intent, dict):
                parsed_intent: DynamicConnectionIntent | None = dynamic_connection_intent_from_dict(
                    data=persisted_intent,
                    root_block=block,
                )
                if parsed_intent is not None:
                    block.connection_intents.append(parsed_intent)
                elif is_legacy_suppressed_connection_intent_tombstone(
                        data=persisted_intent,
                        root_block=block):
                    # Older editors persisted harmless suppressed history after
                    # replacing a block. Accept it as a migration tombstone and
                    # omit it from the reconstructed current model.
                    pass
                else:
                    self._add_warning(msg="Invalid dynamic connection intent ignored while parsing persisted data",
                                      block_name=block_name,
                                      block_uid=block_uid_value,
                                      field_name="connection_intents",
                                      missing_uid=None)
            else:
                self._add_warning(msg="Invalid dynamic connection intent ignored while parsing persisted data",
                                  block_name=block_name,
                                  block_uid=block_uid_value,
                                  field_name="connection_intents",
                                  missing_uid=None)
        normalize_dynamic_connection_intents(block=block)
        normalize_event_parameter_initialization(block=block)

        diagram_data = data.get("diagram", None)
        if diagram_data is not None:
            block.diagram.parse(diagram_data)

        self.block_dict[block.uid] = block

        return block


def block_deep_copy(block: Block, var_factory: VarFactory) -> Block:
    """Duplicate one block without a serialization round trip.

    :param block: Source block.
    :param var_factory: Factory owning the duplicated symbolic variables.
    :return: Duplicated block with remapped internal identities.
    """
    return duplicate_block(block=block, var_factory=var_factory)


def duplicate_var(
        var_factory: VarFactory,
        source_non_mutable_uid_to_new_var: Dict[int, Var],
        var: Var | None,
) -> Var | None:
    """
    Duplicate one symbolic variable while preserving structural-identity reuse.

    The helper now accepts ``None`` because some FMU/EMT external mappings intentionally
    leave optional references unresolved. In those cases the missing mapping must stay
    missing after the block clone.

    :param var_factory: Variable factory used to allocate the cloned variable.
    :param source_non_mutable_uid_to_new_var: Clone map keyed by stable source identity.
    :param var: Source variable or ``None``.
    :return: Cloned variable or ``None``.
    """
    if var is None:
        new_var: Var | None = None
    else:
        source_non_mutable_uid: int = var.non_mutable_uid
        if source_non_mutable_uid in source_non_mutable_uid_to_new_var:
            new_var = source_non_mutable_uid_to_new_var[source_non_mutable_uid]
        else:
            # Shared references belong to their factory. Recreate the source
            # identity once in the destination so cloned variables never retain
            # the reference object owned by the source block or template.
            shared_reference_name: str | None
            if var.shared_ref is None:
                shared_reference_name = None
            else:
                shared_reference_name = var.shared_ref.name
                if shared_reference_name not in var_factory.get_references_dict():
                    var_factory.create_reference(
                        reference_name=shared_reference_name,
                        uid=var.shared_ref.uid,
                    )
                else:
                    pass

            if var.base_var is not None:
                base_var_new: Var = duplicate_required_var(
                    var_factory,
                    source_non_mutable_uid_to_new_var,
                    var.base_var,
                )

                # Differential variables must be linked to the cloned base variable. Passing the
                # original differential pointer here would reconnect the new chain to the source.
                new_var = var_factory.add_diff_var(
                    name=var.name,
                    reference=var.ref,
                    network_conn=var.network_conn,
                    shared_reference=shared_reference_name,
                    diff_var=None,
                    base_var=base_var_new
                )

            else:
                # Base variables are allocated without pulling their derivative pointer through.
                # The derivative clone will attach itself when it is duplicated.
                new_var = var_factory.add_var(
                    name=var.name,
                    reference=var.ref,
                    network_conn=var.network_conn,
                    shared_reference=shared_reference_name,
                )

            source_non_mutable_uid_to_new_var[source_non_mutable_uid] = new_var

    return new_var


def duplicate_var_uid(
        var_factory: VarFactory,
        source_non_mutable_uid_to_new_var: Dict[int, Var],
        var: Var | None,
) -> Var | None:
    """
    Duplicate one variable while preserving both of its symbolic identities.

    The returned object is allocated by ``var_factory`` and is independent of
    the source object. Repeated structural references reuse the same duplicate.

    :param var_factory: Private factory that owns the editor variable.
    :param source_non_mutable_uid_to_new_var: Editor variables keyed by stable identity.
    :param var: Source variable or ``None``.
    :return: Independent variable with the source UID values, or ``None``.
    """
    if var is None:
        new_var: Var | None = None
    else:
        source_non_mutable_uid: int = var.non_mutable_uid
        existing_var: Var | None = source_non_mutable_uid_to_new_var.get(
            source_non_mutable_uid,
            None,
        )
        if existing_var is not None:
            new_var = existing_var
        elif var.base_var is not None:
            duplicated_base_var: Var | None = duplicate_var_uid(
                var_factory=var_factory,
                source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
                var=var.base_var,
            )
            if duplicated_base_var is None:
                raise TypeError("duplicate_var_uid: differential base variable cannot be None")
            else:
                pass

            shared_reference_name: str | None
            if var.shared_ref is None:
                shared_reference_name = None
            else:
                shared_reference_name = var.shared_ref.name
                if shared_reference_name is not None:
                    if shared_reference_name not in var_factory.get_references_dict():
                        var_factory.create_reference(
                            reference_name=shared_reference_name,
                            uid=var.shared_ref.uid,
                        )
                    else:
                        pass
            new_var = var_factory.add_diff_var(
                name=var.name,
                reference=var.ref,
                network_conn=var.network_conn,
                shared_reference=shared_reference_name,
                non_mutable_uid=var.non_mutable_uid,
                uid=var.uid,
                diff_var=None,
                base_var=duplicated_base_var,
            )
            source_non_mutable_uid_to_new_var[source_non_mutable_uid] = new_var
        else:
            if var.shared_ref is None:
                shared_reference_name = None
            else:
                shared_reference_name = var.shared_ref.name
                if shared_reference_name not in var_factory.get_references_dict():
                    var_factory.create_reference(
                        reference_name=shared_reference_name,
                        uid=var.shared_ref.uid,
                    )
                else:
                    pass
            new_var = var_factory.add_var(
                name=var.name,
                reference=var.ref,
                network_conn=var.network_conn,
                shared_reference=shared_reference_name,
                non_mutable_uid=var.non_mutable_uid,
                uid=var.uid,
            )
            source_non_mutable_uid_to_new_var[source_non_mutable_uid] = new_var

    return new_var


def duplicate_required_var(
        var_factory: VarFactory,
        source_non_mutable_uid_to_new_var: Dict[int, Var],
        var: Var,
) -> Var:
    """
    Duplicate a variable that must exist in the source block structure.

    :param var_factory: Variable factory used to allocate the cloned variable.
    :param source_non_mutable_uid_to_new_var: Clone map keyed by stable source identity.
    :param var: Source variable.
    :return: Cloned variable.
    """
    new_var: Var | None = duplicate_var(
        var_factory,
        source_non_mutable_uid_to_new_var,
        var,
    )
    if new_var is None:
        raise TypeError("duplicate_required_var: source variable cannot be None")
    else:
        return new_var


def duplicate_const(var_factory: VarFactory,
                    old_to_new_const: Dict[int, Const],
                    const: Const) -> Const:
    """

    :param var_factory:
    :param old_to_new_const:
    :param const:
    :return:
    """
    if const.uid in old_to_new_const:
        return old_to_new_const[const.uid]

    new_const = var_factory.add_const(value=const.value, name=const.name)
    old_to_new_const[const.uid] = new_const
    return new_const


def duplicate_const_uid(var_factory: VarFactory,
                        source_uid_to_new_const: Dict[int, Const],
                        const: Const) -> Const:
    """
    Duplicate one constant while preserving its symbolic UID.

    :param var_factory: Private factory that owns the editor constant.
    :param source_uid_to_new_const: Editor constants keyed by source UID.
    :param const: Source constant.
    :return: Independent constant carrying the source UID.
    """
    existing_const: Const | None = source_uid_to_new_const.get(const.uid, None)
    if existing_const is not None:
        new_const: Const = existing_const
    else:
        new_const = var_factory.add_const(
            value=const.value,
            uid=const.uid,
            name=const.name,
        )
        source_uid_to_new_const[const.uid] = new_const
    return new_const


def duplicate_expr(var_factory: VarFactory,
                   old_to_new_const: Dict[int, Const],
                   source_non_mutable_uid_to_new_var: Dict[int, Var],
                   expr: Expr) -> Expr:
    """

    :param var_factory:
    :param old_to_new_const:
    :param source_non_mutable_uid_to_new_var: Clone map keyed by stable source identity.
    :param expr:
    :return:
    """
    if isinstance(expr, Var):
        return duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, expr)
    if isinstance(expr, Const):
        return duplicate_const(var_factory, old_to_new_const, expr)
    if isinstance(expr, BinOp):
        return BinOp(
            duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, expr.left),
            expr.op,
            duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, expr.right)
        )
    if isinstance(expr, UnOp):
        return UnOp(
            expr.op,
            duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, expr.operand),
        )
    if isinstance(expr, Func):
        return Func(
            duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, expr.arg),
            expr.op,
        )
    if isinstance(expr, Func2):
        return Func2(expr.name,
                     duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, expr.arg1),
                     duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, expr.arg2))
    return expr


def duplicate_condition(
        var_factory: VarFactory,
        old_to_new_const: Dict[int, Const],
        source_non_mutable_uid_to_new_var: Dict[int, Var],
        condition: Expr | Comparison,
) -> Expr | Comparison:
    """Duplicate one expression or symbolic comparison.

    :param var_factory: Variable factory used to allocate owned symbols.
    :param old_to_new_const: Source-to-duplicate constant mapping.
    :param source_non_mutable_uid_to_new_var: Clone map keyed by stable source identity.
    :param condition: Expression or comparison to duplicate.
    :return: Condition rebuilt against the resolved symbolic mapping.
    """
    if isinstance(condition, Comparison):
        source_rhs: Expr | int | float | complex = condition.rhs
        if isinstance(source_rhs, Expr):
            target_rhs: Expr | int | float | complex = duplicate_expr(
                var_factory,
                old_to_new_const,
                source_non_mutable_uid_to_new_var,
                source_rhs,
            )
        else:
            target_rhs = source_rhs

        return Comparison(
            lhs=duplicate_expr(
                var_factory,
                old_to_new_const,
                source_non_mutable_uid_to_new_var,
                condition.lhs,
            ),
            op=condition.op,
            rhs=target_rhs,
        )
    else:
        return duplicate_expr(
            var_factory,
            old_to_new_const,
            source_non_mutable_uid_to_new_var,
            condition,
        )


def _remember_var(var: Var | None, vars_by_non_mutable_uid: Dict[int, Var]) -> None:
    """
    Collect one variable and its derivative chain by stable structural identity.

    :param var: Variable to collect, or ``None`` for optional mappings.
    :param vars_by_non_mutable_uid: Accumulator keyed by source stable identity.
    :return: Nothing.
    """
    if var is None:
        pass
    else:
        if var.non_mutable_uid in vars_by_non_mutable_uid:
            pass
        else:
            vars_by_non_mutable_uid[var.non_mutable_uid] = var
            _remember_var(var.base_var, vars_by_non_mutable_uid)
            _remember_var(var.diff_var, vars_by_non_mutable_uid)


def _remember_expr_vars(expr: Expr, vars_by_non_mutable_uid: Dict[int, Var]) -> None:
    """
    Collect variables referenced by one expression.

    :param expr: Expression to scan.
    :param vars_by_non_mutable_uid: Accumulator keyed by source stable identity.
    :return: Nothing.
    """
    var: Var
    for var in expr.get_vars():
        _remember_var(var, vars_by_non_mutable_uid)


def _remember_condition_vars(
        condition: Expr | Comparison,
        vars_by_non_mutable_uid: Dict[int, Var],
) -> None:
    """Collect variables referenced by an expression or comparison.

    :param condition: Symbolic expression or comparison to scan.
    :param vars_by_non_mutable_uid: Accumulator keyed by source stable identity.
    :return: None.
    """
    if isinstance(condition, Comparison):
        _remember_expr_vars(condition.lhs, vars_by_non_mutable_uid)
        if isinstance(condition.rhs, Expr):
            _remember_expr_vars(condition.rhs, vars_by_non_mutable_uid)
        else:
            pass
    else:
        _remember_expr_vars(condition, vars_by_non_mutable_uid)


def _collect_block_vars_by_non_mutable_uid(
        block: Block,
        vars_by_non_mutable_uid: Dict[int, Var] | None = None,
) -> Dict[int, Var]:
    """
    Collect all variables reachable from a block, including expression-only references.

    :param block: Block to scan.
    :param vars_by_non_mutable_uid: Optional accumulator for recursive child scans.
    :return: Variables keyed by source stable identity.
    """
    if vars_by_non_mutable_uid is None:
        result: Dict[int, Var] = dict()
    else:
        result = vars_by_non_mutable_uid

    for var_list in (
            block.state_vars,
            block.algebraic_vars,
            block.diff_vars,
            block.reformulated_vars,
            block.in_vars,
            block.out_vars,
    ):
        var: Var
        for var in var_list:
            _remember_var(var, result)

    for mapping in (
            block.parameters,
            block.init_values,
            block.init_eqs,
            block.diff_init_eqs,
            block.post_init_seed_eqs,
            block.discrete_eqs,
            block.event_dict,
            block.mode_dict,
            block.boolean_guards,
    ):
        mapping_key: Var
        mapping_value: Expr | Comparison
        for mapping_key, mapping_value in mapping.items():
            _remember_var(mapping_key, result)
            _remember_condition_vars(mapping_value, result)

    external_var: Var | None
    for external_var in block.external_mapping.values():
        _remember_var(external_var, result)

    api_var: Var | None
    for api_var in block.api_obj_mapping.values():
        _remember_var(api_var, result)

    for expr_list in (
            block.state_eqs,
            block.algebraic_eqs,
            block.differential_eqs,
            block.inequalities,
    ):
        condition: Expr | Comparison
        for condition in expr_list:
            _remember_condition_vars(condition, result)

    child: Block
    for child in block.children:
        _collect_block_vars_by_non_mutable_uid(child, result)

    return result


def _collect_owned_block_vars_by_non_mutable_uid(
        block: Block,
        vars_by_non_mutable_uid: Dict[int, Var] | None = None,
) -> Dict[int, Var]:
    """Collect variables structurally owned by one complete block tree.

    Variables appearing only inside expressions are external references and
    deliberately remain outside this ownership set.

    :param block: Block tree whose owned variables are required.
    :param vars_by_non_mutable_uid: Optional accumulator for recursive child scans.
    :return: Structurally owned variables keyed by source stable identity.
    """
    if vars_by_non_mutable_uid is None:
        result: Dict[int, Var] = dict()
    else:
        result = vars_by_non_mutable_uid

    var_list: List[Var]
    for var_list in (
            block.state_vars,
            block.algebraic_vars,
            block.diff_vars,
            block.reformulated_vars,
            block.in_vars,
            block.out_vars,
    ):
        owned_var: Var
        for owned_var in var_list:
            _remember_var(owned_var, result)

    owned_mapping: Mapping[Var, object]
    for owned_mapping in (
            block.parameters,
            block.init_values,
            block.init_eqs,
            block.diff_init_eqs,
            block.post_init_seed_eqs,
            block.discrete_eqs,
            block.event_dict,
            block.mode_dict,
            block.boolean_guards,
    ):
        owned_key: Var
        for owned_key in owned_mapping.keys():
            _remember_var(owned_key, result)

    mapped_var: Var | None
    for mapped_var in block.external_mapping.values():
        _remember_var(mapped_var, result)
    for mapped_var in block.api_obj_mapping.values():
        _remember_var(mapped_var, result)

    child: Block
    for child in block.children:
        _collect_owned_block_vars_by_non_mutable_uid(child, result)

    return result


def _build_var_mapping(
        source_vars_by_non_mutable_uid: Dict[int, Var],
        source_non_mutable_uid_to_new_var: Dict[int, Var],
) -> Dict[Expr | str, Expr]:
    """
    Build the object/name substitution map used by procedural logic cloning.

    :param source_vars_by_non_mutable_uid: Source variables keyed by stable identity.
    :param source_non_mutable_uid_to_new_var: Cloned variables keyed by source stable identity.
    :return: Procedural logic variable substitution map.
    """
    mapping: Dict[Expr | str, Expr] = dict()
    source_non_mutable_uid: int
    source_var: Var
    for source_non_mutable_uid, source_var in source_vars_by_non_mutable_uid.items():
        new_var: Var | None = source_non_mutable_uid_to_new_var.get(source_non_mutable_uid, None)
        if new_var is not None:
            mapping[source_var] = new_var
            mapping[source_var.name] = new_var
        else:
            pass
    return mapping


def _find_source_var_by_uid(
        source_uid: int,
        source_vars_by_non_mutable_uid: Dict[int, Var],
) -> Var | None:
    """Find the first structural source variable carrying one effective UID.

    Dynamic-model contracts persist effective UIDs, while block duplication is
    keyed by stable identities. Resolve the source object first so the clone
    lookup never reuses the mutable UID as a structural key.

    :param source_uid: Effective UID persisted by the source contract.
    :param source_vars_by_non_mutable_uid: Source variables keyed by stable identity.
    :return: Matching source variable, or ``None`` when the contract is stale.
    """
    result: Var | None = None
    source_var: Var
    for source_var in source_vars_by_non_mutable_uid.values():
        if result is None and source_var.uid == source_uid:
            result = source_var
        else:
            pass
    return result


def _remap_optional_duplicate_uid(
        source_uid: int | None,
        source_vars_by_non_mutable_uid: Dict[int, Var],
        source_non_mutable_uid_to_new_var: Dict[int, Var],
) -> int | None:
    """Translate one optional source UID into a duplicated block tree.

    :param source_uid: Source variable UID or ``None``.
    :param source_vars_by_non_mutable_uid: Source variables keyed by stable identity.
    :param source_non_mutable_uid_to_new_var: Cloned variables keyed by source stable identity.
    :return: Duplicated variable UID or ``None`` when not declared.
    """
    if source_uid is None:
        return None
    else:
        source_var: Var | None = _find_source_var_by_uid(
            source_uid=source_uid,
            source_vars_by_non_mutable_uid=source_vars_by_non_mutable_uid,
        )
        if source_var is None:
            raise KeyError(
                f"Dynamic-model contract UID '{source_uid}' was not duplicated"
            )
        else:
            mapped_var: Var | None = source_non_mutable_uid_to_new_var.get(
                source_var.non_mutable_uid,
                None,
            )
            if mapped_var is None:
                raise KeyError(
                    f"Dynamic-model contract UID '{source_uid}' was not duplicated"
                )
            else:
                return mapped_var.uid


def _remap_duplicate_uids(
        source_uids: Iterable[int],
        source_vars_by_non_mutable_uid: Dict[int, Var],
        source_non_mutable_uid_to_new_var: Dict[int, Var],
) -> List[int]:
    """Translate every required contract UID into a duplicated block tree.

    :param source_uids: Required source variable UIDs.
    :param source_vars_by_non_mutable_uid: Source variables keyed by stable identity.
    :param source_non_mutable_uid_to_new_var: Cloned variables keyed by source stable identity.
    :return: Duplicated variable UIDs in source order.
    """
    result: List[int] = list()
    source_uid: int
    for source_uid in source_uids:
        mapped_uid: int | None = _remap_optional_duplicate_uid(
            source_uid=source_uid,
            source_vars_by_non_mutable_uid=source_vars_by_non_mutable_uid,
            source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
        )
        if mapped_uid is None:
            raise KeyError(
                f"Dynamic-model contract UID '{source_uid}' was not duplicated"
            )
        else:
            result.append(mapped_uid)
    return result


def _duplicate_block(block: Block,
                     var_factory: VarFactory,
                     source_non_mutable_uid_to_new_var: Dict[int, Var],
                     old_to_new_const: Dict[int, Const],
                     old_to_new_block_uid: Dict[int, int]) -> Block:
    """
    Duplicate a block using shared maps so child/parent variable links remain coherent.

    :param block: Source block.
    :param var_factory: Variable factory used to allocate cloned variables and constants.
    :param source_non_mutable_uid_to_new_var: Clone map keyed by stable source identity.
    :param old_to_new_const: UID-to-constant clone map shared across the block tree.
    :param old_to_new_block_uid: Source-to-clone block UID map shared across the block tree.
    :return: Duplicated block.
    """
    source_vars_by_non_mutable_uid: Dict[int, Var] = _collect_block_vars_by_non_mutable_uid(block)
    owned_vars_by_non_mutable_uid: Dict[int, Var] = _collect_owned_block_vars_by_non_mutable_uid(block)

    source_non_mutable_uid: int
    source_var: Var
    for source_non_mutable_uid, source_var in source_vars_by_non_mutable_uid.items():
        if source_non_mutable_uid in owned_vars_by_non_mutable_uid:
            pass
        else:
            existing_var: Var | None = source_non_mutable_uid_to_new_var.get(source_non_mutable_uid, None)
            if existing_var is None:
                source_non_mutable_uid_to_new_var[source_non_mutable_uid] = source_var
            else:
                # A variable already resolved by its owning parent or sibling
                # must remain canonical throughout the recursive duplication.
                pass

    for source_var in owned_vars_by_non_mutable_uid.values():
        duplicate_var(var_factory, source_non_mutable_uid_to_new_var, source_var)

    const: Const
    for const in block.parameters.values():
        duplicate_const(var_factory, old_to_new_const, const)

    for const in block.init_values.values():
        duplicate_const(var_factory, old_to_new_const, const)

    # Clone the variable containers from the shared stable-identity map so every repeated
    # reference inside the source block points to the same cloned object.
    new_state_vars: List[Var] = [
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, v)
        for v in block.state_vars
    ]
    new_algebraic_vars: List[Var] = [
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, v)
        for v in block.algebraic_vars
    ]
    new_diff_vars: List[Var] = [
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, v)
        for v in block.diff_vars
    ]
    new_reformulated_vars: List[Var] = [
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, v)
        for v in block.reformulated_vars
    ]
    new_in_vars: List[Var] = [
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, v)
        for v in block.in_vars
    ]
    new_out_vars: List[Var] = [
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, v)
        for v in block.out_vars
    ]

    # Clone equations after all variables are known, otherwise expression-only
    # variables could accidentally diverge from the block variable containers.
    new_state_eqs: List[Expr] = [
        duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, e)
        for e in block.state_eqs
    ]
    new_algebraic_eqs: List[Expr] = [
        duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, e)
        for e in block.algebraic_eqs
    ]
    new_differential_eqs: List[Expr] = [
        duplicate_expr(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, e)
        for e in block.differential_eqs
    ]
    new_inequalities: List[Expr | Comparison] = [
        duplicate_condition(var_factory, old_to_new_const, source_non_mutable_uid_to_new_var, e)
        for e in block.inequalities
    ]

    new_init_eqs: Dict[Var, Expr] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_expr(
            var_factory,
            old_to_new_const,
            source_non_mutable_uid_to_new_var,
            v,
        )
        for k, v in block.init_eqs.items()
    }

    new_diff_init_eqs: Dict[Var, Expr] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_expr(
            var_factory,
            old_to_new_const,
            source_non_mutable_uid_to_new_var,
            v,
        )
        for k, v in block.diff_init_eqs.items()
    }

    new_post_init_seed_eqs: Dict[Var, Expr | Const] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_expr(
            var_factory,
            old_to_new_const,
            source_non_mutable_uid_to_new_var,
            v,
        )
        for k, v in block.post_init_seed_eqs.items()
    }

    new_discrete_eqs: Dict[Var, Expr] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_expr(
            var_factory,
            old_to_new_const,
            source_non_mutable_uid_to_new_var,
            v,
        )
        for k, v in block.discrete_eqs.items()
    }

    new_event_dict: Dict[Var, Expr] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_expr(
            var_factory,
            old_to_new_const,
            source_non_mutable_uid_to_new_var,
            v,
        )
        for k, v in block.event_dict.items()
    }

    new_mode_dict: Dict[Var, Expr] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_expr(
            var_factory,
            old_to_new_const,
            source_non_mutable_uid_to_new_var,
            v,
        )
        for k, v in block.mode_dict.items()
    }

    new_boolean_guards: Dict[Var, Expr | Comparison] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_condition(
            var_factory,
            old_to_new_const,
            source_non_mutable_uid_to_new_var,
            v,
        )
        for k, v in block.boolean_guards.items()
    }

    new_parameters: Dict[Var, Const] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_const(
            var_factory,
            old_to_new_const,
            v,
        )
        for k, v in block.parameters.items()
    }

    new_init_values: Dict[Var, Const] = {
        duplicate_required_var(var_factory, source_non_mutable_uid_to_new_var, k): duplicate_const(
            var_factory,
            old_to_new_const,
            v,
        )
        for k, v in block.init_values.items()
    }

    new_external_mapping: Dict[VarPowerFlowReferenceType, Var | None] = {
        k: duplicate_var(var_factory, source_non_mutable_uid_to_new_var, v)
        for k, v in block.external_mapping.items()
    }
    new_api_obj_mapping: Dict[ParamPowerFlowReferenceType, Var | None] = {
        k: duplicate_var(var_factory, source_non_mutable_uid_to_new_var, v)
        for k, v in block.api_obj_mapping.items()
    }

    new_children: List[Block] = [
        _duplicate_block(
            child,
            var_factory,
            source_non_mutable_uid_to_new_var,
            old_to_new_const,
            old_to_new_block_uid,
        )
        for child in block.children
    ]

    if block.procedural_logic:
        procedural_var_mapping: Dict[Expr | str, Expr] = _build_var_mapping(
            source_vars_by_non_mutable_uid,
            source_non_mutable_uid_to_new_var,
        )
        new_procedural_logic: List[ProceduralLogicEntryContract[Expr]] = list(
            entry.remap_with_structural_vars(
                var_mapping=procedural_var_mapping,
                structural_var_mapping=source_non_mutable_uid_to_new_var,
            )
            for entry in block.procedural_logic
        )
    else:
        new_procedural_logic = list()

    new_block: Block = Block(
        state_vars=new_state_vars,
        state_eqs=new_state_eqs,
        algebraic_vars=new_algebraic_vars,
        algebraic_eqs=new_algebraic_eqs,
        inequalities=new_inequalities,
        diff_vars=new_diff_vars,
        reformulated_vars=new_reformulated_vars,
        differential_eqs=new_differential_eqs,
        parameters=new_parameters,
        init_values=new_init_values,
        init_eqs=new_init_eqs,
        diff_init_eqs=new_diff_init_eqs,
        post_init_seed_eqs=new_post_init_seed_eqs,
        discrete_eqs=new_discrete_eqs,
        children=new_children,
        in_vars=new_in_vars,
        out_vars=new_out_vars,
        event_dict=new_event_dict,
        mode_dict=new_mode_dict,
        boolean_guards=new_boolean_guards,
        procedural_logic=new_procedural_logic,
        external_mapping=new_external_mapping,
        api_obj_mapping=new_api_obj_mapping,
        name=block.name,
        model_family_name=block.model_family_name,
    )

    # Intent targets use stable block and variable identities. Rebuild both
    # identities after the complete cloned child subtree has been allocated.
    old_to_new_block_uid[block.uid] = new_block.uid
    source_intent: DynamicConnectionIntent
    source_internal_block: Block | None
    source_internal_var: Var | None
    source_candidate_block: Block
    source_candidate_var: Var
    source_variables: List[Var]
    cloned_internal_block_uid: int | None
    cloned_internal_var: Var | None

    for source_intent in block.connection_intents:
        source_internal_block = None
        for source_candidate_block in block.get_all_blocks():
            if source_candidate_block.uid == source_intent.get_internal_block_uid():
                source_internal_block = source_candidate_block
            else:
                pass

        source_internal_var = None
        if source_internal_block is None:
            source_variables = list()
        elif source_intent.get_direction() == DynamicConnectionIntentDirection.INPUT:
            source_variables = source_internal_block.in_vars
        else:
            source_variables = source_internal_block.out_vars

        for source_candidate_var in source_variables:
            if source_candidate_var.non_mutable_uid == source_intent.get_internal_variable_uid():
                source_internal_var = source_candidate_var
            else:
                pass

        cloned_internal_block_uid = old_to_new_block_uid.get(source_intent.get_internal_block_uid(), None)
        if source_internal_var is None:
            cloned_internal_var = None
        else:
            cloned_internal_var = source_non_mutable_uid_to_new_var.get(
                source_internal_var.non_mutable_uid,
                None,
            )

        if cloned_internal_block_uid is None or cloned_internal_var is None:
            pass
        else:
            new_block.connection_intents.append(DynamicConnectionIntent(
                origin=source_intent.get_origin(),
                root_reference=source_intent.get_root_reference(),
                direction=source_intent.get_direction(),
                internal_block_uid=cloned_internal_block_uid,
                internal_variable_uid=cloned_internal_var.non_mutable_uid,
                suppressed=source_intent.is_suppressed(),
            ))

    normalize_dynamic_connection_intents(block=new_block)
    normalize_event_parameter_initialization(block=new_block)

    # Runtime identity is part of the declared Block contract. Copy every
    # scalar declaration explicitly, then translate symbolic UIDs through the
    # same map that owns the duplicated variables and expressions.
    new_block.dynamic_model_contract = copy.deepcopy(
        block.dynamic_model_contract
    )
    source_contract: DynamicModelContract = block.dynamic_model_contract
    target_contract: DynamicModelContract = new_block.dynamic_model_contract

    target_contract.dgs_elmsym_rotor_angle_var_uid = _remap_optional_duplicate_uid(
        source_contract.dgs_elmsym_rotor_angle_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.dgs_elmsym_speed_var_uid = _remap_optional_duplicate_uid(
        source_contract.dgs_elmsym_speed_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.dgs_elmsym_angular_frequency_var_uid = _remap_optional_duplicate_uid(
        source_contract.dgs_elmsym_angular_frequency_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.dgs_elmsym_rated_field_voltage_var_uid = _remap_optional_duplicate_uid(
        source_contract.dgs_elmsym_rated_field_voltage_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.dgs_elmsym_excitation_gain_var_uid = _remap_optional_duplicate_uid(
        source_contract.dgs_elmsym_excitation_gain_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.dgs_elmsym_active_base_factor_var_uid = _remap_optional_duplicate_uid(
        source_contract.dgs_elmsym_active_base_factor_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.dgs_elmsym_reference_speed_var_uid = _remap_optional_duplicate_uid(
        source_contract.dgs_elmsym_reference_speed_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.rms_conduction_status_var_uid = _remap_optional_duplicate_uid(
        source_contract.rms_conduction_status_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.rms_topology_constraint_status_var_uid = _remap_optional_duplicate_uid(
        source_contract.rms_topology_constraint_status_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )
    target_contract.dgs_elmsvs_remote_voltage_var_uid = _remap_optional_duplicate_uid(
        source_contract.dgs_elmsvs_remote_voltage_var_uid,
        source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var,
    )

    target_contract.dgs_explicit_initialization_uids = set(
        _remap_duplicate_uids(
            source_uids=source_contract.dgs_explicit_initialization_uids,
            source_vars_by_non_mutable_uid=source_vars_by_non_mutable_uid,
            source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
        )
    )
    target_contract.runtime_equipment_shell_sync_var_uids = _remap_duplicate_uids(
        source_uids=source_contract.runtime_equipment_shell_sync_var_uids,
        source_vars_by_non_mutable_uid=source_vars_by_non_mutable_uid,
        source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
    )
    source_measurement_point: RmsPhysicalMeasurementPoint | None = (
        source_contract.rms_physical_measurement_point
    )
    if source_measurement_point is None:
        target_contract.rms_physical_measurement_point = None
    else:
        remapped_measurement_uids: List[int] = _remap_duplicate_uids(
            source_uids=source_measurement_point.get_output_var_uids(),
            source_vars_by_non_mutable_uid=source_vars_by_non_mutable_uid,
            source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
        )
        target_contract.rms_physical_measurement_point = (
            RmsPhysicalMeasurementPoint(
                source_fid=source_measurement_point.get_source_fid(),
                target_fid=source_measurement_point.get_target_fid(),
                terminal_side=source_measurement_point.get_terminal_side(),
                meter_kind=source_measurement_point.get_meter_kind(),
                output_signal_names=(
                    source_measurement_point.get_output_signal_names()
                ),
                output_var_uids=tuple(remapped_measurement_uids),
            )
        )
    target_contract.explicit_init_override_init_exprs = dict(
        (
            variable_name,
            duplicate_expr(
                var_factory,
                old_to_new_const,
                source_non_mutable_uid_to_new_var,
                source_expression,
            ),
        )
        for variable_name, source_expression
        in source_contract.explicit_init_override_init_exprs.items()
    )

    return new_block


def _copy_editor_block_identity(
        source_block: Block,
        duplicated_block: Block,
        source_non_mutable_uid_to_new_var: Dict[int, Var],
) -> None:
    """
    Restore persistent block metadata on one editor duplicate tree.

    ``_duplicate_block`` intentionally allocates new block identities for model
    instantiation. Editor copies instead represent the same persistent document,
    so block identifiers, diagrams and non-symbolic configuration stay stable.

    :param source_block: Persistent block being copied.
    :param duplicated_block: Independent editor block receiving stable metadata.
    :param source_non_mutable_uid_to_new_var: Editor variables keyed by stable identity.
    :return: None.
    """
    source_child: Block
    duplicated_child: Block
    mapped_var: Var

    duplicated_block.uid = source_block.uid
    duplicated_block.is_decomposable = source_block.is_decomposable
    duplicated_block.tpe_uid = source_block.tpe_uid
    duplicated_block.vars_glob_name2uid = copy.deepcopy(source_block.vars_glob_name2uid)
    duplicated_block.connection_intents = copy.deepcopy(source_block.connection_intents)
    duplicated_block.diagram = copy.deepcopy(source_block.diagram)
    duplicated_block.dynamic_model_contract = copy.deepcopy(source_block.dynamic_model_contract)
    duplicated_block._modal_template_kind = copy.deepcopy(source_block._modal_template_kind)
    duplicated_block._modal_template_config = copy.deepcopy(source_block._modal_template_config)
    duplicated_block._jmarti_fit_bundle = copy.deepcopy(source_block._jmarti_fit_bundle)
    duplicated_block._jmarti_runtime_data = copy.deepcopy(source_block._jmarti_runtime_data)

    # Preserve every explicit textual lookup while redirecting its values to
    # variables owned by the private editor factory.
    duplicated_block.var_mapping = dict()
    for variable_name, source_var in source_block.var_mapping.items():
        mapped_var = source_non_mutable_uid_to_new_var[source_var.non_mutable_uid]
        duplicated_block.var_mapping[variable_name] = mapped_var

    if len(source_block.children) != len(duplicated_block.children):
        raise ValueError("Editor block duplication changed the child count")
    else:
        pass

    for source_child, duplicated_child in zip(source_block.children, duplicated_block.children):
        _copy_editor_block_identity(
            source_block=source_child,
            duplicated_block=duplicated_child,
            source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
        )


def _remember_expression_consts(expr: Expr | Comparison,
                                consts_by_uid: Dict[int, Const]) -> None:
    """
    Collect constants reachable from one symbolic expression tree.

    :param expr: Expression or comparison to inspect.
    :param consts_by_uid: Constant accumulator keyed by symbolic UID.
    :return: None.
    """
    if isinstance(expr, Const):
        consts_by_uid[expr.uid] = expr
    elif isinstance(expr, BinOp):
        _remember_expression_consts(expr.left, consts_by_uid)
        _remember_expression_consts(expr.right, consts_by_uid)
    elif isinstance(expr, UnOp):
        _remember_expression_consts(expr.operand, consts_by_uid)
    elif isinstance(expr, Func):
        _remember_expression_consts(expr.arg, consts_by_uid)
    elif isinstance(expr, Func2):
        _remember_expression_consts(expr.arg1, consts_by_uid)
        _remember_expression_consts(expr.arg2, consts_by_uid)
    elif isinstance(expr, Comparison):
        _remember_expression_consts(expr.lhs, consts_by_uid)
        if isinstance(expr.rhs, Expr):
            _remember_expression_consts(expr.rhs, consts_by_uid)
        else:
            pass
    else:
        pass


def _collect_block_consts_by_uid(block: Block) -> Dict[int, Const]:
    """
    Collect every symbolic constant owned by one recursive block tree.

    :param block: Root block to inspect.
    :return: Constants keyed by their source UID.
    """
    consts_by_uid: Dict[int, Const] = dict()
    current_block: Block
    expression_groups: tuple[List[Expr], ...]
    expression_group: List[Expr]
    expression: Expr
    condition: Expr | Comparison
    mapped_expression: Expr | Const
    source_const: Const

    for current_block in block.get_all_blocks():
        for source_const in current_block.parameters.values():
            consts_by_uid[source_const.uid] = source_const
        for source_const in current_block.init_values.values():
            consts_by_uid[source_const.uid] = source_const

        expression_groups = (
            current_block.state_eqs,
            current_block.algebraic_eqs,
            current_block.differential_eqs,
        )
        for expression_group in expression_groups:
            for expression in expression_group:
                _remember_expression_consts(expression, consts_by_uid)

        for condition in current_block.inequalities:
            _remember_expression_consts(condition, consts_by_uid)
        for mapped_expression in current_block.init_eqs.values():
            _remember_expression_consts(mapped_expression, consts_by_uid)
        for mapped_expression in current_block.diff_init_eqs.values():
            _remember_expression_consts(mapped_expression, consts_by_uid)
        for mapped_expression in current_block.post_init_seed_eqs.values():
            _remember_expression_consts(mapped_expression, consts_by_uid)
        for mapped_expression in current_block.discrete_eqs.values():
            _remember_expression_consts(mapped_expression, consts_by_uid)
        for mapped_expression in current_block.event_dict.values():
            _remember_expression_consts(mapped_expression, consts_by_uid)
        for mapped_expression in current_block.mode_dict.values():
            _remember_expression_consts(mapped_expression, consts_by_uid)
        for condition in current_block.boolean_guards.values():
            _remember_expression_consts(condition, consts_by_uid)
        for expression in current_block.dynamic_model_contract.explicit_init_override_init_exprs.values():
            _remember_expression_consts(expression, consts_by_uid)

    return consts_by_uid


def _duplicate_block_uid(
        block: Block,
        var_factory: VarFactory,
        source_non_mutable_uid_to_new_var: Dict[int, Var],
) -> Block:
    """
    Duplicate one block tree with variables preallocated under source identities.

    :param block: Persistent source block.
    :param var_factory: Private editor factory owning every duplicated variable.
    :param source_non_mutable_uid_to_new_var: Editor variables keyed by stable identity.
    :return: Independent editor block preserving persistent identifiers.
    """
    source_vars_by_non_mutable_uid: Dict[int, Var] = _collect_block_vars_by_non_mutable_uid(block)
    source_consts_by_uid: Dict[int, Const] = _collect_block_consts_by_uid(block)
    source_uid_to_new_const: Dict[int, Const] = dict()
    source_var: Var
    source_const: Const

    # Preallocate every variable through the private factory. Once this map is
    # complete, the established structural duplicator rebuilds all expressions
    # and containers without ever falling back to a source-tree Var object.
    for source_var in source_vars_by_non_mutable_uid.values():
        duplicate_var_uid(
            var_factory=var_factory,
            source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
            var=source_var,
        )

    for source_const in source_consts_by_uid.values():
        duplicate_const_uid(
            var_factory=var_factory,
            source_uid_to_new_const=source_uid_to_new_const,
            const=source_const,
        )

    duplicated_block: Block = _duplicate_block(
        block=block,
        var_factory=var_factory,
        source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
        old_to_new_const=source_uid_to_new_const,
        old_to_new_block_uid=dict(),
    )
    _copy_editor_block_identity(
        source_block=block,
        duplicated_block=duplicated_block,
        source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
    )
    return duplicated_block


def duplicate_block(block: Block, var_factory: VarFactory | None) -> Block:
    """
    Create a duplicate of this block with new variable UIDs.

    The new block contains variables with the same names but different UIDs,
    and equations rebuilt using those new variables.

    :param block: Source block.
    :param var_factory: Variable factory used to allocate cloned variables and constants.
    :return: A new Block with duplicated variables and equations.
    """
    if var_factory is None:
        raise TypeError("duplicate_block: var_factory cannot be None")
    else:
        # Freeze the existing connection graph before allocating cloned variables.
        # Reconnecting the duplicated variables modifies this same registry, so the
        # traversal must use an immutable view of the original directed edges.
        original_connections: List[tuple[int, int]] = list()
        incoming_non_mutable_uid: int
        connections: List[Connection]
        connection: Connection
        for incoming_non_mutable_uid, connections in var_factory.get_connections_dict().items():
            for connection in connections:
                original_connections.append((
                    incoming_non_mutable_uid,
                    connection.non_mutable_uid,
                ))

        # Only structurally owned variables have a real homologue in the new block.
        # Expression-only external references can occur in the shared duplication map,
        # but must never cause a clone to reconnect to an object from the source model.
        owned_source_vars: Dict[int, Var] = _collect_owned_block_vars_by_non_mutable_uid(block)

        # Every child owns an independent typed contract. Validate each local
        # owner before cloning so an invalid descendant cannot be hidden by a
        # structurally valid root contract.
        source_block: Block
        for source_block in block.get_all_blocks():
            validate_dynamic_model_contract(source_block)
        else:
            pass

        source_non_mutable_uid_to_new_var: Dict[int, Var] = dict()
        duplicated_block: Block = _duplicate_block(
            block=block,
            var_factory=var_factory,
            source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
            old_to_new_const=dict(),
            old_to_new_block_uid=dict(),
        )

        # Restore every connection whose source and substituted target both belong
        # to the duplicated tree. The registry key is the incoming variable that
        # remains intact; each Connection identifies the variable whose UID changes.
        substituted_non_mutable_uid: int
        cloned_incoming_var: Var | None
        cloned_var_to_substitute: Var | None
        for incoming_non_mutable_uid, substituted_non_mutable_uid in original_connections:
            if (incoming_non_mutable_uid in owned_source_vars
                    and substituted_non_mutable_uid in owned_source_vars):
                cloned_incoming_var = source_non_mutable_uid_to_new_var.get(
                    incoming_non_mutable_uid,
                    None,
                )
                cloned_var_to_substitute = source_non_mutable_uid_to_new_var.get(
                    substituted_non_mutable_uid,
                    None,
                )
                if cloned_incoming_var is not None and cloned_var_to_substitute is not None:
                    if cloned_incoming_var.network_conn:
                        var_factory.add_network_connection(
                            var_to_subs=cloned_var_to_substitute,
                            incoming_var=cloned_incoming_var,
                        )
                    else:
                        var_factory.add_connection(
                            var_to_subs=cloned_var_to_substitute,
                            incoming_var=cloned_incoming_var,
                        )
                else:
                    pass
            else:
                pass

        # Remapped declarations must remain local to the duplicated owner;
        # checking the root alone would not inspect meter children.
        duplicated_candidate: Block
        for duplicated_candidate in duplicated_block.get_all_blocks():
            validate_dynamic_model_contract(duplicated_candidate)
        else:
            pass
        return duplicated_block


def duplicate_block_across_factories(
        block: Block,
        source_var_factory: VarFactory,
        target_var_factory: VarFactory,
) -> Block:
    """Create a new block instance in a different variable factory.

    Variables, constants, shared references, and connection records are
    allocated in ``target_var_factory``. Only source-factory connections whose
    two endpoints belong structurally to ``block`` are restored in the target.

    :param block: Source block owned by ``source_var_factory``.
    :param source_var_factory: Factory containing the source connection graph.
    :param target_var_factory: Factory receiving the duplicated block graph.
    :return: Independent block instance owned by the target factory.
    """
    # Define the structural boundary before reading the shared source graph so
    # external device and bus connections cannot leak into the editor factory.
    owned_source_vars: Dict[int, Var] = _collect_owned_block_vars_by_non_mutable_uid(block)
    source_connections: List[tuple[int, int]] = list()
    incoming_non_mutable_uid: int
    connection_records: List[Connection]
    connection_record: Connection
    for incoming_non_mutable_uid, connection_records in (
            source_var_factory.get_connections_dict().items()
    ):
        if incoming_non_mutable_uid in owned_source_vars:
            for connection_record in connection_records:
                if connection_record.non_mutable_uid in owned_source_vars:
                    source_connections.append((
                        incoming_non_mutable_uid,
                        connection_record.non_mutable_uid,
                    ))
                else:
                    pass
        else:
            pass

    # Validate every local contract before allocating any destination objects.
    source_block: Block
    for source_block in block.get_all_blocks():
        validate_dynamic_model_contract(source_block)
    else:
        pass

    # The established structural duplicator creates fresh variables, constants,
    # expressions, block identities, and factory-local shared references.
    source_non_mutable_uid_to_new_var: Dict[int, Var] = dict()
    duplicated_block: Block = _duplicate_block(
        block=block,
        var_factory=target_var_factory,
        source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
        old_to_new_const=dict(),
        old_to_new_block_uid=dict(),
    )

    # Replay each internal source edge with cloned endpoints. Registration in
    # the target propagates the incoming UID and name through its alias graph.
    source_incoming_uid: int
    source_substituted_uid: int
    duplicated_incoming_var: Var | None
    duplicated_substituted_var: Var | None
    for source_incoming_uid, source_substituted_uid in source_connections:
        duplicated_incoming_var = source_non_mutable_uid_to_new_var.get(
            source_incoming_uid,
            None,
        )
        duplicated_substituted_var = source_non_mutable_uid_to_new_var.get(
            source_substituted_uid,
            None,
        )
        if duplicated_incoming_var is not None and duplicated_substituted_var is not None:
            if duplicated_incoming_var.network_conn:
                target_var_factory.add_network_connection(
                    var_to_subs=duplicated_substituted_var,
                    incoming_var=duplicated_incoming_var,
                )
            else:
                target_var_factory.add_connection(
                    var_to_subs=duplicated_substituted_var,
                    incoming_var=duplicated_incoming_var,
                )
        else:
            pass

    # Validate remapped contracts on every duplicated owner before publication.
    duplicated_candidate: Block
    for duplicated_candidate in duplicated_block.get_all_blocks():
        validate_dynamic_model_contract(duplicated_candidate)
    else:
        pass
    return duplicated_block


def duplicate_block_vars_uid(
        block: Block,
        source_var_factory: VarFactory,
        target_var_factory: VarFactory,
) -> Block:
    """
    Create an isolated editor duplicate while preserving symbolic identities.

    Every variable in the duplicated tree is a new object registered in
    ``target_var_factory`` with the same ``uid`` and ``non_mutable_uid`` as its
    source. Internal connection records are copied from ``source_var_factory``
    without replaying them, because their current propagated UIDs and saved
    restoration metadata already describe the source state.

    :param block: Persistent block tree to duplicate.
    :param source_var_factory: Factory containing the persistent connection graph.
    :param target_var_factory: Empty private factory for the editor session.
    :return: Independent block tree owned symbolically by the target factory.
    """
    source_block: Block
    source_non_mutable_uid_to_new_var: Dict[int, Var] = dict()

    if len(target_var_factory.get_vars_dict()) > 0 or len(target_var_factory.get_diff_var_dict()) > 0:
        raise ValueError("duplicate_block_vars_uid requires an empty target VarFactory")
    else:
        pass

    for source_block in block.get_all_blocks():
        validate_dynamic_model_contract(source_block)

    duplicated_block: Block = _duplicate_block_uid(
        block=block,
        var_factory=target_var_factory,
        source_non_mutable_uid_to_new_var=source_non_mutable_uid_to_new_var,
    )

    source_non_mutable_uid: int
    source_connections: List[Connection]
    source_connection: Connection
    duplicated_connections: List[Connection]
    target_connection_graph: Dict[int, List[Connection]] = target_var_factory.get_connections_dict()

    # Copy only edges fully contained in the duplicated tree. A device block is
    # not allowed to import foreign variables into the editor-owned factory.
    for source_non_mutable_uid, source_connections in source_var_factory.get_connections_dict().items():
        if source_non_mutable_uid in source_non_mutable_uid_to_new_var:
            duplicated_connections = list()
            for source_connection in source_connections:
                if source_connection.non_mutable_uid in source_non_mutable_uid_to_new_var:
                    duplicated_connections.append(Connection(
                        non_mutable_uid=source_connection.non_mutable_uid,
                        name=source_connection.name,
                        uid=source_connection.uid,
                    ))
                else:
                    pass

            if len(duplicated_connections) > 0:
                target_connection_graph[source_non_mutable_uid] = duplicated_connections
            else:
                pass
        else:
            pass

    for source_block in duplicated_block.get_all_blocks():
        validate_dynamic_model_contract(source_block)

    return duplicated_block


def compare_blocks(
        block1: Block,
        block2: Block,
        var_factory1: VarFactory,
        var_factory2: VarFactory,
        testing: bool = False,
) -> bool:
    """Compare the declarative symbolic content of two blocks.

    :param block1:
    :param block2:
    :param var_factory1: Variable factory that owns ``block1`` references.
    :param var_factory2: Variable factory that owns ``block2`` references.
    :param testing: Backward-compatible diagnostic flag; equality semantics
        remain identical in production and diagnostic callers.
    :return: Whether both blocks produce the same persisted symbolic content.
    """
    if testing:
        # Diagnostic callers intentionally exercise the production equality
        # path, so the flag does not select a weaker comparison algorithm.
        pass
    else:
        pass

    # TODO: do not use dictionaries and compare directly using the block information
    saver1 = BlockSaver(var_factory1)
    saver1.save_block(block1, main=False)
    const_save1 = saver1.get_const_to_save()
    vars_save1 = saver1.get_vars_to_save()
    diff_vars_save1 = saver1.get_diff_vars_to_save()
    blocks1 = saver1.get_blocks()

    saver2 = BlockSaver(var_factory2)
    saver2.save_block(block2, main=False)
    const_save2 = saver2.get_const_to_save()
    vars_save2 = saver2.get_vars_to_save()
    diff_vars_save2 = saver2.get_diff_vars_to_save()
    blocks2 = saver2.get_blocks()

    return (blocks1, const_save1, vars_save1, diff_vars_save1) == (blocks2, const_save2, vars_save2, diff_vars_save2)
