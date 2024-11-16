import GridCalEngine.api as gce
import numpy as np

# Set the printing precision to 4 decimal places
np.set_printoptions(precision=4)

# fname = './../../tests/data/grids/fubm_caseHVDC_vt.m'
fname = 'C:/Users/J/Desktop/GridCal/Grids_and_profiles/grids/fubm_caseHVDC_vt_josep.gridcal'
grid = gce.open_file(fname)

opt = gce.PowerFlowOptions(retry_with_other_methods=False, verbose=3, solver_type=gce.SolverType.GENERALISED)
driver = gce.PowerFlowDriver(grid=grid, options=opt)
driver.run()
results = driver.results

print(results.get_bus_df())
print()
print(results.get_branch_df())
print("Error:", results.error)
print("Vm:", np.abs(results.voltage))
driver.logger.print()
