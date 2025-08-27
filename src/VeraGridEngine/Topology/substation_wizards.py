# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple, List
import VeraGridEngine.Devices as dev
from VeraGridEngine import Country, BusGraphicType, SwitchGraphicType
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import SubstationTypes


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
    :param offset_x:
    :param offset_y:
    :return:
    """

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5
    l_x_pos = []
    l_y_pos = []

    if include_disconnectors:

        bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                      width=max(n_lines, n_trafos) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
                          max(n_lines, n_trafos) - 1),
                      xpos=offset_x - bus_width, ypos=offset_y + y_dist * 3, country=country,
                      graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar)
        l_x_pos.append(bar.x)
        l_y_pos.append(bar.y)

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + 0, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_bus(bus3)
            l_x_pos.append(bus3.x)
            l_y_pos.append(bus3.y)

            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 4, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_switch(dis1)
            grid.add_switch(cb1)

    else:

        bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                      width=max(n_lines, n_trafos) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
                          max(n_lines, n_trafos) - 1),
                      xpos=offset_x - bus_width, ypos=offset_y + y_dist, country=country,
                      graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar)
        l_x_pos.append(bar.x)
        l_y_pos.append(bar.y)

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_switch(cb1)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_switch(cb1)

    offset_total_x = max(l_x_pos, default=0) + x_dist
    offset_total_y = max(l_y_pos, default=0) + y_dist

    return vl, offset_total_x, offset_total_y


def create_single_bar_with_bypass(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
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
    :param offset_x:
    :param offset_y:
    :return:
    """

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5
    l_x_pos = []
    l_y_pos = []

    if include_disconnectors:

        bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                      width=max(n_lines, n_trafos) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
                          max(n_lines, n_trafos) - 1),
                      xpos=offset_x - bus_width, ypos=offset_y + y_dist * 3, country=country,
                      graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar)
        l_x_pos.append(bar.x)
        l_y_pos.append(bar.y)

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + 0, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus3, bus_to=bar, graphic_type=SwitchGraphicType.Disconnector)
            bypass_dis = dev.Switch(name=f"Bypass_Dis_{i}", bus_from=bus1, bus_to=bar,
                                    graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_bus(bus3)
            l_x_pos.append(bus3.x)
            l_y_pos.append(bus3.y)

            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)
            grid.add_switch(bypass_dis)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 5, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 4, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)
            bypass_dis = dev.Switch(name=f"Bypass_Dis_{i}", bus_from=bus1, bus_to=bar,
                                    graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(bypass_dis)
    else:

        bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                      width=max(n_lines, n_trafos) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
                          max(n_lines, n_trafos) - 1),
                      xpos=offset_x - bus_width, ypos=offset_y + y_dist * 1, country=country,
                      graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar)
        l_x_pos.append(bar.x)
        l_y_pos.append(bar.y)

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.CircuitBreaker)
            bypass_dis = dev.Switch(name=f"Bypass_Dis_{i}", bus_from=bus1, bus_to=bar,
                                    graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_switch(cb1)
            grid.add_switch(bypass_dis)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)
            bypass_dis = dev.Switch(name=f"Bypass_Dis_{i}", bus_from=bus1, bus_to=bar,
                                    graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_switch(cb1)
            grid.add_switch(bypass_dis)

    offset_total_x = max(l_x_pos, default=0) + x_dist
    offset_total_y = max(l_y_pos, default=0) + y_dist

    return vl, offset_total_x, offset_total_y


def create_single_bar_with_splitter(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
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
    :param offset_x:
    :param offset_y:
    :return:
    """

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5
    bar_2_x_offset = bus_width * 1.2
    bar_2_y_offset = bus_width * 1.2
    l_x_pos = []
    l_y_pos = []

    n_lines_bar_1 = n_lines // 2
    n_trafos_bar_1 = n_trafos // 2
    n_lines_bar_2 = n_lines - n_lines_bar_1
    n_trafos_bar_2 = n_trafos - n_trafos_bar_1

    width_bar_1 = max(n_lines_bar_1, n_trafos_bar_1) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
        max(n_lines_bar_1, n_trafos_bar_1) - 1)
    width_bar_2 = max(n_lines_bar_2, n_trafos_bar_2) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
        max(n_lines_bar_2, n_trafos_bar_2) - 1)

    if include_disconnectors:

        bar1 = dev.Bus(f"{name} bar 1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=width_bar_1, xpos=offset_x - bus_width, ypos=offset_y + y_dist * 3, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar1)
        l_x_pos.append(bar1.x)
        l_y_pos.append(bar1.y)

        bar2 = dev.Bus(f"{name} bar 2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=width_bar_2, xpos=offset_x + width_bar_1 + bar_2_x_offset,
                       ypos=offset_y + y_dist * 3 + bar_2_y_offset,
                       country=country, graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)
        l_x_pos.append(bar2.x)
        l_y_pos.append(bar2.y)

        cb_bars = dev.Switch(name=f"CB_bars", bus_from=bar1, bus_to=bar2, graphic_type=SwitchGraphicType.CircuitBreaker)
        grid.add_switch(cb_bars)

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
                           xpos=offset_x + i * x_dist + x_offset, ypos=offset_y + y_offset, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist + x_offset, ypos=offset_y + y_dist + y_offset, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist + x_offset, ypos=offset_y + y_dist * 2 + y_offset,
                           width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_bus(bus3)
            l_x_pos.append(bus3.x)
            l_y_pos.append(bus3.y)

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
                           xpos=offset_x + i * x_dist + x_offset, ypos=offset_y + y_dist * 5 + y_offset,
                           width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist + x_offset, ypos=offset_y + y_dist * 4 + y_offset,
                           width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_switch(dis1)
            grid.add_switch(cb1)
    else:

        bar1 = dev.Bus(f"{name} bar 1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=width_bar_1, xpos=offset_x - bus_width, ypos=offset_y + y_dist * 1, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar1)
        l_x_pos.append(bar1.x)
        l_y_pos.append(bar1.y)

        bar2 = dev.Bus(f"{name} bar 2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=width_bar_2, xpos=offset_x + width_bar_1 + bar_2_x_offset,
                       ypos=offset_y + y_dist * 1 + bar_2_y_offset,
                       country=country, graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)
        l_x_pos.append(bar2.x)
        l_y_pos.append(bar2.y)

        cb_bars = dev.Switch(name=f"CB_bars", bus_from=bar1, bus_to=bar2, graphic_type=SwitchGraphicType.CircuitBreaker)
        grid.add_switch(cb_bars)

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
                           xpos=offset_x + i * x_dist + x_offset, ypos=offset_y + y_dist * 0 + y_offset,
                           width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

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
                           xpos=offset_x + i * x_dist + x_offset, ypos=offset_y + y_dist * 2 + y_offset,
                           width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_switch(cb1)

    offset_total_x = max(l_x_pos, default=0) + x_dist
    offset_total_y = max(l_y_pos, default=0) + y_dist

    return vl, offset_total_x, offset_total_y


def create_double_bar(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
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
    :param offset_x:
    :param offset_y:
    :return:
    """

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5
    l_x_pos = []
    l_y_pos = []

    if include_disconnectors:

        bar1 = dev.Bus(f"{name} bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 2 + (x_dist - bus_width) * max(
                           n_lines,
                           n_trafos),
                       xpos=offset_x - bus_width, ypos=offset_y + y_dist * 3, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar1)
        l_x_pos.append(bar1.x)
        l_y_pos.append(bar1.y)

        bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 2 + (x_dist - bus_width) * max(
                           n_lines,
                           n_trafos),
                       xpos=offset_x - bus_width, ypos=offset_y + y_dist * 4, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)
        l_x_pos.append(bar2.x)
        l_y_pos.append(bar2.y)

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 2, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar1, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bar2, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_bus(bus3)
            l_x_pos.append(bus3.x)
            l_y_pos.append(bus3.y)

            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)
            grid.add_switch(dis3)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar2, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_switch(dis1)
            grid.add_switch(dis2)
            grid.add_switch(cb1)

        # coupling
        bus1 = dev.Bus(f"{name}_coupling_bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=offset_x + max(n_lines, n_trafos) * x_dist, ypos=offset_y + y_dist * 3.6, width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        bus2 = dev.Bus(f"{name}_coupling_bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=offset_x + max(n_lines, n_trafos) * x_dist + x_dist * 0.5, ypos=offset_y + y_dist * 3.6,
                       width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        dis1 = dev.Switch(name="Dis_bar1", bus_from=bar1, bus_to=bus1, graphic_type=SwitchGraphicType.Disconnector)
        dis2 = dev.Switch(name="Dis_bar2", bus_from=bar2, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
        cb1 = dev.Switch(name="CB_coupling", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

        grid.add_bus(bus1)
        l_x_pos.append(bus1.x)
        l_y_pos.append(bus1.y)

        grid.add_bus(bus2)
        l_x_pos.append(bus2.x)
        l_y_pos.append(bus2.y)

        grid.add_switch(dis1)
        grid.add_switch(dis2)
        grid.add_switch(cb1)

    else:

        bar1 = dev.Bus(f"{name} bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 2 + (x_dist - bus_width) * max(
                           n_lines,
                           n_trafos),
                       xpos=offset_x - bus_width, ypos=offset_y + y_dist * 2, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar1)
        l_x_pos.append(bar1.x)
        l_y_pos.append(bar1.y)

        bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 2 + (x_dist - bus_width) * max(
                           n_lines,
                           n_trafos),
                       xpos=offset_x - bus_width, ypos=offset_y + y_dist * 3, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)
        l_x_pos.append(bar2.x)
        l_y_pos.append(bar2.y)

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 0, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis1 = dev.Switch(name=f"Dis2_{i}", bus_from=bar1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis3_{i}", bus_from=bar2, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_switch(cb1)
            grid.add_switch(dis1)  # this disconnectors must be included to respect the SE geometry
            grid.add_switch(dis2)  # this disconnectors must be included to respect the SE geometry

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 4, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bar1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar2, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_switch(dis1)  # this disconnectors must be included to respect the SE geometry
            grid.add_switch(dis2)  # this disconnectors must be included to respect the SE geometry
            grid.add_switch(cb1)

        # coupling
        cb1 = dev.Switch(name="CB_coupling", bus_from=bar1, bus_to=bar2, graphic_type=SwitchGraphicType.CircuitBreaker)
        grid.add_switch(cb1)

    offset_total_x = max(l_x_pos, default=0) + x_dist
    offset_total_y = max(l_y_pos, default=0) + y_dist

    return vl, offset_total_x, offset_total_y


def create_double_bar_with_transference_bar(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
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
    :param offset_x:
    :param offset_y:
    :return:
    """

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5
    l_x_pos = []
    l_y_pos = []

    if include_disconnectors:

        bar1 = dev.Bus(f"{name} bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (x_dist - bus_width) * max(
                           n_lines,
                           n_trafos),
                       xpos=offset_x - bus_width, ypos=offset_y + y_dist * 3, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar1)
        l_x_pos.append(bar1.x)
        l_y_pos.append(bar1.y)

        bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (x_dist - bus_width) * max(
                           n_lines,
                           n_trafos),
                       xpos=offset_x - bus_width, ypos=offset_y + y_dist * 4, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)
        l_x_pos.append(bar2.x)
        l_y_pos.append(bar2.y)

        transfer_bar = dev.Bus(f"{name} transfer bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                               width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (
                                   x_dist - bus_width) * max(
                                   n_lines,
                                   n_trafos),
                               xpos=offset_x - bus_width, ypos=offset_y + y_dist * 5, country=country,
                               graphic_type=BusGraphicType.BusBar)
        grid.add_bus(transfer_bar)
        l_x_pos.append(transfer_bar.x)
        l_y_pos.append(transfer_bar.y)

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist + x_dist * 0.2, ypos=offset_y, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - x_dist * 0.25, ypos=offset_y + y_dist, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - x_dist * 0.25, ypos=offset_y + y_dist * 2, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar1, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bar2, bus_to=bus3, graphic_type=SwitchGraphicType.Disconnector)
            dis4 = dev.Switch(name=f"Dis4_{i}", bus_from=bus1, bus_to=transfer_bar,
                              graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_bus(bus3)
            l_x_pos.append(bus3.x)
            l_y_pos.append(bus3.y)

            grid.add_switch(dis1)
            grid.add_switch(cb1)
            grid.add_switch(dis2)
            grid.add_switch(dis3)
            grid.add_switch(dis4)

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 8, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 7, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"trafo3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus3, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bus3, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
            dis4 = dev.Switch(name=f"Dis4_{i}", bus_from=bus1, bus_to=transfer_bar,
                              graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_bus(bus3)
            l_x_pos.append(bus3.x)
            l_y_pos.append(bus3.y)

            grid.add_switch(dis1)
            grid.add_switch(dis2)
            grid.add_switch(cb1)
            grid.add_switch(dis3)
            grid.add_switch(dis4)

        # coupling
        bus1 = dev.Bus(f"{name}_coupling_bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=offset_x + max(n_lines, n_trafos) * x_dist + x_dist * 0.25, ypos=offset_y + y_dist * 3.6,
                       width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        bus2 = dev.Bus(f"{name}_coupling_bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=offset_x + max(n_lines, n_trafos) * x_dist + x_dist * 0.25, ypos=offset_y + y_dist * 4.6,
                       width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        dis1 = dev.Switch(name="Dis_bar1", bus_from=bus1, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
        dis2 = dev.Switch(name="Dis_bar2", bus_from=bus1, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
        cb1 = dev.Switch(name="CB_coupling", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
        dis3 = dev.Switch(name="Dis_coupling", bus_from=bus2, bus_to=transfer_bar,
                          graphic_type=SwitchGraphicType.Disconnector)

        grid.add_bus(bus1)
        l_x_pos.append(bus1.x)
        l_y_pos.append(bus1.y)

        grid.add_bus(bus2)
        l_x_pos.append(bus2.x)
        l_y_pos.append(bus2.y)

        grid.add_switch(dis1)
        grid.add_switch(dis2)
        grid.add_switch(cb1)
        grid.add_switch(dis3)

    else:

        bar1 = dev.Bus(f"{name} bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (x_dist - bus_width) * max(
                           n_lines,
                           n_trafos),
                       xpos=offset_x - bus_width, ypos=offset_y + y_dist * 2, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar1)
        l_x_pos.append(bar1.x)
        l_y_pos.append(bar1.y)

        bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (x_dist - bus_width) * max(
                           n_lines,
                           n_trafos),
                       xpos=offset_x - bus_width, ypos=offset_y + y_dist * 3, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)
        l_x_pos.append(bar2.x)
        l_y_pos.append(bar2.y)

        transfer_bar = dev.Bus(f"{name} transfer bar", substation=substation, Vnom=v_nom, voltage_level=vl,
                               width=(max(n_lines, n_trafos) + 1) * bus_width + bus_width * 3 + (
                                   x_dist - bus_width) * max(
                                   n_lines,
                                   n_trafos),
                               xpos=offset_x - bus_width, ypos=offset_y + y_dist * 4, country=country,
                               graphic_type=BusGraphicType.BusBar)
        grid.add_bus(transfer_bar)
        l_x_pos.append(transfer_bar.x)
        l_y_pos.append(transfer_bar.y)

        for i in range(n_lines):
            bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist + x_dist * 0.1, ypos=offset_y, width=bus_width, country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - x_dist * 0.1, ypos=offset_y + y_dist, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus2, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus2, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bus1, bus_to=transfer_bar,
                              graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_switch(cb1)
            grid.add_switch(dis1)  # this disconnector must be included to respect the SE geometry
            grid.add_switch(dis2)  # this disconnector must be included to respect the SE geometry
            grid.add_switch(dis3)  # this disconnector must be included to respect the SE geometry

        for i in range(n_trafos):
            bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 6, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"trafo2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 5, width=bus_width,
                           country=country, graphic_type=BusGraphicType.Connectivity)
            dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus2, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
            dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bus2, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
            cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bus2, graphic_type=SwitchGraphicType.CircuitBreaker)
            dis3 = dev.Switch(name=f"Dis3_{i}", bus_from=bus1, bus_to=transfer_bar,
                              graphic_type=SwitchGraphicType.Disconnector)

            grid.add_bus(bus1)
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_switch(dis1)
            grid.add_switch(dis2)  # this disconnector must be included to respect the SE geometry
            grid.add_switch(cb1)  # this disconnector must be included to respect the SE geometry
            grid.add_switch(dis3)  # this disconnector must be included to respect the SE geometry

        # coupling
        bus1 = dev.Bus(f"{name}_coupling_bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       xpos=offset_x + max(n_lines, n_trafos) * x_dist + x_dist * 0.25, ypos=offset_y + y_dist * 3.6,
                       width=bus_width,
                       country=country,
                       graphic_type=BusGraphicType.Connectivity)
        dis1 = dev.Switch(name="Dis_bar1", bus_from=bus1, bus_to=bar1, graphic_type=SwitchGraphicType.Disconnector)
        dis2 = dev.Switch(name="Dis_bar2", bus_from=bus1, bus_to=bar2, graphic_type=SwitchGraphicType.Disconnector)
        cb1 = dev.Switch(name="CB_coupling", bus_from=bus1, bus_to=transfer_bar,
                         graphic_type=SwitchGraphicType.CircuitBreaker)

        grid.add_bus(bus1)
        l_x_pos.append(bus1.x)
        l_y_pos.append(bus1.y)

        grid.add_switch(dis1)  # this disconnector must be included to respect the SE geometry
        grid.add_switch(dis2)  # this disconnector must be included to respect the SE geometry
        grid.add_switch(cb1)

    offset_total_x = max(l_x_pos, default=0) + x_dist
    offset_total_y = max(l_y_pos, default=0) + y_dist

    return vl, offset_total_x, offset_total_y


def create_breaker_and_a_half(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
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
    :param offset_x:
    :param offset_y:
    :return:
    """

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    bus_width = 120
    x_dist = bus_width * 2
    y_dist = bus_width * 1.5
    l_x_pos = []
    l_y_pos = []

    if include_disconnectors:

        bar1 = dev.Bus(f"{name} bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(n_lines + n_lines % 2) * x_dist, xpos=offset_x - x_dist, ypos=offset_y, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar1)
        l_x_pos.append(bar1.x)
        l_y_pos.append(bar1.y)

        bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(n_lines + n_lines % 2) * x_dist, xpos=offset_x - x_dist, ypos=offset_y + y_dist * 9,
                       country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)
        l_x_pos.append(bar2.x)
        l_y_pos.append(bar2.y)

        for i in range(0, n_lines, 2):
            bus1 = dev.Bus(f"LineBus1_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus2 = dev.Bus(f"LineBus2_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist * 2, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus3 = dev.Bus(f"LineBus3_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist * 3, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus_line_connection_1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom,
                                            voltage_level=vl,
                                            xpos=offset_x + (i - 1) * x_dist - bus_width / 2,
                                            ypos=offset_y + y_dist * 2.7, width=0,
                                            country=country,
                                            graphic_type=BusGraphicType.Connectivity)
            bus4 = dev.Bus(f"LineBus4_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist * 4, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus5 = dev.Bus(f"LineBus4_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist * 5, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus6 = dev.Bus(f"LineBus6_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist * 6, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus_line_connection_2 = dev.Bus(f"{name}_line_conn_{i + 1}", substation=substation, Vnom=v_nom,
                                            voltage_level=vl,
                                            xpos=offset_x + (i - 1) * x_dist - bus_width / 2,
                                            ypos=offset_y + y_dist * 5.7, width=0,
                                            country=country,
                                            graphic_type=BusGraphicType.Connectivity)
            bus7 = dev.Bus(f"LineBus7_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist * 7, width=bus_width,
                           country=country,
                           graphic_type=BusGraphicType.Connectivity)
            bus8 = dev.Bus(f"LineBus8_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
                           xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist * 8, width=bus_width,
                           country=country,
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
            l_x_pos.append(bus1.x)
            l_y_pos.append(bus1.y)

            grid.add_bus(bus2)
            l_x_pos.append(bus2.x)
            l_y_pos.append(bus2.y)

            grid.add_bus(bus3)
            l_x_pos.append(bus3.x)
            l_y_pos.append(bus3.y)

            grid.add_bus(bus4)
            l_x_pos.append(bus4.x)
            l_y_pos.append(bus4.y)

            grid.add_bus(bus5)
            l_x_pos.append(bus5.x)
            l_y_pos.append(bus5.y)

            grid.add_bus(bus6)
            l_x_pos.append(bus6.x)
            l_y_pos.append(bus6.y)

            grid.add_bus(bus7)
            l_x_pos.append(bus7.x)
            l_y_pos.append(bus7.y)

            grid.add_bus(bus8)
            l_x_pos.append(bus8.x)
            l_y_pos.append(bus8.y)

            grid.add_bus(bus_line_connection_1)
            l_x_pos.append(bus_line_connection_1.x)
            l_y_pos.append(bus_line_connection_1.y)

            grid.add_bus(bus_line_connection_2)
            l_x_pos.append(bus_line_connection_2.x)
            l_y_pos.append(bus_line_connection_2.y)

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

        bar1 = dev.Bus(f"{name} bar1", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(n_lines + n_lines % 2) * x_dist, xpos=offset_x - x_dist, ypos=offset_y, country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar1)
        l_x_pos.append(bar1.x)
        l_y_pos.append(bar1.y)

        bar2 = dev.Bus(f"{name} bar2", substation=substation, Vnom=v_nom, voltage_level=vl,
                       width=(n_lines + n_lines % 2) * x_dist, xpos=offset_x - x_dist, ypos=offset_y + y_dist * 3,
                       country=country,
                       graphic_type=BusGraphicType.BusBar)
        grid.add_bus(bar2)
        l_x_pos.append(bar2.x)
        l_y_pos.append(bar2.y)

        for i in range(0, n_lines, 2):
            bus_line_connection_1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom,
                                            voltage_level=vl,
                                            xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist, width=0,
                                            country=country,
                                            graphic_type=BusGraphicType.Connectivity)
            bus_line_connection_2 = dev.Bus(f"{name}_line_conn_{i + 1}", substation=substation, Vnom=v_nom,
                                            voltage_level=vl,
                                            xpos=offset_x + i * x_dist - bus_width / 2, ypos=offset_y + y_dist * 2,
                                            width=0,
                                            country=country,
                                            graphic_type=BusGraphicType.Connectivity)
            cb1 = dev.Switch(name=f"SW1_{i}", bus_from=bar1, bus_to=bus_line_connection_1,
                             graphic_type=SwitchGraphicType.CircuitBreaker)
            cb2 = dev.Switch(name=f"SW2_{i}", bus_from=bus_line_connection_1, bus_to=bus_line_connection_2,
                             graphic_type=SwitchGraphicType.CircuitBreaker)
            cb3 = dev.Switch(name=f"SW3_{i}", bus_from=bus_line_connection_2, bus_to=bar2,
                             graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_bus(bus_line_connection_1)
            l_x_pos.append(bus_line_connection_1.x)
            l_y_pos.append(bus_line_connection_1.y)

            grid.add_bus(bus_line_connection_2)
            l_x_pos.append(bus_line_connection_2.x)
            l_y_pos.append(bus_line_connection_2.y)

            grid.add_switch(cb1)
            grid.add_switch(cb2)
            grid.add_switch(cb3)

    offset_total_x = max(l_x_pos, default=0) + x_dist
    offset_total_y = max(l_y_pos, default=0) + y_dist

    return vl, offset_total_x, offset_total_y


def create_ring(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
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
    :param offset_x:
    :param offset_y:
    :return:
    """

    vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
    grid.add_voltage_level(vl)

    bus_width = 80
    bus_height = 80
    x_dist = bus_width * 3.5
    y_dist = bus_width * 3.5
    l_x_pos = []
    l_y_pos = []

    n_positions = max(n_lines, n_trafos, 2) * 2

    if include_disconnectors:

        if n_positions == 4:

            busL0 = dev.Bus(f"{name}_line_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x, ypos=offset_y, width=bus_width, height=bus_height, country=country,
                            graphic_type=BusGraphicType.Connectivity)
            busT0 = dev.Bus(f"{name}_trafo_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x, ypos=offset_y + y_dist * 3, width=bus_width, height=bus_height,
                            country=country, graphic_type=BusGraphicType.Connectivity)
            busL1 = dev.Bus(f"{name}_line_conn_1", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 3, ypos=offset_y + y_dist * 3, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            busT1 = dev.Bus(f"{name}_trafo_conn_1", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 3, ypos=offset_y, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)

            grid.add_bus(busL0)
            l_x_pos.append(busL0.x)
            l_y_pos.append(busL0.y)

            grid.add_bus(busT0)
            l_x_pos.append(busT0.x)
            l_y_pos.append(busT0.y)

            grid.add_bus(busL1)
            l_x_pos.append(busL1.x)
            l_y_pos.append(busL1.y)

            grid.add_bus(busT1)
            l_x_pos.append(busT1.x)
            l_y_pos.append(busT1.y)

            bus_L0_T1 = dev.Bus(f"Bus_L0_T1", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 1, ypos=offset_y, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T1_L0 = dev.Bus(f"Bus_T1_L0", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 2, ypos=offset_y, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_L0_T0 = dev.Bus(f"bus_L0_T0", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x, ypos=offset_y + y_dist * 1, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T0_L0 = dev.Bus(f"bus_T0_L0", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x, ypos=offset_y + y_dist * 2, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T1_L1 = dev.Bus(f"Bus_T1_L1", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 3, ypos=offset_y + y_dist * 1, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_L1_T1 = dev.Bus(f"Bus_L1_T1", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 3, ypos=offset_y + y_dist * 2, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T0_L1 = dev.Bus(f"Bus_T0_L1", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 1, ypos=offset_y + y_dist * 3, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_L1_T0 = dev.Bus(f"Bus_L1_T0", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 2, ypos=offset_y + y_dist * 3, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)

            grid.add_bus(bus_L0_T1)
            l_x_pos.append(bus_L0_T1.x)
            l_y_pos.append(bus_L0_T1.y)

            grid.add_bus(bus_T1_L0)
            l_x_pos.append(bus_T1_L0.x)
            l_y_pos.append(bus_T1_L0.y)

            grid.add_bus(bus_L0_T0)
            l_x_pos.append(bus_L0_T0.x)
            l_y_pos.append(bus_L0_T0.y)

            grid.add_bus(bus_T0_L0)
            l_x_pos.append(bus_T0_L0.x)
            l_y_pos.append(bus_T0_L0.y)

            grid.add_bus(bus_T1_L1)
            l_x_pos.append(bus_T1_L1.x)
            l_y_pos.append(bus_T1_L1.y)

            grid.add_bus(bus_L1_T1)
            l_x_pos.append(bus_L1_T1.x)
            l_y_pos.append(bus_L1_T1.y)

            grid.add_bus(bus_T0_L1)
            l_x_pos.append(bus_T0_L1.x)
            l_y_pos.append(bus_T0_L1.y)

            grid.add_bus(bus_L1_T0)
            l_x_pos.append(bus_L1_T0.x)
            l_y_pos.append(bus_L1_T0.y)

            cb_00 = dev.Switch(name=f"CB_00", bus_from=bus_L0_T0, bus_to=bus_T0_L0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_01 = dev.Switch(name=f"CB_01", bus_from=bus_L0_T1, bus_to=bus_T1_L0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_10 = dev.Switch(name=f"CB_10", bus_from=bus_T0_L1, bus_to=bus_L1_T0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_11 = dev.Switch(name=f"CB_11", bus_from=bus_L1_T1, bus_to=bus_T1_L1,
                               graphic_type=SwitchGraphicType.CircuitBreaker)

            dis_L0_T1 = dev.Switch(name=f"Dis_L0_T1", bus_from=busL0, bus_to=bus_L0_T1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T1_L0 = dev.Switch(name=f"Dis_T1_L0", bus_from=bus_T1_L0, bus_to=busT1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_L0_T0 = dev.Switch(name=f"Dis_L0_T0", bus_from=busL0, bus_to=bus_L0_T0,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T0_L0 = dev.Switch(name=f"Dis_T0_L0", bus_from=bus_T0_L0, bus_to=busT0,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T1_L1 = dev.Switch(name=f"Dis_T1_L1", bus_from=busT1, bus_to=bus_T1_L1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_L1_T1 = dev.Switch(name=f"Dis_L1_T1", bus_from=bus_L1_T1, bus_to=busL1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T0_L1 = dev.Switch(name=f"Dis_T0_L1", bus_from=busT0, bus_to=bus_T0_L1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_L1_T0 = dev.Switch(name=f"Dis_L1_T0", bus_from=bus_L1_T0, bus_to=busL1,
                                   graphic_type=SwitchGraphicType.Disconnector)

            grid.add_switch(cb_00)
            grid.add_switch(cb_01)
            grid.add_switch(cb_10)
            grid.add_switch(cb_11)

            grid.add_switch(dis_L0_T1)
            grid.add_switch(dis_T1_L0)
            grid.add_switch(dis_L0_T0)
            grid.add_switch(dis_T0_L0)
            grid.add_switch(dis_T1_L1)
            grid.add_switch(dis_L1_T1)
            grid.add_switch(dis_T0_L1)
            grid.add_switch(dis_L1_T0)

        elif n_positions == 6:
            busL0 = dev.Bus(f"{name}_line_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x, ypos=offset_y, width=bus_width, height=bus_height, country=country,
                            graphic_type=BusGraphicType.Connectivity)
            busT0 = dev.Bus(f"{name}_trafo_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x, ypos=offset_y + y_dist * 3, width=bus_width, height=bus_height,
                            country=country, graphic_type=BusGraphicType.Connectivity)
            busL1 = dev.Bus(f"{name}_line_conn_1", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 3, ypos=offset_y + y_dist * 4, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            busT1 = dev.Bus(f"{name}_trafo_conn_1", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 3, ypos=offset_y + y_dist * -1, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            busL2 = dev.Bus(f"{name}_line_conn_2", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 6, ypos=offset_y, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            busT2 = dev.Bus(f"{name}_trafo_conn_2", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 6, ypos=offset_y + y_dist * 3, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)

            grid.add_bus(busL0)
            l_x_pos.append(busL0.x)
            l_y_pos.append(busL0.y)

            grid.add_bus(busT0)
            l_x_pos.append(busT0.x)
            l_y_pos.append(busT0.y)

            grid.add_bus(busL1)
            l_x_pos.append(busL1.x)
            l_y_pos.append(busL1.y)

            grid.add_bus(busT1)
            l_x_pos.append(busT1.x)
            l_y_pos.append(busT1.y)

            grid.add_bus(busL2)
            l_x_pos.append(busL2.x)
            l_y_pos.append(busL2.y)

            grid.add_bus(busT2)
            l_x_pos.append(busT2.x)
            l_y_pos.append(busT2.y)

            bus_L0_T1 = dev.Bus(f"Bus_L0_T1", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 1, ypos=offset_y - y_dist / 3, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T1_L0 = dev.Bus(f"Bus_T1_L0", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 2, ypos=offset_y - y_dist * 2 / 3, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_L0_T0 = dev.Bus(f"bus_L0_T0", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x, ypos=offset_y + y_dist * 1, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T0_L0 = dev.Bus(f"bus_T0_L0", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x, ypos=offset_y + y_dist * 2, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T2_L2 = dev.Bus(f"Bus_T2_L2", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 6, ypos=offset_y + y_dist * 2, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_L2_T2 = dev.Bus(f"Bus_L2_T2", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 6, ypos=offset_y + y_dist * 1, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T0_L1 = dev.Bus(f"Bus_T0_L1", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 1, ypos=offset_y + y_dist * (3 + 1 / 3), width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_L1_T0 = dev.Bus(f"Bus_L1_T0", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 2, ypos=offset_y + y_dist * (3 + 2 / 3), width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T1_L2 = dev.Bus(f"Bus_T1_L2", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 4, ypos=offset_y - y_dist * 2 / 3, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_L2_T1 = dev.Bus(f"Bus_L2_T1", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 5, ypos=offset_y - y_dist * 1 / 3, width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_L1_T2 = dev.Bus(f"Bus_L1_T2", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 4, ypos=offset_y + y_dist * (3 + 2 / 3), width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            bus_T2_L1 = dev.Bus(f"Bus_T2_L1", substation=substation, Vnom=v_nom, voltage_level=vl,
                                xpos=offset_x + x_dist * 5, ypos=offset_y + y_dist * (3 + 1 / 3), width=bus_width,
                                height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)

            grid.add_bus(bus_L0_T1)
            l_x_pos.append(bus_L0_T1.x)
            l_y_pos.append(bus_L0_T1.y)

            grid.add_bus(bus_T1_L0)
            l_x_pos.append(bus_T1_L0.x)
            l_y_pos.append(bus_T1_L0.y)

            grid.add_bus(bus_L0_T0)
            l_x_pos.append(bus_L0_T0.x)
            l_y_pos.append(bus_L0_T0.y)

            grid.add_bus(bus_T0_L0)
            l_x_pos.append(bus_T0_L0.x)
            l_y_pos.append(bus_T0_L0.y)

            grid.add_bus(bus_T2_L2)
            l_x_pos.append(bus_T2_L2.x)
            l_y_pos.append(bus_T2_L2.y)

            grid.add_bus(bus_L2_T2)
            l_x_pos.append(bus_L2_T2.x)
            l_y_pos.append(bus_L2_T2.y)

            grid.add_bus(bus_T0_L1)
            l_x_pos.append(bus_T0_L1.x)
            l_y_pos.append(bus_T0_L1.y)

            grid.add_bus(bus_L1_T0)
            l_x_pos.append(bus_L1_T0.x)
            l_y_pos.append(bus_L1_T0.y)

            grid.add_bus(bus_T1_L2)
            l_x_pos.append(bus_T1_L2.x)
            l_y_pos.append(bus_T1_L2.y)

            grid.add_bus(bus_L2_T1)
            l_x_pos.append(bus_L2_T1.x)
            l_y_pos.append(bus_L2_T1.y)

            grid.add_bus(bus_L1_T2)
            l_x_pos.append(bus_L1_T2.x)
            l_y_pos.append(bus_L1_T2.y)

            grid.add_bus(bus_T2_L1)
            l_x_pos.append(bus_T2_L1.x)
            l_y_pos.append(bus_T2_L1.y)

            cb_00 = dev.Switch(name=f"CB_00", bus_from=bus_L0_T0, bus_to=bus_T0_L0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_01 = dev.Switch(name=f"CB_01", bus_from=bus_L0_T1, bus_to=bus_T1_L0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_10 = dev.Switch(name=f"CB_10", bus_from=bus_T0_L1, bus_to=bus_L1_T0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_12 = dev.Switch(name=f"CB_12", bus_from=bus_L1_T2, bus_to=bus_T2_L1,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_21 = dev.Switch(name=f"CB_21", bus_from=bus_T1_L2, bus_to=bus_L2_T1,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_22 = dev.Switch(name=f"CB_22", bus_from=bus_L2_T2, bus_to=bus_T2_L2,
                               graphic_type=SwitchGraphicType.CircuitBreaker)

            dis_L0_T1 = dev.Switch(name=f"Dis_L0_T1", bus_from=busL0, bus_to=bus_L0_T1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T1_L0 = dev.Switch(name=f"Dis_T1_L0", bus_from=bus_T1_L0, bus_to=busT1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_L0_T0 = dev.Switch(name=f"Dis_L0_T0", bus_from=busL0, bus_to=bus_L0_T0,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T0_L0 = dev.Switch(name=f"Dis_T0_L0", bus_from=bus_T0_L0, bus_to=busT0,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T0_L1 = dev.Switch(name=f"Dis_T0_L1", bus_from=busT0, bus_to=bus_T0_L1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_L1_T0 = dev.Switch(name=f"Dis_L1_T0", bus_from=bus_L1_T0, bus_to=busL1,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_L1_T2 = dev.Switch(name=f"Dis_L1_T2", bus_from=busL1, bus_to=bus_L1_T2,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T2_L1 = dev.Switch(name=f"Dis_T2_L1", bus_from=bus_T2_L1, bus_to=busT2,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T1_L2 = dev.Switch(name=f"Dis_T1_L2", bus_from=busT1, bus_to=bus_T1_L2,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_L2_T1 = dev.Switch(name=f"Dis_L2_T1", bus_from=bus_L2_T1, bus_to=busL2,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_T2_L2 = dev.Switch(name=f"Dis_T2_L2", bus_from=busT2, bus_to=bus_T2_L2,
                                   graphic_type=SwitchGraphicType.Disconnector)
            dis_L2_T2 = dev.Switch(name=f"Dis_L2_T2", bus_from=bus_L2_T2, bus_to=busL2,
                                   graphic_type=SwitchGraphicType.Disconnector)

            grid.add_switch(cb_00)
            grid.add_switch(cb_01)
            grid.add_switch(cb_10)
            grid.add_switch(cb_21)
            grid.add_switch(cb_12)
            grid.add_switch(cb_22)

            grid.add_switch(dis_L0_T1)
            grid.add_switch(dis_T1_L0)
            grid.add_switch(dis_L0_T0)
            grid.add_switch(dis_T0_L0)
            grid.add_switch(dis_T2_L2)
            grid.add_switch(dis_L2_T2)
            grid.add_switch(dis_T0_L1)
            grid.add_switch(dis_L1_T0)
            grid.add_switch(dis_L1_T2)
            grid.add_switch(dis_T2_L1)
            grid.add_switch(dis_T1_L2)
            grid.add_switch(dis_L2_T1)

        else:
            pass

    else:

        if n_positions == 4:
            busL0 = dev.Bus(f"{name}_line_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x, ypos=offset_y, width=bus_width, height=bus_height, country=country,
                            graphic_type=BusGraphicType.Connectivity)
            busT0 = dev.Bus(f"{name}_trafo_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x, ypos=offset_y + y_dist * 2, width=bus_width, height=bus_height,
                            country=country, graphic_type=BusGraphicType.Connectivity)
            busL1 = dev.Bus(f"{name}_line_conn_1", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 2, ypos=offset_y + y_dist * 2, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            busT1 = dev.Bus(f"{name}_trafo_conn_1", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 2, ypos=offset_y, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)

            grid.add_bus(busL0)
            l_x_pos.append(busL0.x)
            l_y_pos.append(busL0.y)

            grid.add_bus(busT0)
            l_x_pos.append(busT0.x)
            l_y_pos.append(busT0.y)

            grid.add_bus(busL1)
            l_x_pos.append(busL1.x)
            l_y_pos.append(busL1.y)

            grid.add_bus(busT1)
            l_x_pos.append(busT1.x)
            l_y_pos.append(busT1.y)

            cb_00 = dev.Switch(name=f"CB_00", bus_from=busL0, bus_to=busT0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_01 = dev.Switch(name=f"CB_01", bus_from=busL0, bus_to=busT1,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_10 = dev.Switch(name=f"CB_10", bus_from=busL1, bus_to=busT0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_11 = dev.Switch(name=f"CB_11", bus_from=busL1, bus_to=busT1,
                               graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_switch(cb_00)
            grid.add_switch(cb_01)
            grid.add_switch(cb_10)
            grid.add_switch(cb_11)

        elif n_positions == 6:
            busL0 = dev.Bus(f"{name}_line_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x, ypos=offset_y, width=bus_width, height=bus_height, country=country,
                            graphic_type=BusGraphicType.Connectivity)
            busT0 = dev.Bus(f"{name}_trafo_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x, ypos=offset_y + y_dist * 2, width=bus_width, height=bus_height,
                            country=country, graphic_type=BusGraphicType.Connectivity)
            busL1 = dev.Bus(f"{name}_line_conn_1", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 2, ypos=offset_y + y_dist * 2 + y_dist, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            busT1 = dev.Bus(f"{name}_trafo_conn_1", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 2, ypos=offset_y - y_dist, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            busL2 = dev.Bus(f"{name}_line_conn_2", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 4, ypos=offset_y, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
            busT2 = dev.Bus(f"{name}_trafo_conn_2", substation=substation, Vnom=v_nom, voltage_level=vl,
                            xpos=offset_x + x_dist * 4, ypos=offset_y + y_dist * 2, width=bus_width,
                            height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)

            grid.add_bus(busL0)
            l_x_pos.append(busL0.x)
            l_y_pos.append(busL0.y)

            grid.add_bus(busT0)
            l_x_pos.append(busT0.x)
            l_y_pos.append(busT0.y)

            grid.add_bus(busL1)
            l_x_pos.append(busL1.x)
            l_y_pos.append(busL1.y)

            grid.add_bus(busT1)
            l_x_pos.append(busT1.x)
            l_y_pos.append(busT1.y)

            grid.add_bus(busL2)
            l_x_pos.append(busL1.x)
            l_y_pos.append(busL1.y)

            grid.add_bus(busT2)
            l_x_pos.append(busT1.x)
            l_y_pos.append(busT1.y)

            cb_00 = dev.Switch(name=f"CB_00", bus_from=busL0, bus_to=busT0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_01 = dev.Switch(name=f"CB_01", bus_from=busL0, bus_to=busT1,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_10 = dev.Switch(name=f"CB_10", bus_from=busL1, bus_to=busT0,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_12 = dev.Switch(name=f"CB_12", bus_from=busL1, bus_to=busT2,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_21 = dev.Switch(name=f"CB_21", bus_from=busT1, bus_to=busL2,
                               graphic_type=SwitchGraphicType.CircuitBreaker)
            cb_22 = dev.Switch(name=f"CB_22", bus_from=busL2, bus_to=busT2,
                               graphic_type=SwitchGraphicType.CircuitBreaker)

            grid.add_switch(cb_00)
            grid.add_switch(cb_01)
            grid.add_switch(cb_10)
            grid.add_switch(cb_12)
            grid.add_switch(cb_21)
            grid.add_switch(cb_22)

        else:
            pass

    offset_total_x = max(l_x_pos, default=0) + x_dist
    offset_total_y = max(l_y_pos, default=0) + y_dist

    return vl, offset_total_x, offset_total_y


# def create_ring_v2(name, grid: MultiCircuit, n_lines: int, n_trafos: int, v_nom: float,
#                    substation: dev.Substation, country: Country = None,
#                    include_disconnectors: bool = True,
#                    offset_x=0, offset_y=0) -> Tuple[dev.VoltageLevel, int, int]:
#     """
#
#     :param name:
#     :param grid:
#     :param n_lines:
#     :param n_trafos:
#     :param v_nom:
#     :param substation:
#     :param country:
#     :param include_disconnectors:
#     :param offset_x:
#     :param offset_y:
#     :return:
#     """
#
#     vl = dev.VoltageLevel(name=name, substation=substation, Vnom=v_nom)
#     grid.add_voltage_level(vl)
#
#     bus_width = 80
#     bus_height = 80
#     x_dist = bus_width * 3
#     y_dist = bus_width * 3.5
#     l_x_pos = []
#     l_y_pos = []
#
#     n_positions = max(n_lines, n_trafos, 2) * 2
#
#     if include_disconnectors:
#
#         busL0 = dev.Bus(f"{name}_line_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
#                         xpos=offset_x, ypos=offset_y, width=bus_width, height=bus_height, country=country,
#                         graphic_type=BusGraphicType.Connectivity)
#         busT0 = dev.Bus(f"{name}_trafo_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
#                         xpos=offset_x, ypos=offset_y + y_dist * 3, width=bus_width, height=bus_height, country=country,
#                         graphic_type=BusGraphicType.Connectivity)
#         busLn = dev.Bus(f"{name}_line_conn_{int(n_positions / 2) - 1}", substation=substation, Vnom=v_nom,
#                         voltage_level=vl, xpos=offset_x + (n_positions - 1) * x_dist, ypos=offset_y, width=bus_width,
#                         height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
#         busTn = dev.Bus(f"{name}_trafo_conn_{int(n_positions / 2) - 1}", substation=substation, Vnom=v_nom,
#                         voltage_level=vl, xpos=offset_x + (n_positions - 1) * x_dist, ypos=offset_y + y_dist * 3,
#                         width=bus_width, height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
#
#         grid.add_bus(busL0)
#         l_x_pos.append(busL0.x)
#         l_y_pos.append(busL0.y)
#
#         grid.add_bus(busT0)
#         l_x_pos.append(busT0.x)
#         l_y_pos.append(busT0.y)
#
#         grid.add_bus(busLn)
#         l_x_pos.append(busLn.x)
#         l_y_pos.append(busLn.y)
#
#         grid.add_bus(busTn)
#         l_x_pos.append(busTn.x)
#         l_y_pos.append(busTn.y)
#
#         bus0 = dev.Bus(f"Bus0", substation=substation, Vnom=v_nom, voltage_level=vl,
#                        xpos=offset_x, ypos=offset_y + y_dist * 1, width=bus_width, height=bus_height, country=country,
#                        graphic_type=BusGraphicType.Connectivity)
#         bus1 = dev.Bus(f"Bus1", substation=substation, Vnom=v_nom, voltage_level=vl,
#                        xpos=offset_x, ypos=offset_y + y_dist * 2, width=bus_width, height=bus_height, country=country,
#                        graphic_type=BusGraphicType.Connectivity)
#         bus2 = dev.Bus(f"Bus2", substation=substation, Vnom=v_nom, voltage_level=vl,
#                        xpos=offset_x + (n_positions - 1) * x_dist, ypos=offset_y + y_dist * 1, width=bus_width,
#                        height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
#         bus3 = dev.Bus(f"Bus3", substation=substation, Vnom=v_nom, voltage_level=vl,
#                        xpos=offset_x + (n_positions - 1) * x_dist, ypos=offset_y + y_dist * 2, width=bus_width,
#                        height=bus_height, country=country, graphic_type=BusGraphicType.Connectivity)
#
#         grid.add_bus(bus0)
#         l_x_pos.append(bus0.x)
#         l_y_pos.append(bus0.y)
#
#         grid.add_bus(bus1)
#         l_x_pos.append(bus1.x)
#         l_y_pos.append(bus1.y)
#
#         grid.add_bus(bus2)
#         l_x_pos.append(bus2.x)
#         l_y_pos.append(bus2.y)
#
#         grid.add_bus(bus3)
#         l_x_pos.append(bus3.x)
#         l_y_pos.append(bus3.y)
#
#         bus5 = dev.Bus(f"Bus5", substation=substation, Vnom=v_nom, voltage_level=vl,
#                        xpos=offset_x + x_dist, ypos=offset_y, width=bus_width, height=bus_height, country=country,
#                        graphic_type=BusGraphicType.Connectivity)
#         bus6 = dev.Bus(f"Bus6", substation=substation, Vnom=v_nom, voltage_level=vl,
#                        xpos=offset_x + x_dist * 2, ypos=offset_y, width=bus_width, height=bus_height, country=country,
#                        graphic_type=BusGraphicType.Connectivity)
#         bus7 = dev.Bus(f"Bus7", substation=substation, Vnom=v_nom, voltage_level=vl,
#                        xpos=offset_x + x_dist, ypos=offset_y + y_dist * 3, width=bus_width, height=bus_height,
#                        country=country, graphic_type=BusGraphicType.Connectivity)
#         bus8 = dev.Bus(f"Bus8", substation=substation, Vnom=v_nom, voltage_level=vl,
#                        xpos=offset_x + x_dist * 2, ypos=offset_y + y_dist * 3, width=bus_width, height=bus_height,
#                        country=country, graphic_type=BusGraphicType.Connectivity)
#
#         grid.add_bus(bus5)
#         l_x_pos.append(bus5.x)
#         l_y_pos.append(bus5.y)
#
#         grid.add_bus(bus6)
#         l_x_pos.append(bus6.x)
#         l_y_pos.append(bus6.y)
#
#         grid.add_bus(bus7)
#         l_x_pos.append(bus7.x)
#         l_y_pos.append(bus7.y)
#
#         grid.add_bus(bus8)
#         l_x_pos.append(bus8.x)
#         l_y_pos.append(bus8.y)
#
#         if n_positions > 4:
#             bus9 = dev.Bus(f"Bus9", substation=substation, Vnom=v_nom, voltage_level=vl,
#                            xpos=offset_x + (n_positions - 2) * x_dist, ypos=offset_y, width=bus_width,
#                            height=bus_height,
#                            country=country, graphic_type=BusGraphicType.Connectivity)
#             bus10 = dev.Bus(f"Bus10", substation=substation, Vnom=v_nom, voltage_level=vl,
#                             xpos=offset_x + (n_positions - 2) * x_dist, ypos=offset_y + y_dist * 3, width=bus_width,
#                             height=bus_height,
#                             country=country, graphic_type=BusGraphicType.Connectivity)
#
#             grid.add_bus(bus9)
#             l_x_pos.append(bus9.x)
#             l_y_pos.append(bus9.y)
#
#             grid.add_bus(bus10)
#             l_x_pos.append(bus10.x)
#             l_y_pos.append(bus10.y)
#
#             dis6 = dev.Switch(name=f"Dis5", bus_from=bus9, bus_to=busLn, graphic_type=SwitchGraphicType.Disconnector)
#             dis7 = dev.Switch(name=f"Dis5", bus_from=bus10, bus_to=busTn, graphic_type=SwitchGraphicType.Disconnector)
#
#         else:
#             dis6 = dev.Switch(name=f"Dis5", bus_from=bus6, bus_to=busLn, graphic_type=SwitchGraphicType.Disconnector)
#             dis7 = dev.Switch(name=f"Dis5", bus_from=bus8, bus_to=busTn, graphic_type=SwitchGraphicType.Disconnector)
#
#         dis0 = dev.Switch(name=f"Dis0", bus_from=busL0, bus_to=bus0, graphic_type=SwitchGraphicType.Disconnector)
#         cb0 = dev.Switch(name=f"CB_0", bus_from=bus0, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)
#         dis1 = dev.Switch(name=f"Dis1", bus_from=bus1, bus_to=busT0, graphic_type=SwitchGraphicType.Disconnector)
#
#         dis2 = dev.Switch(name=f"Dis2", bus_from=busLn, bus_to=bus2, graphic_type=SwitchGraphicType.Disconnector)
#         cb1 = dev.Switch(name=f"CB_1", bus_from=bus2, bus_to=bus3, graphic_type=SwitchGraphicType.CircuitBreaker)
#         dis3 = dev.Switch(name=f"Dis3", bus_from=bus3, bus_to=busTn, graphic_type=SwitchGraphicType.Disconnector)
#
#         dis4 = dev.Switch(name=f"Dis4", bus_from=busL0, bus_to=bus5, graphic_type=SwitchGraphicType.Disconnector)
#         cb2 = dev.Switch(name=f"CB_2", bus_from=bus5, bus_to=bus6, graphic_type=SwitchGraphicType.CircuitBreaker)
#
#         dis5 = dev.Switch(name=f"Dis5", bus_from=busT0, bus_to=bus7, graphic_type=SwitchGraphicType.Disconnector)
#         cb3 = dev.Switch(name=f"CB_3", bus_from=bus7, bus_to=bus8, graphic_type=SwitchGraphicType.CircuitBreaker)
#
#         grid.add_switch(dis0)
#         grid.add_switch(cb0)
#         grid.add_switch(dis1)
#         grid.add_switch(dis2)
#         grid.add_switch(cb1)
#         grid.add_switch(dis3)
#         grid.add_switch(dis4)
#         grid.add_switch(cb2)
#         grid.add_switch(dis5)
#         grid.add_switch(cb3)
#         grid.add_switch(dis6)
#         grid.add_switch(dis7)
#
#         for i in range(int(n_positions / 2 - 2)):
#             print('Hola')
#
#         busL0 = dev.Bus(f"{name}_line_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
#                         xpos=offset_x, ypos=offset_y, width=bus_width, height=bus_height, country=country,
#                         graphic_type=BusGraphicType.Connectivity)
#         busT0 = dev.Bus(f"{name}_trafo_conn_0", substation=substation, Vnom=v_nom, voltage_level=vl,
#                         xpos=offset_x, ypos=offset_y + y_dist * 3, width=bus_width, height=bus_height, country=country,
#                         graphic_type=BusGraphicType.Connectivity)
#         # if i + 1 < n_positions:
#         #
#         #     dis1 = dev.Switch(name=f"Dis1_{i}", bus_from=bus1, bus_to=bus2,
#         #                       graphic_type=SwitchGraphicType.Disconnector)
#         #     cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus2, bus_to=bus3,
#         #                      graphic_type=SwitchGraphicType.CircuitBreaker)
#         #     dis2 = dev.Switch(name=f"Dis2_{i}", bus_from=bar, bus_to=bus3,
#         #                       graphic_type=SwitchGraphicType.Disconnector)
#         #
#         # grid.add_bus(bus1)
#         # l_x_pos.append(bus1.x)
#         # l_y_pos.append(bus1.y)
#         #
#         # grid.add_bus(bus2)
#         # l_x_pos.append(bus2.x)
#         # l_y_pos.append(bus2.y)
#         #
#         # grid.add_bus(bus3)
#         # l_x_pos.append(bus3.x)
#         # l_y_pos.append(bus3.y)
#         #
#         # grid.add_switch(dis1)
#         # grid.add_switch(cb1)
#         # grid.add_switch(dis2)
#
#     else:
#
#         bar = dev.Bus(f"{name} bar", substation=substation, Vnom=v_nom, voltage_level=vl,
#                       width=max(n_lines, n_trafos) * bus_width + bus_width * 2 + (x_dist - bus_width) * (
#                           max(n_lines, n_trafos) - 1),
#                       xpos=offset_x - bus_width, ypos=offset_y + y_dist, country=country,
#                       graphic_type=BusGraphicType.BusBar)
#         grid.add_bus(bar)
#         l_x_pos.append(bar.x)
#         l_y_pos.append(bar.y)
#
#         for i in range(n_lines):
#             bus1 = dev.Bus(f"{name}_line_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
#                            xpos=offset_x + i * x_dist, ypos=offset_y, width=bus_width, country=country,
#                            graphic_type=BusGraphicType.Connectivity)
#         cb1 = dev.Switch(name=f"CB_{i}", bus_from=bus1, bus_to=bar, graphic_type=SwitchGraphicType.CircuitBreaker)
#
#         grid.add_bus(bus1)
#         l_x_pos.append(bus1.x)
#         l_y_pos.append(bus1.y)
#
#         grid.add_switch(cb1)
#
#         for i in range(n_trafos):
#             bus1 = dev.Bus(f"{name}_trafo_conn_{i}", substation=substation, Vnom=v_nom, voltage_level=vl,
#                            xpos=offset_x + i * x_dist, ypos=offset_y + y_dist * 2, width=bus_width, country=country,
#                            graphic_type=BusGraphicType.Connectivity)
#         cb1 = dev.Switch(name=f"CB_{i}", bus_from=bar, bus_to=bus1, graphic_type=SwitchGraphicType.CircuitBreaker)
#
#         grid.add_bus(bus1)
#         l_x_pos.append(bus1.x)
#         l_y_pos.append(bus1.y)
#
#         grid.add_switch(cb1)
#
#         offset_total_x = max(l_x_pos, default=0) + x_dist
#         offset_total_y = max(l_y_pos, default=0) + y_dist
#
#     return vl, offset_total_x, offset_total_y


def create_substation(grid: MultiCircuit,
                      se_name: str,
                      se_code: str,
                      lat: float,
                      lon: float,
                      vl_templates: List[dev.VoltageLevelTemplate]) -> Tuple[dev.Substation, List[dev.VoltageLevel]]:
    """

    :param grid:
    :param se_name:
    :param se_code:
    :param lat:
    :param lon:
    :param vl_templates:
    :return: se_object, [vl list]
    """
    # create the SE
    se_object = dev.Substation(name=se_name,
                               code=se_code,
                               latitude=lat,
                               longitude=lon)

    grid.add_substation(obj=se_object)
    # substation_graphics = self.add_api_substation(api_object=se_object, lat=lat, lon=lon)

    voltage_levels = list()

    offset_x = 0
    offset_y = 0
    for vl_template in vl_templates:

        if vl_template.vl_type == SubstationTypes.SingleBar:
            vl, offset_total_x, offset_total_y = create_single_bar(
                name=f"{se_object.name}-@{vl_template.name} @{vl_template.voltage} kV VL",
                grid=grid,
                n_lines=vl_template.n_line_positions,
                n_trafos=vl_template.n_transformer_positions,
                v_nom=vl_template.voltage,
                substation=se_object,
                # country: Country = None,
                include_disconnectors=vl_template.add_disconnectors,
                offset_x=offset_x,
                offset_y=offset_y,
            )
            offset_x = offset_total_x
            offset_y = offset_total_y
            voltage_levels.append(vl)

        elif vl_template.vl_type == SubstationTypes.SingleBarWithBypass:
            vl, offset_total_x, offset_total_y = create_single_bar_with_bypass(
                name=f"{se_object.name}-@{vl_template.name} @{vl_template.voltage} kV VL",
                grid=grid,
                n_lines=vl_template.n_line_positions,
                n_trafos=vl_template.n_transformer_positions,
                v_nom=vl_template.voltage,
                substation=se_object,
                # country: Country = None,
                include_disconnectors=vl_template.add_disconnectors,
                offset_x=offset_x,
                offset_y=offset_y,
            )
            offset_x = offset_total_x
            offset_y = offset_total_y
            voltage_levels.append(vl)

        elif vl_template.vl_type == SubstationTypes.SingleBarWithSplitter:
            vl, offset_total_x, offset_total_y = create_single_bar_with_splitter(
                name=f"{se_object.name}-@{vl_template.name} @{vl_template.voltage} kV VL",
                grid=grid,
                n_lines=vl_template.n_line_positions,
                n_trafos=vl_template.n_transformer_positions,
                v_nom=vl_template.voltage,
                substation=se_object,
                # country: Country = None,
                include_disconnectors=vl_template.add_disconnectors,
                offset_x=offset_x,
                offset_y=offset_y,
            )
            offset_x = offset_total_x
            offset_y = offset_total_y
            voltage_levels.append(vl)

        elif vl_template.vl_type == SubstationTypes.DoubleBar:
            vl, offset_total_x, offset_total_y = create_double_bar(
                name=f"{se_object.name}-@{vl_template.name} @{vl_template.voltage} kV VL",
                grid=grid,
                n_lines=vl_template.n_line_positions,
                n_trafos=vl_template.n_transformer_positions,
                v_nom=vl_template.voltage,
                substation=se_object,
                # country: Country = None,
                include_disconnectors=vl_template.add_disconnectors,
                offset_x=offset_x,
                offset_y=offset_y,
            )
            offset_x = offset_total_x
            offset_y = offset_total_y
            voltage_levels.append(vl)

        elif vl_template.vl_type == SubstationTypes.DoubleBarWithBypass:
            # TODO: Implement
            pass

        elif vl_template.vl_type == SubstationTypes.DoubleBarWithTransference:
            vl, offset_total_x, offset_total_y = create_double_bar_with_transference_bar(
                name=f"{se_object.name}-@{vl_template.name} @{vl_template.voltage} kV VL",
                grid=grid,
                n_lines=vl_template.n_line_positions,
                n_trafos=vl_template.n_transformer_positions,
                v_nom=vl_template.voltage,
                substation=se_object,
                # country: Country = None,
                include_disconnectors=vl_template.add_disconnectors,
                offset_x=offset_x,
                offset_y=offset_y,
            )
            offset_x = offset_total_x
            offset_y = offset_total_y
            voltage_levels.append(vl)

        elif vl_template.vl_type == SubstationTypes.DoubleBarDuplex:
            # TODO: Implement
            pass

        elif vl_template.vl_type == SubstationTypes.Ring:
            vl, offset_total_x, offset_total_y = create_ring(
                name=f"{se_object.name}-@{vl_template.name} @{vl_template.voltage} kV VL",
                grid=grid,
                n_lines=vl_template.n_line_positions,
                n_trafos=vl_template.n_transformer_positions,
                v_nom=vl_template.voltage,
                substation=se_object,
                # country: Country = None,
                include_disconnectors=vl_template.add_disconnectors,
                offset_x=offset_x,
                offset_y=offset_y,
            )
            offset_x = offset_total_x
            offset_y = offset_total_y
            voltage_levels.append(vl)

        elif vl_template.vl_type == SubstationTypes.BreakerAndAHalf:
            vl, offset_total_x, offset_total_y = create_breaker_and_a_half(
                name=f"{se_object.name}-@{vl_template.name} @{vl_template.voltage} kV VL",
                grid=grid,
                n_lines=vl_template.n_line_positions,
                n_trafos=vl_template.n_transformer_positions,
                v_nom=vl_template.voltage,
                substation=se_object,
                # country: Country = None,
                include_disconnectors=vl_template.add_disconnectors,
                offset_x=offset_x,
                offset_y=offset_y,
            )
            offset_x = offset_total_x
            offset_y = offset_total_y
            voltage_levels.append(vl)

        else:
            print(f"{vl_template.vl_type} not implemented :/")

    return se_object, voltage_levels
