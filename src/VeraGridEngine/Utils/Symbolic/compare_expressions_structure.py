# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Symbolic Expression Equivalence Engine.

Provides canonicalization, structural hashing, DAG representation,
and equivalence checking for symbolic expressions without modifying
the original expression trees.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from VeraGridEngine.Utils.Symbolic.symbolic import (
    Expr, Const, Var, BinOp, UnOp, Func, Func2,
    _to_expr,
)

CommutativeOps = {"+", "*"}
NonSimplifiableOps = {"+", "-", "*", "/", "**"}


class DAGNode:
    """
    Node in a Directed Acyclic Graph representation of an expression.
    
    Attributes:
        op: Operator type (str for BinOp/UnOp/Func, or node type name)
        children: List of child DAGNode references
        structural_hash: Precomputed structural hash string
    """
    __slots__ = ("op", "children", "structural_hash", "_expr")

    def __init__(
        self,
        op: str,
        children: List["DAGNode"],
        structural_hash: str,
        expr: Optional[Expr] = None,
    ):
        self.op: str = op
        self.children: List["DAGNode"] = children
        self.structural_hash: str = structural_hash
        self._expr: Optional[Expr] = expr

    def __repr__(self) -> str:
        if self.children:
            return f"DAGNode({self.op}, [{len(self.children)} children], hash={self.structural_hash[:8]})"
        return f"DAGNode({self.op}, [], hash={self.structural_hash[:8]})"


def _canonical_const(value: Any) -> Tuple[str, Any]:
    """Return canonical (type_key, normalized_value) for constants."""
    if value is None:
        return ("none", None)
    if isinstance(value, complex):
        return ("complex", (float(value.real), float(value.imag)))
    if isinstance(value, float):
        if value == int(value):
            return ("int", int(value))
        return ("float", value)
    return (type(value).__name__, value)


def _flatten_assoc(expr: Expr, op: str) -> List[Expr]:
    """
    Flatten associative operations.
    (a + (b + c)) -> [a, b, c]
    """
    if isinstance(expr, BinOp) and expr.op == op:
        return _flatten_assoc(expr.left, op) + _flatten_assoc(expr.right, op)
    return [expr]


def _sort_exprs(exprs: List[Expr], key_func) -> List[Expr]:
    """Sort expressions using structural hash as key for determinism."""
    return sorted(exprs, key=key_func)


def canonical(expr: Expr, depth: int = 0) -> Expr:
    """
    Transform an expression into canonical form.
    
    Applies:
    - Flatten associative operators (+, *)
    - Sort commutative operands
    - Constant folding
    - Remove neutral elements (a+0=a, a*1=a, a*0=0)
    - Normalize powers (a**1=a, a**0=1)
    
    Does NOT mutate the original expression.
    
    :param expr: Expression to canonicalize
    :param depth: Current recursion depth for cycle detection
    :return: New canonical expression
    """
    if depth > 100:
        return expr
    
    if isinstance(expr, Const):
        return Const(expr.value)

    if isinstance(expr, Var):
        return Var(
            name=expr.name,
            reference=expr.ref,
            network_conn=expr.network_conn,
            shared_reference=expr.shared_ref,
            non_mutable_uid=expr.non_mutable_uid,
            uid=expr.uid,
            diff_var=expr.diff_var,
            base_var=expr.base_var,
        )

    if isinstance(expr, UnOp):
        canonical_operand = canonical(expr.operand, depth + 1)
        if expr.op == "-":
            if isinstance(canonical_operand, Const):
                return Const(-canonical_operand.value)
            if isinstance(canonical_operand, UnOp) and canonical_operand.op == "-":
                return canonical_operand.operand
            return UnOp("-", canonical_operand)
        return UnOp(expr.op, canonical_operand)

    if isinstance(expr, BinOp):
        left = canonical(expr.left, depth + 1)
        right = canonical(expr.right, depth + 1)

        if expr.op == "+":
            terms = _flatten_assoc(BinOp(left, "+", right), "+")
            const_sum = 0.0
            non_const_terms = []
            for t in terms:
                if isinstance(t, Const) and t.value is not None:
                    const_sum += t.value
                else:
                    non_const_terms.append(t)
            if const_sum != 0.0 or not non_const_terms:
                non_const_terms.append(Const(const_sum))
            if len(non_const_terms) == 1:
                return non_const_terms[0]
            return _build_sum(non_const_terms)

        if expr.op == "*":
            factors = _flatten_assoc(BinOp(left, "*", right), "*")
            zero_found = False
            const_product = 1.0
            non_const_factors = []
            for f in factors:
                if isinstance(f, Const) and f.value is not None:
                    if f.value == 0:
                        zero_found = True
                        break
                    const_product *= f.value
                else:
                    non_const_factors.append(f)
            if zero_found:
                return Const(0)
            if const_product != 1.0:
                non_const_factors.append(Const(const_product))
            if not non_const_factors:
                return Const(1)
            if len(non_const_factors) == 1:
                return non_const_factors[0]
            return _build_product(non_const_factors)

        if expr.op == "-":
            if isinstance(right, Const) and isinstance(left, Const):
                return Const(left.value - right.value)
            if isinstance(right, Const) and right.value == 0:
                return left
            if isinstance(left, Const) and left.value == 0:
                return UnOp("-", right)
            return BinOp(left, "-", right)

        if expr.op == "/":
            if isinstance(left, Const) and isinstance(right, Const):
                if right.value != 0:
                    return Const(left.value / right.value)
            if isinstance(right, Const) and right.value == 1:
                return left
            if isinstance(left, Const) and left.value == 0:
                return Const(0)
            return BinOp(left, "/", right)

        if expr.op == "**":
            if isinstance(right, Const) and right.value == 0:
                return Const(1)
            if isinstance(right, Const) and right.value == 1:
                return left
            if isinstance(left, Const) and isinstance(right, Const):
                return Const(left.value ** right.value)
            return BinOp(left, "**", right)

        return BinOp(left, expr.op, right)

    if isinstance(expr, Func):
        arg_canon = canonical(expr.arg)
        if isinstance(arg_canon, Const) and arg_canon.value is not None:
            try:
                import math
                result = _eval_func(expr.op, arg_canon.value)
                return Const(result)
            except (ValueError, TypeError):
                pass
        return Func(arg_canon, expr.op)

    if isinstance(expr, Func2):
        arg1_canon = canonical(expr.arg1)
        arg2_canon = canonical(expr.arg2)
        return Func2(expr.name, arg1_canon, arg2_canon)

    return expr


