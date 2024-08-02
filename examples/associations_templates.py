import os
import numpy as np
import GridCalEngine.api as gce

# fname = os.path.join('C:/Users/J/Downloads/simple1.gridcal')
# main_circuit = gce.open_file(fname)
folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'simple1.gridcal')
main_circuit = gce.open_file(fname)


results = gce.power_flow(main_circuit)

print(main_circuit.name)
print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
