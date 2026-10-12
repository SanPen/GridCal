from __future__ import annotations
import ast
import copy
import json
import pytest
import math
import numpy as np
from typing import Any, Callable, Dict
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian
from VeraGridEngine.Utils.Symbolic.jit_compiler import SubexpressionAnalyzer
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    DynamicModelContract,
    RmsPhysicalMeasurementPoint,
    RmsPhysicalMeterKind,
    RmsTerminalPowerContribution,
    RmsTerminalSide,
    collect_rms_physical_measurement_points,
)
from VeraGridEngine.Utils.Symbolic.symbolic_io import (
    duplicate_block,
    duplicate_block_across_factories,
    duplicate_block_vars_uid,
    expr_to_dict,
    parse_expr,
    BlockSaver,
    BlockParser,
)
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagram
from VeraGridEngine.Devices.Dynamic.var_factory import Connection, VarFactory
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Utils.procedural_logic import AnalogFlipFlopLogic, ProceduralLogicCodec, aflipflop

# -----------------------------------------------------------------------------
# Atomic & basic operations
# -----------------------------------------------------------------------------

def test_const_eval() -> None:
    assert sym.Const(42).eval() == 42


def test_var_eval() -> None:
    x = sym.Var("x")
    assert x.eval(x=3.14) == 3.14
    with pytest.raises(ValueError):
        x.eval()  # missing binding


def test_binary_arithmetic() -> None:
    x, y = sym.Var("x1"), sym.Var("y")
    expr = 2 * x + y / 4 - 1
    result = expr.eval(x1=8, y=20)  # 2*8 + 20/4 - 1 = 16 + 5 - 1 = 20
    assert result == 20


def test_safe_divide_uses_explicit_zero_denominator_value() -> None:
    """Verify the explicit denominator fallback and reject a zero fallback.

    :return: None.
    """
    numerator: sym.Var = sym.Var("numerator")
    denominator: sym.Var = sym.Var("denominator")
    expression: sym.Expr = sym.safe_divide(
        numerator=numerator,
        denominator=denominator,
        zero_denominator_value=sym.Const(0.25),
    )

    assert expression.eval(numerator=12.0, denominator=3.0) == 4.0
    assert expression.eval(numerator=12.0, denominator=0.0) == 48.0
    with pytest.raises(ValueError, match="must be non-zero"):
        sym.safe_divide(
            numerator=numerator,
            denominator=denominator,
            zero_denominator_value=sym.Const(0.0),
        )


def test_safe_divide_derivative_matches_generated_expression() -> None:
    """Verify safe division has consistent symbolic and generated derivatives.

    :return: None.
    """
    numerator: sym.Var = sym.Var("numerator")
    denominator: sym.Var = sym.Var("denominator")
    expression: sym.Expr = sym.safe_divide(
        numerator=numerator,
        denominator=denominator,
        zero_denominator_value=sym.Const(0.25),
    )
    numerator_derivative: sym.Expr = expression.diff(numerator)
    compiler_names: Dict[int, str] = {
        numerator.uid: "numerator",
        denominator.uid: "denominator",
    }
    generated_expression: str = sym.expression2numba(
        expr=expression,
        compiler_names_dict=compiler_names,
    )

    assert numerator_derivative.eval(numerator=12.0, denominator=3.0) == 1.0 / 3.0
    assert numerator_derivative.eval(numerator=12.0, denominator=0.0) == 4.0
    parsed_expression: ast.Expression = ast.parse(generated_expression, mode="eval")
    assert isinstance(parsed_expression.body, ast.BinOp)
    assert generated_expression == (
        "numerator / ((_heaviside(denominator) + _heaviside(-denominator)) * denominator + "
        "(1.0 - (_heaviside(denominator) + _heaviside(-denominator))) * 0.25)"
    )
    assert expression.eval(numerator=12.0, denominator=3.0) == 4.0
    assert expression.eval(numerator=12.0, denominator=0.0) == 48.0


def test_sqrt_derivative_uses_finite_zero_boundary_slope() -> None:
    """Keep square-root Jacobians finite at a limited zero boundary.

    :return: None.
    """
    argument: sym.Var = sym.Var("argument")
    derivative: sym.Expr = sym.sqrt(argument).diff(argument)
    compiler_names: Dict[int, str] = {argument.uid: "argument"}
    generated_derivative: str = sym.expression2numba(
        expr=derivative,
        compiler_names_dict=compiler_names,
    )

    assert derivative.eval(argument=0.0) == 0.0
    assert derivative.eval(argument=4.0) == pytest.approx(0.25)
    parsed_derivative: ast.Expression = ast.parse(generated_derivative, mode="eval")
    assert isinstance(parsed_derivative.body, ast.BinOp)
    assert generated_derivative == (
        "1 / ((_heaviside(2 * np.sqrt(argument)) + _heaviside(-(2 * np.sqrt(argument)))) * "
        "(2 * np.sqrt(argument)) + (1.0 - (_heaviside(2 * np.sqrt(argument)) + "
        "_heaviside(-(2 * np.sqrt(argument)))))) * _heaviside(argument)"
    )


def test_unary_neg_pow() -> None:
    x = sym.Var("x")
    expr = -(x ** 2)
    assert expr.eval(x=3) == -9

# -----------------------------------------------------------------------------
# Functional expressions (sin, cos, tan, exp)
# -----------------------------------------------------------------------------

def test_trig_and_exp() -> None:
    x = sym.Var("x")
    expr = sym.sin(x) + sym.exp(2 * x)
    val = expr.eval(x=0)
    assert math.isclose(val, 1.0)  # sin(0)=0, exp(0)=1

# -----------------------------------------------------------------------------
# UID behaviour
# -----------------------------------------------------------------------------

def test_uid_uniqueness() -> None:
    a, b = sym.Var("x"), sym.Var("x")
    assert a.uid != b.uid
    expr = a + b
    assert len({a.uid, b.uid, expr.uid}) == 3  # all distinct


def test_subexpression_analyzer_distinguishes_duplicate_names_by_uid() -> None:
    a = sym.Var("x")
    b = sym.Var("x")
    analyzer = SubexpressionAnalyzer()

    assert analyzer.hash_expr(a + sym.Const(1.0)) != analyzer.hash_expr(b + sym.Const(1.0))

# -----------------------------------------------------------------------------
# JSON round‑trip
# -----------------------------------------------------------------------------

def test_serialisation_roundtrip() -> None:
    x, y = sym.Var("x"), sym.Var("y")
    expr = sym.sin(x) * (y + 3)

    blob = expr.to_json()
    clone = sym.Expr.from_json(blob)

    assert expr.eval(x=0.5, y=2) == clone.eval(x=0.5, y=2)
    # ensure UIDs are preserved
    assert expr.uid == json.loads(blob)["uid"]


