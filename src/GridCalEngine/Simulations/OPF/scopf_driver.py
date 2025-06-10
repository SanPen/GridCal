# scopf_driver.py
# SPDX-License-Identifier: MPL-2.0
import json
import os
import time

import numpy as np
from typing import List, Dict
from dataclasses import dataclass

from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import LinearMultiContingencies
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.OPF.scopf_results import SCOPFResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.enumerations import SimulationTypes, EngineType, SolverType, AcOpfMode
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import (run_nonlinear_MP_opf, run_nonlinear_SP_scopf)


# @dataclass
# class SCOPFResult:
#     Pg: np.ndarray  # Base‐case generator outputs
#     contingency_outputs: List[Dict]  # One dict per branch and per contingency
#     converged: bool


class SCOPFDriver(TimeSeriesDriverTemplate):
    name = 'Security-constrained optimal power flow'
    tpe = SimulationTypes.SCOPF_run

    def __init__(self,
                 grid: MultiCircuit,
                 pf_options: PowerFlowOptions,
                 scopf_options: OptimalPowerFlowOptions,
                 engine: EngineType = EngineType.GridCal):
        super().__init__(grid=grid,
                         time_indices=None,
                         clustering_results=None,
                         engine=engine,
                         check_time_series=False)

        self.scopf_options = scopf_options
        self.pf_options = pf_options
        # Will hold the final SCOPFResult
        self.results: SCOPFResults = None

    #
    # def run(self) -> SCOPFResults:
    #     """
    #     Runs the security-constrained optimal power flow (SCOPF) simulation.
    #
    #     :return: SCOPFResults object containing the results of the simulation.
    #     """
    #     # Call the actual SCOPF run method
    #     scopf_res = case_loop()


    def run(self) -> SCOPFResults:
        import numpy as np
        import time
        from GridCalEngine.Simulations.SCOPF_GNN.NumericalMethods.scopf import (
            run_nonlinear_MP_opf, run_nonlinear_SP_scopf
        )
        self.scopf_options.acopf_mode = AcOpfMode.ACOPFslacks
        self.scopf_options.ips_tolerance = 1e-6
        time_start = time.time()
        grid = self.grid
        pf_options = self.pf_options
        scopf_options = self.scopf_options


        # Monitor branch loading
        for line in grid.lines:
            line.monitor_loading = True
        for tr in grid.transformers2w:
            tr.monitor_loading = True

        perturbation_factor = 0.0  # ±10%

        for load in grid.loads:
            original_P = load.P
            delta_P = (np.random.rand() * 2 - 1) * perturbation_factor * max(original_P, 1.0)
            load.P = max(original_P + delta_P, 0.0)  # Ensure P stays ≥ 0

            original_Q = load.Q
            delta_Q = (np.random.rand() * 2 - 1) * perturbation_factor * max(original_Q, 1.0)
            load.Q = max(original_Q + delta_Q, 0.0)  # Ensure Q stays ≥ 0

        nc = compile_numerical_circuit_at(grid, t_idx=None)

        # Run base OPF
        acopf_results = run_nonlinear_MP_opf(nc=nc,
                                             pf_options=pf_options,
                                             opf_options=scopf_options,
                                             pf_init=False,
                                             load_shedding=False)

        linear_multiple_contingencies = LinearMultiContingencies(grid, grid.get_contingency_groups())
        prob_cont = 0
        max_iter = 10
        tolerance = 1e-5

        n_con_groups = len(linear_multiple_contingencies.contingency_groups_used)
        n_con_all = n_con_groups * 100
        v_slacks = np.zeros(n_con_all)
        f_slacks = np.zeros(n_con_all)
        W_k_vec = np.zeros(n_con_all)
        Z_k_vec = np.zeros((n_con_all, nc.generator_data.nelm))
        u_j_vec = np.zeros((n_con_all, nc.generator_data.nelm))

        contingency_outputs = []
        num_perturbations = 1
        for p in range(num_perturbations):
            print(f"\n====== Perturbation case {p + 1} of {num_perturbations} ======\n")

            for klm in range(max_iter):
                viols = 0
                W_k_local = np.zeros(n_con_groups)
                br_lists = grid.get_branch_lists()
                all_branches = [br for group in br_lists for br in group]

                for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):

                    contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]
                    print(f"\nContingency group {ic}: {contingency_group.name}")

                    if contingencies is None:
                        print(f"Contingencies have not been initialised.")
                        break

                    # Set contingency status
                    nc.set_con_or_ra_status(contingencies)

                    for cont in contingencies:
                        try:
                            br_idx = next(i for i, br in enumerate(all_branches) if br.name == cont.name)
                            nc.passive_branch_data.active[br_idx] = False  # Deactivate the affected branch

                            # Rebuild islands after modification
                            islands = nc.split_into_islands(ignore_single_node_islands=False)

                            if len(islands) > 1:
                                island_sizes = [island.nbus for island in islands]
                                largest_island_idx = np.argmax(island_sizes)
                                island = islands[largest_island_idx]
                            else:
                                island = islands[0]

                            indices = island.get_simulation_indices()

                            if len(indices.vd) > 0:
                                print('Selected island with size:', island.nbus)

                                slack_sol_cont = run_nonlinear_SP_scopf(
                                    nc=island,
                                    pf_options=pf_options,
                                    opf_options=scopf_options,
                                    pf_init=False,
                                    mp_results=acopf_results,
                                    load_shedding=False,
                                )
                                print(f"Error: {slack_sol_cont.error}")

                                # Collect slacks
                                v_slack = max(np.maximum(slack_sol_cont.sl_vmax, slack_sol_cont.sl_vmin))
                                f_slack = max(np.maximum(slack_sol_cont.sl_sf, slack_sol_cont.sl_st))
                                v_slacks[ic] = v_slack
                                f_slacks[ic] = f_slack
                                W_k_local[ic] = slack_sol_cont.W_k

                                print(f"Error: {slack_sol_cont.error}")
                                print(f"u_j: {slack_sol_cont.u_j}")

                                if slack_sol_cont.W_k > tolerance:
                                    W_k_vec[prob_cont] = slack_sol_cont.W_k
                                    Z_k_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.Z_k
                                    u_j_vec[prob_cont, island.generator_data.original_idx] = slack_sol_cont.u_j
                                    prob_cont += 1
                                    viols += 1
                                    print('VIOLATION')

                                # print('nbus', island.nbus, 'ngen', island.ngen)
                                print(f"W_k: {slack_sol_cont.W_k}")
                                print(f"Z_k: {slack_sol_cont.Z_k}")
                                print(f"u_j: {slack_sol_cont.u_j}")
                                print(f"Vmax slack: {slack_sol_cont.sl_vmax}")
                                print(f"Vmin slack: {slack_sol_cont.sl_vmin}")
                                print(f"Sf slack: {slack_sol_cont.sl_sf}")
                                print(f"St slack: {slack_sol_cont.sl_st}")

                                for line in grid.lines:
                                    from_idx = grid.buses.index(line.bus_from)
                                    to_idx = grid.buses.index(line.bus_to)
                                    contingency_outputs.append({
                                        "from_bus": from_idx,
                                        "to_bus": to_idx,
                                        "R": line.R,
                                        "X": line.X,
                                        "B": line.B,
                                        "is_active": bool(nc.passive_branch_data.active[grid.lines.index(line)])
                                    })

                                contingency_outputs.append({
                                    "contingency_index": int(ic),
                                    "W_k": float(slack_sol_cont.W_k),
                                    "Z_k": slack_sol_cont.Z_k.tolist(),
                                    "u_j": slack_sol_cont.u_j.tolist(),
                                    "Pg": acopf_results.Pg.tolist(),
                                })

                            else:
                                print("No valid voltage-dependent nodes found in island. Skipping.")

                            nc.passive_branch_data.active[br_idx] = True
                        except StopIteration:
                            print(f"Line with name '{cont.name}' not found in grid.lines. Skipping.")

                    # Revert contingency
                    nc.set_con_or_ra_status(contingencies, revert=True)

                if viols > 0:
                    # crop the dimension 0
                    W_k_vec_used = W_k_vec[:prob_cont]
                    Z_k_vec_used = Z_k_vec[:prob_cont, :]
                    u_j_vec_used = u_j_vec[:prob_cont, :]

                # Store metrics for this iteration
                # if viols > 0:
                #     iteration_data['max_wk'].append(W_k_local.max())
                #     iteration_data['max_voltage_slack'].append(v_slacks.max())
                #     iteration_data['avg_voltage_slack'].append(v_slacks.mean())
                #     iteration_data['max_flow_slack'].append(f_slacks.max())
                #     iteration_data['avg_flow_slack'].append(f_slacks.mean())
                # else:
                #     iteration_data['max_wk'].append(1e-10)
                #     iteration_data['max_voltage_slack'].append(1e-10)
                #     iteration_data['avg_voltage_slack'].append(1e-10)
                #     iteration_data['max_flow_slack'].append(1e-10)
                #     iteration_data['avg_flow_slack'].append(1e-10)
                #     print('Master problem solution found')
                #
                # iteration_data['num_violations'].append(viols)

                # Run the MP with information from the SPs
                print('')
                print("--- Feeding SPs info to MP ---")
                acopf_results = run_nonlinear_MP_opf(nc=nc,
                                                     pf_options=pf_options,
                                                     opf_options=scopf_options,
                                                     pf_init=False,
                                                     W_k_vec=W_k_vec_used,
                                                     Z_k_vec=Z_k_vec_used,
                                                     u_j_vec=u_j_vec_used,
                                                     load_shedding=False)

                # Store generation cost
                total_cost = np.sum(acopf_results.Pcost)
                # iteration_data['total_cost'].append(total_cost)
                #
                # # Print current iteration metrics
                # print(f"Maximum W_k: {iteration_data['max_wk'][-1]}")
                # print(f"Number of violations: {iteration_data['num_violations'][-1]}")
                # print(f"Maximum voltage slack: {iteration_data['max_voltage_slack'][-1]}")
                # print(f"Average voltage slack: {iteration_data['avg_voltage_slack'][-1]}")
                # print(f"Maximum flow slack: {iteration_data['max_flow_slack'][-1]}")
                # print(f"Average flow slack: {iteration_data['avg_flow_slack'][-1]}")
                # print(f"Total generation cost: {total_cost}")

                if viols == 0:
                    break
                # iteration_data['num_cuts'].append(prob_cont)
                # print(f"Total number of cuts: {iteration_data['num_cuts'][-1]}")
                # print('-')
                # print('Length W_k_vec', len(W_k_vec))

                # print(f"W_k_vec: {W_k_vec}")
                # print(f"Z_k_vec: {Z_k_vec}")
                # print(f"u_j_vec: {u_j_vec}")
                #
                # save_dir = "/Users/CristinaFray/PycharmProjects/GridCal/src/GridCalEngine/Simulations/SCOPF_GNN/new_aug_data/scopf_outputs_39"
                # os.makedirs(save_dir, exist_ok=True)
                # save_path = os.path.join(save_dir, f"scopf_result_39_{klm:03d}.json")
                # with open(save_path, "w") as f:
                #     json.dump(contingency_outputs, f, indent=2)

                # print(f"Saved results for perturbation {p} to {save_path}")

        time_end = time.time()
        print(f"SCOPF completed in {time_end - time_start:.2f} seconds")

        from GridCalEngine.Simulations.OPF.scopf_results import SCOPFResults

        self.results = SCOPFResults(
            bus_names=np.array([bus.name for bus in self.grid.buses]),
            generator_names=np.array([gen.name for gen in self.grid.generators]),
            branch_names=np.array([line.name for line in self.grid.lines]),
            Pg=acopf_results.Pg,
            contingency_outputs=contingency_outputs,
            converged=(viols == 0)
        )

        return self.results

        def opf(self, remote=False, batteries_energy_0=None) -> OptimalPowerFlowResults:
            """
            Run a power flow for every circuit
            :param remote: is this function being called from the time series?
            :param batteries_energy_0: initial state of the batteries, if None the default values are taken
            :return: OptimalPowerFlowResults object
            """

            self.report_progress(0.0)
            for it, t in enumerate(self.time_indices):

                # report progress
                self.report_text('Nonlinear OPF at ' + str(self.grid.time_profile[t]) + '...')
                self.report_progress2(it, len(self.time_indices))

                # run opf
                res = run_nonlinear_opf(
                    grid=self.grid,
                    opf_options=self.options,
                    pf_options=self.pf_options,
                    t_idx=t,
                    # for the first power flow, use the given strategy
                    # for the successive ones, use the previous solution
                    pf_init=self.options.ips_init_with_pf if it == 0 else True,
                    Sbus_pf0=self.results.Sbus[it - 1, :] if it > 0 else None,
                    voltage_pf0=self.results.voltage[it - 1, :] if it > 0 else None,
                    logger=self.logger
                )
                Sbase = self.grid.Sbase
                self.results.voltage[it, :] = res.V
                self.results.Sbus[it, :] = res.S * Sbase
                self.results.bus_shadow_prices[it, :] = res.lam_p
                # self.results.load_shedding = npa_res.load_shedding[0, :]
                # self.results.battery_power = npa_res.battery_p[0, :]
                # self.results.battery_energy = npa_res.battery_energy[0, :]
                self.results.generator_power[it, :] = res.Pg * Sbase
                self.results.generator_reactive_power[it, :] = res.Qg * Sbase
                self.results.generator_cost[it, :] = res.Pcost

                self.results.shunt_like_reactive_power[it, :] = res.Qsh * Sbase

                self.results.Sf[it, :] = res.Sf * Sbase
                self.results.St[it, :] = res.St * Sbase
                self.results.overloads[it, :] = (res.sl_sf - res.sl_st) * Sbase
                self.results.loading[it, :] = res.loading
                self.results.phase_shift[it, :] = res.tap_phase

                self.results.hvdc_Pf[it, :] = res.hvdc_Pf
                self.results.hvdc_loading[it, :] = res.hvdc_loading
                self.results.converged[it] = res.converged

                if self.__cancel__:
                    return self.results

            # Compute the emissions, fuel costs and energy used
            (self.results.system_fuel,
             self.results.system_emissions,
             self.results.system_energy_cost) = self.get_fuel_emissions_energy_calculations(
                gen_p=self.results.generator_power,
                gen_cost=self.results.generator_cost
            )