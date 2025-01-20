# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Dict
from GridCalEngine.IO.ucte.devices.circuit import UCTECircuit
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as dev


def parse_nodes(ucte_grid: UCTECircuit, grid: MultiCircuit) -> Dict[str, dev.Bus]:
    """

    :param ucte_grid:
    :param grid:
    :return:
    """
    bus_dict: Dict[str, dev.Bus] = dict()

    # create technologies
    # H: hydro, N: nuclear, L: lignite,
    # C: hard coal, G: gas, O: oil, W: wind, F: further
    tech_dict = {
        "H": dev.Technology(name="Hydro"),
        "N": dev.Technology(name="Nuclear"),
        "L": dev.Technology(name="lignite"),
        "C": dev.Technology(name="hard coal"),
        "G": dev.Technology(name="Gas"),
        "O": dev.Technology(name="Oil"),
        "W": dev.Technology(name="Wind"),
        "F": dev.Technology(name="further"),
    }
    for key, elm in tech_dict.items():
        grid.add_technology(obj=elm)

    # create buses
    for ucte_elm in ucte_grid.nodes:
        elm = dev.Bus(
            name=ucte_elm.geo_name,
            code=ucte_elm.node_code,
            active=bool(ucte_elm.status),
            is_slack=ucte_elm.node_type == 3,
            Vnom=ucte_elm.voltage,
        )

        if ucte_elm.has_load():

            # create load
            ld = dev.Load(
                name=elm.code,
                P=ucte_elm.active_load,
                Q=ucte_elm.reactive_load,
            )
            grid.add_load(bus=elm, api_obj=ld)

        if ucte_elm.has_gen():

            # Create generator
            gen = dev.Generator(
                name=elm.code,
                P=ucte_elm.active_gen,
                Pmin=ucte_elm.min_gen_mw,
                Pmax=ucte_elm.max_gen_mw,
                Qmin=ucte_elm.min_gen_mvar,
                Qmax=ucte_elm.max_gen_mvar,
            )

            # get the technology
            tech = tech_dict.get(ucte_elm.plant_type, None)
            if tech is not None:
                gen.associate_technology(tech, 1.0)

            grid.add_generator(bus=elm, api_obj=gen)

        # add bus
        grid.add_bus(obj=elm)

        # store in the dictionary for later
        bus_dict[elm.code] = elm

    return bus_dict


def parse_lines(ucte_grid: UCTECircuit, grid: MultiCircuit, bus_dict: Dict[str, dev.Bus]):
    pass


def parse_transformer(ucte_grid: UCTECircuit, grid: MultiCircuit, bus_dict: Dict[str, dev.Bus]):
    pass


def parse_transformer_regulation(ucte_grid: UCTECircuit, grid: MultiCircuit, bus_dict: Dict[str, dev.Bus]):
    pass


def parse_transformers_special(ucte_grid: UCTECircuit, grid: MultiCircuit, bus_dict: Dict[str, dev.Bus]):
    pass


def parse_exchange_power(ucte_grid: UCTECircuit, grid: MultiCircuit, bus_dict: Dict[str, dev.Bus]):
    pass


def convert_ucte_to_gridcal(ucte_grid: UCTECircuit) -> MultiCircuit:
    """
    Convert UCTE grid to GridCal
    :param ucte_grid: UCTECircuit
    :return: MultiCircuit
    """
    grid = MultiCircuit()
    grid.fBase = 50.0  # we're on europe
    grid.Sbase = 100.0
    grid.comments = ucte_grid.fuse_comments()

    bus_dict: Dict[str, dev.Bus] = parse_nodes(ucte_grid=ucte_grid, grid=grid)
    parse_lines(ucte_grid=ucte_grid, grid=grid, bus_dict=bus_dict)
    parse_transformer(ucte_grid=ucte_grid, grid=grid, bus_dict=bus_dict)
    parse_transformer_regulation(ucte_grid=ucte_grid, grid=grid, bus_dict=bus_dict)
    parse_transformers_special(ucte_grid=ucte_grid, grid=grid, bus_dict=bus_dict)
    parse_exchange_power(ucte_grid=ucte_grid, grid=grid, bus_dict=bus_dict)

    return grid
