# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import numba as nb
import scipy.linalg as la
import scipy.sparse.linalg as spla
import math
import time
import scipy.sparse as sp

from typing import Union, Any

from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_results import SmallSignalStabilityRmsResults
from VeraGridEngine.enumerations import EngineType, SimulationTypes
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.basic_structures import Vec, Mat
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae, RmsProblemTemplate
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import SparseLinearSolverBackendProvider
from VeraGridEngine.Utils.NumericalMethods.sparse_lu_selection import resolve_sparse_lu_provider


def compute_state_matrix(problem: RmsProblemTemplate, x: Vec, dx: Vec) -> tuple[Mat, Mat]:
    """
    Small Signal Stability analysis state matrix computation.
    Handles rank-deficient (singular) Jacobian matrices using SVD-based pseudo-inverse.
    :param problem: RmsProblemTemplate
    :param x: Vec. Variables value at assessment time
    :param dx: Vec. Derivatives value at assessment time
    :return
    """
    h = problem.get_dt_value()
    # h = 0.001
    fx: sp.csc_matrix = problem.get_j11(x, dx, h).tocsc()  # ∂f/∂x
    fy: sp.csc_matrix = problem.get_j12(x, dx, h).tocsc()  # ∂f/∂y
    gx: sp.csc_matrix = problem.get_j21(x, dx, h).tocsc()  # ∂g/∂x
    gy: sp.csc_matrix = problem.get_j22(x, dx, h).tocsc()  # ∂g/∂y

    # Convert to dense for SVD-based solve (handles singular matrices)

    differential_vars = problem.get_diff_var_number()
    if differential_vars == 0:
        try:
            gy_lu: spla.SuperLU = spla.splu(gy)
        except RuntimeError as factorization_error:
            reference_indices: tuple[int, int] | None = problem.get_small_signal_reference_indices()
            if reference_indices is not None:
                reference_row: int
                reference_column: int
                reference_row, reference_column = reference_indices
                number_of_states: int = problem.get_states_number()
                algebraic_row: int = reference_row - number_of_states
                algebraic_column: int = reference_column - number_of_states

                if (0 <= algebraic_row < gy.shape[0]
                        and 0 <= algebraic_column < gy.shape[1]):
                    # Replace the redundant slack active-power row by the
                    # voltage-angle reference only after the original algebraic
                    # factorization has proved exactly singular.
                    constrained_gy: sp.lil_matrix = gy.tolil(copy=True)
                    constrained_gx: sp.lil_matrix = gx.tolil(copy=True)
                    constrained_gy.rows[algebraic_row] = [algebraic_column]
                    constrained_gy.data[algebraic_row] = [1.0]
                    constrained_gx.rows[algebraic_row] = list()
                    constrained_gx.data[algebraic_row] = list()
                    gy = constrained_gy.tocsc()
                    gx = constrained_gx.tocsc()
                    try:
                        gy_lu = spla.splu(gy)
                    except RuntimeError as constrained_factorization_error:
                        raise RuntimeError(
                            "The algebraic Jacobian remains singular after fixing the voltage-angle reference. "
                            "The dense all-modes reduction is not valid for this RMS model. "
                            "Select a positive number of modes to use the sparse DAE eigensolver."
                        ) from constrained_factorization_error
                else:
                    raise RuntimeError("Invalid RMS small-signal angle-reference indices") from factorization_error
            else:
                raise RuntimeError(
                    "The algebraic Jacobian is singular and the RMS problem has no voltage-angle reference. "
                    "The dense all-modes reduction cannot be constructed."
                ) from factorization_error

        gy_inv_gx = gy_lu.solve(gx.toarray())
    else:
        # Badly conditioned or singular: use SVD-based pseudo-inverse
        # Regularize small singular values for numerical stability    gy_dense = gy.toarray()
        gx_dense = gx.toarray()
        gy_dense = gy.toarray()
        tol = 1e-10
        U, s, Vh = la.svd(gy_dense, full_matrices=False)
        s_reg = np.where(s > tol, s, 0.0)
        s_inv = np.where(s_reg > 0, 1.0 / s_reg, 0.0)

        # Compute pseudo-inverse: gy^+ = V @ diag(s_inv) @ U^T
        gy_pinv = Vh.T @ np.diag(s_inv) @ U.T
        gy_inv_gx = gy_pinv @ gx_dense

    A = fx.toarray() - fy.toarray() @ gy_inv_gx

    A_bal, scale_factors = la.matrix_balance(A=A, separate=False)

    return A_bal, A


