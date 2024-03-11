from GridCalEngine.api import *
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Topology.topology import find_islands, get_adjacency_matrix
from scipy.sparse import lil_matrix


def createExampleGridDiagram1() -> MultiCircuit:
    """
    This function creates a Multicircuit example from SE Diagram 1 in documentation to test topology processor
    """

    grid = MultiCircuit()

    # Add busbar representing physical nodes not the calculation ones
    bus_bar_dict = {}
    cn_dict = {}
    for i in range(5):
        bb = dev.BusBar(name='BB{}'.format(i + 1))
        bb.cn.name = 'T{}'.format(i + 1)
        bus_bar_dict['BB{}'.format(i + 1)] = bb
        cn_dict[bb.cn.name] = bb.cn  # each busbar has an internal connectivity node
        grid.add_bus_bar(bb)  # both the bar and the internal cn are added to the grid

    for i in range(5, 11):  # create the rest of terminals
        term_name = f"T{i + 1}"
        cn = dev.ConnectivityNode(name=term_name)
        cn_dict[term_name] = cn
        grid.add_connectivity_node(cn)

    # Add lines
    line_data = {
        'L1': ('T6', 'T9'),
        'L2': ('T7', 'T10'),
        'L3': ('T8', 'T11'),
        'L4': ('T4', 'T5')
    }

    for line_name, (term_from_name, term_to_name) in line_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        li = dev.Line(name=line_name, cn_from=cn_from, cn_to=cn_to)
        grid.lines.append(li)

    # Add switches
    switch_data = {
        'SW1': ('T1', 'T2', 'closed'),
        'SW2': ('T1', 'T6', 'closed'),
        'SW3': ('T2', 'T7', 'closed'),
        'SW4': ('T2', 'T8', 'closed'),
        'SW5': ('T3', 'T9', 'closed'),
        'SW6': ('T4', 'T10', 'closed'),
        'SW7': ('T4', 'T11', 'closed')
    }

    for switch_name, (term_from_name, term_to_name, active_name) in switch_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        active = active_name == 'closed'
        s = dev.Switch(name=switch_name, cn_from=cn_from, cn_to=cn_to, active=active)
        grid.switch_devices.append(s)

    return grid


def createExampleGridTest1() -> MultiCircuit:
    """
    This function creates a Multicircuit example from Grid Test 1 in documentation to test topology processor
    """

    grid = MultiCircuit()

    # Add busbar representing physical nodes not the calculation ones
    bus_bar_dict = {}
    cn_dict = {}
    for i in range(4):
        bb = dev.BusBar(name='BB{}'.format(i + 1))
        bb.cn.name = 'T{}'.format(i + 1)
        bus_bar_dict['BB{}'.format(i + 1)] = bb
        cn_dict[bb.cn.name] = bb.cn  # each busbar has an internal connectivity node
        grid.add_bus_bar(bb)  # both the bar and the internal cn are added to the grid

    for i in range(4, 7):  # create the rest of terminals
        term_name = f"T{i + 1}"
        cn = dev.ConnectivityNode(name=term_name)
        cn_dict[term_name] = cn
        grid.add_connectivity_node(cn)

    # Add lines
    line_data = {
        'L1': ('T6', 'T2'),
        'L2': ('T2', 'T3'),
        'L3': ('T5', 'T3')
    }

    for line_name, (term_from_name, term_to_name) in line_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        li = dev.Line(name=line_name, cn_from=cn_from, cn_to=cn_to)
        grid.lines.append(li)

    # Add switches
    switch_data = {
        'SW1': ('T1', 'T5', 'open'),
        'SW2': ('T4', 'T5', 'closed'),
        'SW3': ('T1', 'T6', 'open'),
        'SW4': ('T4', 'T6', 'closed'),
        'SW5': ('T1', 'T7', 'closed')
    }

    for switch_name, (term_from_name, term_to_name, active_name) in switch_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        active = active_name == 'closed'
        s = dev.Switch(name=switch_name, cn_from=cn_from, cn_to=cn_to, active=active)
        grid.switch_devices.append(s)

    return grid


