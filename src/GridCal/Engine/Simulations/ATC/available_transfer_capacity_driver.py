# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
def get_proportional_deltas_sensed(P, idx, dP=1.0):
    """

    :param P: all power injections
    :param idx: bus indices of the sending region
    :param dP: Power amount
    :return:
    """

    # declare the power increment due to the transference
    deltaP = np.zeros(len(P))

    nU = 0.0
    nD = 0.0

    for i in idx:

        if P[i] > 0:
            nU += P[i]

        if P[i] < 0:
            nD -= P[i]  # store it as positive value

    # compute witch proportion to attend with positive and negative sense
    dPu = nU / (nU + nD)  # positive proportion
    dPd = 1 - dPu  # negative proportion

    for i in idx:

        if P[i] > 0:
            deltaP[i] = dP * dPu * P[i] / nU

        if P[i] < 0:
            deltaP[i] = -dP * dPd * P[i] / nD  # P[i] is already negative

    return deltaP


@nb.njit()
def scale_proportional_sensed(P, idx1, idx2, dT=1.0):
    """

    :param P: Power vector
    :param idx1: indices of sending region
    :param idx2: indices of receiving region
    :param dT: Exchange amount
    :return:
    """

    dPu = get_proportional_deltas_sensed(P, idx1, dP=dT)
    dPd = get_proportional_deltas_sensed(P, idx2, dP=-dT)

    dP = dPu + dPd

    return P + dP


@nb.njit(cache=True)
def compute_alpha(ptdf, P0, Pgen, Pinstalled, Pload, idx1, idx2, dT=1.0, mode=0):
    """
    Compute line sensitivity to power transfer
    :param ptdf: Power transfer distribution factors (n-branch, n-bus)
    :param P0: all bus injections [p.u.]
    :param Pinstalled: bus generation installed power [p.u.]
    :param Pgen: bus generation current power [p.u.]
    :param Pload: bus load power [p.u.]
    :param idx1: bus indices of the sending region
    :param idx2: bus indices of the receiving region
    :param dT: Exchange amount
    :param mode: Type of power shift
                 0: shift generation based on the current generated power
                 1: shift generation based on the installed power
                 2: shift load
                 3 (or else): shift updating generation and load

    :return: Exchange sensitivity vector for all the lines
    """

    if mode == 0:
        # move the generators based on the generated power
        P = Pgen

    elif mode == 1:
        # move the generators based on the installed power
        P = Pinstalled

    elif mode == 2:
        # move the load
        P = Pload

    else:
        # move all of it
        P = P0

    # compute the bus injection increments due to the exchange
    dPu = get_proportional_deltas_sensed(P, idx1, dP=dT)
    dPd = get_proportional_deltas_sensed(P, idx2, dP=-dT)

    dP = dPu + dPd

    # compute the line flow increments due to the exchange increment dT in MW
    dflow = ptdf.dot(dP)

    # compute the sensitivity
    alpha = dflow / dT

    return alpha