@nb.jit(cache=True)
def compute_participation_factors(v: np.ndarray,
                                  w: np.ndarray) -> np.ndarray:
    """
    Calculates normalized participation factors correctly for both dense and sparse.
    Compatible with strict Numba (without keep dims).
    :param v: right eigenvectors (columns) - should be complex128
    :param w: left eigenvectors (columns) - should be complex128
    :return PF_norm: Return normalized participation factors
    """
    n_rows = v.shape[0]
    k = v.shape[1]

    for i in range(k):
        norm_factor = 0j
        for j in range(n_rows):
            norm_factor += w[j, i] * v[j, i]

        if np.abs(norm_factor) > 1e-15:
            for j in range(n_rows):
                w[j, i] = w[j, i] / norm_factor
        else:
            pass

    PF = np.empty_like(v, dtype=np.float64)
    for i in range(k):
        for j in range(n_rows):
            PF[j, i] = np.abs(w[j, i] * v[j, i])

    PF_norm = np.empty_like(PF)
    for i in range(k):
        col_sum = np.sum(PF[:, i])
        if col_sum > 1e-15:
            for j in range(n_rows):
                PF_norm[j, i] = PF[j, i] / col_sum
        else:
            for j in range(n_rows):
                PF_norm[j, i] = PF[j, i]

    return PF_norm


def compute_participation_factors_generalized(v: np.ndarray,
                                              w: np.ndarray,
                                              E: Union[np.ndarray, sp.spmatrix]) -> np.ndarray:
    """
    Participation factors for generalized eigenproblems A x = lambda E x.

    Assumes:
    - v[:, i] is the right eigenvector of mode i.
    - w[:, i] is the corresponding left eigenvector of mode i.
    - left/right eigenvectors are ordered consistently.
    - finite, well-separated eigenvalues are being analysed.

    Uses the normalization:

        w_i^T E v_i = 1

    and computes ``p_ki = |v_ki (w_i^T E)_k|``.

    The returned participation factors are column-normalized.
    """
    v_c = v.astype(np.complex128, copy=False)
    w_c = w.astype(np.complex128, copy=False).copy()

    k = v_c.shape[1]

    if sp.issparse(E):
        Ev = E @ v_c
    else:
        E_arr = np.asarray(E, dtype=np.complex128)
        Ev = E_arr @ v_c

    for i in range(k):
        norm_factor = w_c[:, i] @ Ev[:, i]

        if np.abs(norm_factor) > 1e-15:
            w_c[:, i] /= norm_factor
        else:
            pass

    if sp.issparse(E):
        Etw = E.T @ w_c
    else:
        Etw = E_arr.T @ w_c

    PF = np.abs(v_c * Etw)

    col_sum = np.sum(PF, axis=0)
    PF_norm = PF.copy()

    valid = col_sum > 1e-15
    PF_norm[:, valid] /= col_sum[valid]

    return PF_norm.astype(np.float64, copy=False)

def select_eigs_without_conjugates(eigenvalues: Vec) -> Vec:
    """
    Select oscillatory modes. Conjugate modes appear only once in the selection.
    :param eigenvalues: row np array with modes
    :return: row np array with only the positive complex conjugate modes
    """
    eig_list: list = list()
    seen: set = set()
    tol: float = 1e-12

    for z in eigenvalues:
        if np.isreal(z):
            seen.add(z)
        elif z.imag > tol:
            if z not in seen and np.conj(z) not in seen:
                seen.add(z)
                eig_list.append(z)
            else:
                pass
        else:
            pass
    return np.array(eig_list)


