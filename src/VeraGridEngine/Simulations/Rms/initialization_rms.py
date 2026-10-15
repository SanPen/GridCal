# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Consistent steady-state initialization for RMS DAE problems."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Set, Tuple
import warnings

import numpy as np
import scipy.optimize as spo
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian, SymbolicVector
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import RmsInitializationMethod

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae


def _build_state_equation_lookup(problem: Any) -> Dict[int, Expr]:
    """Map each RMS state UID to its differential right-hand side."""
    return {
        state_var.uid: state_eq
        for state_var, state_eq in zip(problem.state_vars, problem.state_eqs)
    }


def _collect_fixed_pf_bus_voltage_uids(problem: Any) -> Set[int]:
    """Return bus-voltage UIDs that must retain their power-flow seeds."""
    fixed_uids: Set[int] = set()
    grid = getattr(problem, "grid", None)
    for bus in getattr(grid, "buses", []):
        bus_model = getattr(bus, "rms_model", None)
        for bus_var in getattr(bus_model, "algebraic_vars", []):
            if isinstance(bus_var, Var):
                fixed_uids.add(bus_var.uid)
    return fixed_uids


def _collect_initialization_problem(
        problem: Any,
        fix_pf_bus_voltages: bool,
) -> Tuple[List[Var], List[Expr]] | None:
    """Collect unresolved states, free algebraics, and consistency residuals."""
    state_eq_lookup = _build_state_equation_lookup(problem)
    init_eq_lookup: Dict[Var, Expr] = problem.sys_block.init_eqs
    state_unknown_vars: List[Var] = []
    state_residual_eqs: List[Expr] = []

    for state_var in problem.state_vars:
        if state_var.uid in problem.init_guess:
            continue
        state_unknown_vars.append(state_var)
        if state_var in init_eq_lookup:
            state_residual_eqs.append(state_var - init_eq_lookup[state_var])
        elif state_var.uid in state_eq_lookup:
            state_residual_eqs.append(state_eq_lookup[state_var.uid])
        else:
            state_residual_eqs.append(state_var)

    algebraic_vars: List[Var] = list(problem.algebraic_vars)
    algebraic_eqs: List[Expr] = list(problem.algebraic_eqs)
    fixed_uids = (
        _collect_fixed_pf_bus_voltage_uids(problem)
        if fix_pf_bus_voltages
        else set()
    )
    algebraic_unknown_vars = [
        var for var in algebraic_vars if var.uid not in fixed_uids
    ]

    # When the slack angle is free, replace the redundant slack active-power
    # row with the PF angle reference to remove the global angle gauge.
    get_reference_indices = getattr(problem, "get_small_signal_reference_indices", None)
    reference_indices = get_reference_indices() if get_reference_indices is not None else None
    if reference_indices is not None:
        reference_row, reference_column = reference_indices
        algebraic_row = reference_row - len(problem.state_eqs)
        algebraic_column = reference_column - len(problem.state_vars)
        if (0 <= algebraic_row < len(algebraic_eqs)
                and 0 <= algebraic_column < len(algebraic_vars)):
            reference_var = algebraic_vars[algebraic_column]
            if reference_var.uid not in fixed_uids:
                reference_value = float(problem.init_guess.get(reference_var.uid, 0.0))
                algebraic_eqs[algebraic_row] = reference_var - Const(reference_value)

    unknown_vars = state_unknown_vars + algebraic_unknown_vars
    residual_eqs = state_residual_eqs + algebraic_eqs
    if not unknown_vars:
        return None
    return unknown_vars, residual_eqs


def _build_constant_param_array(problem: Any) -> np.ndarray:
    """Build the constant-parameter vector used by compiled RMS expressions."""
    return np.asarray(
        [float(item.value) for item in problem.get_parameters_values()],
        dtype=np.float64,
    )


def _extract_unknown_vector(
        problem: Any,
        unknown_vars: List[Var],
        x: np.ndarray,
) -> np.ndarray:
    """Extract reduced unknown values from the complete RMS variable vector."""
    return np.asarray(
        [float(x[problem.uid2idx_vars[var.uid]]) for var in unknown_vars],
        dtype=np.float64,
    )


def _scatter_unknown_vector(
        problem: Any,
        unknown_vars: List[Var],
        x: np.ndarray,
        reduced_x: np.ndarray,
) -> None:
    """Scatter reduced unknown values into the complete RMS variable vector."""
    for idx, var in enumerate(unknown_vars):
        x[problem.uid2idx_vars[var.uid]] = float(reduced_x[idx])


def _max_abs_value(values: np.ndarray) -> float:
    """Return a dense vector's infinity norm."""
    return 0.0 if values.size == 0 else float(np.max(np.abs(values)))


def _solve_square_linear_system(
        matrix: sp.csc_matrix,
        rhs: np.ndarray,
) -> np.ndarray:
    """Solve a square Newton system with dense and sparse fallbacks."""
    if matrix.shape[0] <= 48:
        try:
            return np.linalg.solve(matrix.toarray(), rhs)
        except np.linalg.LinAlgError:
            return np.linalg.lstsq(matrix.toarray(), rhs, rcond=None)[0]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            return spla.spsolve(matrix, rhs)
    except Exception:
        return np.asarray(spla.lsqr(matrix, rhs)[0], dtype=np.float64)


