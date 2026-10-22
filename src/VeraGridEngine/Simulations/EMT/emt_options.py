# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import math
from typing import Tuple

from VeraGridEngine.Simulations.options_template import OptionsTemplate
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledWarmupPolicy
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, EmtProblemTypes, SparseSolver
from VeraGridEngine.Devices.Parents.editable_device import GCProp



class EmtOptions(OptionsTemplate):
    """
    EMT simulation options
    """

    __slots__ = (
        "time_step",
        "simulation_time",
        "tolerance",
        "solver_type",
        "integration_method",
        "verbose",
        "initialization_method",
        "problem_type",
        "init_newton_tol",
        "init_newton_max_iter",
        "init_newton_backtracking",
        "init_dense_threshold",
        "init_ptc_dtau0",
        "init_ptc_dtau_min",
        "init_ptc_dtau_max",
        "init_ptc_max_iter",
        "init_ptc_backward_euler_residual",
        "init_allow_state_equilibrium",
        "init_fix_pf_bus_voltages",
        "init_fix_seeded_states",
        "init_periodic_samples",
        "newton_compute_dense_cond",
        "newton_enable_fallback",
        "newton_enable_index1_check",
        "newton_enable_backtracking",
        "newton_step_norm_explode",
        "newton_dense_cond_warn",
        "newton_dense_cond_max_n",
        "newton_index1_max_block_n",
        "newton_index1_warn_pivot_ratio",
        "newton_index1_fail_pivot_ratio",
        "newton_backtracking_beta",
        "newton_backtracking_min_alpha",
        "newton_backtracking_max_iter",
        "compiled_warmup_policy",
        "sparse_solver",
        "external_sparse_solver_directory",
        "external_sparse_solver_plugin_name",
        "allow_internal_sparse_fallback",
        "fmi_state_event_time_tolerance",
        "fmi_state_event_max_iterations",
        "fmi_me_newton_absolute_tolerance",
        "fmi_me_newton_relative_tolerance",
        "fmi_me_newton_max_iterations",
        "fmi_me_max_continuous_states",
        "fmi_me_max_runtime_evaluations_per_step",
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(key="time_step", tpe=float),
        GCProp(key="simulation_time", tpe=float),
        GCProp(key="tolerance", tpe=float),
        GCProp(key="solver_type", tpe=EmtSolverTypes),
        GCProp(key="integration_method", tpe=DynamicIntegrationMethod),
        GCProp(key="verbose", tpe=int),
        GCProp(key="initialization_method", tpe=EmtInitializationMethod),
        GCProp(key="problem_type", tpe=EmtProblemTypes),
        GCProp(key="init_newton_tol", tpe=float),
        GCProp(key="init_newton_max_iter", tpe=int),
        GCProp(key="init_newton_backtracking", tpe=bool),
        GCProp(key="init_dense_threshold", tpe=int),
        GCProp(key="init_ptc_dtau0", tpe=float),
        GCProp(key="init_ptc_dtau_min", tpe=float),
        GCProp(key="init_ptc_dtau_max", tpe=float),
        GCProp(key="init_ptc_max_iter", tpe=int),
        GCProp(key="init_ptc_backward_euler_residual", tpe=bool),
        GCProp(key="init_allow_state_equilibrium", tpe=bool),
        GCProp(key="init_fix_pf_bus_voltages", tpe=bool),
        GCProp(key="init_fix_seeded_states", tpe=bool),
        GCProp(key="init_periodic_samples", tpe=int),
        GCProp(key="newton_compute_dense_cond", tpe=bool),
        GCProp(key="newton_enable_fallback", tpe=bool),
        GCProp(key="newton_enable_index1_check", tpe=bool),
        GCProp(key="newton_enable_backtracking", tpe=bool),
        GCProp(key="newton_step_norm_explode", tpe=float),
        GCProp(key="newton_dense_cond_warn", tpe=float),
        GCProp(key="newton_dense_cond_max_n", tpe=int),
        GCProp(key="newton_index1_max_block_n", tpe=int),
        GCProp(key="newton_index1_warn_pivot_ratio", tpe=float),
        GCProp(key="newton_index1_fail_pivot_ratio", tpe=float),
        GCProp(key="newton_backtracking_beta", tpe=float),
        GCProp(key="newton_backtracking_min_alpha", tpe=float),
        GCProp(key="newton_backtracking_max_iter", tpe=int),
        GCProp(key="compiled_warmup_policy", tpe=StructuralCompiledWarmupPolicy),
        GCProp(key="sparse_solver", tpe=SparseSolver),
        GCProp(key="external_sparse_solver_directory", tpe=str),
        GCProp(key="external_sparse_solver_plugin_name", tpe=str),
        GCProp(key="allow_internal_sparse_fallback", tpe=bool),
        GCProp(key="fmi_state_event_time_tolerance", tpe=float),
        GCProp(key="fmi_state_event_max_iterations", tpe=int),
        GCProp(key="fmi_me_newton_absolute_tolerance", tpe=float),
        GCProp(key="fmi_me_newton_relative_tolerance", tpe=float),
        GCProp(key="fmi_me_newton_max_iterations", tpe=int),
        GCProp(key="fmi_me_max_continuous_states", tpe=int),
        GCProp(key="fmi_me_max_runtime_evaluations_per_step", tpe=int),
    )

    def __init__(self,
                 time_step: float = 5e-6,
                 simulation_time: float = 0.02,
                 tolerance: float = 1e-6,
                 solver_type: EmtSolverTypes = EmtSolverTypes.StructuralAD,
                 integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                 verbose: int = 0,
                 initialization_method: EmtInitializationMethod = EmtInitializationMethod.Auto,
                 problem_type: EmtProblemTypes = EmtProblemTypes.CurrentBalance,
                 init_newton_tol: float = 1e-8,
                 init_newton_max_iter: int = 20,
                 init_newton_backtracking: bool = True,
                 init_dense_threshold: int = 48,
                 init_ptc_dtau0: float = 1.0,
                 init_ptc_dtau_min: float = 1e-6,
                 init_ptc_dtau_max: float = 1e1,
                 init_ptc_max_iter: int = 60,
                 init_ptc_backward_euler_residual: bool = False,
                 init_allow_state_equilibrium: bool = True,
                 init_fix_pf_bus_voltages: bool = False,
                 newton_compute_dense_cond: bool = False,
                 newton_enable_fallback: bool = False,
                 newton_enable_index1_check: bool = False,
                 newton_enable_backtracking: bool = False,
                 newton_step_norm_explode: float = 1e6,
                 newton_dense_cond_warn: float = 1e12,
                 newton_dense_cond_max_n: int = 600,
                 newton_index1_max_block_n: int = 128,
                 newton_index1_warn_pivot_ratio: float = 1e-10,
                 newton_index1_fail_pivot_ratio: float = 1e-14,
                 newton_backtracking_beta: float = 0.5,
                 newton_backtracking_min_alpha: float = 1e-4,
                 newton_backtracking_max_iter: int = 6,
                 compiled_warmup_policy: StructuralCompiledWarmupPolicy = StructuralCompiledWarmupPolicy.Adaptive,
                 sparse_solver: SparseSolver = SparseSolver.SuperLU,
                 external_sparse_solver_directory: str = "",
                 external_sparse_solver_plugin_name: str = "",
                 allow_internal_sparse_fallback: bool = True,
                 fmi_state_event_time_tolerance: float = 1e-9,
                 fmi_state_event_max_iterations: int = 32,
                 fmi_me_newton_absolute_tolerance: float = 1e-8,
                 fmi_me_newton_relative_tolerance: float = 1e-8,
                 fmi_me_newton_max_iterations: int = 20,
                 fmi_me_max_continuous_states: int = 128,
                 fmi_me_max_runtime_evaluations_per_step: int = 100000,
                 init_fix_seeded_states: bool = True,
                 init_periodic_samples: int = 0) -> None:
        """
        EmtOptions
        :param time_step: time step of the simulations (s)
        :param simulation_time: simulation time (s)
        :param tolerance: Integration tolerance
        :param verbose: Verbosity level
        :param init_fix_seeded_states: Keep seeded differential states fixed in the global
            reduced initializer. If False, use their values as starting guesses and solve
            their initialization equations (or equilibrium equations when allowed).
            These instantaneous equations do not impose periodic steady state and may
            contain dependent seed assignments. Does not change Explicit or device-local PTC.
        :param init_periodic_samples: Zero uses instantaneous initialization. An odd value
            >= 9 selects independent cycle constraints for native Newton/global PTC,
            releasing all states and bus voltages regardless of init_fix_seeded_states.
            Currently validated for smooth autonomous synchronous-machine Kundur models.
        :param fmi_state_event_time_tolerance: Absolute FMI ME event-time tolerance in seconds.
        :param fmi_state_event_max_iterations: Maximum FMI ME event bisections.
        :param fmi_me_newton_absolute_tolerance: Absolute scale used by the FMI ME Newton residual.
        :param fmi_me_newton_relative_tolerance: Relative scale used by the FMI ME Newton residual.
        :param fmi_me_newton_max_iterations: Maximum FMI ME Backward Euler Newton updates.
        :param fmi_me_max_continuous_states: Maximum dense FMI ME state dimension.
        :param fmi_me_max_runtime_evaluations_per_step: Shared runtime-call limit for one FMI ME step.
        :return: None.
        """

        OptionsTemplate.__init__(self, name='EmtSimulationOptions')

        self.time_step: float = time_step
        self.simulation_time: float = simulation_time
        self.tolerance: float = tolerance
        self.solver_type: EmtSolverTypes = solver_type
        self.integration_method: DynamicIntegrationMethod = integration_method
        self.verbose = verbose
        self.initialization_method: EmtInitializationMethod = initialization_method
        self.problem_type: EmtProblemTypes = problem_type
        self.init_newton_tol: float = init_newton_tol
        self.init_newton_max_iter: int = init_newton_max_iter
        self.init_newton_backtracking: bool = init_newton_backtracking
        self.init_dense_threshold: int = init_dense_threshold
        self.init_ptc_dtau0: float = init_ptc_dtau0
        self.init_ptc_dtau_min: float = init_ptc_dtau_min
        self.init_ptc_dtau_max: float = init_ptc_dtau_max
        self.init_ptc_max_iter: int = init_ptc_max_iter
        self.init_ptc_backward_euler_residual: bool = init_ptc_backward_euler_residual
        self.init_allow_state_equilibrium: bool = init_allow_state_equilibrium
        self.init_fix_pf_bus_voltages: bool = init_fix_pf_bus_voltages
        self.init_fix_seeded_states: bool = init_fix_seeded_states
        self.init_periodic_samples: int = init_periodic_samples
        self.newton_compute_dense_cond = newton_compute_dense_cond
        self.newton_enable_fallback = newton_enable_fallback
        self.newton_enable_index1_check = newton_enable_index1_check
        self.newton_enable_backtracking = newton_enable_backtracking
        self.newton_step_norm_explode = newton_step_norm_explode
        self.newton_dense_cond_warn = newton_dense_cond_warn
        self.newton_dense_cond_max_n = newton_dense_cond_max_n
        self.newton_index1_max_block_n = newton_index1_max_block_n
        self.newton_index1_warn_pivot_ratio = newton_index1_warn_pivot_ratio
        self.newton_index1_fail_pivot_ratio = newton_index1_fail_pivot_ratio
        self.newton_backtracking_beta = newton_backtracking_beta
        self.newton_backtracking_min_alpha = newton_backtracking_min_alpha
        self.newton_backtracking_max_iter = newton_backtracking_max_iter
        self.compiled_warmup_policy: StructuralCompiledWarmupPolicy = compiled_warmup_policy
        self.sparse_solver: SparseSolver = sparse_solver
        self.external_sparse_solver_directory: str = external_sparse_solver_directory
        self.external_sparse_solver_plugin_name: str = external_sparse_solver_plugin_name
        self.allow_internal_sparse_fallback: bool = allow_internal_sparse_fallback
        if (
            math.isfinite(fmi_state_event_time_tolerance)
            and fmi_state_event_time_tolerance > 0.0
        ):
            self.fmi_state_event_time_tolerance: float = (
                fmi_state_event_time_tolerance
            )
        else:
            raise ValueError(
                "EMT FMI state-event time tolerance must be finite and positive"
            )
        if (
            isinstance(fmi_state_event_max_iterations, int)
            and not isinstance(fmi_state_event_max_iterations, bool)
            and fmi_state_event_max_iterations > 0
        ):
            self.fmi_state_event_max_iterations: int = (
                fmi_state_event_max_iterations
            )
        else:
            raise ValueError(
                "EMT FMI state-event maximum iterations must be a positive integer"
            )
        if (
            math.isfinite(fmi_me_newton_absolute_tolerance)
            and fmi_me_newton_absolute_tolerance > 0.0
        ):
            self.fmi_me_newton_absolute_tolerance: float = (
                fmi_me_newton_absolute_tolerance
            )
        else:
            raise ValueError(
                "EMT FMI ME Newton absolute tolerance must be finite and positive"
            )
        if (
            math.isfinite(fmi_me_newton_relative_tolerance)
            and fmi_me_newton_relative_tolerance > 0.0
        ):
            self.fmi_me_newton_relative_tolerance: float = (
                fmi_me_newton_relative_tolerance
            )
        else:
            raise ValueError(
                "EMT FMI ME Newton relative tolerance must be finite and positive"
            )
        if (
            isinstance(fmi_me_newton_max_iterations, int)
            and not isinstance(fmi_me_newton_max_iterations, bool)
            and 1 <= fmi_me_newton_max_iterations <= 100
        ):
            self.fmi_me_newton_max_iterations: int = fmi_me_newton_max_iterations
        else:
            raise ValueError(
                "EMT FMI ME Newton iteration limit must be an integer between 1 and 100"
            )
        if (
            isinstance(fmi_me_max_continuous_states, int)
            and not isinstance(fmi_me_max_continuous_states, bool)
            and 1 <= fmi_me_max_continuous_states <= 128
        ):
            self.fmi_me_max_continuous_states: int = fmi_me_max_continuous_states
        else:
            raise ValueError(
                "EMT FMI ME state limit must be an integer between 1 and 128"
            )
        if (
            isinstance(fmi_me_max_runtime_evaluations_per_step, int)
            and not isinstance(fmi_me_max_runtime_evaluations_per_step, bool)
            and 1 <= fmi_me_max_runtime_evaluations_per_step <= 10_000_000
        ):
            self.fmi_me_max_runtime_evaluations_per_step: int = (
                fmi_me_max_runtime_evaluations_per_step
            )
        else:
            raise ValueError(
                "EMT FMI ME runtime evaluation limit must be an integer between "
                "1 and 10000000"
            )
