# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import copy
import json
import math
import ast
import uuid
import builtins
import numpy as np
from enum import Enum
import numba as nb

from typing import Any, Dict, Mapping, Union, List, Sequence, Tuple, Set, Optional

from VeraGridEngine.enumerations import VarPowerFlowReferenceType


NUMBER = Union[int, float, complex]


# -----------------------------------------------------------------------------
# UUID helper
# -----------------------------------------------------------------------------

def _new_uid() -> int:
    """Generate a fresh UUID‑v4 string."""
    return uuid.uuid4().int


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------


def _to_expr(val: Any) -> "Expr":
    """

    returns an expression

    :param val:
    :type val: Union[VeraGridEngine.Utils.Symbolic.symbolic.Const, VeraGridEngine.Utils.Symbolic.symbolic.Var, int, float, VeraGridEngine.Utils.Symbolic.symbolic.Func, complex, VeraGridEngine.Utils.Symbolic.symbolic.BinOp, VeraGridEngine.Utils.Symbolic.symbolic.DiffVar, VeraGridEngine.Utils.Symbolic.symbolic.UnOp]
    :return:
    :rtype: Union[VeraGridEngine.Utils.Symbolic.symbolic.Const, VeraGridEngine.Utils.Symbolic.symbolic.Var, VeraGridEngine.Utils.Symbolic.symbolic.Func, VeraGridEngine.Utils.Symbolic.symbolic.BinOp, VeraGridEngine.Utils.Symbolic.symbolic.DiffVar, VeraGridEngine.Utils.Symbolic.symbolic.UnOp]
    """
    if isinstance(val, Expr):
        return val
    if isinstance(val, (int, float, complex)):
        return Const(val)
    if val is None:
        return Const(None)
    raise TypeError(f"Cannot convert {val!r} to Expr")


# ----------------------------------------------------------------------------
# Function helpers
# ----------------------------------------------------------------------------


class SharedVarReferenceType:
    __slots__ = ("name", "uid")
    # this class is related to var factory, and a dictionary contains all the "shared vars" that have a certain reference.
    def __init__(self, name: str, uid: int| None = None):
        """Create an identity shared by variables that represent one signal.

        :param name: Human-readable name of the shared signal reference.
        :param uid: Existing reference identifier, or ``None`` to allocate one.
        """
        self.uid: int = _new_uid() if uid is None else uid
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if not isinstance(other, SharedVarReferenceType):
            return NotImplemented
        return self.uid == other.uid

    def __hash__(self):
        return hash(self.uid)


class CmpOp(Enum):
    """
    comparisons
    """
    __slots__ = ()

    LE = "≤"  # ≤
    GE = "≥"  # ≥
    LT = "<"
    GT = ">"
    EQ = "="  # =


class Comparison:
    """
    Symbolic comparison wrapper.

    :param lhs: Left-hand side symbolic expression.
    :param op: Comparison operator.
    :param rhs: Right-hand side symbolic expression or numeric value.
    """

    __slots__ = ("lhs", "op", "rhs")

    def __init__(self, lhs: "Expr", op: CmpOp, rhs: "Expr | NUMBER"):
        """
        Comparison constructor
        :param lhs: Left-hand side
        :param op: operator
        :param rhs: Right-hand side
        """
        self.lhs: Expr = lhs
        self.op: CmpOp = op
        self.rhs: Expr | NUMBER = rhs

    def to_expression(self) -> "Expr":
        """
        Convert the comparison into a heaviside-based symbolic expression.

        :return: Equivalent symbolic expression.
        """
        rhs_expr: Expr = _to_expr(self.rhs)
        eps: Const = Const(1e-6)
        if self.op == CmpOp.LT:
            return heaviside(rhs_expr - self.lhs - eps)
        elif self.op == CmpOp.LE:
            return heaviside(rhs_expr - self.lhs + eps)
        elif self.op == CmpOp.GT:
            return heaviside(self.lhs - rhs_expr - eps)
        elif self.op == CmpOp.GE:
            return heaviside(self.lhs - rhs_expr + eps)
        elif self.op == CmpOp.EQ:
            return heaviside(self.lhs - rhs_expr + eps) * heaviside(rhs_expr - self.lhs + eps)
        else:
            raise ValueError(f"operator not supported {self.op}")

    def __repr__(self) -> str:
        return f"Comparison(lhs={self.lhs!r}, op={self.op!r}, rhs={self.rhs!r})"

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Comparison":
        rhs_expr: Expr = _to_expr(self.rhs)
        return Comparison(self.lhs.subs(mapping), self.op, rhs_expr.subs(mapping))

    def to_residual(self) -> "Expr":
        rhs_expr: Expr = _to_expr(self.rhs)
        if self.op in (CmpOp.LE, CmpOp.LT):
            return self.lhs - rhs_expr
        elif self.op in (CmpOp.GE, CmpOp.GT):
            return rhs_expr - self.lhs
        elif self.op == CmpOp.EQ:
            return self.lhs - rhs_expr
        else:
            raise ValueError(f"operator not supported {self.op}")


