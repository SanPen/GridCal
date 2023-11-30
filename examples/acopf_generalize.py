# from GridCalEngine.IO import FileOpen
# from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
import GridCalEngine.api as gce

# grid = gce.FileOpen('../Grids_and_profiles/grids/IEEE39.xlsx').open()
# snapshot = gce.compile_numerical_circuit_at(grid)
# print('Done')

grid = gce.MultiCircuit()

b1 = gce.Bus()
b2 = gce.Bus()
b3 = gce.Bus()

grid.add_bus(b1)
grid.add_bus(b2)
grid.add_bus(b3)

grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='line 1-2', r=0.01, x=0.05 ))
grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='line 2-3', r=0.01, x=0.05 ))
grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1', r=0.01, x=0.05 ))

grid.add_load(b3, gce.Load(name='load 3', P=50, Q=20))
grid.add_generator(b1, gce.Generator('Slack', vset=1.0))

options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
power_flow = gce.PowerFlowDriver(grid, options)
power_flow.run()

print('\n\n', grid.name)
print('\tConv:', power_flow.results.get_bus_df())
print('\tConv:', power_flow.results.get_branch_df())

nc = gce.compile_numerical_circuit_at(grid)
print('')