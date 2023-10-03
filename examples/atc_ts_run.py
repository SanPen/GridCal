from GridCalEngine.api import *
fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

main_circuit = FileOpen(fname).open()

simulation_ = LinearAnalysis(grid=main_circuit)
simulation_.run()

pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                              retry_with_other_methods=True)
power_flow = PowerFlowDriver(main_circuit, pf_options)
power_flow.run()

options = AvailableTransferCapacityOptions()
driver = AvailableTransferCapacityTimeSeriesDriver(main_circuit, options, power_flow.results)
driver.run()

print()