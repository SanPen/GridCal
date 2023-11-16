import os
import GridCalEngine.api as gce

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'IEEE 5 Bus.xlsx')

main_circuit = gce.open_file(fname)

options_ = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=True)

# snapshot
sn_driver = gce.LinearAnalysisDriver(grid=main_circuit, options=options_)
sn_driver.run()

print("Bus results:\n", sn_driver.results.get_bus_df())
print("Branch results:\n", sn_driver.results.get_branch_df())
print("PTDF:\n", sn_driver.results.mdl(gce.ResultTypes.PTDF).to_df())
print("LODF:\n", sn_driver.results.mdl(gce.ResultTypes.LODF).to_df())
