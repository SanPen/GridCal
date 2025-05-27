import os
import numpy as np
import GridCalEngine.api as gce

fname = os.path.join('..', '..', '..', 'Grids_and_profiles',  'grids', 'KULeuven_5node_hvdc.gridcal')
grid = gce.FileOpen(fname).open()

options = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
simulation = gce.LinearAnalysisDriver(grid=grid, options=options)
simulation.run()
res = simulation.results


print("PTDF:\n", res.PTDF)

print("HvdcDF:\n", res.HvdcDF)
print("HvdcODF:\n", res.HvdcODF)

print("VscDF:\n", res.VscDF)
print("VscODF:\n", res.VscODF)