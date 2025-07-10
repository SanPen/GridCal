# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import GridCalEngine.Devices as dev
from GridCalEngine import Country
from GridCalEngine.Devices.multi_circuit import MultiCircuit


def simple_bar(name, grid: MultiCircuit, n_lines: int, n_trafo: int, v_nom: float,
               lat: float | None = None, lon: float | None = None, country: Country = None,
               include_disconnectors: bool = True):
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_trafo:
    :param v_nom:
    :param lat:
    :param lon:
    :param country:
    :param include_disconnectors:
    :return:
    """

    substation = dev.Substation(name=name, latitude=lat, longitude=lon, country=country)
    grid.add_substation(substation)

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    dist = 300
    bus_width = 100

    bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                  width=max(n_lines, n_trafo) * bus_width + bus_width * 2 + (dist * 2 - bus_width) * (
                          max(n_lines, n_trafo) - 1),
                  xpos=-bus_width, ypos=dist * 3, country=country)
    grid.add_bus(bar)
    # busbar = dev.BusBar(f"{name} bar")

    if include_disconnectors:

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * dist * 2, ypos=0, width=bus_width, country=country)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * dist * 2, ypos=dist, width=bus_width, country=country)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * dist * 2, ypos=dist * 2, width=bus_width, country=country)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus3)
            sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bus3, bus_to=bar)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(sec1)
            grid.add_switch(sw1)
            grid.add_switch(sec2)

        for i in range(n_trafo):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=abs(n_lines - n_trafo) * dist * 2 + i * dist * 2, ypos=dist * 5, width=bus_width,
                           country=country)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=abs(n_lines - n_trafo) * dist * 2 + i * dist * 2, ypos=dist * 4, width=bus_width,
                           country=country)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus1)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(sec1)
            grid.add_switch(sw1)

    else:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * dist * 2, ypos=dist * 2, width=bus_width, country=country)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bar)

            grid.add_bus(bus1)
            grid.add_switch(sw1)

        for i in range(n_trafo):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=abs(n_lines - n_trafo) * dist * 2 + i * dist * 2, ypos=dist * 4, width=bus_width,
                           country=country)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bar, bus_to=bus1)

            grid.add_bus(bus1)
            grid.add_switch(sw1)


def simple_bar_with_bypass(name, grid: MultiCircuit, n_lines: int, n_trafo: int, v_nom,
                           lat: float | None = None, lon: float | None = None, country: Country = None,
                           include_disconnectors: bool = True):
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_trafo:
    :return:
    """

    substation = dev.Substation(name=name, latitude=lat, longitude=lon, country=country)
    grid.add_substation(substation)

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    dist = 300
    bus_width = 100

    bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                  width=max(n_lines, n_trafo) * bus_width + bus_width * 2 + (dist * 2 - bus_width) * (
                          max(n_lines, n_trafo) - 1),
                  xpos=-bus_width, ypos=dist * 3, country=country)
    grid.add_bus(bar)

    for i in range(n_lines):
        bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=0 + i * dist * 1.5, ypos=0, width=bus_width*3, country=country)
        bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=0 + i * dist * 1.5, ypos=dist, width=bus_width, country=country)
        bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=0 + i * dist * 1.5, ypos=dist * 2, width=bus_width, country=country)
        sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
        sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus3)
        sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bus3, bus_to=bar)
        sec3 = dev.Switch(name=f"Sec3_{i}", bus_from=bus1, bus_to=bar)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_bus(bus3)
        grid.add_switch(sec1)
        grid.add_switch(sw1)
        grid.add_switch(sec2)
        grid.add_switch(sec3)

    for i in range(n_trafo):
        bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=abs(n_lines - n_trafo) * dist * 1.5 + i * dist * 1.5, ypos=dist * 5, width=bus_width*3,
                       country=country)
        bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=abs(n_lines - n_trafo) * dist * 1.5 + i * dist * 1.5, ypos=dist * 4, width=bus_width,
                       country=country)
        sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar, bus_to=bus2)
        sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus1)
        sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bus1, bus_to=bar)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_switch(sec1)
        grid.add_switch(sw1)
        grid.add_switch(sec2)