def _build_sum(terms: List[Expr]) -> Expr:
    """Build a canonical sum from a list of terms."""
    if len(terms) == 0:
        return Const(0)
    if len(terms) == 1:
        return terms[0]
    result = terms[0]
    for t in terms[1:]:
        result = BinOp(result, "+", t)
    return result


def _build_product(factors: List[Expr]) -> Expr:
    """Build a canonical product from a list of factors."""
    if len(factors) == 0:
        return Const(1)
    if len(factors) == 1:
        return factors[0]
    result = factors[0]
    for f in factors[1:]:
        result = BinOp(result, "*", f)
    return result


def _expand_power(expr: Expr) -> Expr:
    """
    Expand a power expression to multiplication: x**2 -> x*x
    
    :param expr: Expression that may be a power
    :return: Expanded expression or original
    """
    if not isinstance(expr, BinOp) or expr.op != "**":
        return expr
    
    base = expr.left
    exponent = expr.right
    
    if isinstance(exponent, Const) and isinstance(exponent.value, (int, float)):
        n = int(exponent.value)
        if n == 2:
            return canonical(BinOp(base, "*", base))
        if n >= 2 and n <= 10:
            result = base
            for _ in range(n - 1):
                result = canonical(BinOp(result, "*", base))
            return result
    
    return expr


def _expand_product_sum(expr: Expr) -> Expr:
    """
    Expand products of sums: (a+b)*(c+d) -> a*c + a*d + b*c + b*d
    Also handles (a+b)^n for small integer n.
    
    :param expr: Binary operation expression
    :return: Expanded expression
    """
    if not isinstance(expr, BinOp):
        return expr
    
    left = expr.left
    right = expr.right
    op = expr.op
    
    if op == "**":
        if isinstance(right, Const) and isinstance(right.value, (int, float)):
            n = int(right.value)
            if n == 2 and isinstance(left, BinOp) and left.op == "+":
                a = left.left
                b = left.right
                a_sq = _expand_power(BinOp(a, "**", Const(2)))
                b_sq = _expand_power(BinOp(b, "**", Const(2)))
                ab = BinOp(a, "*", b)
                ba = BinOp(b, "*", a)
                two_ab = BinOp(Const(2), "*", ab)
                result = BinOp(BinOp(a_sq, "+", two_ab), "+", b_sq)
                return _combine_like_terms_sum(result)
            if n >= 2 and n <= 10 and isinstance(left, BinOp) and left.op == "+":
                result = left
                for _ in range(n - 1):
                    result = BinOp(result, "*", left)
                return _combine_like_terms_sum(expand(result))
    
    if op == "*":
        left_exp = _expand_product_sum(left)
        right_exp = _expand_product_sum(right)
        
        if isinstance(left_exp, BinOp) and left_exp.op == "+":
            term1 = BinOp(left_exp.left, "*", right_exp)
            term2 = BinOp(left_exp.right, "*", right_exp)
            result = BinOp(term1, "+", term2)
            return _combine_like_terms_sum(result)
        
        if isinstance(right_exp, BinOp) and right_exp.op == "+":
            term1 = BinOp(left_exp, "*", right_exp.left)
            term2 = BinOp(left_exp, "*", right_exp.right)
            result = BinOp(term1, "+", term2)
            return _combine_like_terms_sum(result)
        
        if isinstance(left_exp, BinOp) and left_exp.op == "-":
            term1 = BinOp(left_exp.left, "*", right_exp)
            term2 = BinOp(left_exp.right, "*", right_exp)
            return canonical(BinOp(term1, "-", term2))
        
        if isinstance(right_exp, BinOp) and right_exp.op == "-":
            term1 = BinOp(left_exp, "*", right_exp.left)
            term2 = BinOp(left_exp, "*", right_exp.right)
            return canonical(BinOp(term1, "-", term2))
    
    return expr


