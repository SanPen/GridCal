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
from enum import Enum

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, make_worst_contingency_transfer_limits
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import DriverTemplate

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class AvailableTransferMode(Enum):
    Generation = 0
    InstalledPower = 1
    Load = 2
    GenerationAndLoad = 3


@nb.njit()
def compute_alpha(ptdf, P0, Pinstalled, idx1, idx2, bus_types, dT=1.0, mode=0):
    """
    Compute all lines' ATC
    :param ptdf: Power transfer distribution factors (n-branch, n-bus)
    :param P0: all bus injections [p.u.]
    :param idx1: bus indices of the sending region
    :param idx2: bus indices of the receiving region
    :param bus_types: Array of bus types {1: pq, 2: pv, 3: slack}
    :param dT: Exchange amount
    :param mode: Type of power shift
                 0: shift generation based on the current generated power
                 1: shift generation based on the installed power
                 2: shift load
                 3 (or else): shift using generation and load

    :return: Exchange sensitivity vector for all the lines
    """

    nbr = ptdf.shape[0]
    nbus = ptdf.shape[1]

    # declare the bus injections increment due to the transference
    dP = np.zeros(nbus)

    if mode == 0:  # move the generators based on the generated power --------------------
        # set the sending power increment proportional to the current power (Area 1)
        n1 = 0.0
        for i in idx1:
            if bus_types[i] == 2 or bus_types[i] == 3:  # it is a PV or slack node
                n1 += P0[i]

        for i in idx1:
            if bus_types[i] == 2 or bus_types[i] == 3:  # it is a PV or slack node
                dP[i] = dT * P0[i] / abs(n1)

        # set the receiving power increment proportional to the current power (Area 2)
        n2 = 0.0
        for i in idx2:
            if bus_types[i] == 2 or bus_types[i] == 3:  # it is a PV or slack node
                n2 += P0[i]

        for i in idx2:
            if bus_types[i] == 2 or bus_types[i] == 3:  # it is a PV or slack node
                dP[i] = -dT * P0[i] / abs(n2)

    elif mode == 1:  # move the generators based on the installed power --------------------

        # set the sending power increment proportional to the current power (Area 1)
        n1 = 0.0
        for i in idx1:
            if bus_types[i] == 2 or bus_types[i] == 3:  # it is a PV or slack node
                n1 += Pinstalled[i]

        for i in idx1:
            if bus_types[i] == 2 or bus_types[i] == 3:  # it is a PV or slack node
                dP[i] = dT * Pinstalled[i] / abs(n1)

        # set the receiving power increment proportional to the current power (Area 2)
        n2 = 0.0
        for i in idx2:
            if bus_types[i] == 2 or bus_types[i] == 3:  # it is a PV or slack node
                n2 += Pinstalled[i]

        for i in idx2:
            if bus_types[i] == 2 or bus_types[i] == 3:  # it is a PV or slack node
                dP[i] = -dT * Pinstalled[i] / abs(n2)

    elif mode == 2:  # move the load ------------------------------------------------------

        # set the sending power increment proportional to the current power (Area 1)
        n1 = 0.0
        for i in idx1:
            if bus_types[i] == 1:  # it is a PV or slack node
                n1 += P0[i]

        for i in idx1:
            if bus_types[i] == 1:  # it is a PV or slack node
                dP[i] = dT * P0[i] / abs(n1)

        # set the receiving power increment proportional to the current power (Area 2)
        n2 = 0.0
        for i in idx2:
            if bus_types[i] == 1:  # it is a PV or slack node
                n2 += P0[i]

        for i in idx2:
            if bus_types[i] == 1:  # it is a PV or slack node
                dP[i] = -dT * P0[i] / abs(n2)

    else:  # move all of it -----------------------------------------------------------------

        # set the sending power increment proportional to the current power
        n1 = 0.0
        for i in idx1:
            n1 += P0[i]

        for i in idx1:
            dP[i] = dT * P0[i] / abs(n1)

        # set the receiving power increment proportional to the current power
        n2 = 0.0
        for i in idx2:
            n2 += P0[i]

        for i in idx2:
            dP[i] = -dT * P0[i] / abs(n2)

    # ----------------------------------------------------------------------------------------
    # compute the line flow increments due to the exchange increment dT in MW
    dflow = ptdf.dot(dP)

    # compute the sensitivity
    alpha = dflow / dT

    return alpha