def simple_split_bars(name, grid: MultiCircuit, n_lines: int, n_trafo: int):
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_trafo:
    :return:
    """

    pass


def double_bar(name, grid: MultiCircuit, n_lines: int, n_trafo: int):
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_trafo:
    :return:
    """

    bar1 = dev.Bus(f"{name} bar1")
    bar2 = dev.Bus(f"{name} bar2")

    for i in range(n_lines):
        bus1 = dev.Bus(f"{name}_line_conn_{i}")
        bus2 = dev.Bus(f"LineBus2_{i}")
        bus3 = dev.Bus(f"LineBus3_{i}")
        sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
        sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus3)
        sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bus3, bus_to=bar1)
        sec3 = dev.Switch(name=f"Sec3_{i}", bus_from=bus3, bus_to=bar2)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_bus(bus3)
        grid.add_switch(sec1)
        grid.add_switch(sw1)
        grid.add_switch(sec2)
        grid.add_switch(sec3)

    for i in range(n_trafo):
        bus1 = dev.Bus(f"{name}_trafo_conn_{i}")
        bus2 = dev.Bus(f"trafo2_{i}")
        sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar1, bus_to=bus1)
        sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bar2, bus_to=bus1)
        sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bus2)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_switch(sec1)
        grid.add_switch(sec2)
        grid.add_switch(sw1)

    # coupling

    bus1 = dev.Bus(f"{name}_coupling_bar1")
    bus2 = dev.Bus(f"{name}_coupling_bar2")
    sec1 = dev.Switch(name="Sec_bar1", bus_from=bar1, bus_to=bus1)
    sec2 = dev.Switch(name="Sec_bar2", bus_from=bar2, bus_to=bus2)
    sw1 = dev.Switch(name="SW_coupling", bus_from=bus1, bus_to=bus2)

    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_switch(sec1)
    grid.add_switch(sec2)
    grid.add_switch(sw1)


def double_bar_with_transfer_bar(name, grid: MultiCircuit, n_lines: int, n_trafo: int):
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_trafo:
    :return:
    """

    bar1 = dev.Bus(f"{name} bar1")
    bar2 = dev.Bus(f"{name} bar2")
    transfer_bar = dev.Bus(f"{name}_transfer_bar")

    for i in range(n_lines):
        bus1 = dev.Bus(f"{name}_line_conn_{i}")
        bus2 = dev.Bus(f"LineBus2_{i}")
        bus3 = dev.Bus(f"LineBus3_{i}")
        sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
        sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus3)
        sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bus3, bus_to=bar1)
        sec3 = dev.Switch(name=f"Sec3_{i}", bus_from=bus3, bus_to=bar2)
        sec4 = dev.Switch(name=f"Sec4_{i}", bus_from=bus1, bus_to=transfer_bar)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_bus(bus3)
        grid.add_switch(sec1)
        grid.add_switch(sw1)
        grid.add_switch(sec2)
        grid.add_switch(sec3)
        grid.add_switch(sec4)

    for i in range(n_trafo):
        bus1 = dev.Bus(f"{name}_trafo_conn_{i}")
        bus2 = dev.Bus(f"trafo2_{i}")
        sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar1, bus_to=bus1)
        sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bar2, bus_to=bus1)
        sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bus2)
        sec3 = dev.Switch(name=f"Sec3_{i}", bus_from=transfer_bar, bus_to=bus2)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_switch(sec1)
        grid.add_switch(sec2)
        grid.add_switch(sw1)
        grid.add_switch(sec3)

    # coupling

    bus1 = dev.Bus(f"{name}_coupling_bus1")
    bus2 = dev.Bus(f"{name}_coupling_bus2")
    sec1 = dev.Switch(name="Sec_bar1", bus_from=bar1, bus_to=bus1)
    sec2 = dev.Switch(name="Sec_bar2", bus_from=bar2, bus_to=bus1)
    sw1 = dev.Switch(name="SW_coupling", bus_from=bus1, bus_to=bus2)
    sec3 = dev.Switch(name="Sec_transfer_bar", bus_from=bus2, bus_to=transfer_bar)

    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_switch(sec1)
    grid.add_switch(sec2)
    grid.add_switch(sw1)
    grid.add_switch(sec3)
