# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import time
import scipy.sparse as sp
from scipy.sparse import csc_matrix
from collections.abc import Callable

from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import (
    project_initial_algebraic_state,
    solve_rms_newton_correction,
)
from VeraGridEngine.Simulations.Rms.numerical.implicit_jacobian_assembler import ImplicitJacobianAssembler
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import SparseLinearSolverBackendProvider
from VeraGridEngine.basic_structures import Vec, Mat


class BackEulerImplicitIntegration:
    """
    Backward Euler implicit integration solver.
    """
    __slots__ = (
        "problem",
        "t0",
        "h",
        "max_iter_0",
        "steps",
        "t",
        "y",
        "tol",
        "_cancel_checker",
        "_sparse_solver_backend_provider",
        "_jacobian_assembler",
        "_timings",
    )

    def __init__(self,
                 problem: RmsProblemDae,
                 t0: float,
                 t_end: float,
                 h: float,
                 max_iter: int,
                 tolerance: float = 1e-7,
                 cancel_checker: Callable[[], bool] | None = None,
                 sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None = None) -> None:
        """
        Initializes an object to solve a given DAE (Differential-Algebraic Equation) problem using numerical
        methods. This constructor sets up the time grid and prepares storage for results.

        :param problem: The DAE solver problem instance containing the system equations and other solver
            configurations.
        :type problem: RmsProblemDae
        :param t0: The initial time of the simulation.
        :type t0: float
        :param t_end: The final time of the simulation.
        :type t_end: float
        :param h: The time step size to be used for the simulation.
        :type h: float
        :param max_iter: Maximum local Newton corrections; also the iteration
            limit passed to the existing initial projection.
        :type max_iter: int
        :param tolerance: Non-linear residual tolerance used by the Newton loop.
        :type tolerance: float
        :param cancel_checker: Optional cancellation callback checked at each macro time step.
        :type cancel_checker: Callable[[], bool] | None
        :param sparse_solver_backend_provider: Sparse LU provider for the Newton corrections; None keeps SciPy spsolve.
        :type sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None
        :return: None
        :rtype: None
        """

        # if not problem.is_initialized():
        #     raise Exception('Problem is not initialized')

        self.problem: RmsProblemDae = problem
        self.t0: float = t0
        self.h: float = h
        self.max_iter_0: int = max_iter
        self.steps: int = int(np.ceil((t_end - t0) / h))
        self.t: Vec = np.empty(self.steps + 1)
        self.y: Mat = np.empty((self.steps + 1, self.problem.get_all_vars_number()))
        self.tol: float = tolerance
        self._cancel_checker: Callable[[], bool] | None = cancel_checker
        self._sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None = sparse_solver_backend_provider
        # The implicit Jacobian is assembled on a packed pattern reused across Newton corrections.
        self._jacobian_assembler: ImplicitJacobianAssembler = ImplicitJacobianAssembler()

    def _rhs_implicit(self,
                      x: Vec,
                      dx: Vec,
                      xn: Vec,
                      h: float) -> Vec:
        """
        Return 𝑑x/dt given the current *state* vector.
        :param x: get the right-hand-side give a state vector
        :param dx:
        :param xn:
        :return f_state_update or f_algeb
        """
        _t0 = time.time()
        f_algeb = self.problem.rhs_algebraic(x, dx)
        self._timings["rhs_algeb_time"] += time.time() - _t0

        if self.problem.get_states_number() > 0:
            _t0 = time.time()
            f_state = self.problem.rhs_state(x, dx)
            self._timings["rhs_state_time"] += time.time() - _t0
            f_state_update = x[:self.problem.get_states_number()] - xn[:self.problem.get_states_number()] - h * f_state
            return np.r_[f_state_update, f_algeb]

        else:
            return f_algeb

    def _jacobian_implicit(self,
                           x: Vec,
                           dx: Vec,
                           h: float) -> sp.csc_matrix:
        """
        :param x: vector or variables' values
        :param dx: vector of diff values
        :param h: step
        :return:
        """

        """
                  state Var    algeb var
        state eq |I - h * J11 | - h* J12  |    | ∆ state var|    | ∆ state eq |
                 |            |           |    |            |    |            |
                 -------------------------- x  |------------|  = |------------|
        algeb eq |J21         | J22       |    | ∆ algeb var|    | ∆ algeb eq |
                 |            |           |    |            |    |            |
        """

        # returns only j22 if no states, returns J if states
        if self.problem.get_states_number() == 0:
            t0 = time.time()
            j22: sp.csc_matrix = self.problem.get_j22(x, dx, h)
            self._timings["jac_j22_time"] += time.time() - t0
            return j22

        t0 = time.time()
        j11_val: csc_matrix = self.problem.get_j11(x, dx, h)
        self._timings["jac_j11_time"] += time.time() - t0
        t0 = time.time()
        j12_val: csc_matrix = self.problem.get_j12(x, dx, h)
        self._timings["jac_j12_time"] += time.time() - t0
        t0 = time.time()
        j21_val: csc_matrix = self.problem.get_j21(x, dx, h)
        self._timings["jac_j21_time"] += time.time() - t0
        t0 = time.time()
        j22_val: csc_matrix = self.problem.get_j22(x, dx, h)
        self._timings["jac_j22_time"] += time.time() - t0

        # Same matrix as pack_4_by_4_scipy((I - h*J11).tocsc(), -h*J12, J21, J22), without rebuilding its pattern.
        J: sp.csc_matrix = self._jacobian_assembler.assemble(self.problem.get_states_number(), h,
                                                            j11_val, j12_val, j21_val, j22_val)

        return J

    def simulate(self) -> tuple[Vec, Mat, bool, bool]:
        """Integrate accepted local steps with a bounded Newton correction count.

        The final allowed correction is checked against the configured strict
        tolerance. Failed steps expose only initial and completed macro samples.

        :return: Matching time/state prefixes, initial projection status and
            convergence status of the requested trajectory.
        """
        converged: bool = False
        completed_samples: int = 1

        x0: Vec = self.problem.get_x0()

        # we assume steady state
        dx0: Vec = np.zeros(self.problem.get_diff_var_number(), dtype=float)
        self.problem.update_variable_params(
            t=self.t0,
            x_snapshot=x0,
            scheduled_t=self.t0,
        )
        self.problem.update(
            self.t0,
            x0,
            self.problem._variable_parameters_values,
        )
        initial_residual: float
        x0, well_initialized, initial_residual = project_initial_algebraic_state(
            problem=self.problem,
            initial_values=x0,
            differential_values=dx0,
            tolerance=self.tol,
            max_iter=self.max_iter_0,
        )
        if well_initialized:
            pass
        else:
            self.problem.logger.add_error(
                msg="RMS algebraic initial projection did not converge",
                device="BackEulerImplicitIntegration",
                value=initial_residual,
                expected_value=self.tol,
            )

        # timing accumulators
        self._timings = {
            "jacobian_time": 0.0,
            "rhs_time": 0.0,
            "lag_update_time": 0.0,
            "linear_solver_time": 0.0,
            "initial_step_time": 0.0,
            "rhs_algeb_time": 0.0,
            "rhs_state_time": 0.0,
            "jac_j11_time": 0.0,
            "jac_j12_time": 0.0,
            "jac_j21_time": 0.0,
            "jac_j22_time": 0.0,
        }
        timings = self._timings

        self.t[0] = self.t0
        dx = dx0.copy()
        dx_last = dx0.copy()
        residual = 0.0
        self.y[0, :] = x0.copy()

        has_fmu_cs = True
        has_fmu_me = True

        try:
            self.problem.initialize_fmu_cs_devices(x0, self.t0)
        except AttributeError:
            has_fmu_cs = False

        try:
            self.problem.initialize_fmu_me_devices(x0, self.t0)
        except AttributeError:
            has_fmu_me = False

        try:
            for step_idx in range(self.steps):
                if self._cancel_checker is not None and self._cancel_checker():
                    return self.t[:step_idx + 1].copy(), self.y[:step_idx + 1, :].copy(), well_initialized, converged

                self.problem.report_progress2(step_idx, self.steps)

                t_current_macro: float = self.t[step_idx]
                # Derive every macro boundary from the integer step index so
                # floating-point accumulation cannot activate an event early.
                t_macro_target: float = self.t0 + float(step_idx + 1) * self.h

                x_prev = self.y[step_idx, :].copy()
                x_new = x_prev.copy()
                t_local_prev = t_current_macro
                is_first_local_step = True
                dx_last = dx
                substep_converged = True

                while t_local_prev < (t_macro_target - 1e-15):
                    forced_event_time: float | None = self.problem.get_next_forced_event_time(
                        t_local_prev,
                        t_macro_target,
                    )

                    if forced_event_time is None:
                        t_curr = t_macro_target
                    else:
                        t_curr = forced_event_time

                    h_eff: float = t_curr - t_local_prev
                    if h_eff <= 0.0:
                        self.problem.logger.add_error(
                            msg=(f"Invalid RMS local step size {h_eff:g} s at "
                                 f"time {t_local_prev:g} s (macro step {step_idx + 1}). "
                                 f"Completed results through "
                                 f"{self.t[completed_samples - 1]:g} s are retained; "
                                 f"the failed step is omitted."),
                            device="BackEulerImplicitIntegration",
                        )
                        substep_converged = False
                        converged = False
                        break

                    # Continuous controls use the local target so a step at an
                    # accepted boundary drives the immediately following
                    # interval. Scheduled modes retain the previous time view
                    # because their latches own separate boundary semantics.
                    self.problem.update_variable_params(t=t_curr,
                                                        x_snapshot=x_new,
                                                        scheduled_t=t_local_prev)

                    self.problem.update(t_curr, x_new, self.problem._variable_parameters_values)

                    if has_fmu_me:
                        self.problem.advance_fmu_me_devices(t=t_local_prev, x_snapshot=x_prev, h=h_eff)
                        state_event_retry_time: float | None = (
                            self.problem.prepare_fmu_me_state_event_retry()
                        )
                    else:
                        state_event_retry_time = None
                    co_simulation_advanced: bool = False
                    if has_fmu_cs and state_event_retry_time is None:
                        co_simulation_advanced = (
                            self.problem.advance_fmu_cs_devices(
                                t=t_local_prev,
                                x_snapshot=x_prev,
                                h=h_eff,
                            )
                        )
                    else:
                        pass

                    n_iter: int = 0
                    substep_converged = state_event_retry_time is not None
                    tol: float = self.tol

                    # Validate the last corrected point, even when no further
                    # correction is permitted, before resolving the FMI boundary.
                    while not substep_converged:
                        if not np.all(np.isfinite(x_new)):
                            self.problem.logger.add_error(
                                msg=(f"Non-finite RMS candidate at {t_curr:g} s "
                                     f"(macro step {step_idx + 1}); the failed step is omitted."),
                                device="BackEulerImplicitIntegration",
                            )
                            break
                        else:
                            pass
                        if step_idx == 0 and is_first_local_step:
                            dx = dx0.copy()
                        else:
                            dx = self.problem.get_dx(x_new, x_prev, dx_last, h_eff)

                        rhs_start = time.time()
                        rhs = self._rhs_implicit(x_new, dx, x_prev, h_eff)
                        rhs_end = time.time()
                        timings["rhs_time"] += rhs_end - rhs_start

                        # A full finite residual is required before either
                        # acceptance or a Jacobian evaluation can be safe.
                        if not np.all(np.isfinite(rhs)):
                            self.problem.logger.add_error(
                                msg=(f"Non-finite RMS residual at {t_curr:g} s "
                                     f"(macro step {step_idx + 1}); the failed step is omitted."),
                                device="BackEulerImplicitIntegration",
                            )
                            break
                        else:
                            pass
                        residual = np.linalg.norm(rhs, np.inf)
                        substep_converged = residual < tol

                        if not substep_converged:
                            # The residual check consumes no correction budget;
                            # never assemble a Jacobian after that budget is spent.
                            if n_iter >= self.max_iter_0:
                                self.problem.logger.add_error(
                                    msg=(f"RMS Newton correction budget exhausted at {t_curr:g} s "
                                         f"(macro step {step_idx + 1}); the failed step is omitted."),
                                    device="BackEulerImplicitIntegration",
                                    value=residual,
                                    expected_value=tol,
                                )
                                break
                            else:
                                pass
                            solved = False
                            jac_start = time.time()
                            Jf = self._jacobian_implicit(x_new, dx, h_eff)
                            jac_end = time.time()
                            timings["jacobian_time"] += jac_end - jac_start
                            linear_start = time.time()
                            reference_indices: tuple[int, int] | None = (
                                self.problem.get_small_signal_reference_indices()
                            )
                            reference_column: int | None
                            if reference_indices is not None:
                                reference_column = reference_indices[1]
                            else:
                                reference_column = None
                            delta: Vec = solve_rms_newton_correction(
                                jacobian=Jf,
                                residual=rhs,
                                reference_column=reference_column,
                                sparse_solver_backend_provider=self._sparse_solver_backend_provider,
                            )
                            linear_end = time.time()
                            timings["linear_solver_time"] += linear_end - linear_start
                            solved = np.all(np.isfinite(delta))

                            if not solved and Jf.shape[0] == Jf.shape[1]:
                                # Tikhonov-regularized Newton step
                                lam = 1e-4
                                while lam <= 1e-1 and not solved:
                                    delta = sp.linalg.spsolve(
                                        (Jf + lam * sp.eye(Jf.shape[0], format='csc')).tocsc(), -rhs)
                                    solved = np.all(np.isfinite(delta))
                                    lam *= 1000.0

                            if not solved:
                                delta, *_ = sp.linalg.lsqr(Jf, -rhs)
                                solved = np.all(np.isfinite(delta))
                                _, s, vh = np.linalg.svd(Jf.toarray() if sp.issparse(Jf) else Jf)
                                singular_dirs = np.where(s < tol)[0]
                                for i in singular_dirs:
                                    v = vh.T[:, i]  # variable-space vector
                                    abs_v = np.abs(v)
                                    dominant_idx = np.argsort(abs_v, kind="stable")[::-1][:5]  # top 5 vars
                                    print(f"\nSingular direction {i}, σ={s[i]:.3e}")
                                    for j in dominant_idx:
                                        if j < self.problem.get_algebraic_var_number():
                                            var_name = self.problem.algebraic_vars[j].name
                                            print(f"  {var_name:20s} {v[j]:+.3e}")
                                print("Using LSQR")
                                print(f"residual is {residual} for timestep {step_idx}")
                            else:
                                pass

                            if not solved:
                                nonfinite_rhs = np.flatnonzero(~np.isfinite(rhs)).tolist()
                                self.problem.logger.add_error(
                                    msg=(f"RMS linear solve returned non-finite values at "
                                         f"time {t_curr:g} s (macro step {step_idx + 1}); "
                                         f"Jacobian shape={Jf.shape}, "
                                         f"non-finite RHS indices={nonfinite_rhs}. "
                                         f"Completed results through "
                                         f"{self.t[completed_samples - 1]:g} s are retained; "
                                         f"the failed step is omitted."),
                                    device="BackEulerImplicitIntegration",
                                )
                                substep_converged = False
                                break

                            # Damped Newton
                            _dmax = np.max(np.abs(delta))
                            if _dmax > 1.0:
                                delta = delta * (1.0 / _dmax)
                            x_new += delta
                            # Finite operands can overflow during the correction;
                            # reject before presenting this point to FMI ME inputs.
                            if not np.all(np.isfinite(x_new)):
                                self.problem.logger.add_error(
                                    msg=(f"Non-finite corrected RMS candidate at {t_curr:g} s "
                                         f"(macro step {step_idx + 1}); the failed step is omitted."),
                                    device="BackEulerImplicitIntegration",
                                )
                                break
                            else:
                                pass
                            if has_fmu_me:
                                # Replace the candidate with outputs evaluated
                                # from the corrected network iterate before the
                                # next residual is formed.
                                self.problem.advance_fmu_me_devices(
                                    t=t_local_prev,
                                    x_snapshot=x_new,
                                    h=h_eff,
                                )
                                state_event_retry_time = (
                                    self.problem.prepare_fmu_me_state_event_retry()
                                )
                                if state_event_retry_time is not None:
                                    if co_simulation_advanced:
                                        self.problem.logger.add_error(
                                            msg=(f"RMS FMI ME state event at {t_curr:g} s "
                                                 f"cannot retry after Co-Simulation devices advanced. "
                                                 f"Completed results through "
                                                 f"{self.t[completed_samples - 1]:g} s are retained; "
                                                 f"the failed step is omitted."),
                                            device="BackEulerImplicitIntegration",
                                        )
                                        substep_converged = False
                                        converged = False
                                        break
                                    else:
                                        substep_converged = True
                                else:
                                    pass
                            else:
                                pass
                            n_iter += 1

                    if substep_converged:
                        if state_event_retry_time is None:
                            if has_fmu_me:
                                self.problem.resolve_fmu_me_devices(accepted=True)
                            else:
                                pass
                            self.problem.resolve_manufacturer_native_boundary(
                                t=float(t_curr),
                                x=x_new,
                            )
                            dx_last = dx.copy()
                            x_prev = x_new.copy()
                            t_local_prev = t_curr
                            is_first_local_step = False
                        else:
                            # Keep the accepted network point unchanged; the
                            # next local iteration targets the localized event.
                            x_new = x_prev.copy()
                    else:
                        if has_fmu_me:
                            self.problem.resolve_fmu_me_devices(accepted=False)
                        else:
                            pass
                        print(f"Failed to converge at step {step_idx} and n_iter is {n_iter}")
                        print(f"Residual is {residual}")
                        converged = False
                        break

                if not substep_converged:
                    break

                lag_update_start = time.time()
                # print(f'converged is {True} at step {step_idx} with {n_iter} iterations')

                self.y[step_idx + 1, :] = x_prev
                self.t[step_idx + 1] = t_macro_target

                lag_update_end = time.time()
                timings["lag_update_time"] += lag_update_end - lag_update_start
                converged = True
                completed_samples = step_idx + 2
        finally:
            if has_fmu_cs:
                self.problem.close_fmu_cs_devices()
            if has_fmu_me:
                self.problem.close_fmu_me_devices()

        return (self.t[:completed_samples],
                self.y[:completed_samples, :],
                well_initialized, converged)
