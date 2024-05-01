import os
import numpy as np
import matplotlib.pyplot as plt
from GridCalEngine.IO.file_handler import FileOpen
import GridCalEngine.Simulations as sim
from GridCalEngine.enumerations import InvestmentEvaluationMethod, ResultTypes
import time
import cProfile
import cProfile
import pstats

if __name__ == "__main__":
    # absolute_path = os.path.abspath(
    #   os.path.join(os.getcwd(), 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal'))

    fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal')
    grid = FileOpen(fname).open()

    pf_options = sim.PowerFlowOptions()

    options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.NSGA3,
                                               max_eval=50 * len(grid.investments),
                                               pf_options=pf_options)

    inv = sim.InvestmentsEvaluationDriver(grid, options=options)
    st_time = time.time()
    inv.run()
    e_time = time.time()
    print(e_time - st_time)