# @nb.njit()
# def compute_atc(br_idx, contingency_br_idx, lodf, alpha, flows, rates, contingency_rates, threshold=0.005):
#     """
#     Compute all lines' ATC
#     :param br_idx: array of branch indices to analyze
#     :param contingency_br_idx: array of branch indices to fail
#     :param lodf: Line outage distribution factors (n-branch, n-outage branch)
#     :param alpha: Branch sensitivities to the exchange [p.u.]
#     :param flows: branches power injected at the "from" side [MW]
#     :param rates: all branches rates vector
#     :param contingency_rates: all branches contingency rates vector
#     :param threshold: value that determines if a line is studied for the ATC calculation
#     :return:
#              beta_mat: Matrix of beta values (branch, contingency_branch)
#              beta: vector of actual beta value used for each branch (n-branch)
#              atc_n: vector of ATC values in "N" (n-branch)
#              atc_final: vector of ATC in "N" or "N-1" whatever is more limiting (n-branch)
#              atc_limiting_contingency_branch: most limiting contingency branch index vector (n-branch)
#              atc_limiting_contingency_flow: most limiting contingency flow vector (n-branch)
#     """
#
#     nbr = len(br_idx)
#
#     # explore the ATC
#     atc_n = np.zeros(nbr)
#     atc_mc = np.zeros(nbr)
#     atc_final = np.zeros(nbr)
#     beta_mat = np.zeros((nbr, nbr))
#     beta_used = np.zeros(nbr)
#     atc_limiting_contingency_branch = np.zeros(nbr)
#     atc_limiting_contingency_flow = np.zeros(nbr)
#     # processed = list()
#     # mm = 0
#     for im, m in enumerate(br_idx):  # for each branch
#
#         # if abs(alpha[m]) > threshold and abs(flows[m]) < rates[m]:  # if the branch is relevant enough for the ATC...
#         if abs(alpha[m]) > threshold:  # if the branch is relevant enough for the ATC...
#
#             # compute the ATC in "N"
#             if alpha[m] == 0:
#                 atc_final[im] = np.inf
#             elif alpha[m] > 0:
#                 atc_final[im] = (rates[m] - flows[m]) / alpha[m]
#             else:
#                 atc_final[im] = (-rates[m] - flows[m]) / alpha[m]
#
#             # remember the ATC in "N"
#             atc_n[im] = atc_final[im]
#
#             # set to the current branch, since we don't know if there will be any contingency that make the ATC worse
#             atc_limiting_contingency_branch[im] = m
#
#             # explore the ATC in "N-1"
#             for ic, c in enumerate(contingency_br_idx):  # for each contingency
#                 # compute the exchange sensitivity in contingency conditions
#                 beta_mat[im, ic] = alpha[m] + lodf[m, c] * alpha[c]
#
#                 if m != c:
#
#                     # compute the contingency flow
#                     contingency_flow = flows[m] + lodf[m, c] * flows[c]
#
#                     # set the default values (worst contingency by itself, not comparing with the base situation)
#                     if abs(contingency_flow) > abs(atc_limiting_contingency_flow[im]):
#                         atc_limiting_contingency_flow[im] = contingency_flow  # default
#                         atc_limiting_contingency_branch[im] = c
#
#                     # now here, do compare with the base situation
#                     if abs(beta_mat[im, ic]) > threshold and abs(contingency_flow) <= contingency_rates[m]:
#
#                         # compute the ATC in "N-1"
#                         if beta_mat[im, ic] == 0:
#                             atc_mc[im] = np.inf
#                         elif beta_mat[im, ic] > 0:
#                             atc_mc[im] = (contingency_rates[m] - contingency_flow) / beta_mat[im, ic]
#                         else:
#                             atc_mc[im] = (-contingency_rates[m] - contingency_flow) / beta_mat[im, ic]
#
#                         # refine the ATC to the most restrictive value every time
#                         if abs(atc_mc[im]) < abs(atc_final[im]):
#                             atc_final[im] = atc_mc[im]
#                             beta_used[im] = beta_mat[im, ic]
#                             atc_limiting_contingency_flow[im] = contingency_flow
#                             atc_limiting_contingency_branch[im] = c
#
#     return beta_mat, beta_used, atc_n, atc_mc, atc_final, atc_limiting_contingency_branch, atc_limiting_contingency_flow


