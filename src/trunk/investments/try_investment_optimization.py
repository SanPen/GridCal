import os
import sys
import time
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from GridCalEngine import *
from GridCalEngine.IO.file_handler import FileOpen
import GridCalEngine.Core.Devices as dev
import GridCalEngine.Simulations as sim
import trunk.investments.InvestmentsEvaluation as invsim
from GridCalEngine.enumerations import InvestmentEvaluationMethod
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, multi_island_pf_nc

# Define investment power lines in the grid
def add_investments_to_grid(grid):


    line1 = dev.Line(grid.get_buses()[23], grid.get_buses()[71], 'Line_inv_1', r=0.0488, x=0.196, b=0.0488, rate=4.3,
                     cost=2)
    line2 = dev.Line(grid.get_buses()[23], grid.get_buses()[69], 'Line_inv_2', r=0.00221, x=0.4115, b=0.10198, rate=9.4,
                     cost=2)
    line3 = dev.Line(grid.get_buses()[71], grid.get_buses()[70], 'Line_inv_3', r=0.0446, x=0.18, b=0.04444, rate=13,
                     cost=2)
    line4_1 = dev.Line(grid.get_buses()[71], grid.get_buses()[69], 'Line_inv_41', r=0.02, x=0.2, b=0.08, rate=10,
                       cost=2)
    line5_1 = dev.Line(grid.get_buses()[23], grid.get_buses()[66], 'Line_inv_51', r=0.02, x=0.2, b=0.02, rate=10,
                       cost=2)
    line6_1 = dev.Line(grid.get_buses()[71], grid.get_buses()[22], 'Line_inv_61', r=0.02, x=0.2, b=0.02, rate=10,
                       cost=2)
    line4_2 = dev.Line(grid.get_buses()[71], grid.get_buses()[69], 'Line_inv_42', r=0.02, x=0.2, b=0.08, rate=10,
                       cost=2)
    line5_2 = dev.Line(grid.get_buses()[23], grid.get_buses()[66], 'Line_inv_52', r=0.02, x=0.2, b=0.02, rate=10,
                       cost=2)
    line6_2 = dev.Line(grid.get_buses()[71], grid.get_buses()[22], 'Line_inv_62', r=0.02, x=0.2, b=0.02, rate=10,
                       cost=2)

    lines_list = [line1, line2, line3, line4_1, line5_1, line6_1, line4_2, line5_2, line6_2]

    # Add each line as an investment & Investment group
    for i, line in enumerate(lines_list):
        grid.add_line(line)
        inv_group = dev.InvestmentsGroup(name='Ig' + str(i))
        investment = dev.Investment(device_idtag=line.idtag, name='Investment' + str(i), CAPEX=1,
                                    group=inv_group)
        grid.add_investment(investment)
        grid.add_investments_group(inv_group)

    return grid


def add_random_lines_investments(grid, num_lines):
    """
    Adds a specified number of random lines to the grid.

    Parameters:
    - grid (MultiCircuit): The power grid to which lines will be added.
    - num_lines (int): The number of random lines to add.

    Returns:
    - Grid: The updated power grid with added lines and corresponding investments.
    """
    random.seed(23)
    for i in range(num_lines):
        buses = grid.get_buses()

        # Select two distinct buses randomly
        bus_f, bus_t = random.sample(range(len(buses)), 2)

        # Ensure the selected 'from' bus has more than one occurrence in the grid
        while buses.count(buses[bus_f].Vnom) == 1:
            bus_f = random.randint(0, len(buses) - 1)

        # Ensure the 'from' and 'to' buses have the same Vnom and are distinct
        while buses[bus_f].Vnom != buses[bus_t].Vnom or bus_f == bus_t:
            bus_t = random.randint(0, len(buses) - 1)

        # Create a new line and corresponding investment
        line = dev.Line(grid.get_buses()[bus_f], grid.get_buses()[bus_t], f'Line_inv_rand_{i}',
                        r=0.02, x=0.2, b=0.02, rate=10, cost=2)

        inv_group = dev.InvestmentsGroup(name=f'Ig_rand_{i}')
        investment = dev.Investment(device_idtag=line.idtag, name=f'Investment_rand_{i}', CAPEX=i % 3 + 1,
                                    group=inv_group)

        # Add the line and investments to the grid
        grid.add_line(line)
        grid.add_investment(investment)
        grid.add_investments_group(inv_group)

    return grid


