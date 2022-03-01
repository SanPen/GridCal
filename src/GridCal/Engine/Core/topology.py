# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from typing import List
import numpy as np
import numba as nb
from scipy.sparse import csc_matrix, diags


# @nb.jit(cache=True)
def find_islands_numba(node_number, indptr, indices, active: np.ndarray):
    """
    Method to get the islands of a graph
    This is the non-recursive version
    :return: list of islands, where each element is a list of the node indices of the island
    """

    # Mark all the vertices as not visited
    visited = np.zeros(node_number, dtype=int)

    # storage structure for the islands (list of lists)
    islands = list()  # type: List[List[int]]
    # islands = nb.typeof([[0]])

    # set the island index
    island_idx = 0

    # go though all the vertices...
    for node in range(node_number):

        # if the node has not been visited...
        if not visited[node] and active[node]:

            # add new island, because the recursive process has already visited all the island connected to v
            # if island_idx >= len(islands):
            islands.append(list())

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
                    islands[island_idx].append(v)

                    # Add the neighbours of v to the stack
                    start = indptr[v]
                    end = indptr[v + 1]
                    for i in range(start, end):
                        k = indices[i]  # get the row index in the CSC scheme
                        if not visited[k] and active[k]:
                            stack.append(k)
            # ------------------------------------------------------------------------------------------------------

            # increase the islands index, because all the other connected vertices have been visited
            island_idx += 1

    # sort each of the islands to maintain raccord
    for island in islands:
        island.sort()  # the sorting is done in-place

    return islands


@nb.njit(cache=True)
def get_elements_of_the_island_numba(n_rows, indptr, indices, island, active):
    """
    Get the element indices of the island
    :param n_rows: Number of rows of the connectivity matrix
    :param indptr: CSC index pointers of the element-node connectivity matrix
    :param indices: CSC indices of the element-node connectivity matrix
    :param island: island node indices
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

    return elm_idx


def find_islands(adj: csc_matrix, active: np.ndarray):
    """
    Method to get the islands of a graph
    This is the non-recursive version
    :return: list of islands, where each element is a list of the node indices of the island
    """
    return find_islands_numba(node_number=adj.shape[0],
                              indptr=adj.indptr,
                              indices=adj.indices,
                              active=active)


def get_elements_of_the_island(C_element_bus, island, active):
    """
    Get the branch indices of the island
    :param C_element_bus: CSC elements-buses connectivity matrix with the dimensions: elements x buses
    :param island: array of bus indices of the island
    :return: array of indices of the elements that match that island
    """

    if not isinstance(C_element_bus, csc_matrix):
        C_element_bus = C_element_bus.tocsc()

    # faster method
    return get_elements_of_the_island_numba(n_rows=C_element_bus.shape[0],
                                            indptr=C_element_bus.indptr,
                                            indices=C_element_bus.indices,
                                            island=np.array(island, dtype=int),
                                            active=active)


def get_adjacency_matrix(C_branch_bus_f, C_branch_bus_t, branch_active, bus_active):
    """
    Compute the adjacency matrix
    :param C_branch_bus_f: Branch-bus_from connectivity matrix
    :param C_branch_bus_t: Branch-bus_to connectivity matrix
    :param branch_active: array of branches availability
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