@nb.jit(cache=True)
def compute_damping_ratios_and_frequencies(eigenvalues: Vec,
                                           eig_no_conjugates: Vec) -> tuple[Vec, Vec]:
    """
    :param eigenvalues: row np array with modes
    :param eig_no_conjugates: row np array with only the positive complex conjugate modes
    :return: damping_ratios: list with damping ratios for the positive complex conjugate modes. Nan for other modes
    :return: conjugate_frequencies: list with oscillation frequencies for the positive complex conjugate modes. Nan for other modes
    """
    damping_ratios = np.full(eigenvalues.shape[0], np.nan, dtype=np.float64)
    conjugate_frequencies = np.full(eigenvalues.shape[0], np.nan, dtype=np.float64)
    tol = 1e-12
    match_tol = 1e-8

    for i in range(eigenvalues.shape[0]):
        mode = eigenvalues[i]
        found = False
        for j in range(eig_no_conjugates.shape[0]):
            if np.abs(mode - eig_no_conjugates[j]) <= match_tol:
                found = True
                break
            else:
                pass
        if found:
            re = mode.real
            im = mode.imag
            conjugate_frequencies[i] = im / (2.0 * np.pi)
            modz = np.abs(mode)
            if modz < tol:
                damping_ratios[i] = 0.0
            else:
                damping_ratios[i] = -re / modz
        else:
            damping_ratios[i] = np.nan
            conjugate_frequencies[i] = np.nan

    return damping_ratios, conjugate_frequencies




def run_dense_small_signal_stability(problem: RmsProblemTemplate,
                                     x: Vec,
                                     dx: Vec,
                                     verbose: int = 0) -> tuple[Vec, Vec, Mat, Vec, Vec, Mat, None]:
    """
    Run small signal stability analysis using dense matrices calculations. The operation returns all the eigenvalues.
    :param problem: RmsProblemTemplate
    :param x: Vec. Variables value at assessment time
    :param dx: Vec. Derivatives value at assessment time
    :param verbose: verbosity
    :return eigenvalues: Vec. Modes
    :return participation_factors: Mat. Normalized participation factors
    :return damping_ratios: Vec. Damping ratios of oscillatory modes.
    :return conjugate_freq: Vec. Frequency of oscillatory modes.
    :return A_orig: Mat. Original state matrix
    """

    # We obtain the balanced matrix

    differential_vars = problem.get_diff_var_number()
    if differential_vars == 0:
        # Scipy returns w such that w^TA = lambda w^H. We must conjugate it to W^TA = lambda W^T.
        A_bal, A_orig = compute_state_matrix(problem=problem, x=x, dx=dx)
        A_bal += sp.eye(A_bal.shape[0]) * 1e-10
        eig_results = list(la.eig(A_bal, left=True, right=True))
    else:
        E_raw = problem.get_E_matrix(x, dx)
        E_matrix = E_raw.toarray() if sp.issparse(E_raw) else np.asarray(E_raw, dtype=float)
        A_raw = problem.get_static_state_matrix(x, dx)
        A_dense = A_raw.toarray() if sp.issparse(A_raw) else np.asarray(A_raw, dtype=float)
        A_dense += np.eye(A_dense.shape[0]) * 1e-7
        A_orig = A_dense.copy()
        # Convert to dense for eig
        eig_results = list(la.eig(A_dense, -E_matrix, left=True, right=True))

    eigenvalues = eig_results[0]
    w_raw = eig_results[1]
    v = eig_results[2]

    w = w_raw.conj()

    # Ensure eigenvectors are complex (scipy may return float64 for real eigenvalues)
    v = v.astype(np.complex128, copy=False)
    w = w.astype(np.complex128, copy=False)

    if differential_vars == 0:
        participation_factors = compute_participation_factors(v=v, w=w)
    else:
        participation_factors = compute_participation_factors_generalized(v=v, w=w, E=E_matrix)

    eig_no_conjugates = select_eigs_without_conjugates(eigenvalues)
    damping_ratios, conjugate_freq = compute_damping_ratios_and_frequencies(eigenvalues, eig_no_conjugates)

    if verbose:
        print("Eigenvalues:", eigenvalues)
        print("Participation Factors:", participation_factors)

    return eigenvalues,v, participation_factors, damping_ratios, conjugate_freq, A_orig, None


