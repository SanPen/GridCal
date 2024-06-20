import os
import numpy as np
import matplotlib.pyplot as plt
import pandas
import pandas as pd
from GridCalEngine.IO.file_handler import FileOpen
import GridCalEngine.Simulations as Sim
from GridCalEngine.enumerations import InvestmentEvaluationMethod, ResultTypes
import time
import cProfile
import cProfile
import pstats
from pymoo.config import Config

Config.warnings['not_compiled'] = False

if __name__ == "__main__":
    fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal')
    # fname = os.path.join('/Users/CristinaFray/PycharmProjects/GridCal/src/trunk/investments/edited_IEEE 118 Bus - investments.gridcal')
    grid = FileOpen(fname).open()

    st_time = time.time()

    pf_options = Sim.PowerFlowOptions()
    options = Sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.NSGA3_platypus,
                                               max_eval=4 * len(grid.investments),
                                               pf_options=pf_options)

    inv = Sim.InvestmentsEvaluationDriver(grid, options=options)
    inv.run()
    e_time = time.time()
    print(f"Simulation time: {e_time - st_time} sec")
