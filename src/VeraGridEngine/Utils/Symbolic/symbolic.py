# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import json
import math
import pdb
import uuid
import numpy as np
from enum import Enum
from scipy.sparse import csc_matrix
import numba as nb
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Dict, Mapping, Union, List, Sequence, Tuple, Set

# from VeraGridEngine.Utils.Symbolic.events import EventParam

NUMBER = Union[int, float, complex]

NAME = 'name'


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
    if isinstance(val, Expr):
        return val
    if isinstance(val, (int, float, complex)):
        return Const(val)
    raise TypeError(f"Cannot convert {val!r} to Expr")


def _var_name(sym: Var | str) -> str:
    return sym.name if isinstance(sym, Var) else sym


def _var_uid(sym: Var | str) -> str:
    return sym.uid if isinstance(sym, Var) else sym


# ----------------------------------------------------------------------------
# Function helpers
# ----------------------------------------------------------------------------

def _stepwise(x: NUMBER) -> NUMBER:
    return 1 if x >= 0 else 0


def _heaviside(x: NUMBER) -> NUMBER:
    if x > 0:
        return 1
    elif x < 0:
        return 0
    else:
        return 0.5


class CmpOp(Enum):
    LE = "≤"  # ≤
    GE = "≥"  # ≥
    LT = "<"
    GT = ">"
    EQ = "="  # =


@dataclass(frozen=True, slots=True)
class Comparison:
    lhs: "Expr"
    op: CmpOp  # "<=", ">=", "=="
    rhs: Union["Expr", NUMBER]


class Expr:
    """
    Abstract base class for all expression nodes.
    """
    uid: str  # real dataclass field lives in subclasses

    def eval(self, **bindings: float | int) -> float | int:  # pragma: no cover – abstract
        """
        Numeric evaluation
        :param bindings:
        :return:
        """
        raise NotImplementedError

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:  # pragma: no cover – abstract
        """

        :param uid_bindings:
        :return:
        """
        raise NotImplementedError

    __call__ = eval  # allow f(x=…)

    def diff(self, var: Var | str, order: int = 1) -> "Expr":
        """
        Differentiation (higher‑order)
        :param var:
        :param order:
        :return:
        """
        if order < 0:
            raise ValueError("order must be >= 0")
        expr: Expr = self
        for _ in range(order):
            expr = expr._diff1(var).simplify()
        return expr

    def _diff1(self, var: Var | str) -> "Expr":  # pragma: no cover
        raise NotImplementedError

    def simplify(self) -> "Expr":
        """
        Simplification & substitution (no‑ops by default)
        :return:
        """
        return self

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Expr":
        return mapping.get(self, self)

    def to_dict(self) -> Dict[str, Any]:
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
    def __add__(self, other: Any) -> "Expr":
        return BinOp("+", self, _to_expr(other))

    def __radd__(self, other: Any) -> "Expr":
        return BinOp("+", _to_expr(other), self)

    def __sub__(self, other: Any) -> "Expr":
        return BinOp("-", self, _to_expr(other))

    def __rsub__(self, other: Any) -> "Expr":
        return BinOp("-", _to_expr(other), self)

    def __mul__(self, other: Any) -> "Expr":
        return BinOp("*", self, _to_expr(other))

    def __rmul__(self, other: Any) -> "Expr":
        return BinOp("*", _to_expr(other), self)

    def __truediv__(self, other: Any) -> "Expr":
        return BinOp("/", self, _to_expr(other))

    def __rtruediv__(self, other: Any) -> "Expr":
        return BinOp("/", _to_expr(other), self)

    def __pow__(self, other: Any) -> "Expr":
        return BinOp("**", self, _to_expr(other))

    def __rpow__(self, other: Any) -> "Expr":
        return BinOp("**", _to_expr(other), self)

    def __neg__(self) -> "Expr":
        return UnOp("-", self)

    def __le__(self, other: "Expr" | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.LE, other)

    def __ge__(self, other: "Expr" | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.GE, other)

    def __eq__(self, other: "Expr" | NUMBER) -> Comparison:  # type: ignore[override]
        return Comparison(self, CmpOp.EQ, other)

    def __lt__(self, other: "Expr" | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.LT, other)

    def __gt__(self, other: "Expr" | NUMBER) -> Comparison:
        return Comparison(self, CmpOp.GT, other)

    def __str__(self) -> str:  # pragma: no cover – abstract
        """
        Display helper
        :return:
        """
        raise NotImplementedError

    def __repr__(self):
        return self.__str__()


