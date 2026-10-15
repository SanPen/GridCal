# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import time
import pandas as pd
import numpy as np
from typing import Dict

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_vectorized import RmsProblemDaeVec
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_vectorized import BackEulerImplicitIntegrationVec
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_full_vectorized import BackEulerImplicitIntegrationFullVec
from VeraGridEngine.Simulations.dynamic_parameter_results import collect_declared_dynamic_parameter_values
from VeraGridEngine.enumerations import EngineType, SimulationTypes, DynamicIntegrationMethod
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from VeraGridEngine.basic_structures import Vec, StrVec
from VeraGridEngine.enumerations import PlotSimulationType, RmsProblemTypes
from VeraGridEngine.IO.manufacturer_native.runtime_session import ManufacturerNativeRuntimeSession
from VeraGridEngine.IO.native_runtime import NativeWorkerLimits


def _collect_rms_group_parameter_values(problem: RmsProblemDae | RmsProblemDaeVec,
                                        grid: MultiCircuit) -> Dict[str, float]:
    """
    Export one event-group parameter snapshot from the RMS problem.

    :param problem: Solved RMS problem instance.
    :param grid: Circuit containing the configured RMS model parameters.
    :return: Parameter scalar map keyed by ``device_idtag:param_name``.
    """
    parameter_values: Dict[str, float] = collect_declared_dynamic_parameter_values(
        grid=grid,
        simulation_type=PlotSimulationType.RMS,
        # Mapping diagnostics were already emitted while constructing the
        # problem. Result export must remain read-only and must not duplicate
        # the same information entry for every event-group snapshot.
        logger=None,
    )
    event_parameter_count: int = len(problem._variable_parameters)
    parameter_index: int

    # Runtime parameters override a same-name static declaration because these
    # values are the ones actually consumed by the selected event group.
    if problem._variable_parameters_values is not None:
        for parameter_index in range(event_parameter_count):
            parameter_var = problem._variable_parameters[parameter_index]
            device_idtag: str | None = problem._event_parameter_device_idtags.get(parameter_var.uid, None)
            if device_idtag is not None:
                parameter_key: str = str(device_idtag) + ":" + str(parameter_var.name)
                parameter_values[parameter_key] = float(problem._variable_parameters_values[parameter_index])
            else:
                pass
    else:
        pass

    return parameter_values