def _collect_sum_terms(expr: Expr) -> Expr:
    """Collect and combine like terms in a sum expression."""
    if not isinstance(expr, BinOp) or expr.op != "+":
        return expr
    
    terms = _flatten_and_collect_terms(expr)
    return _combine_terms_list(terms)


def _flatten_and_collect_terms(expr: Expr) -> List[Expr]:
    """Flatten a sum into a list of terms."""
    if isinstance(expr, BinOp) and expr.op == "+":
        return _flatten_and_collect_terms(expr.left) + _flatten_and_collect_terms(expr.right)
    return [expr]


def _combine_terms_list(terms: List[Expr]) -> Expr:
    """Combine like terms from a list of expressions."""
    term_map: Dict[str, Tuple[float, Expr]] = {}
    
    for term in terms:
        term_canon = canonical(term)
        term_hash = _hash_expr(term_canon)
        
        const_factor = _get_const_from_expr(term_canon)
        non_const = _remove_const_from_expr(term_canon)
        non_const_hash = _hash_expr(non_const)
        
        if non_const_hash in term_map:
            existing_const, _ = term_map[non_const_hash]
            term_map[non_const_hash] = (existing_const + const_factor, non_const)
        else:
            term_map[non_const_hash] = (const_factor, non_const)
    
    combined_terms = []
    for const_factor, non_const in term_map.values():
        if const_factor == 0:
            continue
        if isinstance(non_const, Const):
            combined_terms.append(Const(const_factor))
        else:
            combined_terms.append(canonical(BinOp(Const(const_factor), "*", non_const)))
    
    if not combined_terms:
        return Const(0)
    
    combined_terms.sort(key=_hash_expr)
    result = combined_terms[0]
    for t in combined_terms[1:]:
        result = canonical(BinOp(result, "+", t))
    return result


def _get_const_from_expr(expr: Expr) -> float:
    """Get the constant multiplier from an expression."""
    if isinstance(expr, Const):
        return expr.value if expr.value is not None else 1.0
    if isinstance(expr, BinOp) and expr.op == "*":
        total = 1.0
        factors = _flatten_assoc(expr, "*")
        for f in factors:
            if isinstance(f, Const) and f.value is not None:
                total *= f.value
            else:
                return total
        return total
    if isinstance(expr, BinOp) and expr.op == "**":
        if isinstance(expr.right, Const) and expr.right.value == 2:
            base_const = _get_const_from_expr(expr.left)
            if isinstance(expr.left, Var):
                return base_const
            return base_const * base_const
    return 1.0


def _remove_const_from_expr(expr: Expr) -> Expr:
    """Remove constant factors from an expression, returning the non-constant part."""
    if isinstance(expr, Const):
        return Const(1)
    if isinstance(expr, Var):
        return expr
    if isinstance(expr, BinOp) and expr.op == "*":
        factors = _flatten_assoc(expr, "*")
        non_const_factors = []
        for f in factors:
            if not (isinstance(f, Const) and f.value is not None):
                non_const_factors.append(_remove_const_from_expr(f))
        if not non_const_factors:
            return Const(1)
        if len(non_const_factors) == 1:
            return non_const_factors[0]
        result = non_const_factors[0]
        for f in non_const_factors[1:]:
            result = BinOp(result, "*", f)
        return result
    if isinstance(expr, BinOp) and expr.op == "**":
        if isinstance(expr.right, Const) and expr.right.value == 2:
            base = _remove_const_from_expr(expr.left)
            return canonical(BinOp(base, "*", base))
    return expr


def _collect_and_combine_terms(expr: Expr) -> Expr:
    """
    Collect like terms in a sum and combine them.
    For example: x*y + y*x -> 2*x*y
    """
    if isinstance(expr, BinOp) and expr.op == "+":
        left = expr.left
        right = expr.right
        
        if isinstance(left, BinOp) and left.op == "+":
            left_result = _collect_and_combine_terms(left)
            right_result = _collect_and_combine_terms(right) if isinstance(right, BinOp) else right
            combined = BinOp(left_result, "+", right_result)
            return _collect_and_combine_terms(combined)
        
        right_result = _collect_and_combine_terms(right) if isinstance(right, BinOp) else right
        
        combined = BinOp(left, "+", right_result)
        return _do_combine_terms(combined)
    
    return expr


def _do_combine_terms(expr: Expr) -> Expr:
    """Helper to actually combine terms in a sum."""
    if not isinstance(expr, BinOp) or expr.op != "+":
        return expr
    
    left = expr.left
    right = expr.right
    
    if isinstance(left, BinOp) and left.op == "+":
        left_combined = _do_combine_terms(left)
        right_combined = _do_combine_terms(right) if isinstance(right, BinOp) else right
        return canonical(BinOp(left_combined, "+", right_combined))
    
    right = _do_combine_terms(right) if isinstance(right, BinOp) else right
    
    left_vars = _get_product_vars_sorted(left)
    right_vars = _get_product_vars_sorted(right)
    
    if left_vars and left_vars == right_vars:
        left_const = _get_const_from_term(left)
        right_const = _get_const_from_term(right)
        
        if left_const is not None and right_const is not None:
            total_const = left_const * right_const
            non_const = _get_non_const_part(left)
            combined = canonical(BinOp(Const(total_const), "*", non_const))
            return combined
    
    return canonical(BinOp(left, "+", right))


