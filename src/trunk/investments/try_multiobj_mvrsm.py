import os
import numpy as np
import matplotlib.pyplot as plt
from GridCalEngine.IO.file_handler import FileOpen
import GridCalEngine.Simulations as sim
import trunk.investments.InvestmentsEvaluation as invsim
from GridCalEngine.enumerations import InvestmentEvaluationMethod, ResultTypes
import time
import cProfile
import cProfile
import pstats


if __name__ == "__main__":
    fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal')
    grid = FileOpen(fname).open()
    # absolute_path = os.path.abspath(
    #     os.path.join(os.getcwd(), 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal'))
    # grid = FileOpen(absolute_path).open()

    pf_options = sim.PowerFlowOptions()
    mvrsm_multi = InvestmentEvaluationMethod.MVRSM_multi
    mvrsm_1 = InvestmentEvaluationMethod.MVRSM

    solvers = np.array([mvrsm_1, mvrsm_multi])
    results_tpe_plot = ResultTypes.InvestmentsParetoPlot4
    inv_results = []

    for i, solver in enumerate(solvers):
        options = sim.InvestmentsEvaluationOptions(solver=solver, max_eval=2*len(grid.investments),
                                                   pf_options=pf_options)

        inv = sim.InvestmentsEvaluationDriver(grid, options=options)
        st_time = time.time()
        inv.run()
        e_time = time.time()
        print(e_time - st_time)
        inv_results.append(inv.results)

    results1 = inv_results[0]
    results2 = inv_results[1]

    results_table = results1.mdl(results_tpe_plot)

    # Extract data for plotting
    x = results_table.data_c[:, 0]  # Investment cost
    y = results_table.data_c[:, 1]  # Technical cost

    # Plot the Pareto curve
    plt.scatter(x, y, facecolor="none", edgecolor="red")
    plt.xlabel("Investment cost (M€)")
    plt.ylabel("Technical cost (M€)")
    plt.show()

    '''# Profile 
    profiler = cProfile.Profile()
    profiler.enable()
    inv.run()
    profiler.disable()

    # Print profiling statistics to the console
    stats = pstats.Stats(profiler)
    stats.print_stats()'''


