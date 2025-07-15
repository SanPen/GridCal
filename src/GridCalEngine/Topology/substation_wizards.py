# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from pandas.core.nanops import set_use_bottleneck

import GridCalEngine.Devices as dev
from GridCalEngine import Country, BusGraphicType
from GridCalEngine.Devices.multi_circuit import MultiCircuit


def simple_bar(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
               lat: float | None = None, lon: float | None = None, country: Country = None,
               include_disconnectors: bool = True):
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_trafos:
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

    bus_width = 120
    x_dist = bus_width*2
    y_dist = bus_width*1.5

    bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                  width=max(n_lines, n_trafos) * bus_width + bus_width * 2 + (x_dist - bus_width) * (max(n_lines, n_trafos) - 1),
                  xpos=-bus_width, ypos=y_dist * 3, country=country)
    grid.add_bus(bar)
    # busbar = dev.BusBar(f"{name} bar")

    if include_disconnectors:

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=0, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus3)
            sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bar, bus_to=bus3)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(sec1)
            grid.add_switch(sw1)
            grid.add_switch(sec2)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 4, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bus2)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(sec1)
            grid.add_switch(sw1)

    else:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bar)

            grid.add_bus(bus1)
            grid.add_switch(sw1)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 4, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bar, bus_to=bus1)

            grid.add_bus(bus1)
            grid.add_switch(sw1)


def simple_bar_with_bypass(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
                           lat: float | None = None, lon: float | None = None, country: Country = None,
                           include_disconnectors: bool = True):
    """
    :param name:
    :param grid:
    :param n_lines:
    :param n_trafos:
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

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5

    bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                  width=max(n_lines, n_trafos) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
                          max(n_lines, n_trafos) - 1),
                  xpos=-bus_width, ypos=y_dist * 3, country=country)
    grid.add_bus(bar)

    if include_disconnectors:

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=0, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
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

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 5, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 4, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus1)
            sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bus1, bus_to=bar)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(sec1)
            grid.add_switch(sw1)
            grid.add_switch(sec2)
    else:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bar)
            sec3 = dev.Switch(name=f"Sec_{i}", bus_from=bus1, bus_to=bar)

            grid.add_bus(bus1)
            grid.add_switch(sw1)
            grid.add_switch(sec3)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 4, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bar, bus_to=bus1)
            sec2 = dev.Switch(name=f"Sec_{i}", bus_from=bus1, bus_to=bar)

            grid.add_bus(bus1)
            grid.add_switch(sw1)
            grid.add_switch(sec2)


def simple_split_bars(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
                           lat: float | None = None, lon: float | None = None, country: Country = None,
                           include_disconnectors: bool = True):
    """
    :param name:
    :param grid:
    :param n_lines:
    :param n_trafos:
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

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5
    bar_2_x_offset = bus_width * 1.2
    bar_2_y_offset = bus_width * 1.2

    n_lines_bar_1 = n_lines//2
    n_trafos_bar_1 = n_trafos//2
    n_lines_bar_2 = n_lines - n_lines_bar_1
    n_trafos_bar_2 = n_trafos - n_trafos_bar_1

    width_bar_1 = max(n_lines_bar_1, n_trafos_bar_1) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
                      max(n_lines_bar_1, n_trafos_bar_1) - 1)
    width_bar_2 = max(n_lines_bar_2, n_trafos_bar_2) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
        max(n_lines_bar_2, n_trafos_bar_2) - 1)

    bar1 = dev.Bus(f"{name} bar 1", substation=substation, Vnom=v_nom, voltage_level=vl,
                  width=width_bar_1, xpos=-bus_width, ypos=y_dist * 3, country=country)
    grid.add_bus(bar1)

    bar2 = dev.Bus(f"{name} bar 2", substation=substation, Vnom=v_nom, voltage_level=vl,
                   width=width_bar_2, xpos=width_bar_1 + bar_2_x_offset, ypos=y_dist * 3 + bar_2_y_offset,
                   country=country)
    grid.add_bus(bar2)

    sw_bars = dev.Switch(name=f"SW_bars", bus_from=bar1, bus_to=bar2)
    grid.add_switch(sw_bars)

    if include_disconnectors:

        for i in range(n_lines):
            if i < n_lines_bar_1:
                bar = bar1
                x_offset = 0
                y_offset = 0
            else:
                bar = bar2
                x_offset = bar_2_x_offset + 2*bus_width
                y_offset = bar_2_y_offset

            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_offset, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist + y_offset, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist * 2 + y_offset, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus3)
            sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bar, bus_to=bus3)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(sec1)
            grid.add_switch(sw1)
            grid.add_switch(sec2)

        for i in range(n_trafos):
            if i < n_trafos_bar_1:
                bar = bar1
                x_offset = 0
                y_offset = 0
            else:
                bar = bar2
                x_offset = bar_2_x_offset + 2*bus_width
                y_offset = bar_2_y_offset

            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist * 5 + y_offset, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist * 4 + y_offset, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bus2)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(sec1)
            grid.add_switch(sw1)
    else:
        for i in range(n_lines):
            if i < n_lines_bar_1:
                bar = bar1
                x_offset = 0
                y_offset = 0
            else:
                bar = bar2
                x_offset = bar_2_x_offset + 2 * bus_width
                y_offset = bar_2_y_offset

            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist*2 + y_offset, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bar, bus_to=bus1)

            grid.add_bus(bus1)
            grid.add_switch(sw1)

        for i in range(n_trafos):
            if i < n_trafos_bar_1:
                bar = bar1
                x_offset = 0
                y_offset = 0
            else:
                bar = bar2
                x_offset = bar_2_x_offset + 2 * bus_width
                y_offset = bar_2_y_offset

            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist * 4 + y_offset, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bar, bus_to=bus1)

            grid.add_bus(bus1)
            grid.add_switch(sw1)


