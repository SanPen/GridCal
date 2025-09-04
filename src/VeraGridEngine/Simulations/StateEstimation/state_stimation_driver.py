# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union

from VeraGridEngine.Simulations.StateEstimation.observability_analysis import \
    check_for_observability_and_return_unobservable_buses, add_pseudo_measurements_for_unobservable_buses
from VeraGridEngine.Simulations.StateEstimation.pseudo_measurements_augmentation import PseudoMeasurement
from VeraGridEngine.Simulations.StateEstimation.state_estimation_results import StateEstimationResults
from VeraGridEngine.basic_structures import ConvergenceReport
from VeraGridEngine.Simulations.StateEstimation.state_estimation import solve_se_nr, solve_se_lm, solve_se_gauss_newton, \
    decoupled_state_estimation
from VeraGridEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.enumerations import SolverType


class StateEstimationOptions:

    def __init__(self, solver: SolverType = SolverType.NR,
                 tol: float = 1e-8, max_iter: int = 100, verbose: int = 0,
                 prefer_correct: bool = True, c_threshold: int = 4.0,
                 fixed_slack: bool = False, run_observability_analyis: bool = False,
                 add_pseudo_measurements: bool = False,run_measurement_profiling:bool=False,
                 include_line_measurements_on_both_ends:bool=True,
                 pseudo_meas_std: float = 1.0):
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
        self.fixed_slack= fixed_slack
        self.observability_analysis = run_observability_analyis
        self.add_pseudo_measurements = add_pseudo_measurements
        self.pseudo_meas_std= pseudo_meas_std
        self.run_meas_profiling= run_measurement_profiling
        self.include_line_measurements_on_both_ends = include_line_measurements_on_both_ends


