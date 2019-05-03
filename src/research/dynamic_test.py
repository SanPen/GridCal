from GridCal.Engine.calculation_engine import *
from GridCal.Engine.Simulations.Dynamics.dynamic_modules import *


grid = MultiCircuit()
# grid.load_file('lynn5buspv.xlsx')
grid.load_file('IEEE30.xlsx')
grid.compile()
circuit = grid.circuits[0]

options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9)
power_flow = PowerFlow(grid, options)
power_flow.run()


dynamic_devices = circuit.get_generators()
bus_indices = [circuit.buses_dict[elm.bus] for elm in dynamic_devices]

res = dynamic_simulation(n=len(circuit.buses),
                         Vbus=power_flow.results.voltage,
                         Sbus=circuit.power_flow_input.Sbus,
                         Ybus=circuit.power_flow_input.Ybus,
                         Sbase=circuit.Sbase,
                         fBase=50,
                         t_sim=50,
                         h=0.001,
                         dynamic_devices=dynamic_devices,
                         bus_indices=bus_indices)


from matplotlib import pyplot as plt

plt.figure()
plt.plot(res.time, abs(res.voltage), linewidth=1)
plt.title('Generator voltages')

plt.figure()
plt.plot(res.time, abs(res.omegas), linewidth=1)
plt.title('Angular speeds')
plt.show()
