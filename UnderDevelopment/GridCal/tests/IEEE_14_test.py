from GridCal.grid.CalculationEngine import *

'''
This file tests GridCal results against the well established results for IEEE 14
'''

fname_test = 'IEEE_14BUS_results.xls'

grid = MultiCircuit()
grid.load_file('IEEE_14.xlsx')
grid.compile()

options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False)

####################################################################################################################
# PowerFlow
####################################################################################################################
print('\n\n')
power_flow = PowerFlow(grid, options)
power_flow.run()

for c in grid.circuits:
    print(c.name)
    # print(pd.DataFrame(circuit.power_flow_input.Ybus.todense()))
    # print('\tV:', c.power_flow_results.voltage)
    print('\t|V|:', abs(c.power_flow_results.voltage))
    print('\t|Sbranch|:', abs(c.power_flow_results.Sbranch))
    print('\t|loading|:', abs(c.power_flow_results.loading) * 100)
    print('\terr:', c.power_flow_results.error)
    print('\tConv:', c.power_flow_results.converged)

print('\n\n', grid.name)
print('\t|V|:', abs(grid.power_flow_results.voltage))
print('\t|Sbranch|:', abs(grid.power_flow_results.Sbranch))
print('\t|loading|:', abs(grid.power_flow_results.loading) * 100)
print('\terr:', grid.power_flow_results.error)
print('\tConv:', grid.power_flow_results.converged)