def _get_product_vars_sorted(expr: Expr) -> List[str]:
    """Get sorted list of variable names in a term (product or single var)."""
    if isinstance(expr, Var):
        return [expr.name]
    if isinstance(expr, Const):
        return []
    if isinstance(expr, BinOp) and expr.op == "*":
        return sorted(_get_product_vars_sorted(expr.left) + _get_product_vars_sorted(expr.right))
    if isinstance(expr, BinOp) and expr.op == "**":
        return _get_product_vars_sorted(expr.left) * int(expr.right.value) if isinstance(expr.right, Const) else []
    return []


def _get_const_from_term(expr: Expr) -> Optional[float]:
    """Get constant factor from a term (product or single const)."""
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, BinOp) and expr.op == "*":
        consts = []
        if isinstance(expr.left, Const):
            consts.append(expr.left.value)
        elif isinstance(expr.right, Const):
            consts.append(expr.right.value)
        else:
            consts_left = _get_const_from_term(expr.left)
            consts_right = _get_const_from_term(expr.right)
            if consts_left is not None:
                consts.append(consts_left)
            if consts_right is not None:
                consts.append(consts_right)
        if consts:
            result = 1.0
            for c in consts:
                result *= c
            return result
    return None


def _get_non_const_part(expr: Expr) -> Expr:
    """Get the non-constant part of a term."""
    if isinstance(expr, Const):
        return Const(1)
    if isinstance(expr, Var):
        return expr
    if isinstance(expr, BinOp) and expr.op == "*":
        left_part = _get_non_const_part(expr.left) if not isinstance(expr.left, Const) else None
        right_part = _get_non_const_part(expr.right) if not isinstance(expr.right, Const) else None
        if left_part is None and right_part is None:
            return Const(1)
        if left_part is None:
            return right_part
        if right_part is None:
            return left_part
        return BinOp(left_part, "*", right_part)
    return expr


def _get_product_vars(expr: Expr) -> List[str]:
    """Get sorted list of variable names in a product."""
    if isinstance(expr, Var):
        return [expr.name]
    if isinstance(expr, BinOp) and expr.op == "*":
        return _get_product_vars(expr.left) + _get_product_vars(expr.right)
    return []


def _get_const_factor_in_product(expr: Expr) -> Optional[float]:
    """Get constant factor from a product expression."""
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, BinOp) and expr.op == "*":
        if isinstance(expr.left, Const) and expr.left.value is not None:
            return expr.left.value
        if isinstance(expr.right, Const) and expr.right.value is not None:
            return expr.right.value
    return None


def _remove_const_from_product(expr: Expr) -> Expr:
    """Remove constant factor from a product, returning the non-constant part."""
    if isinstance(expr, BinOp) and expr.op == "*":
        if isinstance(expr.left, Const):
            return expr.right
        if isinstance(expr.right, Const):
            return expr.left
    return expr
    
    left = expr.left
    right = expr.right
    
    if isinstance(left, BinOp) and left.op == "+":
        left_combined = _collect_and_combine_terms(left)
        right_combined = _collect_and_combine_terms(right)
        combined = BinOp(left_combined, "+", right_combined)
        return _collect_and_combine_terms(combined)
    
    right_combined = _collect_and_combine_terms(right) if isinstance(right, BinOp) else right
    
    left_hash = _hash_expr(left)
    right_hash = _hash_expr(right)
    
    left_vars = _get_product_vars(left)
    right_vars = _get_product_vars(right)
    
    if left_vars and str(sorted(left_vars)) == str(sorted(right_vars)):
        left_const = _get_const_factor_in_product(left)
        right_const = _get_const_factor_in_product(right)
        
        if left_const is not None and right_const is not None:
            new_const = Const(left_const * right_const)
            left_non_const = _remove_const_from_product(left)
            right_non_const = _remove_const_from_product(right)
            
            if _hash_expr(left_non_const) == _hash_expr(right_non_const):
                combined_product = canonical(BinOp(new_const, "*", left_non_const))
                return combined_product
    
    return canonical(BinOp(left, "+", right_combined))


def _get_product_vars(expr: Expr) -> List[str]:
    """Get sorted list of variable names in a product."""
    if isinstance(expr, Var):
        return [expr.name]
    if isinstance(expr, BinOp) and expr.op == "*":
        return _get_product_vars(expr.left) + _get_product_vars(expr.right)
    return []


def _get_const_factor_in_product(expr: Expr) -> Optional[float]:
    """Get constant factor from a product expression."""
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, BinOp) and expr.op == "*":
        if isinstance(expr.left, Const) and expr.left.value is not None:
            return expr.left.value
        if isinstance(expr.right, Const) and expr.right.value is not None:
            return expr.right.value
    return None


