# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Structural affinity classification of the Kundur EMT residual rows, checked by numerical oracles."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

import numpy as np
import pytest

from tests.EMT.test_kundur_emt_initialization import _build_kundur_problem
from VeraGridEngine.enumerations import ExpressionAffinity
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.problems.emt_residual_row_classification import (
    EmtResidualRowClassification,
    classify_emt_residual_rows,
)
from VeraGridEngine.Utils.Symbolic.structural_affinity import StructuralAffinityAnalyzer
from VeraGridEngine.Utils.Symbolic.symbolic import Var

STEP_SIZE: float = 5e-6
DISCRETISATION_GAIN: float = 2.0 / STEP_SIZE
TOLERANCE: float = 1e-9
SEED: int = 20261020


class _OracleContext:
    """Problem data and uid bindings used by the eval_uid oracles, independent of the classifier."""

    __slots__ = ("problem", "state_vars", "rows", "unknown_uids", "constant_uids", "excitation_uids",
                 "variables", "history", "state_origin_uids")

    def __init__(self, problem: EmtProblemDae) -> None:
        """
        Collect rows in solver order and every variable they reference.

        :param problem: Kundur EMT problem.
        """
        self.problem: EmtProblemDae = problem
        self.state_vars: List[Var] = problem.get_state_vars()
        self.rows: List[Any] = list(problem.get_state_eqs()) + list(problem.get_algebraic_eqs())
        self.unknown_uids: Set[int] = set()
        for var in self.state_vars:
            self.unknown_uids.add(var.uid)
        for var in problem.get_algebraic_vars():
            self.unknown_uids.add(var.uid)
        self.constant_uids: Set[int] = set()
        for var in problem.get_constant_parameters():
            self.constant_uids.add(var.uid)
        self.excitation_uids: Set[int] = {problem.glob_time.uid}
        for var in problem.get_variable_parameters():
            self.excitation_uids.add(var.uid)
        self.variables: Dict[int, Var] = dict()
        for row in self.rows:
            for var in row.get_vars():
                self.variables[var.uid] = var
        rng: np.random.Generator = np.random.default_rng(SEED)
        self.history: Dict[int, float] = dict()
        for uid in sorted(self.unknown_uids):
            self.history[uid] = float(rng.normal())
        self.state_origin_uids: List[int] = list()
        for var in self.state_vars:
            self.state_origin_uids.append(_chain_origin(var).uid)


def _chain_origin(var: Var) -> Var:
    """
    Walk a base_var chain without touching the caching origin_var property.

    :param var: Variable to resolve.
    :return: Root of the chain.
    """
    current: Var = var
    while current.base_var is not None:
        current = current.base_var
    return current


def _chain_order(var: Var) -> int:
    """
    Return the derivative order of a placeholder.

    :param var: Variable to inspect.
    :return: Number of base_var links.
    """
    order: int = 0
    current: Var = var
    while current.base_var is not None:
        current = current.base_var
        order += 1
    return order


def _excitation_binding(context: _OracleContext, time_value: float, seed: int) -> Dict[int, float]:
    """
    Bind parameters and time for one excitation scenario.

    Runtime parameters take their problem values at ``time_value`` scaled by an
    independent factor in [0.9, 1.1]; zero-valued ones get a small positive
    offset so that their coefficients are exercised.

    :param context: Oracle context.
    :param time_value: Simulation time of the scenario.
    :param seed: Seed of the scenario.
    :return: Uid bindings for parameters, time and the step size.
    """
    rng: np.random.Generator = np.random.default_rng(seed)
    problem: EmtProblemDae = context.problem
    binding: Dict[int, float] = dict()
    for var, value in zip(problem.get_constant_parameters(), problem.get_parameters_values()):
        binding[var.uid] = float(value.value)
    runtime_values: np.ndarray = problem.def_event_params_fn(np.array(problem.event_params_values, dtype=np.float64), time_value)
    assert len(runtime_values) == len(problem.get_variable_parameters())
    for var, value in zip(problem.get_variable_parameters(), runtime_values):
        scaled: float = float(value) * float(rng.uniform(0.9, 1.1))
        if scaled == 0.0:
            scaled = float(rng.uniform(0.01, 0.1))
        else:
            pass
        binding[var.uid] = scaled
    for uid, var in context.variables.items():
        if uid in binding:
            pass
        elif var.name in ("time", problem.TIME_NAME):
            binding[uid] = time_value
        elif var.name == "h" and var.base_var is None and uid not in context.unknown_uids:
            binding[uid] = STEP_SIZE
        else:
            pass
    binding[problem.glob_time.uid] = time_value
    return binding