@nb.njit(cache=True)
def compute_atc_list(br_idx, contingency_br_idx, lodf, alpha, flows, rates, contingency_rates, base_exchange,
                     threshold, time_idx):
    """
    Compute all lines' ATC
    :param br_idx: array of branch indices to analyze
    :param contingency_br_idx: array of branch indices to fail
    :param lodf: Line outage distribution factors (n-branch, n-outage branch)
    :param alpha: Branch sensitivities to the exchange [p.u.]
    :param flows: branches power injected at the "from" side [MW]
    :param rates: all branches rates vector
    :param contingency_rates: all branches contingency rates vector
    :param base_exchange: amount already exchanges between areas
    :param threshold: value that determines if a line is studied for the ATC calculation
    :param time_idx: time index of the calculation
    :return:
             beta_mat: Matrix of beta values (branch, contingency_branch)
             beta: vector of actual beta value used for each branch (n-branch)
             atc_n: vector of ATC values in "N" (n-branch)
             atc_final: vector of ATC in "N" or "N-1" whatever is more limiting (n-branch)
             atc_limiting_contingency_branch: most limiting contingency branch index vector (n-branch)
             atc_limiting_contingency_flow: most limiting contingency flow vector (n-branch)
    """

    results = list()

    for im, m in enumerate(br_idx):  # for each branch

        # if abs(alpha[m]) > threshold and abs(flows[m]) < rates[m]:  # if the branch is relevant enough for the ATC...
        if abs(alpha[m]) > threshold:  # if the branch is relevant enough for the ATC...

            # compute the ATC in "N"
            if alpha[m] == 0:
                atc_n = np.inf
            elif alpha[m] > 0:
                atc_n = (rates[m] - flows[m]) / alpha[m]
            else:
                atc_n = (-rates[m] - flows[m]) / alpha[m]

            # explore the ATC in "N-1"
            for ic, c in enumerate(contingency_br_idx):  # for each contingency

                # compute the exchange sensitivity in contingency conditions
                beta = alpha[m] + lodf[m, c] * alpha[c]

                if m != c and abs(lodf[m, c]) > threshold and abs(beta) > threshold:

                    # compute the contingency flow
                    contingency_flow = flows[m] + lodf[m, c] * flows[c]

                    # now here, do compare with the base situation
                    # if abs(contingency_flow) <= contingency_rates[m]:

                    # compute the ATC in "N-1"
                    if beta == 0:
                        atc_mc = np.inf
                    elif beta > 0:
                        atc_mc = (contingency_rates[m] - contingency_flow) / beta
                    else:
                        atc_mc = (-contingency_rates[m] - contingency_flow) / beta

                    final_atc = min(atc_mc, atc_n)
                    ntc = final_atc + base_exchange

                    # refine the ATC to the most restrictive value every time
                    results.append((time_idx,           # 0
                                    m,                  # 1
                                    c,                  # 2
                                    alpha[m],           # 3
                                    beta,               # 4
                                    lodf[m, c],         # 5
                                    atc_n,              # 6
                                    atc_mc,             # 7
                                    final_atc,          # 8
                                    ntc,                # 9
                                    flows[m],           # 10
                                    contingency_flow,   # 11
                                    flows[m] / (rates[m] + 1e-9) * 100.0,  # 12
                                    contingency_flow / (contingency_rates[m] + 1e-9) * 100.0,  # 13
                                    base_exchange))    # 14

    return results


