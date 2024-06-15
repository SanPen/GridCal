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
from GridCalEngine.Devices import Investment, InvestmentsGroup
import random


if __name__ == "__main__":
    fname = os.path.join('IEEE 118 Bus - investments.gridcal')
    grid = FileOpen(fname).open()

    if grid is None:
        raise Exception("No grid found")

    for load in grid.get_loads():
        load.P = 1.5*load.P
        load.Q = 1.5*load.Q

    for gen in grid.get_generators():
        gen.P = 1.5*gen.P

    new_lines = []
    for line in grid.get_lines():
        new_line = line.copy(forced_new_idtag=True)
        new_line.active = False
        # new_line.B = 0
        # new_line.R = 0
        new_lines.append(new_line)

    for new_line in new_lines:
        grid.add_line(new_line)

    new_trs = []
    for transformer in grid.get_transformers2w():
        new_tr = transformer.copy(forced_new_idtag=True)
        new_tr.active = False
        new_trs.append(new_tr)

    for new_tr in new_trs:
        grid.add_transformer2w(new_tr)

    for buses in grid.get_buses():
        buses.Vmin = 0.95

    num_lines = len(grid.get_lines())
    nset_lines = int(num_lines / 2)  # number of investments
    for ii in range(nset_lines):
        group = InvestmentsGroup(idtag=None,
                                 name=f'Investment {ii}',
                                 category="single")
        grid.add_investments_group(group)

        # add the selection as investments to the group
        elm = grid.get_lines()[nset_lines + ii]
        con = Investment(device_idtag=elm.idtag,
                         code=elm.code,
                         name=elm.type_name + ": " + elm.name,
                         CAPEX=100,
                         OPEX=0,
                         group=group)
        grid.add_investment(con)

    num_trs = grid.get_transformers2w()
    nset_trs = int(num_trs / 2)  # number of investments
    for ii in range(nset_trs):
        group = InvestmentsGroup(idtag=None,
                                 name=f'Investment {ii}',
                                 category="single")
        grid.add_investments_group(group)

        # add the selection as investments to the group
        elm = grid.get_transformers2w()[nset_trs + ii]
        con = Investment(device_idtag=elm.idtag,
                         code=elm.code,
                         name=elm.type_name + ": " + elm.name,
                         CAPEX=random.randint(1, 100),
                         OPEX=0,
                         group=group)
        grid.add_investment(con)

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
