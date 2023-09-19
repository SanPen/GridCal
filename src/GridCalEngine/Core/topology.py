# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from typing import List, Dict, Tuple
import numpy as np
import numba as nb
from scipy.sparse import csc_matrix, csr_matrix, diags
from GridCalEngine.basic_structures import BusMode, IntVec, Vec, Mat, CxVec


@nb.njit(cache=True)
def find_islands_numba(node_number: int, indptr: IntVec, indices: IntVec, active: IntVec) -> List[Vec]:
    """
    Method to get the islands of a graph
    This is the non-recursive version
    :param node_number:
    :param indptr: index pointers in the CSC scheme
    :param indices: column indices in the CSCS scheme
    :param active: array of node active
    :return: list of islands, where each element is a list of the node indices of the island
    """

    # Mark all the vertices as not visited
    visited = np.zeros(node_number, dtype=np.int32)

    # storage structure for the islands (2D Numpy array)
    # there can be as many islands as nodes
    islands = list()  # type: List[Vec]

    node_count = 0
    current_island = np.empty(node_number, dtype=np.int64)

    # set the island index
    island_idx = 0

    # go though all the vertices...
    for node in range(node_number):

        # if the node has not been visited...
        if not visited[node] and active[node]:

            # ------------------------------------------------------------------------------------------------------
            # DFS: store in the island all the reachable vertices from current vertex "node"
            #
            # declare a stack with the initial node to visit (node)
            stack = list()  # type: List[int]
            stack.append(node)

            while len(stack) > 0:

                # pick the first element of the stack
                v = stack.pop(0)

                # if v has not been visited...
                if not visited[v]:

                    # mark as visited
                    visited[v] = 1

                    # add element to the island
                    current_island[node_count] = v
                    node_count += 1

                    # Add the neighbours of v to the stack
                    start = indptr[v]
                    end = indptr[v + 1]
                    for i in range(start, end):
                        k = indices[i]  # get the row index in the CSC scheme
                        if not visited[k] and active[k]:
                            stack.append(k)
            # ------------------------------------------------------------------------------------------------------
            # all the other connected vertices have been visited
            # ------------------------------------------------------------------------------------------------------

            # slice the current island to its actual size
            island = current_island[:node_count].copy()
            island.sort()  # sort in-place

            # assign the current island
            islands.append(island)

            # increase the islands index, because
            island_idx += 1

            # reset the current island
            # no need to re-allocate "current_island" since it is going to be overwritten
            node_count = 0

    return islands


@nb.njit(cache=True)
def get_elements_of_the_island_numba(n_rows: int,
                                     indptr: IntVec,
                                     indices: IntVec,
                                     island: IntVec,
                                     active: IntVec) -> IntVec:
    """
    Get the element indices of the island
    :param n_rows: Number of rows of the connectivity matrix
    :param indptr: CSC index pointers of the element-node connectivity matrix
    :param indices: CSC indices of the element-node connectivity matrix
    :param island: island node indices
    :param active: Array of bus active
    :return: array of indices of the elements that match that island
    """

    visited = np.zeros(n_rows, dtype=nb.int32)
    elm_idx = np.zeros(n_rows, dtype=nb.int32)
    n_visited = 0

    for k in range(len(island)):

        j = island[k]  # column index

        for l in range(indptr[j], indptr[j + 1]):

            i = indices[l]  # row index

            if not visited[i] and active[i]:
                visited[i] = 1
                elm_idx[n_visited] = i
                n_visited += 1

    # resize vector
    elm_idx = elm_idx[:n_visited]
    elm_idx.sort()
    return elm_idx


def find_islands(adj: csc_matrix, active: IntVec) -> List[List[int]]:
    """
    Method to get the islands of a graph
    This is the non-recursive version
    :return: list of islands, where each element is a list of the node indices of the island
    """
    return find_islands_numba(node_number=adj.shape[0],
                              indptr=adj.indptr,
                              indices=adj.indices,
                              active=active)


def get_elements_of_the_island(C_element_bus: csc_matrix, island: IntVec, active: IntVec) -> IntVec:
    """
    Get the branch indices of the island
    :param C_element_bus: CSC elements-buses connectivity matrix with the dimensions: elements x buses
    :param island: array of bus indices of the island
    :param active: Array of bus active
    :return: array of indices of the elements that match that island
    """

    if not isinstance(C_element_bus, csc_matrix):
        C_element_bus = C_element_bus.tocsc()

    # faster method
    indices = get_elements_of_the_island_numba(n_rows=C_element_bus.shape[0],
                                               indptr=C_element_bus.indptr,
                                               indices=C_element_bus.indices,
                                               island=np.array(island, dtype=int),
                                               active=active)

    return indices