def test_symbolic_io_func2_roundtrip() -> None:
    x: sym.Var = sym.Var("x")
    y: sym.Var = sym.Var("y")
    expr: sym.Expr = sym.atan2(x + sym.Const(1.0), y * sym.Const(2.0))
    const_dict: Dict[int, sym.Const] = dict()
    var_dict: Dict[int, sym.Var] = {x.uid: x, y.uid: y}
    diff_var_dict: Dict[int, sym.Var] = dict()

    payload: Dict[str, object] = expr_to_dict(expr=expr,
                                              const_dict=const_dict,
                                              var_dict=var_dict,
                                              diff_var_dict=diff_var_dict)
    restored: sym.Expr = parse_expr(data=payload,
                                    const_dict=const_dict,
                                    var_dict=var_dict,
                                    diff_var_dict=diff_var_dict)
    payload_roundtrip: Dict[str, object] = expr_to_dict(expr=restored,
                                                        const_dict=const_dict,
                                                        var_dict=var_dict,
                                                        diff_var_dict=diff_var_dict)

    assert isinstance(restored, sym.Func2)
    assert restored.name == "atan2"
    assert payload_roundtrip == payload
    assert math.isclose(restored.eval(x=1.5, y=0.25), expr.eval(x=1.5, y=0.25), rel_tol=1.0e-12)

# -----------------------------------------------------------------------------
# Immutability guarantees
# -----------------------------------------------------------------------------

# def test_func2_impl_mappingproxy():
#     with pytest.raises(TypeError):
#         sym.Func2._impl["atan2"] = None


# -----------------------------------------------------------------------------
# String representations (non‑critical, but nice to see)
# -----------------------------------------------------------------------------

def test_str_roundtrip() -> None:
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

def test_constant_and_variable_eval() -> None:
    c = sym.Const(7)
    assert c.eval() == 7

    x = sym.Var("x")
    assert x.eval(x=3.14) == 3.14
    with pytest.raises(ValueError):
        x.eval()  # missing binding

# -----------------------------------------------------------------------------
# 2. UID‑based evaluation for duplicate names
# -----------------------------------------------------------------------------

def test_eval_uid_duplicate_names() -> None:
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
def test_elementary_functions(sym_func: Callable[[sym.Expr], sym.Expr],
                              math_func: Callable[[float], float],
                              point: float) -> None:
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

# def test_general_power_rule():
#     x = sym.Var("x")
#     expr = x ** x
#     d = expr.diff(x).simplify()           # x**x * (log(x) + 1)
#     expected = lambda t: t ** t * (math.log(t) + 1)  # noqa: E731
#     assert math.isclose(d.eval(x=2.0), expected(2.0), rel_tol=1e-9)

# -----------------------------------------------------------------------------
# 5. Higher‑order derivatives & simplification
# -----------------------------------------------------------------------------

def test_higher_order_derivatives() -> None:
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

def test_simplification_identities() -> None:
    x = sym.Var("x")
    assert ((x + sym.Const(0)).simplify()).__str__() == "x"
    assert ((sym.Const(0) * x).simplify()).eval(x=99) == 0
    assert ((x ** sym.Const(0)).simplify()).eval(x=5) == 1

# -----------------------------------------------------------------------------
# 7. Substitution mechanics
# -----------------------------------------------------------------------------

def test_substitution() -> None:
    x, y = sym.Var("x"), sym.Var("y")
    expr = x ** 2 + y
    replaced = expr.subs({x: y + 1})
    assert replaced.eval(y=3) == (3 + 1) ** 2 + 3  # 16 + 3 = 19

# -----------------------------------------------------------------------------
# 8. JSON round‑trip with UID preservation
# -----------------------------------------------------------------------------

def test_json_roundtrip_uid() -> None:
    x = sym.Var("x")
    expr = sym.sin(x) + sym.sqrt(x)
    clone = sym.Expr.from_json(expr.to_json())
    assert expr.uid == clone.uid
    assert expr.eval(x=0.9) == clone.eval(x=0.9)


def test_symbolic_jacobian_nonlinear_5x5() -> None:
    # -----------------------------
    # Variables
    # --------sym.---------------------
    x0 = sym.Var("x0")
    x1 = sym.Var("x1")
    x2 = sym.Var("x2")
    x3 = sym.Var("x3")
    x4 = sym.Var("x4")

    variables = [x0, x1, x2, x3, x4]

    # -----------------------------
    # Functions
    # -----------------------------
    f1 = x0 ** 2 + sym.sin(x1) + x2 * x3
    f2 = x1 ** 2 + sym.cos(x2) + x3 * x4
    f3 = x0 * x4 + x1 * x2
    f4 = sym.sin(x0) + x2 ** 2 + x3
    f5 = x0 * x1 + x4 ** 2

    eqs = [f1, f2, f3, f4, f5]

    # -----------------------------
    # Dictionaries for compilation
    # -----------------------------
    compiler_names_dict: Dict[int, str] = {}
    alias_names_dict: Dict[int, str] = {}

    VARS_NAME = "x"

    for i, v in enumerate(variables):
        compiler_names_dict[v.uid] = f"{VARS_NAME}[{i}]"
        alias_names_dict[v.uid] = f"{VARS_NAME}_{i}"

    # -----------------------------
    # Symbolic Jacobian
    # -----------------------------
    jac = SymbolicJacobian(
        eqs=eqs,
        variables=variables,
        compiler_names_dict=compiler_names_dict,
        alias_names_dict=alias_names_dict,
        VARS_NAME="x",
        DIFF_NAME="dx",
        EVENT_PARAMS_NAME="vp",
        PARAMS_NAME="cp",
        use_jit=False,
        batch_size=10,
        n_jobs=1
    )

    # -----------------------------
    # Evaluation point
    # -----------------------------
    xval = np.array([1.0, 2.0, 0.5, -1.0, 0.8])
    dx = np.zeros_like(xval)
    vp = np.zeros(0)
    cp = np.zeros(0)

    J_compiled = jac(xval, dx, vp, cp, h=1e-8).toarray()

    # -----------------------------
    # Numeric calculation
    # -----------------------------
    J_expected = np.array([
        [2 * xval[0], np.cos(xval[1]), xval[3], xval[2], 0.0],
        [0.0, 2 * xval[1], -np.sin(xval[2]), xval[4], xval[3]],
        [xval[4], xval[2], xval[1], 0.0, xval[0]],
        [np.cos(xval[0]), 0.0, 2 * xval[2], 1.0, 0.0],
        [xval[1], xval[0], 0.0, 0.0, 2 * xval[4]]
    ])

    print("J_compiled:\n", J_compiled)
    print("J_expected:\n", J_expected)

    assert np.allclose(J_compiled, J_expected, atol=1e-8)


def test_diff_var_deepcopy_does_not_mutate_original_links() -> None:
    """
    Check that copying a differential variable never rewires the source chain.

    :return: Nothing.
    """
    vf: VarFactory = VarFactory()
    x: sym.Var = vf.add_var(
        name="x",
        reference=VarPowerFlowReferenceType.Vm,
        network_conn=True,
        shared_reference="shared-x",
    )
    dx: sym.Var = vf.add_diff_var("dx", base_var=x)

    copied_dx: sym.Var = copy.deepcopy(dx)

    assert x.diff_var is dx
    assert dx.base_var is x
    assert copied_dx is not dx
    assert copied_dx.uid == dx.uid
    assert copied_dx.base_var is not x
    assert copied_dx.base_var.uid == x.uid
    assert copied_dx.base_var.diff_var is copied_dx


