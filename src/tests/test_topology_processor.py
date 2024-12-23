# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

from GridCalEngine.api import *
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.api import power_flow
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc


def test_cn_makes_a_bus() -> None:
    """
    Checks if by crating a CN, we also create a bus
    :return:
    """
    grid = MultiCircuit()
    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0"))

    assert grid.get_bus_number() == 1


def test_cn_makes_a_bus2():
    """
    Checks if by crating a CN, with a pre-existing bus, we don't create a new bus
    """
    grid = MultiCircuit()
    b0 = grid.add_bus(dev.Bus(name="B0"))

    assert grid.get_bus_number() == 1

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))

    assert grid.get_bus_number() == 1

    assert grid.buses[0] == b0


def test_busbar_makes_a_bus():
    """
    Checks if by crating a busbar, we also create a cn and a bus
    """
    grid = MultiCircuit()

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    assert grid.get_connectivity_nodes_number() == 1

    assert grid.get_bus_number() == 1

    assert grid.buses[0] == bb3.cn.bus


def test_busbar_makes_a_bus2():
    """
    Checks if by crating a busbar using an existing cn, we respect the exiting buses and cn's
    """
    grid = MultiCircuit()

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0"))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3", cn=cn0))

    assert grid.get_connectivity_nodes_number() == 1

    assert grid.get_bus_number() == 1

    assert grid.connectivity_nodes[0] == bb3.cn

    assert grid.buses[0] == bb3.cn.bus


