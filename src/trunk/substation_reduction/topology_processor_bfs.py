from GridCalEngine.api import *
import GridCalEngine.Core.Devices as dev
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.topology import find_islands, get_adjacency_matrix
from scipy.sparse import lil_matrix, csc_matrix


def createExampleGrid() -> MultiCircuit:
    """
    Función para crear un Multicircuit a partir de la red del diagrama 1 de la documentación
    """

    grid = MultiCircuit()

    # Add busbar representing physical nodes not the calculation ones
    bus_bar_dict = {}
    for i in range(5):
        # TODO: Me genera confusión que esto se llame igual que el próximo Busbar que será el nudo de cálculo
        b = dev.BusBar(name='B{}'.format(i + 1))
        bus_bar_dict['B{}'.format(i + 1)] = b
        grid.bus_bars.append(b)

    # Add Connectivity Nodes representing physical connections
    cn2bus_data = {
        'T1': 'B1',
        'T2': 'B2',
        'T3': 'B1',
        'T4': 'B2',
        'T5': 'B2',
        'T12': 'B3',
        'T13': 'B4',
        'T14': 'B4',
        'T15': 'B4',
        'T16': 'B5'
    }
    cn_dict = {}
    for i in range(16):
        term_name = f"T{i + 1}"
        cn = dev.ConnectivityNode(name=term_name)
        cn_dict[term_name] = cn
        grid.add_connectivity_node(cn)

    # set associations
    for term_name, bus_bar_name in cn2bus_data.items():
        bus_bar = bus_bar_dict[bus_bar_name]
        cn = cn_dict[term_name]
        cn.bus_bar = bus_bar

    # Add lines
    line_data = {
        'L1': ('T6', 'T9'),
        'L2': ('T7', 'T10'),
        'L3': ('T8', 'T11'),
        'L4': ('T15', 'T16')
    }

    for line_name, (term_from_name, term_to_name) in line_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        li = dev.Line(name=line_name, cn_from=cn_from, cn_to=cn_to)
        grid.lines.append(li)

    # Add switches
    switch_data = {
        'SW1': ('T1', 'T2', 'closed'),
        'SW2': ('T3', 'T6', 'closed'),
        'SW3': ('T4', 'T7', 'closed'),
        'SW4': ('T5', 'T8', 'closed'),
        'SW5': ('T9', 'T12', 'closed'),
        'SW6': ('T10', 'T13', 'closed'),
        'SW7': ('T11', 'T14', 'closed')
    }

    for switch_name, (term_from_name, term_to_name, active_name) in switch_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        active = active_name == 'closed'
        s = dev.Switch(name=switch_name, cn_from=cn_from, cn_to=cn_to, active=active)
        grid.switch_devices.append(s)

    return grid


class CandidatesInfo:
    """
    CandidatesInfo
    """

    def __init__(self) -> None:

        # list of buses that appear because of connectivity nodes
        self.new_candidates: List[dev.Bus] = list()

        # list of final candidate buses for reduction
        self.candidates: List[dev.Bus] = list()

        # map of ConnectivityNodes to candidate Buses
        self.cn_to_candidate: dict[dev.ConnectivityNode, dev.Bus] = dict()

        # map of BusBars to candidate Buses
        self.busbar_to_candidate: dict[dev.BusBar, dev.Bus] = dict()

        # integer position of the candidate bus matching a connectivity node
        self.candidate_to_int_dict = dict()

        # map of ConnectivityNodes to final Buses
        self.cn_to_final_bus: dict[dev.ConnectivityNode, dev.Bus] = dict()

    def add_new_candidate(self, new_candidate: dev.Bus):
        """

        :param new_candidate:
        :return:
        """
        self.new_candidates.append(new_candidate)

    def add_candidate(self, new_candidate: dev.Bus):
        """

        :param new_candidate:
        :return:
        """
        self.candidate_to_int_dict[new_candidate] = len(self.candidates)
        self.candidates.append(new_candidate)

    def candidate_number(self) -> int:
        """
        Number of candidated
        :return:
        """
        return len(self.candidates)

    def get_candidate_pos_from_cn(self, cn: dev.ConnectivityNode) -> int:
        """
        Get the integer position of the candidate bus matching a connectivity node
        :param cn:
        :return:
        """
        candidate = self.cn_to_candidate[cn]
        return self.candidate_to_int_dict[candidate]

    def get_candidate_active(self, t_idx: Union[None, int]) -> IntVec:
        """

        :param t_idx:
        :return:
        """
        bus_active = np.ones(self.candidate_number(), dtype=int)

        for i, elm in enumerate(self.candidates):
            bus_active[i] = int(elm.active) if t_idx is None else int(elm.active_prof[t_idx])

        return bus_active

    def apply_results(self, islands: List[List[int]]) -> List[dev.Bus]:
        """
        Apply the topology results
        :param islands: rsults from the topology search
        :return: list of final buses
        """
        final_buses = list()
        for island in islands:
            print(",".join([self.candidates[i].name for i in island]))

            island_bus = self.candidates[island[0]]

            # pick the first bus from each island
            final_buses.append(island_bus)

            for cn, candidate_bus in self.cn_to_candidate.items():
                for i in island:
                    if candidate_bus == self.candidates[i]:
                        self.cn_to_final_bus[cn] = island_bus

        return final_buses

    def get_final_bus(self, cn: dev.ConnectivityNode) -> dev.Bus:
        """
        Get the final Bus that should map to a connectivity node
        :param cn: ConnectivityNode
        :return: Final calculation Bus
        """
        return self.cn_to_final_bus[cn]