def test_var_factory_deepcopy_keeps_copied_diff_links_internal() -> None:
    """
    Check that copied factories contain derivative links only to copied variables.

    :return: Nothing.
    """
    vf: VarFactory = VarFactory()
    x: sym.Var = vf.add_var(
        "x",
        reference=VarPowerFlowReferenceType.Vm,
        network_conn=True,
        shared_reference="shared-x",
    )
    dx: sym.Var = vf.add_diff_var("dx", base_var=x)

    copied_vf: VarFactory = copy.deepcopy(vf)
    copied_x_or_none: sym.Var | None = copied_vf.get_var(x.non_mutable_uid)
    assert copied_x_or_none is not None
    copied_x: sym.Var = copied_x_or_none
    copied_dx: sym.Var = copied_vf.get_diff_var(dx.non_mutable_uid)

    assert x.diff_var is dx
    assert dx.base_var is x
    assert copied_x is not x
    assert copied_dx is not dx
    assert copied_x.diff_var is copied_dx
    assert copied_dx.base_var is copied_x


def test_block_deepcopy_reuses_copied_vars_inside_equations() -> None:
    """
    Check that copied blocks reuse the same cloned variables in lists and equations.

    :return: Nothing.
    """
    vf: VarFactory = VarFactory()
    x: sym.Var = vf.add_var("x")
    dx: sym.Var = vf.add_diff_var("dx", base_var=x)
    p: sym.Var = vf.add_var("p")
    c: sym.Const = vf.add_const(3.0, name="p_value")
    block: Block = Block(
        state_vars=[x],
        diff_vars=[dx],
        state_eqs=[dx + x],
        init_eqs={x: x + sym.Const(1.0)},
        diff_init_eqs={dx: dx + sym.Const(2.0)},
        parameters={p: c},
    )

    copied: Block = copy.deepcopy(block)
    copied_x: sym.Var = copied.state_vars[0]
    copied_dx: sym.Var = copied.diff_vars[0]

    assert x.diff_var is dx
    assert dx.base_var is x
    assert copied_x is not x
    assert copied_dx is not dx
    assert copied_x.diff_var is copied_dx
    assert copied_dx.base_var is copied_x
    assert copied.state_eqs[0].left is copied_dx
    assert copied.state_eqs[0].right is copied_x

    copied_const: sym.Const = next(iter(copied.parameters.values()))
    copied_const.value = 9.0
    assert c.value == 3.0


def test_block_deepcopy_preserves_editor_structure_metadata() -> None:
    """Keep editor structure metadata available on an isolated block copy.

    The dynamic editor commits a deep working copy back into the owned block.
    Losing either field during that boundary makes a valid editor model
    impossible to apply or changes whether its internal structure is exposed.

    :return: None.
    """
    source_block: Block = Block(is_decomposable=False)
    source_block.tpe_uid = 73

    copied_block: Block = copy.deepcopy(source_block)

    assert copied_block.is_decomposable is False
    assert copied_block.tpe_uid == 73


def test_duplicate_block_vars_uid_creates_isolated_factory_graph() -> None:
    """Verify editor cloning preserves identities without sharing symbolic state.

    :return: None.
    """
    source_vf: VarFactory = VarFactory()
    source_var: sym.Var = source_vf.add_var(name="source")
    target_var: sym.Var = source_vf.add_var(name="target", shared_reference="shared_signal")
    parameter_var: sym.Var = source_vf.add_var(name="gain")
    parameter_const: sym.Const = source_vf.add_const(value=2.0, name="gain_value")
    source_vf.add_connection(var_to_subs=target_var, incoming_var=source_var)
    owner: object = object()
    source_vf.register_var(dev=owner, var=target_var)
    source_block: Block = Block(
        algebraic_vars=list((source_var, target_var)),
        algebraic_eqs=list((source_var, target_var)),
        parameters=dict(((parameter_var, parameter_const),)),
        in_vars=list((target_var,)),
        out_vars=list((source_var,)),
        name="source_block",
    )
    target_vf: VarFactory = VarFactory()

    duplicated_block: Block = duplicate_block_vars_uid(
        block=source_block,
        source_var_factory=source_vf,
        target_var_factory=target_vf,
    )
    duplicated_source: sym.Var = duplicated_block.out_vars[0]
    duplicated_target: sym.Var = duplicated_block.in_vars[0]

    assert duplicated_block is not source_block
    assert duplicated_block.uid == source_block.uid
    assert duplicated_source is not source_var
    assert duplicated_target is not target_var
    assert duplicated_source.uid == source_var.uid
    assert duplicated_source.non_mutable_uid == source_var.non_mutable_uid
    assert duplicated_target.uid == target_var.uid
    assert duplicated_target.non_mutable_uid == target_var.non_mutable_uid
    assert duplicated_block.algebraic_eqs[0] is duplicated_source
    assert duplicated_block.algebraic_eqs[1] is duplicated_target
    duplicated_parameter_var: sym.Var = next(iter(duplicated_block.parameters.keys()))
    duplicated_parameter_const: sym.Const = duplicated_block.parameters[duplicated_parameter_var]
    assert duplicated_parameter_var.uid == parameter_var.uid
    assert duplicated_parameter_const.uid == parameter_const.uid
    assert duplicated_parameter_const is not parameter_const
    assert target_vf.get_var(duplicated_source.non_mutable_uid) is duplicated_source
    assert target_vf.get_var(duplicated_target.non_mutable_uid) is duplicated_target
    assert target_vf.get_connections_dict() is not source_vf.get_connections_dict()
    assert len(target_vf.get_connections_dict()[duplicated_source.non_mutable_uid]) == 1

    target_vf.remove_connection(
        var_to_disconnect=duplicated_target,
        outgoing_var=duplicated_source,
    )

    assert duplicated_source.non_mutable_uid not in target_vf.get_connections_dict()
    assert source_var.non_mutable_uid in source_vf.get_connections_dict()

    source_vf.merge_editor_var_factory(working_var_factory=target_vf)

    assert source_vf.get_var(duplicated_source.non_mutable_uid) is duplicated_source
    assert source_vf.get_var(duplicated_target.non_mutable_uid) is duplicated_target
    assert source_vf.get_const(parameter_const.uid) is duplicated_parameter_const
    assert source_vf.vars_info[owner][0] is duplicated_target
    assert duplicated_target.shared_ref is source_vf.get_references_dict()["shared_signal"]
    assert duplicated_source.non_mutable_uid not in source_vf.get_connections_dict()