def obtain_random_points(grid, num_random_combinations, pf_options):
    list_length = len(grid.investments_groups)
    combinations_list = [[random.choice([0, 1]) for _ in range(list_length)] for _ in range(num_random_combinations)]

    investments_by_group = grid.get_investmenst_by_groups_index_dict()

    results = []

    nc = compile_numerical_circuit_at(circuit=grid, t_idx=None)

    for combination in combinations_list:
        inv_list = list()
        for i, active in enumerate(combination):
            if active == 1:
                inv_list += investments_by_group[i]

        # enable the investment

        nc.set_investments_status(investments_list=inv_list, status=1)

        # do something
        res = multi_island_pf_nc(nc=nc, options=pf_options)
        total_losses = np.sum(res.losses.real)
        overload_score = res.get_overload_score(branch_prices=nc.branch_data.overload_cost)
        voltage_score = res.get_undervoltage_overvoltage_score(undervoltage_prices=nc.bus_data.undervoltage_cost,
                                                               overvoltage_prices=nc.bus_data.overvoltage_cost,
                                                               vmin=nc.bus_data.Vmin,
                                                               vmax=nc.bus_data.Vmax)

        total_capex_opex = np.sum([inv.CAPEX for inv in inv_list]) + np.sum([inv.OPEX for inv in inv_list])

        technical_criterion = total_losses + overload_score + voltage_score

        nc.set_investments_status(investments_list=inv_list, status=0)

        results.append({'CAPEX (M€)': total_capex_opex, 'Technical criterion': technical_criterion})

    return pd.DataFrame(results)


def plot_scatter_plot(df1, df2, title, plot_df2=True):
    # Create a categorical variable based on the index of df1
    df1['color_category'] = pd.Categorical(df1.index)

    # Scatter plot for the first DataFrame (df1) with colors based on the original order
    scatter = plt.scatter(df1['CAPEX (M€)'], df1['Technical criterion'], marker='o', alpha=0.5, label='Optimization algorithm',
                          c=df1['color_category'].cat.codes, cmap='viridis')

    # Add colorbar for the association between index numbers and colors
    cbar = plt.colorbar(scatter, label='Index Numbers')
    #cbar.set_ticks([])  # Remove ticks from the colorbar

    # Scatter plot for the second DataFrame (df2) if plot_df2 is True
    if plot_df2:
        plt.scatter(df2['CAPEX (M€)'], df2['Technical criterion'], marker='o', alpha=0.5, label='Random points', color='green')

    # Set axis labels and title
    plt.xlabel('CAPEX + OPEX (M€)')
    plt.ylabel('Losses + Over/undervoltage + Overload')
    plt.title(title)

    # Show legend
    plt.legend()

    # Show the plot
    plt.show()


if __name__ == "__main__":
    import cProfile

    absolute_path = os.path.abspath(
        os.path.join(os.getcwd(), 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal'))
    grid = FileOpen(absolute_path).open()

    pf_options = sim.PowerFlowOptions()
    mvrsm = InvestmentEvaluationMethod.MVRSM_multi

    print(4*len(grid.investments))
    options = invsim.InvestmentsEvaluationOptions(solver=mvrsm, max_eval=4*len(grid.investments), pf_options=pf_options)
    inv = invsim.InvestmentsEvaluationDriver(grid, options=options)

    # Profile the inv.run() method
    import cProfile
    import pstats

    profiler = cProfile.Profile()
    profiler.enable()
    inv.run()
    profiler.disable()

    # Print profiling statistics to the console
    stats = pstats.Stats(profiler)
    stats.print_stats()

    inv_results = inv.results
    results_tpe_report = sim.result_types.ResultTypes.InvestmentsReportResults
    results_tpe_plot = sim.result_types.ResultTypes.InvestmentsParetoPlot

    print('Before plot')
    mdl = inv_results.mdl(results_tpe_plot)
    print('Done')