def run_sparse_small_signal_stability(problem: RmsProblemTemplate,
                                      x: Vec,
                                      dx: Vec,
                                      k: int,
                                      verbose: int = 0) -> tuple[Vec, Vec, Mat, Vec, Vec, Mat, None]:
    """
    Run small signal stability analysis using sparse matrices calculations. The operation returns k eigenvalues.
    :param problem: RmsProblemTemplate
    :param x: Vec. Variables value at assessment time
    :param dx: Vec. Derivatives value at assessment time
    :param k: int. Number of modes to be calculated. k max = N-2
    :param verbose: verbosity
    :return eigenvalues: Vec. Modes
    :return participation_factors: Mat. Normalized participation factors
    :return damping_ratios: Vec. Damping ratios of oscillatory modes.
    :return conjugate_freq: Vec. Frequency of oscillatory modes.
    :return A_orig: Mat. Original state matrix
    """

    t0: float = time.perf_counter()
    A_static = problem.get_static_state_matrix(x, dx)
    J_aug = A_static.tocsc() if sp.issparse(A_static) else sp.csc_matrix(np.asarray(A_static, dtype=float))
    reference_indices: tuple[int, int] | None = problem.get_small_signal_reference_indices()
    if reference_indices is not None:
        reference_row: int
        reference_column: int
        reference_row, reference_column = reference_indices

        # Replace only the redundant slack active-power row in the numerical
        # eigenproblem.  The physical RMS DAE still retains its original nodal
        # balance equation; this operation merely selects one angular gauge for
        # a factorization that would otherwise be exactly singular.
        reference_jacobian: sp.lil_matrix = J_aug.tolil(copy=True)
        reference_jacobian.rows[reference_row] = [reference_column]
        reference_jacobian.data[reference_row] = [1.0]
        J_aug = reference_jacobian.tocsc()
    else:
        pass
    differential_vars = problem.get_diff_var_number()
    n_states: int = problem.get_states_number()
    E = None

    if differential_vars == 0:
        # In small systems, k_search cannot exceed the dimension of the operator.
        k_search = min(k + 6, n_states - 2)
        if k_search <= 0:
            k_search = k
        else:
            pass

        # A zero mode makes direct factorization of J_aug singular.  Shift only
        # the differential-state block, matching the generalized sparse path,
        # and recover the original eigenvalues after inverse iteration.
        shift_diagonal: Vec = np.zeros(J_aug.shape[0], dtype=float)
        shift_diagonal[:n_states] = 1.0
        state_shift_matrix: sp.csc_matrix = sp.diags(shift_diagonal, format="csc")
        full_shift_matrix: sp.csc_matrix = sp.eye(J_aug.shape[0], format="csc")
        descriptor_sigmas: tuple[float, ...] = (0.0, 1.0e-8, 1.0e-7, 1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3)
        regularization_sigmas: tuple[float, ...] = (1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1)
        shift_strategies: list[tuple[str, sp.csc_matrix, tuple[float, ...]]] = list()
        shift_strategies.append(("descriptor", state_shift_matrix, descriptor_sigmas))
        shift_strategies.append(("full regularization", full_shift_matrix, regularization_sigmas))
        eig_ok: bool = False
        last_error: RuntimeError | ValueError | spla.ArpackNoConvergence | None = None

        for shift_name, shift_matrix, sigma_candidates in shift_strategies:
            for sigma in sigma_candidates:
                try:
                    J_shift: sp.csc_matrix = (J_aug - sigma * shift_matrix).tocsc()
                    J_shift_lu: Any = spla.splu(J_shift)

                    op_methods: SparseShiftAndInvertMethods = SparseShiftAndInvertMethods(
                        n_states=n_states,
                        total_size=J_shift.shape[0],
                        J_aug_lu=J_shift_lu,
                    )
                    inv_a_op: spla.LinearOperator = spla.LinearOperator(
                        shape=(n_states, n_states),
                        matvec=op_methods.matvec,
                        rmatvec=op_methods.rmatvec,
                        dtype=np.complex128,
                    )

                    mu_R, v_raw = spla.eigs(inv_a_op, k=k_search, which="LM", tol=1e-10)
                    mu_L, w_raw = spla.eigs(inv_a_op.T, k=k_search, which="LM", tol=1e-10)

                    # Filter algebraic noise: mu -> 0 represents lambda -> infinity.
                    tol_mu: float = 1.0e-8
                    valid_mask_R: np.ndarray = np.isfinite(mu_R) & (np.abs(mu_R) > tol_mu)
                    valid_mask_L: np.ndarray = np.isfinite(mu_L) & (np.abs(mu_L) > tol_mu)
                    mu_R_valid: Vec = mu_R[valid_mask_R]
                    mu_L_valid: Vec = mu_L[valid_mask_L]
                    v_valid = v_raw[:, valid_mask_R]
                    w_valid = w_raw[:, valid_mask_L]
                    eigenvalues_R = sigma + 1.0 / mu_R_valid
                    eigenvalues_L = sigma + 1.0 / mu_L_valid

                    if (eigenvalues_R.size == 0
                            or eigenvalues_L.size == 0
                            or not np.all(np.isfinite(eigenvalues_R))
                            or not np.all(np.isfinite(eigenvalues_L))
                            or v_valid.shape[1] == 0
                            or w_valid.shape[1] == 0):
                        raise ValueError("ARPACK returned empty or non-finite standard eigenvalues")
                    else:
                        pass

                    eig_ok = True
                    if verbose:
                        print(f"Sparse standard {shift_name} shift-invert converged with sigma={sigma:.1e}")
                    else:
                        pass
                    break
                except (RuntimeError, ValueError, spla.ArpackNoConvergence) as error:
                    last_error = error
                    if verbose:
                        print(f"Sparse standard {shift_name} shift-invert failed "
                              f"with sigma={sigma:.1e}: {error}")
                    else:
                        pass

            if eig_ok:
                break
            else:
                pass

        if eig_ok:
            pass
        else:
            raise RuntimeError(f"Sparse standard eigensolver failed with all sigma candidates: {last_error}")
    else:
        # Sparse generalized shift-invert using custom LinearOperator.
        E_raw = problem.get_E_matrix(x, dx)
        E = E_raw.tocsc() if sp.issparse(E_raw) else sp.csc_matrix(E_raw)
        # Keep sign convention consistent with dense path:
        # dense solves la.eig(A_dense, -E_matrix, ...)
        E_eff = (-E).tocsc()
        n_states = J_aug.shape[0]

        k_search = min(k + 6, n_states - 2)
        if k_search <= 0:
            k_search = min(max(1, k), n_states - 2)
        else:
            pass

        sigma_candidates = (1e-5, 1e-4, 1e-3, 1e-2, 1e-1)
        eig_ok = False
        last_err = None

        for sigma in sigma_candidates:
            try:
                J_shift = (J_aug - sigma * E_eff).tocsc()
                J_shift_lu = spla.splu(J_shift)

                op_methods = SparseGeneralizedShiftInvertMethods(n_states=n_states,
                                                                 total_size=J_shift.shape[0],
                                                                 J_aug_lu=J_shift_lu,
                                                                 E=E_eff)
                inv_op = spla.LinearOperator(shape=(n_states, n_states),
                                             matvec=op_methods.matvec,
                                             rmatvec=op_methods.rmatvec,
                                             dtype=np.complex128)

                mu_R, v_raw = spla.eigs(inv_op, k=k_search, which="LM", tol=1e-10)
                mu_L, w_raw = spla.eigs(inv_op.T, k=k_search, which="LM", tol=1e-10)

                tol_mu = 1e-8
                valid_mask_R = np.isfinite(mu_R) & (np.abs(mu_R) > tol_mu)
                valid_mask_L = np.isfinite(mu_L) & (np.abs(mu_L) > tol_mu)

                mu_R_valid = mu_R[valid_mask_R]
                mu_L_valid = mu_L[valid_mask_L]
                v_valid = v_raw[:, valid_mask_R]
                w_valid = w_raw[:, valid_mask_L]

                eigenvalues_R = sigma + 1.0 / mu_R_valid
                eigenvalues_L = sigma + 1.0 / mu_L_valid

                if (eigenvalues_R.size == 0
                        or eigenvalues_L.size == 0
                        or not np.all(np.isfinite(eigenvalues_R))
                        or not np.all(np.isfinite(eigenvalues_L))
                        or v_valid.shape[1] == 0
                        or w_valid.shape[1] == 0):
                    raise ValueError("ARPACK returned empty or non-finite generalized eigenvalues")

                eig_ok = True
                if verbose:
                    print(f"Sparse generalized shift-invert eigs converged with sigma={sigma:.1e}")
                break
            except (RuntimeError, ValueError) as err:
                last_err = err
                if verbose:
                    print(f"Sparse generalized shift-invert eigs failed with sigma={sigma:.1e}: {err}")

        if not eig_ok:
            raise RuntimeError(f"Sparse generalized eigensolver failed with all sigma candidates: {last_err}")

    # 5. STRICT MATCHING
    # To avoid Arnoldi asymmetries, we use a metric that combines Re and Im.
    # We sort from lowest to highest natural frequency.
    order_R = np.argsort(np.abs(eigenvalues_R.imag) + np.abs(eigenvalues_R.real), kind="stable")
    order_L = np.argsort(np.abs(eigenvalues_L.imag) + np.abs(eigenvalues_L.real), kind="stable")

    eigenvalues_R = eigenvalues_R[order_R]

    v_valid = v_valid[:, order_R]
    w_valid = w_valid[:, order_L]

    # We strictly truncate to the requested k modes.
    if len(eigenvalues_R) > k:
        eigenvalues_R = eigenvalues_R[:k]
        v_valid = v_valid[:, :k]
    else:
        pass

    # We use w_valid shape for validate the size of L_eigen
    if w_valid.shape[1] > k:
        w_valid = w_valid[:, :k]
    else:
        pass

    eigenvalues = eigenvalues_R

    # 6. PARTICIPATION
    # Ensure eigenvectors are complex (scipy may return float64 for real eigenvalues)
    v_valid = v_valid.astype(np.complex128, copy=False)
    w_valid = w_valid.astype(np.complex128, copy=False)
    if differential_vars == 0:
        participation_factors = compute_participation_factors(v=v_valid, w=w_valid)
    else:
        participation_factors = compute_participation_factors_generalized(v=v_valid, w=w_valid, E=E)

    eig_no_conjugates = select_eigs_without_conjugates(eigenvalues)
    damping_ratios, conjugate_freq = compute_damping_ratios_and_frequencies(eigenvalues, eig_no_conjugates)

    if verbose:
        print(f"Sparse SSS Math Time: {(time.perf_counter() - t0) * 1000:.2f} ms")

    return eigenvalues, v_valid, participation_factors, damping_ratios, conjugate_freq, np.empty(0), None


