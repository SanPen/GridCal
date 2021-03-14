import pandas as pd
import numpy as np
from scipy.sparse import lil_matrix, csc_matrix


terminals = pd.DataFrame(['T' + str(i+1) for i in range(16)],
                         columns=['Terminals'],
                         index=['T' + str(i+1) for i in range(16)])

buses = pd.DataFrame(['B' + str(i+1) for i in range(5)],
                     columns=['Bus'],
                     index=['B' + str(i+1) for i in range(5)])

switches = pd.DataFrame([[1, 1, 2, 1],
                         [2, 3, 6, 1],
                         [3, 4, 7, 1],
                         [4, 5, 8, 1],
                         [5, 9, 12, 1],
                         [6, 10, 13, 1],
                         [7, 11, 14, 1]], columns=['Switch', 'From', 'To', 'State'])

lines = pd.DataFrame([[1, 6, 9],
                      [2, 7, 10],
                      [3, 8, 11],
                      [4, 15, 16]], columns=['Line', 'From', 'To'])

terminal_buses = pd.DataFrame([[1, 1],
                               [3, 1],
                               [2, 2],
                               [4, 2],
                               [5, 2],
                               [12, 3],
                               [13, 4],
                               [14, 4],
                               [15, 4],
                               [16, 5]], columns=['Terminal', 'Bus'])
n_terminal = terminals.shape[0]
n_bus = buses.shape[0]
n_switch = switches.shape[0]
n_line = lines.shape[0]

# ----------------------------------------------------------------------------------------------------------------------
#  Conversion to calculation nodes
# ----------------------------------------------------------------------------------------------------------------------

# rule 1: The buses are directly translated to calculation nodes
# rule 2: The terminals that are connected to a bus, are directly translated to the same calculation node as the bus
# rule 3: The remaining terminals, become calculation nodes

# this is a dictionary that translates the terminals to calculation nodes
calc_nodes_dict = dict()
terminal_in_bus = np.zeros(n_terminal, dtype=bool)

# the number of calculation nodes is the number of terminals, minus the number of terminals that belong to a bus
n_calc_nodes = n_terminal - n_bus

calc_node_names = [''] * n_calc_nodes

for k, row in terminal_buses.iterrows():
    j = row['Terminal'] - 1
    i = row['Bus'] - 1

    terminal_in_bus[j] = True
    calc_nodes_dict[j] = i

    calc_node_names[i] = 'B' + str(i + 1)

k = n_bus
for i in range(n_terminal):
    if not terminal_in_bus[i]:
        calc_node_names[k] = 'N' + str(k)
        calc_nodes_dict[i] = k
        k += 1

# ----------------------------------------------------------------------------------------------------------------------
#  Topology processing: prepare the matrices from the input data
# ----------------------------------------------------------------------------------------------------------------------
C_bus_cn = lil_matrix((n_bus, n_calc_nodes), dtype=int)
for i in range(n_bus):
    C_bus_cn[i, i] = 1

nbr = n_switch + n_line
C_br_cn = lil_matrix((nbr, n_calc_nodes), dtype=int)
C_bus_sw = lil_matrix((n_calc_nodes, n_switch), dtype=int)
states = np.zeros((nbr, nbr))
for k, row in switches.iterrows():
    i = row['Switch'] - 1
    f = calc_nodes_dict[row['From'] - 1]
    t = calc_nodes_dict[row['To'] - 1]
    C_br_cn[i, f] = 1
    C_br_cn[i, t] = 1
#    C_bus_sw[f, i] = 1
#    C_bus_sw[t, i] = 1
    states[i, i] = row['State']
    C_bus_sw[f, i] = row['State']
    C_bus_sw[t, i] = row['State']

for k, row in lines.iterrows():
    i = row['Line'] - 1 + n_switch
    f = calc_nodes_dict[row['From'] - 1]
    t = calc_nodes_dict[row['To'] - 1]
    C_br_cn[i, f] = 1
    C_br_cn[i, t] = 1
    states[i, i] = 1

"""
To detect which buses are joint via a simple switch
it is sufficient with multiplying the Bus-Switch matrix 
by its transposed.
The off-diagonal non-zeros of the resulting matrix tells us 
that the buses i and j should be merged  n_bus
"""
C_buses_joint_by_switches = C_bus_sw * C_bus_sw.T
C_buses_joint_by_switches = C_buses_joint_by_switches.tocsc()
"""
process of reduction:

1.  For each row i of C_buses_joint_by_switches
    1.1     For each row j=i+1
        1.1.1   Look at the lower diagonal of the matrix
        1.1.2   If C[i, i] is in the row j:
                    Add the row i to the row j
                    mark the element i in an aux1 vector as 1  # the reduced vector
                    
for c in range(n_calc_nodes):
    for r in range(c + 1, n_calc_nodes):
        if C[r, c] > 0:
            C[r, :] += C[c, :]
            reduced[r] += 1
"""
C = C_buses_joint_by_switches.copy()
reduced = np.zeros(n_calc_nodes, dtype=int)  # stores which buses are to merge with another bus

print('C:\n', C.toarray())

for c in range(n_calc_nodes):  # para cada columna j ...
    print(c, ':', end='')
    for k in range(C.indptr[c], C.indptr[c + 1]):  # para cada entrada de la columna ....
        r = C.indices[k]
        print(r, ' ', end='')
    print()

# the structure of the CSC matrix is going to change while traversing it
# but we only care about the original structure
indptr = C.indptr.copy()
indices = C.indices.copy()
for c in range(n_calc_nodes):  # para cada columna j ...
    a = indptr[c]
    b = indptr[c + 1]
    for k in range(a, b):  # para cada entrada de la columna ....
        r = indices[k]                           # obtener el índice de la fila
        if r > c:  # if we are here is that the value is != 0 because this is a sparse matrix
            C[r, :] += C[c, :]
            C = csc_matrix(C)
            reduced[r] += 1

            print("\nC (reduced N{}) @ c:{}, r:{}:\n".format(c + 1, c, r), C.toarray())
            print(C.indices)

print("C (final):\n", C.toarray())

"""
Once the matrix C is found, we examine the buses, 
and determine which buses group together
"""
print()
groups = dict()
for j in range(n_calc_nodes):

    group = list()

    if reduced[j] == 0:  # the buses that were not marked as reduced are the "master buses"

        for k in range(C.indptr[j], C.indptr[j + 1]):  # para cada entrada de la columna ....
            i = C.indices[k]  # obtener el índice de la fila
            if i >= j:
                group.append(i)  # the group includes the master bus

        if len(group) == 0:
            group.append(j)  # if the group has no length, add the main bus, because it is not reducible

    if len(group) > 0:
        same = ', '.join(['N' + str(i+1) for i in group])
        print('The nodes ' + same + ' are the same')
        groups[j] = group

print(groups)
