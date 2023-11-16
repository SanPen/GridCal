# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow import continuation_nr
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_options import ContinuationPowerFlowOptions
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_input import ContinuationPowerFlowInput
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_results import ContinuationPowerFlowResults
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate


class ContinuationPowerFlowDriver(DriverTemplate):
    name = 'Continuation Power Flow'
    tpe = SimulationTypes.ContinuationPowerFlow_run

    def __init__(self, circuit: MultiCircuit,
                 options: ContinuationPowerFlowOptions,
                 inputs: ContinuationPowerFlowInput,
                 pf_options: PowerFlowOptions,
                 opf_results=None, t=0):
        """
        ContinuationPowerFlowDriver constructor
        :param circuit: NumericalCircuit instance
        :param options: ContinuationPowerFlowOptions instance
        :param inputs: ContinuationPowerFlowInput instance
        :param pf_options: PowerFlowOptions instance
        :param opf_results:
        """

        DriverTemplate.__init__(self, grid=circuit)

        # voltage stability options
        self.options = options

        self.inputs = inputs

        self.pf_options = pf_options

        self.opf_results = opf_results

        self.t = t

        self.results = None

    def get_steps(self):
        """
        List of steps
        """
        if self.results.lambdas is not None:
            return ['Lambda:' + str(l) for l in self.results.lambdas]
        else:
            return list()

    def progress_callback(self, lmbda):
        """
        Send progress report
        :param lmbda: lambda value
        :return: None
        """
        self.progress_text.emit('Running continuation power flow (lambda:' + "{0:.2f}".format(lmbda) + ')...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        self.tic()
        nc = compile_numerical_circuit_at(circuit=self.grid,
                                          t_idx=None,
                                          apply_temperature=self.pf_options.apply_temperature_correction,
                                          branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode,
                                          opf_results=self.opf_results)

        islands = nc.split_into_islands(ignore_single_node_islands=self.pf_options.ignore_single_node_islands)

        result_series = list()

        for island in islands:

            self.progress_text.emit('Running voltage collapse at circuit ' + str(nc) + '...')

            if len(island.vd) > 0 and len(island.pqpv) > 0:
                results = continuation_nr(Ybus=island.Ybus,
                                          Cf=island.Cf,
                                          Ct=island.Ct,
                                          Yf=island.Yf,
                                          Yt=island.Yt,
                                          branch_rates=island.branch_rates,
                                          Sbase=island.Sbase,
                                          Ibus_base=island.Ibus,
                                          Ibus_target=island.Ibus,
                                          Sbus_base=self.inputs.Sbase[island.original_bus_idx],
                                          Sbus_target=self.inputs.Starget[island.original_bus_idx],
                                          V=self.inputs.Vbase[island.original_bus_idx],
                                          distributed_slack=self.pf_options.distributed_slack,
                                          bus_installed_power=island.bus_installed_power,
                                          vd=island.vd,
                                          pv=island.pv,
                                          pq=island.pq,
                                          step=self.options.step,
                                          approximation_order=self.options.approximation_order,
                                          adapt_step=self.options.adapt_step,
                                          step_min=self.options.step_min,
                                          step_max=self.options.step_max,
                                          error_tol=self.options.error_tol,
                                          tol=self.options.tol,
                                          max_it=self.options.max_it,
                                          stop_at=self.options.stop_at,
                                          control_q=self.pf_options.control_Q,
                                          qmax_bus=island.Qmax_bus,
                                          qmin_bus=island.Qmin_bus,
                                          original_bus_types=island.bus_types,
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
                                                    bus_names=nc.bus_names,
                                                    branch_names=nc.branch_names,
                                                    bus_types=nc.bus_types)

        # fill extra info for area manipulation
        self.results.fill_circuit_info(grid=self.grid)

        for i in range(len(result_series)):
            if len(result_series[i]) > 0:
                self.results.apply_from_island(result_series[i],
                                               islands[i].original_bus_idx,
                                               islands[i].original_branch_idx)

        self.toc()