def _solve_initialization_problem(
        problem: Any,
        unknown_vars: List[Var],
        residual_eqs: List[Expr],
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
) -> bool:
    """Compile and solve the RMS consistency equations."""
    residual_fn = SymbolicVector(
        eqs=residual_eqs,
        compiler_names_dict=problem.get_compiler_names_dict(),
        alias_names_dict=problem.get_alias_names_dict(),
        VARS_NAME=problem.VARS_NAME,
        DIFF_NAME=problem.DIFF_NAME,
        EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
        PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
    )
    jacobian_fn = SymbolicJacobian(
        eqs=residual_eqs,
        variables=unknown_vars,
        compiler_names_dict=problem.get_compiler_names_dict(),
        alias_names_dict=problem.get_alias_names_dict(),
        VARS_NAME=problem.VARS_NAME,
        DIFF_NAME=problem.DIFF_NAME,
        EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
        PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
    )
    reduced_x = _extract_unknown_vector(problem, unknown_vars, x)
    max_iter = max(1, int(problem.options.max_iter))
    tol = max(float(problem.options.tolerance), 1.0e-10)

    def residual(values: np.ndarray) -> np.ndarray:
        _scatter_unknown_vector(problem, unknown_vars, x, values)
        return residual_fn(x, dx, runtime_params, constant_params).copy()

    def jacobian(values: np.ndarray) -> sp.csc_matrix:
        residual(values)
        return jacobian_fn(
            x, dx, runtime_params, constant_params, 1.0
        ).tocsc(copy=True)

    # Use inexpensive damped Newton while the system is square.
    if len(residual_eqs) == len(unknown_vars):
        for _ in range(max_iter):
            current_residual = residual(reduced_x)
            residual_norm = _max_abs_value(current_residual)
            if residual_norm <= tol:
                return True
            delta = _solve_square_linear_system(
                jacobian(reduced_x), -current_residual
            )
            if not np.all(np.isfinite(delta)):
                break
            alpha = 1.0
            accepted = False
            while alpha >= 1.0e-4:
                trial_x = reduced_x + alpha * delta
                if _max_abs_value(residual(trial_x)) < residual_norm:
                    reduced_x = trial_x
                    accepted = True
                    break
                alpha *= 0.5
            if not accepted:
                break

    def finish_consistent(start_values: np.ndarray) -> Tuple[bool, np.ndarray]:
        least_squares_result = spo.least_squares(
            fun=residual,
            x0=start_values,
            jac=jacobian,
            x_scale="jac",
            ftol=min(tol * 0.01, 1.0e-12),
            xtol=min(tol * 0.01, 1.0e-12),
            gtol=min(tol * 0.01, 1.0e-12),
            max_nfev=max_iter * 50,
        )
        final_values = least_squares_result.x
        final_residual = residual(final_values)
        if (len(final_residual) == len(final_values)
                and _max_abs_value(final_residual) > tol):
            root_result = spo.root(
                fun=residual,
                x0=final_values,
                jac=lambda values: jacobian(values).toarray(),
                method="hybr",
                options={
                    "xtol": min(tol * 0.01, 1.0e-12),
                    "maxfev": max_iter * 50,
                },
            )
            if np.all(np.isfinite(root_result.x)):
                final_values = root_result.x
                final_residual = residual(final_values)
        converged = bool(
            np.all(np.isfinite(final_values))
            and _max_abs_value(final_residual) <= tol
        )
        return converged, final_values

    converged, final_values = finish_consistent(reduced_x)
    if converged:
        return True
    return False


def _apply_solution(problem: Any, x: np.ndarray) -> None:
    """Persist the complete solved RMS vector into the initial-guess map."""
    for var in list(problem.state_vars) + list(problem.algebraic_vars):
        problem.init_guess[var.uid] = float(x[problem.uid2idx_vars[var.uid]])


def run_rms_consistent_initialization(
        problem: RmsProblemDae,
        options: RmsOptions,
        logger: Logger | None,
) -> bool:
    """
    Run global RMS consistent initialization after explicit seeding.

    :param problem: RMS DAE problem whose initial operating point is solved.
    :param options: RMS simulation options controlling the initialization method.
    :param logger: Driver-owned logger available for initialization diagnostics.
    :return: ``True`` when the consistent initialization converges, otherwise ``False``.
    """
    if options.initialization_method not in {
        RmsInitializationMethod.ConsistentNewton,
        RmsInitializationMethod.Auto,
    }:
        raise ValueError(
            "run_rms_consistent_initialization requires ConsistentNewton or Auto"
        )

    payload = _collect_initialization_problem(
        problem=problem,
        fix_pf_bus_voltages=bool(options.init_fix_pf_bus_voltages),
    )
    if payload is None:
        return True

    unknown_vars, residual_eqs = payload
    x = problem.get_x0()
    converged = _solve_initialization_problem(
        problem=problem,
        unknown_vars=unknown_vars,
        residual_eqs=residual_eqs,
        x=x,
        dx=problem.get_dx0(),
        runtime_params=problem.get_eventparams0(),
        constant_params=_build_constant_param_array(problem),
    )
    if not converged:
        if options.initialization_method == RmsInitializationMethod.Auto:
            if logger is not None:
                logger.add_warning(
                    msg=(
                        "RMS consistent initialization did not converge; "
                        "Auto mode is continuing with the last initialization candidate."
                    ),
                    device_class="RMS",
                    device_property="initialization",
                    value=options.initialization_method,
                    expected_value=f"Residual <= {options.tolerance:g}",
                )
            else:
                pass
            _apply_solution(problem, x)
            return False
        else:
            error_message: str = (
                "RMS consistent initialization did not converge; "
                "simulation construction is stopping."
            )
            if logger is not None:
                logger.add_error(
                    msg=error_message,
                    device_class="RMS",
                    device_property="initialization",
                    value=options.initialization_method,
                    expected_value=f"Residual <= {options.tolerance:g}",
                )
            else:
                pass
            raise RuntimeError(error_message)
    else:
        pass
    _apply_solution(problem, x)
    return True
