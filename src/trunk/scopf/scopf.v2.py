# # import os
# # import numpy as np
# # import GridCalEngine.api as gce
# # from GridCalEngine.Simulations.PowerFlow.power_flow_worker import __solve_island_complete_support
# # from GridCalEngine.api import *
# # from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import multi_island_pf_nc
# # from GridCalEngine.basic_structures import Logger
# # from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingencies
# #
# # # Load basic grid
# # # fname = os.path.join('src', 'trunk', 'scopf', '3bus_cont1.gridcal')
# # fname = os.path.join('C:/Users/some1/Desktop/GridCal_SCOPF/Grids_and_profiles/grids/IEEE 5 Bus_exp.gridcal')
# # grid = gce.FileOpen(fname).open()
# #
# # for line_idx in range(len(grid.lines)):
# #     nc = compile_numerical_circuit_at(grid, t_idx=None)
# #     nc.passive_branch_data.active[line_idx] = False
# #
# #     islands = nc.split_into_islands()
# #     print("Islands:", len(islands))
# #
# #     if len(islands) > 1:
# #         # count number of buses in each island and make largest one the island to use
# #         island_sizes = [island.nbus for island in islands]
# #         largest_island_idx = np.argmax(island_sizes)
# #         island = islands[largest_island_idx]
# #     else:
# #         island = islands[0]
# #
# #     indices = island.get_simulation_indices()
# #
# #     if len(indices.vd) > 0:
# #         print('this is the island size it chose', island.nbus)
# #         linear_multiple_contingencies = LinearMultiContingencies(grid, grid.get_contingency_groups())
# #         for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):
# #             # get the group's contingencies
# #             contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]
# #             print(f"Contingency group {ic}: {contingency_group.name}")
# #             # set the status
# #             nc.set_con_or_ra_status(contingencies)
# #             # solve the contingency
# #             # opf
# #             pf_options = PowerFlowOptions(
# #                 solver_type=GridCalEngine.enumerations.SolverType.NR,
# #                 tolerance=1e-8,
# #                 max_iter=20,
# #                 control_q=True
# #             )
# #             pf_results = multi_island_pf_nc(nc=island, options=pf_options)
# #             print(f"Error: {pf_results.error}")
# #             print('nbus', island.nbus, 'ngen', island.ngen)
# #             nc.set_con_or_ra_status(contingencies, revert=True)
# #     print('i found an isolated island')
# #     nc.passive_branch_data.active[line_idx] = True
#
#
#
# import os
# import numpy as np
# import GridCalEngine.api as gce
# from GridCalEngine.api import *
# from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import multi_island_pf_nc
# from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingencies
#
# # Load grid
# fname = os.path.join('C:/Users/some1/Desktop/GridCal_SCOPF/Grids_and_profiles/grids/IEEE 5 Bus_exp.gridcal')
# grid = gce.FileOpen(fname).open()
#
# # Compile the numerical circuit
# nc = compile_numerical_circuit_at(grid, t_idx=None)
# islands = nc.split_into_islands()
#
# # Find largest island
# if len(islands) > 1:
#     island_sizes = [island.nbus for island in islands]
#     largest_island_idx = np.argmax(island_sizes)
#     island = islands[largest_island_idx]
# else:
#     island = islands[0]
#
# indices = island.get_simulation_indices()
#
# if len(indices.vd) > 0:
#     print('Selected island with size:', island.nbus)
#
#     # Load contingency groups
#     linear_multiple_contingencies = LinearMultiContingencies(grid, grid.get_contingency_groups())
#
#     print("Contingency groups available:", linear_multiple_contingencies.contingency_groups_used)
#
#     for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):
#
#         contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]
#         print(f"\nContingency group {ic}: {contingency_group.name}")
#
#         nc.set_con_or_ra_status(contingencies)
#
#         for cont in contingencies:
#             line_idx = next(i for i, l in enumerate(grid.lines) if l.name == cont.name)
#             print(line_idx)
#             nc.passive_branch_data.active[line_idx] = False  # Deactivate the affected line
#             # Run power flow under contingency
#
#             pf_options = PowerFlowOptions(
#                 solver_type=GridCalEngine.enumerations.SolverType.NR,
#                 tolerance=1e-8,
#                 max_iter=20,
#                 control_q=True
#             )
#
#             pf_results = multi_island_pf_nc(nc=island, options=pf_options)
#             print(f"Error: {pf_results.error}")
#             print('nbus', island.nbus, 'ngen', island.ngen)
#
#             # Reactivate the line after testing
#             nc.passive_branch_data.active[line_idx] = True
#
#         # Revert the contingency status
#         nc.set_con_or_ra_status(contingencies, revert=True)


import os
import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.api import *
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import multi_island_pf_nc
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingencies

# Load grid
fname = os.path.join('C:/Users/some1/Desktop/GridCal_SCOPF/Grids_and_profiles/grids/IEEE 5 Bus_exp.gridcal')
grid = gce.FileOpen(fname).open()
print('Grid loaded:', fname)

# Load contingency groups
linear_multiple_contingencies = LinearMultiContingencies(grid, grid.get_contingency_groups())

for ic, contingency_group in enumerate(linear_multiple_contingencies.contingency_groups_used):

    contingencies = linear_multiple_contingencies.contingency_group_dict[contingency_group.idtag]
    print(f"\nContingency group {ic}: {contingency_group.name} (Category: {contingency_group.category})")

    # Set contingency status
    nc = compile_numerical_circuit_at(grid, t_idx=None)
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

                # Run power flow under contingency
                pf_options = PowerFlowOptions(
                    solver_type=GridCalEngine.enumerations.SolverType.NR,
                    tolerance=1e-8,
                    max_iter=20,
                    control_q=True
                )

                pf_results = multi_island_pf_nc(nc=island, options=pf_options)
                print(f"Error: {pf_results.error}")
                print('nbus', island.nbus, 'ngen', island.ngen)

            else:
                print("No valid voltage-dependent nodes found in island. Skipping.")

            # Reactivate the line after testing
            nc.passive_branch_data.active[line_idx] = True

        except StopIteration:
            print(f"Line with name '{cont.name}' not found in grid.lines. Skipping.")

    # Revert contingency status
    nc.set_con_or_ra_status(contingencies, revert=True)