class SparseGeneralizedShiftInvertMethods:
    """
    Helper class to hold the matvec and rmatvec operations for the Sparse LinearOperator for 
    generalized eigenvalues.
    """
    __slots__ = ['n_states', 'total_size', 'J_aug_lu', 'E']

    def __init__(self, n_states: int, total_size: int, J_aug_lu, E: sp.spmatrix):
        self.n_states = n_states
        self.total_size = total_size
        self.J_aug_lu = J_aug_lu
        self.E = E.tocsc()

    def matvec(self, v: np.ndarray) -> np.ndarray:
        ev = self.E @ v
        rhs_r = np.zeros(self.total_size, dtype=np.float64)
        rhs_i = np.zeros(self.total_size, dtype=np.float64)
        rhs_r[:self.n_states] = np.asarray(ev.real, dtype=np.float64)
        rhs_i[:self.n_states] = np.asarray(ev.imag, dtype=np.float64)

        sol_r = self.J_aug_lu.solve(rhs_r)
        sol_i = self.J_aug_lu.solve(rhs_i)
        return sol_r[:self.n_states] + 1j * sol_i[:self.n_states]

    def rmatvec(self, v: np.ndarray) -> np.ndarray:
        rhs_r = np.zeros(self.total_size, dtype=np.float64)
        rhs_i = np.zeros(self.total_size, dtype=np.float64)
        rhs_r[:self.n_states] = np.asarray(v.real, dtype=np.float64)
        rhs_i[:self.n_states] = np.asarray(v.imag, dtype=np.float64)

        sol_r = self.J_aug_lu.solve(rhs_r, trans='T')
        sol_i = self.J_aug_lu.solve(rhs_i, trans='T')
        sol = sol_r[:self.n_states] + 1j * sol_i[:self.n_states]
        return self.E.T @ sol