# ----------------------------------------------------------------------------------------------------------------------
# Atomic nodes
# ----------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Const(Expr):
    value: NUMBER
    name: str = 'name'
    uid: int = field(default_factory=_new_uid)

    def eval(self, **bindings: NUMBER) -> NUMBER:
        return self.value

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        return self.value

    def _diff1(self, var: Var | str) -> "Expr":
        return Const(0)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        if self in mapping:
            return mapping[self]
        if self.name in mapping:
            return mapping[self.name]
        return self

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return self.__str__()


@dataclass(frozen=True)
class Var(Expr):
    """
    Any variable
    """
    name: str
    uid: int = field(default_factory=_new_uid)

    def eval(self, **bindings: NUMBER) -> NUMBER:
        try:
            return bindings[self.name]
        except KeyError as exc:
            raise ValueError(f"No value for variable '{self.name}'.") from exc

    def eval_uid(self, uid_bindings: Dict[int, NUMBER]) -> NUMBER:
        try:
            return uid_bindings[self.uid]
        except KeyError as exc:
            raise ValueError(f"No value for uid '{self.uid}'.") from exc

    def _diff1(self, var: Var | str) -> Expr:
        return Const(1 if self.uid == _var_uid(var) else 0)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        if self in mapping:
            return mapping[self]
        if self.name in mapping:
            return mapping[self.name]
        return self

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    # def __eq__(self, other: "Var"):
    #     return self.uid == other.uid
    def __eq__(self, other: "Expr" | NUMBER) -> Comparison:  # type: ignore[override]
        return Comparison(self, CmpOp.EQ, other)


@dataclass(frozen=True)
class BinOp(Expr):
    """
    Binary operation expression
    """
    op: str
    left: Expr
    right: Expr
    uid: int = field(default_factory=_new_uid, init=False)

    _impl: ClassVar[Mapping[str, Callable[[NUMBER, NUMBER], NUMBER]]] = MappingProxyType({
        "+": lambda a, b: a + b,
        "-": lambda a, b: a - b,
        "*": lambda a, b: a * b,
        "/": lambda a, b: a / b,
        "**": lambda a, b: a ** b,
    })

    def eval(self, **bindings: NUMBER) -> NUMBER:
        """
        Evaluation using names
        :param bindings:
        :return:
        """
        return self._impl[self.op](self.left.eval(**bindings), self.right.eval(**bindings))

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        """
        Evaluate using uuid's
        :param uid_bindings:
        :return:
        """
        return self._impl[self.op](self.left.eval_uid(uid_bindings), self.right.eval_uid(uid_bindings))

    def _diff1(self, var: Var | str) -> Expr:
        """
        Differentiation of this expression w.r.t var
        :param var: variable to differentiate with respect to
        :return: Expression
        """
        u, v = self.left, self.right
        du, dv = u._diff1(var), v._diff1(var)
        if self.op == "+":
            return du + dv
        if self.op == "-":
            return du - dv
        if self.op == "*":
            return du * v + u * dv
        if self.op == "/":
            return (du * v - u * dv) / (v ** Const(2))
        if self.op == "**":
            if isinstance(v, Const):
                # numeric exponent
                n = v.value
                return Const(n) * (u ** Const(n - 1)) * du
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
            return Const(self._impl[self.op](l.value, r.value))

        if self.op == "+":
            if isinstance(l, Const) and l.value == 0:
                return r
            if isinstance(r, Const) and r.value == 0:
                return l

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

        return BinOp(self.op, l, r)

    def subs(self, mapping: Dict[Any, Expr]) -> Expr:
        """
        Substitution
        :param mapping: mapping of variables to expressions
        :return:
        """
        if self in mapping:
            return mapping[self]
        return BinOp(self.op, self.left.subs(mapping), self.right.subs(mapping))

    def __str__(self) -> str:
        return f"({self.left}) {self.op} ({self.right})"

    def __repr__(self) -> str:
        return self.__str__()


@dataclass(frozen=True)
class UnOp(Expr):
    """
    Unary operation expression
    """
    op: str
    operand: Expr
    uid: int = field(default_factory=_new_uid, init=False)

    def eval(self, **bindings: NUMBER) -> NUMBER:
        val = self.operand.eval(**bindings)
        return -val if self.op == "-" else math.nan

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        val = self.operand.eval_uid(uid_bindings)
        return -val if self.op == "-" else math.nan

    def _diff1(self, var: Var | str) -> "Expr":
        return -self.operand._diff1(var) if self.op == "-" else Const(float("nan"))

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

    def __str__(self) -> str:
        return f"{self.op}({self.operand})"

    def __repr__(self) -> str:
        return self.__str__()