def _bindings(context: _OracleContext, unknowns: Dict[int, float], excitation: Dict[int, float]) -> Dict[int, float]:
    """
    Combine unknown values with an excitation scenario and discretise placeholders.

    Parameter bindings take precedence over placeholder bindings, matching the
    compiler's role order.

    :param context: Oracle context.
    :param unknowns: Values of the unknowns.
    :param excitation: Parameter, time and step-size bindings.
    :return: Complete uid bindings.
    """
    binding: Dict[int, float] = dict(excitation)
    binding.update(unknowns)
    for uid, var in context.variables.items():
        if uid in binding or var.base_var is None:
            pass
        else:
            origin_uid: int = _chain_origin(var).uid
            value: float = unknowns[origin_uid]
            order: int = _chain_order(var)
            while order > 0:
                value = DISCRETISATION_GAIN * (value - context.history[origin_uid])
                order -= 1
            binding[uid] = value
    return binding


def _row_value(context: _OracleContext, row_index: int, binding: Dict[int, float]) -> float:
    """
    Evaluate one residual row; state rows are evaluated as gain*(origin - history) - f.

    :param context: Oracle context.
    :param row_index: Row in solver order.
    :param binding: Complete uid bindings.
    :return: Residual value.
    """
    value: float = float(context.rows[row_index].eval_uid(binding))
    if row_index < len(context.state_vars):
        origin_uid: int = context.state_origin_uids[row_index]
        value = DISCRETISATION_GAIN * (binding[origin_uid] - context.history[origin_uid]) - value
    else:
        pass
    return value


def _random_unknowns(context: _OracleContext, rng: np.random.Generator) -> Dict[int, float]:
    """
    Draw one random point for every unknown.

    :param context: Oracle context.
    :param rng: Random generator.
    :return: Values of the unknowns.
    """
    values: Dict[int, float] = dict()
    for uid in sorted(context.unknown_uids):
        values[uid] = float(rng.normal())
    return values


def _independent_support(context: _OracleContext, row_index: int) -> Set[int]:
    """
    Compute the referenced unknowns of a row with Expr.get_vars, independently of the analyzer.

    :param context: Oracle context.
    :param row_index: Row in solver order.
    :return: Referenced unknown uids, placeholders mapped to their origin.
    """
    support: Set[int] = set()
    for var in context.rows[row_index].get_vars():
        if var.uid in context.unknown_uids:
            support.add(var.uid)
        elif var.uid in context.constant_uids or var.uid in context.excitation_uids:
            pass
        elif var.base_var is not None and _chain_origin(var).uid in context.unknown_uids:
            support.add(_chain_origin(var).uid)
        else:
            pass
    if row_index < len(context.state_vars):
        support.add(context.state_origin_uids[row_index])
    else:
        pass
    return support


def _var_snapshot(context: _OracleContext) -> List[Tuple[int, int, int, int, str]]:
    """
    Record the identity-relevant slots of every reachable variable.

    :param context: Oracle context.
    :return: One tuple per variable.
    """
    snapshot: List[Tuple[int, int, int, int, str]] = list()
    reachable: List[Var] = list(context.state_vars) + list(context.variables.values())
    for var in reachable:
        snapshot.append((id(var.diff_var), id(var.base_var), id(var._origin_var), var.uid, var.name))
    return snapshot


@pytest.fixture(scope="module")
def kundur_problem() -> EmtProblemDae:
    """
    Build the self-contained Kundur EMT problem once for this module.

    :return: Kundur EMT problem.
    """
    return _build_kundur_problem()[0]


def test_kundur_rows_follow_solver_order_and_do_not_mutate_the_problem(kundur_problem: EmtProblemDae) -> None:
    """Row count and order follow the solver; no variable or equation is touched."""
    context: _OracleContext = _OracleContext(kundur_problem)
    variables_before: List[Tuple[int, int, int, int, str]] = _var_snapshot(context)
    equation_ids_before: List[int] = [id(row) for row in context.rows]
    equation_text_before: List[str] = [str(row) for row in context.rows]

    classification: EmtResidualRowClassification = classify_emt_residual_rows(kundur_problem)

    assert _var_snapshot(context) == variables_before
    assert [id(row) for row in list(kundur_problem.get_state_eqs()) + list(kundur_problem.get_algebraic_eqs())] == equation_ids_before
    assert [str(row) for row in context.rows] == equation_text_before
    assert len(classification.get_row_affinities()) == len(kundur_problem.get_state_eqs()) + len(kundur_problem.get_algebraic_eqs())
    assert classification.get_state_row_count() == len(kundur_problem.get_state_eqs())
    for row_index in range(classification.get_state_row_count()):
        assert classification.get_row_affinities()[row_index] in (ExpressionAffinity.AFFINE, ExpressionAffinity.NONLINEAR)


