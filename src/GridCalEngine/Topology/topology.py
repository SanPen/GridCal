# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

from typing import List, Dict, Union, Tuple
import numpy as np
import numba as nb
import scipy.sparse as sp
from scipy.sparse import csc_matrix, diags, csr_matrix
from GridCalEngine.basic_structures import IntVec, Vec, Logger
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.Devices.types import BRANCH_TYPES


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


def find_islands(adj: csc_matrix, active: IntVec) -> List[IntVec]:
    """
    Method to get the islands of a graph
    This is the non-recursive version
    :param adj: adjacency
    :param active: active state of the nodes
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
    def A(self) -> sp.csc_matrix:
        return (self.Cf_ - self.Ct_).tocsc()


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


def compute_connectivity_with_hvdc(branch_active: IntVec,
                                   Cf_: csc_matrix,
                                   Ct_: csc_matrix,
                                   hvdc_active: Union[None, IntVec] = None,
                                   Cf_hvdc: Union[None, csc_matrix] = None,
                                   Ct_hvdc: Union[None, csc_matrix] = None) -> ConnectivityMatrices:
    """
    Compute the from and to connectivity matrices applying the branch states
    :param branch_active: array of branch states
    :param Cf_: Connectivity branch-bus "from"
    :param Ct_: Connectivity branch-bus "to"
    :param hvdc_active: array of hvdc states
    :param Cf_hvdc: Connectivity hvdc-bus "from"
    :param Ct_hvdc: Connectivity hvdc-bus "to"
    :return: Final Ct and Cf in CSC format
    """
    br_states_diag = sp.diags(branch_active)
    hvdc_states_diag = sp.diags(hvdc_active)
    Cf = sp.vstack([br_states_diag * Cf_, hvdc_states_diag * Cf_hvdc])
    Ct = sp.vstack([br_states_diag * Ct_, hvdc_states_diag * Ct_hvdc])

    return ConnectivityMatrices(Cf=Cf.tocsc(), Ct=Ct.tocsc())


class TopologyProcessorInfo:
    """
    TopologyProcessorInfo
    """

    def __init__(self) -> None:

        # list of buses that appear because of connectivity nodes
        self.new_candidates: List[Bus] = list()

        # list of final candidate buses for reduction
        self.candidates: List[Bus] = list()

        # map of ConnectivityNodes to candidate Buses
        self.cn_to_candidate: dict[ConnectivityNode, Bus] = dict()

        # integer position of the candidate bus matching a connectivity node
        self.candidate_to_int_dict = dict()

        # map of ConnectivityNodes to final Buses
        self.cn_to_final_bus: dict[ConnectivityNode, Bus] = dict()

    def get_connection_indices(self, elm: BRANCH_TYPES, logger: Logger) -> Tuple[int, int, bool]:
        """
        Get connection indices
        :param elm:
        :param logger:
        :return: f, t, ok
        """
        # if elm.cn_from is not None and elm.cn_to is not None and elm.bus_from is not None and elm.bus_to is not None:
        #     # All properties are not None
        #     f = self.get_candidate_pos_from_cn(elm.cn_from)
        #     t = self.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is not None and elm.bus_from is not None and elm.bus_to is None:
        #     # bus_to is None
        #     f = self.get_candidate_pos_from_cn(elm.cn_from)
        #     t = self.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is not None and elm.bus_from is None and elm.bus_to is not None:
        #     # bus_from is None
        #     f = self.get_candidate_pos_from_cn(elm.cn_from)
        #     t = self.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is not None and elm.bus_from is None and elm.bus_to is None:
        #     # bus_from and bus_to are None
        #     f = self.get_candidate_pos_from_cn(elm.cn_from)
        #     t = self.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is None and elm.bus_from is not None and elm.bus_to is not None:
        #     # cn_to is None
        #     f = self.get_candidate_pos_from_cn(elm.cn_from)
        #     t = self.get_candidate_pos_from_bus(elm.bus_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is None and elm.bus_from is not None and elm.bus_to is None:
        #     # cn_to and bus_to are None
        #     # raise ValueError("No to connection provided!")
        #     logger.add_error(msg="No to connection provided!", device=elm.name)
        #     return -1, -1, False
        #
        # elif elm.cn_from is not None and elm.cn_to is None and elm.bus_from is None and elm.bus_to is not None:
        #     # cn_to and bus_from are None
        #     f = self.get_candidate_pos_from_cn(elm.cn_from)
        #     t = self.get_candidate_pos_from_bus(elm.bus_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is None and elm.bus_from is None and elm.bus_to is None:
        #     # cn_to, bus_from, and bus_to are None
        #     # raise ValueError("No to connection provided!")
        #     logger.add_error(msg="No to connection provided!", device=elm.name)
        #     return -1, -1, False
        #
        # elif elm.cn_from is None and elm.cn_to is not None and elm.bus_from is not None and elm.bus_to is not None:
        #     # cn_from is None
        #     f = self.get_candidate_pos_from_bus(elm.bus_from)
        #     t = self.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is None and elm.cn_to is not None and elm.bus_from is not None and elm.bus_to is None:
        #     # cn_from and bus_to are None
        #     f = self.get_candidate_pos_from_bus(elm.bus_from)
        #     t = self.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is None and elm.cn_to is not None and elm.bus_from is None and elm.bus_to is not None:
        #     # cn_from and bus_from are None
        #     # raise ValueError("No from connection provided!")
        #     logger.add_error(msg="No to connection provided!", device=elm.name)
        #     return -1, -1, False
        #
        # elif elm.cn_from is None and elm.cn_to is not None and elm.bus_from is None and elm.bus_to is None:
        #     # cn_from, bus_from, and bus_to are None
        #     # raise ValueError("No from connection provided!")
        #     logger.add_error(msg="No to connection provided!", device=elm.name)
        #     return -1, -1, False
        #
        # elif elm.cn_from is None and elm.cn_to is None and elm.bus_from is not None and elm.bus_to is not None:
        #     # cn_from and cn_to are None
        #     f = self.get_candidate_pos_from_bus(elm.bus_from)
        #     t = self.get_candidate_pos_from_bus(elm.bus_to)
        #
        # elif elm.cn_from is None and elm.cn_to is None and elm.bus_from is not None and elm.bus_to is None:
        #     # cn_from, cn_to, and bus_to are None
        #     # raise ValueError("No to connection provided!")
        #     logger.add_error(msg="No to connection provided!", device=elm.name)
        #     return -1, -1, False
        #
        # elif elm.cn_from is None and elm.cn_to is None and elm.bus_from is None and elm.bus_to is not None:
        #     # cn_from, cn_to, and bus_from are None
        #     # raise ValueError("No from connection provided!")
        #     logger.add_error(msg="No to connection provided!", device=elm.name)
        #     return -1, -1, False
        #
        # elif elm.cn_from is None and elm.cn_to is None and elm.bus_from is None and elm.bus_to is None:
        #     # All properties are None
        #     # raise ValueError("isolated branch!")
        #     logger.add_error(msg="Isolated branch!", device=elm.name)
        #     return -1, -1, False
        #
        # else:
        #     # All properties are None
        #     # raise ValueError("isolated branch!")
        #     logger.add_error(msg="Isolated branch!", device=elm.name)
        #     return -1, -1, False

        fr_obj, to_obj, ok = elm.get_from_and_to_objects(logger=logger)

        if ok:
            if isinstance(fr_obj, ConnectivityNode):
                f = self.get_candidate_pos_from_cn(fr_obj)
            elif isinstance(fr_obj, Bus):
                f = self.get_candidate_pos_from_bus(fr_obj)
            else:
                f = -1

            if isinstance(to_obj, ConnectivityNode):
                t = self.get_candidate_pos_from_cn(to_obj)
            elif isinstance(to_obj, Bus):
                t = self.get_candidate_pos_from_bus(to_obj)
            else:
                t = -1

            if f == t:
                logger.add_error(msg="Loop connected branch!", device=elm.name)
                return -1, -1, False

            return f, t, True

        else:
            logger.add_error(msg="No to connection provided!", device=elm.name)
            return -1, -1, False

    def add_new_candidate(self, new_candidate: Bus):
        """

        :param new_candidate:
        :return:
        """
        self.new_candidates.append(new_candidate)

    def add_candidate(self, new_candidate: Bus):
        """

        :param new_candidate:
        :return:
        """
        self.candidate_to_int_dict[new_candidate] = len(self.candidates)
        self.candidates.append(new_candidate)

    def candidate_number(self) -> int:
        """
        Number of candidates
        :return: integer
        """
        return len(self.candidates)

    def get_candidate_pos_from_cn(self, cn: ConnectivityNode) -> int:
        """
        Get the integer position of the candidate bus matching a connectivity node
        :param cn: ConnectivityNode
        :return: integer
        """
        candidate = self.cn_to_candidate[cn]
        return self.candidate_to_int_dict[candidate]

    def get_candidate_pos_from_bus(self, bus: Bus) -> int:
        """
        Get the integer position of the candidate bus matching
        :param bus: Bus
        :return: integer
        """
        return self.candidate_to_int_dict[bus]

    def get_candidate_active(self, t_idx: Union[None, int]) -> IntVec:
        """
        Get the active array of candidate buses at a time index
        :param t_idx: time index
        :return: Array of bus active
        """
        bus_active = np.ones(self.candidate_number(), dtype=int)

        for i, elm in enumerate(self.candidates):
            bus_active[i] = int(elm.active) if t_idx is None else int(elm.active_prof[t_idx])

        return bus_active

    def apply_results(self, islands: List[List[int]]) -> List[Bus]:
        """
        Apply the topology results
        :param islands: rsults from the topology search
        :return: list of final buses
        """
        final_buses = list()
        # print("Islands:")
        for island in islands:
            # print(",".join([self.candidates[i].name for i in island]))

            island_bus = self.candidates[island[0]]

            # pick the first bus from each island
            final_buses.append(island_bus)

            for cn, candidate_bus in self.cn_to_candidate.items():
                for i in island:
                    if candidate_bus == self.candidates[i]:
                        self.cn_to_final_bus[cn] = island_bus

        return final_buses

    def get_final_bus(self, cn: ConnectivityNode) -> Bus:
        """
        Get the final Bus that should map to a connectivity node
        :param cn: ConnectivityNode
        :return: Final calculation Bus
        """
        return self.cn_to_final_bus[cn]

    def get_cn_lists_per_bus(self) -> Dict[Bus, List[ConnectivityNode]]:
        """
        Invert cn_to_final_bus
        :return: Dict[Bus, List[ConnectivityNode]]
        """
        data = dict()

        for cn, bus in self.cn_to_final_bus.items():

            lst = data.get(bus, None)

            if lst is None:
                data[bus] = [cn]
            else:
                lst.append(cn)

        return data

    def get_candidate_names(self) -> List[str]:
        """

        :return:
        """
        return [c.name for c in self.candidates]


def compute_connectivity_acdc_isolated(branch_active: IntVec,
                                       Cf_: csc_matrix,
                                       Ct_: csc_matrix,
                                       vsc_active: Union[None, IntVec] = None,
                                       Cf_vsc: Union[None, csc_matrix] = None,
                                       Ct_vsc: Union[None, csc_matrix] = None,
                                       vsc_branch_idx: Union[None, IntVec] = None) -> ConnectivityMatrices:
    """
    Remove the VSC branches from the connectivity matrices by setting rows indexed by vsc_branch_idx to zero.
    """

    # Convert matrices to LIL format for efficient row manipulation
    Cf = Cf_.tolil()
    Ct = Ct_.tolil()

    # Set rows corresponding to VSC branches to zero
    for idx in vsc_branch_idx:
        Cf[idx, :] = 0
        Ct[idx, :] = 0

    # print("(topology.py) Modified Cf:")
    # print(Cf)
    # print("(topology.py) Modified Ct:")
    # print(Ct)

    # Convert back to CSC format for efficient matrix operations
    return ConnectivityMatrices(Cf=Cf.tocsc(), Ct=Ct.tocsc())
