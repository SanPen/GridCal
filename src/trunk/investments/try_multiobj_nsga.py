import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from GridCalEngine.IO.file_handler import FileOpen
import GridCalEngine.Simulations as sim
from GridCalEngine.enumerations import InvestmentEvaluationMethod, ResultTypes, InvestmentsEvaluationObjectives
import time
import cProfile
import cProfile
import pstats
from GridCalEngine.enumerations import SolverType

if __name__ == "__main__":
    # absolute_path = os.path.abspath(
    #   os.path.join(os.getcwd(), 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal'))

    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal')
    # fname = os.path.join('final_edited_118_bus_grid.gridcal')
    # fname = 'C:/Users/J/Downloads/claudia_v2.gridcal'
    # fname = r'C:\Users\cmach\Documents\Project_a\Model\claudia_v4.1_shunttest.gridcal'
    # fname = r'C:\Users\cmach\Documents\Project_a\Model\claudia_v4.1_OPF_test.gridcal'
    # fname = r'C:\Users\cmach\Documents\Project_a\Model\claudia_v4.1_controllableshunttest.gridcal'
    fname = 'C:/Users/J/Downloads/claudia_v41_2shunttest.gridcal'

    # fname = 'C:/Users/J/Downloads/jm1.gridcal'
    grid = FileOpen(fname).open()

    pf_options = sim.PowerFlowOptions()
    opf_options = sim.OptimalPowerFlowOptions(solver=SolverType.NONLINEAR_OPF, verbose=0, ips_init_with_pf=True)
    # options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.NSGA3,
    #                                            max_eval=1 * len(grid.investments),
    #                                            pf_options=pf_options)

    # options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.MVRSM,
    #                                            max_eval=1 * len(grid.investments),
    #                                            pf_options=pf_options)

    options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.MixedVariableGA,
                                               max_eval=6 * len(grid.investments),
                                               pf_options=pf_options,
                                               opf_options=opf_options,
                                               obj_tpe=InvestmentsEvaluationObjectives.OptimalPowerFlow)

    # options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.Independent,
    #                                            max_eval=1 * len(grid.investments),
    #                                            pf_options=pf_options)

    # options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.Random,
    #                                            max_eval=1 * len(grid.investments),
    #                                            pf_options=pf_options)

    inv = sim.InvestmentsEvaluationDriver(grid, options=options)
    st_time = time.time()
    inv.run()
    e_time = time.time()
    print(e_time - st_time)
