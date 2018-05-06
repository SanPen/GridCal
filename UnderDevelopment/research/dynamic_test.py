from GridCal.Engine.CalculationEngine import *
from GridCal.Engine.Numerical.DynamicModels import *


grid = MultiCircuit()
# grid.load_file('lynn5buspv.xlsx')
grid.load_file('IEEE30.xlsx')
grid.compile()
circuit = grid.circuits[0]

options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9)
power_flow = PowerFlow(grid, options)
power_flow.run()


dynamic_devices = circuit.get_controlled_generators()
bus_indices = [circuit.buses_dict[elm.bus] for elm in dynamic_devices]

dynamic_simulation(n=len(circuit.buses),
                   Vbus=power_flow.results.voltage,
                   Sbus=circuit.power_flow_input.Sbus,
                   Ybus=circuit.power_flow_input.Ybus,
                   Sbase=circuit.Sbase,
                   fBase=80,
                   t_sim=50,
                   h=0.001,
                   dynamic_devices=dynamic_devices,
                   bus_indices=bus_indices)
