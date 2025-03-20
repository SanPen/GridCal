# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Dict
import numpy as np
import numba as nb
import scipy.sparse as sp
from scipy.sparse import csc_matrix, diags, csr_matrix
from GridCalEngine.basic_structures import IntVec, Vec, BoolVec, CxVec


@nb.njit(cache=True)
def find_islands_numba(node_number: int, indptr: IntVec, indices: IntVec, active: IntVec) -> List[IntVec]:
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
            stack: List[int] = list()  # type:
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


def find_islands(adj: csc_matrix, active: IntVec) -> List[IntVec]:
    """
    Method to get the islands of a graph
    This is the non-recursive version
    :param adj: adjacency
    :param active: active state of the nodes
    :return: list of islands, where each element is a list of the node indices of the island
    """
    if adj.format != "csc":
        adj = adj.tocsc()

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

    assert C_element_bus.shape[0] == len(active), "You should probably transpose the matrix :/"

    # faster method
    indices = get_elements_of_the_island_numba(n_rows=C_element_bus.shape[0],
                                               indptr=C_element_bus.indptr,
                                               indices=C_element_bus.indices,
                                               island=np.array(island, dtype=int),
                                               active=active)

    return indices


@nb.njit(cache=True)
def get_island_monopole_indices(bus_map: IntVec, elm_active: BoolVec, elm_bus: IntVec) -> IntVec:
    """

    :param bus_map:
    :param elm_active:
    :param elm_bus:
    :return:
    """
    n_elm = len(elm_active)
    indices = np.zeros(n_elm, dtype=np.int64)

    ii = 0
    for k in range(n_elm):
        if elm_active[k] and bus_map[elm_bus[k]] > -1:
            indices[ii] = k
            ii += 1

    return indices[:ii]


@nb.njit(cache=True)
def get_island_branch_indices(bus_map: IntVec, elm_active: BoolVec, F: IntVec, T: IntVec) -> IntVec:
    """

    :param bus_map:
    :param elm_active:
    :param F:
    :param T:
    :return:
    """
    n_elm = len(elm_active)
    indices = np.zeros(n_elm, dtype=np.int64)

    ii = 0
    for k in range(n_elm):
        if elm_active[k] and bus_map[F[k]] > -1 and bus_map[T[k]] > -1:
            indices[ii] = k
            ii += 1

    return indices[:ii]


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


def get_csr_bus_indices(C: csr_matrix) -> IntVec:
    """
    Get the bus indices given a CSR shunt-element->bus connectivity matrix
    :param C: CSR connectivity matrix
    :return: Bus indices
    """
    arr = np.zeros(C.shape[1], dtype=int)
    for j in range(C.shape[0]):  # para cada columna j ...
        for k in range(C.indptr[j], C.indptr[j + 1]):  # para cada entrada de la columna ....
            i = C.indices[k]  # obtener el índice de la fila
            # value = data[k]  # obtener el valor de i, j
            arr[i] = j
    return arr


class ConnectivityMatrices:
    """
    Connectivity matrices
    """

    def __init__(self, Cf: sp.csc_matrix, Ct: sp.csc_matrix):
        self.Cf_ = Cf
        self.Ct_ = Ct

    @property
    def Cf(self) -> sp.csc_matrix:
        """
        Get the connectivity from matrix
        :return: sp.csc_matrix
        """
        if not isinstance(self.Cf_, sp.csc_matrix):
            self.Cf_ = self.Cf_.tocsc()
        return self.Cf_

    @property
    def Ct(self) -> sp.csc_matrix:
        """
        Get the connectivity to matrix
        :return: sp.csc_matrix
        """
        if not isinstance(self.Ct_, sp.csc_matrix):
            self.Ct_ = self.Ct_.tocsc()
        return self.Ct_

    @property
    def C(self) -> sp.csc_matrix:
        """
        Adjacency matrix
        :return:
        """
        return (self.Cf_ + self.Ct_).tocsc()

    def get_adjacency(self, bus_active: IntVec) -> csc_matrix:
        """

        :param bus_active:
        :return:
        """
        return (diags(bus_active) * (self.C.T @ self.C)).tocsc()


def compute_connectivity(branch_active: IntVec,
                         Cf_: csc_matrix,
                         Ct_: csc_matrix) -> ConnectivityMatrices:
    """
    Compute the from and to connectivity matrices applying the branch states
    :param branch_active: array of branch states
    :param Cf_: Connectivity branch-bus "from"
    :param Ct_: Connectivity branch-bus "to"
    :return: Final Ct and Cf in CSC format
    """
    br_states_diag = sp.diags(branch_active)
    Cf = br_states_diag * Cf_
    Ct = br_states_diag * Ct_

    return ConnectivityMatrices(Cf=Cf.tocsc(), Ct=Ct.tocsc())


