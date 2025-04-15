
from GridCalEngine.Simulations.OPF.NumericalMethods.scopf import *

def case_loop() -> None:
    """
    Simple 5 bus system from where to build the SCOPF, looping
    :return:
    """
    # Load basic grid
    file_path = 'IEEE 5 Bus_exp.gridcal'
    grid = FileOpen(file_path).open()

    # Set options
    pf_options = PowerFlowOptions(control_q=False)
    opf_base_options = OptimalPowerFlowOptions(ips_method=SolverType.NR,
                                               ips_tolerance=1e-8,
                                               ips_iterations=50,
                                               acopf_mode=AcOpfMode.ACOPFstd)
    opf_slack_options = OptimalPowerFlowOptions(ips_method=SolverType.NR,
                                                ips_tolerance=1e-8,
                                                ips_iterations=50,
                                                acopf_mode=AcOpfMode.ACOPFslacks)

    nc = compile_numerical_circuit_at(grid, t_idx=None)
    acopf_results = run_nonlinear_MP_opf(nc=nc, pf_options=pf_options,
                                         opf_options=opf_slack_options, pf_init=True)

    print()
    print(f"--- Base case ---")
    print(f"Base OPF loading {acopf_results.loading} .")
    print(f"Voltage magnitudes: {acopf_results.Vm}")
    print(f"Generators P: {acopf_results.Pg}")
    print(f"Generators Q: {acopf_results.Qg}")
    print(f"Error: {acopf_results.error}")

    print()
    print("--- Starting loop with fixed number of repetitions, then breaking ---")

    # Initialize tracking dictionary
    iteration_data = {
        'max_wk': [],
        'num_violations': [],
        'max_voltage_slack': [],
        'avg_voltage_slack': [],
        'max_flow_slack': [],
        'avg_flow_slack': [],
        'total_cost': []
    }

    linear_multiple_contingencies = LinearMultiContingencies(grid, grid.get_contingency_groups())

    # Start main loop over iterations
    for klm in range(20):
        print(f"General iteration {klm + 1} of 20")

        n_con_groups = len(linear_multiple_contingencies.contingency_groups_used)

        # Global slack and weight trackers
        v_slacks = np.zeros(n_con_groups)
        f_slacks = np.zeros(n_con_groups)
        prob_cont = 0
        W_k_vec = np.zeros(n_con_groups)
        Z_k_vec = np.zeros((n_con_groups, nc.bus_data.nbus))
        u_j_vec = np.zeros((n_con_groups, nc.bus_data.nbus))
        W_k_local = np.zeros(n_con_groups)

        for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):

            contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]
            print(f"\nContingency group {ic}: {contingency_group.name} (Category: {contingency_group.category})")

            # Set contingency status
            nc.set_con_or_ra_status(contingencies)

            for cont in contingencies:
                try:
                    line_idx = next(i for i, l in enumerate(grid.lines) if l.name == cont.name)
                    nc.passive_branch_data.active[line_idx] = False  # Deactivate the affected line

                    # Rebuild islands after modification
                    islands = nc.split_into_islands()

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
                            opf_options=opf_slack_options,
                            pf_init=True,
                            mp_results=acopf_results
                        )

                        # Collect slacks
                        v_slack = max(np.maximum(slack_sol_cont.sl_vmax, slack_sol_cont.sl_vmin))
                        f_slack = max(np.maximum(slack_sol_cont.sl_sf, slack_sol_cont.sl_st))
                        v_slacks[ic] = v_slack
                        f_slacks[ic] = f_slack

                        if slack_sol_cont.W_k > 0.0001:
                            W_k_vec[ic] = slack_sol_cont.W_k
                            Z_k_vec[ic, island.bus_data.original_idx] = slack_sol_cont.Z_k
                            u_j_vec[ic, island.bus_data.original_idx] = slack_sol_cont.u_j
                            prob_cont += 1
                        W_k_local[ic] = slack_sol_cont.W_k

                        print('nbus', island.nbus, 'ngen', island.ngen)

                    else:
                        print("No valid voltage-dependent nodes found in island. Skipping.")

                    nc.passive_branch_data.active[line_idx] = True
                except StopIteration:
                    print(f"Line with name '{cont.name}' not found in grid.lines. Skipping.")

            # Revert contingency
            nc.set_con_or_ra_status(contingencies, revert=True)

        # Store metrics for this iteration
        iteration_data['max_wk'].append(W_k_local.max())
        iteration_data['num_violations'].append(prob_cont)
        iteration_data['max_voltage_slack'].append(v_slacks.max())
        iteration_data['avg_voltage_slack'].append(v_slacks.mean())
        iteration_data['max_flow_slack'].append(f_slacks.max())
        iteration_data['avg_flow_slack'].append(f_slacks.mean())

        # Run the MP with information from the SPs
        print("--- Feeding SPs info to MP ---")
        acopf_results = run_nonlinear_MP_opf(nc=nc,
                                             pf_options=pf_options,
                                             opf_options=opf_slack_options,
                                             pf_init=True,
                                             W_k_vec=W_k_vec,
                                             Z_k_vec=Z_k_vec,
                                             u_j_vec=u_j_vec)

        # Store generation cost
        total_cost = np.sum(acopf_results.Pcost)
        iteration_data['total_cost'].append(total_cost)

        # Print current iteration metrics
        print(f"Maximum W_k: {iteration_data['max_wk'][-1]}")
        print(f"Number of violations: {iteration_data['num_violations'][-1]}")
        print(f"Maximum voltage slack: {iteration_data['max_voltage_slack'][-1]}")
        print(f"Average voltage slack: {iteration_data['avg_voltage_slack'][-1]}")
        print(f"Maximum flow slack: {iteration_data['max_flow_slack'][-1]}")
        print(f"Average flow slack: {iteration_data['avg_flow_slack'][-1]}")
        print(f"Total generation cost: {total_cost}")

        if prob_cont == 0:
            break

    # Plot the results
    plot_scopf_progress(iteration_data)

    return None


if __name__ == '__main__':
    # case_v0()
    case_loop()
