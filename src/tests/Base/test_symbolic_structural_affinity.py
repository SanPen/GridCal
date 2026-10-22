# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for the conservative structural affinity analyzer."""

from __future__ import annotations

from typing import Dict, List, Tuple

from VeraGridEngine.enumerations import ExpressionAffinity
from VeraGridEngine.IO.modelica.modelica_parser import ExternalFunc, LogicExpr
from VeraGridEngine.Utils.Symbolic.structural_affinity import StructuralAffinityAnalyzer
from VeraGridEngine.Utils.Symbolic.symbolic import (
    BinOp,
    CmpOp,
    Comparison,
    Const,
    Expr,
    Func,
    Func2,
    UnOp,
    Var,
    atan2,
    cos,
    exp,
    heaviside,
    rand,
    sin,
    sqrt,
)

CONSTANT: ExpressionAffinity = ExpressionAffinity.CONSTANT
EXCITATION: ExpressionAffinity = ExpressionAffinity.EXCITATION
AFFINE: ExpressionAffinity = ExpressionAffinity.AFFINE
NONLINEAR: ExpressionAffinity = ExpressionAffinity.NONLINEAR


class _Symbols:
    """Fresh symbols and an analyzer configured with EMT-like roles."""

    __slots__ = ("x", "y", "v", "p", "q", "p_var", "t", "t_clone", "h", "d_x", "d_v", "z", "d_z", "d2_x", "stray", "analyzer")

    def __init__(self) -> None:
        """Create unknowns x, y, v; constant parameters p, q; runtime parameter p_var; time t."""
        self.x: Var = Var("x")
        self.y: Var = Var("y")
        self.v: Var = Var("v")
        self.p: Var = Var("p")
        self.q: Var = Var("q")
        self.p_var: Var = Var("p_var")
        self.t: Var = Var("glob_time")
        self.t_clone: Var = Var("time")
        self.h: Var = Var("h")
        self.z: Var = Var("z")
        self.d_x: Var = Var("d_x", base_var=self.x)
        self.d_v: Var = Var("d_v", base_var=self.v)
        self.d_z: Var = Var("d_z", base_var=self.z)
        self.d2_x: Var = Var("d2_x", base_var=self.d_x)
        self.stray: Var = Var("stray")
        self.analyzer: StructuralAffinityAnalyzer = StructuralAffinityAnalyzer(
            unknown_uids={self.x.uid, self.y.uid, self.v.uid},
            epoch_constant_uids={self.p.uid, self.q.uid},
            excitation_uids={self.p_var.uid, self.t.uid},
            excitation_names={"time", "glob_time"},
            epoch_constant_names={"h"},
        )


def test_acceptance_examples_of_the_lattice() -> None:
    """Affine rows with symbolic coefficients, constants and excitations are recognised."""
    s = _Symbols()
    assert s.analyzer.classify(3 * s.p * s.x + s.y - sin(s.t)) == AFFINE
    assert s.analyzer.classify(s.p * s.q) == CONSTANT
    assert s.analyzer.classify(cos(s.t) * s.p) == EXCITATION
    assert s.analyzer.classify(s.x / (2 * s.p)) == AFFINE
    assert s.analyzer.classify(s.x ** 1.0) == AFFINE
    assert s.analyzer.classify(s.x ** Const(1)) == AFFINE
    assert s.analyzer.classify(s.x ** Const(0)) == CONSTANT
    assert s.analyzer.classify(s.p ** 2) == CONSTANT
    assert s.analyzer.classify(s.t ** 2) == EXCITATION
    assert s.analyzer.classify(-s.x + s.p_var) == AFFINE
    assert s.analyzer.classify(s.h * s.x) == AFFINE


def test_counter_examples_of_the_lattice() -> None:
    """Products, functions, divisions and powers of unknowns are NONLINEAR."""
    s = _Symbols()
    assert s.analyzer.classify(s.x * s.y) == NONLINEAR
    assert s.analyzer.classify(sin(s.x)) == NONLINEAR
    assert s.analyzer.classify(s.x / s.y) == NONLINEAR
    assert s.analyzer.classify(s.p / s.x) == NONLINEAR
    assert s.analyzer.classify(s.x ** 2) == NONLINEAR
    assert s.analyzer.classify(s.x ** s.p) == NONLINEAR
    assert s.analyzer.classify(s.x ** Const(None)) == NONLINEAR
    assert s.analyzer.classify(Const(2) ** s.x) == NONLINEAR
    assert s.analyzer.classify(s.p ** s.x) == NONLINEAR
    assert s.analyzer.classify(s.t ** s.x) == NONLINEAR
    assert s.analyzer.classify(Const(10) ** (s.x / 20) - s.y) == NONLINEAR


def test_time_and_runtime_coefficients_are_nonlinear() -> None:
    """Coefficients that move with time or runtime parameters break the invariance horizon."""
    s = _Symbols()
    assert s.analyzer.classify(s.t * s.x) == NONLINEAR
    assert s.analyzer.classify(s.t_clone * s.x) == NONLINEAR
    assert s.analyzer.classify(s.p_var * s.x) == NONLINEAR
    assert s.analyzer.classify(s.x / s.p_var) == NONLINEAR
    assert s.analyzer.classify(Const(None) * s.x) == NONLINEAR
    assert s.analyzer.classify(sin(s.t_clone)) == EXCITATION


