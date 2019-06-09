import pandas as pd
import numpy as np
from scipy.sparse import lil_matrix, csc_matrix

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


file_name = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\Reduction Model 2.xlsx'

from GridCal.Engine.calculation_engine import MultiCircuit, BranchType


circuit = MultiCircuit()

circuit.load_file(file_name)

circuit.compile()

# form C
threshold = 1e-5
m = len(circuit.branches)
n = len(circuit.buses)
C = lil_matrix((m, n), dtype=int)
buses_dict = {bus: i for i, bus in enumerate(circuit.buses)}
branches_to_keep_idx = list()
branches_to_remove_idx = list()
states = np.zeros(m, dtype=int)
br_idx = [None] * m
for i in range(len(circuit.branches)):
    # get the from and to bus indices
    f = buses_dict[circuit.branches[i].bus_from]
    t = buses_dict[circuit.branches[i].bus_to]
    C[i, f] = 1
    C[i, t] = -1
    br_idx[i] = i
    rx = circuit.branches[i].R + circuit.branches[i].X

    if circuit.branches[i].branch_type == BranchType.Branch:
        branches_to_remove_idx.append(i)
        states[i] = 0
    else:
        branches_to_keep_idx.append(i)
        states[i] = 1

C = csc_matrix(C)

df_C = pd.DataFrame(C.todense(),
                    columns=circuit.circuits[0].power_flow_input.bus_names,
                    index=circuit.circuits[0].power_flow_input.branch_names)

print('C:\n', df_C)

df_Cb = pd.DataFrame((C.transpose() * C).todense(),
                     columns=circuit.circuits[0].power_flow_input.bus_names,
                     index=circuit.circuits[0].power_flow_input.bus_names)

print('C:\n', df_Cb)


B = C[branches_to_keep_idx, :]

df_B = pd.DataFrame(B.todense(),
                    columns=circuit.circuits[0].power_flow_input.bus_names,
                    index=circuit.circuits[0].power_flow_input.branch_names[branches_to_keep_idx])

print('B:\n', df_B)

# B is a CSC matrix
buses_to_keep = list()
for j in range(B.shape[1]):  # column index

    bus_occurrences = 0  # counter

    for k in range(B.indptr[j], B.indptr[j + 1]):
        # i = B.indices[k]  # row index
        # val = B.data[k]  # value
        bus_occurrences += 1

    if bus_occurrences > 0:  # if the bus appeared more than one time in the column of B, then we propose to keep it
        buses_to_keep.append(j)

D = B[:, buses_to_keep]

df_D = pd.DataFrame(D.todense(),
                    columns=circuit.circuits[0].power_flow_input.bus_names[buses_to_keep],
                    index=circuit.circuits[0].power_flow_input.branch_names[branches_to_keep_idx])

print('D:\n', df_D)

new_branches_to_keep = list()
buses_to_keep_s = set(buses_to_keep)
buses_availability = np.zeros(n, dtype=int)
for i in range(len(circuit.branches)):
    # get the from and to bus indices
    f = buses_dict[circuit.branches[i].bus_from]
    t = buses_dict[circuit.branches[i].bus_to]

    if f in buses_to_keep_s and t in buses_to_keep_s:
        new_branches_to_keep.append(i)
        buses_availability[i] = 1

E = C[new_branches_to_keep, :][:, buses_to_keep]

df_E = pd.DataFrame(E.todense(),
                    columns=circuit.circuits[0].power_flow_input.bus_names[buses_to_keep],
                    index=circuit.circuits[0].power_flow_input.branch_names[new_branches_to_keep])

print('E:\n', df_E)

# determine which buses to merge
for j in range(C.shape[1]):  # column index

    for k in range(C.indptr[j], C.indptr[j + 1]):
        i = B.indices[k]  # row index
