"""examples.py – Showcase every feature of *symbolic.py*.

Run this file directly with `python examples.py` to see the output of each
feature or open it to copy‑paste snippets into a REPL / notebook.
"""

from __future__ import annotations

import json
import math
import VeraGridEngine.Utils.Symbolic.symbolic as sym

# -----------------------------------------------------------------------------
# 1. Build basic expressions with arithmetic operators
# -----------------------------------------------------------------------------
print("# 1. Arithmetic operators")
x, y = sym.Var("x"), sym.Var("y")
arith_expr = (2 * x + 3) / (y - 4) - x ** 2
print("Expression:", arith_expr)
print("Eval x=5, y=7 →", arith_expr.eval(x=5, y=7))
print()

# -----------------------------------------------------------------------------
# 2. Combine trigonometric and exponential functions
# -----------------------------------------------------------------------------
print("# 2. Trigonometric & exponential")
trig_expr = sym.sin(x) + sym.cos(y) * sym.exp(x / 2)
print("Expression:", trig_expr)
print("Eval x=0.5, y=1.2 →", trig_expr.eval(x=0.5, y=1.2))
print()

# -----------------------------------------------------------------------------
# 3. Differentiation (partial derivatives)
# -----------------------------------------------------------------------------
print("# 3. Differentiation")
complex_expr = sym.sin(x) * sym.exp(y) + x**3

print("f(x,y) =", complex_expr)
print("∂f/∂x  =", complex_expr.diff("x"))
print("∂f/∂y  =", sym.diff(complex_expr, y))
print("Eval ∂f/∂x at (x=1,y=0) →", complex_expr.diff(x).eval(x=1, y=0))
print()

# -----------------------------------------------------------------------------
# 4. Unique identifiers (UUIDv4)
# -----------------------------------------------------------------------------
print("# 4. Unique IDs")
print("x.uid =", x.uid)
print("(Another Var('x')).uid ≠ x.uid →", sym.Var("x").uid)
print()

# -----------------------------------------------------------------------------
# 5. JSON serialisation & deserialisation
# -----------------------------------------------------------------------------
print("# 5. Serialisation round‑trip")
blob = complex_expr.to_json(indent=2)
print("JSON string:")
print(blob)
clone = sym.Expr.from_json(blob)
print("Clone equals original numeric eval (x=0.3,y=0.7) →",
      math.isclose(clone.eval(x=0.3, y=0.7), complex_expr.eval(x=0.3, y=0.7)))
print("UID preserved?", clone.uid == complex_expr.uid)
print()

# -----------------------------------------------------------------------------
# 6. Immutability demonstration of operator maps
# -----------------------------------------------------------------------------
print("# 6. Immutability check (_impl is MappingProxyType)")
try:
    sym.BinOp._impl["+"] = None  # type: ignore[misc]
except TypeError as exc:
    print("Attempt to mutate BinOp._impl →", exc)
print()

# -----------------------------------------------------------------------------
# 7. Error handling examples
# -----------------------------------------------------------------------------
print("# 7. Error handling")
try:
    y.eval()  # no binding supplied
except ValueError as exc:
    print("Missing binding →", exc)

try:
    (sym.Var("z") / sym.Const(0)).eval(z=1)
except ZeroDivisionError as exc:
    print("Division by zero →", exc)

try:
    sym.Func("bogus", sym.Const(0)).eval()
except KeyError as exc:
    print("Unknown function →", exc)
print()

# -----------------------------------------------------------------------------
# 8. Pretty-print of nested expression tree (repr)
# -----------------------------------------------------------------------------
print("# 8. Repr / str form")
print(complex_expr)
print()

print("All feature demonstrations complete!")
