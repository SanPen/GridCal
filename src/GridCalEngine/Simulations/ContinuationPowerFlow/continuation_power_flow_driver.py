# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from typing import Union
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow import continuation_nr
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_options import ContinuationPowerFlowOptions
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_input import ContinuationPowerFlowInput
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_results import ContinuationPowerFlowResults
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate


class ContinuationPowerFlowDriver(DriverTemplate):
    name = 'Continuation Power Flow'
    tpe = SimulationTypes.ContinuationPowerFlow_run

    def __init__(self, grid: MultiCircuit,
                 options: ContinuationPowerFlowOptions,
                 inputs: ContinuationPowerFlowInput,
                 pf_options: PowerFlowOptions,
                 opf_results=None, t=0):
        """
        ContinuationPowerFlowDriver constructor
        :param grid: NumericalCircuit instance
        :param options: ContinuationPowerFlowOptions instance
        :param inputs: ContinuationPowerFlowInput instance
        :param pf_options: PowerFlowOptions instance
        :param opf_results:
        """

        DriverTemplate.__init__(self, grid=grid)

        # voltage stability options
        self.options = options

        self.inputs = inputs

        self.pf_options = pf_options

        self.opf_results = opf_results

        self.t = t

        self.results = ContinuationPowerFlowResults(nval=0,
                                                    nbus=self.grid.get_bus_number(),
                                                    nbr=self.grid.get_branch_number_wo_hvdc(),
                                                    bus_names=self.grid.get_bus_names(),
                                                    branch_names=self.grid.get_branch_names_wo_hvdc(),
                                                    bus_types=np.ones(self.grid.get_bus_number()))

    def get_steps(self):
        """
        List of steps
        """
        if self.results.lambdas is not None:
            return ['Lambda:' + str(l) for l in self.results.lambdas]
        else:
            return list()

    def progress_callback(self, lmbda: float) -> None:
        """
        Send progress report
        :param lmbda: lambda value
        :return: None
        """
        self.report_text('Running continuation power flow (lambda:' + "{0:.2f}".format(lmbda) + ')...')

    def run_at(self, t_idx: Union[int, None] = None) -> ContinuationPowerFlowResults:
        """
        run the voltage collapse simulation
        @return: ContinuationPowerFlowResults
        """
        self.tic()
        nc = compile_numerical_circuit_at(circuit=self.grid,
                                          t_idx=t_idx,
                                          apply_temperature=self.pf_options.apply_temperature_correction,
                                          branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode,
                                          opf_results=self.opf_results,
                                          logger=self.logger)

        islands = nc.split_into_islands(ignore_single_node_islands=self.pf_options.ignore_single_node_islands)

        result_series = list()

        for is_idx, island in enumerate(islands):

            self.report_text(f'Running voltage collapse at circuit island {is_idx + 1}...')
            adm = island.get_admittance_matrices()
            idx = nc.get_simulation_indices()

            if len(idx.vd) > 0 and len(idx.no_slack) > 0:

                Qmax_bus, Qmin_bus = island.get_reactive_power_limits()

                results = continuation_nr(Ybus=adm.Ybus,
                                          Cf=island.passive_branch_data.Cf,
                                          Ct=island.passive_branch_data.Ct,
                                          Yf=adm.Yf,
                                          Yt=adm.Yt,
                                          branch_rates=island.passive_branch_data.rates,
                                          Sbase=island.Sbase,
                                          Sbus_base=self.inputs.Sbase[island.bus_data.original_idx],
                                          Sbus_target=self.inputs.Starget[island.bus_data.original_idx],
                                          V=self.inputs.Vbase[island.bus_data.original_idx],
                                          distributed_slack=self.pf_options.distributed_slack,
                                          bus_installed_power=island.bus_data.installed_power,
                                          vd=idx.vd,
                                          pv=idx.pv,
                                          pq=idx.pq,
                                          pqv=idx.pqv,
                                          p=idx.p,
                                          step=self.options.step,
                                          approximation_order=self.options.approximation_order,
                                          adapt_step=self.options.adapt_step,
                                          step_min=self.options.step_min,
                                          step_max=self.options.step_max,
                                          error_tol=self.options.step_tol,
                                          tol=self.options.solution_tol,
                                          max_it=self.options.max_it,
                                          stop_at=self.options.stop_at,
                                          control_q=self.pf_options.control_Q,
                                          control_remote_voltage=self.pf_options.control_remote_voltage,
                                          qmax_bus=Qmax_bus,
                                          qmin_bus=Qmin_bus,
                                          original_bus_types=island.bus_data.bus_types,
                                          base_overload_number=self.inputs.base_overload_number,
                                          verbose=False,
                                          call_back_fx=self.progress_callback)

                # store the result series
                result_series.append(results)

        # analyze the result series to compact all the results into one object
        if len(result_series) > 0:
            max_len = max([len(r) for r in result_series])
        else:
            max_len = 0

            # declare results
        self.results = ContinuationPowerFlowResults(nval=max_len,
                                                    nbus=nc.nbus,
                                                    nbr=nc.nbr,
                                                    bus_names=nc.bus_data.names,
                                                    branch_names=nc.passive_branch_data.names,
                                                    bus_types=nc.bus_data.bus_types)

        # fill extra info for area manipulation
        self.results.fill_circuit_info(grid=self.grid)

        for i in range(len(result_series)):
            if len(result_series[i]) > 0:
                self.results.apply_from_island(result_series[i],
                                               islands[i].bus_data.original_idx,
                                               islands[i].passive_branch_data.original_idx)

        if nc.topology_performed:
            self.results.voltage = nc.propagate_bus_result_mat(self.results.voltage)

        self.toc()
        return self.results

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        self.run_at(t_idx=None)
