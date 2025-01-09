import os
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
import GridCalEngine.api as gce
import faulthandler

faulthandler.enable()  # start @ the beginning

"""
Check that a transformer can regulate the voltage at a bus
"""
# fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', 'AC-DC with all and DCload.gridcal')
fname = "G:/.shortcut-targets-by-id/1B4zzyZBFXXFuEGTYGLt-sPLVc6VD2iL4/eRoots Analytics Shared Drive/Development/Project ACDC1 AC-DC Power Flow/Training grids/5714v2.gridcal"

grid = gce.open_file(fname)

options = PowerFlowOptions(SolverType.NR,
                           verbose=0,
                           control_q=False,
                           retry_with_other_methods=False,
                           control_taps_phase=True,
                           control_taps_modules=True,
                           max_iter=80,
                           tolerance=1e-12, )

results = gce.power_flow(grid, options)

print(results.get_bus_df())
print(results.error)
assert results.converged