class StateEstimationConvergenceReport(ConvergenceReport):
    def __init__(self) -> None:
        """
        Constructor
        """
        super().__init__()
        self.bad_data_detected = False
        self.unobservable_buses = list()
        self.bus_contribution = list()
        self.pseudo_measurements = list()
        self.is_observable = True
        self.measurement_profile = list()

    def add_se(self, method,
               converged: bool,
               error: float,
               elapsed: float,
               iterations: int,
               bad_data_detected: bool,
               is_observable: bool,
               bus_contribution: list,
               pseudo_measurements: list,
               unobservable_buses: list,
               measurement_profile:dict):
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
        self.bad_data_detected=bad_data_detected
        self.is_observable=is_observable
        self.add_bus_contribution(bus_contribution)
        self.add_pseudo_measurements(pseudo_measurements)
        self.add_unobservable_buses(unobservable_buses)
        self.measurement_profile.append(measurement_profile)

    def is_observable(self) -> bool:
        """
        Get info is the island was observable
        :return: List of is_obsevable booleans
        """
        return self.is_observable

    def get_bad_data_detected(self) -> bool:
        """
        Get bad data detection results
        :return: List of bad data detection results
        """
        return self.bad_data_detected

    def get_unobservable_buses(self) -> list:
        return self.unobservable_buses

    def get_bus_contribution(self) -> list:
        return self.bus_contribution

    def get_pseudo_measurements(self) -> list:
        return self.pseudo_measurements

    def add_unobservable_buses(self, unobservable_buses):
        self.unobservable_buses.append(unobservable_buses)

    def add_bus_contribution(self, bus_contribution):
        self.bus_contribution.append(bus_contribution)

    def add_pseudo_measurements(self, se_input):
        for m in se_input.p_inj:
            if isinstance(m, PseudoMeasurement):
                self.pseudo_measurements.append(m)

    def add_measurement_profile(self, meas_profile):
        self.measurement_profile.append(meas_profile)

    def get_measurement_profile(self) -> list:
        return self.measurement_profile


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

            bus_dict = {i:self.grid.buses[idx] for i, idx in enumerate(island.bus_data.original_idx)}

            conn = island.get_connectivity_matrices()

            report = StateEstimationConvergenceReport()

            is_observable = True # by default we consider it True, if SE diverges and LM solver is chosen there assert
            # statement explicitly mentions unobservability, if user runs observability analysis, this boolean is
            # assigned as per standard output
            solution = None  # initialized so observability results can be saved without running SE
            unobservable_buses=[]
            bus_contrib={}
            measurement_profile={}

            # the idea is to first run observability analysis uif user wants then the normal SE
            if self.options.observability_analysis:
                # this will provide the result of unobservable branches
                # here we have to store Jacobian and measurements so that it is not again recalculated in
                # State estimation calculations
                # if pseudo meas is allowed it will create meas at the unobser branches so that the net is observable
                # in that case Jacobian needs to be called again in SE formulations(needs to be worked upon)
                is_observable, unobservable_buses, measurement_profile, V, bus_contrib = check_for_observability_and_return_unobservable_buses(
                    nc=island,
                    Ybus=adm.Ybus,
                    Yf=adm.Yf,
                    Yt=adm.Yt,
                    no_slack=idx.no_slack,
                    F=island.passive_branch_data.F,
                    T=island.passive_branch_data.T,
                    Cf=conn.Cf,
                    Ct=conn.Ct,
                    se_input=se_input_island,
                    fixed_slack=self.options.fixed_slack,
                    do_profiling_of_measurements=self.options.run_meas_profiling,
                    include_line_measurements_on_both_ends=self.options.include_line_measurements_on_both_ends,
                    logger=self.logger)
                if unobservable_buses and self.options.add_pseudo_measurements:
                    se_input_island = add_pseudo_measurements_for_unobservable_buses(bus_dict=bus_dict,
                                                                                     unobservable_buses=unobservable_buses,
                                                                                     se_input=se_input_island, V=V,
                                                                                     Ybus=adm.Ybus,
                                                                                     Cf=conn.Cf,
                                                                                     Ct=conn.Ct,
                                                                                     sigma_pseudo_meas_value=
                                                                                     self.options.pseudo_meas_std,
                                                                                     Sbase=nc.Sbase,
                                                                                     logger=self.logger)
            # run Solver
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
            elif self.options.solver == SolverType.Decoupled_LU:
                solution = decoupled_state_estimation(nc=island,
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
            elif SolverType.NoSolver:
                self.logger.add_info(f"Solver_Type is not defined explicitly to run observability analysis only")
            else:
                raise ValueError(f"State Estimation solver type not recognized: {self.options.solver.value}")


            # we need to switch is_observable back to True in case the pseudo measurements were added and SE converged
            # if not is_observable and self.options.add_pseudo_measurements and solution.converged:
            #     is_observable=True
            # we leave unobservable buses and bus_contrinb as record that pseudo measurements were added

            report.add_se(method=self.options.solver,
                          converged=solution.converged if solution else False,
                          error=solution.norm_f if solution else 1e9,
                          elapsed=solution.elapsed if solution else 0,
                          iterations=solution.iterations if solution else 0,
                          bad_data_detected=solution.bad_data_detected if solution else is_observable,
                          is_observable=solution.is_observable if solution else is_observable ,
                          unobservable_buses=unobservable_buses,
                          bus_contribution=bus_contrib,
                          measurement_profile=measurement_profile,
                          pseudo_measurements=se_input_island)

            self.results.convergence_reports.append(report)

            # Scale power results from per-unit to MVA before applying
            island_sbase = island.Sbase
            if solution is not None:
                solution.Scalc *= island_sbase

                self.results.apply_from_island(
                    results=solution,
                    b_idx=island.bus_data.original_idx,
                    br_idx=island.passive_branch_data.original_idx,
                    hvdc_idx=island.hvdc_data.original_idx,
                    vsc_idx=island.vsc_data.original_idx
                )
            # export unobservable buses, bus_contrib and/or measurement profiling to json

        self.toc()
