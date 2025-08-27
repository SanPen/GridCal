# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import highspy
from typing import Dict, List, Union, cast, Tuple, Protocol, runtime_checkable
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const, BinOp, CmpOp, Comparison

INF = 1.0e20
LOWER_INF  = -1.0e20
Number = Union[int, float]


@runtime_checkable
class _AB(Protocol):
    a: Expr
    b: Expr


@runtime_checkable
class _LeftRight(Protocol):
    left: Expr
    right: Expr


@runtime_checkable
class _LhsRhs(Protocol):
    lhs: Expr
    rhs: Expr


# Union of all accepted layouts (for static checkers / IDEs)
_BinChildrenT = Tuple[Expr, Expr]


def _binop_children(node: BinOp) -> _BinChildrenT:
    """
    Return the two operands of *node*.

    Accepted layouts (checked **statically** and **at runtime**):

      • .a / .b
      • .left / .right
      • .lhs / .rhs

    Anything else raises ``TypeError`` immediately.
    """
    if isinstance(node, _AB):
        return cast(_BinChildrenT, (node.a, node.b))

    if isinstance(node, _LeftRight):
        return cast(_BinChildrenT, (node.left, node.right))

    if isinstance(node, _LhsRhs):
        return cast(_BinChildrenT, (node.lhs, node.rhs))

    raise TypeError(
        "BinOp implementation must expose either "
        "('a','b'), ('left','right') or ('lhs','rhs') attributes "
        f"(got {type(node).__name__})."
    )


# =====================================================================
#  Affine extractor  (no lambdas, no nested fns)
# =====================================================================
def _combine(dst: Dict[Var, float], src: Dict[Var, float]) -> None:
    for v, k in src.items():
        dst[v] = dst.get(v, 0.0) + k


def _affine_parts(node: Expr, scale: float = 1.0) -> Tuple[Dict[Var, float], float]:
    if isinstance(node, Const):
        return {}, scale * float(node.value)

    if isinstance(node, Var):
        return {node: scale}, 0.0

    if isinstance(node, BinOp):
        op = getattr(node, "op", None)
        a, b = _binop_children(node)

        if op == "+":
            ca, ka = _affine_parts(a, scale)
            cb, kb = _affine_parts(b, scale)
            _combine(ca, cb)
            return ca, ka + kb

        if op == "-":
            ca, ka = _affine_parts(a, scale)
            cb, kb = _affine_parts(b, -scale)
            _combine(ca, cb)
            return ca, ka + kb

        if op == "*":
            if isinstance(a, Const):
                return _affine_parts(b, scale * float(a.value))
            if isinstance(b, Const):
                return _affine_parts(a, scale * float(b.value))

    raise ValueError("expression is not affine")


@dataclass(frozen=True, slots=True)
class LinExpr:
    """
    Linear expression
    """
    coeffs: Dict[Var, float]
    constant: float = 0.0

    @staticmethod
    def from_expr(expr: Expr) -> "LinExpr":
        c, k = _affine_parts(expr, 1.0)
        return LinExpr(c, k)

    # simple arith
    def __add__(self, other: "LinExpr") -> "LinExpr":
        d = self.coeffs.copy()
        _combine(d, other.coeffs)
        return LinExpr(d, self.constant + other.constant)

    def __sub__(self, other: "LinExpr") -> "LinExpr":
        d = self.coeffs.copy()
        for v, k in other.coeffs.items():
            d[v] = d.get(v, 0.0) - k
        return LinExpr(d, self.constant - other.constant)

@dataclass(frozen=True, slots=True)
class Constraint:
    expr: "LinExpr"                 # constant term is 0
    lhs: float = LOWER_INF
    rhs: float = INF

    # central builder -------------------------------------------------
    @staticmethod
    def from_sides(lhs: LinExpr | Expr | Number,
                   op:  CmpOp,
                   rhs: LinExpr | Expr | Number) -> "Constraint":
        lhs_lin = _to_lin(lhs)
        rhs_lin = _to_lin(rhs)
        diff    = lhs_lin - rhs_lin           # lhs − rhs
        cst     = diff.constant
        expr    = LinExpr(diff.coeffs, 0.0)   # strip constant

        if op is CmpOp.LE:
            return Constraint(expr, LOWER_INF, -cst)
        if op is CmpOp.GE:
            return Constraint(expr, -cst, INF)
        if op is CmpOp.EQ:
            return Constraint(expr, -cst, -cst)
        raise ValueError("Unknown comparison op")

    # helper factories (optional) ------------------------------------
    @classmethod
    def leq(cls, expr: "LinExpr | Expr", rhs: Number) -> "Constraint":
        return cls(expr=_to_lin(expr), lhs=LOWER_INF, rhs=float(rhs))

    @classmethod
    def geq(cls, expr: "LinExpr | Expr", rhs: Number) -> "Constraint":
        return cls(expr=_to_lin(expr), lhs=float(rhs), rhs=INF)

    @classmethod
    def eq(cls, expr: "LinExpr | Expr", rhs: Number) -> "Constraint":
        r = float(rhs)
        return cls(expr=_to_lin(expr), lhs=r, rhs=r)


def _as_constraint(obj: Union[Constraint, Comparison, tuple["Expr | Number", CmpOp, "Expr | Number"]]) -> Constraint:
    """

    :param obj:
    :return:
    """
    if isinstance(obj, Constraint):
        return obj

    if isinstance(obj, Comparison):
        return Constraint.from_sides(obj.lhs, obj.op, obj.rhs)

    if isinstance(obj, tuple) and len(obj) == 3:
        lhs, op, rhs = obj
        return Constraint.from_sides(lhs, op, rhs)

    raise TypeError("Invalid constraint specification")

