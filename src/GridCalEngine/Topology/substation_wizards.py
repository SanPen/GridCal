# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple
import GridCalEngine.Devices as dev
from GridCalEngine import Country, BusGraphicType, SwitchGraphicType
from GridCalEngine.Devices.multi_circuit import MultiCircuit


def create_single_bar(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
                      substation: dev.Substation, country: Country = None,
                      include_disconnectors: bool = True,
                      offset_x=0, offset_y=0) -> Tuple[dev.VoltageLevel, int, int]:
    """

    :param name:
    :param grid:
    :param n_lines:
    :param n_trafos:
    :param v_nom:
    :param substation:
    :param country:
    :param include_disconnectors:
    :return:
    """
    offset_inc_x = 0
    offset_inc_y = 0
    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5

    bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                  width=max(n_lines, n_trafos) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
                          max(n_lines, n_trafos) - 1),
                  xpos=-bus_width, ypos=y_dist * 3, country=country, graphic_type=BusGraphicType.BusBar)
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
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 4, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(dis1)
            grid.add_switch(cb1)

    else:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            grid.add_switch(cb1)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 4, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            grid.add_switch(cb1)

    return vl, offset_inc_x, offset_inc_y


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
                  xpos=-bus_width, ypos=y_dist * 3, country=country, graphic_type=BusGraphicType.BusBar)
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
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus3, bus_to=bar, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)
            grid.add_switch(dis3)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 5, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 4, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)
    else:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis3 = dev.Switch(name=f"Dis_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_switch(cb1)
            grid.add_switch(dis3)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 4, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)


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

    n_lines_bar_1 = n_lines // 2
    n_trafos_bar_1 = n_trafos // 2
    n_lines_bar_2 = n_lines - n_lines_bar_1
    n_trafos_bar_2 = n_trafos - n_trafos_bar_1

    width_bar_1 = max(n_lines_bar_1, n_trafos_bar_1) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
            max(n_lines_bar_1, n_trafos_bar_1) - 1)
    width_bar_2 = max(n_lines_bar_2, n_trafos_bar_2) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
            max(n_lines_bar_2, n_trafos_bar_2) - 1)

    bar1 = dev.Bus(f"{name} bar 1", substation=substation, Vnom=v_nom, voltage_level=vl,
                   width=width_bar_1, xpos=-bus_width, ypos=y_dist * 3, country=country,
                   graphic_type=BusGraphicType.BusBar)
    grid.add_bus(bar1)

    bar2 = dev.Bus(f"{name} bar 2", substation=substation, Vnom=v_nom, voltage_level=vl,
                   width=width_bar_2, xpos=width_bar_1 + bar_2_x_offset, ypos=y_dist * 3 + bar_2_y_offset,
                   country=country, graphic_type=BusGraphicType.BusBar)
    grid.add_bus(bar2)

    cb_bars = dev.Switch(name=f"CB_bars", bus_from=bar1, bus_to=bar2, graphic_type=SwitchGraphicType.CircuitBreaker)
    grid.add_switch(cb_bars)

    if include_disconnectors:

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
                           xpos=i * x_dist + x_offset, ypos=y_offset, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist + y_offset, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist * 2 + y_offset, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)

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
                           xpos=i * x_dist + x_offset, ypos=y_dist * 5 + y_offset, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_offset, ypos=y_dist * 4 + y_offset, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(dis1)
            grid.add_switch(cb1)
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
                           xpos=i * x_dist + x_offset, ypos=y_dist * 2 + y_offset, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            grid.add_switch(cb1)

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
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            grid.add_switch(cb1)


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
                   width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 2 + (x_dist - bus_width) * max(n_lines,
                                                                                                               n_trafos),
                   xpos=-bus_width, ypos=y_dist * 3, country=country, graphic_type=BusGraphicType.BusBar)
    grid.add_bus(bar1)

    bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                   width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 2 + (x_dist - bus_width) * max(n_lines,
                                                                                                               n_trafos),
                   xpos=-bus_width, ypos=y_dist * 4, country=country, graphic_type=BusGraphicType.BusBar)
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
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar1, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bar2, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)
            grid.add_switch(dis3)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar2, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(dis1)
            grid.add_switch(dis2)
            grid.add_switch(cb1)

        # coupling
        bus1 = dev.Bus(f"{name}_coupling_bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos) * x_dist, ypos=y_dist * 3.6, width=bus_width, country=country,
                       graphic_type=BusGraphicType.Connectivity)
        bus2 = dev.Bus(f"{name}_coupling_bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos) * x_dist + x_dist * 0.5, ypos=y_dist * 3.6, width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        dis1 = dev.Switch(name="Dis_bar1", bus_from=bar1, bus_to=bus1, graphic_type=SwitchGraphicType.Disconnector)
        dis2 = dev.Switch(name="Dis_bar2", bus_from=bar2, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
        cb1 = dev.Switch(name="CB_coupling", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_switch(dis1)  # this disconnectors must be included to respect the SE geometry
        grid.add_switch(dis2)  # this disconnectors must be included to respect the SE geometry
        grid.add_switch(cb1)

    else:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=0 + i * x_dist, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis1 = dev.Switch(name=f"Dis2_{i}", bus_from=bar1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis3_{i}", bus_from=bar2, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(cb1)
            grid.add_switch(dis1)  # this disconnectors must be included to respect the SE geometry
            grid.add_switch(dis2)  # this disconnectors must be included to respect the SE geometry

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar2, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(dis1)  # this disconnectors must be included to respect the SE geometry
            grid.add_switch(dis2)  # this disconnectors must be included to respect the SE geometry
            grid.add_switch(cb1)

        # coupling
        cb1 = dev.Switch(name="CB_coupling", bus_from=bar1, bus_to=bar2, graphic_type=SwitchGraphicType.CircuitBreaker)
        grid.add_switch(cb1)


def double_bar_with_transfer_bar(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
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
                   width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (x_dist - bus_width) * max(n_lines,
                                                                                                               n_trafos),
                   xpos=-bus_width, ypos=y_dist * 3, country=country, graphic_type=BusGraphicType.BusBar)
    grid.add_bus(bar1)

    bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                   width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (x_dist - bus_width) * max(n_lines,
                                                                                                               n_trafos),
                   xpos=-bus_width, ypos=y_dist * 4, country=country, graphic_type=BusGraphicType.BusBar)
    grid.add_bus(bar2)

    transfer_bar = dev.Bus(f"{name} transfer bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                           width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (x_dist - bus_width) * max(
                               n_lines,
                               n_trafos),
                           xpos=-bus_width, ypos=y_dist * 5, country=country, graphic_type=BusGraphicType.BusBar)
    grid.add_bus(transfer_bar)

    if include_disconnectors:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_dist * 0.2, ypos=0, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - x_dist * 0.25, ypos=y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - x_dist * 0.25, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar1, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bar2, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)
            dis4 = dev.Switch(name=f"Dis4_{i}", bus_from=bus1, bus_to=transfer_bar,
                              graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)
            grid.add_switch(dis3)
            grid.add_switch(dis4)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 8, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 7, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"trafo3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus3, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bus3, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
            dis4 = dev.Switch(name=f"Dis4_{i}", bus_from=bus1, bus_to=transfer_bar,
                              graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_switch(dis1)
            grid.add_switch(dis2)
            grid.add_switch(cb1)
            grid.add_switch(dis3)
            grid.add_switch(dis4)

        # coupling
        bus1 = dev.Bus(f"{name}_coupling_bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos) * x_dist + x_dist * 0.25, ypos=y_dist * 3.6, width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        bus2 = dev.Bus(f"{name}_coupling_bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos) * x_dist + x_dist * 0.25, ypos=y_dist * 4.6, width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        dis1 = dev.Switch(name="Dis_bar1", bus_from=bus1, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
        dis2 = dev.Switch(name="Dis_bar2", bus_from=bus1, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
        cb1 = dev.Switch(name="CB_coupling", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
        dis3 = dev.Switch(name="Dis_coupling", bus_from=bus2, bus_to=transfer_bar,
                          graphic_type=SwitchGraphicType.Disconnector)

        grid.add_bus(bus1)
        grid.add_bus(bus2)
        grid.add_switch(dis1)
        grid.add_switch(dis2)
        grid.add_switch(cb1)
        grid.add_switch(dis3)

    else:
        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist + x_dist * 0.1, ypos=y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - x_dist * 0.1, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus2, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus2, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bus1, bus_to=transfer_bar,
                              graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(cb1)
            grid.add_switch(dis1)  # this disconnector must be included to respect the SE geometry
            grid.add_switch(dis2)  # this disconnector must be included to respect the SE geometry
            grid.add_switch(dis3)  # this disconnector must be included to respect the SE geometry

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 7, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist, ypos=y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus2, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus2, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bus1, bus_to=transfer_bar,
                              graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_switch(dis1)
            grid.add_switch(dis2)  # this disconnector must be included to respect the SE geometry
            grid.add_switch(cb1)  # this disconnector must be included to respect the SE geometry
            grid.add_switch(dis3)  # this disconnector must be included to respect the SE geometry

        # coupling
        bus1 = dev.Bus(f"{name}_coupling_bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=max(n_lines, n_trafos) * x_dist + x_dist * 0.25, ypos=y_dist * 3.6, width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        dis1 = dev.Switch(name="Dis_bar1", bus_from=bus1, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
        dis2 = dev.Switch(name="Dis_bar2", bus_from=bus1, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
        cb1 = dev.Switch(name="CB_coupling", bus_from=bus1, bus_to=transfer_bar,
                         graphic_type=SwitchGraphicType.CircuitBreaker)

        grid.add_bus(bus1)
        grid.add_switch(dis1)
        grid.add_switch(dis2)
        grid.add_switch(cb1)


def breaker_and_a_half(name, grid: MultiCircuit, n_lines: int, v_nom: float,
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
                   width=(n_lines + n_lines % 2) * x_dist, xpos=-x_dist, ypos=0, country=country,
                   graphic_type=BusGraphicType.BusBar)
    grid.add_bus(bar1)

    if include_disconnectors:
        bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(n_lines + n_lines % 2) * x_dist, xpos=-x_dist, ypos=y_dist * 9, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)

        for i in range(0, n_lines, 2):
            bus1 = dev.Bus(f"LineBus1_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - bus_width / 2, ypos=y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - bus_width / 2, ypos=y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - bus_width / 2, ypos=y_dist * 3, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus_line_connection_1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom,
                                            voltage_level=vl,
                                            xpos=(i - 1) * x_dist - bus_width / 2, ypos=y_dist * 2.7, width=0,
                                            country=country,
                                            graphic_type=BusGraphicType.Connectivity)
            bus4 = dev.Bus(f"LineBus4_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - bus_width / 2, ypos=y_dist * 4, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus5 = dev.Bus(f"LineBus4_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - bus_width / 2, ypos=y_dist * 5, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus6 = dev.Bus(f"LineBus6_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - bus_width / 2, ypos=y_dist * 6, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus_line_connection_2 = dev.Bus(f"{name}_line_conn_{i + 1}", substation=substation, Vnom=v_nom,
                                            voltage_level=vl,
                                            xpos=(i - 1) * x_dist - bus_width / 2, ypos=y_dist * 5.7, width=0,
                                            country=country,
                                            graphic_type=BusGraphicType.Connectivity)
            bus7 = dev.Bus(f"LineBus7_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - bus_width / 2, ypos=y_dist * 7, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus8 = dev.Bus(f"LineBus8_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=i * x_dist - bus_width / 2, ypos=y_dist * 8, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar1, bus_to=bus1, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"SW1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bus3, bus_to=bus_line_connection_1,
                              graphic_type=SwitchGraphicType.CircuitBreaker)
            dis4 = dev.Switch(name=f"Dis4_{i}", bus_from=bus3, bus_to=bus4, graphic_type=SwitchGraphicType.Disconnector)
            cb2 = dev.Switch(name=f"SW2_{i}", bus_from=bus4, bus_to=bus5, graphic_type=SwitchGraphicType.Disconnector)
            dis5 = dev.Switch(name=f"Dis5_{i}", bus_from=bus5, bus_to=bus6, graphic_type=SwitchGraphicType.Disconnector)
            dis6 = dev.Switch(name=f"Dis6_{i}", bus_from=bus6, bus_to=bus_line_connection_2,
                              graphic_type=SwitchGraphicType.CircuitBreaker)
            dis7 = dev.Switch(name=f"Dis6_{i}", bus_from=bus6, bus_to=bus7, graphic_type=SwitchGraphicType.Disconnector)
            cb3 = dev.Switch(name=f"SW3_{i}", bus_from=bus7, bus_to=bus8, graphic_type=SwitchGraphicType.Disconnector)
            dis8 = dev.Switch(name=f"Dis6_{i}", bus_from=bus8, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            grid.add_bus(bus2)
            grid.add_bus(bus3)
            grid.add_bus(bus4)
            grid.add_bus(bus5)
            grid.add_bus(bus6)
            grid.add_bus(bus7)
            grid.add_bus(bus8)
            grid.add_bus(bus_line_connection_1)
            grid.add_bus(bus_line_connection_2)
            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)
            grid.add_switch(dis3)
            grid.add_switch(dis4)
            grid.add_switch(cb2)
            grid.add_switch(dis5)
            grid.add_switch(dis6)
            grid.add_switch(dis7)
            grid.add_switch(cb3)
            grid.add_switch(dis8)

    else:
        bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(n_lines + n_lines % 2) * x_dist, xpos=-x_dist, ypos=y_dist * 3, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)

        for i in range(0, n_lines, 2):
            bus_line_connection_1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom,
                                            voltage_level=vl,
                                            xpos=i * x_dist - bus_width / 2, ypos=y_dist, width=0,
                                            country=country,
                                            graphic_type=BusGraphicType.Connectivity)
            bus_line_connection_2 = dev.Bus(f"{name}_line_conn_{i + 1}", substation=substation, Vnom=v_nom,
                                            voltage_level=vl,
                                            xpos=i * x_dist - bus_width / 2, ypos=y_dist * 2, width=0,
                                            country=country,
                                            graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"SW1_{i}", bus_from=bar1, bus_to=bus_line_connection_1,
                             graphic_type=SwitchGraphicType.CircuitBreaker)
            cb2 = dev.Switch(name=f"SW2_{i}", bus_from=bus_line_connection_1, bus_to=bus_line_connection_2,
                             graphic_type=SwitchGraphicType.CircuitBreaker)
            cb3 = dev.Switch(name=f"SW3_{i}", bus_from=bus_line_connection_2, bus_to=bar2,
                             graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus_line_connection_1)
            grid.add_bus(bus_line_connection_2)
            grid.add_switch(cb1)
            grid.add_switch(cb2)
            grid.add_switch(cb3)