def createExampleGridTest2() -> MultiCircuit:
    """
    This function creates a Multicircuit example from Grid Test 2 in documentation to test topology processor
    """

    grid = MultiCircuit()

    # Add busbar representing physical nodes not the calculation ones
    bus_bar_dict = {}
    cn_dict = {}
    for i in range(5):
        bb = dev.BusBar(name='BB{}'.format(i + 1))
        bb.cn.name = 'T{}'.format(i + 1)
        bus_bar_dict['BB{}'.format(i + 1)] = bb
        cn_dict[bb.cn.name] = bb.cn  # each busbar has an internal connectivity node
        grid.add_bus_bar(bb)  # both the bar and the internal cn are added to the grid

    for i in range(5, 11):  # create the rest of terminals
        term_name = f"T{i + 1}"
        cn = dev.ConnectivityNode(name=term_name)
        cn_dict[term_name] = cn
        grid.add_connectivity_node(cn)

    # Add lines
    line_data = {
        'L1': ('T6', 'T2'),
        'L2': ('T7', 'T3'),
        'L3': ('T2', 'T3')
    }

    for line_name, (term_from_name, term_to_name) in line_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        li = dev.Line(name=line_name, cn_from=cn_from, cn_to=cn_to)
        grid.lines.append(li)

    # Add transformers
    transformer_data = {
        'TR1': ('T9', 'T10')
    }

    for tr_name, (term_from_name, term_to_name) in transformer_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        tr = dev.Transformer2W(name=tr_name, cn_from=cn_from, cn_to=cn_to)
        grid.transformers2w.append(tr)

    # Add switches
    switch_data = {
        'SW1': ('T1', 'T6', 'closed'),
        'SW2': ('T6', 'T5', 'closed'),
        'SW3': ('T1', 'T7', 'closed'),
        'SW4': ('T7', 'T5', 'closed'),
        'SW5': ('T1', 'T5', 'closed'),
        'SW6': ('T8', 'T5', 'closed'),
        'SW7': ('T8', 'T9', 'closed'),
        'SW8': ('T10', 'T4', 'closed'),
        'SW9': ('T1', 'T11', 'closed')
    }

    for switch_name, (term_from_name, term_to_name, active_name) in switch_data.items():
        cn_from = cn_dict[term_from_name]
        cn_to = cn_dict[term_to_name]
        active = active_name == 'closed'
        s = dev.Switch(name=switch_name, cn_from=cn_from, cn_to=cn_to, active=active)
        grid.switch_devices.append(s)

    return grid


class TopologyProcessorInfo:
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
        # self.busbar_to_candidate: dict[dev.BusBar, dev.Bus] = dict()

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
        print("Islands:")
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


def create_topology_process_info(grid: MultiCircuit) -> TopologyProcessorInfo:
    """
    Create the candidate buses for reduction from a set of BusBars and ConnectivityNodes
    :param grid: MultiCircuit
    :return: CandidatesInfo
    """
    info = TopologyProcessorInfo()

    # traverse connectivity nodes
    for cn in grid.get_connectivity_nodes():

        if cn.default_bus is None:  # connectivity nodes can be linked to a previously existing Bus
            # create a new candidate
            candidate_bus = dev.Bus(f"Candidate from {cn.name}")
            info.add_new_candidate(candidate_bus)
        else:
            # pick the default candidate
            candidate_bus = cn.default_bus

        # register
        info.add_candidate(candidate_bus)
        info.cn_to_candidate[cn] = candidate_bus

    return info


def compute_connectivities(nbus_candidate: int,
                           all_branches: List[Any],
                           process_info: TopologyProcessorInfo,
                           t_idx: Union[int, None] = None):
    """
    Compute the connectivity from and to matrices and the branches availabiility vector
    :param nbus_candidate: number of candidate buses
    :param all_branches: list of all branches
    :param process_info: CandidatesInfo previously created
    :param t_idx: Time index
    :return: Cf, Ct, br_active
    """
    nbr = len(all_branches)

    # declare the matrices
    Cf = lil_matrix((nbr, nbus_candidate))
    Ct = lil_matrix((nbr, nbus_candidate))
    br_active = np.empty(nbr, dtype=int)

    # fill matrices approprietly
    for i, elm in enumerate(all_branches):

        if elm.cn_from is not None:
            f = process_info.get_candidate_pos_from_cn(elm.cn_from)
            Cf[i, f] = 1

        if elm.cn_to is not None:
            t = process_info.get_candidate_pos_from_cn(elm.cn_to)
            Ct[i, t] = 1

        if elm.device_type == DeviceType.SwitchDevice:
            br_active[i] = int(elm.active) if t_idx is None else int(elm.active_prof[t_idx])
        else:
            # non switches form islands, because we want islands to be
            # the set of candidates to fuse into one
            br_active[i] = 0

    return Cf, Ct, br_active