@nb.njit()
def compute_atc(br_idx, ptdf, lodf, alpha, flows, rates, contingency_rates, threshold=0.005):
    """
    Compute all lines' ATC
    :param br_idx: array of branch indices to analyze
    :param ptdf: Power transfer distribution factors (n-branch, n-bus)
    :param lodf: Line outage distribution factors (n-branch, n-outage branch)
    :param alpha: Branch sensitivities to the exchange [p.u.]
    :param flows: branches power injected at the "from" side [MW]
    :param rates: all branches rates vector
    :param contingency_rates: all branches contingency rates vector
    :param threshold: value that determines if a line is studied for the ATC calculation
    :return:
             beta_mat: Matrix of beta values (branch, contingency_branch)
             beta: vector of actual beta value used for each branch (n-branch)
             atc_n: vector of ATC values in "N" (n-branch)
             atc_final: vector of ATC in "N" or "N-1" whatever is more limiting (n-branch)
             atc_limiting_contingency_branch: most limiting contingency branch index vector (n-branch)
             atc_limiting_contingency_flow: most limiting contingency flow vector (n-branch)
    """

    nbr = len(br_idx)

    # explore the ATC
    atc_n = np.zeros(nbr)
    atc_mc = np.zeros(nbr)
    atc_final = np.zeros(nbr)
    beta_mat = np.zeros((nbr, nbr))
    beta_used = np.zeros(nbr)
    atc_limiting_contingency_branch = np.zeros(nbr)
    atc_limiting_contingency_flow = np.zeros(nbr)
    # processed = list()
    # mm = 0
    for im, m in enumerate(br_idx):  # for each branch

        if abs(alpha[m]) > threshold and abs(flows[m]) < rates[m]:  # if the branch is relevant enough for the ATC...

            # compute the ATC in "N"
            if alpha[m] == 0:
                atc_final[im] = np.inf
            elif alpha[m] > 0:
                atc_final[im] = (rates[m] - flows[m]) / alpha[m]
            else:
                atc_final[im] = (-rates[m] - flows[m]) / alpha[m]

            # remember the ATC in "N"
            atc_n[im] = atc_final[im]

            # set to the current branch, since we don't know if there will be any contingency that make the ATC worse
            atc_limiting_contingency_branch[im] = m

            # explore the ATC in "N-1"
            for ic, c in enumerate(br_idx):  # for each contingency
                # compute the exchange sensitivity in contingency conditions
                beta_mat[im, ic] = alpha[m] + lodf[m, c] * alpha[c]
                beta_used[im] = beta_mat[im, ic]  # default

                if m != c:

                    # compute the contingency flow
                    contingency_flow = flows[m] + lodf[m, c] * flows[c]

                    # set the default values (worst contingency by itself, not comparing with the base situation)
                    if abs(contingency_flow) > abs(atc_limiting_contingency_flow[im]):
                        atc_limiting_contingency_flow[im] = contingency_flow  # default
                        atc_limiting_contingency_branch[im] = c
                        beta_used[im] = beta_mat[im, ic]

                    # now here, do compare with the base situation
                    if abs(beta_mat[im, ic]) > threshold and abs(contingency_flow) <= contingency_rates[m]:

                        # compute the ATC in "N-1"
                        if beta_mat[im, ic] == 0:
                            atc_mc[im] = np.inf
                        elif beta_mat[im, ic] > 0:
                            atc_mc[im] = (contingency_rates[m] - contingency_flow) / beta_mat[im, ic]
                        else:
                            atc_mc[im] = (-contingency_rates[m] - contingency_flow) / beta_mat[im, ic]

                        # refine the ATC to the most restrictive value every time
                        if abs(atc_mc[im]) < abs(atc_final[im]):
                            atc_final[im] = atc_mc[im]
                            beta_used[im] = beta_mat[im, ic]
                            atc_limiting_contingency_flow[im] = contingency_flow
                            atc_limiting_contingency_branch[im] = c

    return beta_mat, beta_used, atc_n, atc_mc, atc_final, atc_limiting_contingency_branch, atc_limiting_contingency_flow


