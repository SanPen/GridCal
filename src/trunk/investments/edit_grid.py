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
from GridCalEngine.IO import FileOpen, FileSave


if __name__ == "__main__":
    fname = os.path.join('IEEE 118 Bus - ntc_areas_two.gridcal')
    grid = FileOpen(fname).open()
    for load in grid.loads:
        load.Q = 3.5*load.Q
    pf_options = sim.PowerFlowOptions()

    st_time = time.time()

    driver = sim.PowerFlowDriver(grid, pf_options)
    driver.run()
    print(min(abs(driver.results.voltage)))
    new_fname = "edited_" + os.path.basename(fname)
    FileSave(grid, new_fname).save()
    print("Edited grid saved as:", new_fname)

    e_time = time.time()
    print(e_time - st_time)
