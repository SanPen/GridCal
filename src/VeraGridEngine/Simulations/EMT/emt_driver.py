# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from typing import Dict, List

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.EMT.emt_problem_factory import build_emt_problem
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.dynamic_parameter_results import collect_declared_dynamic_parameter_values
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonDiagnosticsConfig
from VeraGridEngine.IO.fmu.fmu_device_integration import CompositeEmtBoundaryUpdater, build_emt_boundary_updater
from VeraGridEngine.basic_structures import Vec, StrVec
from VeraGridEngine.IO.manufacturer_native.runtime_session import ManufacturerNativeRuntimeSession
from VeraGridEngine.IO.native_runtime import NativeWorkerLimits
from VeraGridEngine.Utils.Symbolic.symbolic import Var

from VeraGridEngine.enumerations import EngineType, PlotSimulationType, SimulationTypes


def _compare_first_step_non_angle_states(
        values: np.ndarray,
        state_vars: List[Var],
        tolerance: float = 1.0e-4,
) -> bool | None:
    """Compare non-angle model states across the first integration step.

    This is a local sample-to-sample diagnostic. It does not establish an EMT
    equilibrium or periodic steady state because sinusoidal physical states are
    expected to evolve even when their phasors are stationary.

    :param values: Simulated variable samples with time along the first axis.
    :param state_vars: State variables corresponding to the leading columns.
    :param tolerance: Relative change accepted as unchanged.
    :return: ``True`` when every compared state remains within tolerance,
        ``False`` when at least one changes, or ``None`` when comparison is not
        possible.
    """
    values_array: np.ndarray = np.asarray(values, dtype=float)
    inputs_are_valid: bool = bool(
        np.isfinite(tolerance)
        and tolerance >= 0.0
        and values_array.ndim == 2
        and values_array.shape[0] >= 2
        and values_array.shape[1] >= len(state_vars)
    )
    if inputs_are_valid:
        pass
    else:
        return None

    indices: List[int] = list()
    state_index: int
    state_var: Var
    for state_index, state_var in enumerate(state_vars):
        is_angle_state: bool = state_var.name.lower().startswith(("theta", "angle", "phi"))
        if is_angle_state:
            pass
        else:
            indices.append(state_index)

    if len(indices) == 0:
        return None
    else:
        pass

    first_values: np.ndarray = values_array[0, indices]
    second_values: np.ndarray = values_array[1, indices]
    samples_are_finite: bool = bool(
        np.all(np.isfinite(first_values)) and np.all(np.isfinite(second_values))
    )
    if samples_are_finite:
        pass
    else:
        return None

    scale: np.ndarray = np.maximum(
        1.0,
        np.maximum(np.abs(first_values), np.abs(second_values)),
    )
    relative_change: np.ndarray = np.abs(second_values - first_values) / scale
    return bool(np.all(relative_change <= tolerance))


def _collect_emt_group_parameter_values(problem: EmtProblemDae,
                                        grid: MultiCircuit) -> Dict[str, float]:
    """
    Export one event-group parameter snapshot from the EMT problem.

    :param problem: Solved EMT problem instance.
    :param grid: Circuit containing the configured EMT model parameters.
    :return: Parameter scalar map keyed by ``device_idtag:param_name``.
    """
    parameter_values: Dict[str, float] = collect_declared_dynamic_parameter_values(
        grid=grid,
        simulation_type=PlotSimulationType.EMT,
        # The problem builder already reported mapping diagnostics. Rebuilding
        # result metadata must not emit them again for every saved snapshot.
        logger=None,
    )
    event_parameter_count: int = len(problem.get_variable_parameters())
    parameter_index: int

    # Runtime values are authoritative when a symbolic name is present in both
    # constant and event-capable contracts.
    for parameter_index in range(event_parameter_count):
        parameter_var = problem.get_variable_parameters()[parameter_index]
        device_idtag: str | None = problem._event_parameter_device_idtags.get(parameter_var.uid, None)
        if device_idtag is not None:
            parameter_key: str = str(device_idtag) + ":" + str(parameter_var.name)
            parameter_values[parameter_key] = float(problem._event_params_values[parameter_index])
        else:
            pass

    return parameter_values


