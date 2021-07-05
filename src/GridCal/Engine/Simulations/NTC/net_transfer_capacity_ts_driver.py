# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import time
import json
import numpy as np
import pandas as pd

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit
import GridCal.Engine.Simulations.LinearFactors.linear_analysis as la
from GridCal.Engine.Simulations.NTC.net_transfer_capacity_driver import NetTransferCapacityOptions, compute_ntc, compute_alpha
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import TSDriverTemplate


class NetTransferCapacityTimeSeriesResults(ResultsTemplate):

    def __init__(self, n_br, n_bus, time_array, br_names, bus_names, bus_types):
        """

        :param n_br:
        :param n_bus:
        :param time_array:
        :param br_names:
        :param bus_names:
        :param bus_types:
        """
        ResultsTemplate.__init__(self,
                                 name='ATC Time Series Results',
                                 available_results=[
                                                     ResultTypes.NetTransferCapacity,
                                                     ResultTypes.NetTransferCapacityN,
                                                     ResultTypes.NetTransferCapacityAlpha,
                                                     ResultTypes.NetTransferCapacityReport
                                                    ],
                                 data_variables=['alpha',
                                                 'beta',
                                                 'atc',
                                                 'atc_n',
                                                 'atc_limiting_contingency_branch',
                                                 'atc_limiting_contingency_flow',
                                                 'base_flow',
                                                 'rates',
                                                 'contingency_rates',
                                                 'report',
                                                 'report_headers',
                                                 'report_indices',
                                                 'branch_names',
                                                 'bus_names',
                                                 'bus_types',
                                                 'branch_names'])
        self.n_br = n_br
        self.n_bus = n_bus
        self.nt = len(time_array)
        self.time_array = time_array
        self.branch_names = br_names
        self.bus_names = bus_names
        self.bus_types = bus_types

        # available transfer capacity matrix (branch, contingency branch)
        self.rates = np.zeros((self.nt, self.n_br))
        self.contingency_rates = np.zeros((self.nt, self.n_br))

        self.alpha = np.zeros((self.nt, self.n_br))
        self.atc = np.zeros((self.nt, self.n_br))
        self.atc_n = np.zeros((self.nt, self.n_br))

        self.beta = np.zeros((self.nt, self.n_br))
        self.atc_limiting_contingency_branch = np.zeros((self.nt, self.n_br), dtype=int)
        self.atc_limiting_contingency_flow = np.zeros((self.nt, self.n_br))
        self.base_flow = np.zeros((self.nt, self.n_br))

        self.report = np.empty((self.n_br, 10), dtype=object)
        self.report_headers = ['Branch',
                               'Base flow',
                               'Rate',
                               'Alpha',
                               'ATC normal',
                               'Limiting contingency branch',
                               'Limiting contingency flow',
                               'Contingency rate',
                               'Beta',
                               'ATC']
        self.report_indices = self.time_array

    def get_steps(self):
        return

    def make_report(self, prog_func=None):
        """

        :return:
        """
        dim = self.n_br
        self.report_headers = ['Branch',
                               'Base flow (avg)',
                               'Base flow (min)',
                               'Base flow (max)',
                               'Rate (min)',
                               'Rate (max)',
                               'Alpha (avg)',
                               'Alpha (min)',
                               'Alpha (max)',
                               'ATC normal (avg)',
                               'ATC normal (min)',
                               'ATC normal (max)',
                               'Limiting contingency branch',
                               'Limiting contingency flow (avg)',
                               'Limiting contingency flow (min)',
                               'Limiting contingency flow (max)',
                               'Contingency rate (min)',
                               'Contingency rate (max)',
                               'Beta (avg)',
                               'Beta (min)',
                               'Beta (max)',
                               'ATC (avg)',
                               'ATC (min)',
                               'ATC (max)']
        self.report = np.empty((dim, len(self.report_headers)), dtype=object)
        self.report_indices = np.arange(dim)

        for i in range(self.n_br):
            self.report[i, 0] = self.branch_names[i]

            self.report[i, 1] = self.base_flow[:, i].mean()
            self.report[i, 2] = self.base_flow[:, i].min()
            self.report[i, 3] = self.base_flow[:, i].max()

            self.report[i, 4] = self.rates[:, i].min()
            self.report[i, 5] = self.rates[:, i].max()

            self.report[i, 6] = self.alpha[:, i].mean()
            self.report[i, 7] = self.alpha[:, i].min()
            self.report[i, 8] = self.alpha[:, i].max()

            self.report[i, 9] = self.atc_n[:, i].mean()
            self.report[i, 10] = self.atc_n[:, i].min()
            self.report[i, 11] = self.atc_n[:, i].max()

            # self.report[i, 12] = self.branch_names[self.atc_limiting_contingency_branch[t, i]]
            self.report[i, 12] = ''

            self.report[i, 13] = self.atc_limiting_contingency_flow[:, i].mean()
            self.report[i, 14] = self.atc_limiting_contingency_flow[:, i].min()
            self.report[i, 15] = self.atc_limiting_contingency_flow[:, i].max()

            self.report[i, 16] = self.contingency_rates[:, i].min()
            self.report[i, 17] = self.contingency_rates[:, i].max()

            self.report[i, 18] = self.beta[:, i].mean()
            self.report[i, 19] = self.beta[:, i].min()
            self.report[i, 20] = self.beta[:, i].max()

            self.report[i, 21] = self.atc[:, i].mean()
            self.report[i, 22] = self.atc[:, i].min()
            self.report[i, 23] = self.atc[:, i].max()

            if prog_func is not None:
                prog_func((i+1) / self.n_br * 100)

        # sort by ATC min
        idx = np.argsort(self.report[:, 22].astype(float))
        self.report = self.report[idx, :]

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'atc': self.atc.tolist(),
                'atc_limiting_contingency_flow': self.atc_limiting_contingency_flow.tolist(),
                'base_flow': self.base_flow,
                'atc_limiting_contingency_branch': self.atc_limiting_contingency_branch}
        return data

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        index = pd.to_datetime(self.time_array)

        if result_type == ResultTypes.NetTransferCapacity:
            data = self.atc
            y_label = '(MW)'
            title, _ = result_type.value
            labels = self.branch_names

        elif result_type == ResultTypes.NetTransferCapacityN:
            data = self.atc_n
            y_label = '(MW)'
            title, _ = result_type.value
            labels = self.branch_names

        elif result_type == ResultTypes.NetTransferCapacityAlpha:
            data = self.alpha
            y_label = '(p.u.)'
            title, _ = result_type.value
            labels = self.branch_names

        elif result_type == ResultTypes.NetTransferCapacityReport:
            data = np.array(self.report)
            y_label = ''
            title, _ = result_type.value
            index = self.report_indices
            labels = self.report_headers
        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsModel(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl


class NetTransferCapacityTimeSeriesDriver(TSDriverTemplate):
    tpe = SimulationTypes.NetTransferCapacityTS_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: NetTransferCapacityOptions, start_=0, end_=None):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        @:param pf_results: PowerFlowResults, this is to get the Sf
        """
        TSDriverTemplate.__init__(self,
                                  grid=grid,
                                  start_=start_,
                                  end_=end_)

        # Options to use
        self.options = options

        # OPF results
        self.results = NetTransferCapacityTimeSeriesResults(n_br=0,
                                                            n_bus=0,
                                                            time_array=[],
                                                            br_names=[],
                                                            bus_names=[],
                                                            bus_types=[])

    def run(self):
        """
        Run thread
        """
        start = time.time()

        self.progress_signal.emit(0)

        time_indices = self.get_time_indices()

        # declare the linear analysis
        self.progress_text.emit('Analyzing...')
        linear_analysis = la.LinearAnalysis(grid=self.grid,
                                            distributed_slack=self.options.distributed_slack,
                                            correct_values=self.options.correct_values)
        linear_analysis.run()

        nc = compile_time_circuit(self.grid)
        # ne = nc.nbr
        # nc = nc.nbr
        nt = len(nc.time_array)

        # declare the results
        self.results = NetTransferCapacityTimeSeriesResults(n_br=nc.nbr,
                                                            n_bus=nc.nbus,
                                                            time_array=nc.time_array,
                                                            br_names=nc.branch_names,
                                                            bus_names=nc.bus_names,
                                                            bus_types=nc.bus_types)

        # compute the base Sf
        P = nc.Sbus.real  # these are in p.u.
        flows = linear_analysis.get_flows_time_series(P)  # will be converted to MW internally
        contingency_rates = nc.ContingencyRates.T
        rates = nc.Rates.T

        # these results can be copied directly
        self.results.base_flow = flows
        self.results.rates = rates
        self.results.contingency_rates = contingency_rates

        for t in time_indices:

            if self.progress_text is not None:
                self.progress_text.emit('Available transfer capacity at ' + str(self.grid.time_profile[t]))

            # compute the branch exchange sensitivity (alpha)
            alpha = compute_alpha(ptdf=linear_analysis.PTDF,
                                  P0=P[:, t],  # no problem that there are in p.u., are only used for the sensitivity
                                  Pinstalled=nc.bus_installed_power,
                                  idx1=self.options.bus_idx_from,
                                  idx2=self.options.bus_idx_to,
                                  bus_types=nc.bus_types_prof(t),
                                  dT=self.options.dT,
                                  mode=self.options.mode.value)

            # compute NTC
            beta_mat, beta_used, atc_n, atc_final, \
            atc_limiting_contingency_branch, \
            atc_limiting_contingency_flow = compute_ntc(ptdf=linear_analysis.PTDF,
                                                        lodf=linear_analysis.LODF,
                                                        alpha=alpha,
                                                        flows=flows[t, :],
                                                        rates=rates[t, :],
                                                        contingency_rates=contingency_rates[t, :],
                                                        threshold=self.options.threshold
                                                        )

            # post-process and store the results
            self.results.alpha[t, :] = alpha
            self.results.atc[t, :] = atc_final
            self.results.atc_n[t, :] = atc_n
            self.results.beta[t, :] = beta_used
            self.results.atc_limiting_contingency_branch[t, :] = atc_limiting_contingency_branch.astype(int)
            self.results.atc_limiting_contingency_flow[t, :] = atc_limiting_contingency_flow

            if self.progress_signal is not None:
                self.progress_signal.emit((t + 1) / nt * 100)

            if self.__cancel__:
                break

        self.progress_text.emit('Building the report...')
        self.results.make_report(prog_func=self.progress_signal.emit)

        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v for v in self.results.branch_names]
        else:
            return list()

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':

    from GridCal.Engine import PowerFlowOptions, FileOpen, LinearAnalysis, PowerFlowDriver, SolverType
    fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    simulation_ = LinearAnalysis(grid=main_circuit)
    simulation_.run()

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  retry_with_other_methods=True)
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()

    options = NetTransferCapacityOptions()
    driver = NetTransferCapacityTimeSeriesDriver(main_circuit, options, power_flow.results)
    driver.run()

    print()

