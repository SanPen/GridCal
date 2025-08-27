from __future__ import annotations
import json
import pytest
import math
import numpy as np
from scipy.sparse import csc_matrix
from types import MappingProxyType
from typing import Any, Callable, Dict
import VeraGridEngine.Utils.Symbolic.symbolic as sym

# -----------------------------------------------------------------------------
# Atomic & basic operations
# -----------------------------------------------------------------------------

def test_const_eval():
    assert sym.Const(42).eval() == 42


def test_var_eval():
    x = sym.Var("x")
    assert x.eval(x=3.14) == 3.14
    with pytest.raises(ValueError):
        x.eval()  # missing binding


def test_binary_arithmetic():
    x, y = sym.Var("x1"), sym.Var("y")
    expr = 2 * x + y / 4 - 1
    result = expr.eval(x1=8, y=20)  # 2*8 + 20/4 - 1 = 16 + 5 - 1 = 20
    assert result == 20


def test_unary_neg_pow():
    x = sym.Var("x")
    expr = -(x ** 2)
    assert expr.eval(x=3) == -9

# -----------------------------------------------------------------------------
# Functional expressions (sin, cos, tan, exp)
# -----------------------------------------------------------------------------

def test_trig_and_exp():
    x = sym.Var("x")
    expr = sym.sin(x) + sym.exp(2 * x)
    val = expr.eval(x=0)
    assert math.isclose(val, 1.0)  # sin(0)=0, exp(0)=1

# -----------------------------------------------------------------------------
# UID behaviour
# -----------------------------------------------------------------------------

def test_uid_uniqueness():
    a, b = sym.Var("x"), sym.Var("x")
    assert a.uid != b.uid
    expr = a + b
    assert len({a.uid, b.uid, expr.uid}) == 3  # all distinct

# -----------------------------------------------------------------------------
# JSON round‑trip
# -----------------------------------------------------------------------------

def test_serialisation_roundtrip():
    x, y = sym.Var("x"), sym.Var("y")
    expr = sym.sin(x) * (y + 3)

    blob = expr.to_json()
    clone = sym.Expr.from_json(blob)

    assert expr.eval(x=0.5, y=2) == clone.eval(x=0.5, y=2)
    # ensure UIDs are preserved
    assert expr.uid == json.loads(blob)["uid"]

# -----------------------------------------------------------------------------
# Immutability guarantees
# -----------------------------------------------------------------------------

def test_impl_mappingproxy():
    with pytest.raises(TypeError):
        sym.BinOp._impl["+"] = None  # mappingproxy is read‑only
    with pytest.raises(TypeError):
        sym.Func._impl["sin"] = None

# -----------------------------------------------------------------------------
# String representations (non‑critical, but nice to see)
# -----------------------------------------------------------------------------

def test_str_roundtrip():
    x = sym.Var("x")
    expr = (2 * x) / 5 - sym.cos(x)
    s = str(expr)
    # rudimentary checks — parentheses and operator symbols appear
    assert "(" in s and ")" in s and "/" in s and "cos" in s

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _numdiff(f: Callable[[float], float], x: float, h: float = 1e-6) -> float:
    """Central finite‑difference derivative."""
    return (f(x + h) - f(x - h)) / (2 * h)

# -----------------------------------------------------------------------------
# 1. Constant & variable evaluation
# -----------------------------------------------------------------------------

def test_constant_and_variable_eval():
    c = sym.Const(7)
    assert c.eval() == 7

    x = sym.Var("x")
    assert x.eval(x=3.14) == 3.14
    with pytest.raises(ValueError):
        x.eval()  # missing binding

# -----------------------------------------------------------------------------
# 2. UID‑based evaluation for duplicate names
# -----------------------------------------------------------------------------

def test_eval_uid_duplicate_names():
    x1, x2 = sym.Var("x"), sym.Var("x")
    expr = x1 + 2 * x2
    # name‑based → same value for both
    assert expr.eval(x=2) == 6
    # uid‑based → independent values
    vals = {x1.uid: 2, x2.uid: 5}
    assert sym.eval_uid(expr, vals) == 12

