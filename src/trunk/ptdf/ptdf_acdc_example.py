import os
import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.Simulations.LinearFactors.linear_analysis import make_acdc_ptdf

# fname = os.path.join('..', '..', '..', 'Grids_and_profiles',  'grids', 'simple_acdc.gridcal')
# fname = os.path.join('..', '..', '..', 'Grids_and_profiles',  'grids', 'case5_3_he.gridcal')
fname = "/home/santi/Documentos/Git/GitHub/GridCal/src/tests/data/grids/ntc_test_cont (vsc).gridcal"
grid = gce.FileOpen(fname).open()

# options = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
# simulation = gce.LinearAnalysisDriver(grid=grid, options=options)
# simulation.run()
# res = simulation.results

nc = gce.compile_numerical_circuit_at(grid)

S = nc.get_power_injections()

# PTDF = make_acdc_ptdf(nc=nc, logger=gce.Logger(), distribute_slack=False)
lin = gce.LinearAnalysis(nc=nc, distributed_slack=False, correct_values=False, logger=gce.Logger())

# Pf[k] = Pf0[k] + PTDF[i,k] · ∆Pi
flows_0 = lin.PTDF @ S.real + lin.VscDF @ nc.vsc_data.control1_val

# now let's examine the outage of the VSC [0]
flows_c = flows_0 + lin.VscODF[:, 0] * nc.vsc_data.control1_val[0]

print(lin.PTDF)

print(flows_0)
print(flows_c)

