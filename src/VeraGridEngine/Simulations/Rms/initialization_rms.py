# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Consistent steady-state initialization for RMS DAE problems."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple, Protocol
import warnings

import numpy as np
import scipy.optimize as spo
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.basic_structures import Vec, Logger
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian, SymbolicVector
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import SparseLinearSolverBackendProvider
from VeraGridEngine.Utils.NumericalMethods.sparse_lu_selection import solve_sparse_system_once
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import RmsInitializationMethod, VarPowerFlowReferenceType


class RmsInitializationProblem(Protocol):
    """Static view of an assembled RMS problem consumed by reduced Newton.

    Concrete problems retain ownership of their equations, UID mappings and
    numerical guesses. This protocol introduces no runtime model or dispatch.
    """

    __slots__ = ()

    options: RmsOptions
    grid: MultiCircuit | None
    sys_block: Block
    state_vars: List[Var]
    state_eqs: List[Expr]
    algebraic_vars: List[Var]
    algebraic_eqs: List[Expr]
    variable_parameters: List[Var]
    event_parameters_eqs: List[Expr | Const]
    event_parameters_eqs0: List[Expr | Const]
    uid2idx_vars: Dict[int, int]
    uid2idx_event_params: Dict[int, int]
    init_guess: Dict[int, float | int | complex | None]
    VARS_NAME: str
    DIFF_NAME: str
    VARIABLE_PARAMS_NAME: str
    CONSTANT_PARAMS_NAME: str

    def get_x0(self) -> np.ndarray:
        """Return startup variables in the assembled global UID order.

        :return: Dense real state and algebraic startup vector.
        """
        ...

    def get_dx0(self) -> np.ndarray:
        """Return the problem's existing startup derivative convention.

        :return: Dense real derivative vector in derivative UID order.
        """
        ...

    def get_eventparams0(self) -> np.ndarray:
        """Return the fixed initial event snapshot used by consistency.

        :return: Dense real parameter vector in global event UID order.
        """
        ...

    def get_parameters_values(self) -> List[Const]:
        """Return constants in the compiled parameter array order.

        :return: Existing ordered constant expressions.
        """
        ...

    def get_compiler_names_dict(self) -> Dict[int, str]:
        """Return UID bindings for the assembled numerical arrays.

        :return: Existing compiler UID mapping.
        """
        ...

    def get_alias_names_dict(self) -> Dict[int, str]:
        """Return the assembled readable aliases for compiled expressions.

        :return: Existing compiler alias mapping.
        """
        ...


    def get_states_number(self) -> int:
        """Locate algebraic coordinates after the fixed differential states.

        :return: Number of state coordinates preceding the algebraic variables.
        """
        ...

    def rhs_algebraic(self, x: Vec, dx: Vec, /) -> Vec:
        """Evaluate the original compiled algebraic rows at a fixed snapshot.

        :param x: Ordered state and algebraic values.
        :param dx: Ordered derivative values held fixed during projection.
        :return: Unscaled native algebraic residual vector.
        """
        ...

    def get_j22(self, x: Vec, dx: Vec, h: float, /) -> sp.csc_matrix:
        """Evaluate the compiled algebraic Jacobian for the native projection.

        :param x: Ordered state and algebraic values.
        :param dx: Ordered derivative values held fixed during projection.
        :param h: Native Jacobian time-step argument; projection uses one.
        :return: Jacobian of algebraic residuals with respect to algebraic values.
        """
        ...

    def get_small_signal_reference_indices(self) -> tuple[int, int] | None:
        """Identify the existing electrical angle gauge when one is declared.

        :return: Augmented-Jacobian reference row and global variable column,
            or ``None`` when the problem has no explicit gauge coordinate.
        """
        ...