def test_derivative_placeholders_follow_their_origin() -> None:
    """A derivative placeholder is affine in its unknown origin, at any order."""
    s = _Symbols()
    assert s.analyzer.classify(Const(2) * s.d_v - s.p_var) == AFFINE
    assert s.analyzer.get_unknown_support(Const(2) * s.d_v - s.p_var) == frozenset({s.v.uid})
    assert s.analyzer.classify(s.y * s.d_x) == NONLINEAR
    assert s.analyzer.classify(s.d2_x + s.y) == AFFINE
    assert s.analyzer.get_unknown_support(s.d2_x + s.y) == frozenset({s.x.uid, s.y.uid})
    assert s.analyzer.classify(s.d_z) == NONLINEAR
    assert s.analyzer.get_unknown_support(s.d_z) == frozenset()


def test_unresolved_variables_are_nonlinear() -> None:
    """A variable without any role is never treated as a constant."""
    s = _Symbols()
    assert s.analyzer.classify(s.stray) == NONLINEAR
    assert s.analyzer.classify(s.stray + s.x) == NONLINEAR


def test_function_whitelist() -> None:
    """Deterministic functions of constants keep their class; rand and unknown operators do not."""
    s = _Symbols()
    assert s.analyzer.classify(exp(s.p) * s.x) == AFFINE
    assert s.analyzer.classify(sqrt(s.p_var)) == EXCITATION
    assert s.analyzer.classify(heaviside(s.t) + s.x) == AFFINE
    assert s.analyzer.classify(atan2(s.p, s.q) * s.x) == AFFINE
    assert s.analyzer.classify(Func2("max", s.p_var, s.p)) == EXCITATION
    assert s.analyzer.classify(Func2("min", s.x, s.p)) == NONLINEAR
    assert s.analyzer.classify(rand(Const(1)) * s.x) == NONLINEAR
    assert s.analyzer.classify(s.x + rand(Const(0))) == NONLINEAR
    assert s.analyzer.classify(Func(s.p, "unknown_op")) == NONLINEAR
    assert s.analyzer.classify(Func2("hypot", s.p, s.q)) == NONLINEAR
    assert s.analyzer.classify(UnOp("not", s.p)) == NONLINEAR
    assert s.analyzer.classify(BinOp(s.p, "%", s.q)) == NONLINEAR


def test_unsupported_nodes_are_nonlinear_and_opaque() -> None:
    """Nodes outside the supported set make a row NONLINEAR with all unknowns as support."""
    s = _Symbols()
    all_unknowns: frozenset = frozenset({s.x.uid, s.y.uid, s.v.uid})
    external: ExternalFunc = ExternalFunc("f", (s.x,))
    logic: LogicExpr = LogicExpr("and", (s.p, s.q))
    comparison: Comparison = Comparison(s.x, CmpOp.LE, s.y)
    for row in (external + s.y, logic * s.x, comparison, rand(s.p) + s.x, BinOp(s.p, "%", s.q)):
        assert s.analyzer.classify(row) == NONLINEAR
        assert s.analyzer.is_opaque(row)
        assert s.analyzer.get_unknown_support(row) == all_unknowns
    assert not s.analyzer.is_opaque(s.x * s.y + sin(s.p))


def test_supports_map_placeholders_and_skip_parameters() -> None:
    """Supports contain referenced unknowns only."""
    s = _Symbols()
    assert s.analyzer.get_unknown_support(s.p * s.x + s.t + s.d_v) == frozenset({s.x.uid, s.v.uid})
    assert s.analyzer.get_unknown_support(s.p + s.q) == frozenset()


def test_every_pairwise_rank_maximum() -> None:
    """Sums take the higher rank for every ordered pair of classes."""
    s = _Symbols()
    representatives: Dict[ExpressionAffinity, Expr] = {
        CONSTANT: s.p,
        EXCITATION: s.p_var,
        AFFINE: s.x,
        NONLINEAR: s.x * s.y,
    }
    order: List[ExpressionAffinity] = [CONSTANT, EXCITATION, AFFINE, NONLINEAR]
    for first_rank, first in enumerate(order):
        for second_rank, second in enumerate(order):
            expected: ExpressionAffinity = order[first_rank if first_rank >= second_rank else second_rank]
            assert s.analyzer.classify(representatives[first] + representatives[second]) == expected
            assert s.analyzer.classify(representatives[first] - representatives[second]) == expected


def test_shared_subexpressions_are_classified_once_and_deep_trees_do_not_recurse() -> None:
    """The memo is identity-keyed and the traversal is iterative."""
    s = _Symbols()
    shared: Expr = s.p * s.x + s.q * s.y
    first: Expr = shared + s.v
    second: Expr = shared - s.v
    assert s.analyzer.classify(first) == AFFINE
    assert s.analyzer.classify(second) == AFFINE

    deep: Expr = s.x
    depth: int = 0
    while depth < 10000:
        deep = BinOp(deep, "+", Const(1.0))
        depth += 1
    assert s.analyzer.classify(deep) == AFFINE
    assert s.analyzer.get_unknown_support(deep) == frozenset({s.x.uid})


def test_classification_does_not_write_variables() -> None:
    """The analyzer neither fills origin caches nor rewires derivative chains."""
    s = _Symbols()
    snapshot: List[Tuple[int, int, int, int]] = list()
    for var in (s.x, s.v, s.d_x, s.d_v, s.d2_x):
        snapshot.append((id(var.diff_var), id(var.base_var), var.uid, id(var._origin_var)))
    row: Expr = s.y * s.d2_x + s.d_v
    s.analyzer.classify(row)
    s.analyzer.get_unknown_support(row)
    after: List[Tuple[int, int, int, int]] = list()
    for var in (s.x, s.v, s.d_x, s.d_v, s.d2_x):
        after.append((id(var.diff_var), id(var.base_var), var.uid, id(var._origin_var)))
    assert snapshot == after