class EmtSimulationDriver(DriverTemplate):
    __slots__ = (
        "pf_results_3Ph",
        "pf_results",
        "options",
        "problem",
        "line_states",
    )

    name = 'EMT Simulation'
    tpe = SimulationTypes.EmtDynamic_run

    """
    Dynamic wrapper to use with Qt
    """

    def __init__(self,
                 grid: MultiCircuit,
                 options: EmtOptions,
                 pf_results_3ph: PowerFlowResults3Ph | None = None,
                 pf_results: PowerFlowResults | None = None,
                 engine: EngineType = EngineType.VeraGrid) -> None:
        """
        DynamicDriver class constructor
        :param grid: MultiCircuit instance
        :param options: EmtOptions instance (optional)
        :param pf_results_3ph: PowerFlowResults3ph
        :param pf_results: PowerFlowResults
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        self.grid = grid

        self.pf_results_3Ph: PowerFlowResults3Ph | None = pf_results_3ph

        self.pf_results: PowerFlowResults | None = pf_results

        self.options = options

        self.results: EmtResults | None = None
        self.problem: EmtProblemDae | None = None

        self.line_states = {}

    def run(self) -> None:
        """
        Main function to initialize and run the system simulation.

        This function sets up logging, starts the dynamic simulation, and
        logs the outcome. It handles and logs any exceptions raised during execution.
        :return:
        """
        # Run the dynamic simulation
        self.run_time_simulation()

    def run_time_simulation(self) -> None:
        """
        Performs the EMTP loop using the chosen method.
        :return:
        """
        self.progress_signal.emit(0)

        # set emt events groups
        emt_events_groups = (self.grid.emt_events_groups
                             if self.grid.emt_events_groups is None
                             else self.grid.emt_events_groups)

        # if self.grid.emt_events_groups is None:
        #     emt_events_groups = EmtEventsGroup(name="simulation1")
        #     self.grid.add_emt_events_group(emt_events_groups)
        # else:
        #     emt_events_groups = self.grid.emt_events_groups

        emt_events_group_names: StrVec = np.array([elm.name for elm in emt_events_groups])
        emt_events_group_idtags: StrVec = np.array([str(elm.idtag) for elm in emt_events_groups])

        steps = int(np.ceil((self.options.simulation_time - 0) / self.options.time_step))
        t: Vec = np.arange(steps + 1) * self.options.time_step

        # initialize buses
        # for bus in self.grid.buses:
        #     get_bus_emt_template(self.grid, bus)

        # create the problem
        if self.is_cancel():
            self.report_text("Cancelled!")
            return

        problem = build_emt_problem(
            grid=self.grid,
            options=self.options,
            pf_results=self.pf_results,
            pf_results_3ph=self.pf_results_3Ph,
            progress_signal=self.progress_signal,
            logger= self.logger,
        )
        self.problem = problem

        if self.is_cancel():
            self.report_text("Cancelled!")
            return


        # create the results
        # The results container keeps the full declared event-group layout so
        # downstream code can preserve stable event-group identities. The extra
        # availability mask records which of those declared groups are actually
        # simulated in this run, which is the information the plot binder needs.
        has_event_group_results: np.ndarray = np.array([bool(elm.active) for elm in emt_events_groups], dtype=bool)
        self.results = EmtResults(
            time_array=pd.DatetimeIndex(pd.to_datetime(t * 1e9)),
            emt_events_group_names=emt_events_group_names,
            emt_events_group_idtags=emt_events_group_idtags,
            variables=self.problem.state_and_algebraic_vars(),
            diff_variables=self.problem.get_diff_vars(),
            uid2idx_vars=self.problem.uid2idx_vars,
            uid2idx_diff=self.problem.uid2idx_diff,
            vars_glob_name2uid=self.problem.vars_glob_name2uid,
            devices_vars_info=self.problem.get_device_vars_dict(),
            initial_parameter_value_maps=[dict() for _ in range(len(emt_events_groups))],
            parameter_value_maps=[dict() for _ in range(len(emt_events_groups))],
            has_event_group_results=has_event_group_results,
        )

        newton_diag_config = NewtonDiagnosticsConfig(
            step_norm_explode=self.options.newton_step_norm_explode,
            dense_cond_warn=self.options.newton_dense_cond_warn,
            compute_dense_cond=self.options.newton_compute_dense_cond,
            dense_cond_max_n=self.options.newton_dense_cond_max_n,
            enable_fallback=self.options.newton_enable_fallback,
            enable_index1_check=self.options.newton_enable_index1_check,
            index1_max_block_n=self.options.newton_index1_max_block_n,
            index1_warn_pivot_ratio=self.options.newton_index1_warn_pivot_ratio,
            index1_fail_pivot_ratio=self.options.newton_index1_fail_pivot_ratio,
            enable_backtracking=self.options.newton_enable_backtracking,
            backtracking_beta=self.options.newton_backtracking_beta,
            backtracking_min_alpha=self.options.newton_backtracking_min_alpha,
            backtracking_max_iter=self.options.newton_backtracking_max_iter,
        )


        for group_idx, emt_events_group in enumerate(emt_events_groups):

            if self.is_cancel():
                self.report_text("Cancelled!")
                return

            if emt_events_group.active:

                self.report_text("Simulating EMT event group " + emt_events_group.name)

                self.progress_signal.emit(11)

                self.report_text("Simulating EMT event group " + emt_events_group.name)
                problem.set_events_group(emt_events_group=emt_events_group)

                self.report_text(
                    f"Simulating EMT event group  {emt_events_group.name} with "
                    f"{self.options.integration_method.value}"
                )

                solver = build_emt_solver(
                    options=self.options,
                    problem=problem,
                    t0=0.0,
                    t_end=self.options.simulation_time,
                    h=self.options.time_step,
                    method=self.options.integration_method,
                    newton_diag_config=newton_diag_config,
                    progress_signal=self.progress_signal,
                    cancel_checker=self.is_cancel,
                    logger=self.logger,
                )

                native_session: ManufacturerNativeRuntimeSession | None = None
                if len(self.grid.manufacturer_native_models) > 0:
                    native_session = ManufacturerNativeRuntimeSession(
                        providers=self.grid.manufacturer_native_models,
                        platform=None,
                        limits=NativeWorkerLimits(),
                        logger=self.logger,
                    )
                    try:
                        problem.resolve_manufacturer_native_boundary(native_session)
                    except BaseException:
                        native_session.close()
                        raise
                else:
                    pass

                # EMT runtime parameters are initialized by problem/solver
                # construction. Snapshot them now, before any event evolution.
                self.results.initial_parameter_value_maps[group_idx] = _collect_emt_group_parameter_values(
                    problem=problem,
                    grid=self.grid,
                )
                boundary_updater: EmtProblemDae | CompositeEmtBoundaryUpdater = build_emt_boundary_updater(problem)
                try:
                    # The solver uses the FMU-aware wrapper when native adapters
                    # are present and the original problem otherwise.
                    t, y, dy, well_initialized, converged = solver.simulate(boundary_updater=boundary_updater)
                finally:
                    # The driver creates this wrapper, so it also owns releasing
                    # every native runtime on success, failure, or cancellation.
                    if isinstance(boundary_updater, CompositeEmtBoundaryUpdater):
                        boundary_updater.close()
                    else:
                        pass
                    problem.resolve_manufacturer_native_boundary(None)
                    if native_session is not None:
                        native_session.close()
                    else:
                        pass

                if self.is_cancel():
                    self.report_text("Cancelled!")
                    return

                if converged and well_initialized:
                    print(f"Event group {emt_events_group} successfully simulated.")
                    self.report_text(
                        f"Event group {emt_events_group} successfully simulated.")
                else:
                    init_summary: str = ""
                    if problem.initialization_report is None:
                        pass
                    else:
                        init_summary = (
                            f" init_status={problem.initialization_report.status.name}"
                            f", init_method={problem.initialization_report.method_used}"
                            f", init_res0={problem.initialization_report.initial_residual_inf:.3e}"
                            f", init_resf={problem.initialization_report.final_residual_inf:.3e}"
                        )
                    print(
                        f"Event group {emt_events_group} finished with EMT Newton failures "
                        f"(well_initialized={well_initialized}, converged={converged}).{init_summary}"
                    )
                    self.report_text(
                        f"Event group {emt_events_group} finished with EMT Newton failures "
                        f"(well_initialized={well_initialized}, converged={converged}).{init_summary}"
                    )

                print(f"converged ={converged}")
                print(f"well_initialized ={well_initialized}")
                # Qualification belongs to the existing initialization report.
                if problem.initialization_report is None:
                    pass
                else:
                    initialization_summary: str = (
                        f"Initialization status={problem.initialization_report.status.name}: "
                        f"{problem.initialization_report.message}"
                    )
                    print(initialization_summary)
                    self.report_text(initialization_summary)
                first_step_states_unchanged: bool | None
                if well_initialized:
                    first_step_states_unchanged = _compare_first_step_non_angle_states(
                        values=y,
                        state_vars=problem.get_state_vars(),
                    )
                else:
                    first_step_states_unchanged = None

                if first_step_states_unchanged is None:
                    self.report_text(
                        "First-step non-angle EMT state comparison is unavailable because "
                        "initialization failed or comparable finite samples were not produced."
                    )
                else:
                    if first_step_states_unchanged:
                        self.report_text(
                            "Non-angle EMT states remained unchanged between the initial sample "
                            "and the first integration sample."
                        )
                    else:
                        self.report_text(
                            "Non-angle EMT states changed between the initial sample and the first "
                            "integration sample. This sample comparison does not by itself indicate "
                            "failed initialization; periodic AC states normally evolve in time."
                        )

                # Persist the solver status in the shared results object so the
                # GUI post-processing stage reports the actual simulation
                # outcome instead of the default False placeholders.
                self.results.converged[group_idx] = converged
                self.results.well_initialized[group_idx] = well_initialized
                # Keep the declared group/time layout while marking uncomputed rows.
                completed_samples: int = y.shape[0]
                self.results.values[:completed_samples, :, group_idx] = y
                self.results.diff_values[:completed_samples, :, group_idx] = dy
                self.results.values[completed_samples:, :, group_idx] = np.nan
                self.results.diff_values[completed_samples:, :, group_idx] = np.nan
                self.results.parameter_value_maps[group_idx] = _collect_emt_group_parameter_values(
                    problem=problem,
                    grid=self.grid,
                )

                self.progress_signal.emit(90)

            else:
                self.report_text( emt_events_group.name + "skipped")

        self.progress_signal.emit(100)