def solve_rms_newton_correction(
        jacobian: sp.csc_matrix,
        residual: Vec,
        reference_column: int | None,
        sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None = None,
) -> Vec:
    """Solve one RMS Newton system while fixing an explicit gauge coordinate.

    AC RMS systems can retain one global voltage-angle coordinate while exposing
    one fewer independent residual. Appending a zero-correction constraint for
    the recorded reference angle makes that Newton system square without
    discarding any physical equation or moving the accepted reference frame.

    :param jacobian: Newton Jacobian for the current residual vector.
    :param residual: Residual vector whose correction is required.
    :param reference_column: Optional Jacobian column of the fixed gauge value.
    :param sparse_solver_backend_provider: Sparse LU provider for the direct
        solves; None keeps SciPy spsolve.
    :return: Finite direct correction when the system is square or has one known
        gauge coordinate; otherwise the minimum-norm least-squares correction.
    """
    row_count: int = int(jacobian.shape[0])
    column_count: int = int(jacobian.shape[1])
    correction: Vec

    if row_count == column_count:
        correction = solve_sparse_system_once(jacobian, -residual, sparse_solver_backend_provider)
    else:
        has_single_reference_coordinate: bool = (
            row_count + 1 == column_count
            and reference_column is not None
            and 0 <= reference_column < column_count
        )
        if has_single_reference_coordinate:
            reference_row: sp.csc_matrix = sp.csc_matrix(
                (
                    np.ones(1, dtype=float),
                    (
                        np.zeros(1, dtype=int),
                        np.array([reference_column], dtype=int),
                    ),
                ),
                shape=(1, column_count),
            )
            augmented_jacobian: sp.csc_matrix = sp.vstack(
                (jacobian, reference_row),
                format="csc",
            )
            augmented_residual: Vec = np.concatenate(
                (residual, np.zeros(1, dtype=float))
            )
            # Native controller equations mix gains, per-unit network balances,
            # and time identities over several orders of magnitude. Symmetric
            # row/column equilibration keeps the reference-augmented solve from
            # losing the small time and controller residuals to pivot scaling.
            row_magnitudes: Vec = np.asarray(
                np.abs(augmented_jacobian).max(axis=1).toarray()
            ).ravel()
            row_magnitudes[row_magnitudes < 1.0e-14] = 1.0
            row_scaling: Vec = 1.0 / row_magnitudes
            row_scaled_jacobian: sp.csc_matrix = (
                sp.diags(row_scaling, format="csc") @ augmented_jacobian
            ).tocsc()
            column_magnitudes: Vec = np.asarray(
                np.abs(row_scaled_jacobian).max(axis=0).toarray()
            ).ravel()
            column_magnitudes[column_magnitudes < 1.0e-14] = 1.0
            column_scaling: Vec = 1.0 / column_magnitudes
            equilibrated_jacobian: sp.csc_matrix = (
                row_scaled_jacobian @ sp.diags(column_scaling, format="csc")
            ).tocsc()
            equilibrated_residual: Vec = augmented_residual * row_scaling

            equilibrated_correction: Vec = solve_sparse_system_once(
                equilibrated_jacobian,
                -equilibrated_residual,
                sparse_solver_backend_provider,
            )
            correction = column_scaling * equilibrated_correction
        else:
            correction = sp.linalg.lsqr(jacobian, -residual)[0]

    return correction


def project_initial_algebraic_state(
        problem: RmsInitializationProblem,
        initial_values: Vec,
        differential_values: Vec,
        tolerance: float,
        max_iter: int,
) -> Tuple[Vec, bool, float]:
    """Project an RMS initial vector onto its algebraic constraint manifold.

    Explicit ``inc(...)`` equations seed controller states, while the remaining
    algebraic variables still need a zero-time network solve. Performing that
    solve before the first accepted sample prevents an artificial algebraic
    jump from entering derivative history on the second integration step.

    :param problem: Compiled RMS problem that owns the algebraic residual.
    :param initial_values: Explicitly seeded state and algebraic vector.
    :param differential_values: Initial differential-variable values.
    :param tolerance: Required infinity norm of the algebraic residual.
    :param max_iter: Maximum Newton projection iterations.
    :return: Projected vector, convergence flag, and final residual norm.
    """
    projected_values: Vec = initial_values.copy()
    algebraic_offset: int = problem.get_states_number()
    residual: Vec = problem.rhs_algebraic(projected_values, differential_values)

    if residual.size == 0:
        return projected_values, True, 0.0
    else:
        pass

    residual_inf: float = float(np.linalg.norm(residual, np.inf))
    iteration: int = 0

    while residual_inf > tolerance and iteration < max_iter:
        jacobian: sp.csc_matrix = problem.get_j22(
            projected_values,
            differential_values,
            1.0,
        ).tocsc()
        reference_indices: tuple[int, int] | None = (
            problem.get_small_signal_reference_indices()
        )
        algebraic_reference_column: int | None
        if reference_indices is not None:
            algebraic_reference_column = reference_indices[1] - algebraic_offset
        else:
            algebraic_reference_column = None
        delta: Vec = solve_rms_newton_correction(
            jacobian=jacobian,
            residual=residual,
            reference_column=algebraic_reference_column,
        )

        if np.all(np.isfinite(delta)):
            pass
        else:
            delta = sp.linalg.lsqr(jacobian, -residual)[0]

        if np.all(np.isfinite(delta)):
            pass
        else:
            return projected_values, False, residual_inf

        step_scale: float = 1.0
        accepted: bool = False
        while step_scale >= 1.0e-4 and not accepted:
            trial_values: Vec = projected_values.copy()
            trial_values[algebraic_offset:] += step_scale * delta
            trial_residual: Vec = problem.rhs_algebraic(
                trial_values,
                differential_values,
            )
            trial_residual_inf: float = float(
                np.linalg.norm(trial_residual, np.inf)
            )
            if np.isfinite(trial_residual_inf) and trial_residual_inf < residual_inf:
                projected_values = trial_values
                residual = trial_residual
                residual_inf = trial_residual_inf
                accepted = True
            else:
                step_scale *= 0.5

        if accepted:
            iteration += 1
        else:
            return projected_values, False, residual_inf

    converged: bool = bool(np.isfinite(residual_inf) and residual_inf <= tolerance)
    return projected_values, converged, residual_inf


