import numpy as np
import GridCalEngine.api as gce

fname = '../Grids_and_profiles/grids/IEEE39_1W.gridcal'
main_circuit = gce.FileOpen(fname).open()

# let's set all ratings to 0 so that it cannot solve
# for br in main_circuit.get_branches_wo_hvdc():
#     br.rate = 1e-20

for bus in main_circuit.get_buses():
    bus.angle_max = 6
    bus.angle_min = 0.01

for gen in main_circuit.get_generators():
    gen.Pmax = 0

# declare the snapshot opf
opf_driver = gce.OptimalPowerFlowDriver(grid=main_circuit)

print('Solving...')
opf_driver.run()

print(str(opf_driver.logger))

print("Status:", opf_driver.results.converged)
print('Angles\n', np.angle(opf_driver.results.voltage))
print('Branch loading\n', opf_driver.results.loading)
print('Gen power\n', opf_driver.results.generator_power)
print('Nodal prices \n', opf_driver.results.bus_shadow_prices)

