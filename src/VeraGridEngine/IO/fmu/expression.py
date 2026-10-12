# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.enumerations import Precedence
from typing import Any


from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, CmpOp, Comparison, Const, Expr, Func, Func2, UnOp, Var


class RenderedExpr:
    """Rendered C expression and its precedence."""

    __slots__ = ("code", "precedence")

    def __init__(self, code: str, precedence: Precedence) -> None:
        """:param code: C source for the expression.
        :param precedence: Precedence used when embedding the expression.
        """
        self.code = code
        self.precedence = precedence


def _wrap(rendered: RenderedExpr, parent: Precedence, *, allow_equal: bool = False) -> str:
    """Execute the `_wrap` operation.

    :param rendered: Function input.
    :param parent: Function input.
    :param allow_equal: Function input.
    :return: Function result.
    """
    if rendered.precedence > parent or (allow_equal and rendered.precedence == parent):
        return rendered.code
    return f"({rendered.code})"


def _number_literal(value: float | int | bool | None) -> str:
    """Execute the `_number_literal` operation.

    :param value: Function input.
    :return: Function result.
    """
    if value is None:
        return "0.0"
    if isinstance(value, bool):
        return "1.0" if value else "0.0"
    if isinstance(value, int):
        return f"{value}.0"
    text = format(float(value), ".17g")
    if "e" not in text and "." not in text:
        text = f"{text}.0"
    return text


class ExprToCVisitor:
    __slots__ = ("resolver",)

    def __init__(self, resolver: Any):
        """Initialize the object state.

        :param resolver: Function input.
        :return: None.
        """
        self.resolver = resolver

    def render(self, expr: Expr | Comparison | float | int | bool) -> str:
        """Execute the `render` operation.

        :param expr: Function input.
        :return: Function result.
        """
        return self.visit(expr).code

    def visit(self, expr: Expr | Comparison | float | int | bool) -> RenderedExpr:
        """Execute the `visit` operation.

        :param expr: Function input.
        :return: Function result.
        """
        if isinstance(expr, (int, float, bool)):
            return RenderedExpr(_number_literal(expr), Precedence.ATOM)
        if isinstance(expr, Const):
            return RenderedExpr(_number_literal(expr.value), Precedence.ATOM)
        if isinstance(expr, Var):
            special = self.resolver.resolve_special(expr.name)
            if special is not None:
                return RenderedExpr(special, Precedence.ATOM)
            return RenderedExpr(self.resolver.resolve_var(expr.uid), Precedence.ATOM)
        if isinstance(expr, BinOp):
            return self.visit_binop(expr)
        if isinstance(expr, UnOp):
            return self.visit_unop(expr)
        if isinstance(expr, Func):
            return self.visit_func(expr)
        if isinstance(expr, Func2):
            return self.visit_func2(expr)
        if isinstance(expr, Comparison):
            return self.visit_comparison(expr)
        raise ValueError(f"Unsupported expression node: {type(expr).__name__}")

    def visit_binop(self, expr: BinOp) -> RenderedExpr:
        """Execute the `visit_binop` operation.

        :param expr: Function input.
        :return: Function result.
        """
        left = self.visit(expr.left)
        right = self.visit(expr.right)
        if expr.op == "**":
            return RenderedExpr(f"pow({_wrap(left, Precedence.CALL)}, {_wrap(right, Precedence.CALL)})", Precedence.CALL)
        if expr.op in {"+", "-"}:
            return RenderedExpr(
                f"{_wrap(left, Precedence.ADDITIVE, allow_equal=True)} {expr.op} {_wrap(right, Precedence.ADDITIVE)}",
                Precedence.ADDITIVE,
            )
        if expr.op in {"*", "/"}:
            return RenderedExpr(
                f"{_wrap(left, Precedence.MULTIPLICATIVE, allow_equal=True)} {expr.op} {_wrap(right, Precedence.MULTIPLICATIVE)}",
                Precedence.MULTIPLICATIVE,
            )
        raise ValueError(f"Unsupported binary operator {expr.op!r}")

    def visit_unop(self, expr: UnOp) -> RenderedExpr:
        """Execute the `visit_unop` operation.

        :param expr: Function input.
        :return: Function result.
        """
        if expr.op != "-":
            raise ValueError(f"Unsupported unary operator {expr.op!r}")
        operand = self.visit(expr.operand)
        return RenderedExpr(f"-{_wrap(operand, Precedence.UNARY)}", Precedence.UNARY)

    def visit_func(self, expr: Func) -> RenderedExpr:
        """Execute the `visit_func` operation.

        :param expr: Function input.
        :return: Function result.
        """
        c_name = {
            "sin": "sin",
            "cos": "cos",
            "tan": "tan",
            "exp": "exp",
            "log": "vg_safe_log",
            "sqrt": "vg_safe_sqrt",
            "abs": "fabs",
            "heaviside": "vg_heaviside",
            "asin": "asin",
            "acos": "acos",
            "atan": "atan",
            "sinh": "sinh",
            "cosh": "cosh",
        }.get(expr.op)
        if c_name is None:
            raise ValueError(f"Unsupported function {expr.op!r}")
        arg = self.visit(expr.arg)
        return RenderedExpr(f"{c_name}({_wrap(arg, Precedence.CALL)})", Precedence.CALL)

    def visit_func2(self, expr: Func2) -> RenderedExpr:
        """Execute the `visit_func2` operation.

        :param expr: Function input.
        :return: Function result.
        """
        c_name = {"atan2": "atan2", "min": "fmin", "max": "fmax"}.get(expr.name)
        if c_name is None:
            raise ValueError(f"Unsupported binary function {expr.name!r}")
        arg1 = self.visit(expr.arg1)
        arg2 = self.visit(expr.arg2)
        return RenderedExpr(
            f"{c_name}({_wrap(arg1, Precedence.CALL)}, {_wrap(arg2, Precedence.CALL)})",
            Precedence.CALL,
        )

    def visit_comparison(self, expr: Comparison) -> RenderedExpr:
        """Execute the `visit_comparison` operation.

        :param expr: Function input.
        :return: Function result.
        """
        left = self.visit(expr.lhs)
        right = self.visit(expr.rhs if isinstance(expr.rhs, Expr) else Const(float(expr.rhs)))
        if expr.op == CmpOp.LE:
            cmp = "<="
        elif expr.op == CmpOp.GE:
            cmp = ">="
        elif expr.op == CmpOp.LT:
            cmp = "<"
        elif expr.op == CmpOp.GT:
            cmp = ">"
        elif expr.op == CmpOp.EQ:
            return RenderedExpr(f"(fabs({_wrap(left, Precedence.CALL)} - {_wrap(right, Precedence.CALL)}) <= 1e-9 ? 1.0 : 0.0)", Precedence.CALL)
        else:
            raise ValueError(f"Unsupported comparison operator {expr.op!r}")
        return RenderedExpr(
            f"(({_wrap(left, Precedence.COMPARISON)}) {cmp} ({_wrap(right, Precedence.COMPARISON)}) ? 1.0 : 0.0)",
            Precedence.CALL,
        )