def _build_state_equation_lookup(problem: Any) -> Dict[int, Expr]:
    """Map each RMS state UID to its differential right-hand side."""
    return {
        state_var.uid: state_eq
        for state_var, state_eq in zip(problem.state_vars, problem.state_eqs)
    }


def _collect_fixed_pf_bus_voltage_uids(problem: RmsInitializationProblem) -> Set[int]:
    """Select declared algebraic voltage coordinates without freezing nodal power.

    :param problem: Native problem that owns canonical bus models and PF seeds.
    :return: Algebraic bus-voltage UIDs eligible for the existing fixed-PF option.
    """
    fixed_uids: Set[int] = set()
    grid: MultiCircuit | None = problem.grid
    bus: Bus
    bus_model: Block | None
    bus_var: Var
    voltage_references: tuple[VarPowerFlowReferenceType, ...] = (
        VarPowerFlowReferenceType.Vm, VarPowerFlowReferenceType.Va,
        VarPowerFlowReferenceType.Vr, VarPowerFlowReferenceType.Vi,
        VarPowerFlowReferenceType.Vdc,
    )
    if grid is None:
        pass
    else:
        for bus in grid.buses:
            bus_model = bus.rms_model
            if bus_model is None:
                pass
            else:
                for bus_var in bus_model.algebraic_vars:
                    # A capacitive DC bus owns algebraic P, which must remain solvable.
                    if bus_var.ref in voltage_references:
                        fixed_uids.add(bus_var.uid)
                    else:
                        pass
    return fixed_uids


def _collect_initialization_problem(
        problem: Any,
        fix_pf_bus_voltages: bool,
) -> Tuple[List[Var], List[Expr], np.ndarray] | None:
    """Collect unresolved states, free algebraics, and consistency residuals."""
    state_eq_lookup = _build_state_equation_lookup(problem)
    init_eq_lookup: Dict[Var, Expr] = problem.sys_block.init_eqs
    state_unknown_vars: List[Var] = []
    state_residual_eqs: List[Expr] = []
    state_equilibrium_flags: List[float] = []

    for state_var in problem.state_vars:
        if state_var.uid in problem.init_guess:
            continue
        state_unknown_vars.append(state_var)
        if state_var in init_eq_lookup:
            state_residual_eqs.append(state_var - init_eq_lookup[state_var])
            state_equilibrium_flags.append(0.0)
        elif state_var.uid in state_eq_lookup:
            state_residual_eqs.append(state_eq_lookup[state_var.uid])
            state_equilibrium_flags.append(1.0)
        else:
            state_residual_eqs.append(state_var)
            state_equilibrium_flags.append(0.0)

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

    # Fixed seeded states can already anchor the physical voltage frame.
    # Keep every original power balance row in the reduced initialization system.
    unknown_vars = state_unknown_vars + algebraic_unknown_vars
    residual_eqs = state_residual_eqs + algebraic_eqs
    state_equilibrium_mask = np.asarray(
        state_equilibrium_flags + [0.0] * len(algebraic_unknown_vars),
        dtype=np.float64,
    )
    if not unknown_vars:
        return None
    return unknown_vars, residual_eqs, state_equilibrium_mask


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


