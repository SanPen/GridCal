from GridCalEngine.api import *
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from scipy.sparse import lil_matrix, csc_matrix


def createExampleGrid():
    """
    Función para crear un Multicircuit a partir de la red del diagrama 1 de la documentación
    """

    grid = MultiCircuit()

    # Add busbar representing physical nodes not the calculation ones
    busbardict = {}
    for i in range(5):
        # TODO: Me genera confusión que esto se llame igual que el próximo Busbar que será el nudo de cálculo
        b = dev.BusBar(name='B{}'.format(i + 1))
        busbardict['B{}'.format(i + 1)] = i
        grid.bus_bars.append(b)

    # Add Connectivity Schema representing physical connections
    cnbus = {'T1': 'B1', 'T2': 'B2', 'T3': 'B1', 'T4': 'B2', 'T5': 'B2',
             'T12': 'B3', 'T13': 'B4', 'T14': 'B4', 'T15': 'B4', 'T16': 'B5'}
    cndict = {}
    for i in range(16):
        busbar = grid.bus_bars[busbardict[cnbus['T{}'.format(i + 1)]]] if 'T{}'.format(i + 1) in cnbus else None
        t = dev.ConnectivityNode(name='T{}'.format(i + 1), bus_bar=busbar)
        cndict['T{}'.format(i + 1)] = i
        grid.connectivity_nodes.append(t)

    # Add lines
    linelist = {'L1': ('T6', 'T9'), 'L2': ('T7', 'T10'), 'L3': ('T8', 'T11'), 'L4': ('T15', 'T16')}
    for l in linelist:
        cnfrom = grid.connectivity_nodes[cndict[linelist[l][0]]] if linelist[l][0] else None
        cnto = grid.connectivity_nodes[cndict[linelist[l][1]]] if linelist[l][1] else None
        li = dev.Line(name=l, cn_from=cnfrom, cn_to=cnto)
        grid.lines.append(li)

    # Add switches
    switchlist = {'SW1': ('T1', 'T2', 'closed'), 'SW2': ('T3', 'T6', 'closed'), 'SW3': ('T4', 'T7', 'closed'),
                  'SW4': ('T5', 'T8', 'closed'), 'SW5': ('T9', 'T12', 'closed'), 'SW6': ('T10', 'T13', 'closed'),
                  'SW7': ('T11', 'T14', 'closed')}

    for s in switchlist:
        cnfrom = grid.connectivity_nodes[cndict[switchlist[s][0]]] if switchlist[s][0] else None
        cnto = grid.connectivity_nodes[cndict[switchlist[s][1]]] if switchlist[s][1] else None
        pos = True if switchlist[s][2] == 'closed' else False
        s = dev.Switch(name=s, cn_from=cnfrom, cn_to=cnto, active=pos)
        grid.switch_devices.append(s)

    return grid


def topology_proc(grid: MultiCircuit):
    nbus = len(grid.connectivity_nodes)
    nswitch = len(grid.switch_devices)
    cndict = {i.name: t for t, i in enumerate(grid.connectivity_nodes)}
    # Sustitution step: calculation busbar creation

    # 1. Searching for calculation busbar
    n_calc_nodes = 0
    obb = len(grid.bus_bars)  # Amount of original busbar
    busbarvisited = {}  # Dictionary to link original buses with new calculation nodes
    newbusbar = {}  # Calculation node position in grid.bus_bar
    for t in grid.connectivity_nodes:
        if t.bus_bar:
            if t.bus_bar.name in busbarvisited:
                t.bus_bar = grid.bus_bars[newbusbar[busbarvisited[t.bus_bar.name]]]
            else:
                n = dev.BusBar(name='N{}'.format(n_calc_nodes + 1))
                busbarvisited[t.bus_bar.name] = 'N{}'.format(n_calc_nodes + 1)
                newbusbar['N{}'.format(n_calc_nodes + 1)] = n_calc_nodes + obb
                grid.bus_bars.append(n)
                t.bus_bar = grid.bus_bars[newbusbar['N{}'.format(n_calc_nodes + 1)]]
                n_calc_nodes += 1
        else:
            n = dev.BusBar(name='N{}'.format(n_calc_nodes + 1))
            newbusbar['N{}'.format(n_calc_nodes + 1)] = n_calc_nodes + obb
            grid.bus_bars.append(n)
            t.bus_bar = grid.bus_bars[newbusbar['N{}'.format(n_calc_nodes + 1)]]
            n_calc_nodes += 1
    # TODO: ¿eliminamos los busbar originales?

    # 2. Switch Adjacency Matrix

    M = lil_matrix((n_calc_nodes, nswitch), dtype=int)
    for t, s in enumerate(grid.switch_devices):
        M[newbusbar[s.cn_from.bus_bar.name] - obb, t] = 1 if s.active else 0
        M[newbusbar[s.cn_to.bus_bar.name] - obb, t] = 1 if s.active else 0
    C = M @ M.T
    C = C.tocsc()

    # 3. Schema reduction

    reduced = np.zeros(n_calc_nodes, dtype=int)  # stores which buses are to merge with another bus

    indptr = C.indptr.copy()  # Indptr from csc matrix
    indices = C.indices.copy()  # Indices from csc matrix
    for c in range(n_calc_nodes):  # Cover every column
        a = indptr[c]
        b = indptr[c + 1]
        for k in range(a, b):  # Cover row range with values != 0
            r = indices[k]
            if r > c:  # if we are here is that the value is != 0 because this is a sparse matrix
                C[r, :] += C[c, :]
                C = csc_matrix(C)
                reduced[r] += 1
        indptr = C.indptr.copy()
        indices = C.indices.copy()

    # 4. Grouping
    groups = dict()
    j = 0
    for c in range(n_calc_nodes):
        if reduced[c] == 0:  # the buses that were not marked as reduced are the "master buses"
            group = list()
            for r in range(c, n_calc_nodes):
                if C[r, c] > 0:
                    group.append(r)  # the group includes the master bus
            if len(group) == 0:
                group.append(c)  # if the group has no length, add the main bus, because it is not reducible
            groups[j] = group
            j += 1

    return grid


def test_topology_processor():
    # Loading grid
    grid = createExampleGrid()

    # Topology processors
    grid_processed = topology_proc(grid)


if __name__ == '__main__':
    test_topology_processor()
