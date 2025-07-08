# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.multi_circuit import MultiCircuit


def simple_bar(name, grid: MultiCircuit, n_lines: int, n_gen: int):
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_gen:
    :return:
    """
    bar = dev.Bus(f"{name} bar")
    # busbar = dev.BusBar(f"{name} bar")

    for i in range(n_lines):

        bus1 = dev.Bus(f"{name}_line_conn_{i}")
        bus2 = dev.Bus(f"LineBus2_{i}")
        bus3 = dev.Bus(f"LIneBus3_{i}")
        sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
        sw1 = dev.Switch(name=f"SW_{i}",bus_from=bus2, bus_to=bus3)
        sec2 = dev.Switch(name=f"Sec2_{i}",bus_from=bus3, bus_to=bar)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_bus(bus3)
        grid.add_switch(sec1)
        grid.add_switch(sw1)
        grid.add_switch(sec2)

    for i in range(n_gen):

        bus1 = dev.Bus(f"{name}_gen_conn_{i}")
        bus2 = dev.Bus(f"gen2_{i}")
        sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
        sw1 = dev.Switch(name=f"SW_{i}",bus_from=bus2, bus_to=bar)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_switch(sec1)
        grid.add_switch(sw1)