def _solve_equilibrated_linear_system(
        matrix: sp.csc_matrix,
        rhs: np.ndarray,
) -> np.ndarray:
    """Solve a square system after row and column equilibration."""
    squared = matrix.multiply(matrix)
    row_scale = np.maximum(
        np.sqrt(np.asarray(squared.sum(axis=1)).ravel()),
        1.0e-12,
    )
    row_scaled = (sp.diags(1.0 / row_scale, format="csc") @ matrix).tocsc()
    column_scale = np.maximum(
        np.sqrt(np.asarray(row_scaled.multiply(row_scaled).sum(axis=0)).ravel()),
        1.0e-12,
    )
    equilibrated = (
        row_scaled @ sp.diags(1.0 / column_scale, format="csc")
    ).tocsc()
    scaled_step = _solve_square_linear_system(equilibrated, rhs / row_scale)
    return scaled_step / column_scale


def _solve_initialization_problem(
        problem: Any,
        unknown_vars: List[Var],
        residual_eqs: List[Expr],
        state_equilibrium_mask: np.ndarray,
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
    seed_reduced_x = reduced_x.copy()
    max_iter = max(1, int(problem.options.max_iter))
    tol: float = float(problem.options.tolerance)
    optimizer_tolerance: float = max(min(tol * 0.01, 1.0e-12), 10.0 * np.finfo(np.float64).eps)

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
            if np.all(np.isfinite(reduced_x)) and np.all(np.isfinite(current_residual)) and residual_norm <= tol:
                return True
            else:
                pass
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
        start_residual: np.ndarray = residual(start_values)
        if np.all(np.isfinite(start_values)) and np.all(np.isfinite(start_residual)):
            pass
        else:
            return False, start_values
        try:
            least_squares_result = spo.least_squares(
                fun=residual,
                x0=start_values,
                jac=jacobian,
                x_scale="jac",
                ftol=optimizer_tolerance,
                xtol=optimizer_tolerance,
                gtol=optimizer_tolerance,
                max_nfev=max_iter * 50,
            )
        except IndexError:
            # Installed sparse TRF has a one-variable subspace edge; fail without installing a trial.
            if start_values.size == 1:
                return False, start_values
            else:
                raise
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
            and np.all(np.isfinite(final_residual))
            and _max_abs_value(final_residual) <= tol
        )
        return converged, final_values

    converged, final_values = finish_consistent(reduced_x)
    if converged:
        return True
    if (problem.options.initialization_method == RmsInitializationMethod.Auto
            and len(residual_eqs) == len(unknown_vars)
            and np.any(state_equilibrium_mask > 0.5)):
        # Direct PTC uses F=[-f,g]. Only state rows sourced from equilibrium
        # equations receive the sign change and residual-scaled pseudo mass.
        row_sign = 1.0 - 2.0 * state_equilibrium_mask
        reduced_x = seed_reduced_x.copy()
        dtau = 1.0
        dtau_min = 1.0e-8
        dtau_max = 1.0e6
        for _ in range(max_iter * 4):
            steady_residual = residual(reduced_x)
            ptc_residual = row_sign * steady_residual
            residual_norm = _max_abs_value(ptc_residual)
            if residual_norm <= tol:
                return True

            ptc_jacobian = (
                sp.diags(row_sign, format="csc") @ jacobian(reduced_x)
            ).tocsc()
            mass_diagonal = (
                state_equilibrium_mask * (0.01 + np.abs(ptc_residual)) / dtau
            )
            linear_matrix = (
                ptc_jacobian + sp.diags(mass_diagonal, format="csc")
            ).tocsc()
            delta = _solve_equilibrated_linear_system(
                linear_matrix,
                -ptc_residual,
            )
            if not np.all(np.isfinite(delta)):
                dtau = max(dtau_min, 0.5 * dtau)
                continue

            best_values: np.ndarray | None = None
            best_norm = np.inf
            for scale in (1.0, 0.5, 0.25, 0.125):
                trial_values = reduced_x + scale * delta
                trial_norm = _max_abs_value(row_sign * residual(trial_values))
                if np.isfinite(trial_norm) and trial_norm < best_norm:
                    best_values = trial_values
                    best_norm = trial_norm
            if best_values is None:
                dtau = max(dtau_min, 0.5 * dtau)
                continue

            beta = float(np.clip(
                max(residual_norm, 1.0e-30) / max(best_norm, 1.0e-30),
                0.5,
                5.0,
            ))
            reduced_x = best_values
            dtau = float(np.clip(dtau * beta, dtau_min, dtau_max))

        converged, final_values = finish_consistent(reduced_x)
        if converged:
            return True
    return False


def _apply_solution(problem: Any, x: np.ndarray) -> None:
    """Persist the complete solved RMS vector into the initial-guess map."""
    for var in list(problem.state_vars) + list(problem.algebraic_vars):
        problem.init_guess[var.uid] = float(x[problem.uid2idx_vars[var.uid]])


