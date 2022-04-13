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

import numpy as np

import GridCal.Engine.basic_structures as bs
from GridCal.Engine.Simulations.StateEstimation.state_estimation import solve_se_lm
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowResults, power_flow_post_process
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.Devices.measurement import MeasurementType
from GridCal.Engine.Simulations.driver_template import DriverTemplate


class StateEstimationInput:

    def __init__(self):
        """
        State estimation inputs constructor
        """

        # Node active power measurements vector of pointers
        self.p_inj =list()

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

        # nodes without power injection measurements
        self.p_inj_idx = list()

        # branches without power measurements
        self.p_flow_idx = list()

        # nodes without reactive power injection measurements
        self.q_inj_idx = list()

        # branches without reactive power measurements
        self.q_flow_idx = list()

        # branches without current measurements
        self.i_flow_idx = list()

        # nodes without voltage module measurements
        self.vm_m_idx = list()

    def clear(self):
        """
        Clear
        """
        self.p_inj.clear()
        self.p_flow.clear()
        self.q_inj.clear()
        self.q_flow.clear()
        self.i_flow.clear()
        self.vm_m.clear()

        self.p_inj_idx.clear()
        self.p_flow_idx.clear()
        self.q_inj_idx.clear()
        self.q_flow_idx.clear()
        self.i_flow_idx.clear()
        self.vm_m_idx.clear()

    def consolidate(self):
        """
        consolidate the measurements into "measurements" and "sigma"
        :return: measurements, sigma
        """

        nz = len(self.p_inj) + len(self.p_flow) + len(self.q_inj) + len(self.q_flow) + len(self.i_flow) + len(self.vm_m)

        magnitudes = np.zeros(nz)
        sigma = np.zeros(nz)

        # go through the measurements in order and form the vectors
        k = 0
        for m in self.p_flow + self.p_inj + self.q_flow + self.q_inj + self.i_flow + self.vm_m:
            magnitudes[k] = m.val
            sigma[k] = m.sigma
            k += 1

        return magnitudes, sigma


class StateEstimationResults(PowerFlowResults):

    def __init__(self, n, m, n_tr, bus_names, branch_names, transformer_names, bus_types):
        """

        :param n:
        :param m:
        :param n_tr:
        :param bus_names:
        :param branch_names:
        :param transformer_names:
        :param bus_types:
        """
        # initialize the
        PowerFlowResults.__init__(self,
                                  n=n,
                                  m=m,
                                  n_tr=n_tr,
                                  n_hvdc=0,
                                  bus_names=bus_names,
                                  branch_names=branch_names,
                                  transformer_names=transformer_names,
                                  hvdc_names=(),
                                  bus_types=bus_types)


class StateEstimation(DriverTemplate):

    def __init__(self, circuit: MultiCircuit):
        """
        Constructor
        :param circuit: circuit object
        """

        DriverTemplate.__init__(self, grid=circuit)

        self.results = None

    @staticmethod
    def collect_measurements(circuit: MultiCircuit, bus_idx, branch_idx):
        """
        Form the input from the circuit measurements
        :return: nothing, the input object is stored in this class
        """
        se_input = StateEstimationInput()

        # collect the bus measurements
        for i in bus_idx:

            for m in circuit.buses[i].measurements:

                if m.measurement_type == MeasurementType.Pinj:
                    se_input.p_inj_idx.append(i)
                    se_input.p_inj.append(m)

                elif m.measurement_type == MeasurementType.Qinj:
                    se_input.q_inj_idx.append(i)
                    se_input.q_inj.append(m)

                elif m.measurement_type == MeasurementType.Vmag:
                    se_input.vm_m_idx.append(i)
                    se_input.vm_m.append(m)

                else:
                    raise Exception('The bus ' + str(circuit.buses[i]) + ' contains a measurement of type '
                                    + str(m.measurement_type))

        # collect the branch measurements
        branches = circuit.get_branches()
        for i in branch_idx:

            # branch = circuit.branches[i]

            for m in branches[i].measurements:

                if m.measurement_type == MeasurementType.Pflow:
                    se_input.p_flow_idx.append(i)
                    se_input.p_flow.append(m)

                elif m.measurement_type == MeasurementType.Qflow:
                    se_input.q_flow_idx.append(i)
                    se_input.q_flow.append(m)

                elif m.measurement_type == MeasurementType.Iflow:
                    se_input.i_flow_idx.append(i)
                    se_input.i_flow.append(m)

                else:
                    raise Exception('The branch ' + str(branches[i]) + ' contains a measurement of type '
                                    + str(m.measurement_type))

        return se_input

    def run(self):
        """
        Run state estimation
        :return:
        """
        n = len(self.grid.buses)
        m = self.grid.get_branch_number()

        numerical_circuit = compile_snapshot_circuit(self.grid)
        self.results = StateEstimationResults(n=n, m=m,
                                              n_tr=numerical_circuit.ntr,
                                              bus_names=numerical_circuit.bus_names,
                                              branch_names=numerical_circuit.branch_names,
                                              transformer_names=numerical_circuit.transformer_data.tr_names,
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
            report = bs.ConvergenceReport()
            solution = solve_se_lm(Ybus=island.Ybus,
                                   Yf=island.Yf,
                                   Yt=island.Yt,
                                   f=island.F,
                                   t=island.T,
                                   se_input=se_input,
                                   ref=island.vd,
                                   pq=island.pq,
                                   pv=island.pv)

            report.add(method=bs.SolverType.LM,
                       converged=solution.converged,
                       error=solution.norm_f,
                       elapsed=solution.elapsed,
                       iterations=solution.iterations)

            # Compute the branches power and the slack buses power
            Sfb, Stb, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process(calculation_inputs=island,
                                                                                       Sbus=island.Sbus,
                                                                                       V=solution.V,
                                                                                       branch_rates=island.branch_rates,
                                                                                       Yf=None, Yt=None)

            # pack results into a SE results object
            results = StateEstimationResults(n=island.nbus,
                                             m=island.nbr,
                                             n_tr=island.ntr,
                                             bus_names=island.bus_names,
                                             branch_names=island.branch_names,
                                             transformer_names=island.transformer_data.tr_names,
                                             bus_types=island.bus_types)
            results.Sbus = Sbus
            results.Sf = Sfb
            results.voltage = solution.V
            results.losses = losses
            results.loading = loading
            results.convergence_reports.append(report)

            self.results.apply_from_island(results,
                                           island.original_bus_idx,
                                           island.original_branch_idx,
                                           island.original_tr_idx)


if __name__ == '__main__':
    pass