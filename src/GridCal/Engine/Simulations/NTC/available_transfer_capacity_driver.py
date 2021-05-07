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
import numba as nb

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, make_worst_contingency_transfer_limits
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import DriverTemplate

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


@nb.njit()
def compute_transfer_indices(idx1, idx2, bus_types):
    """
    Determine the actual sending and receiving bus indices
    :param idx1:  bus indices of the sending region
    :param idx2: bus indices of the receiving region
    :param bus_types: Array of bus types (1: PQ, 2: PV, 3: Slack)
    :return: sending bus indices, receiving bus indices
    """
    idx1b = list()
    for i in idx1:
        if bus_types[i] == 2:  # 2 is for PV nodes
            idx1b.append(i)

    idx2b = list()
    for i in idx2:
        if bus_types[i] == 1:  # 1 is for PQ nodes
            idx2b.append(i)

    return np.array(idx1b), np.array(idx2b)


@nb.njit()
def compute_ntc(ptdf, lodf, P0, flows, rates, idx1, idx2, dT, threshold=0.02):
    """
    Compute all lines' ATC
    :param ptdf: Power transfer distribution factors (n-branch, n-bus)
    :param lodf: Line outage distribution factors (n-branch, n-outage branch)
    :param P0: all bus injections [MW]
    :param flows: Line Sf [MW]
    :param rates: all line rates vector
    :param idx1:  bus indices of the sending region
    :param idx2: bus indices of the receiving region
    :param dT: Transfer delta [MW]
    :param threshold: value that determines if a line is studied for the ATC calculation
    :return: ATC vector for all the lines
    """

    nbr = ptdf.shape[0]
    nbus = ptdf.shape[1]

    # declare the bus injections increment due to the transference
    dTi = np.zeros(nbus)

    # set the sending power increment proportional to the current power
    dTi[idx1] = dT * (P0[idx1] / P0[idx1].sum())

    # set the receiving power increment proportional to the current power
    dTi[idx2] = -dT * (P0[idx2] / P0[idx2].sum())

    # compute the line flow increments due to the exchange increment dT
    dFlow = ptdf.dot(dTi)

    # compute the sensitivities to the exchange
    alpha = dFlow / dT

    # explore the ATC
    atc_max = np.zeros(nbr)
    atc_min = np.zeros(nbr)
    worst_max = 0
    worst_min = 0
    worst_contingency_max = 0
    worst_contingency_min = 0

    PS_max = 0
    PS_min = 1e20

    for m in range(nbr):  # for each branch

        if abs(alpha[m]) > threshold:  # if the branch is relevant enough for the ACT...

            # explore the ATC in "N-1"
            for c in range(nbr):  # for each contingency

                if m != c:
                    # compute the OTDF
                    otdf = alpha[m] + lodf[m, c] * alpha[c]

                    # compute the contingency flow
                    contingency_flow = flows[m] + lodf[m, c] * flows[c]

                    if abs(otdf) > threshold:
                        # compute the branch+contingency ATC for each "sense" of the flow
                        alpha_ij = (rates[m] - contingency_flow) / otdf
                        beta_ij = (-rates[m] - contingency_flow) / otdf

                        #
                        alpha_p_ij = min(alpha_ij, beta_ij)
                        beta_p_ij = max(alpha_ij, beta_ij)

                        if alpha_p_ij > PS_max:
                            PS_max = alpha_p_ij
                            atc_max[m] = alpha_p_ij
                            worst_max = m
                            worst_contingency_max = c

                        if beta_p_ij < PS_min:
                            PS_min = beta_p_ij
                            atc_min[m] = alpha_p_ij
                            worst_min = m
                            worst_contingency_min = c

    if PS_min == 1e20:
        PS_min = 0.0

    return alpha, atc_max, atc_min, worst_max, worst_min, worst_contingency_max, worst_contingency_min, PS_max, PS_min


