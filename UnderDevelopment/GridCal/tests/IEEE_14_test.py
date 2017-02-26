from GridCal.grid.CalculationEngine import *
import numpy as np

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

####################################################################################################################
# Test the values
####################################################################################################################
fname = 'IEEE_14BUS_results.xls'
voltage_results_df = pd.read_excel(fname, sheetname='voltage')
loading_results_df = pd.read_excel(fname, sheetname='loading')

# the tolerance of the results provided is 0.01
eps = 1e-2


def checkvals(name, original, calculated):
    diff = abs(original - calculated)
    check = diff < eps
    print(name + ': ', check.all(), diff)

# voltage check:
checkvals('Vabs', voltage_results_df['V mag pu'].values, abs(grid.power_flow_results.voltage))

checkvals('Vang', voltage_results_df['V angle'].values, np.angle(grid.power_flow_results.voltage, deg=True))


# loading check

# Losses_in_MW	Reactive_Losses_in_Mvar	Capacitive_Loading_in_Mvar	Current_in_kA

print(loading_results_df['Losses_in_MW'].values)
print(grid.power_flow_results.losses.real)
print(grid.power_flow_results.losses.real.sum())
checkvals('Losses(real)', loading_results_df['Losses_in_MW'].values, grid.power_flow_results.losses.real)