# ----------------------------------------------------------------------------------------------------------------------
# Functional nodes
# ----------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Func(Expr):
    name: str
    arg: Expr
    uid: int = field(default_factory=_new_uid, init=False)

    _impl: ClassVar[Mapping[str, Callable[[NUMBER], NUMBER]]] = MappingProxyType({
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "exp": np.exp,
        "log": math.log,
        "sqrt": math.sqrt,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "sinh": math.sinh,
        "cosh": math.cosh,
        "real": np.real,
        "imag": np.imag,
        "conj": np.conj,
        "angle": np.angle,
        "abs": np.abs,

        "stepwise": _stepwise,
        "heaviside": _heaviside
    })

    # --- evaluation ----------------------------------------------------------
    def eval(self, **bindings: NUMBER) -> NUMBER:
        return self._impl[self.name](self.arg.eval(**bindings))

    def eval_uid(self, uid_bindings: Dict[str, NUMBER]) -> NUMBER:
        return self._impl[self.name](self.arg.eval_uid(uid_bindings))

    # --- differentiation (chain rule) ---------------------------------------
    def _diff1(self, var: Var | str) -> "Expr":
        u = self.arg
        du = u._diff1(var)
        if isinstance(du, Const) and du.value == 0:
            return Const(0)
        if self.name == "sin":
            return cos(u) * du
        if self.name == "cos":
            return -sin(u) * du
        if self.name == "tan":
            return (sec(u) ** Const(2)) * du  # sec defined later
        if self.name == "exp":
            return exp(u) * du
        if self.name == "log":
            return du / u
        if self.name == "sqrt":
            return du / (Const(2) * sqrt(u))
        if self.name == "asin":
            return du / sqrt(Const(1) - u ** Const(2))
        if self.name == "acos":
            return -du / sqrt(Const(1) - u ** Const(2))
        if self.name == "atan":
            return du / (Const(1) + u ** Const(2))
        if self.name == "sinh":
            return cosh(u) * du
        if self.name == "cosh":
            return sinh(u) * du
        if self.name == "stepwise":
            return Const(0)
        if self.name == "heaviside":
            return Const(0)
        raise ValueError(f"Unknown function '{self.name}'")

    # --- simplification ------------------------------------------------------
    def simplify(self) -> "Expr":
        a = self.arg.simplify()
        if isinstance(a, Const):
            try:
                return Const(self._impl[self.name](a.value))
            except ValueError:
                pass  # domain error – keep symbolic
        return Func(self.name, a)

    def subs(self, mapping: Dict[Any, "Expr"]) -> "Expr":
        if self in mapping:
            return mapping[self]
        return Func(self.name, self.arg.subs(mapping))

    def __str__(self) -> str:
        return f"{self.name}({self.arg})"

    def __repr__(self) -> str:
        return self.__str__()


# Helpers for functions not primitive nodes (sec for tan derivative)

def sec(x: Any) -> Expr:
    return Const(1) / cos(x)


# -----------------------------------------------------------------------------
# Public constructor helpers
# -----------------------------------------------------------------------------

def _make_unary(name: str):
    return lambda x: Func(name, _to_expr(x))


sin = _make_unary("sin")
cos = _make_unary("cos")
tan = _make_unary("tan")
exp = _make_unary("exp")
log = _make_unary("log")
sqrt = _make_unary("sqrt")
asin = _make_unary("asin")
acos = _make_unary("acos")
atan = _make_unary("atan")
sinh = _make_unary("sinh")
cosh = _make_unary("cosh")
real = _make_unary("real")
imag = _make_unary("imag")
conj = _make_unary("conj")
angle = _make_unary("angle")
abs = _make_unary("abs")
stepwise = _make_unary("stepwise")
heaviside = _make_unary("heaviside")


def _expr_to_dict(expr: Expr) -> Dict[str, Any]:
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
        return {"type": "Const", "value": expr.value, "uid": expr.uid}

    if isinstance(expr, Var):
        return {"type": "Var", "name": expr.name, "uid": expr.uid}

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
            "name": expr.name,  # sin, cos, log, …
            "arg": _expr_to_dict(expr.arg),
            "uid": expr.uid,
        }

    # ------------------------------------------------------------------
    # Anything else is an API bug
    # ------------------------------------------------------------------
    raise TypeError(f"Unsupported Expr subclass: {type(expr).__name__}")


def _dict_to_expr(data: Dict[str, Any]) -> Expr:
    """
    De-Serialize expression from dictionary
    :param data:
    :return:
    """
    t = data["type"]
    if t == "Const":
        obj: Expr = Const(data["value"])
    elif t == "Var":
        obj = Var(data["name"])
    elif t == "BinOp":
        obj = BinOp(data["op"], _dict_to_expr(data["left"]), _dict_to_expr(data["right"]))
    elif t == "UnOp":
        obj = UnOp(data["op"], _dict_to_expr(data["operand"]))
    elif t == "Func":
        obj = Func(data["name"], _dict_to_expr(data["arg"]))
    else:
        raise ValueError(f"Unknown type '{t}' in deserialisation")
    object.__setattr__(obj, "uid", data["uid"])
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


