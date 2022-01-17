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
import datetime
import numpy as np
from itertools import combinations

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate


def enumerate_states_n_k(m, k=1):
    """
    Enumerates the states to produce the so called N-k failures
    :param m: number of branches
    :param k: failure level
    :return: binary array (number of states, m)
    """

    # num = int(math.factorial(k) / math.factorial(m-k))
    states = list()
    indices = list()
    arr = np.ones(m, dtype=int).tolist()

    idx = list(range(m))
    for k1 in range(k + 1):
        for failed in combinations(idx, k1):
            indices.append(failed)
            arr2 = arr.copy()
            for j in failed:
                arr2[j] = 0
            states.append(arr2)

    return np.array(states), indices


class ContingencyAnalysisOptions:

    def __init__(self, distributed_slack=True, correct_values=True,
                 use_provided_flows=False, Pf=None):

        self.distributed_slack = distributed_slack

        self.correct_values = correct_values

        self.use_provided_flows = use_provided_flows

        self.Pf = Pf


class ContingencyAnalysisDriver(DriverTemplate):
    name = 'Contingency Analysis'
    tpe = SimulationTypes.ContingencyAnalysis_run

    def __init__(self, grid: MultiCircuit, options: ContingencyAnalysisOptions):
        """
        N - k class constructor
        @param grid: MultiCircuit Object
        @param options: N-k options
        @:param pf_options: power flow options
        """
        DriverTemplate.__init__(self, grid=grid)

        # Options to use
        self.options = options

        # N-K results
        self.results = ContingencyAnalysisResults(nbus=0, nbr=0,
                                                  bus_names=(),
                                                  branch_names=(),
                                                  bus_types=())

        self.numerical_circuit = None

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return ['#' + v for v in self.results.branch_names]
        else:
            return list()

    def n_minus_k(self):
        """
        Run N-1 simulation in series
        :return: returns the results
        """

        self.progress_text.emit('Analyzing outage distribution factors...')
        linear_analysis = LinearAnalysis(grid=self.grid,
                                         distributed_slack=self.options.distributed_slack,
                                         correct_values=self.options.correct_values)
        linear_analysis.run()

        # set the numerical circuit
        self.numerical_circuit = linear_analysis.numerical_circuit

        # declare the results
        results = ContingencyAnalysisResults(nbr=self.numerical_circuit.nbr,
                                             nbus=self.numerical_circuit.nbus,
                                             branch_names=self.numerical_circuit.branch_names,
                                             bus_names=self.numerical_circuit.bus_names,
                                             bus_types=self.numerical_circuit.bus_types)

        # get the contingency branch indices
        br_idx = linear_analysis.numerical_circuit.branch_data.get_contingency_enabled_indices()
        mon_idx = linear_analysis.numerical_circuit.branch_data.get_monitor_enabled_indices()
        Pbus = self.numerical_circuit.get_injections(False).real[:, 0]
        PTDF = linear_analysis.PTDF
        LODF = linear_analysis.LODF

        # compute the branch Sf in "n"
        if self.options.use_provided_flows:
            flows_n = self.options.Pf

            if self.options.Pf is None:
                msg = 'The option to use the provided flows is enabled, but no flows are available'
                self.logger.add_error(msg)
                raise Exception(msg)
        else:
            flows_n = linear_analysis.get_flows(self.numerical_circuit.Sbus)

        self.progress_text.emit('Computing loading...')

        for ic, c in enumerate(br_idx):  # branch that fails (contingency)
            results.Sf[mon_idx, c] = flows_n[mon_idx] + LODF[mon_idx, c] * flows_n[c]
            results.loading[mon_idx, c] = results.Sf[mon_idx, c] / (self.numerical_circuit.ContingencyRates[mon_idx] + 1e-9)
            results.S[c, :] = Pbus

            self.progress_signal.emit((ic + 1) / len(br_idx) * 100)

        results.otdf = LODF

        return results

    def run(self):
        """

        :return:
        """
        start = time.time()
        self.results = self.n_minus_k()

        end = time.time()
        self.elapsed = end - start


if __name__ == '__main__':
    import os
    import pandas as pd
    from GridCal.Engine import FileOpen, SolverType, PowerFlowOptions

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/2869 Pegase.gridcal'
    fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    # fname = os.path.join('..', '..', '..', '..', '..', 'Grids_and_profiles', 'grids', '2869 Pegase.gridcal')

    main_circuit = FileOpen(fname).open()

    options_ = ContingencyAnalysisOptions()
    simulation = ContingencyAnalysisDriver(grid=main_circuit, options=options_)
    simulation.run()

    otdf_ = simulation.get_otdf()

    # save the result
    br_names = [b.name for b in main_circuit.branches]
    br_names2 = ['#' + b.name for b in main_circuit.branches]
    w = pd.ExcelWriter('LODF IEEE30.xlsx')
    pd.DataFrame(data=simulation.results.Sf.real,
                 columns=br_names,
                 index=['base'] + br_names2).to_excel(w, sheet_name='branch power')
    pd.DataFrame(data=otdf_,
                 columns=br_names,
                 index=br_names2).to_excel(w, sheet_name='LODF')
    w.save()