# -----------------------------------------------------------------------------
# 3. Elementary functions – value & derivative
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sym_func, math_func, point",
    [
        (sym.sin, math.sin, 0.3),
        (sym.cos, math.cos, 0.3),
        (sym.tan, math.tan, 0.3),
        (sym.exp, math.exp, 0.3),
        (sym.log, math.log, 1.3),
        (sym.sqrt, math.sqrt, 1.3),
        (sym.asin, math.asin, 0.3),
        (sym.acos, math.acos, 0.3),
        (sym.atan, math.atan, 0.3),
        (sym.sinh, math.sinh, 0.3),
        (sym.cosh, math.cosh, 0.3),
    ],
)
def test_elementary_functions(sym_func, math_func, point):
    x = sym.Var("x")
    expr = sym_func(x)
    # value
    assert math.isclose(expr.eval(x=point), math_func(point), rel_tol=1e-9)
    # derivative (numeric check)
    d_expr = expr.diff(x).simplify()
    numeric = _numdiff(math_func, point)
    assert math.isclose(d_expr.eval(x=point), numeric, rel_tol=1e-5)

# -----------------------------------------------------------------------------
# 4. General power rule (u(x) ** v(x))
# -----------------------------------------------------------------------------

def test_general_power_rule():
    x = sym.Var("x")
    expr = x ** x
    d = expr.diff(x).simplify()           # x**x * (log(x) + 1)
    expected = lambda t: t ** t * (math.log(t) + 1)  # noqa: E731
    assert math.isclose(d.eval(x=2.0), expected(2.0), rel_tol=1e-9)

# -----------------------------------------------------------------------------
# 5. Higher‑order derivatives & simplification
# -----------------------------------------------------------------------------

def test_higher_order_derivatives():
    x = sym.Var("x")
    expr = x ** 3
    second = sym.diff(expr, x, 2).simplify()
    third  = sym.diff(expr, x, 3).simplify()
    # Numeric checks
    assert second.eval(x=4) == 6 * 4
    assert isinstance(third, sym.Const) and third.value == 6

# -----------------------------------------------------------------------------
# 6. Simplification rules
# -----------------------------------------------------------------------------

def test_simplification_identities():
    x = sym.Var("x")
    assert ((x + sym.Const(0)).simplify()).__str__() == "x"
    assert ((sym.Const(0) * x).simplify()).eval(x=99) == 0
    assert ((x ** sym.Const(0)).simplify()).eval(x=5) == 1

# -----------------------------------------------------------------------------
# 7. Substitution mechanics
# -----------------------------------------------------------------------------

def test_substitution():
    x, y = sym.Var("x"), sym.Var("y")
    expr = x ** 2 + y
    replaced = expr.subs({x: y + 1})
    assert replaced.eval(y=3) == (3 + 1) ** 2 + 3  # 16 + 3 = 19

# -----------------------------------------------------------------------------
# 8. JSON round‑trip with UID preservation
# -----------------------------------------------------------------------------

def test_json_roundtrip_uid():
    x = sym.Var("x")
    expr = sym.sin(x) + sym.sqrt(x)
    clone = sym.Expr.from_json(expr.to_json())
    assert expr.uid == clone.uid
    assert expr.eval(x=0.9) == clone.eval(x=0.9)

# -----------------------------------------------------------------------------
# 9. Immutability checks
# -----------------------------------------------------------------------------

def test_mappingproxy_immutable():
    assert isinstance(sym.BinOp._impl, MappingProxyType)
    with pytest.raises(TypeError):
        sym.BinOp._impl["+"] = None  # type: ignore[misc]


def test_frozen_dataclass_immutable():
    c = sym.Const(1)
    with pytest.raises(AttributeError):
        c.value = 2  # type: ignore[attr-defined]

