# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

import numpy as np
from typing import Union, Tuple
from GridCalEngine.basic_structures import Vec, ConvergenceReport
from GridCalEngine.Simulations.StateEstimation.state_estimation import solve_se_lm
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowResults, power_flow_post_process
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.enumerations import SolverType


class StateEstimationInput:
    """
    StateEstimationInput
    """

    def __init__(self) -> None:
        """
        State estimation inputs constructor
        """

        # nz = n_pi + n_qi + n_vm + n_pf + n_qf + n_if
        # self.magnitudes = np.zeros(nz)
        # self.sigma = np.zeros(nz)

        # Node active power measurements vector of pointers
        self.p_inj = list()

        # Node  reactive power measurements vector of pointers
        self.q_inj = list()

        # Branch active power measurements vector of pointers
        self.p_flow = list()

        # Branch reactive power measurements vector of pointers
        self.q_flow = list()

        # Branch current module measurements vector of pointers
        self.i_flow = list()

        # Node voltage module measurements vector of pointers
        self.vm_m = list()

        # nodes with power injection measurements
        self.p_inj_idx = list()

        # Branches with power measurements
        self.p_flow_idx = list()

        # nodes with reactive power injection measurements
        self.q_inj_idx = list()

        # Branches with reactive power measurements
        self.q_flow_idx = list()

        # Branches with current measurements
        self.i_flow_idx = list()

        # nodes with voltage module measurements
        self.vm_m_idx = list()

    def consolidate(self) -> Tuple[Vec, Vec]:
        """
        consolidate the measurements into "measurements" and "sigma"
        ordering: Pinj, Pflow, Qinj, Qflow, Iflow, Vm
        :return: measurements vector, sigma vector
        """

        nz = len(self.p_inj) + len(self.p_flow) + len(self.q_inj) + len(self.q_flow) + len(self.i_flow) + len(self.vm_m)

        magnitudes = np.zeros(nz)
        sigma = np.zeros(nz)

        # go through the measurements in order and form the vectors
        k = 0
        for m in self.p_flow + self.p_inj + self.q_flow + self.q_inj + self.i_flow + self.vm_m:
            magnitudes[k] = m.value
            sigma[k] = m.sigma
            k += 1

        return magnitudes, sigma


class StateEstimationResults(PowerFlowResults):

    def __init__(self, n, m, bus_names, branch_names, hvdc_names, bus_types):
        """

        :param n:
        :param m:
        :param bus_names:
        :param branch_names:
        :param bus_types:
        """
        # initialize the
        PowerFlowResults.__init__(self,
                                  n=n,
                                  m=m,
                                  n_hvdc=0,
                                  bus_names=bus_names,
                                  branch_names=branch_names,
                                  hvdc_names=hvdc_names,
                                  bus_types=bus_types)


class StateEstimation(DriverTemplate):

    def __init__(self, circuit: MultiCircuit):
        """
        Constructor
        :param circuit: circuit object
        """

        DriverTemplate.__init__(self, grid=circuit)

        self.results: Union[StateEstimationResults, None] = None

    @staticmethod
    def collect_measurements(circuit: MultiCircuit, bus_idx, branch_idx):
        """
        Form the input from the circuit measurements
        :return: nothing, the input object is stored in this class
        """
        se_input = StateEstimationInput()

        # bus measurements
        bus_dict = circuit.get_bus_index_dict()

        for elm in circuit.get_pi_measurements():
            se_input.p_inj_idx.append(bus_dict[elm.api_object])
            se_input.p_inj.append(elm)

        for elm in circuit.get_qi_measurements():
            se_input.q_inj_idx.append(bus_dict[elm.api_object])
            se_input.q_inj.append(elm)

        for elm in circuit.get_vm_measurements():
            se_input.vm_m_idx.append(bus_dict[elm.api_object])
            se_input.vm_m.append(elm)

        # branch measurements
        branch_dict = circuit.get_branches_wo_hvdc_index_dict()

        for elm in circuit.get_pf_measurements():
            se_input.p_flow_idx.append(branch_dict[elm.api_object])
            se_input.p_flow.append(elm)

        for elm in circuit.get_qf_measurements():
            se_input.q_flow_idx.append(branch_dict[elm.api_object])
            se_input.q_flow.append(elm)

        for elm in circuit.get_if_measurements():
            se_input.i_flow_idx.append(branch_dict[elm.api_object])
            se_input.i_flow.append(elm)

        return se_input

    def run(self):
        """
        Run state estimation
        :return:
        """
        self.tic()
        n = len(self.grid.buses)
        m = self.grid.get_branch_number()

        numerical_circuit = compile_numerical_circuit_at(self.grid, logger=self.logger)
        self.results = StateEstimationResults(n=n,
                                              m=m,
                                              bus_names=numerical_circuit.bus_names,
                                              branch_names=numerical_circuit.branch_names,
                                              hvdc_names=numerical_circuit.hvdc_names,
                                              bus_types=numerical_circuit.bus_types)
        # self.se_results.initialize(n, m)

        islands = numerical_circuit.split_into_islands()

        self.results.bus_types = numerical_circuit.bus_types

        for island in islands:

            # collect inputs of the island
            se_input = self.collect_measurements(circuit=self.grid,
                                                 bus_idx=island.original_bus_idx,
                                                 branch_idx=island.original_branch_idx)

            # run solver
            report = ConvergenceReport()
            solution = solve_se_lm(Ybus=island.Ybus,
                                   Yf=island.Yf,
                                   Yt=island.Yt,
                                   f=island.F,
                                   t=island.T,
                                   se_input=se_input,
                                   ref=island.vd,
                                   pq=island.pq,
                                   pv=island.pv)

            report.add(method=SolverType.LM,
                       converged=solution.converged,
                       error=solution.norm_f,
                       elapsed=solution.elapsed,
                       iterations=solution.iterations)

            # Compute the Branches power and the slack buses power
            Sfb, Stb, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process(calculation_inputs=island,
                                                                                       Sbus=island.Sbus,
                                                                                       V=solution.V,
                                                                                       branch_rates=island.branch_rates,
                                                                                       Ybus=None,
                                                                                       Yf=None,
                                                                                       Yt=None)

            # pack results into a SE results object
            results = StateEstimationResults(n=island.nbus,
                                             m=island.nbr,
                                             bus_names=island.bus_names,
                                             branch_names=island.branch_names,
                                             hvdc_names=island.hvdc_names,
                                             bus_types=island.bus_types)
            results.Sbus = Sbus
            results.Sf = Sfb
            results.voltage = solution.V
            results.losses = losses
            results.loading = loading
            results.convergence_reports.append(report)

            self.results.apply_from_island(results,
                                           island.original_bus_idx,
                                           island.original_branch_idx)

        self.toc()
