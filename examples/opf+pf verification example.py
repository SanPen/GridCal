import os
import GridCalEngine.api as gce
import pandas as pd
pd.set_option('display.precision', 2)

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'Lynn 5 Bus pv (opf).gridcal')

main_circuit = gce.open_file(fname)

# declare the snapshot opf
opf_driver = gce.OptimalPowerFlowDriver(grid=main_circuit)

print('Solving...')
opf_driver.run()
print(opf_driver.results.get_bus_df())
print(opf_driver.results.get_branch_df())

pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
pf_driver = gce.PowerFlowDriver(grid=main_circuit,
                                options=pf_options,
                                opf_results=opf_driver.results)
pf_driver.run()

print('Converged:', pf_driver.results.converged, '\nerror:', pf_driver.results.error)
print(pf_driver.results.get_bus_df())
print(pf_driver.results.get_branch_df())