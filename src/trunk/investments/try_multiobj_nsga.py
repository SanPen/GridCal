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

    st_time = time.time()

    pf_options = sim.PowerFlowOptions()
    #platypus:
    options = sim.InvestmentsEvaluationOptions(solver=InvestmentEvaluationMethod.NSGA3_platypus,
                                            max_eval=4 * len(grid.investments),
                                            pf_options=pf_options)

    #print("max_evals inicializadas: {}".format(4 * len(grid.investments)))
    inv = sim.InvestmentsEvaluationDriver(grid, options=options)
    #st_time = time.time()
    inv.run()
    e_time = time.time()
    print("Simulation time: {} sec".format(e_time - st_time))
    print("Simulation time: {} min".format((e_time - st_time)/60))

    # #============================================================
    # #Results pymoo:
    # # ============================================================
    # output_f=inv.results._f_obj
    # #combinations=inv.results._combinations
    # output_f1=inv.results._financial
    # output_f2=inv.results._electrical
    # #save to excel all solutions (not only non-dominated)
    # data=np.column_stack((output_f1,output_f2))
    # dff = pd.DataFrame(data)
    # dff.to_excel('nsga_PYMOO_all.xlsx')
    #
    # #plot all the results in scatter - not only pareto front - PYMOO
    # import matplotlib.pyplot as plt
    # import matplotlib
    # import pandas as pd
    # matplotlib.use("Qt5Agg")
    # plt.scatter(data[0],data[1])
    # plt.show()

    # ============================================================
    # Results PLATYPUS:
    # ============================================================
    #..................PLOTTING PLATYPUS................................
    import matplotlib.pyplot as plt
    import matplotlib
    import pandas as pd
    matplotlib.use("Qt5Agg")
    data=pd.read_excel(r"C:\Users\cmach\PycharmProjects\GridCal2\src\trunk\investments\nsga_ptp_uf_all.xlsx")
    plt.scatter(data[1],data[0], c='r', edgecolors='r')
    plt.show()


