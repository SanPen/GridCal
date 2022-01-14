GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

import numpy as np

from GridCal.Engine.IO.file_handler import FileSave
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices.branch import Branch
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.generator import Generator
from GridCal.Engine.Devices.load import Load
from GridCal.Engine.Devices.line import Line
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions, PowerFlowDriver
from tests.print_power_flow_results import print_power_flow_results
from tests.conftest import ROOT_PATH


def test_demo_5_node(root_path=ROOT_PATH):
    np.core.arrayprint.set_printoptions(precision=4)

    grid = MultiCircuit()

    # Add buses
    bus1 = Bus('Bus 1', vnom=20)
    grid.add_bus(bus1)
    gen1 = Generator('Slack Generator', voltage_module=1.0)
    grid.add_generator(bus1, gen1)

    bus2 = Bus('Bus 2', vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, Load('load 2', P=40, Q=20))

    bus3 = Bus('Bus 3', vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, Load('load 3', P=25, Q=15))

    bus4 = Bus('Bus 4', vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, Load('load 4', P=40, Q=20))

    bus5 = Bus('Bus 5', vnom=20)
    grid.add_bus(bus5)
    grid.add_load(bus5, Load('load 5', P=50, Q=20))

    # add branches (Lines in this case)
    grid.add_line(Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.02))
    grid.add_line(Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.02))
    grid.add_line(Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.02))
    grid.add_line(Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.02))
    grid.add_line(Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.02))
    grid.add_line(Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.03))
    grid.add_line(Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02))
    # grid.plot_graph()
    print('\n\n', grid.name)

    FileSave(grid, 'demo_5_node.json').save()

    options = PowerFlowOptions(SolverType.NR, verbose=False)

    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    print_power_flow_results(power_flow=power_flow)
    v = np.array([1., 0.9553, 0.9548, 0.9334, 0.9534])
    all_ok = np.isclose(np.abs(power_flow.results.voltage), v, atol=1e-3)
    return all_ok


if __name__ == '__main__':
    test_demo_5_node(root_path=ROOT_PATH)
