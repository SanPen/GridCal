# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import EmtSolverTypes
from VeraGridEngine.Simulations.driver_template import DummySignal

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_solver_registry import resolve_emt_sparse_solver_backend_provider
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonDiagnosticsConfig
from collections.abc import Callable
from typing import Any


EMT_SOLVER_CLASS_MAP = {
    EmtSolverTypes.Symbolic: JitSymbolicSolver,
    EmtSolverTypes.Automatic: JitAdSolver,
    EmtSolverTypes.StructuralAD: StructuralVectorizedSolver,
    EmtSolverTypes.StructuralCompiled: StructuralCompiledSolver,
}


def build_emt_solver(options: EmtOptions,
                     problem: EmtProblemTemplate,
                     t0: float,
                     t_end: float,
                     h: float,
                     method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                     newton_diag_config: NewtonDiagnosticsConfig | None = None,
                     progress_signal: DummySignal | None = None,
                     cancel_checker: Callable[[], bool] | None = None) -> Any:
    """
    Build the configured EMT solver.

    :param options: EMT options selecting the solver implementation.
    :type options: EmtOptions
    :param problem: EMT problem instance consumed by the solver.
    :type problem: EmtProblemTemplate
    :param t0: Initial simulation time.
    :type t0: float
    :param t_end: Final simulation time.
    :type t_end: float
    :param h: Nominal integration time step.
    :type h: float
    :param method: Integration method used by the solver.
    :type method: DynamicIntegrationMethod
    :param newton_diag_config: Optional Newton diagnostics configuration.
    :type newton_diag_config: NewtonDiagnosticsConfig | None
    :param progress_signal: Optional progress signal propagated to the solver loop.
    :type progress_signal: DummySignal | None
    :param cancel_checker: Optional cancellation callback checked by the solver at safe boundaries.
    :type cancel_checker: Callable[[], bool] | None
    :return: Configured EMT solver instance.
    :rtype: Any
    """

    if options.solver_type in EMT_SOLVER_CLASS_MAP:
        solver_cls = EMT_SOLVER_CLASS_MAP[options.solver_type]
    else:
        raise ValueError(f"Unsupported EMT solver type: {options.solver_type}")

    if options.solver_type == EmtSolverTypes.StructuralCompiled:
        sparse_backend_provider = resolve_emt_sparse_solver_backend_provider(
            solver_type=options.sparse_solver,
            external_plugin_name=options.external_sparse_solver_plugin_name,
            external_plugin_directory=options.external_sparse_solver_directory,
            allow_internal_fallback=options.allow_internal_sparse_fallback,
        )
        return solver_cls(problem=problem,
                          t0=t0,
                          t_end=t_end,
                          h=h,
                          method=method,
                          newton_max_iter=options.init_newton_max_iter,
                          warmup_policy=options.compiled_warmup_policy,
                          sparse_solver_backend_provider=sparse_backend_provider,
                          newton_diag_config=newton_diag_config,
                          progress_signal=progress_signal,
                          cancel_checker=cancel_checker,
                          newton_tolerance=options.tolerance)
    elif options.solver_type == EmtSolverTypes.StructuralAD:
        sparse_backend_provider = resolve_emt_sparse_solver_backend_provider(
            solver_type=options.sparse_solver,
            external_plugin_name=options.external_sparse_solver_plugin_name,
            external_plugin_directory=options.external_sparse_solver_directory,
            allow_internal_fallback=options.allow_internal_sparse_fallback,
        )
        return solver_cls(problem=problem,
                          t0=t0,
                          t_end=t_end,
                          h=h,
                          method=method,
                          newton_max_iter=options.init_newton_max_iter,
                          sparse_solver_backend_provider=sparse_backend_provider,
                          newton_diag_config=newton_diag_config,
                          progress_signal=progress_signal,
                          cancel_checker=cancel_checker,
                          newton_tolerance=options.tolerance)
    else:
        return solver_cls(problem=problem,
                          t0=t0,
                          t_end=t_end,
                          h=h,
                          method=method,
                          newton_max_iter=options.init_newton_max_iter,
                          newton_diag_config=newton_diag_config,
                          progress_signal=progress_signal,
                          cancel_checker=cancel_checker,
                          newton_tolerance=options.tolerance)