def _remove_const_from_product(expr: Expr) -> Expr:
    """Remove constant factor from a product, returning the non-constant part."""
    if isinstance(expr, BinOp) and expr.op == "*":
        if isinstance(expr.left, Const):
            return expr.right
        if isinstance(expr.right, Const):
            return expr.left
    return expr
    
    left = expr.left
    right = expr.right
    op = expr.op
    
    if op == "**":
        expanded_base = _expand_product_sum(left)
        if expanded_base is not left:
            new_expr = BinOp(expanded_base, op, right)
        else:
            new_expr = expr
        
        if isinstance(right, Const) and isinstance(right.value, (int, float)):
            n = int(right.value)
            if n == 2 and isinstance(left, BinOp) and left.op == "+":
                a = left.left
                b = left.right
                a_sq = _expand_power(BinOp(a, "**", Const(2)))
                b_sq = _expand_power(BinOp(b, "**", Const(2)))
                a_b = canonical(BinOp(a, "*", b))
                b_a = canonical(BinOp(b, "*", a))
                two_ab = canonical(BinOp(Const(2), "*", a_b))
                return canonical(BinOp(BinOp(a_sq, "+", two_ab), "+", b_sq))
            
            if n >= 2 and n <= 10 and isinstance(left, BinOp) and left.op == "+":
                result = left
                for _ in range(n - 1):
                    result = canonical(BinOp(result, "*", left))
                return result
    
    if op == "*":
        left_exp = _expand_product_sum(left)
        right_exp = _expand_product_sum(right)
        
        if isinstance(left_exp, BinOp) and left_exp.op == "+":
            term1 = BinOp(left_exp.left, "*", right_exp)
            term2 = BinOp(left_exp.right, "*", right_exp)
            return canonical(BinOp(term1, "+", term2))
        
        if isinstance(right_exp, BinOp) and right_exp.op == "+":
            term1 = BinOp(left_exp, "*", right_exp.left)
            term2 = BinOp(left_exp, "*", right_exp.right)
            return canonical(BinOp(term1, "+", term2))
        
        if isinstance(left_exp, BinOp) and left_exp.op == "-":
            term1 = BinOp(left_exp.left, "*", right_exp)
            term2 = BinOp(left_exp.right, "*", right_exp)
            return canonical(BinOp(term1, "-", term2))
        
        if isinstance(right_exp, BinOp) and right_exp.op == "-":
            term1 = BinOp(left_exp, "*", right_exp.left)
            term2 = BinOp(left_exp, "*", right_exp.right)
            return canonical(BinOp(term1, "-", term2))
        
        expanded_left = _expand_power(BinOp(left_exp, "**", Const(2)))
        if expanded_left is not BinOp(left_exp, "**", Const(2)):
            return canonical(BinOp(expanded_left, "*", right_exp))
    
    return expr


def _get_sorted_vars_key(expr: Expr) -> Tuple[str, ...]:
    """Get a canonical key (sorted tuple) for variable comparison in products."""
    return tuple(sorted(_get_product_vars(expr)))


def _combine_like_terms_sum(expr: Expr) -> Expr:
    """Combine like terms in a sum by collecting all terms first."""
    if not isinstance(expr, BinOp) or expr.op != "+":
        return expr
    
    all_terms = _collect_all_terms_sum(expr)
    return _merge_terms_list_sum(all_terms)


def _collect_all_terms_sum(expr: Expr) -> List[Expr]:
    """Collect all terms from a sum into a flat list."""
    if isinstance(expr, BinOp) and expr.op == "+":
        return _collect_all_terms_sum(expr.left) + _collect_all_terms_sum(expr.right)
    return [expr]


def _merge_terms_list_sum(terms: List[Expr]) -> Expr:
    """Merge like terms from a flat list of terms."""
    term_map: Dict[Tuple[str, ...], Tuple[float, Expr]] = {}
    
    for term in terms:
        key = _get_sorted_vars_key(term)
        const = _get_const_factor_in_term(term) or 1.0
        
        if key in term_map:
            existing_const, _ = term_map[key]
            term_map[key] = (existing_const + const, term)
        else:
            term_map[key] = (const, term)
    
    if not term_map:
        return Const(0)
    
    merged = []
    for const, term in term_map.values():
        if const == 0:
            continue
        non_const = _get_non_const_part(term)
        if isinstance(non_const, Const):
            merged.append(Const(const))
        elif const == 1.0:
            merged.append(non_const)
        else:
            merged.append(canonical(BinOp(Const(const), "*", non_const)))
    
    merged.sort(key=lambda e: _hash_expr(e))
    result = merged[0]
    for t in merged[1:]:
        result = canonical(BinOp(result, "+", t))
    return result


def _get_const_factor_in_term(expr: Expr) -> float:
    """Get constant factor from a term (product or single const)."""
    if isinstance(expr, Const):
        return expr.value if expr.value is not None else 1.0
    if isinstance(expr, BinOp) and expr.op == "*":
        consts = []
        if isinstance(expr.left, Const) and expr.left.value is not None:
            consts.append(expr.left.value)
        if isinstance(expr.right, Const) and expr.right.value is not None:
            consts.append(expr.right.value)
        if consts:
            result = 1.0
            for c in consts:
                result *= c
            return result
    return 1.0


