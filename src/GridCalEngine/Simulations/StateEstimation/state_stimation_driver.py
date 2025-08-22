# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union

from GridCalEngine.Simulations.StateEstimation.state_estimation_results import StateEstimationResults
from GridCalEngine.basic_structures import ConvergenceReport
from GridCalEngine.Simulations.StateEstimation.state_estimation import solve_se_nr, solve_se_lm, solve_se_gauss_newton
from GridCalEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.enumerations import SolverType


class StateEstimationOptions:

    def __init__(self, solver: SolverType = SolverType.NR,
                 tol: float = 1e-9, max_iter: int = 100, verbose: int = 0,
                 prefer_correct: bool = True, c_threshold: int = 4.0,
                 fixed_slack: bool = False):
        """
        StateEstimationOptions
        :param tol: Tolerance
        :param max_iter: Maximum number of iterations
        :param verbose: Verbosity level (1 light, 2 heavy)
        :param prefer_correct: Prefer measurement correction? otherwise measurement deletion is used
        :param c_threshold: confidence threshold (default 4.0)
        :param fixed_slack: if true, the measurements on the slack bus are omitted
        """
        self.solver = solver
        self.tol = tol
        self.max_iter = max_iter
        self.verbose = verbose
        self.prefer_correct = prefer_correct
        self.c_threshold = c_threshold
        self.fixed_slack: bool = fixed_slack


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

        for elm in circuit.get_pg_measurements():
            se_input.pg_idx.append(bus_dict[elm.api_object.bus])
            se_input.pg_inj.append(elm)

        for elm in circuit.get_qg_measurements():
            se_input.qg_idx.append(bus_dict[elm.api_object.bus])
            se_input.qg_inj.append(elm)

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
                                              n_hvdc=nc.nhvdc,
                                              n_vsc=nc.nvsc,
                                              n_gen=nc.ngen,
                                              n_batt=nc.nbatt,
                                              n_sh=nc.nshunt,
                                              bus_names=nc.bus_data.names,
                                              branch_names=nc.passive_branch_data.names,
                                              hvdc_names=nc.hvdc_data.names,
                                              vsc_names=nc.vsc_data.names,
                                              gen_names=nc.generator_data.names,
                                              batt_names=nc.battery_data.names,
                                              sh_names=nc.shunt_data.names,
                                              bus_types=nc.bus_data.bus_types)
        # self.se_results.initialize(n, m)

        islands = nc.split_into_islands()

        # collect inputs of the island
        se_input = self.collect_measurements(circuit=self.grid)

        for island in islands:
            idx = island.get_simulation_indices()
            adm = island.get_admittance_matrices()

            se_input_island = se_input.slice(bus_idx=island.bus_data.original_idx,
                                             branch_idx=island.passive_branch_data.original_idx)

            conn = island.get_connectivity_matrices()

            # run solver
            if self.options.solver == SolverType.NR:
                solution = solve_se_nr(nc=island,
                                       Ybus=adm.Ybus,
                                       Yf=adm.Yf,
                                       Yt=adm.Yt,
                                       Yshunt_bus=adm.Yshunt_bus,
                                       F=island.passive_branch_data.F,
                                       T=island.passive_branch_data.T,
                                       Cf=conn.Cf,
                                       Ct=conn.Ct,
                                       se_input=se_input_island,
                                       vd=idx.vd,
                                       pv=idx.pv,
                                       no_slack=idx.no_slack,
                                       tol=self.options.tol,
                                       max_iter=self.options.max_iter,
                                       verbose=self.options.verbose,
                                       prefer_correct=self.options.prefer_correct,
                                       c_threshold=self.options.c_threshold,
                                       fixed_slack=self.options.fixed_slack,
                                       logger=self.logger)

            elif self.options.solver == SolverType.LM:
                solution = solve_se_lm(nc=island,
                                       Ybus=adm.Ybus,
                                       Yf=adm.Yf,
                                       Yt=adm.Yt,
                                       Yshunt_bus=adm.Yshunt_bus,
                                       F=island.passive_branch_data.F,
                                       T=island.passive_branch_data.T,
                                       Cf=conn.Cf,
                                       Ct=conn.Ct,
                                       se_input=se_input_island,
                                       vd=idx.vd,
                                       pv=idx.pv,
                                       no_slack=idx.no_slack,
                                       tol=self.options.tol,
                                       max_iter=self.options.max_iter,
                                       verbose=self.options.verbose,
                                       prefer_correct=self.options.prefer_correct,
                                       c_threshold=self.options.c_threshold,
                                       fixed_slack=self.options.fixed_slack,
                                       logger=self.logger)

            elif self.options.solver == SolverType.GN:
                solution = solve_se_gauss_newton(nc=island,
                                                 Ybus=adm.Ybus,
                                                 Yf=adm.Yf,
                                                 Yt=adm.Yt,
                                                 Yshunt_bus=adm.Yshunt_bus,
                                                 F=island.passive_branch_data.F,
                                                 T=island.passive_branch_data.T,
                                                 Cf=conn.Cf,
                                                 Ct=conn.Ct,
                                                 se_input=se_input_island,
                                                 vd=idx.vd,
                                                 pv=idx.pv,
                                                 no_slack=idx.no_slack,
                                                 tol=self.options.tol,
                                                 max_iter=self.options.max_iter,
                                                 verbose=self.options.verbose,
                                                 prefer_correct=self.options.prefer_correct,
                                                 c_threshold=self.options.c_threshold,
                                                 fixed_slack=self.options.fixed_slack,
                                                 logger=self.logger)
            else:
                raise ValueError(f"State Estimation solver type not recognized: {self.options.solver.value}")

            report = StateEstimationConvergenceReport()

            report.add_se(method=SolverType.LM,
                          converged=solution.converged,
                          error=solution.norm_f,
                          elapsed=solution.elapsed,
                          iterations=solution.iterations,
                          bad_data_detected=solution.bad_data_detected)

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