class SparseShiftAndInvertMethods:
    """
    Helper class to hold the matvec and rmatvec operations for the Sparse LinearOperator.
    """
    __slots__ = ['n_states', 'total_size', 'J_aug_lu']

    def __init__(self, n_states: int, total_size: int, J_aug_lu: spla.SuperLU):
        """
        Constructor for SparseShiftAndInvertMethods.

        :param n_states: Number of state variables.
        :type n_states: int
        :param total_size: Total size of the augmented Jacobian.
        :type total_size: int
        :param J_aug_lu: SuperLU factorized augmented Jacobian matrix.
        :type J_aug_lu: spla.SuperLU
        """
        self.n_states: int = n_states
        self.total_size: int = total_size
        self.J_aug_lu: spla.SuperLU = J_aug_lu

    def matvec(self, b: Vec) -> Vec:
        """
        Matrix-vector multiplication.

        :param b: Input vector.
        :type b: Vec
        :return: Result vector.
        """
        # SuperLU owns a real factorization while ARPACK may request a complex
        # operator product.  Solve both components explicitly to preserve the
        # imaginary part of Arnoldi vectors.
        rhs_real: Vec = np.zeros(self.total_size, dtype=np.float64)
        rhs_imag: Vec = np.zeros(self.total_size, dtype=np.float64)
        rhs_real[:self.n_states] = np.asarray(b.real, dtype=np.float64)
        rhs_imag[:self.n_states] = np.asarray(b.imag, dtype=np.float64)
        solution_real: Vec = self.J_aug_lu.solve(rhs_real)
        solution_imag: Vec = self.J_aug_lu.solve(rhs_imag)
        return solution_real[:self.n_states] + 1j * solution_imag[:self.n_states]

    def rmatvec(self, b: Vec) -> Vec:
        """
        Adjoint matrix-vector multiplication.

        :param b: Input vector.
        :type b: Vec
        :return: Result vector.
        """
        rhs_real: Vec = np.zeros(self.total_size, dtype=np.float64)
        rhs_imag: Vec = np.zeros(self.total_size, dtype=np.float64)
        rhs_real[:self.n_states] = np.asarray(b.real, dtype=np.float64)
        rhs_imag[:self.n_states] = np.asarray(b.imag, dtype=np.float64)
        solver: Any = self.J_aug_lu
        solution_real: Vec = solver.solve(rhs_real, trans='T')
        solution_imag: Vec = solver.solve(rhs_imag, trans='T')

        return solution_real[:self.n_states] + 1j * solution_imag[:self.n_states]