@dataclass
class Result:
    status: str
    objective: float | None
    primal: Dict[Var, float]
    dual_row: List[float]


@dataclass(slots=True)
class _LinVarExtension:
    """
    Internal data that extends Var to have LP limits
    Users don't need to edit this later
    """
    var: Var
    low: float = -INF
    up: float = INF
    integer: bool = False
    start: float = 0.0


def _to_lin(val: Union[LinExpr, Expr, Number]) -> LinExpr:
    if isinstance(val, LinExpr):
        return val
    if isinstance(val, (int, float)):
        return LinExpr({}, float(val))
    return LinExpr.from_expr(val)


class LPModel:
    """
    LPModel
    """

    def __init__(self) -> None:

        # vars data
        self._var_dict: Dict[Var, int] = dict()
        self._low: List[float] = list()
        self._up: List[float] = list()
        self._integer: List[bool] = list()
        self._start: List[float] = list()

        self._any_int: bool = False

        self._constraints: List[Constraint] = list()
        self._objective: LinExpr | None = None
        self._sense: str = "min"  # or "max"

    # -----------------------------------------------------------------
    # variables
    # -----------------------------------------------------------------
    def add_var(self, name: str, low: float = -INF, up: float = INF, integer: bool = False, start: float = 0.0) -> Var:
        v = Var(name)
        i = len(self._low)
        self._var_dict[v] = i
        self._low.append(low)
        self._up.append(up)
        self._integer.append(integer)
        self._start.append(start)

        if integer:
            self._any_int = True

        return v

    # -----------------------------------------------------------------
    # objective & constraints
    # -----------------------------------------------------------------
    def minimise(self, expr: Expr) -> None:
        self._sense = "min"
        self._objective = LinExpr.from_expr(expr)

    def maximise(self, expr: Expr) -> None:
        self._sense = "max"
        self._objective = LinExpr.from_expr(expr)

    def __iadd__(self, cons: Constraint | Expr) -> "LPModel":
        self._constraints.append(_as_constraint(cons))
        return self

    # -----------------------------------------------------------------
    # HiGHS solve
    # -----------------------------------------------------------------
    def solve(self) -> Result:
        if self._objective is None:
            raise RuntimeError("objective not set")

        num_col = len(self._up)
        num_row = len(self._constraints)
        col_cost = np.zeros(num_col)

        for v, coef in self._objective.coeffs.items():
            i = self._var_dict[v]
            col_cost[i] = coef

        # --- rows & sparse matrix ------------------------------------
        row_low, row_up = [], []
        astart, aindex, avalue = [0], [], []

        for cons in self._constraints:
            row_low.append(cons.lhs)  # a·x = –c
            row_up.append(cons.rhs)

            # sparse coeffs (no constant term)
            for v, coef in cons.expr.coeffs.items():
                if coef != 0.0:
                    aindex.append(self._var_dict[v])
                    avalue.append(coef)
            astart.append(len(aindex))

        # -------- build HighsLp ---------------------------------------
        lp = highspy.HighsLp()
        lp.num_col_ = num_col
        lp.num_row_ = num_row
        lp.col_cost_ = col_cost.tolist()
        lp.col_lower_ = self._low
        lp.col_upper_ = self._up
        lp.row_lower_ = row_low
        lp.row_upper_ = row_up

        mat = lp.a_matrix_
        mat.format_ = highspy.MatrixFormat.kRowwise
        mat.num_col_ = num_col
        mat.num_row_ = num_row
        mat.start_ = np.array(astart, dtype=np.int32)
        mat.index_ = np.array(aindex, dtype=np.int32)
        mat.value_ = np.array(avalue, dtype=np.double)

        if self._any_int:
            highs_int_flags = list()
            for i in self._integer:
                if i:
                    highs_int_flags.append(highspy.HighsVarType.kInteger)
                else:
                    highs_int_flags.append(highspy.HighsVarType.kContinuous)

            lp.integrality_ = highs_int_flags

        lp.sense_ = (highspy.ObjSense.kMinimize
                     if self._sense == "min"
                     else highspy.ObjSense.kMaximize)

        h = highspy.Highs()
        h.passModel(lp)

        # warm start
        # if warm_start:
        #     h.setSolution(highspy.HighsSolution(col_value=self._start))

        h.run()

        sol = h.getSolution()
        info = h.getInfo()

        status = str(h.getModelStatus())
        primal = {var: sol.col_value[i] for var, i in self._var_dict.items()}

        return Result(
            status=status,
            objective=info.objective_function_value,
            primal=primal,
            dual_row=list(sol.row_dual),
        )


# =====================================================================
#  Demo problems
# =====================================================================
def diet_problem() -> None:
    m = LPModel()
    bread = m.add_var("bread")
    milk = m.add_var("milk")

    m.minimise(0.5 * bread + 0.7 * milk)
    m += 4 * bread + 8 * milk <= 50
    m += bread + 6 * milk >= 30

    res = m.solve()
    print("Diet:", res.status, res.objective)
    print({v.name: res.primal[v] for v in (bread, milk)})


def knapsack_demo() -> None:
    m = LPModel()
    items = [("guitar", 6, 30), ("laptop", 3, 20), ("iphone", 1, 15)]
    choose: Dict[str, Var] = {n: m.add_var(n, integer=True, low=0, up=1) for n, _, _ in items}

    value = sum(v * choose[n] for n, _, v in items)
    weight = sum(w * choose[n] for n, w, _ in items)

    m.maximise(value)
    m += weight <= 7

    res = m.solve()
    print("Knapsack:", res.status, res.objective)
    print({k: res.primal[v] for k, v in choose.items()})


if __name__ == "__main__":
    diet_problem()
    knapsack_demo()