def test_kundur_classification_passes_independent_oracles(kundur_problem: EmtProblemDae) -> None:
    """Affinity, coefficient invariance, unknown-free, support and recall oracles hold on Kundur."""
    context: _OracleContext = _OracleContext(kundur_problem)
    classification: EmtResidualRowClassification = classify_emt_residual_rows(kundur_problem)
    affinities: Tuple[ExpressionAffinity, ...] = classification.get_row_affinities()
    rng: np.random.Generator = np.random.default_rng(SEED + 1)
    scenario_1: Dict[int, float] = _excitation_binding(context, 0.01, SEED + 2)
    scenario_2: Dict[int, float] = _excitation_binding(context, 0.37, SEED + 3)

    # Per-row supports reported by an analyzer built with the normative REQ-003 roles.
    analyzer: StructuralAffinityAnalyzer = StructuralAffinityAnalyzer(
        unknown_uids=context.unknown_uids,
        epoch_constant_uids=context.constant_uids,
        excitation_uids=context.excitation_uids,
        excitation_names={"time", kundur_problem.TIME_NAME},
        epoch_constant_names={"h"},
    )

    nonlinear_support: Set[int] = set()
    oracle_affine_rows: int = 0
    recognised_rows: int = 0
    for row_index, affinity in enumerate(affinities):
        point_u: Dict[int, float] = _random_unknowns(context, rng)
        point_v: Dict[int, float] = _random_unknowns(context, rng)
        weight: float = float(rng.uniform(0.1, 0.9))
        point_w: Dict[int, float] = dict()
        for uid in point_u:
            point_w[uid] = weight * point_u[uid] + (1.0 - weight) * point_v[uid]

        r_u: float = _row_value(context, row_index, _bindings(context, point_u, scenario_1))
        r_v: float = _row_value(context, row_index, _bindings(context, point_v, scenario_1))
        r_w: float = _row_value(context, row_index, _bindings(context, point_w, scenario_1))
        r_u_2: float = _row_value(context, row_index, _bindings(context, point_u, scenario_2))
        r_v_2: float = _row_value(context, row_index, _bindings(context, point_v, scenario_2))
        is_affine: bool = abs(r_w - weight * r_u - (1.0 - weight) * r_v) <= TOLERANCE * max(1.0, abs(weight * r_u) + abs((1.0 - weight) * r_v))
        is_invariant: bool = abs((r_u - r_v) - (r_u_2 - r_v_2)) <= TOLERANCE * max(1.0, abs(r_u) + abs(r_v) + abs(r_u_2) + abs(r_v_2))

        # (a) and (b): every non-NONLINEAR row is affine with epoch-constant coefficients.
        if affinity != ExpressionAffinity.NONLINEAR:
            assert is_affine, f"row {row_index} labelled {affinity} fails the affinity oracle"
            assert is_invariant, f"row {row_index} labelled {affinity} fails the invariance oracle"
        else:
            nonlinear_support.update(_independent_support(context, row_index))

        # (c): unknown-free rows do not depend on the unknowns.
        if affinity == ExpressionAffinity.CONSTANT or affinity == ExpressionAffinity.EXCITATION:
            assert r_u == r_v
        else:
            pass

        # (d): unknowns outside the reported support do not change the row.
        reported: Set[int] = set(analyzer.get_unknown_support(context.rows[row_index]))
        if row_index < len(context.state_vars):
            reported.add(context.state_origin_uids[row_index])
        else:
            pass
        assert reported == _independent_support(context, row_index)
        moved: Dict[int, float] = dict(point_u)
        for uid in moved:
            if uid in reported:
                pass
            else:
                moved[uid] = float(rng.normal())
        assert _row_value(context, row_index, _bindings(context, moved, scenario_1)) == r_u

        if is_affine and is_invariant:
            oracle_affine_rows += 1
            if affinity != ExpressionAffinity.NONLINEAR:
                recognised_rows += 1
            else:
                pass
        else:
            pass

    # (e): non-trivial and not over-conservative.
    assert len(classification.get_affine_row_indices()) > 0
    assert len(classification.get_nonlinear_row_indices()) > 0
    assert recognised_rows >= 0.9 * oracle_affine_rows
    # Supports are exact on Kundur: no opaque rows and N equals the independently computed union.
    assert classification.get_opaque_row_indices() == ()
    assert classification.get_nonlinear_support_uids() == frozenset(nonlinear_support)
    assert len(nonlinear_support) < len(context.unknown_uids)