class SmallSignalStabilityRmsDriver(DriverTemplate):
    """
    Small Signal Stability RMS driver
    """
    __slots__ = [
        'problem',
        'sss_options',
        'assessment_time',
        'k',
        'rms_options',
        'integration_methods_dict',
        'results',
    ]

    name = 'Small Signal Stability Simulation'
    tpe = SimulationTypes.RmsSmallSignal_run

    def __init__(self,
                 grid: MultiCircuit,
                 rms_options: Union[RmsOptions, None] = None,
                 sss_options: Union[RmsSmallSignalStabilityOptions, None] = None,
                 pf_results: Union[PowerFlowResults, None] = None,
                 engine: EngineType = EngineType.VeraGrid):

        """
        DynamicDriver class constructor for Small Signal stability analysis
        :param grid: MultiCircuit instance
        :param rms_options: RmsOptions instance
        :param sss_options: SmallSignalOptions instance
        :param pf_results: PowerFlowResults
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        # Normalize optional configurations before the RMS problem consumes
        # them.  This keeps direct API construction consistent with the GUI,
        # which always passes explicit option instances.
        self.rms_options: RmsOptions = RmsOptions() if rms_options is None else rms_options
        self.sss_options: RmsSmallSignalStabilityOptions = (
            RmsSmallSignalStabilityOptions() if sss_options is None else sss_options
        )

        events_group = RmsEventsGroup("simulation1")

        self.problem = RmsProblemDae(grid=grid,
                                     options=self.rms_options,
                                     pf_results=pf_results,
                                     logger=self.logger)

        self.problem.set_events_group(events_group)

        self.assessment_time = self.sss_options.ss_assessment_time

        n_modes = self.problem.get_states_number() + self.problem.get_diff_var_number()
        self.k = self.sss_options.k if self.sss_options.k is not None else n_modes

        self.integration_methods_dict: dict[DynamicIntegrationMethod, type] = dict()
        self.integration_methods_dict[DynamicIntegrationMethod.DaeBackEuler] = BackEulerImplicitIntegration

        self.results: SmallSignalStabilityRmsResults = SmallSignalStabilityRmsResults(eigenvalues=np.empty(0),
                                                                                      right_eigenvectors=np.empty((0, 0)),
                                                                                      participation_factors=np.empty((0, 0)),
                                                                                      damping_ratios=np.empty(0),
                                                                                      conjugate_frequencies=np.empty(0),
                                                                                      state_matrix=np.empty((0, 0)),
                                                                                      stat_vars=list(),
                                                                                      algebraic_vars=list())

    def run(self) -> None:
        """
        Main function to initialize and run the system simulation.

        This function sets up logging, starts the dynamic simulation, and
        logs the outcome. It handles and logs any exceptions raised during execution.
        :return:
        """
        # Run the dynamic simulation
        self.run_small_signal_stability()

    def run_small_signal_stability(self) -> None:
        """
        Performs the numerical integration using the chosen method and the small signal stability assessment.
        :return:
        """
        self.tic()

        # Start the progress sequence before preparing the linearization point so
        # the GUI immediately reflects that the small-signal study is running.
        self.report_progress(0.0)
        self.report_text("Preparing the RMS small-signal stability analysis...")

        x = self.problem.get_x0()
        dx = np.zeros_like(x)

        if not self.assessment_time == 0:

            # The optional time-domain simulation moves the RMS model to the
            # exact operating point requested for the subsequent linearization.
            self.report_progress(10.0)
            self.report_text(
                f"Simulating the RMS model up to the assessment time ({self.assessment_time:g} s)..."
            )

            sparse_solver_backend_provider: SparseLinearSolverBackendProvider = resolve_sparse_lu_provider(
                self.rms_options.sparse_solver,
                self.logger,
            )
            solver = self.integration_methods_dict[self.rms_options.integration_method](
                problem=self.problem,
                t0=0,
                t_end=self.assessment_time,
                h=self.rms_options.time_step,
                max_iter=self.rms_options.max_iter,
                sparse_solver_backend_provider=sparse_solver_backend_provider,
            )

            t, y, well_initialized, converged = solver.simulate()
            i = int(self.assessment_time / self.rms_options.time_step)
            x = y[i]

        else:
            # Without a requested assessment time, the initialized RMS state is
            # already the operating point used to build the small-signal model.
            self.report_text("Using the initialized RMS operating point...")

        # Both operating-point paths converge here before the modal calculation.
        self.report_progress(55.0)

        n = self.problem.get_states_number() + self.problem.get_diff_var_number()
        if self.k >= n - 1 or self.k == 0:
            # The dense solver returns the complete modal spectrum when all
            # system modes have been requested.
            self.report_progress(60.0)
            self.report_text("Computing the complete RMS small-signal modal spectrum...")
            (eigenvalues,
             right_eigenvectors,
             participation_factors,
             damping_ratios,
             conjugate_frequencies,
             state_matrix,
             reduced_state_matrix) = run_dense_small_signal_stability(problem=self.problem,
                                                                      x=x,
                                                                      dx=dx,
                                                                      verbose=self.sss_options.verbose)
        else:
            # The sparse solver targets only the requested modes and avoids the
            # cost of a complete decomposition for larger RMS systems.
            self.report_progress(60.0)
            self.report_text(f"Computing {self.k} RMS small-signal modes with the sparse eigensolver...")
            (eigenvalues,
             right_eigenvectors,
             participation_factors,
             damping_ratios,
             conjugate_frequencies,
             state_matrix,
             reduced_state_matrix) = run_sparse_small_signal_stability(problem=self.problem,
                                                                       x=x, dx=dx,
                                                                       k=self.k,
                                                                       verbose=self.sss_options.verbose)

        # Package the modal quantities only after the eigensolver has completed,
        # keeping the final part of the progress range for result construction.
        self.report_progress(90.0)
        self.report_text("Building the RMS small-signal stability results...")
        state_vars = self.problem.state_vars
        algebraic_vars = self.problem.algebraic_vars
        self.results: SmallSignalStabilityRmsResults = SmallSignalStabilityRmsResults(
            eigenvalues=eigenvalues,
            right_eigenvectors=right_eigenvectors,
            participation_factors=participation_factors,
            damping_ratios=damping_ratios,
            conjugate_frequencies=conjugate_frequencies,
            state_matrix=state_matrix,
            stat_vars=state_vars,
            algebraic_vars= algebraic_vars
        )

        self.toc()
        self.report_progress(100.0)
        self.report_text("RMS small-signal stability analysis completed.")