def test_duplicate_block_across_factories_copies_only_internal_graph() -> None:
    """Clone internal aliases without sharing source variables or references.

    :return: None.
    """
    source_vf: VarFactory = VarFactory()
    source_var: sym.Var = source_vf.add_var(name="source")
    target_var: sym.Var = source_vf.add_var(
        name="target",
        shared_reference="shared_signal",
    )
    external_var: sym.Var = source_vf.add_var(name="external")
    source_vf.add_connection(
        var_to_subs=target_var,
        incoming_var=source_var,
    )
    source_vf.add_connection(
        var_to_subs=external_var,
        incoming_var=source_var,
    )
    source_block: Block = Block(
        algebraic_vars=list((source_var, target_var)),
        in_vars=list((target_var,)),
        out_vars=list((source_var,)),
    )
    target_vf: VarFactory = VarFactory()

    duplicated_block: Block = duplicate_block_across_factories(
        block=source_block,
        source_var_factory=source_vf,
        target_var_factory=target_vf,
    )
    duplicated_source: sym.Var = duplicated_block.out_vars[0]
    duplicated_target: sym.Var = duplicated_block.in_vars[0]
    duplicated_connections: list[Connection] = target_vf.get_connections_dict()[
        duplicated_source.non_mutable_uid
    ]

    assert duplicated_source is not source_var
    assert duplicated_target is not target_var
    assert duplicated_source.non_mutable_uid != source_var.non_mutable_uid
    assert duplicated_target.non_mutable_uid != target_var.non_mutable_uid
    assert duplicated_target.uid == duplicated_source.uid
    assert duplicated_target.name == duplicated_source.name
    assert target_var.shared_ref is not None
    assert duplicated_target.shared_ref is not None
    assert duplicated_target.shared_ref is not target_var.shared_ref
    assert duplicated_target.shared_ref is target_vf.get_references_dict()["shared_signal"]
    assert duplicated_target.shared_ref.uid == target_var.shared_ref.uid
    assert len(duplicated_connections) == 1
    assert duplicated_connections[0].non_mutable_uid == duplicated_target.non_mutable_uid
    assert external_var.non_mutable_uid not in target_vf.get_vars_dict()
    assert len(source_vf.get_connections_dict()[source_var.non_mutable_uid]) == 2


def test_duplicate_block_preserves_parent_child_variable_links_with_new_uids() -> None:
    """
    Check that block duplication keeps parent and child references coherent.

    :return: Nothing.
    """
    x: sym.Var = sym.Var("x")
    dx: sym.Var = sym.Var("dx", base_var=x)
    parent_signal: sym.Var = sym.Var("parent_signal")
    guard: sym.Var = sym.Var("guard")
    child: Block = Block(
        state_vars=[x],
        diff_vars=[dx],
        algebraic_vars=[guard],
        state_eqs=[dx + x],
        algebraic_eqs=[x - parent_signal],
        inequalities=[x < parent_signal],
        boolean_guards={guard: x > parent_signal},
    )
    child.dynamic_model_contract.dgs_elmsym_speed_var_uid = x.uid
    child.dynamic_model_contract.dgs_explicit_initialization_uids = set((x.uid,))
    parent: Block = Block(
        children=[child],
        algebraic_vars=[parent_signal],
        in_vars=[x],
        out_vars=[dx],
    )

    target_vf: VarFactory = VarFactory()
    copied: Block = duplicate_block(parent, target_vf)
    copied_child: Block = copied.children[0]
    copied_x: sym.Var = copied_child.state_vars[0]
    copied_dx: sym.Var = copied_child.diff_vars[0]
    copied_parent_signal: sym.Var = copied.algebraic_vars[0]
    copied_guard: sym.Var = copied_child.algebraic_vars[0]
    copied_inequality: sym.Expr | sym.Comparison = copied_child.inequalities[0]
    copied_guard_condition: sym.Expr | sym.Comparison = copied_child.boolean_guards[
        copied_guard
    ]

    assert copied.in_vars[0] is copied_x
    assert copied.out_vars[0] is copied_dx
    assert copied_x.uid != x.uid
    assert copied_dx.uid != dx.uid
    assert copied_x.diff_var is copied_dx
    assert copied_dx.base_var is copied_x
    assert copied_child.state_eqs[0].left is copied_dx
    assert copied_child.state_eqs[0].right is copied_x
    assert copied_child.algebraic_eqs[0].left is copied_x
    assert copied_child.algebraic_eqs[0].right is copied_parent_signal
    assert isinstance(copied_inequality, sym.Comparison)
    assert copied_inequality.lhs is copied_x
    assert copied_inequality.rhs is copied_parent_signal
    assert isinstance(copied_guard_condition, sym.Comparison)
    assert copied_guard_condition.lhs is copied_x
    assert copied_guard_condition.rhs is copied_parent_signal
    assert copied_child.dynamic_model_contract.dgs_elmsym_speed_var_uid == copied_x.uid
    assert copied_child.dynamic_model_contract.dgs_explicit_initialization_uids == set((copied_x.uid,))
    assert target_vf.get_var(copied_x.non_mutable_uid) is copied_x
    assert target_vf.get_diff_var(copied_dx.non_mutable_uid) is copied_dx

    parent.dynamic_model_contract.dgs_elmsym_speed_var_uid = -1
    with pytest.raises(KeyError, match="UID '-1' is not reachable"):
        duplicate_block(parent, VarFactory())
    parent.dynamic_model_contract.dgs_elmsym_speed_var_uid = None
    child.dynamic_model_contract.dgs_explicit_initialization_uids.add(-1)
    with pytest.raises(KeyError, match="UID '-1' is not reachable"):
        duplicate_block(parent, VarFactory())


def test_duplicate_block_preserves_expression_only_external_variables() -> None:
    """Keep measured network variables shared when duplicating a controller.

    :return: None.
    """
    measured_value: sym.Var = sym.Var("measured_value")
    external_bus_voltage: sym.Var = sym.Var("external_bus_voltage")
    source_block: Block = Block(
        algebraic_vars=[measured_value],
        algebraic_eqs=[measured_value - external_bus_voltage],
    )

    copied_block: Block = duplicate_block(source_block, VarFactory())
    copied_value: sym.Var = copied_block.algebraic_vars[0]

    assert copied_value is not measured_value
    assert copied_block.algebraic_eqs[0].left is copied_value
    assert copied_block.algebraic_eqs[0].right is external_bus_voltage


def test_block_diagram_parse_accepts_empty_legacy_payload() -> None:
    """
    Check that empty legacy diagram payloads load as empty diagrams.

    :return: Nothing.
    """
    diagram: BlockDiagram = BlockDiagram()

    diagram.parse(dict())

    assert diagram.status is None
    assert diagram.node_data == dict()
    assert diagram.con_data == dict()


def test_var_factory_parse_var_dict_accepts_legacy_missing_identity_half() -> None:
    """
    Check that a legacy symbolic variable missing one id still loads.

    :return: Nothing.
    """
    vf: VarFactory = VarFactory()

    vf.parse_var_dict([
        {
            "type": "Var",
            "name": "omega_legacy",
            "uid": 55,
            "shared_ref": None,
        }
    ])

    parsed_var: sym.Var | None = vf.get_vars_dict().get(55, None)
    assert parsed_var is not None
    assert parsed_var.uid == 55
    assert parsed_var.non_mutable_uid == 55