def test_topology_4_nodes_A():
    """
    Topology test 4 Node A
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=b1))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", cn_from=cn0, cn_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, cn_to=bb3.cn, active=False))

    l1 = grid.add_line(dev.Line(name="L1", cn_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    logger = Logger()
    grid.process_topology_at(logger=logger)

    """
    After processing,
    branches: [L1, L2, SW1, SW2]
    L1 must be between B0 and B2
    L2 must be between B0 and a new bus that is not B0, B1 or B2
    SW1 must be in a self-loop where both buses are B0
    SW2 must be connected between B2 and the bus to of L2
    """
    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [0, 0, 0, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 3, 0, 3]).all()
    assert np.equal(nc.generator_data.bus_idx, [3]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_B():
    """
    Topology test 4 Node B
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=b1))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", cn_from=cn0, cn_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, cn_to=bb3.cn, active=True))

    l1 = grid.add_line(dev.Line(name="L1", cn_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    After processing,
    L1 must be between B0 and B2
    L2 must be between B0 and B2
    SW1 must be in a self-loop where both buses are B0
    SW2 must be in a self-loop where both buses are B2
    """
    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [0, 0, 0, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 2, 0, 2]).all()
    assert np.equal(nc.generator_data.bus_idx, [2]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_C():
    """
    Topology test 4 Node C
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=b1))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", cn_from=cn0, cn_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, cn_to=bb3.cn, active=True))

    l1 = grid.add_line(dev.Line(name="L1", cn_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    After processing,
    L1 must be between B0 and B2
    L2 must be between B1 and B2
    SW1 must be between B0 and B1
    SW2 must be in a self-loop where both buses are B2
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [0, 1, 0, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 2, 1, 2]).all()
    assert np.equal(nc.generator_data.bus_idx, [2]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_D():
    """
    Topology test 4 Node D
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=b1))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", cn_from=cn0, cn_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, cn_to=bb3.cn, active=False))

    l1 = grid.add_line(dev.Line(name="L1", cn_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    After processing,
    L1 must be between B0 and B2
    L2 must be between B1 and a new bus that is not b0, b1, b2 
    SW1 must be between B0 and B1
    SW2 must be between B2 and L2 bus_to
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [0, 1, 0, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 3, 1, 3]).all()
    assert np.equal(nc.generator_data.bus_idx, [3]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_E():
    """
    Topology test 4 Node E
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    # there are buses but some are not used (not referenced by the cn's)

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=None))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=None))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", cn_from=cn0, cn_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, cn_to=bb3.cn, active=True))

    l1 = grid.add_line(dev.Line(name="L1", cn_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    After processing,
    L1 must be between a new bus from cn0 and b2
    L2 must be between a new bus from cn0 and b2
    SW1 must be in a self loop where both buses are L1.bus_from
    SW2 must be in a self loop where both buses are L1.bus_to / b2
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [3, 3, 3, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 2, 3, 2]).all()
    assert np.equal(nc.generator_data.bus_idx, [2]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_F():
    """
    Topology test 4 Node F
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    # there are buses but some are not used (not referenced by the cn's)

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=None))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=None))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", cn_from=cn0, cn_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, cn_to=bb3.cn, active=True))

    l1 = grid.add_line(dev.Line(name="L1", cn_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    After processing,
    L1 must be between a new bus from cn0 and b2
    L2 must be between a new bus from cn1 and b2
    SW1 must be between L1.bus_from and L2.bus_from
    SW2 must be in a self loop where both buses are b2
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [3, 4, 3, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 2, 4, 2]).all()
    assert np.equal(nc.generator_data.bus_idx, [2]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_G():
    """
    Topology test 4 Node G
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    # there are buses but some are not used (not referenced by the cn's)

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=None))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=None))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", cn_from=cn0, cn_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, cn_to=bb3.cn, active=False))

    l1 = grid.add_line(dev.Line(name="L1", cn_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    After processing,
    L1 must be between a new bus from cn0 and b2
    L2 must be between a new bus from cn1 and a new bus from cn3 (bb3)
    SW1 must be between L1.bus_from and L2.bus_from
    SW2 must be between L1.bus_to and L2.bus_to
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [3, 4, 3, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 5, 4, 5]).all()
    assert np.equal(nc.generator_data.bus_idx, [5]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_H():
    """
    Topology test 4 Node H
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    # there are buses but some are not used (not referenced by the cn's)

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=None))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=None))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", cn_from=cn0, cn_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, cn_to=bb3.cn, active=False))

    l1 = grid.add_line(dev.Line(name="L1", cn_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    After processing,
    L1 must be between a new bus from cn0 and b2
    L2 must be between a new bus from cn0 and a new bus from cn3 (bb3)
    SW1 must be between in a self loop at L1.bus_from
    SW2 must be between L1.bus_to and L2.bus_to
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [3, 3, 3, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 5, 3, 5]).all()
    assert np.equal(nc.generator_data.bus_idx, [5]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_A2():
    """
    Topology test 4 Node A2
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))
    b3 = grid.add_bus(dev.Bus(name="B3"))

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=b1))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))  # isolated

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, cn_from=cn0, cn_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=b3, cn_to=bb3.cn, active=False))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=b0, bus_to=b2, cn_from=cn0, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=b1, bus_to=b3, cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)  # isolated

    """
    In this test we are connecting to buses and CN,
    The topology algorithm is programmed to prefer existing buses to create new candidates from CN, 
    so if we happen to have cn and bus, no new candidate is created and the cn->bus association is made,
    if it wasn't there before
    Then, after processing,
    L1 must be between B0 and B2
    L2 must be between B0 and B3
    SW1 must be in a self-loop where both buses are B0
    SW2 must be connected between B2 and B3
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [0, 0, 0, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 3, 0, 3]).all()
    assert np.equal(nc.generator_data.bus_idx, [4]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_B2():
    """
    Topology test 4 Node B2
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))
    b3 = grid.add_bus(dev.Bus(name="B3"))

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=b1))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))  # isolated

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, cn_from=cn0, cn_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=b3, cn_to=bb3.cn, active=True))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=b0, bus_to=b2, cn_from=cn0, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=b1, bus_to=b3, cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)  # isolated

    """
    In this test we are connecting to buses and CN,
    The topology algorithm is programmed to prefer existing buses to create new candidates from CN, 
    so if we happen to have cn and bus, no new candidate is created and the cn->bus association is made,
    if it wasn't there before
    Then, after processing,
    L1 must be between B0 and B2
    L2 must be between B0 and B2
    SW1 must be in a self-loop where both buses are B0
    SW2 must be in a self-loop where both buses are B2
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [0, 0, 0, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 2, 0, 2]).all()
    assert np.equal(nc.generator_data.bus_idx, [4]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_C2():
    """
    Topology test 4 Node B2
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))
    b3 = grid.add_bus(dev.Bus(name="B3"))

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=b1))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, cn_from=cn0, cn_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=b3, cn_to=bb3.cn, active=True))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=b0, bus_to=b2, cn_from=cn0, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=b1, bus_to=b3, cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    In this test we are connecting to buses and CN,
    The topology algorithm is programmed to prefer existing buses to create new candidates from CN, 
    so if we happen to have cn and bus, no new candidate is created and the cn->bus association is made,
    if it wasn't there before
    Then, after processing,
    L1 must be between B0 and B2
    L2 must be between B1 and B2
    SW1 must be between B0 and B1
    SW2 must be in a self-loop where both buses are B2
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [0, 1, 0, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 2, 1, 2]).all()
    assert np.equal(nc.generator_data.bus_idx, [4]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_4_nodes_D2():
    """
    Topology test 4 Node B2
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))
    b3 = grid.add_bus(dev.Bus(name="B3"))

    cn0 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN0", default_bus=b0))
    cn1 = grid.add_connectivity_node(dev.ConnectivityNode(name="CN1", default_bus=b1))

    bb3 = grid.add_bus_bar(dev.BusBar(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, cn_from=cn0, cn_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=b3, cn_to=bb3.cn, active=False))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=b0, bus_to=b2, cn_from=cn0, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=b1, bus_to=b3, cn_from=cn1, cn_to=bb3.cn, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), cn=bb3.cn)

    """
    In this test we are connecting to buses and CN,
    The topology algorithm is programmed to prefer existing buses to create new candidates from CN, 
    so if we happen to have cn and bus, no new candidate is created and the cn->bus association is made,
    if it wasn't there before
    Then, after processing,
    L1 must be between B0 and B2
    L2 must be between B1 and B3
    SW1 must be between B0 and B1
    SW2 must be between B2 and B3
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.passive_branch_data.F, [0, 1, 0, 2]).all()
    assert np.equal(nc.passive_branch_data.T, [2, 3, 1, 3]).all()
    assert np.equal(nc.generator_data.bus_idx, [4]).all()
    assert np.equal(nc.load_data.bus_idx, [2]).all()