class NetTransferCapacityResults(ResultsTemplate):

    def __init__(self, n_br, n_bus, br_names, bus_names, bus_types, bus_idx_from, bus_idx_to):
        """

        :param n_br:
        :param n_bus:
        :param br_names:
        :param bus_names:
        :param bus_types:
        """
        ResultsTemplate.__init__(self,
                                 name='ATC Results',
                                 available_results=[ResultTypes.NetTransferCapacityPS,
                                                    ResultTypes.NetTransferCapacityAlpha,
                                                    ResultTypes.NetTransferCapacityReport
                                                    ],
                                 data_variables=['alpha',
                                                 'atc_max',
                                                 'atc_min',
                                                 'worst_max',
                                                 'worst_min',
                                                 'worst_contingency_max',
                                                 'worst_contingency_min',
                                                 'PS_max',
                                                 'PS_min',
                                                 'report',
                                                 'report_headers',
                                                 'report_indices',
                                                 'branch_names',
                                                 'bus_names',
                                                 'bus_types',
                                                 'bus_idx_from',
                                                 'bus_idx_to'])
        self.n_br = n_br
        self.n_bus = n_bus
        self.branch_names = br_names
        self.bus_names = bus_names
        self.bus_types = bus_types
        self.bus_idx_from = bus_idx_from
        self.bus_idx_to = bus_idx_to

        # stores the worst transfer capacities (from to) and (to from)
        self.alpha = np.zeros(self.n_br)

        self.alpha = np.zeros(self.n_br)
        self.atc_max = np.zeros(self.n_br)
        self.atc_min = np.zeros(self.n_br)
        self.worst_max = 0
        self.worst_min = 0
        self.worst_contingency_max = 0
        self.worst_contingency_min = 0
        self.PS_max = 0.0
        self.PS_min = 0.0

        self.report = np.empty((1, 8), dtype=object)
        self.report_headers = ['Branch min',
                               'Branch max',
                               'Worst Contingency min',
                               'Worst Contingency max',
                               'ATC max',
                               'ATC min',
                               'PS max',
                               'PS min']
        self.report_indices = ['All']

    def get_steps(self):
        return

    def make_report(self):
        """

        :return:
        """
        self.report = np.empty((1, 8), dtype=object)
        self.report_headers = ['Branch min',
                               'Branch max',
                               'Worst Contingency min',
                               'Worst Contingency max',
                               'ATC max',
                               'ATC min',
                               'PS max',
                               'PS min']
        self.report_indices = ['All']

        self.report[0, 0] = self.branch_names[self.worst_max]
        self.report[0, 1] = self.branch_names[self.worst_min]
        self.report[0, 2] = self.branch_names[self.worst_contingency_max]
        self.report[0, 3] = self.branch_names[self.worst_contingency_min]
        self.report[0, 4] = self.atc_max[self.worst_max]
        self.report[0, 5] = self.atc_min[self.worst_min]
        self.report[0, 6] = self.PS_max
        self.report[0, 7] = self.PS_min

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'atc_max': self.atc_max.tolist(),
                'atc_min': self.atc_min.tolist(),
                'PS_max': self.PS_max,
                'PS_min': self.PS_min}
        return data

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        index = self.branch_names

        if result_type == ResultTypes.NetTransferCapacityPS:
            data = np.array([self.PS_min, self.PS_max])
            y_label = '(MW)'
            title, _ = result_type.value
            labels = ['Power shift']
            index = ['PS min', 'PS max']
        elif result_type == ResultTypes.NetTransferCapacityAlpha:
            data = self.alpha
            y_label = '(p.u.)'
            title, _ = result_type.value
            labels = ['Sensitivity to the exchange']
            index = self.branch_names
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


class NetTransferCapacityOptions:

    def __init__(self, distributed_slack=True, correct_values=True,
                 bus_idx_from=list(), bus_idx_to=list(), dT=100.0, threshold=0.02):
        """

        :param distributed_slack:
        :param correct_values:
        :param bus_idx_from:
        :param bus_idx_to:
        :param dT:
        :param threshold:
        """
        self.distributed_slack = distributed_slack
        self.correct_values = correct_values
        self.bus_idx_from = bus_idx_from
        self.bus_idx_to = bus_idx_to
        self.dT = dT
        self.threshold = threshold


class NetTransferCapacityDriver(DriverTemplate):

    tpe = SimulationTypes.NetTransferCapacity_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: NetTransferCapacityOptions):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        @:param pf_results: PowerFlowResults, this is to get the Sf
        """
        DriverTemplate.__init__(self, grid=grid)

        # Options to use
        self.options = options

        # OPF results
        self.results = NetTransferCapacityResults(n_br=0,
                                                  n_bus=0,
                                                  br_names=[],
                                                  bus_names=[],
                                                  bus_types=[],
                                                  bus_idx_from=[],
                                                  bus_idx_to=[])

    def run(self):
        """
        Run thread
        """
        start = time.time()
        self.progress_text.emit('Analyzing')
        self.progress_signal.emit(0)

        # compile the circuit
        nc = compile_snapshot_circuit(self.grid)

        # get the converted bus indices
        idx1b, idx2b = compute_transfer_indices(idx1=self.options.bus_idx_from,
                                                idx2=self.options.bus_idx_to,
                                                bus_types=nc.bus_types)

        # declare the linear analysis
        linear = LinearAnalysis(grid=self.grid)
        linear.run()

        # declare the results
        self.results = NetTransferCapacityResults(n_br=linear.numerical_circuit.nbr,
                                                  n_bus=linear.numerical_circuit.nbus,
                                                  br_names=linear.numerical_circuit.branch_names,
                                                  bus_names=linear.numerical_circuit.bus_names,
                                                  bus_types=linear.numerical_circuit.bus_types,
                                                  bus_idx_from=idx1b,
                                                  bus_idx_to=idx2b)

        # compute NTC
        alpha, atc_max, atc_min, worst_max, worst_min, \
        worst_contingency_max, worst_contingency_min, PS_max, PS_min = compute_ntc(ptdf=linear.PTDF,
                                                                                   lodf=linear.LODF,
                                                                                   P0=nc.Sbus.real,
                                                                                   flows=linear.get_flows(nc.Sbus),
                                                                                   rates=nc.Rates,
                                                                                   idx1=idx1b,
                                                                                   idx2=idx2b,
                                                                                   dT=self.options.dT)

        # post-process and store the results
        self.results.alpha = alpha
        self.results.atc_max = atc_max
        self.results.atc_min = atc_min
        self.results.worst_max = worst_max
        self.results.worst_max = worst_max
        self.results.worst_contingency_max = worst_contingency_max
        self.results.worst_contingency_min = worst_contingency_min
        self.results.PS_max = PS_max
        self.results.PS_min = PS_min
        self.results.make_report()

        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_steps(self):
        """
        Get variations list of strings
        """
        return list()


if __name__ == '__main__':

    from GridCal.Engine import *
    fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    options = NetTransferCapacityOptions()
    driver = NetTransferCapacityDriver(main_circuit, options)
    driver.run()

    print()

