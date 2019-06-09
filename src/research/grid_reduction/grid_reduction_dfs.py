from GridCal.Engine.calculation_engine import MultiCircuit, BranchType
from networkx import Graph, all_simple_paths
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix, csc_matrix, diags
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


def get_connectivity(file_name):

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

    graph = Graph()

    for i in range(len(circuit.branches)):
        # get the from and to bus indices
        f = buses_dict[circuit.branches[i].bus_from]
        t = buses_dict[circuit.branches[i].bus_to]
        graph.add_edge(f, t)
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

    return circuit, states, C, C.transpose() * C, graph


def get_branches_of_bus(B, j):
    """
    Get the indices of the branches connected to the bus j
    :param B: Branch-bus CSC matrix
    :param j: bus index
    :return: list of branches in the bus
    """
    return [B.indices[k] for k in range(B.indptr[j], B.indptr[j + 1])]


if __name__ == '__main__':

    fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\Reduction Model 2.xlsx'

    circuit = MultiCircuit()
    circuit.load_file(fname)
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

    graph = Graph()

    for i in range(len(circuit.branches)):
        # get the from and to bus indices
        f = buses_dict[circuit.branches[i].bus_from]
        t = buses_dict[circuit.branches[i].bus_to]
        graph.add_edge(f, t)
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

    # -----------------------------------------------------------------

    for br_idx in branches_to_remove_idx:

        f = buses_dict[circuit.branches[br_idx].bus_from]
        t = buses_dict[circuit.branches[br_idx].bus_to]

        n_paths = 0
        for p in all_simple_paths(graph, f, t):
            n_paths += 1

        if n_paths > 1:
            # just remove the branch
            graph.remove_edge(f, t)
            circuit.branches.pop(br_idx)

        else:
            # merge the buses f and t
            """
            - get the branches of 'f'
            - move all the object of 'f' to 't'
            - replace the bus 'f' by the bus 't' in all the branches
            - delete the bus f from the circuit
            """
            # get the branches of 'f'
            branches = get_branches_of_bus(C, f)
            bus_f = circuit.branches[br_idx].bus_from
            bus_t = circuit.branches[br_idx].bus_to

            # move all the object of 'f' to 't'
            bus_t.loads += bus_f.loads
            bus_t.controlled_generators += bus_f.controlled_generators

            # replace the bus 'f' by the bus 't' in all the branches
            for k in branches:
                f2 = buses_dict[circuit.branches[k].bus_from]
                t2 = buses_dict[circuit.branches[k].bus_to]

                if f2 == f:
                    circuit.branches[k].bus_from = bus_t
                elif t2 == f:
                    circuit.branches[k].bus_to = bus_t

            # delete the bus f from the circuit
            circuit.buses.pop(f)
    # -----------------------------------------------------------------------------------------
