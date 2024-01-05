import GridCalEngine.api as gce
import numpy as np

# main_circuit = gce.FileOpen('../Grids_and_profiles/grids/hydro_grid1.gridcal').open()
# main_circuit = gce.FileOpen('../Grids_and_profiles/grids/hydro_grid2.gridcal').open()
main_circuit = gce.FileOpen('../Grids_and_profiles/grids/hydro_grid4.gridcal').open()

# declare the snapshot opf
opf_driver = gce.OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

print('Solving...')
opf_driver.run()

print("Status:", opf_driver.results.converged)
print('Angles\n', np.angle(opf_driver.results.voltage))
print('Branch loading\n', opf_driver.results.loading)
print('Gen power\n', opf_driver.results.generator_power)
print('Nodal prices \n', opf_driver.results.bus_shadow_prices)

