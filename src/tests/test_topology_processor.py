import os
from GridCalEngine.api import *
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.multi_circuit import MultiCircuit


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


def test_topology_reduction():
    """
    This function tests topology reduction for Node/Breaker model networks
    """
    for grid_ in [createExampleGridTest2(), createExampleGridTest1(), createExampleGridDiagram1()]:

        grid_.process_topology_at(t_idx=None)

        assert grid_.buses, "Buses creation failed"

        for l in grid_.get_branches():
            assert l.bus_from, "{} without bus_from associated".format(l.type_name)
            assert l.bus_to, "{} without bus_to associated".format(l.type_name)
        # TODO: procesador topológico adaptarlo a transformadores de 3
        if grid_.transformers3w:
            for t in grid_.transformers3w:
                assert t.bus1, "Transformer3w without bus1 associated"
                assert t.bus2, "Transformer3w without bus2 associated"
                assert t.bus3, "Transformer3w without bus3 associated"


def test_topology_rts() -> None:
    """
    This function tests topology reduction for Bus/branch model networks
    """
    for fname in [os.path.join('data', 'grids', 'case24_ieee_rts.m')]:
        grid = FileOpen(fname).open()

        # Original grid to compare its topology with reduced topology after creating a Node/Breaker model from it
        original_grid = grid.copy()

        grid.convert_to_node_breaker_adding_switches()  # Converting to Node/Breaker model
        processor_info = grid.process_topology_at(t_idx=None)  # Processing topology from new grid

        # Comparing bus considering bus number assigned
        for loriginal, lnb in zip(grid.get_lines(), original_grid.get_lines()):
            assert loriginal.bus_to.code == lnb.bus_to.code
            assert loriginal.bus_from.code == lnb.bus_from.code


def test_topology_NL_microgrid() -> None:
    fname = os.path.join('data', 'grids', 'CGMES_2_4_15', 'micro_grid_NL_T1.zip')
    grid = FileOpen(fname).open()
    logger = Logger()

    info = grid.process_topology_at(debug=1, logger=logger)

    cn_per_bus = info.get_cn_lists_per_bus()

    bus_names = ['NL_TR_BUS2', 'N1230822413', 'NL_Busbar__4', 'NL-Busbar_2', 'N1230992195',
                 'TN_Border_GY11', 'TN_Border_MA11', 'TN_Border_AL11', 'TN_Border_ST23', 'TN_Border_ST24']

    cn_names = ['NL_TR_BUS2', 'NL_TR_BUS1', 'N1230822396', 'N1230822413', 'NL-Busbar_5', 'NL_Busbar__4', 'NL-Busbar_3',
                'NL-Busbar_2', 'NL-_Busbar_1', 'N1230992201', 'N1230992198', 'N1230992195', 'N1230992231',
                'N1230992228', 'Border_GY11', 'Border_ST23', 'Border_ST24', 'Border_MA11', 'Border_AL11']

    cn_to_bus = {

        # Green bus
        'NL-_Busbar_1': '',
        'N1230992201': '',
        'N1230992198': '',
        'N1230992195': '',

        # ocre system bus 1
        'NL_TR_BUS2': 'NL_TR_BUS2',
        'NL-Busbar_5': 'NL_TR_BUS2',

        # ocre system bus 2
        'N1230822413': 'N1230822413',
        'NL-Busbar_3': 'N1230822413',

        # all purple bus
        'NL-Busbar_2': '',
        'NL_TR_BUS1': '',
        'NL_Busbar__4': '',
        'N1230992228': '',
        'N1230992231': '',
        'N1230822396': '',

        # frontier buses (5 of them)
        'Border_GY11': 'TN_Border_GY11',
        'Border_ST23': 'TN_Border_ST23',
        'Border_ST24': 'TN_Border_ST24',
        'Border_MA11': 'TN_Border_MA11',
        'Border_AL11': 'TN_Border_AL11'
    }
    # NOTE: Probably the candidate nodes are causing trouble here

    logger.print()

    print()
