import os
import VeraGridEngine.api as gce
import pandas as pd

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'simple2.gridcal')

main_circuit = gce.open_file(fname)

results = gce.power_flow(main_circuit)

print(main_circuit.name)
print('Converged:', results.converged, '\nerror:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