def test_block_saver_parser_roundtrip_preserves_declarative_procedural_logic() -> None:
    """
    Check that block saver/parser preserve declarative procedural logic.

    :return: Nothing.
    """
    vf: VarFactory = VarFactory()
    x: sym.Var = vf.add_var(
        "x",
        reference=VarPowerFlowReferenceType.Vm,
        network_conn=True,
        shared_reference="shared-x",
    )
    mode: sym.Var = vf.add_var("mode")
    out: sym.Var = vf.add_var("out")

    block: Block = Block(
        algebraic_vars=[x, mode, out],
        algebraic_eqs=[x + sym.Const(1.0), mode + sym.Const(0.0), out + sym.Const(0.0)],
        inequalities=[x > sym.Const(0.0)],
        discrete_eqs={mode: x + sym.Const(2.0)},
        mode_dict={mode: sym.Const(1.0)},
        procedural_logic=[aflipflop(x=x,
                                    boolset=x > sym.Const(1.0),
                                    boolreset=x < sym.Const(-1.0),
                                    output=out)],
        name="legacy_runtime_block",
    )
    block.dynamic_model_contract.dgs_elmsvs_runtime_adapter = True
    block.dynamic_model_contract.dgs_elmsvs_remote_voltage_var_uid = x.uid
    block.dynamic_model_contract.dgs_explicit_initialization_uids = set((x.uid,))
    block.dynamic_model_contract.dgs_equipment_owned_signal_names = list(("u",))
    block.dynamic_model_contract.explicit_init_excluded_var_names = list(("x",))
    block.dynamic_model_contract.explicit_init_override_init_exprs["x"] = (
        x + sym.Const(3.0)
    )

    direct_restored: Block = Block.parse(
        data=block.to_dict(),
        procedural_logic_codec=ProceduralLogicCodec(),
    )
    direct_restored_x: sym.Var = direct_restored.algebraic_vars[0]
    direct_override: sym.Expr = (
        direct_restored.dynamic_model_contract.explicit_init_override_init_exprs["x"]
    )
    assert direct_restored.dynamic_model_contract.dgs_elmsvs_runtime_adapter
    assert (
        direct_restored.dynamic_model_contract.dgs_elmsvs_remote_voltage_var_uid
        == direct_restored_x.uid
    )
    assert isinstance(direct_override, sym.BinOp)
    assert direct_override.left.uid == direct_restored_x.uid
    assert direct_restored_x.ref is VarPowerFlowReferenceType.Vm
    assert direct_restored_x.network_conn
    assert direct_restored_x.shared_ref is not None
    assert direct_restored_x.shared_ref.name == "shared-x"
    assert direct_restored_x.shared_ref.uid == x.shared_ref.uid

    truncated_data: dict[str, object] = block.to_dict()
    truncated_contract: object = truncated_data["dynamic_model_contract"]
    assert isinstance(truncated_contract, dict)
    truncated_contract.pop("dgs_elmsvs_runtime_adapter")
    with pytest.raises(KeyError, match="dgs_elmsvs_runtime_adapter"):
        Block.parse(
            data=truncated_data,
            procedural_logic_codec=ProceduralLogicCodec(),
        )

    invalid_uid_data: dict[str, object] = block.to_dict()
    invalid_uid_contract: object = invalid_uid_data["dynamic_model_contract"]
    assert isinstance(invalid_uid_contract, dict)
    invalid_uid_contract["dgs_elmsvs_remote_voltage_var_uid"] = -1
    with pytest.raises(KeyError, match="UID '-1' is not reachable"):
        Block.parse(
            data=invalid_uid_data,
            procedural_logic_codec=ProceduralLogicCodec(),
        )

    saver: BlockSaver = BlockSaver(vf)
    saver.save_block(block, main=True)

    # The archive writer JSON-encodes the complete block table.  This check
    # prevents runtime procedural-logic objects from silently causing the
    # ``blocks.symbolic`` archive member to be omitted.
    json.dumps(saver.get_blocks())

    parser_without_codec: BlockParser = BlockParser(VarFactory())
    parser_without_codec.parse_consts(saver.get_const_to_save())
    parser_without_codec.parse_vars(saver.get_vars_to_save())
    parser_without_codec.parse_diff_vars(saver.get_diff_vars_to_save())
    with pytest.raises(ValueError, match="requires an explicit codec"):
        parser_without_codec.parse_block(saver.get_blocks(), block.uid)

    parser: BlockParser = BlockParser(
        var_factory=VarFactory(),
        procedural_logic_codec=ProceduralLogicCodec(),
    )
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())
    restored: Block = parser.parse_block(saver.get_blocks(), block.uid)

    assert len(restored.discrete_eqs) == 1
    assert len(restored.mode_dict) == 1
    assert len(restored.procedural_logic) == 1
    assert isinstance(restored.procedural_logic[0], AnalogFlipFlopLogic)
    restored_x: sym.Var = restored.algebraic_vars[0]
    restored_override: sym.Expr = (
        restored.dynamic_model_contract.explicit_init_override_init_exprs["x"]
    )
    assert restored.dynamic_model_contract.dgs_elmsvs_runtime_adapter
    assert (
        restored.dynamic_model_contract.dgs_elmsvs_remote_voltage_var_uid
        == restored_x.uid
    )
    assert restored.dynamic_model_contract.dgs_explicit_initialization_uids == set(
        (restored_x.uid,)
    )
    assert isinstance(restored_override, sym.BinOp)
    assert restored_override.left is restored_x
    assert len(restored.inequalities) == 1
    restored_inequality: sym.Expr | sym.Comparison = restored.inequalities[0]
    assert isinstance(restored_inequality, sym.Comparison)
    assert restored_inequality.lhs is restored_x
    assert restored_inequality.op is sym.CmpOp.GT