def _sort_binop_args(expr: BinOp) -> Expr:
    """Sort arguments of a multiplication for canonical comparison."""
    if expr.op == "*":
        left_h = _hash_expr(expr.left)
        right_h = _hash_expr(expr.right)
        if left_h > right_h:
            return BinOp(expr.right, expr.op, expr.left)
    return expr


def _get_const_factor(expr: BinOp) -> Optional[float]:
    """Get constant factor from a multiplication expression."""
    if expr.op == "*":
        if isinstance(expr.left, Const) and expr.left.value is not None:
            return expr.left.value
        if isinstance(expr.right, Const) and expr.right.value is not None:
            return expr.right.value
    return None


def _remove_const_factor(expr: BinOp) -> Expr:
    """Remove constant factor from a multiplication expression."""
    if expr.op == "*":
        if isinstance(expr.left, Const):
            return expr.right
        if isinstance(expr.right, Const):
            return expr.left
    return expr


def _try_expand(expr: Expr, max_terms: int = 200) -> Expr:
    """
    Try to expand an expression once. Returns the expanded form or the original.
    """
    if _count_terms(expr) > max_terms:
        return expr
    
    if isinstance(expr, BinOp):
        left_expanded = _try_expand(expr.left, max_terms)
        right_expanded = _try_expand(expr.right, max_terms)
        
        new_expr = BinOp(left_expanded, expr.op, right_expanded)
        
        if new_expr.op == "*":
            expanded = _expand_product_sum(new_expr)
            if expanded is not new_expr:
                return expanded
        
        if new_expr.op == "**":
            pow_expanded = _expand_power(new_expr)
            if pow_expanded is not new_expr:
                return pow_expanded
        
        return new_expr
    
    if isinstance(expr, UnOp):
        operand_expanded = _try_expand(expr.operand, max_terms)
        if operand_expanded is not expr.operand:
            return UnOp(expr.op, operand_expanded)
        return expr
    
    if isinstance(expr, Func):
        arg_expanded = _try_expand(expr.arg, max_terms)
        if arg_expanded is not expr.arg:
            return Func(arg_expanded, expr.op)
        return expr
    
    if isinstance(expr, Func2):
        arg1_expanded = _try_expand(expr.arg1, max_terms)
        arg2_expanded = _try_expand(expr.arg2, max_terms)
        if arg1_expanded is not expr.arg1 or arg2_expanded is not expr.arg2:
            return Func2(expr.name, arg1_expanded, arg2_expanded)
        return expr
    
    return expr


def _count_terms(e: Expr) -> int:
    """Quickly estimate term count without full canonicalization."""
    if isinstance(e, (Const, Var)):
        return 1
    if isinstance(e, UnOp):
        return _count_terms(e.operand)
    if isinstance(e, Func):
        return _count_terms(e.arg)
    if isinstance(e, Func2):
        return _count_terms(e.arg1) + _count_terms(e.arg2)
    if isinstance(e, BinOp):
        if e.op in ("+", "-"):
            return _count_terms(e.left) + _count_terms(e.right)
        if e.op == "*":
            left_terms = _count_terms(e.left)
            right_terms = _count_terms(e.right)
            if left_terms > 1 and right_terms > 1:
                return left_terms * right_terms
            return left_terms + right_terms
        return _count_terms(e.left) + _count_terms(e.right)
    return 1


def _expand_once(e: Expr, max_terms: int, depth: int) -> Expr:
    if depth > 20:
        return e
    if _count_terms(e) > max_terms:
        return e
    return _try_expand(e, max_terms)


def _canonical_once(e: Expr, depth: int) -> Expr:
    if depth > 50:
        return e
    return canonical(e, depth=depth)


def expand(expr: Expr, max_terms: int = 200) -> Expr:
    """
    Fully expand an algebraic expression.
    
    Applies:
    - Product of sums expansion: (a+b)*(c+d) -> a*c + a*d + b*c + b*d
    - Power of sum expansion: (a+b)^2 -> a^2 + 2*a*b + b^2
    
    :param expr: Expression to expand
    :param max_terms: Maximum number of terms before bailing out
    :return: Fully expanded expression
    """
    result = expr
    for _ in range(3):
        if _count_terms(result) > max_terms:
            break
        expanded = _expand_once(result, max_terms, 0)
        if str(expanded) == str(result):
            break
        result = expanded
    
    return result


def expand_and_canonicalize(expr: Expr, max_terms: int = 500) -> Expr:
    """
    Expand and then canonicalize an expression.
    
    This is the recommended function for getting a canonical form
    that handles algebraic expansion.
    
    :param expr: Expression to process
    :param max_terms: Maximum number of terms before bailing out (prevents exponential blowup)
    :return: Expanded and canonicalized expression
    """
    if _count_terms(expr) > max_terms:
        return expr
    
    result = _expand_once(expr, max_terms, 0)
    
    for _ in range(3):
        canonicalized = _canonical_once(result, 0)
        if str(canonicalized) == str(result):
            break
        result = canonicalized
        
        expanded2 = _expand_once(result, max_terms, 0)
        if str(expanded2) == str(result):
            break
        result = expanded2
    
    return result