def get_adjacency_matrix(C_branch_bus_f: csc_matrix, C_branch_bus_t: csc_matrix,
                         branch_active: IntVec, bus_active: IntVec) -> csc_matrix:
    """
    Compute the adjacency matrix
    :param C_branch_bus_f: Branch-bus_from connectivity matrix
    :param C_branch_bus_t: Branch-bus_to connectivity matrix
    :param branch_active: array of Branches availability
    :param bus_active: array of buses availability
    :return: Adjacency matrix
    """

    br_states_diag = diags(branch_active)
    Cf = br_states_diag * C_branch_bus_f
    Ct = br_states_diag * C_branch_bus_t

    # branch - bus connectivity
    C_branch_bus = Cf + Ct

    # Connectivity node - Connectivity node connectivity matrix
    C_bus_bus = diags(bus_active) * (C_branch_bus.T * C_branch_bus)

    return C_bus_bus


def find_different_states(states_array: IntVec, force_all=False) -> Dict[int, List[int]]:
    """
    Find the different branch states in time that may lead to different islands
    :param states_array: bool array indicating the different grid states (time, device)
    :param force_all: Skip analysis and every time step is a state
    :return: Dictionary with the time: [array of times] represented by the index, for instance
             {0: [0, 1, 2, 3, 4], 5: [5, 6, 7, 8]}
             This means that [0, 1, 2, 3, 4] are represented by the topology of 0
             and that [5, 6, 7, 8] are represented by the topology of 5
    """
    ntime = states_array.shape[0]

    if force_all:
        return {i: [i] for i in range(ntime)}  # force all states

    else:

        # initialize
        states = dict()  # type: Dict[int, List[int]]
        k = 1
        for t in range(ntime):

            # search this state in the already existing states
            keys = list(states.keys())
            nn = len(keys)
            found = False
            i = 0
            while i < nn and not found:
                t2 = keys[i]

                # compare state at t2 with the state at t
                if np.array_equal(states_array[t, :], states_array[t2, :]):
                    states[t2].append(t)  # add the state to the existing list of the key
                    found = True

                i += 1

            if not found:
                # new state found (append itself)
                states[t] = [t]

            k += 1

        return states


@nb.njit(cache=True)
def compile_types(Pbus: Vec, types: IntVec) -> Tuple[IntVec, IntVec, IntVec, IntVec]:
    """
    Compile the types.
    :param Pbus: array of real power Injections per node used to choose the slack as
                 the node with greater generation if no slack is provided
    :param types: array of tentative node types (it may be modified internally)
    :return: ref, pq, pv, pqpv
    """

    # check that Sbus is a 1D array
    assert (len(Pbus.shape) == 1)

    pq = np.where(types == BusMode.PQ.value)[0]
    pv = np.where(types == BusMode.PV.value)[0]
    ref = np.where(types == BusMode.Slack.value)[0]

    if len(ref) == 0:  # there is no slack!

        if len(pv) == 0:  # there are no pv neither -> blackout grid
            pass
        else:  # select the first PV generator as the slack

            mx = max(Pbus[pv])
            if mx > 0:
                # find the generator that is injecting the most
                i = np.where(Pbus == mx)[0][0]

            else:
                # all the generators are injecting zero, pick the first pv
                i = pv[0]

            # delete the selected pv bus from the pv list and put it in the slack list
            pv = np.delete(pv, np.where(pv == i)[0])
            ref = np.array([i])

        for r in ref:
            types[r] = BusMode.Slack.value
    else:
        pass  # no problem :)

    pqpv = np.concatenate((pq, pv))
    pqpv.sort()

    return ref, pq, pv, pqpv


def get_csr_bus_indices(C: csr_matrix):
    arr = np.zeros(C.shape[1], dtype=int)
    for j in range(C.shape[0]):  # para cada columna j ...
        for k in range(C.indptr[j], C.indptr[j + 1]):  # para cada entrada de la columna ....
            i = C.indices[k]  # obtener el índice de la fila
            # value = data[k]  # obtener el valor de i, j
            arr[i] = j
    return arr