def test_rms_terminal_power_contract_roundtrips_and_fails_closed() -> None:
    """Discard obsolete RMS terminal metadata while validating old payloads.

    :return: None.
    """
    var_factory: VarFactory = VarFactory()
    dc_power: sym.Var = var_factory.add_var(name="Pdc")
    ac_active_power: sym.Var = var_factory.add_var(name="Pac")
    ac_reactive_power: sym.Var = var_factory.add_var(name="Qac")
    block: Block = Block(
        algebraic_vars=list((dc_power, ac_active_power, ac_reactive_power)),
        algebraic_eqs=list((dc_power, ac_active_power, ac_reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Pf, dc_power),
            (VarPowerFlowReferenceType.Pt, ac_active_power),
            (VarPowerFlowReferenceType.Qt, ac_reactive_power),
        )),
    )
    legacy_contributions = list((
        RmsTerminalPowerContribution(
            terminal_side=RmsTerminalSide.FROM,
            active_power_reference=VarPowerFlowReferenceType.Pf,
            reactive_power_reference=None,
        ),
        RmsTerminalPowerContribution(
            terminal_side=RmsTerminalSide.TO,
            active_power_reference=VarPowerFlowReferenceType.Pt,
            reactive_power_reference=VarPowerFlowReferenceType.Qt,
        ),
    ))

    persisted_data: dict[str, object] = block.to_dict()
    contract_data = persisted_data["dynamic_model_contract"]
    assert isinstance(contract_data, dict)
    assert contract_data["version"] == 6
    assert "rms_terminal_power_contributions" not in contract_data
    restored: Block = Block.parse(data=persisted_data)
    copied: Block = copy.deepcopy(block)
    saver: BlockSaver = BlockSaver(var_factory)
    saver.save_block(block, main=True)
    parser: BlockParser = BlockParser(var_factory=VarFactory())
    parser.parse_consts(saver.get_const_to_save())
    parser.parse_vars(saver.get_vars_to_save())
    parser.parse_diff_vars(saver.get_diff_vars_to_save())
    symbolic_io_restored: Block = parser.parse_block(
        blocks_data=saver.get_blocks(),
        main_block_uid=block.uid,
    )

    assert "rms_terminal_power_contributions" not in DynamicModelContract.__slots__

    # Version 1 predates both formulation-specific terminal contracts.
    legacy_data: dict[str, object] = block.to_dict()
    legacy_contract: object = legacy_data["dynamic_model_contract"]
    assert isinstance(legacy_contract, dict)
    legacy_contract["version"] = 1
    legacy_contract.pop("emt_terminal_current_contributions")
    legacy_contract.pop("emt_internal_grounding_link")
    legacy_contract.pop("rms_physical_measurement_point")
    legacy_restored: Block = Block.parse(data=legacy_data)
    assert (
        legacy_restored.dynamic_model_contract.emt_terminal_current_contributions
        == list()
    )

    # Version 2 retains the RMS declaration and predates only the EMT field.
    version_two_data: dict[str, object] = block.to_dict()
    version_two_contract: object = version_two_data["dynamic_model_contract"]
    assert isinstance(version_two_contract, dict)
    version_two_contract["version"] = 2
    version_two_contract["rms_terminal_power_contributions"] = [
        contribution.to_data() for contribution in legacy_contributions
    ]
    version_two_contract.pop("emt_terminal_current_contributions")
    version_two_contract.pop("emt_internal_grounding_link")
    version_two_contract.pop("rms_physical_measurement_point")
    version_two_restored: Block = Block.parse(data=version_two_data)
    assert (
        version_two_restored.dynamic_model_contract.emt_terminal_current_contributions
        == list()
    )

    # Version 3 includes both terminal contracts but predates typed grounding.
    version_three_data: dict[str, object] = block.to_dict()
    version_three_contract: object = version_three_data["dynamic_model_contract"]
    assert isinstance(version_three_contract, dict)
    version_three_contract["version"] = 3
    version_three_contract["rms_terminal_power_contributions"] = [
        contribution.to_data() for contribution in legacy_contributions
    ]
    version_three_contract.pop("emt_internal_grounding_link")
    version_three_contract.pop("rms_physical_measurement_point")
    version_three_restored: Block = Block.parse(data=version_three_data)
    assert not version_three_restored.dynamic_model_contract.emt_internal_grounding_link

    # Version 4 includes typed grounding but predates physical meter identity.
    version_four_data: dict[str, object] = block.to_dict()
    version_four_contract: object = version_four_data["dynamic_model_contract"]
    assert isinstance(version_four_contract, dict)
    version_four_contract["version"] = 4
    version_four_contract["rms_terminal_power_contributions"] = [
        contribution.to_data() for contribution in legacy_contributions
    ]
    version_four_contract.pop("rms_physical_measurement_point")
    version_four_restored: Block = Block.parse(data=version_four_data)
    assert version_four_restored.dynamic_model_contract.rms_physical_measurement_point is None

    malformed_data: dict[str, object] = block.to_dict()
    malformed_contract: object = malformed_data["dynamic_model_contract"]
    assert isinstance(malformed_contract, dict)
    malformed_contract["version"] = 5
    malformed_contract["rms_terminal_power_contributions"] = [
        contribution.to_data() for contribution in legacy_contributions
    ]
    malformed_contributions: object = malformed_contract[
        "rms_terminal_power_contributions"
    ]
    assert isinstance(malformed_contributions, list)
    malformed_first: object = malformed_contributions[0]
    assert isinstance(malformed_first, dict)
    malformed_first["active_power_reference"] = VarPowerFlowReferenceType.Vm.value
    with pytest.raises(ValueError, match="from-terminal active power"):
        Block.parse(data=malformed_data)


def test_rms_physical_measurement_point_roundtrips_and_indexes_by_fid() -> None:
    """Persist selected meter signals and expose a transient global FID index.

    :return: None.
    """
    active_power: sym.Var = sym.Var(name="p_meter")
    reactive_power: sym.Var = sym.Var(name="q_meter")
    internal_filter_state: sym.Var = sym.Var(name="meter_internal")
    meter_block: Block = Block(
        name="meter",
        algebraic_vars=list((
            active_power,
            reactive_power,
            internal_filter_state,
        )),
        algebraic_eqs=list((
            active_power,
            reactive_power,
            internal_filter_state,
        )),
        out_vars=list((active_power, reactive_power)),
    )
    meter_block.dynamic_model_contract.rms_physical_measurement_point = (
        RmsPhysicalMeasurementPoint(
            source_fid="meter-fid",
            target_fid="branch-fid",
            terminal_side=RmsTerminalSide.TO,
            meter_kind=RmsPhysicalMeterKind.POWER,
            output_signal_names=tuple(("p", "q")),
            output_var_uids=tuple((active_power.uid, reactive_power.uid)),
        )
    )
    root_block: Block = Block(
        name="global_measurement_root",
        children=list((meter_block,)),
    )
    restored_root: Block = Block.parse(data=root_block.to_dict())
    measurement_by_fid: dict[str, RmsPhysicalMeasurementPoint] = (
        collect_rms_physical_measurement_points(block=restored_root)
    )
    restored_point: RmsPhysicalMeasurementPoint = measurement_by_fid["meter-fid"]

    assert restored_point.get_target_fid() == "branch-fid"
    assert restored_point.get_terminal_side() is RmsTerminalSide.TO
    assert restored_point.get_meter_kind() is RmsPhysicalMeterKind.POWER
    assert restored_point.get_output_signal_names() == tuple(("p", "q"))
    assert len(restored_point.get_output_var_uids()) == 2

    duplicated_root: Block = duplicate_block(root_block, VarFactory())
    duplicated_point_by_fid: dict[str, RmsPhysicalMeasurementPoint] = (
        collect_rms_physical_measurement_points(block=duplicated_root)
    )
    duplicated_point: RmsPhysicalMeasurementPoint = duplicated_point_by_fid[
        "meter-fid"
    ]
    duplicated_meter: Block = duplicated_root.children[0]
    duplicated_output_uids: tuple[int, ...] = tuple(
        output_var.uid for output_var in duplicated_meter.out_vars
    )
    assert duplicated_point.get_output_var_uids() == duplicated_output_uids
    assert duplicated_output_uids != tuple((active_power.uid, reactive_power.uid))

    invalid_meter_child: Block = copy.deepcopy(meter_block)
    invalid_internal_var: sym.Var = invalid_meter_child.algebraic_vars[2]
    invalid_meter_child.dynamic_model_contract.rms_physical_measurement_point = (
        RmsPhysicalMeasurementPoint(
            source_fid="invalid-child-meter",
            target_fid="branch-fid",
            terminal_side=RmsTerminalSide.TO,
            meter_kind=RmsPhysicalMeterKind.POWER,
            output_signal_names=tuple(("internal",)),
            output_var_uids=tuple((invalid_internal_var.uid,)),
        )
    )
    invalid_child_root: Block = Block(children=list((invalid_meter_child,)))
    with pytest.raises(KeyError, match="outputs owned by the declaring Block"):
        duplicate_block(invalid_child_root, VarFactory())

    duplicate_root: Block = Block(
        children=list((meter_block, copy.deepcopy(meter_block))),
    )
    with pytest.raises(ValueError, match="meter-fid.*duplicated"):
        collect_rms_physical_measurement_points(block=duplicate_root)

    malformed_data: dict[str, object] = root_block.to_dict()
    malformed_children: object = malformed_data["children"]
    assert isinstance(malformed_children, list)
    malformed_meter: object = malformed_children[0]
    assert isinstance(malformed_meter, dict)
    malformed_contract: object = malformed_meter["dynamic_model_contract"]
    assert isinstance(malformed_contract, dict)
    malformed_point: object = malformed_contract["rms_physical_measurement_point"]
    assert isinstance(malformed_point, dict)
    malformed_point["output_var_uids"] = list((
        internal_filter_state.uid,
        reactive_power.uid,
    ))
    with pytest.raises(KeyError, match="outputs owned by the declaring Block"):
        Block.parse(data=malformed_data)

    parent_owned_data: dict[str, object] = root_block.to_dict()
    parent_contract: object = parent_owned_data["dynamic_model_contract"]
    parent_children: object = parent_owned_data["children"]
    assert isinstance(parent_contract, dict)
    assert isinstance(parent_children, list)
    parent_meter_data: object = parent_children[0]
    assert isinstance(parent_meter_data, dict)
    parent_meter_contract: object = parent_meter_data["dynamic_model_contract"]
    assert isinstance(parent_meter_contract, dict)
    child_point_data: object = parent_meter_contract[
        "rms_physical_measurement_point"
    ]
    parent_contract["rms_physical_measurement_point"] = copy.deepcopy(
        child_point_data
    )
    with pytest.raises(KeyError, match="outputs owned by the declaring Block"):
        Block.parse(data=parent_owned_data)