def apply_results_to_grid(t_idx: Union[None, int],
                          grid: MultiCircuit,
                          final_buses: List[dev.Bus],
                          all_branches: List[Any],
                          process_info: TopologyProcessorInfo,
                          logger: Logger) -> None:
    """
    Apply the results of the topology processing
    :param t_idx: time index to apply the results to
    :param grid: MultiCircuit
    :param final_buses: List of final bus objects resulting from the topology process
    :param all_branches: List of all branches
    :param process_info: TopologyProcessorInfo
    :param logger: Logger
    :return: Nothig, the grid is processed in-place
    """
    # add any extra bus that may arise from the calculation
    print("Extra buses:")
    grid_buses_set = {b for b in grid.get_buses()}
    for bus_device in final_buses:
        if bus_device not in grid_buses_set:
            grid.add_bus(bus_device)
            logger.add_info("Bus added to grid", device=bus_device.name)
            # print("Bus {} added to grid".format(elm))

    # map the buses to the branches from their connectivity nodes
    # todo: make profiles of the bus_from and bus_to
    for i, elm in enumerate(all_branches):
        if elm.cn_from is not None:
            elm.bus_from = process_info.get_final_bus(elm.cn_from)

        if elm.cn_to is not None:
            elm.bus_to = process_info.get_final_bus(elm.cn_to)

    # TODO: Make profiles of the bus
    for dev_lst in grid.get_injection_devices_lists():
        for elm in dev_lst:
            elm.bus = process_info.get_final_bus(elm.cn)


def topology_processor(grid: MultiCircuit, t_idx: Union[int, None], logger: Logger):
    """
    Topology processor finding the Buses that calculate a certain node-breaker topology
    This function fill the bus pointers into the grid object, and adds any new bus required for simulation
    :param grid: MultiCircuit
    :param t_idx: Time index
    :param logger: Logger object
    :return: Results are processed into the grid object
    """
    # compose the candidate nodes (buses)
    process_info = create_topology_process_info(grid=grid)
    nbus_candidate = process_info.candidate_number()
    bus_active = process_info.get_candidate_active(t_idx=t_idx)

    # get a list of all branches
    all_branches = grid.get_branches()

    # create the connectivity matrices
    Cf, Ct, br_active = compute_connectivities(nbus_candidate=nbus_candidate,
                                               all_branches=grid.get_switches(),
                                               process_info=process_info,
                                               t_idx=t_idx)

    # print("Cf:\n", Cf.toarray())

    # compose the adjacency matrix from the connectivity information
    A = get_adjacency_matrix(C_branch_bus_f=Cf.tocsc(),
                             C_branch_bus_t=Ct.tocsc(),
                             branch_active=br_active,
                             bus_active=bus_active)

    # latexA = ('$$\n' + r'\begin{bmatrix}' + '\n'
    #           + (r'\\' + '\n').join('&'.join(str(x) for x in row) for row in A.toarray().astype(int)) + '\n'
    #           + r'\end{bmatrix}' + '\n' + '$$')
    #
    # print("A:\n", A.toarray())
    # print(latexA)

    # perform the topology search, this will find candidate buses that reduce to be the same bus
    # each island is finally a single calculation element
    islands = find_islands(adj=A, active=bus_active)

    # generate auxiliary structures that derive from the topology results
    final_buses = process_info.apply_results(islands=islands)
    # TODO: ¿No estaría bien asignar a cada connectivity node el bus final al que está asociado para invertirlo?
    # apply the results to the grid object
    apply_results_to_grid(t_idx=t_idx,
                          grid=grid,
                          final_buses=final_buses,
                          all_branches=all_branches,
                          process_info=process_info,
                          logger=logger)


if __name__ == '__main__':
    grid_ = createExampleGridDiagram1()
    # grid_ = createExampleGridTest1()
    # grid_ = createExampleGridTest2()
    logger_ = Logger()
    topology_processor(grid=grid_, t_idx=None, logger=logger_)
    logger_.print()
