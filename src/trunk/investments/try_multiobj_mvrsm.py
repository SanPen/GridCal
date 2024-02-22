import os
import numpy as np
import matplotlib.pyplot as plt
from GridCalEngine.IO.file_handler import FileOpen
import GridCalEngine.Simulations as sim
import trunk.investments.InvestmentsEvaluation as invsim
from GridCalEngine.enumerations import InvestmentEvaluationMethod
import cProfile
import cProfile
import pstats

if __name__ == "__main__":
    absolute_path = os.path.abspath(
        os.path.join(os.getcwd(), 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal'))
    grid = FileOpen(absolute_path).open()

    pf_options = sim.PowerFlowOptions()
    mvrsm_multi = InvestmentEvaluationMethod.MVRSM_multi
    mvrsm_1 = InvestmentEvaluationMethod.MVRSM

    solvers = np.array([mvrsm_1, mvrsm_multi])
    results_tpe_plot = sim.result_types.ResultTypes.InvestmentsParetoPlot
    inv_results = []

    for i, solver in enumerate(solvers):
        options = invsim.InvestmentsEvaluationOptions(solver=solver, max_eval=4 * len(grid.investments),
                                                      pf_options=pf_options)

        inv = invsim.InvestmentsEvaluationDriver(grid, options=options)
        inv.run()
        inv_results.append(inv.results)

    results1 = inv_results[0]
    results2 = inv_results[1]

    mdl1 = results1.mdl(results_tpe_plot)
    mdl2 = results2.mdl(results_tpe_plot)
    plt.show()

    '''# Profile 
    profiler = cProfile.Profile()
    profiler.enable()
    inv.run()
    profiler.disable()

    # Print profiling statistics to the console
    stats = pstats.Stats(profiler)
    stats.print_stats()'''
