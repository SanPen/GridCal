import os
import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.Simulations.LinearFactors.linear_analysis import make_acdc_ptdf
fname = os.path.join('..', '..', '..', 'Grids_and_profiles',  'grids', 'case5_3_he.gridcal')
grid = gce.FileOpen(fname).open()

# options = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
# simulation = gce.LinearAnalysisDriver(grid=grid, options=options)
# simulation.run()
# res = simulation.results

nc = gce.compile_numerical_circuit_at(grid)

PTDF = make_acdc_ptdf(nc=nc)

print(PTDF)