class RmsSimulationDriver(DriverTemplate):
    __slots__ = (
        "pf_results",
        "options",
        "problem",
    )

    name = 'Rms Simulation'
    tpe = SimulationTypes.RmsDynamic_run

    """
    Dynamic wrapper to use with Qt
    """

    def __init__(self,
                 grid: MultiCircuit,
                 options: RmsOptions,
                 pf_results: PowerFlowResults,
                 engine: EngineType = EngineType.VeraGrid):
        """
        DynamicDriver class constructor
        :param grid: MultiCircuit instance
        :param options: RmsOptions instance
        :param pf_results: PowerFlowResults
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        self.grid = grid

        self.pf_results: PowerFlowResults = pf_results

        self.options = options

        self.results: RmsResults | None = None
        self.problem: RmsProblemDae | None = None

    def run(self):
        """
        Main function to initialize and run the system simulation.

        This function sets up logging, starts the dynamic simulation, and
        logs the outcome. It handles and logs any exceptions raised during execution.
        :return:
        """
        # Run the dynamic simulation
        self.run_time_simulation()

    def run_time_simulation(self):
        """
        Performs the numerical integration using the chosen method.
        :return:
        """

        self.progress_signal.emit(0)

        rms_events_groups = (self.grid.rms_events_groups
                             if self.grid.rms_events_groups is None
                             else self.grid.rms_events_groups)

        steps = int(np.ceil((self.options.simulation_time - 0) / self.options.time_step))
        t: Vec = np.arange(steps + 1) * self.options.time_step

        rms_events_group_names: StrVec = np.array([elm.name for elm in rms_events_groups])
        rms_events_group_idtags: StrVec = np.array([str(elm.idtag) for elm in rms_events_groups])

        # self.options.problem_type = RmsProblemTypes.PowerBalanceVectorized
        # self.options.problem_type = RmsProblemTypes.PowerBalanceFullVectorized

        if self.is_cancel():
            self.report_text("Cancelled!")
            return

        problem = build_rms_problem(
            grid=self.grid,
            options=self.options,
            pf_results=self.pf_results,
            progress_signal=self.progress_signal,
            logger=self.logger,
        )
        self.problem = problem

        if self.is_cancel():
            self.report_text("Cancelled!")
            return

        # The results container keeps the full declared event-group layout so
        # downstream code can preserve stable event-group identities. The extra
        # availability mask records which of those declared groups are actually
        # simulated in this run, which is the information the plot binder needs.
        has_event_group_results: np.ndarray = np.zeros(len(rms_events_groups), dtype=bool)
        self.results = RmsResults(
            time_array=pd.DatetimeIndex(pd.to_datetime(t * 1e9)),
            rms_events_group_names=rms_events_group_names,
            rms_events_group_idtags=rms_events_group_idtags,
            variables=problem.state_and_algebraic_vars,
            uid2idx=problem.uid2idx_vars,
            vars_glob_name2uid=problem.vars_glob_name2uid,
            devices_vars_info=problem.get_device_vars_dict(),
            initial_parameter_value_maps=[dict() for _ in range(len(rms_events_groups))],
            parameter_value_maps=[dict() for _ in range(len(rms_events_groups))],
            has_event_group_results=has_event_group_results,
        )

        for group_idx, rms_events_group in enumerate(rms_events_groups):

            if self.is_cancel():
                self.report_text("Cancelled!")
                return

            if rms_events_group.active:

                self.report_text("Simulating RMS event group " + rms_events_group.name)

                self.progress_signal.emit(5)

                self.report_text("Simulating RMS event group " + rms_events_group.name)
                problem.set_events_group(rms_events_group=rms_events_group)
                problem.reset_boundary_update_state(0.0)

                # DaeTrapezoidal = "DAE_Trapezoidal"
                # DaeBackEuler = "DAE_BackEuler"
                # DaeBDF2 = "DAE_bdf2"
                # DaeContinuous = "DAE_Continuous"
                # OdeRungeKutta4 = "ODE_Runge_Kutta 4"
                # OdeEuler = "ODE_Euler"

                if self.options.integration_method == DynamicIntegrationMethod.DaeBackEuler:

                    self.report_text(
                        f"Simulating RMS event group  {rms_events_group.name} with "
                        f"{self.options.integration_method.value}"
                    )

                    if self.options.problem_type == RmsProblemTypes.PowerBalance:
                        solver = BackEulerImplicitIntegration(
                            problem=problem,
                            t0=0,
                            t_end=self.options.simulation_time,
                            h=self.options.time_step,
                            max_iter=self.options.max_iter,
                            tolerance=self.options.tolerance,
                            cancel_checker=self.is_cancel,
                        )

                    elif self.options.problem_type == RmsProblemTypes.PowerBalanceVectorized:
                        solver = BackEulerImplicitIntegrationVec(
                            problem=problem,
                            t0=0,
                            t_end=self.options.simulation_time,
                            h=self.options.time_step,
                            max_iter=self.options.max_iter,
                            tolerance=self.options.tolerance,
                            cancel_checker=self.is_cancel,
                        )

                    elif self.options.problem_type == RmsProblemTypes.PowerBalanceFullVectorized:
                        solver = BackEulerImplicitIntegrationFullVec(
                            problem=problem,
                            t0=0,
                            t_end=self.options.simulation_time,
                            h=self.options.time_step,
                            max_iter=self.options.max_iter,
                            tolerance=self.options.tolerance,
                            cancel_checker=self.is_cancel,
                        )

                else:
                    self.logger.add_info("Falling back to DAE-BackEuler method")

                    self.report_text(
                        f"Simulating RMS event group  {rms_events_group.name} with back euler as fallback"
                    )

                    if self.options.problem_type == RmsProblemTypes.PowerBalance:
                        solver = BackEulerImplicitIntegration(
                            problem=problem,
                            t0=0,
                            t_end=self.options.simulation_time,
                            h=self.options.time_step,
                            max_iter=self.options.max_iter,
                            tolerance=self.options.tolerance,
                            cancel_checker=self.is_cancel,
                        )

                    elif self.options.problem_type == RmsProblemTypes.PowerBalanceVectorized:
                        solver = BackEulerImplicitIntegrationVec(
                            problem=problem,
                            t0=0,
                            t_end=self.options.simulation_time,
                            h=self.options.time_step,
                            max_iter=self.options.max_iter,
                            tolerance=self.options.tolerance,
                            cancel_checker=self.is_cancel,
                        )

                    elif self.options.problem_type == RmsProblemTypes.PowerBalanceFullVectorized:
                        solver = BackEulerImplicitIntegrationFullVec(
                            problem=problem,
                            t0=0,
                            t_end=self.options.simulation_time,
                            h=self.options.time_step,
                            max_iter=self.options.max_iter,
                            tolerance=self.options.tolerance,
                            cancel_checker=self.is_cancel,
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
                        problem._set_manufacturer_native_runtime_session(native_session)
                    except BaseException:
                        native_session.close()
                        raise
                else:
                    pass
                _t_start = time.time()
                # Capture the complete scalar state before the solver applies
                # any step or ramp belonging to this event group.
                self.results.initial_parameter_value_maps[group_idx] = _collect_rms_group_parameter_values(
                    problem=problem,
                    grid=self.grid,
                )
                try:
                    t, y, well_initialized, converged = solver.simulate()
                finally:
                    problem._set_manufacturer_native_runtime_session(None)
                    if native_session is not None:
                        native_session.close()
                    else:
                        pass
                _t_end = time.time()
                # print(f"RMS simulation time: {_t_end - _t_start:.4f} s")

                if self.is_cancel():
                    self.report_text("Cancelled!")
                    return

                self.results.converged[group_idx] = converged
                self.results.well_initialized[group_idx] = well_initialized
                sample_count: int = min(self.results.values.shape[0], y.shape[0])
                self.results.values[:sample_count, :, group_idx] = y[:sample_count, :]
                if sample_count < self.results.values.shape[0]:
                    self.results.values[sample_count:, :, group_idx] = np.nan
                self.results.has_event_group_results[group_idx] = sample_count > 0
                self.results.parameter_value_maps[group_idx] = _collect_rms_group_parameter_values(
                    problem=problem,
                    grid=self.grid,
                )

                if not well_initialized:
                    self.logger.add_warning("Not well initialized", device=rms_events_group.name)

                if not converged:
                    self.logger.add_warning(
                        f"RMS stopped after {sample_count} accepted samples; "
                        f"last completed time is {t[sample_count - 1]:g} s",
                        device=rms_events_group.name,
                    )

                self.progress_signal.emit(90)

            else:
                self.report_text(rms_events_group.name + " skipped")

        self.progress_signal.emit(100)
