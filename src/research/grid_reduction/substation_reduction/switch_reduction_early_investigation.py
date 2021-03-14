import pandas as pd
import numpy as np

terminals = pd.DataFrame(['T' + str(i+1) for i in range(14)], columns=['Terminals'], index=['T' + str(i+1) for i in range(14)])
buses = pd.DataFrame(['B' + str(i+1) for i in range(4)], columns=['Bus'], index=['B' + str(i+1) for i in range(4)])

switches = pd.DataFrame([[1, 1, 2, 1],
                         [2, 3, 6, 1],
                         [3, 4, 7, 1],
                         [4, 5, 8, 1],
                         [5, 9, 12, 1],
                         [6, 10, 13, 1],
                         [7, 11, 14, 1]], columns=['Switch', 'From', 'To', 'State'])

lines = pd.DataFrame([[1, 6, 9],
                      [2, 7, 10],
                      [3, 8, 11]], columns=['Line', 'From', 'To'])

terminal_buses = pd.DataFrame([[1, 1],
                               [3, 1],
                               [2, 2],
                               [4, 2],
                               [5, 2],
                               [12, 3],
                               [13, 4],
                               [14, 4]], columns=['Terminal', 'Bus'])

# ----------------------------------------------------------------------------------------------------------------------
#  Topology processing: prepare the matrices from the input data
# ----------------------------------------------------------------------------------------------------------------------
n_terminal = terminals.shape[0]
n_bus = buses.shape[0]
n_switch = switches.shape[0]
n_line = lines.shape[0]

C_sw_term = np.zeros((n_switch, n_terminal))
sw_states = np.zeros((n_switch, n_switch))
for k, row in switches.iterrows():
    i = row['Switch'] - 1
    f = row['From'] - 1
    t = row['To'] - 1
    C_sw_term[i, f] = 1
    C_sw_term[i, t] = 1
    sw_states[i, i] = row['State']

C_br_term = np.zeros((n_line, n_terminal))
for k, row in lines.iterrows():
    i = row['Line'] - 1
    f = row['From'] - 1
    t = row['To'] - 1
    C_br_term[i, f] = 1
    C_br_term[i, t] = 1

C_bus_term = np.zeros((n_bus, n_terminal))
for k, row in terminal_buses.iterrows():
    j = row['Terminal'] - 1
    i = row['Bus'] - 1
    C_bus_term[i, j] = 1

# ----------------------------------------------------------------------------------------------------------------------
# Topology processing: Matrix operations
# ----------------------------------------------------------------------------------------------------------------------
C_sw_term_mod = np.dot(sw_states,  C_sw_term)
C_br_sw = C_br_term.dot(C_sw_term_mod.transpose())
C_bus_sw = C_bus_term.dot(C_sw_term_mod.transpose())
C_br_bus = C_br_sw.dot(C_bus_sw.transpose())

"""
To detect which buses are joint via a simple switch
it is sufficient with multiplying the Bus-Switch matrix 
by its transposed.
The off-diagonal non-zeros of the resulting matrix tells us 
that the buses i and j should be merged  
"""
C_buses_joint_by_switches = np.dot(C_bus_sw, C_bus_sw.transpose())

"""
Likewise, we can obtain the buses that are connected via a 
switch-branch combination, by multiplying
"""
C_buses_joint_by_branches = np.dot(C_br_bus.transpose(), C_br_bus)

"""
The final bus-bus connectivity matrix comes by combining
the connectivities achieved by processing the switches
and the switch-branches' combination
"""
C = C_buses_joint_by_switches + C_buses_joint_by_branches

# ----------------------------------------------------------------------------------------------------------------------
# output
# ----------------------------------------------------------------------------------------------------------------------

print('C_sw_term:\n', C_sw_term)
print('sw_states:\n', sw_states)
print('C_ln_term:\n', C_br_term)
print('C_bus_term:\n', C_bus_term)

df_bus_bus_sw = pd.DataFrame(C_buses_joint_by_switches, index=buses.index, columns=buses.index)
print('\nBuses joint by switches:\n', df_bus_bus_sw)

df_bus_bus_br = pd.DataFrame(C_buses_joint_by_branches, index=buses.index, columns=buses.index)
print('\nBuses joint by branches:\n', df_bus_bus_br)

df_bus_bus = pd.DataFrame(C, index=buses.index, columns=buses.index)
print('\nBuses connectivity:\n', df_bus_bus)
