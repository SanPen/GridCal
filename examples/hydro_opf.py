import GridCalEngine.api as gce
import numpy as np
import pandas as pd
import datetime as dt

# main_circuit = gce.FileOpen('../Grids_and_profiles/grids/hydro_grid1.gridcal').open()
# main_circuit = gce.FileOpen('../Grids_and_profiles/grids/hydro_grid2.gridcal').open()
# main_circuit = gce.FileOpen('../Grids_and_profiles/grids/hydro_grid4.gridcal').open()
#
# # declare the snapshot opf
# opf_driver = gce.OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)
#
# print('Solving...')
# opf_driver.run()
#
# print("Status:", opf_driver.results.converged)
# print('Angles\n', np.angle(opf_driver.results.voltage))
# print('Branch loading\n', opf_driver.results.loading)
# print('Gen power\n', opf_driver.results.generator_power)
# print('Nodal prices \n', opf_driver.results.bus_shadow_prices)
#

grid = gce.MultiCircuit(name='hydro_grid')

# let's create a master profile
date0 = dt.datetime(2023, 1, 1)
time_array = pd.DatetimeIndex([date0 + dt.timedelta(hours=i) for i in range(10)])
x = np.linspace(0, 10, len(time_array))
df_0 = pd.DataFrame(data=x, index=time_array)  # complex values

# set the grid master time profile
grid.time_profile = df_0.index

# Add some fluid nodes, with their electrical buses
fb1 = gce.Bus(name='fb1')
fb2 = gce.Bus(name='fb2')
fb3 = gce.Bus(name='fb3')

grid.add_bus(fb1)
grid.add_bus(fb2)
grid.add_bus(fb3)

f1 = gce.FluidNode(name='fluid_node_1',
                   min_level=0.,
                   max_level=100.,
                   current_level=50.,
                   spillage_cost=10.,
                   inflow=0.,
                   bus=fb1)

f2 = gce.FluidNode(name='fluid_node_2',
                   spillage_cost=10.,
                   bus=fb2)

f3 = gce.FluidNode(name='fluid_node_3',
                   spillage_cost=10.,
                   bus=fb3)

f4 = gce.FluidNode(name='fluid_node_4',
                   min_level=0,
                   max_level=100,
                   current_level=50,
                   spillage_cost=10.,
                   inflow=0.)

grid.add_fluid_node(f1)
grid.add_fluid_node(f2)
grid.add_fluid_node(f3)
grid.add_fluid_node(f4)

# Add the paths
p1 = gce.FluidPath(name='path_1',
                   source=f1,
                   target=f2,
                   min_flow=-50.,
                   max_flow=50.,)

p2 = gce.FluidPath(name='path_2',
                   source=f2,
                   target=f3,
                   min_flow=-50.,
                   max_flow=50.,)

p3 = gce.FluidPath(name='path_3',
                   source=f3,
                   target=f4,
                   min_flow=-50.,
                   max_flow=50.,)

grid.add_fluid_path(p1)
grid.add_fluid_path(p2)
grid.add_fluid_path(p3)

# Add electrical generators for each fluid machine
g1 = gce.Generator(name='turbine_1_gen',
                   Pmax=1000.0,
                   Pmin=0.0,
                   Cost=0.5)

g2 = gce.Generator(name='pump_1_gen',
                   Pmax=0.0,
                   Pmin=-1000.0,
                   Cost=-0.5)

g3 = gce.Generator(name='p2x_1_gen',
                   Pmax=0.0,
                   Pmin=-1000.0,
                   Cost=-0.5)

grid.add_generator(fb3, g1)
grid.add_generator(fb2, g2)
grid.add_generator(fb1, g3)

# Add a turbine
turb1 = gce.FluidTurbine(name='turbine_1',
                         plant=f3,
                         generator=g1,
                         max_flow_rate=45.0,
                         efficiency=0.95)

grid.add_fluid_turbine(f3, turb1)

# Add a pump
pump1 = gce.FluidPump(name='pump_1',
                      reservoir=f2,
                      generator=g2,
                      max_flow_rate=49.0,
                      efficiency=0.85)

grid.add_fluid_pump(f2, pump1)

# Add a p2x
p2x1 = gce.FluidP2x(name='p2x_1',
                    plant=f1,
                    generator=g3,
                    max_flow_rate=49.0,
                    efficiency=0.9)

grid.add_fluid_p2x(f1, p2x1)

# Add the electrical grid part
b1 = gce.Bus(name='b1',
             vnom=10,
             is_slack=True)

b2 = gce.Bus(name='b2',
             vnom=10)

grid.add_bus(b1)
grid.add_bus(b2)

g0 = gce.Generator(name='slack_gen',
                   Pmax=1000.0,
                   Pmin=0.0,
                   Cost=0.8)

grid.add_generator(b1, g0)

l1 = gce.Load(name='l1',
              P=11,
              Q=0)

grid.add_load(b2, l1)

line1 = gce.Line(name='line1',
                 bus_from=b1,
                 bus_to=b2,
                 rate=5,
                 x=0.05)

line2 = gce.Line(name='line2',
                 bus_from=b1,
                 bus_to=fb1,
                 rate=10,
                 x=0.05)

line3 = gce.Line(name='line3',
                 bus_from=b1,
                 bus_to=fb2,
                 rate=10,
                 x=0.05)

line4 = gce.Line(name='line4',
                 bus_from=fb3,
                 bus_to=b2,
                 rate=15,
                 x=0.05)

grid.add_line(line1)
grid.add_line(line2)
grid.add_line(line3)
grid.add_line(line4)

# gce.FileSave(grid, 'hy_test.gridcal').save()

# Run the simulation
opf_driver = gce.OptimalPowerFlowTimeSeriesDriver(grid=grid)

print('Solving...')
opf_driver.run()

print("Status:", opf_driver.results.converged)
print('Angles\n', np.angle(opf_driver.results.voltage))
print('Branch loading\n', opf_driver.results.loading)
print('Gen power\n', opf_driver.results.generator_power)
print('Reservoir level\n', opf_driver.results.fluid_node_current_level)


if __name__ == '__main__':
    import os
    import GridCalEngine.api as gce

    folder = os.path.join('..', 'Grids_and_profiles', 'grids')
    fname = os.path.join(folder, 'hydro_simple.gridcal')
    grid = gce.open_file(fname)

    # Run the simulation
    opf_driver = gce.OptimalPowerFlowTimeSeriesDriver(grid=grid)

    print('Solving...')
    opf_driver.run()

    print('Branch loading\n', opf_driver.results.loading)
    print('Gen power\n', opf_driver.results.generator_power)
    print('Reservoir level\n', opf_driver.results.fluid_node_current_level)