def compute_connectivity_flexible(branch_active: IntVec | None = None,
                                  Cf_: csc_matrix | None = None,
                                  Ct_: csc_matrix | None = None,
                                  hvdc_active: IntVec | None = None,
                                  Cf_hvdc: csc_matrix | None = None,
                                  Ct_hvdc: csc_matrix | None = None,
                                  vsc_active: IntVec | None = None,
                                  Cf_vsc: csc_matrix | None = None,
                                  Ct_vsc: csc_matrix | None = None) -> ConnectivityMatrices:
    """
    Compute the from and to connectivity matrices applying the branch states
    :param branch_active: array of branch states
    :param Cf_: Connectivity branch-bus "from"
    :param Ct_: Connectivity branch-bus "to"
    :param hvdc_active: array of hvdc states
    :param Cf_hvdc: Connectivity hvdc-bus "from"
    :param Ct_hvdc: Connectivity hvdc-bus "to"
    :param vsc_active: array of hvdc states
    :param Cf_vsc: Connectivity hvdc-bus "from"
    :param Ct_vsc: Connectivity hvdc-bus "to"
    :return: Final Ct and Cf in CSC format
    """

    cf_stack = list()
    ct_stack = list()

    if branch_active is not None:
        if len(branch_active):
            br_states_diag = sp.diags(branch_active.astype(int))
            cf_stack.append(br_states_diag @ Cf_)
            ct_stack.append(br_states_diag @ Ct_)

    if hvdc_active is not None:
        if len(hvdc_active):
            hvdc_states_diag = sp.diags(hvdc_active.astype(int))
            cf_stack.append(hvdc_states_diag @ Cf_hvdc)
            ct_stack.append(hvdc_states_diag @ Ct_hvdc)

    if vsc_active is not None:
        if len(vsc_active):
            vsc_states_diag = sp.diags(vsc_active.astype(int))
            cf_stack.append(vsc_states_diag @ Cf_vsc)
            ct_stack.append(vsc_states_diag @ Ct_vsc)

    if len(cf_stack) == 0:
        raise ValueError("No set was provided to compute the connectivity :(")

    elif len(cf_stack) == 1:
        Cf = cf_stack[0]
        Ct = ct_stack[0]

    else:
        Cf = sp.vstack(cf_stack)
        Ct = sp.vstack(ct_stack)

    return ConnectivityMatrices(Cf=Cf.tocsc(), Ct=Ct.tocsc())


@nb.njit(cache=True)
def sum_per_bus(nbus: int, bus_indices: IntVec, magnitude: Vec) -> Vec:
    """
    Summation of magnitudes per bus (real)
    :param nbus: number of buses
    :param bus_indices: elements' bus indices
    :param magnitude: elements' magnitude to add per bus
    :return: array of size nbus
    """
    assert len(bus_indices) == len(magnitude)
    res = np.zeros(nbus, dtype=np.float64)
    for i in range(len(bus_indices)):
        res[bus_indices[i]] += magnitude[i]
    return res


@nb.njit(cache=True)
def sum_per_bus_cx(nbus: int, bus_indices: IntVec, magnitude: CxVec) -> CxVec:
    """
    Summation of magnitudes per bus (complex)
    :param nbus: number of buses
    :param bus_indices: elements' bus indices
    :param magnitude: elements' magnitude to add per bus
    :return: array of size nbus
    """
    assert len(bus_indices) == len(magnitude)
    res = np.zeros(nbus, dtype=np.complex128)
    for i in range(len(bus_indices)):
        res[bus_indices[i]] += magnitude[i]
    return res


@nb.njit(cache=True)
def sum_per_bus_bool(nbus: int, bus_indices: IntVec, magnitude: BoolVec) -> BoolVec:
    """
    Summation of magnitudes per bus (bool)
    :param nbus: number of buses
    :param bus_indices: elements' bus indices
    :param magnitude: elements' magnitude to add per bus
    :return: array of size nbus
    """
    assert len(bus_indices) == len(magnitude)
    res = np.zeros(nbus, dtype=np.bool_)
    for i in range(len(bus_indices)):
        res[bus_indices[i]] += magnitude[i]
    return res


@nb.njit(cache=True)
def dev_per_bus(nbus: int, bus_indices: IntVec) -> IntVec:
    """
    Summation of magnitudes per bus (bool)
    :param nbus: number of buses
    :param bus_indices: elements' bus indices
    :return: array of size nbus
    """
    res = np.zeros(nbus, dtype=np.int64)
    for i in range(len(bus_indices)):
        res[bus_indices[i]] += 1
    return res
