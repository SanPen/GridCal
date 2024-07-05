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
from __future__ import annotations
from typing import List, Dict, Union, Tuple, TYPE_CHECKING
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from GridCalEngine.basic_structures import IntVec, Logger
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.Topology.topology import find_islands, get_adjacency_matrix

if TYPE_CHECKING:
    from GridCalEngine.Devices.multi_circuit import MultiCircuit


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
        #     f = grid.get_candidate_pos_from_cn(elm.cn_from)
        #     t = grid.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is not None and elm.bus_from is not None and elm.bus_to is None:
        #     # bus_to is None
        #     f = grid.get_candidate_pos_from_cn(elm.cn_from)
        #     t = grid.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is not None and elm.bus_from is None and elm.bus_to is not None:
        #     # bus_from is None
        #     f = grid.get_candidate_pos_from_cn(elm.cn_from)
        #     t = grid.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is not None and elm.bus_from is None and elm.bus_to is None:
        #     # bus_from and bus_to are None
        #     f = grid.get_candidate_pos_from_cn(elm.cn_from)
        #     t = grid.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is None and elm.bus_from is not None and elm.bus_to is not None:
        #     # cn_to is None
        #     f = grid.get_candidate_pos_from_cn(elm.cn_from)
        #     t = grid.get_candidate_pos_from_bus(elm.bus_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is None and elm.bus_from is not None and elm.bus_to is None:
        #     # cn_to and bus_to are None
        #     # raise ValueError("No to connection provided!")
        #     logger.add_error(msg="No to connection provided!", device=elm.name)
        #     return -1, -1, False
        #
        # elif elm.cn_from is not None and elm.cn_to is None and elm.bus_from is None and elm.bus_to is not None:
        #     # cn_to and bus_from are None
        #     f = grid.get_candidate_pos_from_cn(elm.cn_from)
        #     t = grid.get_candidate_pos_from_bus(elm.bus_to)
        #
        # elif elm.cn_from is not None and elm.cn_to is None and elm.bus_from is None and elm.bus_to is None:
        #     # cn_to, bus_from, and bus_to are None
        #     # raise ValueError("No to connection provided!")
        #     logger.add_error(msg="No to connection provided!", device=elm.name)
        #     return -1, -1, False
        #
        # elif elm.cn_from is None and elm.cn_to is not None and elm.bus_from is not None and elm.bus_to is not None:
        #     # cn_from is None
        #     f = grid.get_candidate_pos_from_bus(elm.bus_from)
        #     t = grid.get_candidate_pos_from_cn(elm.cn_to)
        #
        # elif elm.cn_from is None and elm.cn_to is not None and elm.bus_from is not None and elm.bus_to is None:
        #     # cn_from and bus_to are None
        #     f = grid.get_candidate_pos_from_bus(elm.bus_from)
        #     t = grid.get_candidate_pos_from_cn(elm.cn_to)
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
        #     f = grid.get_candidate_pos_from_bus(elm.bus_from)
        #     t = grid.get_candidate_pos_from_bus(elm.bus_to)
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
        candidate = self.candidate_to_int_dict.get(new_candidate, None)
        if candidate is None:
            self.candidate_to_int_dict[new_candidate] = len(self.candidates)
            self.candidates.append(new_candidate)
        else:
            # the candidate was added already
            pass

    def was_added(self, bus: Bus) -> bool:
        """
        Check if a bus was added already
        :param bus: Bus
        :return: bool
        """
        return bus in self.candidate_to_int_dict

    def add_cn(self, cn: ConnectivityNode):
        """

        :param cn:
        :return:
        """
        if cn.default_bus is None:  # connectivity nodes can be linked to a previously existing Bus

            # create a new candidate bus
            candidate_bus = Bus(name=f"Candidate from {cn.name}",
                                code=cn.code,  # for soft checking
                                Vnom=cn.Vnom  # we must keep the voltage level for the virtual taps
                                )

            cn.default_bus = candidate_bus  # to avoid adding extra buses upon consecutive runs
            self.add_new_candidate(candidate_bus)
        else:
            # pick the default candidate
            candidate_bus = cn.default_bus
            # candidate_bus.code = cn.code  # for soft checking

        # register
        if not self.was_added(candidate_bus):
            self.add_candidate(candidate_bus)

        self.cn_to_candidate[cn] = candidate_bus

    def add_bus_or_cn(self, cn: ConnectivityNode, bus: Bus):
        """

        :param cn:
        :param bus:
        :return:
        """
        # NOTE: we preffer the CN to the Buses where available
        if cn is not None:
            self.add_cn(cn=cn)
        else:
            if bus is not None:
                self.add_candidate(bus)

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
            # print(",".join([grid.candidates[i].name for i in island]))

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