def eval_uid(expr: Expr, uid_bindings: Dict[str, NUMBER]) -> NUMBER:  # noqa: D401 – simple
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


def _emit(expr: Expr, uid_map_vars: Dict[int, str], uid_map_params: Dict[int, str]) -> str:
    """
    Emit a pure-Python (Numba-friendly) expression string
    :param expr: Expr (expression)
    :param uid_map:
    :return:
    """

    if isinstance(expr, Const):
        return repr(expr.value)
    if isinstance(expr, Var):
        if expr.uid in uid_map_vars.keys():
            return uid_map_vars[expr.uid]  # positional variable
        else:
            # pdb.set_trace()
            return uid_map_params[expr.uid]
    if isinstance(expr, UnOp):
        return f"-({_emit(expr.operand, uid_map_vars, uid_map_params)})"
    if isinstance(expr, BinOp):
        return f"({_emit(expr.left, uid_map_vars, uid_map_params)} {expr.op} {_emit(expr.right, uid_map_vars, uid_map_params)})"
    if isinstance(expr, Func):
        if expr.name in ("real", "imag", "conj", "angle"):
            return f"np.{expr.name}({_emit(expr.arg, uid_map_vars, uid_map_params)})"
        else:
            return f"np.{expr.name}({_emit(expr.arg, uid_map_vars, uid_map_params)})"

    raise TypeError(type(expr))

def _emit_one(expr: Expr, uid_map_vars: Dict[int, str]) -> str:
    """
    Emit a pure-Python (Numba-friendly) expression string
    :param expr: Expr (expression)
    :param uid_map:
    :return:
    """
    if isinstance(expr, Const):
        return repr(expr.value)
    if isinstance(expr, Var):
        return uid_map_vars[expr.uid]  # positional variable
    if isinstance(expr, UnOp):
        return f"-({_emit_one(expr.operand, uid_map_vars)})"
    if isinstance(expr, BinOp):
        return f"({_emit_one(expr.left, uid_map_vars)} {expr.op} {_emit_one(expr.right, uid_map_vars)})"
    if isinstance(expr, Func):
        if expr.name in ("real", "imag", "conj", "angle"):
            return f"np.{expr.name}({_emit_one(expr.arg, uid_map_vars)})"
        else:
            return f"np.{expr.name}({_emit_one(expr.arg, uid_map_vars)})"

    raise TypeError(type(expr))


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


def _compile(expressions: Sequence[Expr],
             sorting_vars: List[Var],
             params: Sequence[Var] | None,
             uid2sym: Dict[int, str] | None,
             add_doc_string: bool = True) -> Callable[[Any], Sequence[float]]:
    """
    Compile the array of expressions to a function that returns an array of values for those expressions
    :param expressions: Iterable of expressions (Expr)
    :param sorting_vars: list of variables indicating the sorting order of the call
    :param add_doc_string: add the docstring?
    :return: Function pointer that returns an array
    """
    if uid2sym is None:
        uid2sym: Dict[int, str] = {v.uid: f"vars[{i}]" for i, v in enumerate(sorting_vars)}
        if params is not None:
            n_sorting_vars = len(sorting_vars)
            for i, v in enumerate(params):
                uid2sym[v.uid] = f"param[{i + n_sorting_vars}]"

    uid_map_params = dict()

    # Build source
    src = f"def _f(args, params):\n"
    src += f"    out = np.zeros({len(expressions)})\n"
    src += "\n".join([f"    out[{i}] = {_emit(e, uid2sym, uid_map_params)}" for i, e in enumerate(expressions)]) + "\n"
    src += f"    return out"
    ns: Dict[str, Any] = {"math": math, "np": np}
    exec(src, ns)
    fn = nb.njit(ns["_f"], fastmath=True)

    if add_doc_string:
        fn.__doc__ = "Positional order:\n  " + "\n  ".join(
            f"arg{i} → {v.name} (uid={v.uid}…)" for i, v in enumerate(sorting_vars)
        )
    return fn


# -----------------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------------

__all__ = [
    "Expr", "Const", "Var", "BinOp", "UnOp", "Func", "CmpOp", "Comparison",
    "sin", "cos", "tan", "exp", "log", "sqrt",
    "asin", "acos", "atan", "sinh", "cosh",
    "diff", "eval_uid",
    "find_vars_order",
    "real",
    "imag",
    "conj",
    "abs",
    "angle",
    "stepwise",
    "heaviside"
]