def test_dynamic_model_contract_rejects_incoherent_persistence_states() -> None:
    """Reject incomplete adapters and contradictory runtime declarations.

    :return: Nothing.
    """
    variable: sym.Var = sym.Var(name="x")

    incomplete_elmsym: Block = Block(
        algebraic_vars=list((variable,)),
        algebraic_eqs=list((variable,)),
    )
    incomplete_elmsym.dynamic_model_contract.dgs_elmsym_runtime_adapter = True
    with pytest.raises(ValueError, match="Completed ElmSym adapter contract is incomplete"):
        incomplete_elmsym.to_dict()

    incomplete_elmsvs: Block = Block(
        algebraic_vars=list((variable,)),
        algebraic_eqs=list((variable,)),
    )
    incomplete_elmsvs.dynamic_model_contract.dgs_elmsvs_runtime_adapter = True
    with pytest.raises(ValueError, match="ElmSvs adapter contract is incomplete"):
        incomplete_elmsvs.to_dict()

    incomplete_genstat: Block = Block(
        algebraic_vars=list((variable,)),
        algebraic_eqs=list((variable,)),
    )
    incomplete_genstat.dynamic_model_contract.dgs_elmgenstat_runtime_adapter = True
    with pytest.raises(ValueError, match="ElmGenstat adapter contract is incomplete"):
        incomplete_genstat.to_dict()

    conflicting_adapters: Block = Block()
    conflicting_adapters.dynamic_model_contract.dgs_elmsym_runtime_adapter_pending = True
    conflicting_adapters.dynamic_model_contract.dgs_elmsvs_runtime_adapter = True
    with pytest.raises(ValueError, match="conflicting equipment adapters"):
        conflicting_adapters.to_dict()

    incomplete_ideal_connector: Block = Block()
    incomplete_ideal_connector.dynamic_model_contract.rms_ideal_ac_connector = True
    with pytest.raises(ValueError, match="RMS ideal AC connector contract is incomplete"):
        incomplete_ideal_connector.to_dict()

    incomplete_ideal_transformer: Block = Block()
    incomplete_ideal_transformer.dynamic_model_contract.rms_ideal_transformer = True
    with pytest.raises(ValueError, match="RMS ideal transformer contract is incomplete"):
        incomplete_ideal_transformer.to_dict()

    conflicting_ideal_models: Block = Block()
    conflicting_ideal_models.dynamic_model_contract.rms_ideal_ac_connector = True
    conflicting_ideal_models.dynamic_model_contract.rms_ideal_transformer = True
    with pytest.raises(ValueError, match="mutually exclusive"):
        conflicting_ideal_models.to_dict()

    mismatched_shells: Block = Block()
    mismatched_shells.dynamic_model_contract.runtime_equipment_shell_sync_names = list(("x",))
    with pytest.raises(ValueError, match="names and UIDs must have equal lengths"):
        mismatched_shells.to_dict()

    incomplete_regc: Block = Block()
    incomplete_regc.dynamic_model_contract.dgs_open_standard_regc_current_pll = True
    with pytest.raises(ValueError, match="requires a complete ElmGenstat adapter"):
        incomplete_regc.to_dict()

    duplicate_names: Block = Block()
    duplicate_names.dynamic_model_contract.runtime_measurement_shell_sync_names = list(("x", "x"))
    with pytest.raises(ValueError, match="non-empty and unique"):
        duplicate_names.to_dict()

    unreachable_override: Block = Block()
    unreachable_override.dynamic_model_contract.explicit_init_override_init_exprs["x"] = variable
    with pytest.raises(KeyError, match="override UID"):
        unreachable_override.to_dict()


def test_block_saver_rejects_incoherent_dynamic_model_contract() -> None:
    """Reject an invalid runtime contract at the canonical file boundary.

    :return: Nothing.
    """
    variable: sym.Var = sym.Var(name="x")
    block: Block = Block(
        algebraic_vars=list((variable,)),
        algebraic_eqs=list((variable,)),
    )
    block.dynamic_model_contract.dgs_elmsvs_runtime_adapter = True
    saver: BlockSaver = BlockSaver(VarFactory())

    with pytest.raises(ValueError, match="ElmSvs adapter contract is incomplete"):
        saver.save_block(block, main=True)


@pytest.mark.parametrize(
    "invalid_resistance",
    (math.nan, math.inf, -math.inf, 0.0, -1.0),
)
def test_dynamic_model_contract_rejects_invalid_open_resistance(
        invalid_resistance: float,
) -> None:
    """Reject non-finite and non-positive logical-actuator resistance.

    :param invalid_resistance: Invalid serialized resistance value.
    :return: Nothing.
    """
    source_data: dict[str, object] = Block().to_dict()
    source_contract: object = source_data["dynamic_model_contract"]
    assert isinstance(source_contract, dict)
    source_contract["dgs_logical_actuator_root_id"] = "root-fid"
    source_contract["dgs_open_resistance_ohm"] = invalid_resistance

    with pytest.raises((ValueError, TypeError)):
        Block.parse(data=source_data)


