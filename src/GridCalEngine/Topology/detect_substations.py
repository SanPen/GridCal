# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Union, TYPE_CHECKING
import numpy as np
import GridCalEngine.Devices as dev
from GridCalEngine import DeviceType
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.Topology.topology import find_islands, get_adjacency_matrix
from GridCalEngine.basic_structures import IntVec
from scipy.sparse import lil_matrix

if TYPE_CHECKING:
    from GridCalEngine.Devices.multi_circuit import MultiCircuit


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
    branches: List[BRANCH_TYPES] = list()
    reducible_types = [
        DeviceType.Transformer2WDevice,
        DeviceType.WindingDevice,
        DeviceType.SeriesReactanceDevice,
        DeviceType.VscDevice
    ]  # these are devices that are supposed to "live" within a substation

    for br in grid.get_branches(add_hvdc=True, add_vsc=True, add_switch=True):
        if br.reducible or br.device_type in reducible_types:
            branches.append(br)
        elif br.device_type == DeviceType.LineDevice:
            if br.R > 0.0 or br.X > 0.0:
                if (br.R + br.X) <= r_x_threshold:
                    branches.append(br)

    # build the connectivity matrix
    nbr = len(branches)
    nbus = grid.get_bus_number()
    bus_dict = grid.get_bus_index_dict()

    # declare the matrices
    Cf = lil_matrix((nbr, nbus))
    Ct = lil_matrix((nbr, nbus))
    br_active = np.ones(nbr, dtype=int)  # we will consider all branches as active for this
    bus_active = np.ones(nbus, dtype=int)

    # fill matrices appropriately
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


def detect_facilities(grid: MultiCircuit) -> None:
    """
    Create facilities automatically
    In essence is packing all the injections connected to the same bus into a facility object
    :param grid: MultiCircuit
    """
    dict_bus_inj = grid.get_injection_devices_grouped_by_bus()

    for bus, inj_list in dict_bus_inj.items():

        if len(inj_list):
            lon, lat = bus.try_to_find_coordinates()
            plant = dev.Facility(name=f"Facility at bus {bus.name}", longitude=lon, latitude=lat)
            grid.add_facility(obj=plant)

            for elm in inj_list:
                elm.facility = plant
