# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Union

from GridCalEngine.Simulations.StateEstimation.state_estimation_results import StateEstimationResults
from GridCalEngine.basic_structures import ConvergenceReport, StateEstimationConverganceReport
from GridCalEngine.Simulations.StateEstimation.state_estimation import solve_se_lm
from GridCalEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowResults
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.enumerations import SolverType


class StateEstimationOptions:

    def __init__(self, tol: float = 1e-9, max_iter: int = 100, verbose: int = 0):
        self.tol = tol
        self.max_iter = max_iter
        self.verbose = verbose


class StateEstimationConvergenceReport(ConvergenceReport):
    def __init__(self) -> None:
        """
        Constructor
        """
        super().__init__()
        self.bad_data_detected = list()

    def add_se(self, method,
               converged: bool,
               error: float,
               elapsed: float,
               iterations: int,
               bad_data_detected: bool):
        """

        :param method:
        :param converged:
        :param error:
        :param elapsed:
        :param iterations:
        :param bad_data_detected:
        :return:
        """
        # Call parent's add method for common parameters
        self.add(method, converged, error, elapsed, iterations)
        self.bad_data_detected.append(bad_data_detected)

    def get_bad_data_detected(self) -> list:
        """
        Get bad data detection results

        :param method: Optional method name to filter results
        :return: List of bad data detection results
        """
        return self.bad_data_detected


class StateEstimation(DriverTemplate):

    def __init__(self, circuit: MultiCircuit, options: StateEstimationOptions | None = None):
        """
        Constructor
        :param circuit: circuit object
        """

        DriverTemplate.__init__(self, grid=circuit)

        self.results: Union[StateEstimationResults, None] = None

        self.options = StateEstimationOptions() if options is None else options

    @staticmethod
    def collect_measurements(circuit: MultiCircuit) -> StateEstimationInput:
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
            se_input.vm_idx.append(bus_dict[elm.api_object])
            se_input.vm_value.append(elm)

        for elm in circuit.get_va_measurements():
            se_input.va_idx.append(bus_dict[elm.api_object])
            se_input.va_value.append(elm)

        # branch measurements
        branch_dict = circuit.get_branches_index_dict(add_vsc=False, add_hvdc=False, add_switch=True)

        for elm in circuit.get_pf_measurements():
            se_input.pf_idx.append(branch_dict[elm.api_object])
            se_input.pf_value.append(elm)

        for elm in circuit.get_pt_measurements():
            se_input.pt_idx.append(branch_dict[elm.api_object])
            se_input.pt_value.append(elm)

        for elm in circuit.get_qf_measurements():
            se_input.qf_idx.append(branch_dict[elm.api_object])
            se_input.qf_value.append(elm)

        for elm in circuit.get_qt_measurements():
            se_input.qt_idx.append(branch_dict[elm.api_object])
            se_input.qt_value.append(elm)

        for elm in circuit.get_if_measurements():
            se_input.if_idx.append(branch_dict[elm.api_object])
            se_input.if_value.append(elm)

        for elm in circuit.get_it_measurements():
            se_input.it_idx.append(branch_dict[elm.api_object])
            se_input.it_value.append(elm)

        return se_input

    def run(self):
        """
        Run state estimation
        :return:
        """
        self.tic()
        n = len(self.grid.buses)
        m = self.grid.get_branch_number(add_vsc=False,
                                        add_hvdc=False,
                                        add_switch=True)

        nc = compile_numerical_circuit_at(self.grid, logger=self.logger)
        self.results = StateEstimationResults(n=n,
                                              m=m,
                                              bus_names=nc.bus_data.names,
                                              branch_names=nc.passive_branch_data.names,
                                              hvdc_names=nc.hvdc_data.names,
                                              bus_types=nc.bus_data.bus_types,
                                              V=np.ones(n, dtype=complex), Scalc=nc.Sbase,
                                              m_values=np.ones(nc.nbr, dtype=float),
                                              tau=np.zeros(nc.nbr, dtype=float), Sf=np.zeros(nc.nbr, dtype=complex),
                                              St=np.zeros(nc.nbr, dtype=complex),  # Placeholder branch power flow (to)
                                              If=np.zeros(nc.nbr, dtype=complex),  # Placeholder branch current (from)
                                              It=np.zeros(nc.nbr, dtype=complex),  # Placeholder branch current (to)
                                              loading=np.zeros(nc.nbr, dtype=float),  # Placeholder loading
                                              losses=np.zeros(nc.nbr, dtype=complex),  # Placeholder losses
                                              Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                              St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                              If_vsc=np.zeros(nc.nvsc, dtype=float),
                                              It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                              losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                              loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                              Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                              St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                              losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                              loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                              norm_f=50,
                                              converged=False,
                                              iterations=0,
                                              elapsed=0,
                                              bad_data_detected=False
                                              )
        # self.se_results.initialize(n, m)

        islands = nc.split_into_islands()

        # collect inputs of the island
        se_input = self.collect_measurements(circuit=self.grid)

        for island in islands:
            idx = island.get_simulation_indices()
            adm = island.get_admittance_matrices()

            se_input_island = se_input.slice(bus_idx=island.bus_data.original_idx,
                                             branch_idx=island.passive_branch_data.original_idx)

            # run solver
            solution = solve_se_lm(nc=island,
                                   Ybus=adm.Ybus,
                                   Yf=adm.Yf,
                                   Yt=adm.Yt,
                                   Yshunt_bus=adm.Yshunt_bus,
                                   F=island.passive_branch_data.F,
                                   T=island.passive_branch_data.T,
                                   se_input=se_input_island,
                                   vd=idx.vd,
                                   pv=idx.pv,
                                   no_slack=idx.no_slack,
                                   tol=self.options.tol,
                                   max_iter=self.options.max_iter,
                                   verbose=self.options.verbose,
                                   logger=self.logger)

            report = StateEstimationConvergenceReport()

            report.add_se(method=SolverType.LM,
                          converged=solution.converged,
                          error=solution.norm_f,
                          elapsed=solution.elapsed,
                          iterations=solution.iterations,
                          bad_data_detected=solution.bad_data_detected)
            breakpoint()
            self.results.convergence_reports.append(report)

            # Scale power results from per-unit to MVA before applying
            island_sbase = island.Sbase
            solution.Scalc *= island_sbase

            self.results.apply_from_island(
                results=solution,
                b_idx=island.bus_data.original_idx,
                br_idx=island.passive_branch_data.original_idx,
                hvdc_idx=island.hvdc_data.original_idx,
                vsc_idx=island.vsc_data.original_idx
            )

        self.toc()
