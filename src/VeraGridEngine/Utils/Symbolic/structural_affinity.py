# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Conservative structural affinity analysis of symbolic expressions.

An expression is classified with respect to a set of unknowns as CONSTANT,
EXCITATION, AFFINE or NONLINEAR. AFFINE means that every partial derivative
with respect to the unknowns depends only on epoch constants (numbers, constant
parameters and the step size), so the corresponding Jacobian row is invariant
while the step size and the integration method stay fixed. Time and runtime
parameters may only enter the unknown-free additive part of an AFFINE
expression. Every construct the analyzer cannot prove affine is NONLINEAR.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, FrozenSet, List, Set, Tuple

from VeraGridEngine.enumerations import ExpressionAffinity
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Const, Func, Func2, UnOp, Var


class SymbolRole(Enum):
    """
    Role of a symbolic variable inside the structural affinity analysis.
    """
    UNKNOWN = "unknown"  # Solved for by the Newton iteration
    DIFFERENTIAL = "differential"  # Derivative placeholder of an origin variable
    EPOCH_CONSTANT = "epoch_constant"  # Constant parameter or step size
    EXCITATION = "excitation"  # Time or runtime parameter
    UNRESOLVED = "unresolved"  # No known role


class StructuralAffinityAnalyzer:
    """
    Classify symbolic expressions over explicit symbol roles.

    Affinity results are memoised by node identity across calls, so one
    instance is valid for one immutable snapshot of the expressions and roles
    only; create a new instance after any expression or uid is rewired.
    The analyzer never constructs, substitutes, simplifies or writes any
    expression or variable.
    """

    __slots__ = (
        "_unknown_uids",
        "_epoch_constant_uids",
        "_excitation_uids",
        "_excitation_names",
        "_epoch_constant_names",
        "_affinity_memo",
    )

    _DETERMINISTIC_UNARY_FUNCTIONS: FrozenSet[str] = frozenset((
        "sin", "cos", "tan", "exp", "log", "log10", "sqrt", "asin", "acos", "atan",
        "sinh", "cosh", "tanh", "floor", "ceil", "round", "real", "imag", "conj",
        "angle", "abs", "heaviside",
    ))

    _DETERMINISTIC_BINARY_FUNCTIONS: FrozenSet[str] = frozenset(("atan2", "min", "max"))

    def __init__(self,
                 unknown_uids: Set[int],
                 epoch_constant_uids: Set[int],
                 excitation_uids: Set[int],
                 excitation_names: Set[str],
                 epoch_constant_names: Set[str]) -> None:
        """
        Create an analyzer for one snapshot of symbol roles.

        :param unknown_uids: Uids of the unknowns of the solve.
        :param epoch_constant_uids: Uids of constant parameters.
        :param excitation_uids: Uids of runtime parameters and time variables.
        :param excitation_names: Variable names that always denote time.
        :param epoch_constant_names: Variable names that always denote the step size.
        """
        self._unknown_uids: FrozenSet[int] = frozenset(unknown_uids)
        self._epoch_constant_uids: FrozenSet[int] = frozenset(epoch_constant_uids)
        self._excitation_uids: FrozenSet[int] = frozenset(excitation_uids)
        self._excitation_names: FrozenSet[str] = frozenset(excitation_names)
        self._epoch_constant_names: FrozenSet[str] = frozenset(epoch_constant_names)
        # Each entry keeps the node alive so that its identity cannot be reused.
        self._affinity_memo: Dict[int, Tuple[Any, ExpressionAffinity]] = dict()

    @staticmethod
    def _rank(affinity: ExpressionAffinity) -> int:
        """
        Return the lattice rank of an affinity.

        :param affinity: Affinity to rank.
        :return: 0 for CONSTANT, 1 for EXCITATION, 2 for AFFINE and 3 for NONLINEAR.
        """
        if affinity == ExpressionAffinity.CONSTANT:
            rank: int = 0
        elif affinity == ExpressionAffinity.EXCITATION:
            rank = 1
        elif affinity == ExpressionAffinity.AFFINE:
            rank = 2
        else:
            rank = 3
        return rank

    @staticmethod
    def _higher(first: ExpressionAffinity, second: ExpressionAffinity) -> ExpressionAffinity:
        """
        Return the affinity with the higher lattice rank.

        :param first: First affinity.
        :param second: Second affinity.
        :return: Higher-ranked affinity.
        """
        if StructuralAffinityAnalyzer._rank(first) >= StructuralAffinityAnalyzer._rank(second):
            result: ExpressionAffinity = first
        else:
            result = second
        return result

    @staticmethod
    def _product(first: ExpressionAffinity, second: ExpressionAffinity) -> ExpressionAffinity:
        """
        Combine the affinities of the two factors of a product.

        :param first: Affinity of the left factor.
        :param second: Affinity of the right factor.
        :return: Affinity of the product.
        """
        if first == ExpressionAffinity.NONLINEAR or second == ExpressionAffinity.NONLINEAR:
            result: ExpressionAffinity = ExpressionAffinity.NONLINEAR
        elif first == ExpressionAffinity.AFFINE and second == ExpressionAffinity.CONSTANT:
            result = ExpressionAffinity.AFFINE
        elif first == ExpressionAffinity.CONSTANT and second == ExpressionAffinity.AFFINE:
            result = ExpressionAffinity.AFFINE
        elif first == ExpressionAffinity.AFFINE or second == ExpressionAffinity.AFFINE:
            # An unknown multiplied by an unknown, time or a runtime parameter.
            result = ExpressionAffinity.NONLINEAR
        else:
            result = StructuralAffinityAnalyzer._higher(first, second)
        return result

    @staticmethod
    def _origin_uid(var: Var) -> int:
        """
        Return the uid of the origin of a derivative placeholder.

        The base_var chain is walked explicitly because the ``origin_var``
        property caches its result into the variable.

        :param var: Variable with a base_var chain.
        :return: Uid of the root of the chain.
        """
        current: Var = var
        while current.base_var is not None:
            current = current.base_var
        return current.uid

    def _resolve_role(self, var: Var) -> SymbolRole:
        """
        Resolve the role of one variable.

        :param var: Variable to resolve.
        :return: Role of the variable.
        """
        if var.uid in self._unknown_uids:
            role: SymbolRole = SymbolRole.UNKNOWN
        elif var.uid in self._epoch_constant_uids:
            role = SymbolRole.EPOCH_CONSTANT
        elif var.uid in self._excitation_uids or var.name in self._excitation_names:
            role = SymbolRole.EXCITATION
        elif var.base_var is not None:
            role = SymbolRole.DIFFERENTIAL
        elif var.name in self._epoch_constant_names:
            role = SymbolRole.EPOCH_CONSTANT
        else:
            role = SymbolRole.UNRESOLVED
        return role

    def _is_traversable(self, node: Any) -> bool:
        """
        Tell whether a node belongs to the explicitly supported operator set.

        :param node: Candidate node.
        :return: True for BinOp + - * / **, UnOp '-', and whitelisted Func and Func2.
        """
        node_type: type = type(node)
        if node_type is BinOp:
            result: bool = node.op in ("+", "-", "*", "/", "**")
        elif node_type is UnOp:
            result = node.op == "-"
        elif node_type is Func:
            result = node.op in self._DETERMINISTIC_UNARY_FUNCTIONS
        elif node_type is Func2:
            result = node.name in self._DETERMINISTIC_BINARY_FUNCTIONS
        else:
            result = False
        return result

    @staticmethod
    def _children(node: Any) -> List[Any]:
        """
        Return the operands of a traversable node.

        :param node: Traversable node.
        :return: Operands in evaluation order.
        """
        node_type: type = type(node)
        if node_type is BinOp:
            children: List[Any] = [node.left, node.right]
        elif node_type is UnOp:
            children = [node.operand]
        elif node_type is Func:
            children = [node.arg]
        else:
            children = [node.arg1, node.arg2]
        return children

    def _leaf_affinity(self, node: Any) -> ExpressionAffinity:
        """
        Classify a Const or Var node.

        :param node: Const or Var node.
        :return: Affinity of the leaf.
        """
        if type(node) is Const:
            if node.value is None:
                # Undefined at compile time; it may be assigned at runtime.
                result: ExpressionAffinity = ExpressionAffinity.EXCITATION
            else:
                result = ExpressionAffinity.CONSTANT
        else:
            role: SymbolRole = self._resolve_role(node)
            if role == SymbolRole.UNKNOWN:
                result = ExpressionAffinity.AFFINE
            elif role == SymbolRole.DIFFERENTIAL:
                if self._origin_uid(node) in self._unknown_uids:
                    # Discretised as an affine function of its origin with h-only coefficients.
                    result = ExpressionAffinity.AFFINE
                else:
                    result = ExpressionAffinity.NONLINEAR
            elif role == SymbolRole.EPOCH_CONSTANT:
                result = ExpressionAffinity.CONSTANT
            elif role == SymbolRole.EXCITATION:
                result = ExpressionAffinity.EXCITATION
            else:
                result = ExpressionAffinity.NONLINEAR
        return result

    def _power_affinity(self, node: BinOp, base: ExpressionAffinity, exponent: ExpressionAffinity) -> ExpressionAffinity:
        """
        Classify a power node.

        :param node: BinOp node with operator '**'.
        :param base: Affinity of the base.
        :param exponent: Affinity of the exponent.
        :return: Affinity of the power.
        """
        if exponent == ExpressionAffinity.AFFINE or exponent == ExpressionAffinity.NONLINEAR:
            result: ExpressionAffinity = ExpressionAffinity.NONLINEAR
        elif base == ExpressionAffinity.NONLINEAR:
            result = ExpressionAffinity.NONLINEAR
        elif base == ExpressionAffinity.AFFINE:
            right: Any = node.right
            if type(right) is Const and right.value is not None and right.value == 1:
                result = ExpressionAffinity.AFFINE
            elif type(right) is Const and right.value is not None and right.value == 0:
                result = ExpressionAffinity.CONSTANT
            else:
                result = ExpressionAffinity.NONLINEAR
        else:
            result = self._higher(base, exponent)
        return result

    def _combine(self, node: Any, operands: List[ExpressionAffinity]) -> ExpressionAffinity:
        """
        Classify a traversable node from the affinities of its operands.

        :param node: Traversable node.
        :param operands: Affinities of the operands in evaluation order.
        :return: Affinity of the node.
        """
        node_type: type = type(node)
        if node_type is BinOp:
            if node.op == "+" or node.op == "-":
                result: ExpressionAffinity = self._higher(operands[0], operands[1])
            elif node.op == "*":
                result = self._product(operands[0], operands[1])
            elif node.op == "/":
                if operands[1] == ExpressionAffinity.AFFINE or operands[1] == ExpressionAffinity.NONLINEAR:
                    result = ExpressionAffinity.NONLINEAR
                else:
                    result = self._product(operands[0], operands[1])
            else:
                result = self._power_affinity(node, operands[0], operands[1])
        elif node_type is UnOp:
            result = operands[0]
        else:
            result = ExpressionAffinity.CONSTANT
            for operand in operands:
                result = self._higher(result, operand)
            if result == ExpressionAffinity.AFFINE or result == ExpressionAffinity.NONLINEAR:
                result = ExpressionAffinity.NONLINEAR
            else:
                pass
        return result

    def classify(self, expr: Any) -> ExpressionAffinity:
        """
        Classify an expression with respect to the unknowns.

        Unsupported node types, non-whitelisted operators and non-Expr objects
        are NONLINEAR. The traversal is iterative.

        :param expr: Expression (or any row object) to classify.
        :return: Affinity of the expression.
        """
        pending: List[Tuple[Any, bool]] = [(expr, False)]
        while len(pending) > 0:
            node, expanded = pending.pop()
            key: int = id(node)
            node_type: type = type(node)
            if key in self._affinity_memo:
                pass
            elif node_type is Const or node_type is Var:
                self._affinity_memo[key] = (node, self._leaf_affinity(node))
            elif not self._is_traversable(node):
                self._affinity_memo[key] = (node, ExpressionAffinity.NONLINEAR)
            elif expanded:
                operands: List[ExpressionAffinity] = list()
                for child in self._children(node):
                    operands.append(self._affinity_memo[id(child)][1])
                self._affinity_memo[key] = (node, self._combine(node, operands))
            else:
                pending.append((node, True))
                for child in self._children(node):
                    pending.append((child, False))
        return self._affinity_memo[id(expr)][1]

    def _collect_support(self, expr: Any) -> Tuple[FrozenSet[int], bool]:
        """
        Collect the unknown support of an expression.

        :param expr: Expression (or any row object) to inspect.
        :return: Support (all unknowns when opaque) and the opacity flag.
        """
        visited: Set[int] = set()
        support: Set[int] = set()
        opaque: bool = False
        pending: List[Any] = [expr]
        while len(pending) > 0:
            node: Any = pending.pop()
            node_type: type = type(node)
            if id(node) in visited:
                pass
            elif node_type is Var:
                visited.add(id(node))
                if node.uid in self._unknown_uids:
                    support.add(node.uid)
                elif self._resolve_role(node) == SymbolRole.DIFFERENTIAL:
                    origin_uid: int = self._origin_uid(node)
                    if origin_uid in self._unknown_uids:
                        support.add(origin_uid)
                    else:
                        pass
                else:
                    pass
            elif node_type is Const:
                visited.add(id(node))
            elif self._is_traversable(node):
                visited.add(id(node))
                pending.extend(self._children(node))
            else:
                visited.add(id(node))
                opaque = True

        if opaque:
            result: FrozenSet[int] = self._unknown_uids
        else:
            result = frozenset(support)
        return result, opaque

    def get_unknown_support(self, expr: Any) -> FrozenSet[int]:
        """
        Return the unknown uids an expression references.

        Derivative placeholders are mapped to their origin. When the expression
        contains a node outside the supported operator set, every unknown is
        returned.

        :param expr: Expression (or any row object) to inspect.
        :return: Unknown uids referenced by the expression.
        """
        return self._collect_support(expr)[0]

    def is_opaque(self, expr: Any) -> bool:
        """
        Tell whether an expression contains a node outside the supported operator set.

        :param expr: Expression (or any row object) to inspect.
        :return: True when the support of the expression cannot be determined structurally.
        """
        return self._collect_support(expr)[1]