def structural_hash_expanded(expr: Expr) -> str:
    """
    Compute structural hash with algebraic expansion.
    
    This version expands expressions before hashing, so that
    (x+1)^2 and x^2+2x+1 produce the same hash.
    
    :param expr: Expression to hash
    :return: Hex string hash (32 chars)
    """
    canon = expand_and_canonicalize(expr)
    return _hash_expr(canon)


def equivalent_expanded(e1: Expr, e2: Expr) -> bool:
    """
    Check if two expressions are mathematically equivalent using expansion.
    
    This version uses algebraic expansion before comparison, so that
    (x+1)^2 and x^2+2x+1 are considered equivalent.
    
    :param e1: First expression
    :param e2: Second expression
    :return: True if equivalent
    """
    if e1 is e2:
        return True
    h1 = structural_hash_expanded(e1)
    h2 = structural_hash_expanded(e2)
    return h1 == h2


def _eval_func(op: str, value: float) -> float:
    """Evaluate a unary function at a constant value."""
    import math
    if op == "sin":
        return math.sin(value)
    if op == "cos":
        return math.cos(value)
    if op == "tan":
        return math.tan(value)
    if op == "exp":
        return math.exp(value)
    if op == "log":
        return math.log(value)
    if op == "sqrt":
        return math.sqrt(value)
    if op == "asin":
        return math.asin(value)
    if op == "acos":
        return math.acos(value)
    if op == "atan":
        return math.atan(value)
    if op == "sinh":
        return math.sinh(value)
    if op == "cosh":
        return math.cosh(value)
    if op == "tanh":
        return math.tanh(value)
    if op == "abs":
        return abs(value)
    if op == "floor":
        return math.floor(value)
    if op == "ceil":
        return math.ceil(value)
    if op == "heaviside":
        return 0.0 if value <= 0 else 1.0
    raise ValueError(f"Cannot evaluate function {op}")


def structural_hash(expr: Expr) -> str:
    """
    Compute a deterministic structural hash for an expression.
    
    Properties:
    - Independent of node UIDs
    - Order-invariant for commutative operators (+, *)
    - Includes operator type and structure
    
    :param expr: Expression to hash
    :return: Hex string hash (32 chars)
    """
    canon = canonical(expr)
    return _hash_expr(canon)


def _hash_expr(expr: Expr) -> str:
    """Recursively compute hash of a canonical expression."""
    if isinstance(expr, Const):
        type_key, norm_val = _canonical_const(expr.value)
        h = hashlib.sha256()
        h.update(f"Const:{type_key}:{norm_val}".encode())
        return h.hexdigest()

    if isinstance(expr, Var):
        h = hashlib.sha256()
        h.update(f"Var:{expr.name}".encode())
        return h.hexdigest()

    if isinstance(expr, UnOp):
        h = hashlib.sha256()
        h.update(f"UnOp:{expr.op}:{_hash_expr(expr.operand)}".encode())
        return h.hexdigest()

    if isinstance(expr, BinOp):
        h = hashlib.sha256()
        child_hash = _hash_expr(expr.left) + _hash_expr(expr.right)
        if expr.op in CommutativeOps:
            child_hash = "".join(sorted(child_hash))
        h.update(f"BinOp:{expr.op}:{child_hash}".encode())
        return h.hexdigest()

    if isinstance(expr, Func):
        h = hashlib.sha256()
        h.update(f"Func:{expr.op}:{_hash_expr(expr.arg)}".encode())
        return h.hexdigest()

    if isinstance(expr, Func2):
        h = hashlib.sha256()
        arg_hash = _hash_expr(expr.arg1) + _hash_expr(expr.arg2)
        if expr.name in {"min", "max"}:
            arg_hash = "".join(sorted([_hash_expr(expr.arg1), _hash_expr(expr.arg2)]))
        h.update(f"Func2:{expr.name}:{arg_hash}".encode())
        return h.hexdigest()

    raise TypeError(f"Unknown expression type: {type(expr)}")


def to_dag(expr: Expr, memo: Optional[Dict[str, DAGNode]] = None) -> DAGNode:
    """
    Convert an expression to a DAG with deduplication.
    
    Nodes are deduplicated by structural hash, so identical
    subexpressions share the same DAG node.
    
    :param expr: Expression to convert
    :param memo: Optional memoization dict (structural_hash -> DAGNode)
    :return: DAGNode root
    """
    if memo is None:
        memo = {}

    canon = canonical(expr)
    return _to_dag_recursive(canon, memo)