def create_candidates(grid: MultiCircuit) -> CandidatesInfo:
    """
    Create the candidate buses for reduction from a set of BusBars and ConnectivityNodes
    :param grid: MultiCircuit
    :return: CandidatesInfo
    """
    info = CandidatesInfo()

    # traverse bus bars
    for bus_bar in grid.get_bus_bars():

        if bus_bar.default_bus is None:
            candidate_bus = dev.Bus(f"Candidate from {bus_bar.name}")
            info.add_new_candidate(candidate_bus)
        else:
            candidate_bus = bus_bar.default_bus

        # register
        info.add_candidate(candidate_bus)
        info.busbar_to_candidate[bus_bar] = candidate_bus

    # traverse connectivity nodes
    for cn in grid.get_connectivity_nodes():

        if cn.bus_bar is not None:
            # pick the candidate of the bus_bar
            candidate_bus = info.busbar_to_candidate[cn.bus_bar]
        else:
            # create a new candidate
            candidate_bus = dev.Bus(f"Candidate from {cn.name}")
            info.add_new_candidate(candidate_bus)
            info.add_candidate(candidate_bus)

        # register
        info.cn_to_candidate[cn] = candidate_bus

    return info


def compute_connectivities(nbus_candidate, all_branches, candidate_info, t_idx: Union[int, None] = None):
    """

    :param nbus_candidate:
    :param all_branches:
    :param candidate_info:
    :param t_idx:
    :return:
    """
    nbr = len(all_branches)

    # declare the matrices
    Cf = lil_matrix((nbr, nbus_candidate))
    Ct = lil_matrix((nbr, nbus_candidate))
    br_active = np.empty(nbr, dtype=int)

    # fill matrices approprietly
    for i, elm in enumerate(all_branches):
        f = candidate_info.get_candidate_pos_from_cn(elm.cn_from)
        t = candidate_info.get_candidate_pos_from_cn(elm.cn_to)

        if elm.device_type == DeviceType.SwitchDevice:
            br_active[i] = int(elm.active) if t_idx is None else int(elm.active_prof[t_idx])
        else:
            # non switches form islands, because we want islands to be
            # the set of candidates to fuse into one
            br_active[i] = 0

        Cf[i, f] = 1
        Ct[i, t] = 1

    return Cf, Ct, br_active


def topology_processor(grid: MultiCircuit, t_idx: Union[int, None] = None):
    """
    Topology processor finding the Buses that calculate a certain node-breaker topology
    This function fill the bus pointers into the grid object, and adds any new bus required for simulation
    :param grid: MultiCircuit
    :param t_idx: Time index
    :return: Results are processed into the grid object
    """
    # compose the candidate nodes (buses)
    candidate_info = create_candidates(grid=grid)
    nbus_candidate = candidate_info.candidate_number()
    bus_active = candidate_info.get_candidate_active(t_idx=t_idx)

    # get a list of all branches
    all_branches = grid.get_branches()

    # create the connectivity matrices
    Cf, Ct, br_active = compute_connectivities(nbus_candidate, all_branches, candidate_info, t_idx)

    # perform the topology search
    A = get_adjacency_matrix(C_branch_bus_f=Cf.tocsc(),
                             C_branch_bus_t=Ct.tocsc(),
                             branch_active=br_active,
                             bus_active=bus_active)

    islands = find_islands(adj=A, active=bus_active)

    final_buses = candidate_info.apply_results(islands=islands)

    # map the buses to all branches
    # todo: make bus_from and bus_to profiles
    for i, elm in enumerate(all_branches):
        elm.bus_from = candidate_info.get_final_bus(elm.cn_from)
        elm.bus_to = candidate_info.get_final_bus(elm.cn_to)

    # add any extra bus that may arise from the calculation
    grid_buses_set = {b for b in grid.get_buses()}
    for elm in final_buses:
        if elm not in grid_buses_set:
            grid.add_bus(elm)
            print("Bus {} added to grid".format(elm))


if __name__ == '__main__':
    grid_ = createExampleGrid()

    topology_processor(grid=grid_)
