import os
import numpy as np
import matplotlib.pyplot as plt
import pandas
import pandas as pd
from GridCalEngine.IO.file_handler import FileOpen
import GridCalEngine.Simulations as sim
from GridCalEngine.enumerations import InvestmentEvaluationMethod, ResultTypes
import time
import cProfile
import cProfile
import pstats
from pymoo.config import Config
Config.warnings['not_compiled'] = False

if __name__ == "__main__":
    # absolute_path = os.path.abspath(
    #   os.path.join(os.getcwd(), 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal'))

    fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'ding0_test_network_2_mvlv.gridcal')
    #fname = os.path.join('/Users/CristinaFray/PycharmProjects/GridCal/src/trunk/investments/edited_IEEE 118 Bus - investments.gridcal')
    grid = FileOpen(fname).open()

    pf_options = sim.PowerFlowOptions()
    #platypus:
    # options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.NSGA3_platypus,
    #                                            max_eval=4 * len(grid.investments),
    #                                            pf_options=pf_options)
    #pymoo:
    options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.NSGA3,
                                               max_eval=4 * len(grid.investments),
                                               pf_options=pf_options)

    print("max_evals inicializadas: {}".format(4 * len(grid.investments)))
    inv = sim.InvestmentsEvaluationDriver(grid, options=options)
    st_time = time.time()
    inv.run()
    e_time = time.time()

    output_f=inv.results._f_obj
    combinations=inv.results._combinations
    #output_f1f2=¿?

    print("Simulation time: {} sec".format(e_time - st_time))

    # #..................PLOTTING PLATYPUS................................
    # import matplotlib.pyplot as plt
    # import matplotlib
    # import pandas as pd
    # matplotlib.use("Qt5Agg")
    # data=pd.read_excel(r"C:\Users\cmach\PycharmProjects\GridCal2\src\trunk\investments\nsga_platypus.xlsx")
    # plt.scatter(data[0],data[1])
    # plt.show()


