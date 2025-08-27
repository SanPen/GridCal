# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

from scipy.sparse import lil_matrix
from VeraGridEngine.api import *
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.api import power_flow
from VeraGridEngine.Topology.topology import compute_connectivity_flexible
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc

def test_topology_4_nodes_A():
    """
    Topology test 4 Node A
    """
    grid = MultiCircuit()

    b0 = grid.add_bus(dev.Bus(name="B0"))
    b1 = grid.add_bus(dev.Bus(name="B1"))
    b2 = grid.add_bus(dev.Bus(name="B2"))

    cn0 = grid.add_bus(b0)
    cn1 = grid.add_bus(b1)

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=cn0, bus_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=bb3, active=False))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=cn1, bus_to=bb3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

    """
    After processing,
    branches: [L1, L2, SW1, SW2]
    L1 must be between B0 and B2
    L2 must be between B0 and a new bus that is not B0, B1 or B2
    SW1 must be in a self-loop where both buses are B0
    SW2 must be connected between B2 and the bus to of L2
    """
    nc = compile_numerical_circuit_at(grid)
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(b0)
    cn1 = grid.add_bus(b1)

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=cn0, bus_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=bb3, active=True))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=cn1, bus_to=bb3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

    """
    After processing,
    L1 must be between B0 and B2
    L2 must be between B0 and B2
    SW1 must be in a self-loop where both buses are B0
    SW2 must be in a self-loop where both buses are B2
    """
    nc = compile_numerical_circuit_at(grid)
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(b0)
    cn1 = grid.add_bus(b1)

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=cn0, bus_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=bb3, active=True))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=cn1, bus_to=bb3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

    """
    After processing,
    L1 must be between B0 and B2
    L2 must be between B1 and B2
    SW1 must be between B0 and B1
    SW2 must be in a self-loop where both buses are B2
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(b0)
    cn1 = grid.add_bus(b1)

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=cn0, bus_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=bb3, active=False))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=cn1, bus_to=bb3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

    """
    After processing,
    L1 must be between B0 and B2
    L2 must be between B1 and a new bus that is not b0, b1, b2 
    SW1 must be between B0 and B1
    SW2 must be between B2 and L2 bus_to
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(dev.Bus(name="CN0"))
    cn1 = grid.add_bus(dev.Bus(name="CN1"))

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=cn0, bus_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=bb3, active=True))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=cn1, bus_to=bb3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

    """
    After processing,
    L1 must be between a new bus from cn0 and b2
    L2 must be between a new bus from cn0 and b2
    SW1 must be in a self loop where both buses are L1.bus_from
    SW2 must be in a self loop where both buses are L1.bus_to / b2
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(dev.Bus(name="CN0"))
    cn1 = grid.add_bus(dev.Bus(name="CN1"))

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=cn0, bus_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=bb3, active=True))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=cn1, bus_to=bb3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

    """
    After processing,
    L1 must be between a new bus from cn0 and b2
    L2 must be between a new bus from cn1 and b2
    SW1 must be between L1.bus_from and L2.bus_from
    SW2 must be in a self loop where both buses are b2
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(dev.Bus(name="CN0"))
    cn1 = grid.add_bus(dev.Bus(name="CN1"))

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=cn0, bus_to=cn1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=bb3, active=False))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=cn1, bus_to=bb3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

    """
    After processing,
    L1 must be between a new bus from cn0 and b2
    L2 must be between a new bus from cn1 and a new bus from cn3 (bb3)
    SW1 must be between L1.bus_from and L2.bus_from
    SW2 must be between L1.bus_to and L2.bus_to
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(dev.Bus(name="CN0"))
    cn1 = grid.add_bus(dev.Bus(name="CN1"))

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=cn0, bus_to=cn1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=bb3, active=False))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=cn0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=cn1, bus_to=bb3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

    """
    After processing,
    L1 must be between a new bus from cn0 and b2
    L2 must be between a new bus from cn0 and a new bus from cn3 (bb3)
    SW1 must be between in a self loop at L1.bus_from
    SW2 must be between L1.bus_to and L2.bus_to
    """

    nc = compile_numerical_circuit_at(grid)
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(b0)
    cn1 = grid.add_bus(b1)

    bb3 = grid.add_bus(dev.Bus(name="BB3"))  # isolated

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=b3, active=False))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=b0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=b1, bus_to=b3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)  # isolated

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
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(b0)
    cn1 = grid.add_bus(b1)

    bb3 = grid.add_bus(dev.Bus(name="BB3"))  # isolated

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, active=True))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=b3, active=True))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=b0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=b1, bus_to=b3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)  # isolated

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
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(b0)
    cn1 = grid.add_bus(b1)

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=b3, active=True))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=b0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=b1, bus_to=b3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

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
    nc.process_reducible_branches()

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

    cn0 = grid.add_bus(b0)
    cn1 = grid.add_bus(b1)

    bb3 = grid.add_bus(dev.Bus(name="BB3"))

    sw1 = grid.add_switch(dev.Switch(name="SW1", bus_from=b0, bus_to=b1, active=False))
    sw2 = grid.add_switch(dev.Switch(name="SW2", bus_from=b2, bus_to=b3, active=False))

    l1 = grid.add_line(dev.Line(name="L1", bus_from=b0, bus_to=b2, x=0.05))
    l2 = grid.add_line(dev.Line(name="L2", bus_from=b1, bus_to=b3, x=0.01))

    grid.add_load(api_obj=dev.Load(P=10), bus=b2)
    grid.add_generator(api_obj=dev.Generator(P=10), bus=bb3)

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
    nc.process_reducible_branches()

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
    nc.process_reducible_branches()

    assert np.equal(nc.generator_data.bus_idx, [0]).all()
    assert np.equal(nc.load_data.bus_idx, [0]).all()


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

    for slv in [SolverType.Linear, SolverType.LACPF,
                SolverType.NR, SolverType.LM, SolverType.PowellDogLeg, SolverType.IWAMOTO, SolverType.HELM,
                SolverType.FASTDECOUPLED, SolverType.GAUSS]:
        options = PowerFlowOptions(solver_type=slv)

        for k in range(nc.passive_branch_data.nelm):
            nc.passive_branch_data.active[k] = 0

            res = multi_island_pf_nc(nc=nc, options=options)

            assert res.Sf[k].real == 0.0
            assert res.Sf[k].imag == 0.0

            nc.passive_branch_data.active[k] = 1


def test_adjacency_calc():
    """
    Compute the adjacency matrix
    :return: csc_matrix
    """

    fname = os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw')
    main_circuit = FileOpen(fname).open()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)
    consider_hvdc_as_island_links = True

    for b_idx in range(nc.bus_data.nbus):

        # set us state
        nc.bus_data.active[b_idx] = 0

        for br_idx in range(nc.passive_branch_data.nelm):

            # fail branch
            nc.passive_branch_data.active[br_idx] = 0

            # ----------------------------------------------------------------------------------------------------------
            conn_matrices = compute_connectivity_flexible(
                branch_active=nc.passive_branch_data.active,
                Cf_=nc.passive_branch_data.Cf.tocsc(),
                Ct_=nc.passive_branch_data.Ct.tocsc(),
                hvdc_active=nc.hvdc_data.active if consider_hvdc_as_island_links else None,
                Cf_hvdc=nc.hvdc_data.Cf.tocsc() if consider_hvdc_as_island_links else None,
                Ct_hvdc=nc.hvdc_data.Ct.tocsc() if consider_hvdc_as_island_links else None,
                vsc_active=nc.vsc_data.active,
                Cf_vsc=nc.vsc_data.Cf.tocsc(),
                Ct_vsc=nc.vsc_data.Ct.tocsc()
            )

            A1 = conn_matrices.get_adjacency(nc.bus_data.active)

            if consider_hvdc_as_island_links:
                structs = [nc.passive_branch_data, nc.vsc_data, nc.hvdc_data]
            else:
                structs = [nc.passive_branch_data, nc.vsc_data]

            # count the number of elements
            n_elm = sum([st.nelm for st in structs])

            mat2 = lil_matrix((nc.bus_data.nbus, nc.bus_data.nbus), dtype=int)
            for struct in structs:
                for k in range(struct.nelm):
                    f = struct.F[k]
                    t = struct.T[k]
                    if struct.active[k] and nc.bus_data.active[f] and nc.bus_data.active[t]:
                        mat2[f, f] += 1
                        mat2[f, t] += 1
                        mat2[t, f] += 1
                        mat2[t, t] += 1

            A2 = mat2.tocsc()

            mat3 = lil_matrix((n_elm, nc.bus_data.nbus), dtype=int)
            ii = 0
            for struct in structs:
                for k in range(struct.nelm):
                    f = struct.F[k]
                    t = struct.T[k]
                    if struct.active[k] and nc.bus_data.active[f] and nc.bus_data.active[t]:
                        mat3[ii, f] += 1
                        mat3[ii, t] += 1
                    ii += 1

            A3 = (mat3.T @ mat3).tocsc()

            assert np.allclose(A2.toarray(), A3.toarray())
            # assert np.allclose(A1.toarray(), A2.toarray())

            # ----------------------------------------------------------------------------------------------------------

            # revert state
            nc.passive_branch_data.active[br_idx] = 1

        # revert state
        nc.bus_data.active[b_idx] = 1


def get_lynn_5_bus() -> MultiCircuit:
    grid = MultiCircuit(name='lynn 5 bus')

    a1 = Area('Area1')
    z1 = Zone('Zone1')
    s1 = Substation('S1')

    grid.add_area(a1)
    grid.add_zone(z1)
    grid.add_substation(s1)

    ####################################################################################################################
    # Define the buses
    ####################################################################################################################
    # I will define this bus with all the properties so you see
    bus1 = Bus(name='Bus1',
               Vnom=10,  # Nominal voltage in kV
               vmin=0.9,  # Bus minimum voltage in per unit
               vmax=1.1,  # Bus maximum voltage in per unit
               xpos=0,  # Bus x position in pixels
               ypos=0,  # Bus y position in pixels
               height=0,  # Bus height in pixels
               width=0,  # Bus width in pixels
               active=True,  # Is the bus active?
               is_slack=False,  # Is this bus a slack bus?
               area=a1,  # Area (for grouping purposes only)
               zone=z1,  # Zone (for grouping purposes only)
               substation=s1  # Substation (for grouping purposes only)
               )

    # the rest of the buses are defined with the default parameters
    bus2 = Bus(name='Bus2')
    bus3 = Bus(name='Bus3')
    bus4 = Bus(name='Bus4')
    bus5 = Bus(name='Bus5')

    # add the bus objects to the circuit
    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    grid.add_bus(bus5)

    ####################################################################################################################
    # Add the loads
    ####################################################################################################################
    # In VeraGrid, the loads, generators ect are stored within each bus object:

    # we'll define the first load completely
    l2 = Load(name='Load',
              G=0,  # Impedance of the ZIP model in MVA at the nominal voltage
              B=0,
              Ir=0,
              Ii=0,  # Current of the ZIP model in MVA at the nominal voltage
              P=40,
              Q=20,  # Power of the ZIP model in MVA
              active=True,  # Is active?
              mttf=0.0,  # Mean time to failure
              mttr=0.0  # Mean time to recovery
              )
    grid.add_load(bus2, l2)

    # Define the others with the default parameters
    grid.add_load(bus3, Load(P=25, Q=15))
    grid.add_load(bus4, Load(P=40, Q=20))
    grid.add_load(bus5, Load(P=50, Q=20))

    ####################################################################################################################
    # Add the generators
    ####################################################################################################################

    g1 = Generator(name='gen',
                   P=0.0,  # Active power in MW, since this generator is used to set the slack , is 0
                   vset=1.0,  # Voltage set point to control
                   Qmin=-9999,  # minimum reactive power in MVAr
                   Qmax=9999,  # Maximum reactive power in MVAr
                   Snom=9999,  # Nominal power in MVA
                   active=True  # Is active?
                   )
    grid.add_generator(bus1, g1)

    ####################################################################################################################
    # Add the lines
    ####################################################################################################################

    br1 = Line(bus_from=bus1,
               bus_to=bus2,
               name='Line 1-2',
               r=0.05,  # resistance of the pi model in per unit
               x=0.11,  # reactance of the pi model in per unit
               b=0.02,  # susceptance of the pi model in per unit
               rate=50,  # Rate in MVA
               active=True,  # is the branch active?
               mttf=0,  # Mean time to failure
               mttr=0,  # Mean time to recovery
               length=1,  # Length in km (to be used with templates)
               )
    grid.add_line(br1)

    grid.add_line(Line(bus1, bus3, name='Line 1-3', r=0.05, x=0.11, b=0.02, rate=50))
    grid.add_line(Line(bus1, bus5, name='Line 1-5', r=0.03, x=0.08, b=0.02, rate=80))
    grid.add_line(Line(bus2, bus3, name='Line 2-3', r=0.04, x=0.09, b=0.02, rate=3))
    grid.add_line(Line(bus2, bus5, name='Line 2-5', r=0.04, x=0.09, b=0.02, rate=10))
    grid.add_line(Line(bus3, bus4, name='Line 3-4', r=0.06, x=0.13, b=0.03, rate=30))
    grid.add_line(Line(bus4, bus5, name='Line 4-5', r=0.04, x=0.09, b=0.02, rate=30))

    return grid


def test_lynn_Ybus():
    """

    :return:
    """
    fname = os.path.join('data', 'grids', 'lynn5node.gridcal')
    main_circuit = FileOpen(fname).open()

    # main_circuit = get_lynn_5_bus()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    adm = nc.get_admittance_matrices()

    Y = np.zeros((5, 5), dtype=complex)
    Y[0, 0] = 10.958904 - 25.997397j
    Y[0, 1] = -3.424658 + 7.534247j
    Y[0, 2] = -3.424658 + 7.534247j
    Y[0, 4] = -4.109589 + 10.958904j

    Y[1, 0] = -3.424658 + 7.534247j
    Y[1, 1] = 11.672080 - 26.060948j
    Y[1, 2] = -4.123711 + 9.278351j
    Y[1, 4] = -4.123711 + 9.278351j

    Y[2, 0] = -3.424658 + 7.534247j
    Y[2, 1] = -4.123711 + 9.278351j
    Y[2, 2] = 10.475198 - 23.119061j
    Y[2, 3] = -2.926829 + 6.341463j

    Y[3, 2] = -2.926829 + 6.341463j
    Y[3, 3] = 7.05041 - 15.594814j
    Y[3, 4] = -4.123711 + 9.278351j

    Y[4, 0] = -4.109589 + 10.958904j
    Y[4, 1] = -4.123711 + 9.278351j
    Y[4, 3] = -4.123711 + 9.278351j
    Y[4, 4] = 12.357012 - 29.485605j

    # print("\n\nY expected:\n", Y)
    # print("\n\n", adm.Ybus.toarray())

    assert np.allclose(adm.Ybus.toarray(), Y)


def test_lynn_Ybus2():
    """

    :return:
    """
    fname = os.path.join('data', 'grids', 'lynn5node.gridcal')
    main_circuit = FileOpen(fname).open()

    # main_circuit = get_lynn_5_bus()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    adm = nc.get_admittance_matrices()

    Y = np.zeros((5, 5), dtype=complex)
    # make by hand the matrices

    for k in range(nc.passive_branch_data.nelm):
        f = nc.passive_branch_data.F[k]
        t = nc.passive_branch_data.T[k]

        if nc.passive_branch_data.active[k]:
            ys = 1.0 / complex(nc.passive_branch_data.R[k], nc.passive_branch_data.X[k])
            bc2 = complex(nc.passive_branch_data.G[k], nc.passive_branch_data.B[k]) / 2.0

            Y[f, f] += ys + bc2
            Y[f, t] += - ys
            Y[t, f] += - ys
            Y[t, t] += ys + bc2

    print("\n\nY expected:\n", Y)
    print("\n\n", adm.Ybus.toarray())

    assert np.allclose(adm.Ybus.toarray(), Y)


def test_lynn_Ybus3() -> None:
    """
    This test randomly deactivates a number of branches and calculates Ybus
    manually and then the assembles Ybus from the possible islands local Ybuses and compares both
    :return:
    """
    fname = os.path.join('data', 'grids', 'lynn5node.gridcal')
    main_circuit = FileOpen(fname).open()

    # main_circuit = get_lynn_5_bus()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    m = nc.passive_branch_data.nelm
    for _ in range(m):
        print("-" * 200)
        cidx = np.unique(np.random.random_integers(0, m - 1, np.random.random_integers(1, m - 1, 1)))

        nc.passive_branch_data.active[cidx] = 0

        print("c_idx: ", cidx)

        # make by hand the matrices
        Y = np.zeros((5, 5), dtype=complex)
        for k in range(nc.passive_branch_data.nelm):
            f = nc.passive_branch_data.F[k]
            t = nc.passive_branch_data.T[k]

            if nc.passive_branch_data.active[k]:
                ys = 1.0 / complex(nc.passive_branch_data.R[k], nc.passive_branch_data.X[k])
                bc2 = complex(nc.passive_branch_data.G[k], nc.passive_branch_data.B[k]) / 2.0

                Y[f, f] += ys + bc2
                Y[f, t] += - ys
                Y[t, f] += - ys
                Y[t, t] += ys + bc2

        # Compose the matrix
        Y2 = np.zeros((5, 5), dtype=complex)
        islands = nc.split_into_islands()
        print("islands:", len(islands))
        for isl in islands:
            bus_idx = isl.bus_data.original_idx
            adm_i = isl.get_admittance_matrices()
            Y2[np.ix_(bus_idx, bus_idx)] = adm_i.Ybus.toarray()

        print("\n\nY expected:\n", Y)
        print("\n\n", Y2)

        assert np.allclose(Y2, Y)

        # revert the state
        nc.passive_branch_data.active[cidx] = 1


def lst_ok(lst1, lst2):
    """
    Check that list 1 and 2 are equal, although ot checking the order
    :param lst1:
    :param lst2:
    :return:
    """
    if len(lst1) != len(lst2):
        return False
    else:
        for a in lst1:
            if a not in lst2:
                return False

        return True


def test_island_slicing():
    """
    This tests checks that things are properly sliced
    """
    fname = os.path.join('data', 'grids', '8_nodes_2_islands.gridcal')
    main_circuit = FileOpen(fname).open()

    # main_circuit = get_lynn_5_bus()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    islands = nc.split_into_islands()

    assert len(islands) == 2

    assert lst_ok(islands[0].bus_data.names, ['Bus 1', 'Bus 2', 'Bus 3', 'Bus 4'])
    assert lst_ok(islands[0].passive_branch_data.names, ['L1', 'L2', 'L3', 'L4'])
    assert lst_ok(islands[0].load_data.names, ['LD1', 'LD2', 'LD3'])
    assert lst_ok(islands[0].generator_data.names, ['G1', 'G2'])

    assert lst_ok(islands[1].bus_data.names, ['Bus 11', 'Bus 22', 'Bus 33', 'Bus 44'])
    assert lst_ok(islands[1].passive_branch_data.names, ['L5', 'L6', 'L7', 'L8'])
    assert lst_ok(islands[1].load_data.names, ['LD4', 'LD5', 'LD6', 'LD7'])
    assert lst_ok(islands[1].generator_data.names, ['G3', 'G4'])


def test_segmenting_by_hvdc():
    fname = os.path.join('data', 'grids', '8_nodes_2_islands_hvdc.gridcal')

    grid = open_file(fname)

    nc = compile_numerical_circuit_at(
        grid,
        t_idx=None,
        apply_temperature=False,
        branch_tolerance_mode=BranchImpedanceMode.Specified,
        opf_results=None,
        use_stored_guess=False,
        bus_dict=None,
        areas_dict=None,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
    )

    islands_1 = nc.split_into_islands(consider_hvdc_as_island_links=True)

    assert len(islands_1) == 1

    islands_1 = nc.split_into_islands(consider_hvdc_as_island_links=False)

    assert len(islands_1) == 2
