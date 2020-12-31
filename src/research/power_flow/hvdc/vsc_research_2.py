

"""
This example is coming from the book:
Power System Load Flow Analysis - Lynn Powell

Author: Santiago Peñate Vera (September 2018)
"""

import numpy as np
import pandas as pd
from GridCal.Engine import *

####################################################################################################################
# Define the circuit
#
# A circuit contains all the grid information regardless of the islands formed or the amount of devices
####################################################################################################################

grid = MultiCircuit(name='lynn 5 bus')

####################################################################################################################
# Define the buses
####################################################################################################################

bus1 = Bus(name='Bus1')
bus2 = Bus(name='Bus2')
bus3 = Bus(name='Bus3')
bus4 = Bus(name='Bus4')
bus5 = Bus(name='Bus5')
bus6 = Bus(name='DC6', is_dc=True)
bus7 = Bus(name='DC7', is_dc=True)
bus8 = Bus(name='Bus8')

# add the bus objects to the circuit
grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus3)
grid.add_bus(bus4)
grid.add_bus(bus5)
grid.add_bus(bus6)
grid.add_bus(bus7)
grid.add_bus(bus8)

####################################################################################################################
# Add the loads
####################################################################################################################
# In GridCal, the loads, generators ect are stored within each bus object:

# Define the others with the default parameters
grid.add_load(bus2, Load(P=40, Q=20))
grid.add_load(bus3, Load(P=25, Q=15))
grid.add_load(bus4, Load(P=40, Q=20))
grid.add_load(bus5, Load(P=50, Q=20))
grid.add_load(bus8, Load(P=40, Q=20))  # after HVDC load

####################################################################################################################
# Add the generators
####################################################################################################################

grid.add_generator(bus1, Generator(name='gen', active_power=0.0))

####################################################################################################################
# Add the lines
####################################################################################################################

grid.add_branch(VSC(bus5, bus6, name='VSC 5-6', r1=0.00001, x1=0.0005, m=1.0, theta=0.0, G0=1e-5, Beq=0.00001, rate=30))
grid.add_branch(DcLine(bus6, bus7, name='DC line 6-7 (1)', r=0.001, rate=30))
grid.add_branch(DcLine(bus6, bus7, name='DC line 6-7 (2)', r=0.001, rate=30))


grid.add_branch(Branch(bus1, bus3, name='Line 1-2', r=0.05, x=0.11, b=0.02, rate=50))
grid.add_branch(Branch(bus1, bus3, name='Line 1-3', r=0.05, x=0.11, b=0.02, rate=50))
grid.add_branch(Branch(bus1, bus5, name='Line 1-5', r=0.03, x=0.08, b=0.02, rate=100))
grid.add_branch(Branch(bus2, bus3, name='Line 2-3', r=0.04, x=0.09, b=0.02, rate=30))
grid.add_branch(Branch(bus2, bus5, name='Line 2-5', r=0.04, x=0.09, b=0.02, rate=10))
grid.add_branch(Branch(bus3, bus4, name='Line 3-4', r=0.06, x=0.13, b=0.03, rate=30))
grid.add_branch(Branch(bus4, bus5, name='Line 4-5', r=0.04, x=0.09, b=0.02, rate=30))

grid.add_branch(VSC(bus7, bus8, name='VSC 7-8', r1=0.00001, x1=0.0005, m=1.05, theta=0.0, G0=1e-5, Beq=0.00001, rate=30))

FileSave(grid, 'hvdc.gridcal').save()
####################################################################################################################
# Run a power flow simulation
####################################################################################################################

# We need to specify power flow options
pf_options = PowerFlowOptions(solver_type=SolverType.NR,  # Base method to use
                              verbose=False,  # Verbose option where available
                              tolerance=1e-6,  # power error in p.u.
                              max_iter=25,  # maximum iteration number
                              control_q=True,  # if to control the reactive power
                              retry_with_other_methods=False
                              )

# Declare and execute the power flow simulation
pf = PowerFlowDriver(grid, pf_options)
pf.run()

# now, let's compose a nice DataFrame with the voltage results
headers = ['Vm (p.u.)', 'Va (Deg)', 'Vre', 'Vim']
Vm = np.abs(pf.results.voltage)
Va = np.angle(pf.results.voltage, deg=True)
Vre = pf.results.voltage.real
Vim = pf.results.voltage.imag
data = np.c_[Vm, Va, Vre, Vim]
v_df = pd.DataFrame(data=data, columns=headers, index=grid.bus_names)
print('\n', v_df)


# Let's do the same for the branch results
headers = ['Loading (%)', 'Current(p.u.)', 'Power (MVA)']
loading = np.abs(pf.results.loading) * 100
current = np.abs(pf.results.Ibranch)
power = np.abs(pf.results.Sbranch)
data = np.c_[loading, current, power]
br_df = pd.DataFrame(data=data, columns=headers, index=grid.branch_names)
print('\n', br_df)

# Finally the execution metrics
print('\nError:', pf.results.error)
print('Elapsed time (s):', pf.results.elapsed, '\n')
