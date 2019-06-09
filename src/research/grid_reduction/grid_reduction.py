from GridCal.Engine.calculation_engine import MultiCircuit, BranchType
from networkx import DiGraph, all_simple_paths
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

    graph = DiGraph()

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


def reduce_grid(circuit: MultiCircuit, rx_criteria=True, rx_threshold=1e-5,
                type_criteria=True, selected_type=BranchType.Branch):

    # form C
    m = len(circuit.branches)
    n = len(circuit.buses)
    C = lil_matrix((m, n), dtype=int)
    buses_dict = {bus: i for i, bus in enumerate(circuit.buses)}
    branches_to_keep_idx = list()
    branches_to_remove_idx = list()

    bus_names = [elm.name for elm in circuit.buses]
    branch_names = [elm.name for elm in circuit.branches]
    graph = DiGraph()

    for i in range(len(circuit.branches)):
        # get the from and to bus indices
        f = buses_dict[circuit.branches[i].bus_from]
        t = buses_dict[circuit.branches[i].bus_to]
        graph.add_edge(f, t)
        C[i, f] = 1
        C[i, t] = -1

        # check if to select the branch for removal
        chosen_to_be_removed = False

        if rx_criteria:
            rx = circuit.branches[i].R + circuit.branches[i].X
            if rx < rx_threshold:
                branches_to_remove_idx.append(i)
                chosen_to_be_removed = True

        if type_criteria and not chosen_to_be_removed:
            if circuit.branches[i].branch_type == selected_type:
                branches_to_remove_idx.append(i)
                chosen_to_be_removed = True

        if not chosen_to_be_removed:
            branches_to_keep_idx.append(i)

    C = csc_matrix(C)

    # -----------------------------------------------------------------
    branches_to_remove_idx.sort(reverse=True)

    print('Branches to remove:')
    for b in branches_to_remove_idx:
        print('\t', circuit.branches[b])

    print('Initial')
    dfc = pd.DataFrame(data=C.toarray(), columns=bus_names, index=branch_names)
    print(dfc)

    for br_idx in branches_to_remove_idx:

        print('Removing ', circuit.branches[br_idx])

        f = buses_dict[circuit.branches[br_idx].bus_from]
        t = buses_dict[circuit.branches[br_idx].bus_to]

        # get the number of paths
        n_paths = len(list(all_simple_paths(graph, f, t)))

        if n_paths > 1:
            # just remove the branch
            print('\tRemoving no merge', circuit.branches[br_idx])
            graph.remove_edge(f, t)
            circuit.branches.pop(br_idx)
            C = csc_matrix(np.delete(C.toarray(), br_idx, 0))
            branch_names.pop(br_idx)
            pass
        else:
            # merge the buses f and t
            """
            - get the branches of 'f'
            - remove the branch
            - move all the object of 'f' to 't'
            - replace the bus 'f' by the bus 't' in all the branches
            - delete the bus f from the circuit
            """
            # get the branches of 'f'
            bus_f = circuit.branches[br_idx].bus_from
            bus_t = circuit.branches[br_idx].bus_to
            print('\tMerging', bus_f, '->', bus_t)

            # move all the object of 'f' to 't'
            bus_t.loads += bus_f.loads
            bus_t.controlled_generators += bus_f.controlled_generators

            # remove matrix branch
            C = csc_matrix(np.delete(C.toarray(), br_idx, 0))

            # replace the bus 'f' by the bus 't' in all the branches
            branches = get_branches_of_bus(C, f)
            print('\tBranches of ', bus_f, ':', [circuit.branches[x].name for x in branches])

            for k in branches:
                '''
                We are deleting the bus 'f'
                in all the branches connected to 'f', we must replace 'f' by 't'
                '''

                f2 = buses_dict[circuit.branches[k].bus_from]
                t2 = buses_dict[circuit.branches[k].bus_to]

                if (f2, t2) in graph.edges:
                    graph.remove_edge(f2, t2)
                else:
                    if (t2, f2) in graph.edges:
                        graph.remove_edge(t2, f2)
                    else:
                        print('WTF!:', circuit.branches[k].name)
                        # return
                        # raise Exception('WTF!')

                if f2 == f:
                    print('\tReassigning at', circuit.branches[k], ':', circuit.branches[k].bus_from, '->', bus_t)
                    circuit.branches[k].bus_from = bus_t
                    graph.add_edge(f2, t)  # the previous edge does no longer exists, create a new relation
                elif t2 == f:
                    print('\tReassigning at', circuit.branches[k], ':', circuit.branches[k].bus_to, '->', bus_t)
                    circuit.branches[k].bus_to = bus_t
                    graph.add_edge(t, t2)   # the previous edge does no longer exists, create a new relation

            # remove the branch
            if (f, t) in graph.edges:
                graph.remove_edge(f, t)
            else:
                if (t, f) in graph.edges:
                    graph.remove_edge(t, f)
                else:
                    raise Exception('WTF2!')
            circuit.branches.pop(br_idx)
            branch_names.pop(br_idx)

            # delete the bus f from the circuit
            # circuit.buses.pop(f)
            print('\tRemoving:', bus_f)
            circuit.buses.remove(bus_f)
            C[:, t] += abs(C[:, f])
            C = csc_matrix(np.delete(C.toarray(), f, 1))
            graph.remove_node(f)
            bus_names.pop(f)

        dfc = pd.DataFrame(data=C.toarray(), columns=bus_names, index=branch_names)
        print(dfc)
        print(list(graph.edges))


if __name__ == '__main__':
    from matplotlib import pyplot as plt
    fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\Reduction Model 2.xlsx'

    circuit_ = MultiCircuit()
    circuit_.load_file(fname)
    # circuit.compile()

    reduce_grid(circuit=circuit_, rx_criteria=False, rx_threshold=1e-5,
                type_criteria=True, selected_type=BranchType.Branch)

    # circuit_.compile()
    # circuit_.plot_graph()
    # plt.show()