class AvailableTransferCapacityResults(ResultsTemplate):

    def __init__(self, n_bus, br_names, bus_names, bus_types, bus_idx_from, bus_idx_to, br_idx):
        """

        :param n_bus:
        :param br_names:
        :param bus_names:
        :param bus_types:
        :param bus_idx_from:
        :param bus_idx_to:
        :param br_idx:
        """
        ResultsTemplate.__init__(self,
                                 name='ATC Results',
                                 available_results=[ResultTypes.AvailableTransferCapacity,
                                                    ResultTypes.NetTransferCapacity,
                                                    ResultTypes.AvailableTransferCapacityN,
                                                    ResultTypes.AvailableTransferCapacityAlpha,
                                                    ResultTypes.AvailableTransferCapacityBeta,
                                                    ResultTypes.AvailableTransferCapacityReport
                                                    ],
                                 data_variables=['alpha',
                                                 'beta_mat',
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
                                                 'bus_idx_from',
                                                 'bus_idx_to',
                                                 'br_idx'])
        self.n_br = len(br_idx)
        self.n_bus = n_bus
        self.branch_names = np.array(br_names, dtype=object)
        self.bus_names = bus_names
        self.bus_types = bus_types
        self.bus_idx_from = bus_idx_from
        self.bus_idx_to = bus_idx_to
        self.br_idx = br_idx

        # stores the worst transfer capacities (from to) and (to from)
        self.rates = np.zeros(self.n_br)
        self.contingency_rates = np.zeros(self.n_br)
        self.base_exchange = 0

        self.alpha = np.zeros(self.n_br)
        self.atc = np.zeros(self.n_br)
        self.atc_n = np.zeros(self.n_br)
        self.atc_mc = np.zeros(self.n_br)
        self.ntc = np.zeros(self.n_br)

        self.beta_mat = np.zeros((self.n_br, self.n_br))
        self.beta = np.zeros(self.n_br)
        self.atc_limiting_contingency_branch = np.zeros(self.n_br, dtype=int)
        self.atc_limiting_contingency_flow = np.zeros(self.n_br)
        self.base_flow = np.zeros(self.n_br)

        self.report = np.empty((self.n_br, 0), dtype=object)
        self.report_headers = list()
        self.report_indices = self.branch_names

    def get_steps(self):
        return

    def make_report(self, threshold: float = 0.0):
        """

        :return:
        """
        self.report_headers = ['Branch',
                               'Base flow',
                               'Rate',
                               'Alpha',
                               'ATC normal',
                               'Limiting contingency branch',
                               'Limiting contingency flow',
                               'Contingency rate',
                               'Beta',
                               'Contingency ATC',
                               'ATC',
                               'Base exchange flow',
                               'NTC']
        self.report = np.empty((self.n_br, len(self.report_headers)), dtype=object)

        # sort by ATC
        self.report_indices = self.branch_names[self.br_idx]
        self.report[:, 0] = self.branch_names[self.br_idx]  # 'Branch'
        self.report[:, 1] = self.base_flow  # 'Base flow'
        self.report[:, 2] = self.rates  # 'Rate',
        self.report[:, 3] = self.alpha  # 'Alpha'
        self.report[:, 4] = self.atc_n  # 'ATC normal'

        # contingency info
        self.report[:, 5] = self.branch_names[self.atc_limiting_contingency_branch]  # 'Limiting contingency branch'
        self.report[:, 6] = self.atc_limiting_contingency_flow  # 'Limiting contingency flow'
        self.report[:, 7] = self.contingency_rates  # 'Contingency rate'
        self.report[:, 8] = self.beta  # 'Beta'
        self.report[:, 9] = self.atc_mc  # 'Contingency ATC'
        self.report[:, 10] = self.atc  # ATC
        self.report[:, 11] = self.base_exchange  # Base exchange flow
        self.report[:, 12] = self.ntc  # NTC

        # sort by NTC
        idx = np.argsort(self.ntc)
        self.report = self.report[idx, :]

        # trim by abs alpha > threshold
        loading = np.abs(self.report[:, 1] / (self.report[:, 2] + 1e-20))
        idx = np.where((np.abs(self.report[:, 3]) > threshold) & (loading < 1.0))[0]
        self.report_indices = self.report_indices[idx]
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

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results
        :param result_type:
        :return:
        """

        if result_type == ResultTypes.AvailableTransferCapacity:
            data = self.atc
            y_label = '(MW)'
            title, _ = result_type.value
            labels = ['ATC']
            index = self.branch_names[self.br_idx]

        elif result_type == ResultTypes.NetTransferCapacity:
            data = self.ntc
            y_label = '(MW)'
            title, _ = result_type.value
            labels = ['NTC']
            index = self.branch_names[self.br_idx]

        elif result_type == ResultTypes.AvailableTransferCapacityN:
            data = self.atc_n
            y_label = '(MW)'
            title, _ = result_type.value
            labels = ['ATC (N)']
            index = self.branch_names[self.br_idx]

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            data = self.alpha
            y_label = '(p.u.)'
            title, _ = result_type.value
            labels = ['Sensitivity to the exchange']
            index = self.branch_names[self.br_idx]

        elif result_type == ResultTypes.AvailableTransferCapacityBeta:
            data = self.beta_mat
            y_label = '(p.u.)'
            title, _ = result_type.value
            labels = ['#' + self.branch_names[x] for x in self.br_idx]
            index = self.branch_names[self.br_idx]

        elif result_type == ResultTypes.AvailableTransferCapacityReport:
            data = np.array(self.report)
            y_label = ''
            title, _ = result_type.value
            index = self.report_indices
            labels = self.report_headers
        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsTable(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl


class AvailableTransferCapacityOptions:

    def __init__(self, distributed_slack=True, correct_values=True, use_provided_flows=False,
                 bus_idx_from=list(), bus_idx_to=list(), idx_br=list(), sense_br=list(), Pf=None,
                 idx_hvdc_br=list(), sense_hvdc_br=list(), Pf_hvdc=None,
                 dT=100.0, threshold=0.02, mode: AvailableTransferMode = AvailableTransferMode.Generation):
        """

        :param distributed_slack:
        :param correct_values:
        :param bus_idx_from:
        :param bus_idx_to:
        :param idx_br:
        :param sense_br:
        :param Pf:
        :param dT:
        :param threshold:
        :param mode:
        """
        self.distributed_slack = distributed_slack
        self.correct_values = correct_values
        self.use_provided_flows = use_provided_flows
        self.bus_idx_from = bus_idx_from
        self.bus_idx_to = bus_idx_to
        self.inter_area_branch_idx = idx_br
        self.inter_area_branch_sense = sense_br
        self.Pf = Pf

        self.idx_hvdc_br = idx_hvdc_br
        self.inter_area_hvdc_branch_sense = sense_hvdc_br
        self.Pf_hvdc = Pf_hvdc

        self.dT = dT
        self.threshold = threshold
        self.mode = mode


class AvailableTransferCapacityDriver(DriverTemplate):

    tpe = SimulationTypes.NetTransferCapacity_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: AvailableTransferCapacityOptions):
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
        self.results = AvailableTransferCapacityResults(n_bus=0,
                                                        br_names=[],
                                                        bus_names=[],
                                                        bus_types=[],
                                                        bus_idx_from=[],
                                                        bus_idx_to=[],
                                                        br_idx=[])

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
        idx1b = self.options.bus_idx_from
        idx2b = self.options.bus_idx_to

        # declare the linear analysis
        linear = LinearAnalysis(grid=self.grid,
                                distributed_slack=self.options.distributed_slack,
                                correct_values=self.options.correct_values)
        linear.run()

        # get the branch indices to analyze
        br_idx = linear.numerical_circuit.branch_data.get_contingency_enabled_indices()

        # declare the results
        self.results = AvailableTransferCapacityResults(n_bus=linear.numerical_circuit.nbus,
                                                        br_names=linear.numerical_circuit.branch_names,
                                                        bus_names=linear.numerical_circuit.bus_names,
                                                        bus_types=linear.numerical_circuit.bus_types,
                                                        bus_idx_from=idx1b,
                                                        bus_idx_to=idx2b,
                                                        br_idx=br_idx)

        # compute the branch exchange sensitivity (alpha)
        alpha = compute_alpha(ptdf=linear.PTDF,
                              P0=nc.Sbus.real,
                              Pinstalled=nc.bus_installed_power,
                              idx1=idx1b,
                              idx2=idx2b,
                              bus_types=nc.bus_types.astype(np.int),
                              dT=self.options.dT,
                              mode=self.options.mode.value)

        # get flow
        if self.options.use_provided_flows:
            flows = self.options.Pf

            if self.options.Pf is None:
                msg = 'The option to use the provided flows is enabled, but no flows are available'
                self.logger.add_error(msg)
                raise Exception(msg)
        else:
            flows = linear.get_flows(nc.Sbus)

        # base exchange
        base_exchange = (self.options.inter_area_branch_sense * flows[self.options.inter_area_branch_idx]).sum()

        # consider the HVDC transfer
        if self.options.Pf_hvdc is not None:
            if len(self.options.idx_hvdc_br):
                base_exchange += (self.options.inter_area_hvdc_branch_sense * self.options.Pf_hvdc[self.options.idx_hvdc_br]).sum()

        # compute ATC
        beta_mat, beta_used, atc_n, atc_mc, atc_final, \
        atc_limiting_contingency_branch, \
        atc_limiting_contingency_flow = compute_atc(br_idx=br_idx,
                                                    ptdf=linear.PTDF,
                                                    lodf=linear.LODF,
                                                    alpha=alpha,
                                                    flows=flows,
                                                    rates=nc.Rates,
                                                    contingency_rates=nc.ContingencyRates,
                                                    threshold=self.options.threshold)

        # post-process and store the results
        self.results.br_idx = br_idx
        self.results.alpha = alpha[br_idx]
        self.results.atc = atc_final
        self.results.atc_n = atc_n
        self.results.atc_mc = atc_mc
        self.results.ntc = atc_final + base_exchange
        self.results.base_exchange = base_exchange
        self.results.beta_mat = beta_mat
        self.results.beta = beta_used
        self.results.atc_limiting_contingency_branch = atc_limiting_contingency_branch.astype(int)
        self.results.atc_limiting_contingency_flow = atc_limiting_contingency_flow
        self.results.base_flow = flows[br_idx]
        self.results.rates = nc.Rates[br_idx]
        self.results.contingency_rates = nc.ContingencyRates[br_idx]

        self.results.make_report(threshold=self.options.threshold)

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

    from GridCal.Engine.IO import *
    fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    options = AvailableTransferCapacityOptions()
    driver = AvailableTransferCapacityDriver(main_circuit, options)
    driver.run()

    print()