class AvailableTransferCapacityResults(ResultsTemplate):

    def __init__(self, br_names, bus_names, rates, contingency_rates):
        """

        :param br_names:
        :param bus_names:
        """
        ResultsTemplate.__init__(self,
                                 name='ATC Results',
                                 available_results=[
                                                    ResultTypes.AvailableTransferCapacityReport
                                                    ],
                                 data_variables=['report',
                                                 'branch_names',
                                                 'bus_names'])

        self.branch_names = np.array(br_names, dtype=object)
        self.bus_names = bus_names
        self.rates = rates
        self.contingency_rates = contingency_rates
        self.base_exchange = 0
        self.report = None
        self.report_headers = None
        self.report_indices = None

        self.raw_report = None

    def get_steps(self):
        return

    def make_report(self, threshold: float = 0.0):
        """

        :return:
        """
        self.report_headers = ['Time',
                               'Branch',
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
        self.report = np.empty((len(self.raw_report), len(self.report_headers)), dtype=object)

        rep = np.array(self.raw_report)

        # sort by ATC
        if len(self.raw_report):

            m = rep[:, 1].astype(int)
            c = rep[:, 2].astype(int)

            self.report_indices = np.arange(0, len(rep))

            # time
            self.report[:, 0] = 0

            # Branch name
            self.report[:, 1] = self.branch_names[m]

            # Base flow'
            self.report[:, 2] = rep[:, 10]

            # rate
            self.report[:, 3] = self.rates[m]  # 'Rate', (time, branch)

            # alpha
            self.report[:, 4] = rep[:, 3]

            # 'ATC normal'
            self.report[:, 5] = rep[:, 6]

            # contingency info -----

            # 'Limiting contingency branch'
            self.report[:, 6] = self.branch_names[c]

            # 'Limiting contingency flow'
            self.report[:, 7] = rep[:, 11]

            # 'Contingency rate' (time, branch)
            self.report[:, 8] = self.contingency_rates[m]

            # 'Beta'
            self.report[:, 9] = rep[:, 4]

            # 'Contingency ATC'
            self.report[:, 10] = rep[:, 7]

            # Final ATC (worst between normal ATC and contingency ATC)
            self.report[:, 11] = rep[:, 8]

            # Base exchange flow
            self.report[:, 12] = rep[:, 14]

            # NTC
            self.report[:, 13] = rep[:, 9]

            # trim by abs alpha > threshold and loading <= 1
            loading = np.abs(self.report[:, 2] / (self.report[:, 3] + 1e-20))
            idx = np.where((np.abs(self.report[:, 4]) > threshold) & (loading <= 1.0))[0]

            self.report = self.report[idx, :]
        else:
            print('Empty raw report :/')

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'report': self.report.tolist()}
        return data

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results
        :param result_type:
        :return:
        """

        if result_type == ResultTypes.AvailableTransferCapacityReport:
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
                 dT=100.0, threshold=0.02, mode: AvailableTransferMode = AvailableTransferMode.Generation,
                 max_report_elements=-1, use_clustering=False, cluster_number=100):
        """

        :param distributed_slack:
        :param correct_values:
        :param use_provided_flows:
        :param bus_idx_from:
        :param bus_idx_to:
        :param idx_br:
        :param sense_br:
        :param Pf:
        :param idx_hvdc_br:
        :param sense_hvdc_br:
        :param Pf_hvdc:
        :param dT:
        :param threshold:
        :param mode:
        :param max_report_elements: maximum number of elements to show in the report (-1 for all)
        :param use_clustering:
        :param n_clusters:
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

        self.max_report_elements = max_report_elements

        self.use_clustering = use_clustering
        self.cluster_number = cluster_number


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
        self.results = AvailableTransferCapacityResults(br_names=[],
                                                        bus_names=[],
                                                        rates=[],
                                                        contingency_rates=[])

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
        br_idx = nc.branch_data.get_monitor_enabled_indices()
        con_br_idx = nc.branch_data.get_contingency_enabled_indices()

        # declare the results
        self.results = AvailableTransferCapacityResults(br_names=linear.numerical_circuit.branch_names,
                                                        bus_names=linear.numerical_circuit.bus_names,
                                                        rates=nc.Rates,
                                                        contingency_rates=nc.ContingencyRates)

        # compute the branch exchange sensitivity (alpha)
        alpha = compute_alpha(ptdf=linear.PTDF,
                              P0=nc.Sbus.real,
                              Pinstalled=nc.bus_installed_power,
                              Pgen=nc.generator_data.get_injections_per_bus(),
                              Pload=nc.load_data.get_injections_per_bus(),
                              idx1=idx1b,
                              idx2=idx2b,
                              dT=self.options.dT,
                              mode=int(self.options.mode.value))

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
        report = compute_atc_list(br_idx=br_idx,
                                  contingency_br_idx=con_br_idx,
                                  lodf=linear.LODF,
                                  alpha=alpha,
                                  flows=flows,
                                  rates=nc.Rates,
                                  contingency_rates=nc.ContingencyRates,
                                  base_exchange=base_exchange,
                                  time_idx=0,
                                  threshold=self.options.threshold)
        report = np.array(report, dtype=object)

        # sort by NTC
        report = report[report[:, 9].argsort()]

        # curtail report
        if self.options.max_report_elements > 0:
            report = report[:self.options.max_report_elements, :]

        # post-process and store the results
        self.results.raw_report = report
        self.results.base_exchange = base_exchange
        self.results.make_report(threshold=self.options.threshold)

        end = time.time()
        self.elapsed = end - start

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