def test_block_parse_rejects_malformed_structural_fields() -> None:
    """Reject malformed containers before reconstructing a partial block graph.

    :return: None.
    """
    source_block: Block = Block(name="typed persistence boundary")

    # Expression collections must remain ordered declarative records.
    malformed_sequence_data: dict[str, object] = source_block.to_dict()
    malformed_sequence_data["state_vars"] = dict()
    with pytest.raises(TypeError, match="field 'state_vars' must be a list"):
        Block.parse(data=malformed_sequence_data)

    # Child declarations cannot retain arbitrary imported objects.
    malformed_child_data: dict[str, object] = source_block.to_dict()
    malformed_child_data["children"] = list((None,))
    with pytest.raises(TypeError, match="field 'children' item 0"):
        Block.parse(data=malformed_child_data)

    # Scalar identity fields are validated before the final constructor runs.
    malformed_name_data: dict[str, object] = source_block.to_dict()
    malformed_name_data["name"] = 17
    with pytest.raises(TypeError, match="field 'name' must be a string"):
        Block.parse(data=malformed_name_data)


def test_block_parsers_migrate_legacy_frequency_mapping() -> None:
    """Migrate persisted ``fn`` API mappings to the canonical ``freq`` key.

    :return: Nothing.
    """
    source_factory: VarFactory = VarFactory()
    frequency: sym.Var = source_factory.add_var("frequency")
    source_block: Block = Block(
        algebraic_vars=list([frequency]),
        api_obj_mapping=dict({ParamPowerFlowReferenceType.freq: frequency}),
        name="legacy_frequency_mapping",
    )

    # Exercise the declarative Block parser after replacing the current key
    # with the spelling emitted by older saved dynamic-model files.
    declarative_data: Dict[str, Any] = source_block.to_dict()
    declarative_mapping: Dict[str, Any] = declarative_data["api_obj_mapping"]
    declarative_mapping["fn"] = declarative_mapping.pop(ParamPowerFlowReferenceType.freq.value)
    declarative_restored: Block = Block.parse(data=declarative_data)
    declarative_frequency: sym.Var | None = declarative_restored.api_obj_mapping.get(
        ParamPowerFlowReferenceType.freq,
        None,
    )

    assert declarative_frequency is not None
    assert declarative_frequency.uid == frequency.uid

    # Exercise the legacy UID-based parser because historical project files
    # use this second persistence representation as well.
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)
    legacy_blocks: Dict[int, Dict[str, Any]] = copy.deepcopy(saver.get_blocks())
    legacy_block_data: Dict[str, Any] = legacy_blocks[source_block.uid]
    legacy_mapping: Dict[str, int | None] = legacy_block_data["api_obj_mapping"]
    legacy_mapping["fn"] = legacy_mapping.pop(ParamPowerFlowReferenceType.freq.value)

    legacy_parser: BlockParser = BlockParser(VarFactory(), logger=Logger())
    legacy_parser.parse_consts(saver.get_const_to_save())
    legacy_parser.parse_vars(saver.get_vars_to_save())
    legacy_parser.parse_diff_vars(saver.get_diff_vars_to_save())
    legacy_restored: Block = legacy_parser.parse_block(legacy_blocks, source_block.uid)
    legacy_frequency: sym.Var | None = legacy_restored.api_obj_mapping.get(
        ParamPowerFlowReferenceType.freq,
        None,
    )

    assert legacy_frequency is not None
    assert legacy_frequency.uid == frequency.uid


def test_block_parser_only_warns_for_broken_optional_mapping_references() -> None:
    """
    Check that optional null mappings are silent while broken UIDs warn.

    :return: Nothing.
    """
    source_factory: VarFactory = VarFactory()
    variable: sym.Var = source_factory.add_var("x")
    source_block: Block = Block(
        algebraic_vars=[variable],
        algebraic_eqs=[variable],
        external_mapping=dict({VarPowerFlowReferenceType.Vm: None}),
        api_obj_mapping=dict({ParamPowerFlowReferenceType.r: None}),
        name="optional_mapping_block",
    )
    saver: BlockSaver = BlockSaver(source_factory)
    saver.save_block(source_block, main=True)

    # Parse the explicit legacy nulls first. They represent optional empty
    # mapping slots and therefore must not interrupt file opening with warnings.
    null_logger: Logger = Logger()
    null_parser: BlockParser = BlockParser(VarFactory(), logger=null_logger)
    null_parser.parse_consts(saver.get_const_to_save())
    null_parser.parse_vars(saver.get_vars_to_save())
    null_parser.parse_diff_vars(saver.get_diff_vars_to_save())
    restored_block: Block = null_parser.parse_block(saver.get_blocks(), source_block.uid)

    assert null_logger.warning_count() == 0
    assert restored_block.api_obj_mapping == dict()
    assert restored_block.external_mapping[VarPowerFlowReferenceType.Vm] is None

    # Replace both optional nulls with non-null UIDs absent from the factory.
    # Those references claim that data exists, so silently dropping them could
    # change model initialization and must remain visible to the user.
    broken_blocks: Dict[int, Dict[str, Any]] = copy.deepcopy(saver.get_blocks())
    broken_block_data: Dict[str, Any] = broken_blocks[source_block.uid]
    broken_api_mapping: Dict[str, int | None] = broken_block_data["api_obj_mapping"]
    broken_external_mapping: Dict[str, int | None] = broken_block_data["external_mapping"]
    broken_api_mapping[ParamPowerFlowReferenceType.r.value] = variable.uid + 1
    broken_external_mapping[VarPowerFlowReferenceType.Vm.value] = variable.uid + 2

    broken_logger: Logger = Logger()
    broken_parser: BlockParser = BlockParser(VarFactory(), logger=broken_logger)
    broken_parser.parse_consts(saver.get_const_to_save())
    broken_parser.parse_vars(saver.get_vars_to_save())
    broken_parser.parse_diff_vars(saver.get_diff_vars_to_save())
    broken_parser.parse_block(broken_blocks, source_block.uid)

    assert broken_logger.warning_count() == 2
    assert {entry.device_property for entry in broken_logger.entries} == {
        "api_obj_mapping",
        "external_mapping",
    }


# -----------------------------------------------------------------------------
# 9. Immutability checks
# -----------------------------------------------------------------------------
#
# def test_mappingproxy_immutable():
#     assert isinstance(sym.BinOp._impl, MappingProxyType)
#     with pytest.raises(TypeError):
#         sym.BinOp._impl["+"] = None  # type: ignore[misc]

#
# def test_frozen_dataclass_immutable():
#     c = sym.Const(1)
#     with pytest.raises(AttributeError):
#         c.value = 2  # type: ignore[attr-defined]
