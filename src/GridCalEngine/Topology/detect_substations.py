# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

from typing import List, Union
import numpy as np
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Topology.topology import find_islands, get_adjacency_matrix
from GridCalEngine.basic_structures import IntVec, Logger
from scipy.sparse import lil_matrix


def get_bus_group_substation(bus_indices: IntVec, buses: List[dev.Bus]) -> Union[dev.Substation, None]:
    """
    Given a list of buses, return the first substation available
    :param bus_indices:
    :param buses: list of bus objects
    :return:
    """

    for i in bus_indices:
        bus = buses[i]
        if bus.substation is not None:
            return bus.substation
    return None


def detect_substations(grid: MultiCircuit, r_x_threshold=1e-3) -> None:
    """
    Given a Grid with buses, it will detect all the missing substations and voltage levels
    :param grid: MultiCircuit
    :param r_x_threshold: sum of r+x under which a line is considered a jumper
    :return: (in-place)
    """
    buses = grid.get_buses()

    # create a connectivity matrix only with transformers and lines with small (r+x)
    branches: List[BRANCH_TYPES] = grid.get_transformers2w() + grid.get_windings()
    for line in grid.get_lines():
        if (line.R + line.X) <= r_x_threshold:
            branches.append(line)

    # build the connectivity matrix
    nbr = len(branches)
    nbus = grid.get_bus_number()
    bus_dict = grid.get_bus_index_dict()

    # declare the matrices
    Cf = lil_matrix((nbr, nbus))
    Ct = lil_matrix((nbr, nbus))
    br_active = np.ones(nbr, dtype=int)  # we will consider all branches as active for this
    bus_active = np.ones(nbus, dtype=int)

    # fill matrices approprietly
    for i, elm in enumerate(branches):
        if elm.bus_from is not None:
            f = bus_dict[elm.bus_from]
            Cf[i, f] = 1

        if elm.bus_to is not None:
            t = bus_dict[elm.bus_to]
            Ct[i, t] = 1

    # compose the adjacency matrix from the connectivity information
    A = get_adjacency_matrix(C_branch_bus_f=Cf.tocsc(),
                             C_branch_bus_t=Ct.tocsc(),
                             branch_active=br_active,
                             bus_active=bus_active)

    # perform the topology search, each island is a substation
    islands = find_islands(adj=A, active=bus_active)

    for is_idx, island in enumerate(islands):
        bus0 = grid.get_buses()[island[0]]

        sub = get_bus_group_substation(bus_indices=island, buses=buses)

        if sub is None:
            sub = dev.Substation(name=bus0.name,
                                 latitude=bus0.latitude,
                                 longitude=bus0.longitude,
                                 area=bus0.area if bus0.area is not None else None,
                                 zone=bus0.zone if bus0.zone is not None else None,
                                 country=bus0.country if bus0.country is not None else None)
            grid.add_substation(sub)

        # set the substation, and get the different voltages
        voltages = set()
        for i in island:
            bus = buses[i]
            bus.substation = sub
            voltages.add(bus.Vnom)

        # add the voltage levels
        voltages_vl = dict()
        for voltage in voltages:
            vl = dev.VoltageLevel(name=sub.name + f"_{int(voltage)}",
                                  Vnom=voltage,
                                  substation=sub)
            grid.add_voltage_level(vl)
            voltages_vl[voltage] = vl

        # assign the VL's
        for i in island:
            bus = buses[i]
            bus.voltage_level = voltages_vl[bus.Vnom]