class Expr:
    """
    Abstract base class for all expression nodes.
    """

    __slots__ = ("uid",)

    def __init__(self, uid: int | None = None):
        """

        :param uid: (optional UID)
        """
        self.uid: int = _new_uid() if uid is None else uid

    def eval(self, **bindings: float | int) -> float | int:  # pragma: no cover – abstract
        """
        Numeric evaluation
        :param bindings:
        :return:
        """
        raise NotImplementedError

    def eval_uid(self, uid_bindings: Dict[int, float]) -> NUMBER:  # pragma: no cover – abstract
        """

        :param uid_bindings:
        :return:
        """
        raise NotImplementedError

    __call__ = eval  # allow f(x=…)

    def diff(self, var: Var | str, order: int = 1, dt: Var | None = None) -> "Expr":
        """
        Differentiation (higher‑order)
        :param var:
        :param order:
        :param dt:
        :return:
        """
        if order < 0:
            raise ValueError("order must be >= 0")
        expr: Expr = self
        for _ in range(order):
            expr = expr._diff1(var, dt).simplify()
        return expr

    def _diff1(self, var: Var | str, dt: Var | None) -> Expr:
        raise NotImplementedError

    def simplify(self) -> "Expr":
        """
        Simplification & substitution (no‑ops by default)
        :return:
        """
        return self

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Expr":
        """
        substitute variables
        :param mapping:
        :type mapping:
        :return:
        :rtype:
        """
        return mapping.get(self, self)

    def contains_var(self, var: Var) -> bool:
        """
        Check if this expression contains the given variable.
        :param var: Variable to search for.
        :return: True if var is in this expression.
        """
        return False

    def to_dict(self) -> Dict[str, Any]:
        """
        returns a dictionary

        :return:
        :rtype:
        """
        return _expr_to_dict(self)

    def to_json(self, **json_kwargs: Any) -> str:
        return json.dumps(self.to_dict(), **json_kwargs)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Expr":
        return _dict_to_expr(data)

    @staticmethod
    def from_json(blob: str) -> "Expr":
        return _dict_to_expr(json.loads(blob))

    # ------------------------------------------------------------------
    # Operator helpers
    # ------------------------------------------------------------------
    def __add__(self, other: Any) -> Expr:
        return BinOp(self, "+", _to_expr(other))

    def __radd__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "+", self)

    def __sub__(self, other: Any) -> Expr:
        return BinOp(self, "-", _to_expr(other))

    def __rsub__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "-", self)

    def __mul__(self, other: Any) -> Expr:
        return BinOp(self, "*", _to_expr(other))

    def __rmul__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "*", self)

    def __truediv__(self, other: Any) -> Expr:
        return BinOp(self, "/", _to_expr(other))

    def __rtruediv__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "/", self)

    def __pow__(self, other: Any) -> Expr:
        return BinOp(self, "**", _to_expr(other))

    def __rpow__(self, other: Any) -> Expr:
        return BinOp(_to_expr(other), "**", self)

    def __neg__(self) -> "Expr":
        return UnOp("-", self)

    def __le__(self, other: Expr | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.LE, other)

    def __ge__(self, other: Expr | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.GE, other)

    def __eq__(self, other: Expr | NUMBER) -> Comparison:  # type: ignore[override]
        return Comparison(self, CmpOp.EQ, other)

    def __lt__(self, other: Expr | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.LT, other)

    def __gt__(self, other: Expr | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.GT, other)

    def __str__(self) -> str:  # pragma: no cover – abstract
        """
        Display helper
        :return:
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.__str__()

    def __hash__(self) -> int:
        return hash(self.uid)

    def get_vars(self) -> List["Var"]:
        """
        Get all variables in this expression.
        :return: List of Var objects
        """
        result: Set[Var] = set()
        _collect_vars(self, result)
        return list(result)


# ----------------------------------------------------------------------------------------------------------------------
# Atomic nodes
# ----------------------------------------------------------------------------------------------------------------------


class Const(Expr):
    __slots__ = (
        "value",
        "name",
    )

    # class to represent constants symbolically

    def __init__(self, value: NUMBER | None = None, uid: int | None = None, name: str = ""):
        """Create a symbolic constant node.

        :param value: Numeric constant value, or ``None`` for an undefined constant.
        :param uid: Existing expression identifier, or ``None`` to allocate one.
        :param name: Optional descriptive name used by editors and serializers.
        """
        super().__init__(uid=uid)
        self.value: NUMBER | None = value
        self.name: str = name

    def __deepcopy__(self, memo: Dict[int, Any]) -> "Const":
        """
        Copy the constant while preserving its symbolic UID.

        :param memo: Standard deepcopy memo table.
        :return: Copied constant.
        """
        if id(self) in memo:
            return memo[id(self)]
        else:
            result: Const = Const(self.value, self.uid, self.name)
            memo[id(self)] = result
            return result

    def eval(self, **bindings: NUMBER) -> NUMBER | None:
        return self.value

    def eval_uid(self, uid_bindings: Dict[int, float]) -> NUMBER | None:
        return self.value

    def _diff1(self, var: Var | str, dt: Var | None = None) -> "Expr":
        return Const(0)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        if self in mapping:
            return mapping[self]
        if self.name in mapping:
            return mapping[self.name]
        if self.value is None:
            # has_none = False
            # for key in mapping.keys():
            #     if isinstance(key, Const) and key.value is None:
            #         has_none = True
            #         none_key = key
            # if has_none:
            #     return mapping[none_key]

            for key in mapping.keys():
                if isinstance(key, Const) and key.value is None:
                    return mapping[key]

        return self

    def contains_var(self, var: Var) -> bool:
        return False

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return self.__str__()

    def to_dict(self) -> Dict[str, Any]:

        d = super().to_dict()

        d["type"] = "Const"

        if isinstance(self.value, complex):
            d["value"] = [self.value.real, self.value.imag]
            d["kind"] = "complex"
            return d

        if self.value is None:
            d["value"] = None
            d["kind"] = "undefined"
            return d

        d["value"] = self.value
        d["kind"] = "float"
        return d


class VarType(Enum):
    __slots__ = ()

    Parameter = "parameter"
    State = "state"
    Algebraic = "algebraic"
    Differential = "differential"


class Var(Expr):
    """
    Any variable
    """

    __slots__ = ("name", "_ref", "_network_conn", "_shared_ref", "uid", "non_mutable_uid", "diff_var", "base_var", "_origin_var")

    def __init__(self, name: str,
                 reference: VarPowerFlowReferenceType | None = None,
                 network_conn: bool = False,
                 shared_reference: SharedVarReferenceType | None = None,
                 non_mutable_uid: int | None = None,
                 uid: int | None = None,
                 diff_var: Var | None = None,
                 base_var: Var | None = None):

        """
        Create a symbolic variable and its optional identity relationships.

        :param name: Symbol name used in equations and user interfaces.
        :param reference: Optional power-flow reference represented by the variable.
        :param network_conn: Whether the variable belongs to a network connection interface.
        :param shared_reference: Optional identity shared with equivalent signal variables.
        :param non_mutable_uid: Stable physical variable identity.
        :param uid: Current symbolic identifier, or ``None`` to allocate one.
        :param diff_var: Optional derivative variable associated with this base variable.
        :param base_var: Optional state variable associated with this derivative variable.
        """
        super().__init__(uid=uid)
        # Preserve the physical variable identity independently from the
        # mutable UID used to represent the currently connected signal.

        resolved_non_mutable_uid: int

        if non_mutable_uid is None:
            resolved_non_mutable_uid = self.uid
        else:
            resolved_non_mutable_uid = non_mutable_uid

        self.non_mutable_uid: int = resolved_non_mutable_uid
        self.name: str = name
        self._ref: VarPowerFlowReferenceType | None = reference
        self._network_conn: bool = network_conn
        self._shared_ref: SharedVarReferenceType | None = shared_reference

        self.diff_var = diff_var
        self.base_var: Var | None = base_var  # assign reference to base var
        self._origin_var: Var | None = None

        if base_var is not None:
            self.base_var.diff_var = self  # assign reference to me in the base var

    def __deepcopy__(self, memo: Dict[int, Any]) -> "Var":
        """
        Copy a symbolic variable without reusing derivative-chain pointers.

        :param memo: Standard deepcopy memo table.
        :return: Copied variable.
        """
        if id(self) in memo:
            return memo[id(self)]
        else:
            result: Var = Var.__new__(Var)
            memo[id(self)] = result
            if isinstance(self._shared_ref, bool):
                print("")

            result.uid = self.uid
            result.non_mutable_uid = self.non_mutable_uid
            result.name = self.name
            result._shared_ref = self._shared_ref
            result._ref = self._ref
            result._network_conn = self._network_conn
            result.diff_var = copy.deepcopy(self.diff_var, memo)
            result.base_var = copy.deepcopy(self.base_var, memo)
            result._origin_var = None
            if isinstance(result._shared_ref, bool):
                print("")
            return result

    def eval(self, **bindings: float) -> float:
        """
        Evaluate this variable
        :param bindings: dictionary like mapping Var: float
        :return:
        """
        try:
            return bindings[self.name]
        except KeyError as exc:
            raise ValueError(f"No value for variable '{self.name}'.") from exc

    def eval_uid(self, uid_bindings: Dict[int, float]) -> float:
        """
        Evaluate using the uid
        :param uid_bindings:
        :return:
        """
        try:
            return uid_bindings[self.uid]
        except KeyError as exc:
            raise ValueError(f"No value for uid '{self.uid}'.") from exc

    def subs(self, mapping: Dict[Var | str, Expr]) -> Expr:
        """
        Substitute this variable
        :param mapping:
        :return:
        """
        if self in mapping:
            return mapping[self]
        if self.name in mapping:
            return mapping[self.name]
        return self

    def contains_var(self, var: Var) -> bool:
        return self.uid == var.uid

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def set_name(self, name: str) -> None:
        """
        Change the variable name without changing the symbolic identity.

        :param name: New variable name.
        :return: None.
        """
        # Only the display and serialization name changes here. The variable
        # identity remains tied to the existing uid fields.
        self.name = name

    def __eq__(self, other: Any) -> bool | Comparison:
        # Var comparison using the uid
        if isinstance(other, Var):
            return self.uid == other.uid

        # Symbolic comparison between any expression Expr or float or int
        if isinstance(other, Expr) or isinstance(other, (int, float)):
            return Comparison(self, CmpOp.EQ, other)

        return NotImplemented

    @staticmethod
    def parse(data: Dict[str, Any]) -> "Var":
        """
        Parse the data
        :param data:
        :return:
        """
        # reconstruct base_var
        base_data = data["base_var"]
        base_var = _dict_to_expr(base_data)
        if not isinstance(base_var, Var):
            raise TypeError("base_var must be a Var")

        obj = Var(name=data["name"], base_var=base_var)
        obj.uid = data["uid"]
        return obj

    @property
    def network_conn(self) -> bool:
        return self._network_conn

    @property
    def diff_order(self) -> int:
        order = 0
        var = self
        while var.base_var is not None:
            var = var.base_var
            order += 1
        return order

    @property
    def origin_var(self) -> Var:

        if self._origin_var is None:
            # lazy evaluation, since this is tied to the base var, we do it only once
            self._origin_var = self.base_var
            while self._origin_var.base_var is not None:
                self._origin_var = self._origin_var.base_var

        return self._origin_var

    @property
    def shared_ref(self) -> SharedVarReferenceType | None:
        return self._shared_ref

    @shared_ref.setter
    def shared_ref(self, val: SharedVarReferenceType) -> None:
        if isinstance(val, SharedVarReferenceType):
            self._shared_ref = val
        else:
            raise ValueError(f"RMS model cannot accept {val}")

    @property
    def ref(self) -> VarPowerFlowReferenceType | None:
        return self._ref

    @ref.setter
    def ref(self, val: VarPowerFlowReferenceType) -> None:
        """Set the typed physical-network reference of this variable.

        :param val: Physical-network reference to assign.
        :return: None.
        """
        if isinstance(val, VarPowerFlowReferenceType):
            self._ref = val
        else:
            raise ValueError(f"Symbolic variable cannot accept reference {val}")

    def _diff1(self, var: Var | str, dt: Var | None = None) -> Expr:
        """
        differentiation
        :param var:
        :type var: VeraGridEngine.Utils.Symbolic.symbolic.Var
        :param dt:
        :type dt: Union[None, VeraGridEngine.Utils.Symbolic.symbolic.Var]
        :return:
        :rtype: Union[VeraGridEngine.Utils.Symbolic.symbolic.Const, None, VeraGridEngine.Utils.Symbolic.symbolic.BinOp]
        """
        target_uid: int | None = None
        target_name: str | None = None
        if isinstance(var, Var):
            target_uid = var.uid
            target_name = var.name
        else:
            target_name = var

        if dt is None or self.base_var is None:
            if target_uid is not None:
                return Const(1 if self.uid == target_uid else 0)
            else:
                return Const(1 if self.name == target_name else 0)
        elif self.base_var is not None:
            # ∂(dx/dt)/∂x = 1/h
            if target_uid is not None and target_uid == self.uid:
                return Const(1)
            elif target_uid is not None and target_uid == self.base_var.uid:
                # Differentiating by immediate base: return 1/dt
                return Const(1) / dt
            elif target_uid is not None and target_uid == self.origin_var.uid:
                # Differentiating by origin (root) variable: apply chain rule
                # This happens for nested diff vars like d2x when diff'ing by x
                result = (Const(1) / dt) * self.base_var.diff(var, dt=dt)
                return result
            elif target_uid is None and target_name == self.name:
                return Const(1)
            elif target_uid is None and target_name == self.base_var.name:
                return Const(1) / dt
            elif target_uid is None and target_name == self.origin_var.name:
                result = (Const(1) / dt) * self.base_var.diff(var, dt=dt)
                return result
            else:
                return Const(0)
        return Const(0)

    def populate_initial_lag(self, x0: float, dx0: np.ndarray, lag_x: float, dt: Optional[Const]) -> float:
        """

        Populate the numeric lag state for the current derivative order.

        :param x0: Initial state value.
        :param dx0:
        :param lag_x: Current lag value used as accumulation base.
        :param dt:
        :return: Numeric lag initialization value.
        """
        # Initialize the lag from the supplied state and derivative samples.
        diff_order: int = self.diff_order
        result: float = x0 if lag_x == 0.0 else lag_x
        if dt is None or dt.value is None:
            dt_value: float = 1.0
        else:
            dt_value = float(dt.value)

        index: int
        for index in range(diff_order):
            result += (dt_value ** (index + 1)) * ((-1.0) ** (index + 1)) * float(dx0[index])

        return result

    def approximation_expr(self, dt: Optional[Var | None], central: bool = False) -> Tuple[Expr, int]:
        """
        Computes the n-th backward finite difference approximation of the derivative
        using the closed-form backward difference formula.
        """
        origin_name = self.origin_var.name
        lag_var_0 = self.origin_var
        if dt is None:
            dt = Const(1.0)
        origin_name = self.origin_var.name
        lag_total = self.diff_order
        if self.diff_order == 1 and central:
            lag_var_2 = Var("aux_2")
            return (lag_var_0 - lag_var_2) / (2 * dt), lag_total

        # Compute the sum: ∑_{i=0}^{n} (-1)^i * C(n, i) * f(x - i*dt)
        terms: List[Expr] = list()
        minus1: Const = Const(-1)

        for i in range(lag_total + 1):
            if i == 0:
                lag_var = lag_var_0
            else:
                lag_var = Var(name=f"{origin_name}_lag_{i}")
            coeff = minus1 ** i * Const(math.comb(lag_total, i))
            terms.append(coeff * lag_var)

        finite_diff_sum = sum(terms)

        # Divide by dt^n for n-th derivative
        result = finite_diff_sum / (dt ** lag_total)
        return result.simplify(), lag_total

    def __hash__(self) -> int:
        return hash(self.uid)


def get_expr_factors(expr: Expr) -> List[Expr]:
    """

    :param expr:
    :type expr: Union[VeraGridEngine.Utils.Symbolic.symbolic.BinOp, VeraGridEngine.Utils.Symbolic.symbolic.UnOp, VeraGridEngine.Utils.Symbolic.symbolic.Const, VeraGridEngine.Utils.Symbolic.symbolic.Var, VeraGridEngine.Utils.Symbolic.symbolic.Func]
    :return:
    :rtype: Union[List[VeraGridEngine.Utils.Symbolic.symbolic.BinOp], List[VeraGridEngine.Utils.Symbolic.symbolic.UnOp], List[VeraGridEngine.Utils.Symbolic.symbolic.Const], List[VeraGridEngine.Utils.Symbolic.symbolic.Var], List[VeraGridEngine.Utils.Symbolic.symbolic.Func]]
    """
    if isinstance(expr, BinOp) and expr.op == '*':
        return get_expr_factors(expr.left.simplify()) + get_expr_factors(expr.right.simplify())
    # Limited expansion of integer powers
    elif isinstance(expr, BinOp) and expr.op == '**':
        base, exp_ = expr.left.simplify(), expr.right.simplify()

        if isinstance(exp_, Const):
            n = exp_.value
            if isinstance(n, int) and n >= 1:
                return get_expr_factors(base) * n

        # otherwise: keep power atomic
        return [expr]
    return [expr]


def build_mul(factors: List[Expr]) -> Expr:
    """

    :param factors:
    :type factors: List[Expr]
    :return:Expr
    """
    if not factors:
        return Const(1)
    expr = factors[0]
    for f in factors[1:]:
        expr = expr * f
    return expr


class BinOp(Expr):
    """
    Binary operation expression
    """

    __slots__ = ("op", "left", "right")

    def __init__(self, left: Expr, op: str, right: Expr, uid: int | None = None):
        """
        Create a symbolic binary-operation node.

        :param left: Symbolic expression on the left-hand side.
        :param op: Supported binary operator token.
        :param right: Symbolic expression on the right-hand side.
        :param uid: Existing expression identifier, or ``None`` to allocate one.
        """
        super().__init__(uid=uid)
        self.op: str = op
        self.left: Expr = left
        self.right: Expr = right

    def eval(self, **bindings: NUMBER) -> NUMBER:
        """
        Evaluation using names
        :param bindings:
        :return:
        """
        # return self._impl[self.op](self.left.eval(**bindings), self.right.eval(**bindings))
        if self.op == "+":
            return self.left.eval(**bindings) + self.right.eval(**bindings)
        elif self.op == "-":
            return self.left.eval(**bindings) - self.right.eval(**bindings)
        elif self.op == "*":
            return self.left.eval(**bindings) * self.right.eval(**bindings)
        elif self.op == "/":
            return self.left.eval(**bindings) / self.right.eval(**bindings)
        elif self.op == "**":
            return self.left.eval(**bindings) ** self.right.eval(**bindings)
        else:
            raise ValueError(f"operation {self.op} not implemented")

    def __deepcopy__(self, memo: Dict[int, Any]) -> "BinOp":
        """
        Copy the binary operation while preserving shared child identity.

        :param memo: Standard deepcopy memo table.
        :return: Copied binary operation.
        """
        if id(self) in memo:
            return memo[id(self)]
        else:
            result: BinOp = BinOp(
                left=copy.deepcopy(self.left, memo),
                op=self.op,
                right=copy.deepcopy(self.right, memo),
                uid=self.uid,
            )
            memo[id(self)] = result
            return result

    def eval_uid(self, uid_bindings: Dict[int, float]) -> NUMBER:
        """
        Evaluate using uuid's
        :param uid_bindings:
        :return:
        """
        # return self._impl[self.op](self.left.eval_uid(uid_bindings), self.right.eval_uid(uid_bindings))
        if self.op == "+":
            return self.left.eval_uid(uid_bindings) + self.right.eval_uid(uid_bindings)
        elif self.op == "-":
            return self.left.eval_uid(uid_bindings) - self.right.eval_uid(uid_bindings)
        elif self.op == "*":
            return self.left.eval_uid(uid_bindings) * self.right.eval_uid(uid_bindings)
        elif self.op == "/":
            return self.left.eval_uid(uid_bindings) / self.right.eval_uid(uid_bindings)
        elif self.op == "**":
            return self.left.eval_uid(uid_bindings) ** self.right.eval_uid(uid_bindings)
        else:
            raise ValueError(f"operation {self.op} not implemented")

    def _diff1(self, var: Var | str, dt: Var | None = None) -> Expr:
        """
        Differentiation of this expression w.r.t var
        :param var: variable to differentiate with respect to
        :return: Expression
        """
        u, v = self.left, self.right
        du, dv = u._diff1(var, dt), v._diff1(var, dt)
        if self.op == "+":
            return du + dv
        if self.op == "-":
            return du - dv
        if self.op == "*":
            return du * v + u * dv
        if self.op == "/":
            return (du * v - u * dv) / (v ** Const(2))
        if self.op == "**":
            if isinstance(v, Const) and v.value is not None:
                # numeric exponent
                return Const(v.value) * (u ** Const(v.value - 1)) * du
            else:
                # general exponent: u**v = exp(v*log u)
                return self * (dv * log(u) + du * v / u)
        raise ValueError("Unsupported operator for diff")

    def simplify(self) -> Expr:
        """
        Simplify expression
        :return: Simplified expression
        """
        l, r = self.left.simplify(), self.right.simplify()
        if isinstance(l, Const) and isinstance(r, Const):
            if self.op == "+":
                return Const(r.value + l.value)
            elif self.op == "-":
                return Const(l.value - r.value)
            elif self.op == "*":
                return Const(r.value * l.value)
            elif self.op == "/":
                if r.value != 0:
                    return Const(l.value / r.value)
                else:
                    raise ZeroDivisionError("Division by zero")
            elif self.op == "**":
                return Const(l.value ** r.value)
            else:
                raise ValueError(f"operation {self.op} not implemented")

        if self.op == "+":
            if isinstance(l, Const) and l.value == 0:
                return r
            if isinstance(r, Const) and r.value == 0:
                return l

        if self.op == "-":
            if isinstance(l, Const) and l.value == 0:
                return -r
            if isinstance(r, Const) and r.value == 0:
                return l
            if l.uid == r.uid:
                return Const(0)

        if self.op == "*":
            for a, b in ((l, r), (r, l)):
                if isinstance(a, Const):
                    if a.value == 0:
                        return Const(0)
                    if a.value == 1:
                        return b

        if self.op == "**" and isinstance(r, Const):
            if r.value == 1:
                return l
            if r.value == 0:
                return Const(1)

        if self.op == '/':
            if isinstance(l, Const) and l.value == 0:
                return Const(0)
            elif isinstance(r, Const) and r.value == 1:
                return l
            elif l.uid == r.uid:
                return Const(1)
            else:
                num_factors = get_expr_factors(l)
                den_factors = get_expr_factors(r)

                new_num: List[Expr] = list()
                new_den = den_factors.copy()

                for f in num_factors:
                    for g in new_den:
                        if f.uid == g.uid:  # or f == g if structural equality
                            new_den.remove(g)
                            break
                    else:
                        new_num.append(f)

                num_expr = build_mul(new_num)
                den_expr = build_mul(new_den)

                if isinstance(den_expr, Const) and den_expr.value == 1:
                    return num_expr
                return BinOp(num_expr, '/', den_expr)

        return BinOp(l, self.op, r)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        """
        Substitution
        :param mapping: mapping of variables to expressions
        :return:
        """
        if self in mapping:
            return mapping[self]
        return BinOp(self.left.subs(mapping), self.op, self.right.subs(mapping))

    def contains_var(self, var: Var) -> bool:
        return self.left.contains_var(var) or self.right.contains_var(var)

    def __str__(self) -> str:
        return f"({self.left}) {self.op} ({self.right})"

    def __repr__(self) -> str:
        return self.__str__()

    def __print__(self) -> str:
        return self.__str__()

    @staticmethod
    def parse(data: Dict[str, Any]) -> Expr:
        obj = BinOp(_dict_to_expr(data["left"]), data["op"], _dict_to_expr(data["right"]))
        obj.uid = data["uid"]
        return obj

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "BinOp"
        d["op"] = self.op
        d["left"] = self.left.to_dict()
        d["right"] = self.right.to_dict()
        return d


class UnOp(Expr):
    """
    Unary operation expression
    """

    __slots__ = ("op", "operand",)

    def __init__(self, op: str, operand: Expr, uid: int | None = None):
        """
        Create a symbolic unary-operation node.

        :param op: Supported unary operator token.
        :param operand: Symbolic expression to which the operator is applied.
        :param uid: Existing expression identifier, or ``None`` to allocate one.
        """
        super().__init__(uid=uid)
        self.op: str = op
        self.operand = operand

    def eval(self, **bindings: NUMBER) -> NUMBER:
        """

        :param bindings:
        :return:
        """
        val = self.operand.eval(**bindings)
        return -val if self.op == "-" else math.nan

    def __deepcopy__(self, memo: Dict[int, Any]) -> "UnOp":
        """
        Copy the unary operation while preserving shared child identity.

        :param memo: Standard deepcopy memo table.
        :return: Copied unary operation.
        """
        if id(self) in memo:
            return memo[id(self)]
        else:
            result: UnOp = UnOp(
                op=self.op,
                operand=copy.deepcopy(self.operand, memo),
                uid=self.uid,
            )
            memo[id(self)] = result
            return result

    def eval_uid(self, uid_bindings: Dict[int, NUMBER]) -> NUMBER:
        """

        :param uid_bindings:
        :return:
        """
        val = self.operand.eval_uid(uid_bindings)
        if self.op == "-":
            return -val
        else:
            raise ValueError(f"Unknown operand {self.op}")

    def _diff1(self, var: Var | str, dt: Var | None = None) -> "Expr":
        """

        :param var:
        :return:
        """
        if self.op == "-":
            return -self.operand._diff1(var, dt)
        else:
            raise ValueError(f"Unknown operand {self.op}")

    def simplify(self) -> Expr:
        """

        :return:
        """
        opr = self.operand.simplify()
        if isinstance(opr, Const):
            return Const(-opr.value)
        return UnOp(self.op, opr)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        """

        :param mapping:
        :return:
        """
        if self in mapping:
            return mapping[self]
        return UnOp(self.op, self.operand.subs(mapping))

    def contains_var(self, var: Var) -> bool:
        return self.operand.contains_var(var)

    def __str__(self) -> str:
        return f"{self.op}({self.operand})"

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    def parse(data: Dict[str, Any]) -> Expr:
        obj = UnOp(data["op"], _dict_to_expr(data["operand"]))
        obj.uid = data["uid"]
        return obj

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "UnOp"
        d["op"] = self.op
        d["operand"] = self.operand.to_dict()
        return d


# ----------------------------------------------------------------------------------------------------------------------
# Functional nodes
# ----------------------------------------------------------------------------------------------------------------------
@nb.jit
def heaviside_num(x):
    return (x > 0) * 1.0


def get_namespace() -> Dict[str, Any]:
    """
    Build the evaluation namespace used by generated expressions.

    :return: Namespace dictionary for generated expressions.
    """
    namespace: Dict[str, Any] = dict()
    namespace["math"] = math
    namespace["np"] = np
    namespace["nb"] = nb
    namespace["_heaviside"] = heaviside_num
    return namespace


def _evaluate_unary_function(op: str, value: NUMBER) -> NUMBER:
    """
    Evaluate a unary symbolic function explicitly by operator name.

    :param op: Function operator name.
    :param value: Numeric argument.
    :return: Numeric function result.
    """
    if op == "sin":
        return math.sin(value)
    elif op == "cos":
        return math.cos(value)
    elif op == "tan":
        return math.tan(value)
    elif op == "exp":
        return np.exp(value)
    elif op == "log":
        if np.iscomplexobj(value):
            return np.log(value)
        else:
            return math.log(value)
    elif op == "log10":
        if np.iscomplexobj(value):
            return np.log10(value)
        else:
            return math.log10(value)
    elif op == "sqrt":
        return math.sqrt(value)
    elif op == "asin":
        return math.asin(value)
    elif op == "acos":
        return math.acos(value)
    elif op == "atan":
        return math.atan(value)
    elif op == "sinh":
        return math.sinh(value)
    elif op == "cosh":
        return math.cosh(value)
    elif op == "tanh":
        return math.tanh(value)
    elif op == "floor":
        return math.floor(value)
    elif op == "ceil":
        return math.ceil(value)
    elif op == "round":
        return builtins.round(value)
    elif op == "real":
        return np.real(value)
    elif op == "imag":
        return np.imag(value)
    elif op == "conj":
        return np.conj(value)
    elif op == "angle":
        return np.angle(value)
    elif op == "abs":
        return builtins.abs(value)
    elif op == "heaviside":
        return heaviside_num(float(value))
    elif op == "rand":
        return np.random.rand()
    else:
        raise ValueError(f"Unknown unary function '{op}'")


def _differentiate_unary_function(op: str, u: Expr, du: Expr) -> Expr:
    """
    Differentiate a unary symbolic function explicitly by operator name.

    :param op: Function operator name.
    :param u: Original symbolic argument.
    :param du: Derivative of the symbolic argument.
    :return: Symbolic derivative.
    """
    if op == "sin":
        return sin_diff(u, du)
    elif op == "cos":
        return cos_diff(u, du)
    elif op == "tan":
        return tan_diff(u, du)
    elif op == "exp":
        return exp_diff(u, du)
    elif op == "log":
        return log_diff(u, du)
    elif op == "log10":
        return log10_diff(u, du)
    elif op == "sqrt":
        return sqrt_diff(u, du)
    elif op == "asin":
        return asin_diff(u, du)
    elif op == "acos":
        return acos_diff(u, du)
    elif op == "atan":
        return atan_diff(u, du)
    elif op == "sinh":
        return sinh_diff(u, du)
    elif op == "cosh":
        return cosh_diff(u, du)
    elif op == "tanh":
        return tanh_diff(u, du)
    elif op in {"floor", "ceil", "round"}:
        return Const(0.0)
    elif op == "abs":
        return abs_diff(u, du)
    elif op == "heaviside":
        return heaviside_diff(u, du)
    else:
        raise ValueError(f"No derivative defined for {op}")


def _evaluate_binary_function(name: str, arg1: NUMBER, arg2: NUMBER) -> NUMBER:
    """
    Evaluate a binary symbolic function explicitly by function name.

    :param name: Function name.
    :param arg1: First numeric argument.
    :param arg2: Second numeric argument.
    :return: Numeric function result.
    """
    if name == "atan2":
        return np.arctan2(arg1, arg2)
    elif name == "min":
        return np.minimum(arg1, arg2)
    elif name == "max":
        return np.maximum(arg1, arg2)
    else:
        raise ValueError(f"Unknown binary function '{name}'")


def _binary_function_to_python(name: str, arg1: str, arg2: str) -> str:
    """
    Emit the NumPy source for one binary symbolic function.

    Legacy files may contain ``Func2`` nodes named ``min`` or ``max``.  Those
    names represent two-operand element-wise operations, whereas ``np.min``
    and ``np.max`` interpret their second positional argument as an axis.
    Keeping the mapping here shared by every code-generation path prevents the
    same persisted expression from acquiring different runtime semantics.

    :param name: Symbolic binary function name.
    :param arg1: Generated source for the first argument.
    :param arg2: Generated source for the second argument.
    :return: NumPy-compatible Python expression source.
    """
    if name == "atan2":
        source: str = f"np.arctan2({arg2}, {arg1})"
    elif name == "min":
        source = f"np.minimum({arg1}, {arg2})"
    elif name == "max":
        source = f"np.maximum({arg1}, {arg2})"
    else:
        source = f"np.{name}({arg1}, {arg2})"

    return source


class Func(Expr):
    __slots__ = ("op", "arg")

    def __init__(self, arg: Expr, op: str = "", uid: int | None = None):
        """
        Create a symbolic single-argument function node.

        :param arg: Symbolic argument passed to the function.
        :param op: Supported function name.
        :param uid: Existing expression identifier, or ``None`` to allocate one.
        """
        super().__init__(uid=uid)
        self.op: str = op
        self.arg: Expr = arg

    # --- evaluation ----------------------------------------------------------
    def eval(self, **bindings: NUMBER) -> NUMBER:
        return _evaluate_unary_function(self.op, self.arg.eval(**bindings))

    def __deepcopy__(self, memo: Dict[int, Any]) -> "Func":
        """
        Copy the unary function node while preserving shared child identity.

        :param memo: Standard deepcopy memo table.
        :return: Copied unary function node.
        """
        if id(self) in memo:
            return memo[id(self)]
        else:
            result: Func = Func(
                arg=copy.deepcopy(self.arg, memo),
                op=self.op,
                uid=self.uid,
            )
            memo[id(self)] = result
            return result

    def eval_uid(self, uid_bindings: Dict[int, NUMBER]) -> NUMBER:
        return _evaluate_unary_function(self.op, self.arg.eval_uid(uid_bindings))

    @staticmethod
    def parse(data: Dict[str, Any]) -> Expr:
        op = data["op"]
        if op is None:
            op = data["name"]
        obj = Func(_dict_to_expr(data["arg"]), op)
        obj.uid = data["uid"]
        return obj

    def to_dict(self) -> Dict[str, Any]:
        """

        :return:
        """
        d = super().to_dict()
        d["type"] = "Func"
        d["op"] = self.op
        d["arg"] = self.arg.to_dict()
        return d

    # --- differentiation (chain rule) ---------------------------------------
    def _diff1(self, var: Var | str, dt: Var | None = None) -> "Expr":
        u = self.arg
        du = u._diff1(var, dt)
        if isinstance(du, Const) and du.value == 0:
            return Const(0)
        else:
            return _differentiate_unary_function(self.op, u, du)

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Expr":
        if self in mapping:
            return mapping[self]
        return Func(self.arg.subs(mapping), self.op)

    def contains_var(self, var: Var) -> bool:
        return self.arg.contains_var(var)

    def __str__(self) -> str:
        return f"{self.op}({self.arg})"

    def __repr__(self) -> str:
        return self.__str__()


def _symbolic_abs(x: Expr) -> Expr:
    """
    Create a symbolic absolute-value expression.

    :param x: Symbolic argument.
    :return: Symbolic absolute-value node.
    """
    return Func(_to_expr(x), "abs")


def abs_diff(u: Expr, du: Expr) -> Expr:
    return heaviside(u) * du


def real(x: Expr) -> Expr:
    return Func(_to_expr(x), "real")


def imag(x: Expr) -> Expr:
    return Func(_to_expr(x), "imag")


def conj(x: Expr) -> Expr:
    return Func(_to_expr(x), "conj")


def angle(x: Expr) -> Expr:
    return Func(_to_expr(x), "angle")


def sin(x: Expr) -> Expr:
    return Func(_to_expr(x), "sin")


def sin_diff(u: Expr, du: Expr) -> Expr:
    return cos(u) * du


def cos(x: Expr) -> Expr:
    return Func(_to_expr(x), "cos")


def cos_diff(u: Expr, du: Expr) -> Expr:
    return -sin(u) * du


def sec(x: Expr | NUMBER) -> Expr:
    return Const(1) / cos(x)


def tan(x: Expr) -> Expr:
    return Func(_to_expr(x), "tan")


def tan_diff(u: Expr, du: Expr) -> Expr:
    return (sec(u) ** Const(2)) * du


def exp(x: Expr) -> Expr:
    return Func(_to_expr(x), "exp")


def exp_diff(u: Expr, du: Expr) -> Expr:
    return exp(u) * du


def log(x: Expr) -> Expr:
    return Func(_to_expr(x), "log")


def log_diff(u: Expr, du: Expr) -> Expr:
    return du / u


def log10(x: Expr) -> Expr:
    return Func(_to_expr(x), "log10")


def log10_diff(u: Expr, du: Expr) -> Expr:
    return du / (u * Const(math.log(10.0)))


def sqrt(x: Expr) -> Expr:
    return Func(_to_expr(x), "sqrt")


def sqrt_diff(u: Expr, du: Expr) -> Expr:
    """Differentiate a square root with a finite boundary convention.

    The analytical derivative is retained for strictly positive arguments.
    At zero, where the derivative is not finite, the symbolic runtime uses a
    zero slope. This is the deterministic boundary convention required by
    limited expressions such as ``sqrt(max(x, 0))``.

    :param u: Square-root argument.
    :param du: Derivative of the argument.
    :return: Symbolic derivative that remains finite at zero.
    """
    protected_derivative: Expr = safe_divide(
        numerator=du,
        denominator=Const(2) * sqrt(u),
        zero_denominator_value=Const(1.0),
    )
    return protected_derivative * heaviside(u)


def asin(x: Expr) -> Expr:
    return Func(_to_expr(x), "asin")


def asin_diff(u: Expr, du: Expr) -> Expr:
    return du / sqrt(Const(1) - u ** Const(2))


def acos(x: Expr) -> Expr:
    return Func(_to_expr(x), "acos")


def acos_diff(u: Expr, du: Expr) -> Expr:
    return -du / sqrt(Const(1) - u ** Const(2))


def atan(x: Expr) -> Expr:
    return Func(_to_expr(x), "atan")


def atan_diff(u: Expr, du: Expr) -> Expr:
    return du / (Const(1) + u ** Const(2))


def sinh(x: Expr) -> Expr:
    return Func(_to_expr(x), "sinh")


def cosh(x: Expr) -> Expr:
    return Func(_to_expr(x), "cosh")


def sinh_diff(u: Expr, du: Expr) -> Expr:
    return cosh(u) * du


def cosh_diff(u: Expr, du: Expr) -> Expr:
    return sinh(u) * du


def tanh(x: Expr) -> Expr:
    return Func(_to_expr(x), "tanh")


def tanh_diff(u: Expr, du: Expr) -> Expr:
    return (Const(1) - tanh(u) ** Const(2)) * du


def floor(x: Expr) -> Expr:
    return Func(_to_expr(x), "floor")


def ceil(x: Expr) -> Expr:
    return Func(_to_expr(x), "ceil")


def round_expr(x: Expr) -> Expr:
    return Func(_to_expr(x), "round")


def round(x: Expr) -> Expr:
    return round_expr(x)


def frac(x: Expr) -> Expr:
    expr = _to_expr(x)
    return expr - floor(expr)


def heaviside(x: Expr) -> Expr:
    return Func(_to_expr(x), "heaviside")


def rand(x: Expr) -> Expr:
    return Func(_to_expr(x), "rand")


#
# def heaviside(x: Expr):
#     return  _heaviside(x)


def heaviside_diff(u: Expr, du: Expr) -> Expr:
    return Const(0)


def _symbolic_max(x: Expr | NUMBER, y: Expr | NUMBER) -> Expr:
    """
    Build a symbolic maximum expression.

    :param x: First operand.
    :param y: Second operand.
    :return: Symbolic maximum expression.
    """
    x_expr: Expr = _to_expr(x)
    y_expr: Expr = _to_expr(y)
    return x_expr * heaviside((x_expr - y_expr)) + y_expr * (Const(1) - heaviside((x_expr - y_expr)))


def _symbolic_min(x: Expr | NUMBER, y: Expr | NUMBER) -> Expr:
    """
    Build a symbolic minimum expression.

    :param x: First operand.
    :param y: Second operand.
    :return: Symbolic minimum expression.
    """
    x_expr: Expr = _to_expr(x)
    y_expr: Expr = _to_expr(y)
    return x_expr * heaviside(y_expr - x_expr) + y_expr * (Const(1) - heaviside(y_expr - x_expr))


def abs(x: Expr) -> Expr:
    """
    Public symbolic absolute-value helper kept for API compatibility.

    :param x: Symbolic argument.
    :return: Symbolic absolute-value node.
    """
    return _symbolic_abs(x)


def max(x: Expr | NUMBER, y: Expr | NUMBER) -> Expr:
    """
    Public symbolic maximum helper kept for API compatibility.

    :param x: First operand.
    :param y: Second operand.
    :return: Symbolic maximum expression.
    """
    return _symbolic_max(x, y)


def min(x: Expr | NUMBER, y: Expr | NUMBER) -> Expr:
    """
    Public symbolic minimum helper kept for API compatibility.

    :param x: First operand.
    :param y: Second operand.
    :return: Symbolic minimum expression.
    """
    return _symbolic_min(x, y)


def atan2(x: Expr, y: Expr) -> Expr:
    return Func2("atan2", _to_expr(x), _to_expr(y))


def safe_divide(
        numerator: Expr | NUMBER,
        denominator: Expr | NUMBER,
        zero_denominator_value: Expr | NUMBER,
) -> Expr:
    """Build a division that remains defined for an exact zero denominator.

    Non-zero denominators retain ordinary division. The caller must state the
    value that replaces an exact zero denominator so the complete numerical
    rule remains visible at every equation site.

    :param numerator: Dividend expression.
    :param denominator: Divisor expression.
    :param zero_denominator_value: Explicit replacement for an exact zero.
    :return: Symbolic division with an explicit zero-denominator branch.
    """
    numerator_expression: Expr = _to_expr(numerator)
    denominator_expression: Expr = _to_expr(denominator)
    zero_denominator_expression: Expr = _to_expr(zero_denominator_value)
    if (
            isinstance(zero_denominator_expression, Const)
            and zero_denominator_expression.value == 0
    ):
        raise ValueError("zero_denominator_value must be non-zero")
    else:
        pass

    denominator_is_nonzero: Expr = (
        heaviside(denominator_expression)
        + heaviside(-denominator_expression)
    )
    effective_denominator: Expr = (
        denominator_is_nonzero * denominator_expression
        + (Const(1.0) - denominator_is_nonzero)
        * zero_denominator_expression
    )
    return numerator_expression / effective_denominator


def hard_sat(x: Expr, x_min: Expr | NUMBER, x_max: Expr | NUMBER) -> Expr:
    """
    Apply a symbolic hard saturation to an expression.

    :param x: Input expression.
    :param x_min: Lower saturation limit.
    :param x_max: Upper saturation limit.
    :return: Symbolic saturation expression.
    """
    x_min_expr: Expr = _to_expr(x_min)
    x_max_expr: Expr = _to_expr(x_max)
    return x_min_expr + (x - x_min_expr) * heaviside(x - x_min_expr) - (x - x_max_expr) * heaviside(x - x_max_expr)


def f_exc(In: Expr) -> Expr:
    exp1 = (Const(1) - Const(0.577) * In)
    exp2 = sqrt(max(Const(1e-6), Const(0.75) - In ** 2))
    exp3 = (Const(1.732) - In * Const(1.732))
    b = (exp1 - exp2) * heaviside(Const(0.433) - In)
    c = (exp2 - exp3) * heaviside(Const(0.75) - In)
    d = exp3 * heaviside(Const(1.0) - In)
    return b + c + d


def piecewise(time_var: Expr, t_events: np.ndarray, new_values: np.ndarray, default_value: Any) -> Expr:
    """
    Symbolic piecewise function.
    Returns default_value before the first event, then switches to
    corresponding new_values after each t_event.

    Parameters
    ----------
    time_var : Expr
        Symbolic time expression
    t_events : np.ndarray
        1D array of event times (must be sorted ascending)
    new_values : np.ndarray
        1D array of values after each event time
    default_value : Any
        Value before the first event
    """
    t_expr = _to_expr(time_var)
    result = _to_expr(default_value)

    for t_event, new_value in zip(t_events, new_values):
        step = heaviside(t_expr - Const(t_event))
        result = step * _to_expr(new_value) + (Const(1) - step) * result

    return result

class Func2(Expr):
    """
    Symbolic binary function node.

    :param name: Binary function name.
    :param arg1: First symbolic argument.
    :param arg2: Second symbolic argument.
    :param uid: Optional node uid.
    """

    __slots__ = ("name", "arg1", "arg2")

    def __init__(self, name: str, arg1: Expr, arg2: Expr, uid: int | None = None):
        """Create a symbolic two-argument function node.

        :param name: Supported binary function name.
        :param arg1: First symbolic function argument.
        :param arg2: Second symbolic function argument.
        :param uid: Existing expression identifier, or ``None`` to allocate one.
        """
        super().__init__(uid=uid)
        self.name: str = name
        self.arg1: Expr = arg1
        self.arg2: Expr = arg2

    def eval(self, **bindings: NUMBER) -> NUMBER:
        return _evaluate_binary_function(self.name, self.arg1.eval(**bindings), self.arg2.eval(**bindings))

    def __deepcopy__(self, memo: Dict[int, Any]) -> "Func2":
        """
        Copy the binary function node while preserving shared child identity.

        :param memo: Standard deepcopy memo table.
        :return: Copied binary function node.
        """
        if id(self) in memo:
            return memo[id(self)]
        else:
            result: Func2 = Func2(
                name=self.name,
                arg1=copy.deepcopy(self.arg1, memo),
                arg2=copy.deepcopy(self.arg2, memo),
                uid=self.uid,
            )
            memo[id(self)] = result
            return result

    def eval_uid(self, uid_bindings: Dict[int, NUMBER]) -> NUMBER:
        return _evaluate_binary_function(self.name, self.arg1.eval_uid(uid_bindings), self.arg2.eval_uid(uid_bindings))

    def _diff1(self, var: Var | str, dt: Var | None) -> Expr:
        """

        differentiation

        :param var:
        :type var:
        :param dt:
        :type dt:
        :return:
        :rtype:
        """
        x = self.arg1
        y = self.arg2

        dx = x._diff1(var, dt)
        dy = y._diff1(var, dt)

        # short-circuit: constant
        if (
                isinstance(dy, Const) and dy.value == 0 and
                isinstance(dx, Const) and dx.value == 0
        ):
            return Const(0)

        if self.name == "atan2":
            return (y * dx - x * dy) / (x ** Const(2) + y ** Const(2))
        if self.name == "min":
            return heaviside(y - x) * dx + heaviside(x - y) * dy
        if self.name == "max":
            return heaviside(x - y) * dx + heaviside(y - x) * dy
        raise ValueError(f"Unknown binary function '{self.name}'")

    # --- simplification ------------------------------------------------------
    def simplify(self) -> "Expr":
        """

        simplification

        :return:
        :rtype:
        """
        a_s = self.arg1.simplify()
        b_s = self.arg2.simplify()

        # constant folding
        if isinstance(a_s, Const) and isinstance(b_s, Const):
            try:
                return Const(_evaluate_binary_function(self.name, a_s.value, b_s.value))
            except ValueError:
                pass  # domain error – keep symbolic

        # min(x, x) → x ; max(x, x) → x
        if (a_s == b_s) and self.name in ("min", "max"):
            return a_s

        # return simplified symbolic form
        return Func2(self.name, a_s, b_s)

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Expr":
        """

        substitude

        :param mapping:
        :type mapping:
        :return:
        :rtype:
        """
        if self in mapping:
            return mapping[self]
        return Func2(
            self.name,
            self.arg1.subs(mapping),
            self.arg2.subs(mapping),
        )

    def contains_var(self, var: Var) -> bool:
        return self.arg1.contains_var(var) or self.arg2.contains_var(var)

    def __str__(self) -> str:
        return f"{self.name}({self.arg1}, {self.arg2})"
        return f"{self.name}({self.arg1}, {self.arg2})"

    def __repr__(self) -> str:
        return self.__str__()


# -----------------------------------------------------------------------------
# Public constructor helpers
# -----------------------------------------------------------------------------


def _expr_to_dict(expr: Expr | Comparison) -> Dict[str, Any]:
    """
    Serialise any `Expr` tree into a plain Python dictionary that’s
    JSON-friendly.  Each node type becomes a small dict that records:

        • its own type      (\"Const\", \"Var\", \"BinOp\", …)
        • the data it carries (value, name, operator…)
        • its unique uid     (string, so it survives round-trip)
        • nested children    (recursively serialised)

    The reverse operation is handled by `_dict_to_expr`.
    """
    # ------------------------------------------------------------------
    # Atomic nodes
    # ------------------------------------------------------------------

    if isinstance(expr, Const):
        val = expr.value
        if isinstance(val, complex):
            return {"type": "Const", "value": [val.real, val.imag], "kind": "complex", "uid": expr.uid}
        return {"type": "Const", "value": val, "uid": expr.uid}

    if isinstance(expr, Var):
        if expr.base_var is None:
            return {
                "type": "Var",
                "name": expr.name,
                "uid": expr.uid,
                "non_mutable_uid": expr.non_mutable_uid,
                "reference": expr.ref.name if expr.ref is not None else None,
                "network_conn": expr.network_conn,
                "shared_reference": (
                    None
                    if expr.shared_ref is None
                    else {"name": expr.shared_ref.name, "uid": expr.shared_ref.uid}
                ),
                "base_var": "None"
            }
        else:
            return {
                "type": "Var",
                "name": expr.name,
                "uid": expr.uid,
                "non_mutable_uid": expr.non_mutable_uid,
                "reference": expr.ref.name if expr.ref is not None else None,
                "network_conn": expr.network_conn,
                "shared_reference": (
                    None
                    if expr.shared_ref is None
                    else {"name": expr.shared_ref.name, "uid": expr.shared_ref.uid}
                ),
                "base_var": _expr_to_dict(expr.base_var),
            }

    # ------------------------------------------------------------------
    # Composite nodes
    # ------------------------------------------------------------------
    if isinstance(expr, BinOp):
        return {
            "type": "BinOp",
            "op": expr.op,
            "left": _expr_to_dict(expr.left),
            "right": _expr_to_dict(expr.right),
            "uid": expr.uid,
        }

    if isinstance(expr, UnOp):
        return {
            "type": "UnOp",
            "op": expr.op,  # only \"-\" for now
            "operand": _expr_to_dict(expr.operand),
            "uid": expr.uid,
        }

    if isinstance(expr, Func):
        return {
            "type": "Func",
            "op": expr.op,
            "arg": _expr_to_dict(expr.arg),
            "uid": expr.uid,
        }

    if isinstance(expr, Func2):
        return {
            "type": "Func2",
            "name": expr.name,
            "arg1": _expr_to_dict(expr.arg1),
            "arg2": _expr_to_dict(expr.arg2),
            "uid": expr.uid,
        }

    if isinstance(expr, Comparison):
        return {
            "type": "Comparison",
            "lhs": _expr_to_dict(expr.lhs),
            "op": expr.op.value,
            "rhs": _expr_to_dict(_to_expr(expr.rhs)),
        }

    # ------------------------------------------------------------------
    # Anything else is an API bug
    # ------------------------------------------------------------------
    raise TypeError(f"Unsupported Expr subclass: {type(expr).__name__}")


def _dict_to_expr(data: Dict[str, Any]) -> Expr | Var | Const | Comparison:
    """
    De-Serialize expression from dictionary
    :param data:
    :return:
    """
    t = data["type"]
    if t == "Const":
        if data.get("kind") == "complex":
            arr = data["value"]
            obj = Const(complex(arr[0], arr[1]))
        elif data.get("kind") == "undefined":
            obj = Const()
        else:
            obj = Const(data["value"])
    elif t == "Var":
        non_mutable_uid_value: object = data.get("non_mutable_uid", data["uid"])
        if isinstance(non_mutable_uid_value, int) and not isinstance(non_mutable_uid_value, bool):
            non_mutable_uid: int = non_mutable_uid_value
        else:
            # Legacy dictionaries only persisted the mutable UID. At creation
            # time that value was also the physical variable identity.
            non_mutable_uid = data["uid"]

        # Preserve the optional physical-network meaning of every variable.
        # Missing fields keep legacy dictionaries readable.
        reference_name_data: object = data.get("reference", None)
        if reference_name_data is None:
            reference: VarPowerFlowReferenceType | None = None
        elif (
                isinstance(reference_name_data, str)
                and reference_name_data in VarPowerFlowReferenceType.__members__
        ):
            reference = VarPowerFlowReferenceType.__members__[reference_name_data]
        else:
            raise ValueError(
                f"Unknown power-flow variable reference '{reference_name_data}'"
            )

        network_conn_data: object = data.get("network_conn", False)
        if isinstance(network_conn_data, bool):
            network_conn: bool = network_conn_data
        else:
            raise TypeError("Variable network_conn must be a boolean")

        shared_reference_data: object = data.get("shared_reference", None)
        if shared_reference_data is None:
            shared_reference: SharedVarReferenceType | None = None
        elif isinstance(shared_reference_data, dict):
            shared_reference_name: object = shared_reference_data.get("name", None)
            shared_reference_uid: object = shared_reference_data.get("uid", None)
            if (
                    isinstance(shared_reference_name, str)
                    and isinstance(shared_reference_uid, int)
                    and not isinstance(shared_reference_uid, bool)
            ):
                shared_reference = SharedVarReferenceType(
                    name=shared_reference_name,
                    uid=shared_reference_uid,
                )
            else:
                raise TypeError(
                    "Variable shared_reference must contain a string name and integer uid"
                )
        else:
            raise TypeError("Variable shared_reference must be a dictionary or None")

        if data["base_var"] == "None":
            obj = Var(
                name=data["name"],
                reference=reference,
                network_conn=network_conn,
                shared_reference=shared_reference,
                non_mutable_uid=non_mutable_uid,
            )
        else:
            # reconstruct base_var
            base_data = data["base_var"]
            base_var = _dict_to_expr(base_data)
            if not isinstance(base_var, Var):
                raise TypeError("base_var must be a Var")

            obj = Var(name=data["name"],
                      reference=reference,
                      network_conn=network_conn,
                      shared_reference=shared_reference,
                      non_mutable_uid=non_mutable_uid,
                      base_var=base_var)


    elif t == "BinOp":
        obj = BinOp(_dict_to_expr(data["left"]), data["op"], _dict_to_expr(data["right"]))

    elif t == "UnOp":
        obj = UnOp(data["op"], _dict_to_expr(data["operand"]))

    elif t == "Func":
        op = data.get("op", None)
        if op is None:
            op = data["name"]
        obj = Func(_dict_to_expr(data["arg"]), op)

    elif t == "Func2":
        obj = Func2(data["name"], _dict_to_expr(data["arg1"]), _dict_to_expr(data["arg2"]))
    elif t == "Comparison":
        lhs_expr = _dict_to_expr(data["lhs"])
        rhs_expr = _dict_to_expr(data["rhs"])
        if not isinstance(lhs_expr, Expr) or not isinstance(rhs_expr, Expr):
            raise TypeError("Comparison serialization expects symbolic Expr operands")

        op_value = data["op"]
        if op_value == CmpOp.LE.value:
            op = CmpOp.LE
        elif op_value == CmpOp.GE.value:
            op = CmpOp.GE
        elif op_value == CmpOp.LT.value:
            op = CmpOp.LT
        elif op_value == CmpOp.GT.value:
            op = CmpOp.GT
        elif op_value == CmpOp.EQ.value:
            op = CmpOp.EQ
        else:
            raise ValueError(f"Unknown comparison operator '{op_value}'")
        return Comparison(lhs_expr, op, rhs_expr)

    else:
        raise ValueError(f"Unknown type '{t}' in deserialisation")

    obj.uid = data["uid"]
    return obj


# ----------------------------------------------------------------------------------------------------------------------
# Convenience top‑level helpers
# ----------------------------------------------------------------------------------------------------------------------

def diff(expr: Expr, var: Var | str, order: int = 1) -> Expr:  # noqa: D401 – simple
    """
    Return ∂^order(expr)/∂var^order.
    :param expr: Expression
    :param var: Variable to differentiate against
    :param order: Derivative order
    :return: Derivative expression
    """
    return expr.diff(var, order)


def eval_uid(expr: Expr, uid_bindings: Dict[int, NUMBER]) -> NUMBER:  # noqa: D401 – simple
    """
    Evaluate *expr* with a mapping from node UID → numeric value.
    :param expr:
    :param uid_bindings:
    :return:
    """
    return expr.eval_uid(uid_bindings)


def _collect_vars(expr: Expr, out: Set[Var]) -> None:
    """
    Collect variables in a deterministic order
    Depth-first, left-to-right variable harvest.
    :param expr: Some expression
    :param out: List to fill
    :return: None
    """
    if isinstance(expr, Var):
        if expr not in out:
            out.add(expr)
    elif isinstance(expr, BinOp):
        _collect_vars(expr.left, out)
        _collect_vars(expr.right, out)
    elif isinstance(expr, UnOp):
        _collect_vars(expr.operand, out)
    elif isinstance(expr, Func):
        _collect_vars(expr.arg, out)
    elif isinstance(expr, Func2):
        _collect_vars(expr.arg1, out)
        _collect_vars(expr.arg2, out)


def _all_vars(expressions: Sequence[Expr]) -> List[Var]:
    """
    Collect all variables in a list of expressions
    :param expressions: Any iterable of expressions
    :return: List of non-repeated variables
    """
    res: Set[Var] = set()
    for e in expressions:
        _collect_vars(e, res)
    return list(res)


def _precedence(expr: Expr) -> int:
    """
    Return operator precedence for expression emission.

    :param expr: Symbolic expression.
    :return: Precedence value.
    """
    if isinstance(expr, BinOp):
        if expr.op == "+" or expr.op == "-":
            return 10
        elif expr.op == "*" or expr.op == "/":
            return 20
        elif expr.op == "**":
            return 30
        else:
            return 0
    elif isinstance(expr, UnOp):
        return 40
    elif isinstance(expr, (Const, Var)):
        return 100
    elif isinstance(expr, Func):
        return 50
    elif isinstance(expr, Func2):
        return 50
    else:
        return 0


def expression2numba(expr: Expr,
                     compiler_names_dict: Dict[int, str],
                     parent_prec: int = 0) -> str:
    """
    Emit a precedence-aware, Numba-friendly Python expression.
    Parentheses are added only when required.
    """

    my_prec = _precedence(expr)

    if isinstance(expr, Const):
        s = repr(expr.value)

    elif isinstance(expr, Var):
        if expr.uid in compiler_names_dict:
            s = compiler_names_dict[expr.uid]
        elif expr.name in {"time", "glob_time"}:
            s = "glob_time"
        else:
            raise KeyError(f"Missing compiler name for var '{expr.name}' (uid={expr.uid})")

    elif isinstance(expr, UnOp):
        operand = expression2numba(expr.operand,
                                   compiler_names_dict,
                                   my_prec)
        s = f"-{operand}"

    elif isinstance(expr, BinOp):
        left = expression2numba(expr.left,
                                compiler_names_dict,
                                my_prec)

        # +1 enforces left associativity
        right = expression2numba(expr.right,
                                 compiler_names_dict,
                                 my_prec + 1)

        s = f"{left} {expr.op} {right}"

    elif isinstance(expr, Func):
        arg = expression2numba(expr.arg,
                               compiler_names_dict,
                               0)
        if expr.op == "heaviside":
            s = f"_heaviside({arg})"
        elif expr.op == "rand":
            s = "np.random.rand()"
        elif expr.op == "atan":
            s = f"np.arctan({arg})"
        else:
            s = f"np.{expr.op}({arg})"

    elif isinstance(expr, Func2):
        arg1 = expression2numba(expr.arg1, compiler_names_dict, 0)
        arg2 = expression2numba(expr.arg2, compiler_names_dict, 0)
        s = _binary_function_to_python(name=expr.name, arg1=arg1, arg2=arg2)

    else:
        raise TypeError(type(expr))

    # Add parentheses only if this expression binds weaker than the parent
    if my_prec < parent_prec:
        return f"({s})"
    else:
        return s


def _emit_event_params_eq(expr: Expr, uid_map_t: Dict[int, str] | None = None) -> str:
    """
    Emit an event-parameter expression as pure Python source.

    :param expr: Symbolic expression to emit.
    :param uid_map_t: Optional uid-to-name mapping for event parameters.
    :return: Numba-friendly Python expression string.
    """
    if uid_map_t is None:
        uid_map_t = dict()

    if isinstance(expr, Const):
        return repr(expr.value)

    if isinstance(expr, Var):
        if expr.uid in uid_map_t:
            return uid_map_t[expr.uid]
        elif expr.name in {"time", "glob_time"}:
            return "glob_time"
        else:
            raise KeyError(expr.uid)

    if isinstance(expr, UnOp):
        return f"-({_emit_event_params_eq(expr.operand, uid_map_t)})"

    if isinstance(expr, BinOp):
        return f"({_emit_event_params_eq(expr.left, uid_map_t)} {expr.op} {_emit_event_params_eq(expr.right, uid_map_t)})"

    if isinstance(expr, Func):

        if expr.op == "heaviside":
            return f"_heaviside({_emit_event_params_eq(expr.arg, uid_map_t)})"
        elif expr.op == "rand":
            return "np.random.rand()"
        elif expr.op == "atan":
            return f"np.arctan({_emit_event_params_eq(expr.arg, uid_map_t)})"
        else:
            return f"np.{expr.op}({_emit_event_params_eq(expr.arg, uid_map_t)})"
    if isinstance(expr, Func2):
        arg1 = _emit_event_params_eq(expr.arg1, uid_map_t)
        arg2 = _emit_event_params_eq(expr.arg2, uid_map_t)
        return _binary_function_to_python(name=expr.name, arg1=arg1, arg2=arg2)
    else:
        raise ValueError(f"Unsupported expression '{type(expr).__name__}' in _emit_params_eq")


def _emit_one(expr: Expr, uid_map_vars: Dict[int, str], uid_map_event_params: Dict[int, str],
              uid_map_params: Dict[int, str]) -> str:
    """
    Emit a pure-Python (Numba-friendly) expression string
    :param expr: Expr (expression)
    :param uid_map_vars:
    :return:
    """
    if isinstance(expr, Const):
        return repr(expr.value)

    if isinstance(expr, Var):
        if expr.uid in uid_map_vars:
            return uid_map_vars[expr.uid]  # positional variable
        elif expr.uid in uid_map_event_params:
            return uid_map_event_params[expr.uid]  # positional variable
        elif expr.name in {"time", "glob_time"}:
            return "glob_time"
        else:
            return uid_map_params[expr.uid]

    if isinstance(expr, UnOp):
        return f"-({_emit_one(expr.operand, uid_map_vars, uid_map_event_params, uid_map_params)})"

    if isinstance(expr, BinOp):
        return (f"({_emit_one(expr.left, uid_map_vars, uid_map_event_params, uid_map_params)} "
                f"{expr.op} {_emit_one(expr.right, uid_map_vars, uid_map_event_params, uid_map_params)})")

    if isinstance(expr, Func):

        if expr.op == "heaviside":
            return f"_heaviside({_emit_one(expr.arg, uid_map_vars, uid_map_event_params, uid_map_params)})"
        elif expr.op == "rand":
            return "np.random.rand()"
        elif expr.op == "atan":
            return f"np.arctan({_emit_one(expr.arg, uid_map_vars, uid_map_event_params, uid_map_params)})"
        else:
            return f"np.{expr.op}({_emit_one(expr.arg, uid_map_vars, uid_map_event_params, uid_map_params)})"

    if isinstance(expr, Func2):
        arg1 = _emit_one(expr.arg1, uid_map_vars, uid_map_event_params, uid_map_params)
        arg2 = _emit_one(expr.arg2, uid_map_vars, uid_map_event_params, uid_map_params)
        return _binary_function_to_python(name=expr.name, arg1=arg1, arg2=arg2)

    raise TypeError(expr)


def find_vars_order(expressions: Union[Expr, Sequence[Expr]],
                    ordering: Sequence[Var] | None = None,
                    var_dict: Dict[int, Var] | None = None) -> List[Var]:
    """
    Return the variable list that positional JIT functions will expect.
    :param expressions: Single expression or any iterable of expressions.
    :param ordering: Is provided, it overrides the default left‑to‑right order.
                    Items in *ordering* can be Var objects or variable names (strings).
    :param var_dict: Dictionary of var uid to var ({v.uid: v for v in vars_list})
    :return:
    """

    if isinstance(expressions, Expr):

        vars_list = _all_vars([expressions])
    else:
        vars_list = _all_vars(expressions)

    if ordering is None:
        return vars_list

    if var_dict is None:
        var_dict: Dict[int, Var] = {v.uid: v for v in vars_list}

    return [v if isinstance(v, Var) else var_dict[v.uid] for v in ordering]


def get_expression_vars(expr: Expr, vars_found: Optional[List[Var]] = None) -> List[Var]:
    """
    Get the list of variables from any expression
    :param expr: Expression Expr
    :param vars_found: already existing list of vars
    :return: Final list of vars
    """
    if vars_found is None:
        vars_found = list()

    if isinstance(expr, Var):
        if expr not in vars_found:
            vars_found.append(expr)

    elif isinstance(expr, BinOp):
        get_expression_vars(expr.left, vars_found)
        get_expression_vars(expr.right, vars_found)

    elif isinstance(expr, UnOp):
        get_expression_vars(expr.operand, vars_found)

    elif isinstance(expr, Func):
        get_expression_vars(expr.arg, vars_found)
    elif isinstance(expr, Func2):
        get_expression_vars(expr.arg1, vars_found)
        get_expression_vars(expr.arg2, vars_found)

    # Todo: add comparisions

    return vars_found


def _get_binop_symbol(op_node: ast.operator) -> str | None:
    """
    Translate a Python AST binary operator into a symbolic operator token.

    :param op_node: Python AST operator node.
    :return: Symbolic operator token or ``None``.
    """
    if isinstance(op_node, ast.Add):
        return "+"
    elif isinstance(op_node, ast.Sub):
        return "-"
    elif isinstance(op_node, ast.Mult):
        return "*"
    elif isinstance(op_node, ast.Div):
        return "/"
    elif isinstance(op_node, ast.Pow):
        return "**"
    else:
        return None


def _get_unop_symbol(op_node: ast.unaryop) -> str | None:
    """
    Translate a Python AST unary operator into a symbolic operator token.

    :param op_node: Python AST unary operator node.
    :return: Symbolic operator token or ``None``.
    """
    if isinstance(op_node, ast.USub):
        return "-"
    else:
        return None


def _call_symbolic_parser_function(function_name: str, arg_expr: Expr) -> Expr:
    """
    Invoke a supported unary symbolic parser function by name.

    :param function_name: Public parser function name.
    :param arg_expr: Symbolic argument.
    :return: Parsed symbolic expression.
    """
    if function_name == "sin":
        return sin(arg_expr)
    elif function_name == "cos":
        return cos(arg_expr)
    elif function_name == "tan":
        return tan(arg_expr)
    elif function_name == "exp":
        return exp(arg_expr)
    elif function_name == "log":
        return log(arg_expr)
    elif function_name == "log10":
        return log10(arg_expr)
    elif function_name == "sqrt":
        return sqrt(arg_expr)
    elif function_name == "asin":
        return asin(arg_expr)
    elif function_name == "acos":
        return acos(arg_expr)
    elif function_name == "atan":
        return atan(arg_expr)
    elif function_name == "sinh":
        return sinh(arg_expr)
    elif function_name == "cosh":
        return cosh(arg_expr)
    elif function_name == "tanh":
        return tanh(arg_expr)
    elif function_name == "abs":
        return abs(arg_expr)
    elif function_name == "real":
        return real(arg_expr)
    elif function_name == "imag":
        return imag(arg_expr)
    elif function_name == "conj":
        return conj(arg_expr)
    elif function_name == "angle":
        return angle(arg_expr)
    elif function_name == "heaviside":
        return heaviside(arg_expr)
    elif function_name == "rand":
        return rand(arg_expr)
    elif function_name == "floor":
        return floor(arg_expr)
    elif function_name == "ceil":
        return ceil(arg_expr)
    elif function_name == "round":
        return round(arg_expr)
    else:
        raise ValueError(f"Unknown function '{function_name}'")


def _get_symbolic_parser_unary_function_names_internal() -> List[str]:
    """
    Return the public unary functions accepted by the symbolic parser.

    :return: Supported unary parser function names.
    """
    return list((
        "sin",
        "cos",
        "tan",
        "exp",
        "log",
        "log10",
        "sqrt",
        "asin",
        "acos",
        "atan",
        "sinh",
        "cosh",
        "tanh",
        "abs",
        "real",
        "imag",
        "conj",
        "angle",
        "heaviside",
        "rand",
        "floor",
        "ceil",
        "round",
    ))


def _get_symbolic_parser_binary_function_names_internal() -> List[str]:
    """Return the public binary functions accepted by the symbolic parser.

    :return: Supported two-argument parser function names.
    """
    return list((
        "atan2",
        "min",
        "max",
    ))


def _ast_to_symbolic(node: ast.AST, symbol_namespace: Mapping[str, Expr | NUMBER]) -> Expr | Comparison:
    """Convert one restricted Python AST node into a symbolic expression.

    :param node: Python syntax node belonging to the parsed expression.
    :param symbol_namespace: Explicit symbolic identities accepted by name.
    :return: Symbolic expression or comparison represented by ``node``.
    :raises ValueError: If the node uses unsupported syntax or identities.
    """
    left_expr: Expr | Comparison
    right_expr: Expr | Comparison
    function_name: str
    op_symbol: str | None

    if isinstance(node, ast.Expression):
        return _ast_to_symbolic(node.body, symbol_namespace)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)) or node.value is None:
            return Const(node.value)
        else:
            raise ValueError(f"Unsupported constant value {node.value!r}")
    elif isinstance(node, ast.Name):
        if node.id in symbol_namespace:
            return _to_expr(symbol_namespace[node.id])
        else:
            raise ValueError(f"Unknown symbol '{node.id}'")
    elif isinstance(node, ast.BinOp):
        left_expr = _ast_to_symbolic(node.left, symbol_namespace)
        right_expr = _ast_to_symbolic(node.right, symbol_namespace)
        op_symbol = _get_binop_symbol(node.op)

        if isinstance(left_expr, Expr) and isinstance(right_expr, Expr):
            if op_symbol is not None:
                return BinOp(left_expr, op_symbol, right_expr)
            else:
                raise ValueError(f"Unsupported binary operator {type(node.op).__name__}")
        else:
            raise ValueError("Binary expressions require symbolic operands")
    elif isinstance(node, ast.UnaryOp):
        op_symbol = _get_unop_symbol(node.op)
        right_expr = _ast_to_symbolic(node.operand, symbol_namespace)

        if isinstance(right_expr, Expr):
            if op_symbol is not None:
                return UnOp(op_symbol, right_expr)
            else:
                raise ValueError(f"Unsupported unary operator {type(node.op).__name__}")
        else:
            raise ValueError("Unary expressions require a symbolic operand")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if len(node.args) == 1 and len(node.keywords) == 0:
                function_name = node.func.id
                right_expr = _ast_to_symbolic(node.args[0], symbol_namespace)

                if isinstance(right_expr, Expr):
                    return _call_symbolic_parser_function(function_name, right_expr)
                else:
                    raise ValueError("Function calls require a symbolic argument")
            elif len(node.args) == 2 and len(node.keywords) == 0:
                function_name = node.func.id
                left_expr = _ast_to_symbolic(node.args[0], symbol_namespace)
                right_expr = _ast_to_symbolic(node.args[1], symbol_namespace)

                # Binary parser functions are kept in the same symbolic
                # catalogue as unary functions so every editor and importer
                # observes one authoritative language definition.
                binary_function_names: List[str] = (
                    _get_symbolic_parser_binary_function_names_internal()
                )
                if (function_name in binary_function_names
                        and isinstance(left_expr, Expr)
                        and isinstance(right_expr, Expr)):
                    return Func2(function_name, left_expr, right_expr)
                else:
                    raise ValueError(
                        f"Unknown two-argument function '{function_name}'"
                    )
            else:
                raise ValueError("Only supported one- or two-argument functions are allowed")
        else:
            raise ValueError("Only named functions are supported")
    elif isinstance(node, ast.Compare):
        if len(node.ops) == 1 and len(node.comparators) == 1:
            left_expr = _ast_to_symbolic(node.left, symbol_namespace)
            right_expr = _ast_to_symbolic(node.comparators[0], symbol_namespace)

            if isinstance(left_expr, Expr) and isinstance(right_expr, Expr):
                if isinstance(node.ops[0], ast.Lt):
                    return left_expr < right_expr
                elif isinstance(node.ops[0], ast.LtE):
                    return left_expr <= right_expr
                elif isinstance(node.ops[0], ast.Gt):
                    return left_expr > right_expr
                elif isinstance(node.ops[0], ast.GtE):
                    return left_expr >= right_expr
                elif isinstance(node.ops[0], ast.Eq):
                    return left_expr == right_expr
                else:
                    raise ValueError(f"Unsupported comparison operator {type(node.ops[0]).__name__}")
            else:
                raise ValueError("Comparisons require symbolic operands")
        else:
            raise ValueError("Only simple two-sided comparisons are supported")
    else:
        raise ValueError(f"Unsupported expression node {type(node).__name__}")


def string_to_symbolic(expression_text: str, symbol_namespace: Mapping[str, Expr | NUMBER]) -> Expr | Comparison:
    """Parse restricted source text into a symbolic expression tree.

    :param expression_text: Python-like symbolic expression without assignments.
    :param symbol_namespace: Explicit symbolic identities accepted by name.
    :return: Parsed symbolic expression or comparison.
    :raises SyntaxError: If ``expression_text`` is not valid Python expression syntax.
    :raises ValueError: If the expression uses unsupported syntax or identities.
    """
    expression_tree: ast.Expression = ast.parse(expression_text, mode="eval")
    return _ast_to_symbolic(expression_tree, symbol_namespace)


def get_symbolic_parser_function_names() -> List[str]:
    """
    Return every public function accepted by :func:`string_to_symbolic`.

    :return: Detached ordered list of unary and binary function names.
    """
    function_names: List[str] = _get_symbolic_parser_unary_function_names_internal()
    function_names.extend(_get_symbolic_parser_binary_function_names_internal())
    return function_names


def get_symbolic_parser_function_arity(function_name: str) -> int | None:
    """Return the positional arity of one public symbolic parser function.

    :param function_name: Function name obtained from symbolic source text.
    :return: Required positional argument count, or ``None`` when unsupported.
    """
    unary_function_names: List[str] = _get_symbolic_parser_unary_function_names_internal()
    binary_function_names: List[str] = _get_symbolic_parser_binary_function_names_internal()
    if function_name in unary_function_names:
        result: int | None = 1
    elif function_name in binary_function_names:
        result = 2
    else:
        result = None
    return result


def symbolic_to_string(expr: Expr) -> str:
    """
    Convert a symbolic expression into a string (parsable by parse_expr).
    """
    if isinstance(expr, Const):
        return str(expr.value)
    elif isinstance(expr, Var):
        return expr.name
    elif isinstance(expr, UnOp):
        if expr.op == "-":
            return f"-({symbolic_to_string(expr.operand)})"
        return f"{expr.op}({symbolic_to_string(expr.operand)})"
    elif isinstance(expr, BinOp):
        left = symbolic_to_string(expr.left)
        right = symbolic_to_string(expr.right)
        return f"({left} {expr.op} {right})"
    elif isinstance(expr, Func):
        return f"{expr.op}({symbolic_to_string(expr.arg)})"
    elif isinstance(expr, Func2):
        return f"{expr.name}({symbolic_to_string(expr.arg1)}, {symbolic_to_string(expr.arg2)})"
    elif isinstance(expr, Comparison):
        left = symbolic_to_string(expr.lhs)
        right = symbolic_to_string(expr.rhs)
        return f"({left} {expr.op} {right})"
    else:
        raise TypeError(f"Unsupported expression type: {type(expr)}")


# -----------------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------------

__all__ = [
    "Expr", "Const", "Var", "BinOp", "UnOp", "Func", "CmpOp", "Comparison", "Func2",
    "sin", "cos", "tan", "exp", "log", "sqrt",
    "asin", "acos", "atan", "sinh", "cosh",
    "diff", "eval_uid",
    "find_vars_order",
    "heaviside",
    "rand",
    "atan2",
    "safe_divide",
    "piecewise",
    "symbolic_to_string",
    "string_to_symbolic",
    "get_symbolic_parser_function_names",
    "get_symbolic_parser_function_arity",
    "hard_sat",
    "f_exc",
    'expression2numba',
    'heaviside_num',
    'get_expression_vars',
    '_dict_to_expr',
    '_expr_to_dict',
    'abs',
    '_to_expr',
    'get_namespace',
    'SharedVarReferenceType'
]