def _to_dag_recursive(expr: Expr, memo: Dict[str, DAGNode]) -> DAGNode:
    """Recursively build DAG with memoization."""
    h = _hash_expr(expr)

    if h in memo:
        return memo[h]

    if isinstance(expr, Const):
        node = DAGNode(op="Const", children=[], structural_hash=h, expr=expr)
        memo[h] = node
        return node

    if isinstance(expr, Var):
        node = DAGNode(op=f"Var:{expr.name}", children=[], structural_hash=h, expr=expr)
        memo[h] = node
        return node

    if isinstance(expr, UnOp):
        child = _to_dag_recursive(expr.operand, memo)
        node = DAGNode(op=f"UnOp:{expr.op}", children=[child], structural_hash=h, expr=expr)
        memo[h] = node
        return node

    if isinstance(expr, BinOp):
        left = _to_dag_recursive(expr.left, memo)
        right = _to_dag_recursive(expr.right, memo)
        children = [left, right]
        if expr.op in CommutativeOps:
            children = sorted(children, key=lambda n: n.structural_hash)
        node = DAGNode(op=f"BinOp:{expr.op}", children=children, structural_hash=h, expr=expr)
        memo[h] = node
        return node

    if isinstance(expr, Func):
        arg = _to_dag_recursive(expr.arg, memo)
        node = DAGNode(op=f"Func:{expr.op}", children=[arg], structural_hash=h, expr=expr)
        memo[h] = node
        return node

    if isinstance(expr, Func2):
        arg1 = _to_dag_recursive(expr.arg1, memo)
        arg2 = _to_dag_recursive(expr.arg2, memo)
        children = [arg1, arg2]
        if expr.name in {"min", "max"}:
            children = sorted(children, key=lambda n: n.structural_hash)
        node = DAGNode(op=f"Func2:{expr.name}", children=children, structural_hash=h, expr=expr)
        memo[h] = node
        return node

    raise TypeError(f"Unknown expression type: {type(expr)}")


def equivalent(e1: Expr, e2: Expr) -> bool:
    """
    Check if two expressions are mathematically equivalent.
    
    Uses canonicalization and structural hashing for O(1) comparison
    after canonical form is computed.
    
    :param e1: First expression
    :param e2: Second expression
    :return: True if equivalent
    """
    if e1 is e2:
        return True
    h1 = structural_hash(e1)
    h2 = structural_hash(e2)
    return h1 == h2


def equivalent_systems(sys1: List[Expr], sys2: List[Expr]) -> bool:
    """
    Check if two systems of equations are equivalent.
    
    Systems are equivalent if they contain the same equations
    in any order. Each equation is compared using structural
    canonical hashing.
    
    :param sys1: First list of equations
    :param sys2: Second list of equations
    :return: True if equivalent systems
    """
    if len(sys1) != len(sys2):
        return False

    hashes1 = sorted(structural_hash(e) for e in sys1)
    hashes2 = sorted(structural_hash(e) for e in sys2)

    return hashes1 == hashes2


def equations_equivalent(eq1: Expr, eq2: Expr) -> bool:
    """
    Check if two equations are equivalent.
    
    An equation is treated as a BinOp with operator "=".
    Two equations are equivalent if their canonical forms match.
    
    :param eq1: First equation (typically BinOp with op="=")
    :param eq2: Second equation
    :return: True if equivalent
    """
    if not isinstance(eq1, BinOp) or not isinstance(eq2, BinOp):
        return structural_hash(eq1) == structural_hash(eq2)

    lhs1_hash = structural_hash(eq1.left)
    lhs2_hash = structural_hash(eq2.left)
    rhs1_hash = structural_hash(eq1.right)
    rhs2_hash = structural_hash(eq2.right)

    if lhs1_hash == lhs2_hash and rhs1_hash == rhs2_hash:
        return True
    if lhs1_hash == rhs2_hash and rhs1_hash == lhs2_hash:
        return True

    diff1 = canonical(BinOp(eq1.left, "-", eq1.right))
    diff2 = canonical(BinOp(eq2.left, "-", eq2.right))
    return structural_hash(diff1) == structural_hash(diff2)


def get_canonical_form(expr: Expr) -> Expr:
    """
    Get the canonical form of an expression.
    
    This is a convenience alias for canonical().
    
    :param expr: Expression to canonicalize
    :return: Canonical expression
    """
    return canonical(expr)


def get_structural_hash(expr: Expr) -> str:
    """
    Get the structural hash of an expression.
    
    This is a convenience alias for structural_hash().
    
    :param expr: Expression to hash
    :return: Hex string hash
    """
    return structural_hash(expr)


def dag_to_string(node: DAGNode, indent: int = 0) -> str:
    """Generate a string representation of a DAG for debugging."""
    prefix = "  " * indent
    if not node.children:
        return f"{prefix}{node.op}"
    children_str = [dag_to_string(c, indent + 1) for c in node.children]
    return f"{prefix}{node.op} -> [\n" + ",\n".join(children_str) + f"\n{prefix}]"


def simplify_deep(expr: Expr) -> Expr:
    """
    Deep simplification with algebraic expansion and canonicalization.
    
    Unlike the built-in simplify(), this applies expansion and 
    canonicalization recursively and handles more cases including
    polynomial equivalence.
    
    :param expr: Expression to simplify
    :return: Simplified expression
    """
    result = expand_and_canonicalize(expr)
    prev_str = str(result)
    for _ in range(10):
        new_result = expand_and_canonicalize(result)
        if str(new_result) == prev_str:
            break
        prev_str = str(new_result)
        result = new_result
    return result


__all__ = [
    "canonical",
    "structural_hash",
    "structural_hash_expanded",
    "to_dag",
    "DAGNode",
    "equivalent",
    "equivalent_expanded",
    "equivalent_systems",
    "equations_equivalent",
    "get_canonical_form",
    "get_structural_hash",
    "dag_to_string",
    "simplify_deep",
    "expand",
    "expand_and_canonicalize",
    "_hash_expr",
    "variables_in_corresponding_attributes",
]