import GridCalEngine.api as gce
import numpy as np

# Set the printing precision to 4 decimal places
np.set_printoptions(precision=4)

fname = '/home/santi/Descargas/matpower-fubm-master/data/fubm_caseHVDC_vt.m'
grid = gce.open_file(fname)

opt = gce.PowerFlowOptions(retry_with_other_methods=False, verbose=3)
driver = gce.PowerFlowDriver(grid=grid, options=opt)
driver.run()
results = driver.results

print(results.get_bus_df())
print()
print(results.get_branch_df())
print("Error:", results.error)
print("Vm:", np.abs(results.voltage))
driver.logger.print()
