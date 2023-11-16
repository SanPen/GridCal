import os
import GridCalEngine.api as gce

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'South Island of New Zealand.gridcal')

grid = gce.open_file(filename=fname)

pf_options = gce.PowerFlowOptions()
pf = gce.PowerFlowDriver(grid, pf_options)
pf.run()

fault_index = 2
sc_options = gce.ShortCircuitOptions(bus_index=fault_index, fault_type=gce.FaultType.LG)
sc = gce.ShortCircuitDriver(grid, options=sc_options, pf_options=pf_options, pf_results=pf.results)
sc.run()

print("Short circuit power: ", sc.results.SCpower[fault_index])