def test_topology_2_nodes_A1():
    """
    Topology test 2 Node A1
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, active=True))

    g1 = grid.add_generator(api_obj=dev.Generator(P=10), bus=b0)
    ld1 = grid.add_load(api_obj=dev.Load(P=10), bus=b1)

    """
    The switch is closed, hence B0 == B1
    the generator and the load must be connected to B0
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.generator_data.bus_idx, [0]).all()
    assert np.equal(nc.load_data.bus_idx, [0]).all()


def test_topology_2_nodes_A2():
    """
    Topology test 2 Node A2
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, active=False))
    grid.add_switch(sw1)

    g1 = grid.add_generator(api_obj=dev.Generator(P=10), bus=b0)
    ld1 = grid.add_load(api_obj=dev.Load(P=10), bus=b1)

    logger = Logger()
    tp_info = grid.process_topology_at(logger=logger)

    """
    The switch is open, the original buses must remain
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_topology()

    assert np.equal(nc.generator_data.bus_idx, [0]).all()
    assert np.equal(nc.load_data.bus_idx, [1]).all()


def test_topology_3_nodes_A1() -> None:
    """
    3 bus grid (closed switch)
    [bus0] __--__ [bus1] --- [bus2]
    [gen]                    [load]
    :return:
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, active=True))
    l1 = grid.add_line(dev.Line(name="L1", bus_from=b1, bus_to=b2, active=True))
    g1 = grid.add_generator(api_obj=dev.Generator(P=10), bus=b0)
    ld1 = grid.add_load(api_obj=dev.Load(P=10), bus=b2)

    res = power_flow(grid)

    assert res.voltage[2] != 0


def test_topology_3_nodes_A2() -> None:
    """
    3 bus grid (open switch)
    [bus0] __/ __ [bus1] --- [bus2]
    [gen]                    [load]
    :return:
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, active=False))
    l1 = grid.add_line(dev.Line(name="L1", bus_from=b1, bus_to=b2, active=True))
    g1 = grid.add_generator(api_obj=dev.Generator(P=10), bus=b0)
    ld1 = grid.add_load(api_obj=dev.Load(P=10), bus=b2)

    res = power_flow(grid)

    assert res.voltage[2] == 0


def test_nc_active_works() -> None:
    """
    This test checks that the failed branch by setting
    the numerical circuit active status
    has zero flow, for many power flow algorithms
    """
    fname = os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw')
    main_circuit = FileOpen(fname).open()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    for slv in [SolverType.DC, SolverType.LACPF,
                SolverType.NR, SolverType.LM, SolverType.PowellDogLeg, SolverType.IWAMOTO, SolverType.HELM,
                SolverType.FASTDECOUPLED, SolverType.GAUSS]:
        options = PowerFlowOptions(solver_type=slv)

        for k in range(nc.passive_branch_data.nelm):
            nc.passive_branch_data.active[k] = 0

            res = multi_island_pf_nc(nc=nc, options=options)

            assert res.Sf[k].real == 0.0
            assert res.Sf[k].imag == 0.0

            nc.passive_branch_data.active[k] = 1