def process_grid_topology_at(grid: MultiCircuit,
                             t_idx: Union[int, None] = None,
                             logger: Union[Logger, None] = None,
                             debug: int = 0) -> TopologyProcessorInfo:
    """
    Topology processor finding the Buses that calculate a certain node-breaker topology
    This function fill the bus pointers into the grid object, and adds any new bus required for simulation
    :param grid: MultiCircuit
    :param t_idx: Time index, None for the Snapshot
    :param logger: Logger object
    :param debug: Debug level
    :return: TopologyProcessorInfo
    """

    if logger is None:
        logger = Logger()

    # declare the auxiliary class
    process_info = TopologyProcessorInfo()

    # get a list of all branches
    all_branches = grid.get_switches() + grid.get_branches()
    nbr = len(all_branches)

    # ------------------------------------------------------------------------------------------------------------------
    # Compose the candidate nodes (buses)
    # ------------------------------------------------------------------------------------------------------------------

    # find out the relevant connectivity nodes and buses from the branches
    for br in all_branches:
        process_info.add_bus_or_cn(cn=br.cn_from, bus=br.bus_from)
        process_info.add_bus_or_cn(cn=br.cn_to, bus=br.bus_to)

    # find out the relevant connectivity nodes and buses from the injection devices
    for lst in grid.get_injection_devices_lists():
        for elm in lst:
            process_info.add_bus_or_cn(cn=elm.cn, bus=elm.bus)

    nbus_candidate = process_info.candidate_number()
    bus_active = process_info.get_candidate_active(t_idx=t_idx)

    # ------------------------------------------------------------------------------------------------------------------
    # Create the connectivity matrices
    # ------------------------------------------------------------------------------------------------------------------

    # declare the matrices
    Cf = lil_matrix((nbr, nbus_candidate))
    Ct = lil_matrix((nbr, nbus_candidate))
    br_active = np.empty(nbr, dtype=int)

    # fill matrices approprietly
    for i, elm in enumerate(all_branches):

        if elm.device_type == DeviceType.SwitchDevice:
            br_active[i] = int(elm.active) if t_idx is None else int(elm.active_prof[t_idx])
        else:
            # non switches form islands, because we want islands to be
            # the set of candidates to fuse into one
            br_active[i] = 0

        # if elm.cn_from is not None and elm.cn_to is not None:
        #     f = process_info.get_candidate_pos_from_cn(elm.cn_from)
        #     t = process_info.get_candidate_pos_from_cn(elm.cn_to)
        if br_active[i]:  # avoid adding zeros
            f, t, is_ok = process_info.get_connection_indices(elm=elm, logger=logger)
            Cf[i, f] = br_active[i]
            Ct[i, t] = br_active[i]

    # ------------------------------------------------------------------------------------------------------------------
    # Compose the adjacency matrix from the connectivity information
    # ------------------------------------------------------------------------------------------------------------------
    A = get_adjacency_matrix(C_branch_bus_f=Cf.tocsc(),
                             C_branch_bus_t=Ct.tocsc(),
                             branch_active=br_active,
                             bus_active=bus_active)

    if debug >= 2:
        candidate_names = process_info.get_candidate_names()
        br_names = [br.name for br in all_branches]
        C = Cf + Ct
        df = pd.DataFrame(data=C.toarray(), columns=candidate_names, index=br_names)
        print(df.replace(to_replace=0.0, value="-"))

        print("A:")

        df = pd.DataFrame(data=A.toarray(), columns=candidate_names, index=candidate_names)
        print(df.replace(to_replace=0.0, value="-"))
        print()

    # ------------------------------------------------------------------------------------------------------------------
    # Perform the topology search, this will find candidate buses that reduce to be the same bus
    # ------------------------------------------------------------------------------------------------------------------
    islands = find_islands(adj=A, active=bus_active)  # each island is finally a single calculation element

    if debug >= 1:
        for i, island in enumerate(islands):
            print(f"island {i}:", island)

    # ------------------------------------------------------------------------------------------------------------------
    # Generate auxiliary structures that derive from the topology results
    # ------------------------------------------------------------------------------------------------------------------
    final_buses = process_info.apply_results(islands=islands)

    # ------------------------------------------------------------------------------------------------------------------
    # Apply the results to the grid object
    # ------------------------------------------------------------------------------------------------------------------

    # Add any extra bus that may arise from the calculation
    grid_buses_set = {b for b in grid.get_buses()}
    for bus_device in final_buses:
        if bus_device not in grid_buses_set:
            grid.add_bus(bus_device)
            if logger:
                logger.add_info("Bus added to grid", device=bus_device.name)

    # map the buses to the branches from their connectivity nodes
    for i, elm in enumerate(all_branches):
        if elm.cn_from is not None:
            elm.set_bus_from_at(t_idx=t_idx, val=process_info.get_final_bus(elm.cn_from))

        if elm.cn_to is not None:
            elm.set_bus_to_at(t_idx=t_idx, val=process_info.get_final_bus(elm.cn_to))

    for dev_lst in grid.get_injection_devices_lists():
        for elm in dev_lst:
            if elm.cn is not None:
                elm.set_bus_at(t_idx=t_idx, val=process_info.get_final_bus(elm.cn))

    # return the TopologyProcessorInfo
    return process_info
