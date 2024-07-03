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

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate


# class TopologyProcessorInfo:
#     """
#     CandidatesInfo
#     """
#
#     def __init__(self) -> None:
#
#         # list of buses that appear because of connectivity nodes
#         self.new_candidates: List[dev.Bus] = list()
#
#         # list of final candidate buses for reduction
#         self.candidates: List[dev.Bus] = list()
#
#         # map of ConnectivityNodes to candidate Buses
#         self.cn_to_candidate: dict[dev.ConnectivityNode, dev.Bus] = dict()
#
#         # map of BusBars to candidate Buses
#         # self.busbar_to_candidate: dict[dev.BusBar, dev.Bus] = dict()
#
#         # integer position of the candidate bus matching a connectivity node
#         self.candidate_to_int_dict = dict()
#
#         # map of ConnectivityNodes to final Buses
#         self.cn_to_final_bus: dict[dev.ConnectivityNode, dev.Bus] = dict()
#
#     def add_new_candidate(self, new_candidate: dev.Bus):
#         """
#
#         :param new_candidate:
#         :return:
#         """
#         self.new_candidates.append(new_candidate)
#
#     def add_candidate(self, new_candidate: dev.Bus):
#         """
#
#         :param new_candidate:
#         :return:
#         """
#         self.candidate_to_int_dict[new_candidate] = len(self.candidates)
#         self.candidates.append(new_candidate)
#
#     def candidate_number(self) -> int:
#         """
#         Number of candidated
#         :return:
#         """
#         return len(self.candidates)
#
#     def get_candidate_pos_from_cn(self, cn: dev.ConnectivityNode) -> int:
#         """
#         Get the integer position of the candidate bus matching a connectivity node
#         :param cn:
#         :return:
#         """
#         candidate = self.cn_to_candidate[cn]
#         return self.candidate_to_int_dict[candidate]
#
#     def get_candidate_active(self, t_idx: Union[None, int]) -> IntVec:
#         """
#
#         :param t_idx:
#         :return:
#         """
#         bus_active = np.ones(self.candidate_number(), dtype=int)
#
#         for i, elm in enumerate(self.candidates):
#             bus_active[i] = int(elm.active) if t_idx is None else int(elm.active_prof[t_idx])
#
#         return bus_active
#
#     def apply_results(self, islands: List[List[int]]) -> List[dev.Bus]:
#         """
#         Apply the topology results
#         :param islands: rsults from the topology search
#         :return: list of final buses
#         """
#         final_buses = list()
#         print("Islands:")
#         for island in islands:
#             print(",".join([self.candidates[i].name for i in island]))
#
#             island_bus = self.candidates[island[0]]
#
#             # pick the first bus from each island
#             final_buses.append(island_bus)
#
#             for cn, candidate_bus in self.cn_to_candidate.items():
#                 for i in island:
#                     if candidate_bus == self.candidates[i]:
#                         self.cn_to_final_bus[cn] = island_bus
#
#         return final_buses
#
#     def get_final_bus(self, cn: dev.ConnectivityNode) -> dev.Bus:
#         """
#         Get the final Bus that should map to a connectivity node
#         :param cn: ConnectivityNode
#         :return: Final calculation Bus
#         """
#         return self.cn_to_final_bus[cn]
#
#
# def create_topology_process_info(grid: MultiCircuit) -> TopologyProcessorInfo:
#     """
#     Create the candidate buses for reduction from a set of BusBars and ConnectivityNodes
#     :param grid: MultiCircuit
#     :return: CandidatesInfo
#     """
#     info = TopologyProcessorInfo()
#
#     # traverse connectivity nodes
#     for cn in grid.get_connectivity_nodes():
#
#         if cn.default_bus is None:  # connectivity nodes can be linked to a previously existing Bus
#             # create a new candidate
#             candidate_bus = dev.Bus(f"Candidate from {cn.name}")
#             candidate_bus.code = cn.code  # for soft checking
#             cn.default_bus = candidate_bus  # to avoid adding extra buses upon consecutive runs
#             info.add_new_candidate(candidate_bus)
#         else:
#             # pick the default candidate
#             candidate_bus = cn.default_bus
#
#         # register
#         info.add_candidate(candidate_bus)
#         info.cn_to_candidate[cn] = candidate_bus
#
#     return info
#
#
# def compute_connectivities(nbus_candidate: int,
#                            all_branches: List[BRANCH_TYPES],
#                            process_info: TopologyProcessorInfo,
#                            t_idx: Union[int, None] = None):
#     """
#     Compute the connectivity from and to matrices and the branches availabiility vector
#     :param nbus_candidate: number of candidate buses
#     :param all_branches: list of all branches
#     :param process_info: CandidatesInfo previously created
#     :param t_idx: Time index
#     :return: Cf, Ct, br_active
#     """
#     nbr = len(all_branches)
#
#     # declare the matrices
#     Cf = lil_matrix((nbr, nbus_candidate))
#     Ct = lil_matrix((nbr, nbus_candidate))
#     br_active = np.empty(nbr, dtype=int)
#
#     # fill matrices approprietly
#     for i, elm in enumerate(all_branches):
#
#         if elm.cn_from is not None:
#             f = process_info.get_candidate_pos_from_cn(elm.cn_from)
#             Cf[i, f] = 1
#
#         if elm.cn_to is not None:
#             t = process_info.get_candidate_pos_from_cn(elm.cn_to)
#             Ct[i, t] = 1
#
#         if elm.device_type == DeviceType.SwitchDevice:
#             br_active[i] = int(elm.active) if t_idx is None else int(elm.active_prof[t_idx])
#         else:
#             # non switches form islands, because we want islands to be
#             # the set of candidates to fuse into one
#             br_active[i] = 0
#
#     return Cf, Ct, br_active
#
#
# def apply_results_to_grid(t_idx: Union[None, int],
#                           grid: MultiCircuit,
#                           final_buses: List[dev.Bus],
#                           all_branches: List[BRANCH_TYPES],
#                           process_info: TopologyProcessorInfo,
#                           logger: Logger) -> None:
#     """
#     Apply the results of the topology processing
#     :param t_idx: time index to apply the results to
#     :param grid: MultiCircuit
#     :param final_buses: List of final bus objects resulting from the topology process
#     :param all_branches: List of all branches
#     :param process_info: TopologyProcessorInfo
#     :param logger: Logger
#     :return: Nothig, the grid is processed in-place
#     """
#     # add any extra bus that may arise from the calculation
#     grid_buses_set = {b for b in grid.get_buses()}
#     for bus_device in final_buses:
#         if bus_device not in grid_buses_set:
#             grid.add_bus(bus_device)
#             logger.add_info("Bus added to grid", device=bus_device.name)
#
#     # map the buses to the branches from their connectivity nodes
#     for i, elm in enumerate(all_branches):
#         if elm.cn_from is not None:
#             elm.set_bus_from_at(t_idx=t_idx, val=process_info.get_final_bus(elm.cn_from))
#
#         if elm.cn_to is not None:
#             elm.set_bus_to_at(t_idx=t_idx, val=process_info.get_final_bus(elm.cn_to))
#
#     for dev_lst in grid.get_injection_devices_lists():
#         for elm in dev_lst:
#             elm.set_bus_at(t_idx=t_idx, val=process_info.get_final_bus(elm.cn))
#
#
# def topology_processor(grid: MultiCircuit, t_idx: Union[int, None], logger: Logger):
#     """
#     Topology processor finding the Buses that calculate a certain node-breaker topology
#     This function fill the bus pointers into the grid object, and adds any new bus required for simulation
#     :param grid: MultiCircuit
#     :param t_idx: Time index
#     :param logger: Logger object
#     :return: Results are processed into the grid object
#     """
#     # compose the candidate nodes (buses)
#     process_info = create_topology_process_info(grid=grid)
#     nbus_candidate = process_info.candidate_number()
#     bus_active = process_info.get_candidate_active(t_idx=t_idx)
#
#     # get a list of all branches
#     all_branches = grid.get_branches()
#
#     # create the connectivity matrices
#     Cf, Ct, br_active = compute_connectivities(nbus_candidate=nbus_candidate,
#                                                all_branches=grid.get_switches(),
#                                                process_info=process_info,
#                                                t_idx=t_idx)
#
#     # compose the adjacency matrix from the connectivity information
#     A = get_adjacency_matrix(C_branch_bus_f=Cf.tocsc(),
#                              C_branch_bus_t=Ct.tocsc(),
#                              branch_active=br_active,
#                              bus_active=bus_active)
#
#     # perform the topology search, this will find candidate buses that reduce to be the same bus
#     # each island is finally a single calculation element
#     islands = find_islands(adj=A, active=bus_active)
#
#     # generate auxiliary structures that derive from the topology results
#     final_buses = process_info.apply_results(islands=islands)
#
#     # apply the results to the grid object
#     apply_results_to_grid(t_idx=t_idx,
#                           grid=grid,
#                           final_buses=final_buses,
#                           all_branches=all_branches,
#                           process_info=process_info,
#                           logger=logger)


class TopologyProcessorDriver(DriverTemplate):
    """
    TopologyProcessorDriver
    """

    name = 'Topology processor'
    tpe = SimulationTypes.TopologyProcessor_run

    def __init__(self, grid: MultiCircuit):
        """
        Electric distance clustering
        :param grid: MultiCircuit instance
        """
        DriverTemplate.__init__(self, grid=grid)

    def run(self):
        """
        Run the topology processing in-place
        @return:
        """
        self.tic()
        self.report_progress(0.0)
        nt = self.grid.get_time_number()

        # process snapshot
        self.grid.process_topology_at(t_idx=None, logger=self.logger)

        for t in range(nt):
            # process time step "t"
            self.grid.process_topology_at(t_idx=t, logger=self.logger)

            self.report_progress2(t, nt)

        # display progress
        self.report_done()
        self.toc()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.report_done("Cancelled!")