def run_rms_consistent_initialization(
        problem: RmsInitializationProblem,
        options: RmsOptions,
        logger: Logger | None = None,
) -> bool:
    """Accept RMS consistency only against the original finite prepared snapshot.

    Seeded differential coordinates remain fixed. Missing-state equations retain
    the existing reduced initialization target; this is not a universal f=0 claim.
    The gauge-conditioned solve cannot replace acceptance of original nodal rows.

    :param problem: Assembled native problem after its startup parameter replay.
    :param options: Selected ConsistentNewton/Auto/PTC mode and required tolerance.
        PTC retains its existing PF anchors and finite seeded states.
    :param logger: Optional caller-owned diagnostics for rejected initialization.
    :return: True for a finite accepted candidate; False for Auto failure without writeback.
    :raises RuntimeError: If strict consistency or initial finiteness fails.
    :raises ValueError: If the selected method is unsupported.
    """
    if options.initialization_method not in (
            RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.Auto,
            RmsInitializationMethod.PseudoTransient):
        raise ValueError("run_rms_consistent_initialization requires ConsistentNewton, Auto or PseudoTransient")
    else:
        pass

    if np.isfinite(options.tolerance) and options.tolerance > 0.0:
        pass
    else:
        raise ValueError("RMS consistent initialization requires a finite positive tolerance")

    # Isolate numerical working arrays without replaying any parameter expression.
    x: np.ndarray = problem.get_x0().copy()
    dx: np.ndarray = problem.get_dx0().copy()
    runtime_params: np.ndarray = problem.get_eventparams0().copy()
    constant_params: np.ndarray = _build_constant_param_array(problem)
    finite_snapshot: bool = bool(
        np.all(np.isfinite(x)) and np.all(np.isfinite(dx))
        and np.all(np.isfinite(runtime_params)) and np.all(np.isfinite(constant_params)))
    if finite_snapshot:
        pass
    elif options.initialization_method == RmsInitializationMethod.Auto:
        return False
    else:
        raise RuntimeError("RMS consistent initialization requires finite initial values")

    # PTC already freezes PF anchors while solving device copies. Global
    # acceptance must preserve those anchors and seeded differential states;
    # the existing collector still owns which algebraic coordinates are voltage.
    fix_pf_bus_voltages: bool = (
        options.initialization_method == RmsInitializationMethod.PseudoTransient
        or bool(options.init_fix_pf_bus_voltages))
    payload: Tuple[List[Var], List[Expr], np.ndarray] | None = _collect_initialization_problem(
        problem=problem, fix_pf_bus_voltages=fix_pf_bus_voltages)
    converged: bool
    if payload is None:
        converged = True
    else:
        unknown_vars: List[Var]
        residual_eqs: List[Expr]
        unknown_vars, residual_eqs, state_equilibrium_mask = payload
        converged = _solve_initialization_problem(
            problem=problem, unknown_vars=unknown_vars, residual_eqs=residual_eqs,
            state_equilibrium_mask=state_equilibrium_mask, x=x, dx=dx, runtime_params=runtime_params, constant_params=constant_params)

    # The caller has prepared this exact runtime snapshot and assembled full-g evaluator.
    # Reuse its original rows after the gauge-conditioned solve; do not compile a second copy.
    original_residual: np.ndarray = problem.rhs_algebraic(x, dx).copy()
    original_residual_norm: float = _max_abs_value(original_residual)
    accepted: bool = bool(
        converged and np.all(np.isfinite(x)) and np.all(np.isfinite(original_residual))
        and original_residual_norm <= options.tolerance)
    if accepted:
        _apply_solution(problem, x)
        return True
    elif options.initialization_method == RmsInitializationMethod.Auto:
        # Keep the prepared state on rejection; report the retained upstream diagnostic.
        if logger is None:
            pass
        else:
            logger.add_warning(
                msg=("RMS consistent initialization did not converge; "
                     "Auto mode is continuing with the prepared initialization state."),
                device_class="RMS",
                device_property="initialization",
                value=options.initialization_method,
                expected_value=f"Residual <= {options.tolerance:g}",
            )
        return False
    else:
        error_message: str = (
            "RMS consistent Newton initialization did not converge; "
            "simulation construction is stopping."
        )
        if logger is None:
            pass
        else:
            logger.add_error(
                msg=error_message,
                device_class="RMS",
                device_property="initialization",
                value=options.initialization_method,
                expected_value=f"Residual <= {options.tolerance:g}",
            )
        raise RuntimeError(error_message)
