# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import numpy as np

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices import Bus
from VeraGridEngine.Devices import Generator
from VeraGridEngine.Devices import Load
from VeraGridEngine.Devices import Line
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions, PowerFlowDriver


def test_demo_5_node():

    grid = MultiCircuit()

    # Add buses
    bus1 = Bus('Bus 1', Vnom=20)
    grid.add_bus(bus1)
    gen1 = Generator('Slack Generator', vset=1.0)
    grid.add_generator(bus1, gen1)

    bus2 = Bus('Bus 2', Vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, Load('load 2', P=40, Q=20))

    bus3 = Bus('Bus 3', Vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, Load('load 3', P=25, Q=15))

    bus4 = Bus('Bus 4', Vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, Load('load 4', P=40, Q=20))

    bus5 = Bus('Bus 5', Vnom=20)
    grid.add_bus(bus5)
    grid.add_load(bus5, Load('load 5', P=50, Q=20))

    # add Branches (Lines in this case)
    grid.add_line(Line(bus1, bus2, name='line 1-2', r=0.05, x=0.11, b=0.02))
    grid.add_line(Line(bus1, bus3, name='line 1-3', r=0.05, x=0.11, b=0.02))
    grid.add_line(Line(bus1, bus5, name='line 1-5', r=0.03, x=0.08, b=0.02))
    grid.add_line(Line(bus2, bus3, name='line 2-3', r=0.04, x=0.09, b=0.02))
    grid.add_line(Line(bus2, bus5, name='line 2-5', r=0.04, x=0.09, b=0.02))
    grid.add_line(Line(bus3, bus4, name='line 3-4', r=0.06, x=0.13, b=0.03))
    grid.add_line(Line(bus4, bus5, name='line 4-5', r=0.04, x=0.09, b=0.02))
    # grid.plot_graph()
    print('\n\n', grid.name)

    # FileSave(grid, 'demo_5_node.json').save()

    options = PowerFlowOptions(SolverType.NR, verbose=False)

    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    v = np.array([1., 0.9553, 0.9548, 0.9334, 0.9534])
    all_ok = np.isclose(np.abs(power_flow.results.voltage), v, atol=1e-3)
    return all_ok


