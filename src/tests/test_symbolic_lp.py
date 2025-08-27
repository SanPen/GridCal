# test_lp_model.py
# ==============================================================
#  Straight-forward pytest checks for lp_model.py
#  (no parametrize, each test stands alone)
# ==============================================================

import math
from pathlib import Path
import pytest

from VeraGridEngine.Utils.Symbolic.lp_model import LPModel, LinExpr
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, sin

TOL = 1e-8


# ──────────────────────────────────────────────────────────────
#  Section 1: LinExpr construction & arithmetic
# ──────────────────────────────────────────────────────────────
def test_linexpr_constant():
    lex = LinExpr.from_expr(Const(7))
    assert lex.coeffs == {}
    assert lex.constant == 7.0


def test_linexpr_single_variable():
    x = Var("x")
    lex = LinExpr.from_expr(x)
    assert math.isclose(lex.coeffs[x], 1.0, rel_tol=0, abs_tol=TOL)
    assert lex.constant == 0.0


def test_linexpr_scalar_multiplication():
    x = Var("x")
    lex = LinExpr.from_expr(3 * x)
    assert math.isclose(lex.coeffs[x], 3.0, abs_tol=TOL)


def test_linexpr_addition_and_constant():
    x = Var("x")
    lex = LinExpr.from_expr(2 * x + 5)
    assert math.isclose(lex.coeffs[x], 2.0, abs_tol=TOL)
    assert math.isclose(lex.constant, 5.0, abs_tol=TOL)


def test_linexpr_subtraction():
    x, y = Var("x"), Var("y")
    lex = LinExpr.from_expr(3 * x - 4 * y + 8)
    assert math.isclose(lex.coeffs[x], 3.0, abs_tol=TOL)
    assert math.isclose(lex.coeffs[y], -4.0, abs_tol=TOL)
    assert math.isclose(lex.constant, 8.0, abs_tol=TOL)


def test_linexpr_add_method():
    x, y = Var("x"), Var("y")
    a = LinExpr.from_expr(2 * x + 1)
    b = LinExpr.from_expr(3 * y - 4)
    c = a + b
    assert math.isclose(c.coeffs[x], 2.0, abs_tol=TOL)
    assert math.isclose(c.coeffs[y], 3.0, abs_tol=TOL)
    assert math.isclose(c.constant, -3.0, abs_tol=TOL)


def test_linexpr_sub_method():
    x, y = Var("x"), Var("y")
    a = LinExpr.from_expr(5 * x + 2)
    b = LinExpr.from_expr(2 * y + 7)
    c = a - b
    assert math.isclose(c.coeffs[x], 5.0, abs_tol=TOL)
    assert math.isclose(c.coeffs[y], -2.0, abs_tol=TOL)
    assert math.isclose(c.constant, -5.0, abs_tol=TOL)


def test_linexpr_non_affine_raises():
    x, y = Var("x"), Var("y")
    with pytest.raises(ValueError):
        LinExpr.from_expr(x * y + 1)


# ──────────────────────────────────────────────────────────────
#  Section 2: Constraint senses & validation
# ──────────────────────────────────────────────────────────────
def test_constraint_valid_senses():
    m = LPModel()
    x = m.add_var("x")
    # all three senses should be accepted
    a = x == 0
    m += x <= 1
    m += x >= -1
    m += x == 0
    # model still has three constraints
    assert len(m._constraints) == 3


# ──────────────────────────────────────────────────────────────
#  Section 3: Solver – continuous diet LP
# ──────────────────────────────────────────────────────────────
@pytest.mark.skip(reason="Not ready yet")
def test_diet_lp_optimal():
    m = LPModel()
    bread = m.add_var("bread")
    milk = m.add_var("milk")
    m.minimise(0.5 * bread + 0.7 * milk)
    m += 4 * bread + 8 * milk <= 500
    m += 1 * bread + 6 * milk >= 30
    res = m.solve()
    assert res.status.lower().startswith("optimal")
    # optimal: all milk, 6.25 L
    assert math.isclose(res.primal[bread], 0.0, abs_tol=1e-3)
    assert math.isclose(res.primal[milk], 6.25, abs_tol=1e-2)


# ──────────────────────────────────────────────────────────────
#  Section 4: Solver – binary knapsack
# ──────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Not ready yet")
def test_knapsack_mip_optimal():
    m = LPModel()
    choose = {
        "guitar": m.add_var("guitar", integer=True, low=0, up=1),
        "laptop": m.add_var("laptop", integer=True, low=0, up=1),
        "iphone": m.add_var("iphone", integer=True, low=0, up=1),
    }
    value = 30 * choose["guitar"] + 20 * choose["laptop"] + 15 * choose["iphone"]
    weight = 6 * choose["guitar"] + 3 * choose["laptop"] + 1 * choose["iphone"]
    m.maximise(value)
    m += weight <= 7
    res = m.solve()
    assert res.status.lower().startswith("optimal")
    # laptop + iphone chosen
    assert res.primal[choose["guitar"]] < 0.5
    assert res.primal[choose["laptop"]] > 0.5
    assert res.primal[choose["iphone"]] > 0.5
    assert math.isclose(res.objective, 35.0, abs_tol=TOL)


# ──────────────────────────────────────────────────────────────
#  Section 5: Warm-start handling
# ──────────────────────────────────────────────────────────────
def test_warm_start():
    m = LPModel()
    x = m.add_var("x", start=10.0)
    m.minimise(x)
    m += x >= 2
    res = m.solve()
    assert math.isclose(res.primal[x], 2.0, abs_tol=TOL)


# ──────────────────────────────────────────────────────────────
#  Section 6: Non-affine objective rejected
# ──────────────────────────────────────────────────────────────
def test_non_affine_objective_rejected():
    m = LPModel()
    x = m.add_var("x")
    with pytest.raises(ValueError):
        m.minimise(sin(x))


# ──────────────────────────────────────────────────────────────
#  Section 7: write() creates a non-empty file
# ──────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Not ready yet")
def test_write_model_to_disk(tmp_path: Path):
    m = LPModel()
    x = m.add_var("x")
    m.minimise(x)
    m += x >= 1
    out_file = tmp_path / "model.lp"
    m.write(str(out_file))
    assert out_file.exists() and out_file.stat().st_size > 0