def double_bar(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
                           lat: float | None = None, lon: float | None = None, country: Country = None,
                           include_disconnectors: bool = True):
    """
    :param name:
    :param grid:
    :param n_lines:
    :param n_trafos:
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

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5

    bar1 = dev.Bus(f"{name} bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                   width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 2 + (x_dist - bus_width) * max(n_lines, n_trafos),
                   xpos=-bus_width, ypos=y_dist*3, country=country)
    grid.add_bus(bar1)

    bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                   width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 2 + (x_dist - bus_width) * max(n_lines, n_trafos),
                   xpos=-bus_width, ypos=y_dist*4, country=country)
    grid.add_bus(bar2)

    if include_disconnectors:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                               xpos=0 + i * x_dist, ypos=0, width=bus_width, country=country,
                               graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bus1, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus2, bus_to=bus3)
            sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bar1, bus_to=bus3)
            sec3 = dev.Switch(name=f"Sec3_{i}", bus_from=bar2, bus_to=bus3)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(sec1)
            grid.add_switch(sw1)
            grid.add_switch(sec2)
            grid.add_switch(sec3)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar1, bus_to=bus2)
            sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bar2, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bus2)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(sec1)
            grid.add_switch(sec2)
            grid.add_switch(sw1)

        # coupling

        bus1 = dev.Bus(f"{name}_coupling_bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos)*x_dist, ypos=y_dist*3.5, width=0, country=country,
                       graphic_type=BusGraphicType.Connectivity)
        bus2 = dev.Bus(f"{name}_coupling_bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos)*x_dist+x_dist*0.5, ypos=y_dist*3.5, width=0, country=country,
                       graphic_type=BusGraphicType.Connectivity)
        sec1 = dev.Switch(name="Sec_bar1", bus_from=bar1, bus_to=bus1)
        sec2 = dev.Switch(name="Sec_bar2", bus_from=bar2, bus_to=bus2)
        sw1 = dev.Switch(name="SW_coupling", bus_from=bus1, bus_to=bus2)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_switch(sec1)
        grid.add_switch(sec2)
        grid.add_switch(sw1)

    else:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist*2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bus2)
            sec1 = dev.Switch(name=f"Sec2_{i}", bus_from=bar1, bus_to=bus2)
            sec2 = dev.Switch(name=f"Sec3_{i}", bus_from=bar2, bus_to=bus2)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(sw1)
            grid.add_switch(sec1)
            grid.add_switch(sec2)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            sec1 = dev.Switch(name=f"Sec1_{i}", bus_from=bar1, bus_to=bus2)
            sec2 = dev.Switch(name=f"Sec2_{i}", bus_from=bar2, bus_to=bus2)
            sw1 = dev.Switch(name=f"SW_{i}", bus_from=bus1, bus_to=bus2)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(sec1)
            grid.add_switch(sec2)
            grid.add_switch(sw1)

        # coupling

        bus1 = dev.Bus(f"{name}_coupling_bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos) * x_dist, ypos=y_dist * 3.5, width=0, country=country,
                       graphic_type=BusGraphicType.Connectivity)
        bus2 = dev.Bus(f"{name}_coupling_bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos) * x_dist + x_dist * 0.5, ypos=y_dist * 3.5, width=0, country=country,
                       graphic_type=BusGraphicType.Connectivity)
        sec1 = dev.Switch(name="Sec_bar1", bus_from=bar1, bus_to=bus1)
        sec2 = dev.Switch(name="Sec_bar2", bus_from=bar2, bus_to=bus2)
        sw1 = dev.Switch(name="SW_coupling", bus_from=bus1, bus_to=bus2)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_switch(sec1)
        grid.add_switch(sec2)
        grid.add_switch(sw1)


def double_bar_with_transfer_bar(name, grid: MultiCircuit, n_lines: int, n_trafos: int):
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_trafos:
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

    for i in range(n_trafos):
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
