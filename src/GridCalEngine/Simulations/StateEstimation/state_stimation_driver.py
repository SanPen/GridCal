# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Union, Tuple
from GridCalEngine.basic_structures import Vec, ConvergenceReport
from GridCalEngine.Simulations.StateEstimation.state_estimation import solve_se_lm
from GridCalEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowResults
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.enumerations import SolverType


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
                                  n_vsc=0,
                                  n_gen=0,
                                  n_batt=0,
                                  n_sh=0,
                                  bus_names=bus_names,
                                  branch_names=branch_names,
                                  hvdc_names=hvdc_names,
                                  vsc_names=np.array([]),
                                  gen_names=np.empty(0, dtype=object),
                                  batt_names=np.empty(0, dtype=object),
                                  sh_names=np.empty(0, dtype=object),
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

        for elm in circuit.get_p_measurements():
            se_input.p_idx.append(bus_dict[elm.api_object])
            se_input.p_inj.append(elm)

        for elm in circuit.get_q_measurements():
            se_input.q_idx.append(bus_dict[elm.api_object])
            se_input.q_inj.append(elm)

        for elm in circuit.get_vm_measurements():
            se_input.vm_m_idx.append(bus_dict[elm.api_object])
            se_input.vm_m.append(elm)

        # branch measurements
        branch_dict = circuit.get_branches_wo_hvdc_index_dict()

        for elm in circuit.get_pf_measurements():
            se_input.pf_idx.append(branch_dict[elm.api_object])
            se_input.pf_value.append(elm)

        for elm in circuit.get_qf_measurements():
            se_input.qf_idx.append(branch_dict[elm.api_object])
            se_input.qf_value.append(elm)

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

        nc = compile_numerical_circuit_at(self.grid, logger=self.logger)
        self.results = StateEstimationResults(n=n,
                                              m=m,
                                              bus_names=nc.bus_data.names,
                                              branch_names=nc.passive_branch_data.names,
                                              hvdc_names=nc.hvdc_data.names,
                                              bus_types=nc.bus_data.bus_types)
        # self.se_results.initialize(n, m)

        islands = nc.split_into_islands()

        for island in islands:
            idx = island.get_simulation_indices()
            adm = island.get_admittance_matrices()

            # collect inputs of the island
            se_input = self.collect_measurements(circuit=self.grid,
                                                 bus_idx=island.bus_data.original_idx,
                                                 branch_idx=island.passive_branch_data.original_idx)

            # run solver
            report = ConvergenceReport()
            solution = solve_se_lm(nc=island,
                                   Ybus=adm.Ybus,
                                   Yf=adm.Yf,
                                   Yt=adm.Yt,
                                   Yshunt_bus=adm.Yshunt_bus,
                                   F=island.passive_branch_data.F,
                                   T=island.passive_branch_data.T,
                                   se_input=se_input,
                                   vd=idx.vd,
                                   pq=idx.pq,
                                   pv=idx.pv)

            report.add(method=SolverType.LM,
                       converged=solution.converged,
                       error=solution.norm_f,
                       elapsed=solution.elapsed,
                       iterations=solution.iterations)

            self.results.convergence_reports.append(report)

            self.results.apply_from_island(
                results=solution,
                b_idx=island.bus_data.original_idx,
                br_idx=island.passive_branch_data.original_idx,
                hvdc_idx=island.hvdc_data.original_idx,
                vsc_idx=island.vsc_data.original_idx
            )

        self.toc()
