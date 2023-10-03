# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

from typing import Any, Dict, Tuple
import json
import numpy as np

from GridCalEngine.Core import Zone, Area
from GridCalEngine.basic_structures import Logger, CompressedJsonStruct
import GridCalEngine.Core.Devices as dev
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.raw.raw_parser_legacy import get_psse_transformer_impedances


# ----------------------------------------------------------------------------------------------------------------------
def parse_circuit(circuit: MultiCircuit, block: CompressedJsonStruct):
    """

    :param circuit:
    :param block:
    :return:
    """
    # ["ic", "sbase", "rev", "xfrrat", "nxfrat", "basfrq", "title1", "title2"]
    data = block.get_dict_at(0)
    circuit.fBase = data['basfrq']
    circuit.Sbase = data['sbase']
    circuit.name = data['title1']
    circuit.comments = str(data['title1']) + "\n" + str(data['title2'])


def get_circuit_block(circuit: MultiCircuit, fields) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(1)
    block.set_at(0, 'basfrq', circuit.fBase)
    block.set_at(0, 'sbase', circuit.Sbase)
    block.set_at(0, 'title1', circuit.name)
    return block


# ----------------------------------------------------------------------------------------------------------------------
def parse_areas(circuit: MultiCircuit, block: CompressedJsonStruct) -> dict[str, Area | Any]:
    """
    Parse PSSe areas
    :param circuit: Multi-circuit
    :param block: block to parse
    :return: dictionary to match the PSSe area code to the actual area object
    """
    # "iarea", "isw", "pdes", "ptol", "arname"
    area_dict = dict()

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)
        area = dev.Area()
        area.code = data['iarea']
        # area.code = data['isw']  # swing bus -> 0
        # area.code = data['pdes']  # desired exchange (MW) -> 0
        # area.code = data['ptol']  # tolerance (MW) -> 99999
        area.name = data['arname']

        circuit.add_area(area)
        area_dict[area.code] = area

    return area_dict


def get_areas_block(circuit: MultiCircuit, fields) -> CompressedJsonStruct:
    """
    Generate PSSe areas from the GridCal Areas
    :param circuit: Multi-circuit
    :param fields:
    :return: CompressedJsonStruct block
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_area_number())

    for i, area in enumerate(circuit.get_areas()):
        # "iarea", "isw", "pdes", "ptol", "arname"
        block.set_at(i, 'iarea', i + 1)
        block.set_at(i, 'isw', 0)
        block.set_at(i, 'pdes', 0)
        block.set_at(i, 'ptol', 99999)
        block.set_at(i, 'arname', area.name)

    return block


# ----------------------------------------------------------------------------------------------------------------------
def parse_zones(circuit: MultiCircuit, block: CompressedJsonStruct) -> dict[str, Zone | Any]:
    """
    Parse PSSe areas
    :param circuit: Multi-circuit
    :param block: block to parse
    :return: dictionary to match the PSSe area code to the actual area object
    """
    # "izone", "zoname"
    area_zone = dict()

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)
        zone = dev.Zone()
        zone.code = data['izone']
        zone.name = data['zoname']

        circuit.add_zone(zone)
        area_zone[zone.code] = zone

    return area_zone


def get_zones_block(circuit: MultiCircuit, fields) -> CompressedJsonStruct:
    """
    Generate PSSe areas from the GridCal Areas
    :param circuit: Multi-circuit
    :param fields:
    :return: CompressedJsonStruct block
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_zone_number())

    for i, area in enumerate(circuit.get_zones()):
        # "izone", "zoname"
        block.set_at(i, 'izone', i + 1)
        block.set_at(i, 'zoname', area.name)

    return block


# ----------------------------------------------------------------------------------------------------------------------
def parse_buses(circuit: MultiCircuit, block: CompressedJsonStruct) \
        -> Tuple[Dict[int, Any], Dict[Any, Tuple[int, int]]]:
    """

    :param circuit:
    :param block:
    :return:
    """
    # ["ibus", "name", "baskv", "ide", "area", "zone", "owner", "vm", "va", "nvhi", "nvlo", "evhi", "evlo"]
    bus_dict = dict()
    bus_area = dict()
    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)
        bus = dev.Bus()
        bus.code = data['ibus']
        bus.name = data['name']
        bus.Vnom = data['baskv']

        if data['ide'] == 4:
            bus.active = False
        elif data['ide'] == 3:
            bus.is_slack = True

        # dictionary with the psse index and the bus object
        bus_dict[data['ibus']] = bus

        # keep the relation to the areas and zones to match properly later
        bus_area[bus] = (data['area'], data['zone'])

        # add to the circuit
        circuit.add_bus(bus)

    return bus_dict, bus_area


def get_buses_block(circuit: MultiCircuit, fields) -> Tuple[CompressedJsonStruct, Dict[Any, int]]:
    """

    :param circuit:
    :param fields:
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_bus_number())

    areas_dict = {elm: i+1 for i, elm in enumerate(circuit.get_areas())}
    zones_dict = {elm: i+1 for i, elm in enumerate(circuit.get_zones())}
    se_dict = {elm: i+1 for i, elm in enumerate(circuit.get_substations())}
    rev_bus_dict = dict()

    for i, bus in enumerate(circuit.get_buses()):
        # ["ibus", "name", "baskv", "ide", "area", "zone", "owner", "vm", "va", "nvhi", "nvlo", "evhi", "evlo"]

        bus_tpe = bus.determine_bus_type().value
        if not bus.active:
            bus_tpe = 4

        i_area = areas_dict[bus.area]
        i_zone = zones_dict[bus.zone]

        try:
            i_psse = int(bus.code)
        except:
            i_psse = i + 1

        block.set_at(i, 'ibus', i_psse)
        block.set_at(i, 'ibus', i_psse)
        block.set_at(i, 'name', bus.name[:12])
        block.set_at(i, 'baskv', bus.Vnom)
        block.set_at(i, 'ide', bus_tpe)
        block.set_at(i, 'area', i_area)
        block.set_at(i, 'zone', i_zone)
        block.set_at(i, 'owner', 1)

        block.set_at(i, 'vm', 1.0)
        block.set_at(i, 'va', 0)

        block.set_at(i, 'nvhi', 1.1)
        block.set_at(i, 'nvlo', 0.9)

        block.set_at(i, 'evhi', 1.1)
        block.set_at(i, 'evlo', 0.9)

        rev_bus_dict[bus] = i_psse

    return block, rev_bus_dict


# ----------------------------------------------------------------------------------------------------------------------
def get_loads_block(circuit: MultiCircuit, fields, rev_bus_dict: Dict[Any, int]) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :param rev_bus_dict: dictionary of buses and their assigned psse number
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_bus_number())

    areas_dict = {elm: i+1 for i, elm in enumerate(circuit.get_areas())}
    zones_dict = {elm: i+1 for i, elm in enumerate(circuit.get_zones())}

    i = 0
    for k, bus in enumerate(circuit.get_buses()):
        for k2, elm in enumerate(bus.loads):

            block.set_at(i, "ibus", rev_bus_dict[elm.bus])
            block.set_at(i,  "loadid", k2 + 1)
            block.set_at(i,  "stat", int(elm.active))
            block.set_at(i,  "area", areas_dict[elm.bus.area])
            block.set_at(i,  "zone", zones_dict[elm.bus.zone])
            block.set_at(i,  "pl", elm.P)
            block.set_at(i,  "ql", elm.Q)
            block.set_at(i,  "ip", elm.Ir)
            block.set_at(i,  "iq", elm.Ii)
            block.set_at(i,  "yp", elm.G)
            block.set_at(i,  "yq", elm.B)
            block.set_at(i,  "owner", 0)
            block.set_at(i,  "scale", 0)  # scale yes/no
            block.set_at(i,  "intrpt", 0)
            block.set_at(i,  "dgenp", 0)
            block.set_at(i,  "dgenq", 0)
            block.set_at(i,  "dgenm", 0)
            block.set_at(i,  "loadtype", 0)

            i += 1

    return block


def parse_loads(circuit: MultiCircuit, block: CompressedJsonStruct, buses_dict: Dict[int, Any]):
    """

    :param circuit:
    :param block:
    :param buses_dict:
    :return:
    """

    # ["ibus", "loadid", "stat", "area", "zone", "pl", "ql", "ip", "iq", "yp", "yq",
    # "owner", "scale", "intrpt", "dgenp", "dgenq", "dgenm", "loadtype"]

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)

        elm = dev.Load()

        elm.bus = buses_dict[data['ibus']]
        elm.code = "{0}_{1}".format(elm.bus.code, data['loadid'])
        elm.active = bool(data['stat'])

        elm.P = data['pl']
        elm.Q = data['ql']

        elm.Ir = data['ip']
        elm.Ii = data['iq']

        elm.G = data['yp']
        elm.B = data['yq']

        circuit.add_load(elm.bus, elm)


# ----------------------------------------------------------------------------------------------------------------------
def get_fixed_shunts_block(circuit: MultiCircuit, fields, rev_bus_dict: Dict[Any, int]) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :param rev_bus_dict: dictionary of buses and their assigned psse number
    :return:
    """
    block = CompressedJsonStruct(fields=fields)

    n = 0
    for k, bus in enumerate(circuit.get_buses()):
        for k2, elm in enumerate(bus.shunts):
            if not elm.is_controlled:
                n += 1

    block.declare_n_entries(n)

    # "ibus", "shntid", "stat", "gl", "bl"
    i = 0
    for k, bus in enumerate(circuit.get_buses()):
        for k2, elm in enumerate(bus.shunts):

            if not elm.is_controlled:
                block.set_at(i, "ibus", rev_bus_dict[elm.bus])
                block.set_at(i,  "shntid", k2 + 1)
                block.set_at(i,  "stat", int(elm.active))
                block.set_at(i,  "gl", elm.G)
                block.set_at(i,  "bl", elm.B)

                i += 1

    return block


def parse_fixed_shunts(circuit: MultiCircuit, block: CompressedJsonStruct, buses_dict: Dict[int, Any]):
    """

    :param circuit:
    :param block:
    :param buses_dict:
    :return:
    """

    # "ibus", "shntid", "stat", "gl", "bl"

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)

        elm = dev.Shunt()

        elm.bus = buses_dict[data['ibus']]
        elm.code = "{0}_{1}".format(elm.bus.code, data['shntid'])
        elm.active = bool(data['stat'])
        elm.is_controlled = False
        elm.G = data['gl']
        elm.B = data['bl']

        circuit.add_shunt(elm.bus, elm)


def parse_switched_shunts(circuit: MultiCircuit, block: CompressedJsonStruct, buses_dict: Dict[int, Any]):
    """

    :param circuit:
    :param block:
    :param buses_dict:
    :return:
    """

    # "ibus", "shntid", "modsw", "adjm", "stat", "vswhi", "vswlo", "swreg", "nreg",
    # "rmpct", "rmidnt", "binit", "s1", "n1", "b1", "s2", "n2", "b2", "s3", "n3", "b3",
    # "s4", "n4", "b4", "s5", "n5", "b5", "s6", "n6", "b6", "s7", "n7", "b7", "s8", "n8", "b8"

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)

        elm = dev.Shunt()

        elm.bus = buses_dict[data['ibus']]
        elm.code = "{0}_{1}".format(elm.bus.code, data['shntid'])
        elm.active = bool(data['stat'])
        elm.is_controlled = True

        g = 0.0
        if data['modsw'] in [1, 2]:
            b = data['binit'] * data['rmpct'] / 100.0
        else:
            b = data['binit']

        elm.G = g
        elm.B = b

        circuit.add_shunt(elm.bus, elm)


# ----------------------------------------------------------------------------------------------------------------------
def get_generators_block(circuit: MultiCircuit, fields, rev_bus_dict: Dict[Any, int]) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :param rev_bus_dict:
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_bus_number())

    for i, elm in enumerate(circuit.get_generators()):

        if "_" in elm.code:
            machine_id = elm.code.split("_")[1]
        else:
            machine_id = ""

        block.set_at(i, "ibus", rev_bus_dict[elm.bus])
        block.set_at(i,  "machid", machine_id)
        block.set_at(i,  "pg", elm.P)
        block.set_at(i,  "qg", 0)
        block.set_at(i,  "qt", elm.Qmax)
        block.set_at(i,  "qb", elm.Qmin)
        block.set_at(i,  "vs", elm.Vset)
        block.set_at(i,  "ireg", 0)
        block.set_at(i,  "nreg", 0)
        block.set_at(i,  "mbase", elm.Snom)
        block.set_at(i,  "zr", 0)
        block.set_at(i,  "zx", 0)
        block.set_at(i,  "rt", 0)
        block.set_at(i,  "xt", 0)
        block.set_at(i,  "gtap", 0)
        block.set_at(i,  "stat", int(elm.active))
        block.set_at(i,  "rmpct", 0)
        block.set_at(i,  "pt", elm.Pmax)
        block.set_at(i,  "pb", elm.Pmin)
        block.set_at(i,  "baslod", 0)
        block.set_at(i,  "o1", None)
        block.set_at(i,  "f1", None)
        block.set_at(i,  "o2", None)
        block.set_at(i,  "f2", None)
        block.set_at(i,  "o3", None)
        block.set_at(i,  "f3", None)
        block.set_at(i,  "o4", None)
        block.set_at(i,  "f4", None)
        block.set_at(i,  "wmod", 0)
        block.set_at(i,  "wpf", 0)

    return block


def parse_generators(circuit: MultiCircuit, block: CompressedJsonStruct, buses_dict: Dict[int, Any]):
    """

    :param circuit:
    :param block:
    :param buses_dict:
    :return:
    """
    # "ibus", "machid", "pg", "qg", "qt", "qb", "vs", "ireg", "nreg", "mbase",
    # "zr", "zx", "rt", "xt", "gtap", "stat", "rmpct", "pt", "pb", "baslod",
    # "o1", "f1", "o2", "f2", "o3", "f3", "o4", "f4", "wmod", "wpf"

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)

        elm = dev.Generator()

        elm.bus = buses_dict[data['ibus']]
        elm.active = bool(data['stat'])
        elm.code = "{0}_{1}".format(elm.bus.code, data['machid'])
        elm.P = data['pg']
        elm.Vset = data['vs']
        elm.pf = 0.8  # data['ql']

        elm.Qmin = data['qb']
        elm.Qmax = data['qt']
        elm.Snom = data['mbase']
        elm.Pmin = data['pb']
        elm.Pmax = data['pt']

        circuit.add_generator(elm.bus, elm)


# ----------------------------------------------------------------------------------------------------------------------
def get_ac_lines_block(circuit: MultiCircuit, fields, rev_bus_dict: Dict[Any, int]) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :param rev_bus_dict:
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_bus_number())

    for i, elm in enumerate(circuit.get_lines()):

        if "_" in elm.code:
            ckt = elm.code.split("_")[2]
        else:
            ckt = "1"

        block.set_at(i,  "ibus", rev_bus_dict[elm.bus_from])
        block.set_at(i,   "jbus", rev_bus_dict[elm.bus_to])
        block.set_at(i,   "ckt", ckt)
        block.set_at(i,   "rpu", elm.R)
        block.set_at(i,   "xpu", elm.X)
        block.set_at(i,   "bpu", elm.B)
        block.set_at(i,   "name", elm.name)
        block.set_at(i,   "rate1", elm.rate)
        block.set_at(i,   "rate2", elm.rate * elm.contingency_factor)
        block.set_at(i,   "rate3", elm.rate)
        block.set_at(i,   "rate4", elm.rate)
        block.set_at(i,   "rate5", elm.rate)
        block.set_at(i,   "rate6", elm.rate)
        block.set_at(i,   "rate7", elm.rate)
        block.set_at(i,   "rate8", elm.rate)
        block.set_at(i,   "rate9", elm.rate)
        block.set_at(i,   "rate10", elm.rate)
        block.set_at(i,   "rate11", elm.rate)
        block.set_at(i,   "rate12", elm.rate)
        block.set_at(i,   "gi", 0)
        block.set_at(i,   "bi", 0)
        block.set_at(i,   "gj", 0)
        block.set_at(i,   "bj", 0)
        block.set_at(i,   "stat", int(elm.active))
        block.set_at(i,   "met", None)
        block.set_at(i,   "len", elm.length)
        block.set_at(i,   "o1", None)
        block.set_at(i,   "f1", None)
        block.set_at(i,   "o2", None)
        block.set_at(i,   "f2", None)
        block.set_at(i,   "o3", None)
        block.set_at(i,   "f3", None)
        block.set_at(i,   "o4", None)
        block.set_at(i,   "f4", None)

        return block


def parse_ac_lines(circuit: MultiCircuit, block: CompressedJsonStruct, buses_dict: Dict[int, Any], logger: Logger):
    """

    :param circuit:
    :param block:
    :param buses_dict:
    :param logger
    :return:
    """
    # "ibus", "jbus", "ckt", "rpu", "xpu", "bpu", "name",
    # "rate1", "rate2", "rate3", "rate4", "rate5", "rate6", "rate7", "rate8", "rate9", "rate10", "rate11", "rate12",
    # "gi", "bi", "gj", "bj", "stat", "met", "len",
    # "o1", "f1", "o2", "f2", "o3", "f3", "o4", "f4"]

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)

        elm = dev.Line()

        elm.bus_from = buses_dict[data['ibus']]
        elm.bus_to = buses_dict[data['jbus']]
        elm.active = bool(data['stat'])

        code = "{0}_{1}_{2}".format(elm.bus_from.code, elm.bus_to.code, data['ckt'])
        elm.code = code

        elm.name = str(data['name']).strip()
        if elm.name == '':
            elm.name = code

        elm.length = data['len']

        elm.rate = data['rate1']
        if float(data['rate2']) != 0:
            elm.contingency_factor = float(data['rate1']) / float(data['rate2'])

        elm.R = data['rpu']
        elm.X = data['xpu']
        elm.B = data['bpu']

        circuit.add_line(elm, logger=logger)

        # add the lie compensations as shunt devices

        if data['gi'] != 0 or data['bi'] != 0:
            sh1 = dev.Shunt(name='Line compensation', code=code, G=data['gi'], B=data['bi'])
            circuit.add_shunt(elm.bus_from, sh1)

        if data['gj'] != 0 or data['bj'] != 0:
            sh1 = dev.Shunt(name='Line compensation', code=code, G=data['gj'], B=data['bj'])
            circuit.add_shunt(elm.bus_to, sh1)


# ----------------------------------------------------------------------------------------------------------------------
def get_twotermdc_block(circuit: MultiCircuit, fields, rev_bus_dict: Dict[Any, int]) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :param rev_bus_dict:
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_hvdc_number())

    for i, elm in enumerate(circuit.get_hvdc()):

        block.set_at(i, "name", elm.name)
        block.set_at(i,  "mdc", 1)
        block.set_at(i,  "rdc", elm.R)
        block.set_at(i,  "setvl", elm.Pset)
        block.set_at(i,  "vschd", None)
        block.set_at(i,  "vcmod", None)
        block.set_at(i,  "rcomp", None)
        block.set_at(i,  "delti", None)
        block.set_at(i,  "met", None)
        block.set_at(i,  "dcvmin", None)
        block.set_at(i,  "cccitmx", None)
        block.set_at(i,  "cccacc", None)
        block.set_at(i,  "ipr", rev_bus_dict[elm.bus_from])
        block.set_at(i,  "nbr", None)
        block.set_at(i,  "anmxr", elm.max_firing_angle_f)
        block.set_at(i,  "anmnr", elm.min_firing_angle_f)
        block.set_at(i,  "rcr", None)
        block.set_at(i,  "xcr", None)
        block.set_at(i,  "ebasr", None)
        block.set_at(i,  "trr", None)
        block.set_at(i,  "tapr", None)
        block.set_at(i,  "tmxr", None)
        block.set_at(i,  "tmnr", None)
        block.set_at(i,  "stpr", None)
        block.set_at(i,  "icr", None)
        block.set_at(i,  "ndr", None)
        block.set_at(i,  "ifr", None)
        block.set_at(i,  "itr", None)
        block.set_at(i,  "idr", None)
        block.set_at(i,  "xcapr", None)
        block.set_at(i,  "ipi", rev_bus_dict[elm.bus_to])
        block.set_at(i,  "nbi", None)
        block.set_at(i,  "anmxi", elm.max_firing_angle_t)
        block.set_at(i,  "anmni", elm.min_firing_angle_t)
        block.set_at(i,  "rci", None)
        block.set_at(i,  "xci", None)
        block.set_at(i,  "ebasi", None)
        block.set_at(i,  "tri", None)
        block.set_at(i,  "tapi", None)
        block.set_at(i,  "tmxi", None)
        block.set_at(i,  "tmni", None)
        block.set_at(i,  "stpi", None)
        block.set_at(i,  "ici", None)
        block.set_at(i,  "ndi", None)
        block.set_at(i,  "ifi", None)
        block.set_at(i,  "iti", None)
        block.set_at(i,  "idi", None)
        block.set_at(i,  "xcapi", None)

        return block


def parse_twotermdc_lines(circuit: MultiCircuit, block: CompressedJsonStruct, buses_dict: Dict[int, Any]):
    """

    :param circuit:
    :param block:
    :param buses_dict:
    :return:
    """
    # "name", "mdc", "rdc", "setvl", "vschd", "vcmod", "rcomp", "delti", "met",
    # "dcvmin", "cccitmx", "cccacc", "ipr", "nbr", "anmxr", "anmnr", "rcr", "xcr",
    # "ebasr", "trr", "tapr", "tmxr", "tmnr", "stpr", "icr", "ndr", "ifr", "itr", "idr",
    # "xcapr", "ipi", "nbi", "anmxi", "anmni", "rci", "xci", "ebasi", "tri", "tapi", "tmxi",
    # "tmni", "stpi", "ici", "ndi", "ifi", "iti", "idi", "xcapi"

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)

        bus_from = buses_dict[data['ipr']]
        bus_to = buses_dict[data['ipi']]
        code = "{0}_{1}_{2}".format(bus_from.code, bus_to.code, '1')
        name1 = str(data['name']).replace("'", "").replace('"', "").replace('/', '').strip()
        if name1 == '':
            name1 = code

        if data['mdc'] == 1 or data['mdc'] == 0:
            # SETVL is in MW
            specified_power = data['setvl']
        elif data['mdc'] == 2:
            # SETVL is in A, specified_power in MW
            specified_power = data['setvl'] * data['vschd'] / 1000.0
        else:
            # doesn't say, so zero
            specified_power = 0.0

        z_base = data['vschd'] * data['vschd'] / circuit.Sbase
        r_pu = data['rdc'] / z_base

        Vset_f = 1.0
        Vset_t = 1.0

        # set the HVDC line active
        active = bus_from.active and bus_to.active

        obj = dev.HvdcLine(bus_from=bus_from,  # Rectifier as of PSSe
                           bus_to=bus_to,  # inverter as of PSSe
                           active=active,
                           name=name1,
                           idtag=code,
                           Pset=specified_power,
                           Vset_f=Vset_f,
                           Vset_t=Vset_t,
                           rate=specified_power,
                           r=r_pu,
                           min_firing_angle_f=np.deg2rad(data['anmnr']),
                           max_firing_angle_f=np.deg2rad(data['anmxr']),
                           min_firing_angle_t=np.deg2rad(data['anmni']),
                           max_firing_angle_t=np.deg2rad(data['anmxi']))

        circuit.add_hvdc(obj)


# ----------------------------------------------------------------------------------------------------------------------
def get_transformers_block(circuit: MultiCircuit, fields, rev_bus_dict: Dict[Any, int]) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :param rev_bus_dict:
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_bus_number())

    for i, elm in enumerate(circuit.get_transformers2w()):

        if "_" in elm.code:
            ckt = elm.code.split("_")[2]
        else:
            ckt = "1"

        v1, v2 = elm.get_from_to_nominal_voltages()

        block.set_at(i,  "ibus", rev_bus_dict[elm.bus_from])
        block.set_at(i,   "jbus", rev_bus_dict[elm.bus_to])
        block.set_at(i,   "kbus", 0)
        block.set_at(i,   "ckt", str(ckt))
        block.set_at(i,   "cw", 1)
        block.set_at(i,   "cz", 1)
        block.set_at(i,   "cm", 1)
        block.set_at(i,   "mag1", 0)
        block.set_at(i,   "mag2", 0)
        block.set_at(i,   "nmet", 2)
        block.set_at(i,   "name", elm.name)
        block.set_at(i,   "stat", int(elm.active))
        block.set_at(i,   "o1", None)
        block.set_at(i,   "f1", None)
        block.set_at(i,   "o2", None)
        block.set_at(i,   "f2", None)
        block.set_at(i,   "o3", None)
        block.set_at(i,   "f3", None)
        block.set_at(i,   "o4", None)
        block.set_at(i,   "f4", None)
        block.set_at(i,   "vecgrp", "")
        block.set_at(i,   "zcod", None)
        block.set_at(i,   "r1_2", elm.R)
        block.set_at(i,   "x1_2", elm.X)
        block.set_at(i,   "sbase1_2", 100)
        block.set_at(i,   "r2_3", 0)
        block.set_at(i,   "x2_3", 0)
        block.set_at(i,   "sbase2_3", 0)
        block.set_at(i,   "r3_1", 0)
        block.set_at(i,   "x3_1", 0)
        block.set_at(i,   "sbase3_1", 0)
        block.set_at(i,   "vmstar", 0)
        block.set_at(i,   "anstar", 0)
        block.set_at(i,   "windv1", elm.tap_module)
        block.set_at(i,   "nomv1", 1.0)
        block.set_at(i,   "ang1", elm.tap_phase)
        block.set_at(i,   "wdg1rate1", elm.rate)
        block.set_at(i,   "wdg1rate2", elm.rate)
        block.set_at(i,   "wdg1rate3", elm.rate)
        block.set_at(i,   "wdg1rate4", elm.rate)
        block.set_at(i,   "wdg1rate5", elm.rate)
        block.set_at(i,   "wdg1rate6", elm.rate)
        block.set_at(i,   "wdg1rate7", elm.rate)
        block.set_at(i,   "wdg1rate8", elm.rate)
        block.set_at(i,   "wdg1rate9", elm.rate)
        block.set_at(i,   "wdg1rate10", elm.rate)
        block.set_at(i,   "wdg1rate11", elm.rate)
        block.set_at(i,   "wdg1rate12", elm.rate)
        block.set_at(i,   "cod1", 0)
        block.set_at(i,   "cont1", 0)
        block.set_at(i,   "node1", 0)
        block.set_at(i,   "rma1", elm.tap_module)
        block.set_at(i,   "rmi1", elm.tap_module)
        block.set_at(i,   "vma1", 1.1)
        block.set_at(i,   "vmi1", 0.9)
        block.set_at(i,   "ntp1", None)
        block.set_at(i,   "tab1", 0)
        block.set_at(i,   "cr1", 0)
        block.set_at(i,   "cx1", 0)
        block.set_at(i,   "cnxa1", 0)
        block.set_at(i,   "windv2", 1.0)
        block.set_at(i,   "nomv2", v2)
        block.set_at(i,   "ang2", None)
        block.set_at(i,   "wdg2rate1", None)
        block.set_at(i,   "wdg2rate2", None)
        block.set_at(i,   "wdg2rate3", None)
        block.set_at(i,   "wdg2rate4", None)
        block.set_at(i,   "wdg2rate5", None)
        block.set_at(i,   "wdg2rate6", None)
        block.set_at(i,   "wdg2rate7", None)
        block.set_at(i,   "wdg2rate8", None)
        block.set_at(i,   "wdg2rate9", None)
        block.set_at(i,   "wdg2rate10", None)
        block.set_at(i,   "wdg2rate11", None)
        block.set_at(i,   "wdg2rate12", None)
        block.set_at(i,   "cod2", None)
        block.set_at(i,   "cont2", None)
        block.set_at(i,   "node2", None)
        block.set_at(i,   "rma2", None)
        block.set_at(i,   "rmi2", None)
        block.set_at(i,   "vma2", None)
        block.set_at(i,   "vmi2", None)
        block.set_at(i,   "ntp2", None)
        block.set_at(i,   "tab2", None)
        block.set_at(i,   "cr2", None)
        block.set_at(i,   "cx2", None)
        block.set_at(i,   "cnxa2", None)
        block.set_at(i,   "windv3", None)
        block.set_at(i,   "nomv3", None)
        block.set_at(i,   "ang3", None)
        block.set_at(i,   "wdg3rate1", None)
        block.set_at(i,   "wdg3rate2", None)
        block.set_at(i,   "wdg3rate3", None)
        block.set_at(i,   "wdg3rate4", None)
        block.set_at(i,   "wdg3rate5", None)
        block.set_at(i,   "wdg3rate6", None)
        block.set_at(i,   "wdg3rate7", None)
        block.set_at(i,   "wdg3rate8", None)
        block.set_at(i,   "wdg3rate9", None)
        block.set_at(i,   "wdg3rate10", None)
        block.set_at(i,   "wdg3rate11", None)
        block.set_at(i,   "wdg3rate12", None)
        block.set_at(i,   "cod3", None)
        block.set_at(i,   "cont3", None)
        block.set_at(i,   "node3", None)
        block.set_at(i,   "rma3", None)
        block.set_at(i,   "rmi3", None)
        block.set_at(i,   "vma3", None)
        block.set_at(i,   "vmi3", None)
        block.set_at(i,   "ntp3", None)
        block.set_at(i,   "tab3", None)
        block.set_at(i,   "cr3", None)
        block.set_at(i,   "cx3", None)
        block.set_at(i,   "cnxa3", None)

    return block


def parse_transformers(circuit: MultiCircuit, block: CompressedJsonStruct, buses_dict: Dict[int, Any], logger=Logger()):
    """

    :param circuit:
    :param block:
    :param buses_dict:
    :return:
    """
    # ibus	 "jbus"	 "kbus"	 "ckt"	 "cw"	 "cz"	 "cm"	 "mag1"	 "mag2"	 "nmet"
    # "name"	 "stat"	 "o1"	 "f1"	 "o2"	 "f2"	 "o3"	 "f3"	 "o4"	 "f4"
    # "vecgrp"	 "zcod"	 "r1_2"	 "x1_2"
    # "sbase1_2"	 "r2_3"	 "x2_3"	 "sbase2_3"
    # "r3_1"	 "x3_1"	 "sbase3_1"
    # "vmstar"	 "anstar"	 "windv1"
    # "nomv1"	 "ang1"
    # "wdg1rate1"	 "wdg1rate2"	 "wdg1rate3"	 "wdg1rate4"	 "wdg1rate5"	 "wdg1rate6"
    # "wdg1rate7"	 "wdg1rate8"	 "wdg1rate9"	 "wdg1rate10"	 "wdg1rate11"	 "wdg1rate12"
    # "cod1"	 "cont1"	 "node1"	 "rma1"	 "rmi1"	 "vma1"	 "vmi1"	 "ntp1"
    # "tab1"	 "cr1"	 "cx1"	 "cnxa1"	 "windv2"	 "nomv2"	 "ang2"
    # "wdg2rate1"	 "wdg2rate2"	 "wdg2rate3"	 "wdg2rate4"	 "wdg2rate5"	 "wdg2rate6"
    # "wdg2rate7"	 "wdg2rate8"	 "wdg2rate9"	 "wdg2rate10"	 "wdg2rate11"	 "wdg2rate12"
    # "cod2"	 "cont2"	 "node2"	 "rma2"	 "rmi2"	 "vma2"	 "vmi2"	 "ntp2"
    # "tab2"	 "cr2"	 "cx2"	 "cnxa2"	 "windv3"	 "nomv3"	 "ang3"
    # "wdg3rate1"	 "wdg3rate2"	 "wdg3rate3"	 "wdg3rate4"	 "wdg3rate5"	 "wdg3rate6"
    # "wdg3rate7"	 "wdg3rate8"	 "wdg3rate9"	 "wdg3rate10"	 "wdg3rate11"	 "wdg3rate12"
    # "cod3"	 "cont3"	 "node3"	 "rma3"	 "rmi3"	 "vma3"	 "vmi3"	 "ntp3"
    # "tab3"	 "cr3"	 "cx3"	 "cnxa3"

    for i in range(block.get_row_number()):
        data = block.get_dict_at(i)

        # get the buses
        bus_from = buses_dict[data['ibus']]
        bus_to = buses_dict[data['jbus']]

        code = "{0}_{1}_{2}".format(bus_from.code, bus_to.code, data['ckt'])

        if data['nomv1'] == 0:
            V1 = bus_from.Vnom
        else:
            V1 = data['nomv1']

        if data['nomv2'] == 0:
            V2 = bus_to.Vnom
        else:
            V2 = data['nomv2']

        r, x, g, b, tap_mod, tap_angle = get_psse_transformer_impedances(CW=data['cw'],
                                                                         CZ=data['cz'],
                                                                         CM=data['cm'],
                                                                         V1=V1,
                                                                         V2=V2,
                                                                         sbase=100,
                                                                         logger=logger,
                                                                         code=code,
                                                                         MAG1=data['mag1'],
                                                                         MAG2=data['mag2'],
                                                                         WINDV1=data['windv1'],
                                                                         WINDV2=data['windv2'],
                                                                         ANG1=data['ang1'],
                                                                         NOMV1=data['nomv1'],
                                                                         NOMV2=data['nomv2'],
                                                                         R1_2=data['r1_2'],
                                                                         X1_2=data['x1_2'],
                                                                         SBASE1_2=data['sbase1_2'])

        if float(data['wdg1rate2']) != 0:
            contingency_factor = float(data['wdg1rate1']) / float(data['wdg1rate2'])
        else:
            contingency_factor = 1.0

        elm = dev.Transformer2W(bus_from=bus_from,
                                bus_to=bus_to,
                                idtag=None,
                                code=code,
                                name=data['name'],
                                HV=V1,
                                LV=V2,
                                r=r,
                                x=x,
                                g=g,
                                b=b,
                                rate=data['wdg1rate1'],
                                contingency_factor=round(contingency_factor, 6),
                                tap_module=tap_mod,
                                tap_phase=tap_angle,
                                active=bool(data['stat']),
                                mttf=0,
                                mttr=0)

        circuit.add_transformer2w(elm)


# ----------------------------------------------------------------------------------------------------------------------


def get_rawx_structure():
    """
    This enumerates the expected structures inside the rawx JSON structure
    :return: dictionary {key: list of properties}
    """
    return {'caseid': ["ic", "sbase", "rev", "xfrrat", "nxfrat", "basfrq", "title1", "title2"],
            'general': ["thrshz", "pqbrak", "blowup", "maxisollvls", "camaxreptsln", "chkdupcntlbl"],
            'gauss': ["itmx", "accp", "accq", "accm", "tol"],
            'newton': ["itmxn", "accn", "toln", "vctolq", "vctolv", "dvlim", "ndvfct"],
            'adjust': ["adjthr", "acctap", "taplim", "swvbnd", "mxtpss", "mxswim"],
            'tysl': ["itmxty", "accty", "tolty"],
            'rating': ["irate", "name", "desc"],
            'bus': ["ibus", "name", "baskv", "ide", "area", "zone", "owner", "vm", "va", "nvhi", "nvlo", "evhi", "evlo"],
            'load': ["ibus", "loadid", "stat", "area", "zone", "pl", "ql", "ip", "iq", "yp", "yq", "owner", "scale", "intrpt", "dgenp", "dgenq", "dgenm", "loadtype"],
            'fixshunt': ["ibus", "shntid", "stat", "gl", "bl"],
            'generator': ["ibus", "machid", "pg", "qg", "qt", "qb", "vs", "ireg", "nreg", "mbase", "zr", "zx", "rt", "xt", "gtap", "stat", "rmpct", "pt", "pb", "baslod", "o1", "f1", "o2", "f2", "o3", "f3", "o4", "f4", "wmod", "wpf"],
            'acline': ["ibus", "jbus", "ckt", "rpu", "xpu", "bpu", "name", "rate1", "rate2", "rate3", "rate4", "rate5", "rate6", "rate7", "rate8", "rate9", "rate10", "rate11", "rate12", "gi", "bi", "gj", "bj", "stat", "met", "len", "o1", "f1", "o2", "f2", "o3", "f3", "o4", "f4"],
            'sysswd': ["ibus", "jbus", "ckt", "xpu", "rate1", "rate2", "rate3", "rate4", "rate5", "rate6", "rate7", "rate8", "rate9", "rate10", "rate11", "rate12", "stat", "nstat", "met", "stype", "name"],
            'transformer': ["ibus", "jbus", "kbus", "ckt", "cw", "cz", "cm", "mag1", "mag2", "nmet", "name", "stat", "o1", "f1", "o2", "f2", "o3", "f3", "o4", "f4", "vecgrp", "zcod", "r1_2", "x1_2", "sbase1_2", "r2_3", "x2_3", "sbase2_3", "r3_1", "x3_1", "sbase3_1", "vmstar", "anstar", "windv1", "nomv1", "ang1", "wdg1rate1", "wdg1rate2", "wdg1rate3", "wdg1rate4", "wdg1rate5", "wdg1rate6", "wdg1rate7", "wdg1rate8", "wdg1rate9", "wdg1rate10", "wdg1rate11", "wdg1rate12", "cod1", "cont1", "node1", "rma1", "rmi1", "vma1", "vmi1", "ntp1", "tab1", "cr1", "cx1", "cnxa1", "windv2", "nomv2", "ang2", "wdg2rate1", "wdg2rate2", "wdg2rate3", "wdg2rate4", "wdg2rate5", "wdg2rate6", "wdg2rate7", "wdg2rate8", "wdg2rate9", "wdg2rate10", "wdg2rate11", "wdg2rate12", "cod2", "cont2", "node2", "rma2", "rmi2", "vma2", "vmi2", "ntp2", "tab2", "cr2", "cx2", "cnxa2", "windv3", "nomv3", "ang3", "wdg3rate1", "wdg3rate2", "wdg3rate3", "wdg3rate4", "wdg3rate5", "wdg3rate6", "wdg3rate7", "wdg3rate8", "wdg3rate9", "wdg3rate10", "wdg3rate11", "wdg3rate12", "cod3", "cont3", "node3", "rma3", "rmi3", "vma3", "vmi3", "ntp3", "tab3", "cr3", "cx3", "cnxa3"],
            'area': ["iarea", "isw", "pdes", "ptol", "arname"],
            'twotermdc': ["name", "mdc", "rdc", "setvl", "vschd", "vcmod", "rcomp", "delti", "met", "dcvmin", "cccitmx", "cccacc", "ipr", "nbr", "anmxr", "anmnr", "rcr", "xcr", "ebasr", "trr", "tapr", "tmxr", "tmnr", "stpr", "icr", "ndr", "ifr", "itr", "idr", "xcapr", "ipi", "nbi", "anmxi", "anmni", "rci", "xci", "ebasi", "tri", "tapi", "tmxi", "tmni", "stpi", "ici", "ndi", "ifi", "iti", "idi", "xcapi"],
            'vscdc': ["name", "mdc", "rdc", "o1", "f1", "o2", "f2", "o3", "f3", "o4", "f4", "ibus1", "type1", "mode1", "dcset1", "acset1", "aloss1", "bloss1", "minloss1", "smax1", "imax1", "pwf1", "maxq1", "minq1", "vsreg1", "nreg1", "rmpct1", "ibus2", "type2", "mode2", "dcset2", "acset2", "aloss2", "bloss2", "minloss2", "smax2", "imax2", "pwf2", "maxq2", "minq2", "vsreg2", "nreg2", "rmpct2"],
            'impcor': ["itable", "tap", "refact", "imfact"],
            'ntermdc': ["name", "nconv", "ndcbs", "ndcln", "mdc", "vconv", "vcmod", "vconvn"],
            'ntermdcconv': ["name", "ib", "nbrdg", "angmx", "angmn", "rc", "xc", "ebas", "tr", "tap", "tpmx", "tpmn", "tstp", "setvl", "dcpf", "marg", "cnvcod"],
            'ntermdcbus': ["name", "idc", "ib", "area", "zone", "dcname", "idc2", "rgrnd", "owner"],
            'ntermdclink': ["name", "idc", "jdc", "dcckt", "met", "rdc", "ldc"],
            'msline': ["ibus", "jbus", "mslid", "met", "dum1", "dum2", "dum3", "dum4", "dum5", "dum6", "dum7", "dum8", "dum9"],
            'zone': ["izone", "zoname"],
            'iatrans': ["arfrom", "arto", "trid", "ptran"],
            'owner': ["iowner", "owname"],
            'facts': ["name", "ibus", "jbus", "mode", "pdes", "qdes", "vset", "shmx", "trmx", "vtmn", "vtmx", "vsmx", "imx", "linx", "rmpct", "owner", "set1", "set2", "vsref", "fcreg", "nreg", "mname"],
            'swshunt': ["ibus", "shntid", "modsw", "adjm", "stat", "vswhi", "vswlo", "swreg", "nreg", "rmpct", "rmidnt", "binit", "s1", "n1", "b1", "s2", "n2", "b2", "s3", "n3", "b3", "s4", "n4", "b4", "s5", "n5", "b5", "s6", "n6", "b6", "s7", "n7", "b7", "s8", "n8", "b8"],
            'gne': ["name", "model", "nterm", "bus1", "bus2", "nreal", "nintg", "nchar", "stat", "owner", "nmet", "real1", "real2", "real3", "real4", "real5", "real6", "real7", "real8", "real9", "real10", "intg1", "intg2", "intg3", "intg4", "intg5", "intg6", "intg7", "intg8", "intg9", "intg10", "char1", "char2", "char3", "char4", "char5", "char6", "char7", "char8", "char9", "char10"],
            'indmach': ["ibus", "imid", "stat", "sc", "dc", "area", "zone", "owner", "tc", "bc", "mbase", "ratekv", "pcode", "pset", "hconst", "aconst", "bconst", "dconst", "econst", "ra", "xa", "xm", "r1", "x1", "r2", "x2", "x3", "e1", "se1", "e2", "se2", "ia1", "ia2", "xamult"],
            'sub': ["isub", "name", "lati", "long", "srg"],
            'subnode': ["isub", "inode", "name", "ibus", "stat", "vm", "va"],
            'subswd': ["isub", "inode", "jnode", "swdid", "name", "type", "stat", "nstat", "xpu", "rate1", "rate2", "rate3"],
            'subterm': ["isub", "inode", "type", "eqid", "ibus", "jbus", "kbus"]}


def rawx_parse(file_name: str) -> [MultiCircuit, Logger]:
    """
    Parse a rawx file from PSSe
    :param file_name: file name
    :return: [MultiCircuit, Logger] instances
    """
    # read json file into dictionary
    data = json.load(open(file_name))

    # get structures
    struct = get_rawx_structure()
    circuit = MultiCircuit()
    logger = Logger()

    # get the data
    if 'network' in data.keys():
        data2 = data['network']
    else:
        logger.add_error('This is not a rawx json file :(')
        return circuit, logger

    # bus dictionary
    bus_dict = dict()
    areas_dict = dict()
    zones_dict = dict()
    bus_area = dict()
    for entry, fields in struct.items():
        if entry in data2.keys():

            # read the struct values
            block = CompressedJsonStruct(fields=data2[entry]['fields'],
                                         data=data2[entry]['data'])

            if entry == 'caseid':
                parse_circuit(circuit=circuit, block=block)

            elif entry == 'general':
                pass

            elif entry == 'gauss':
                pass

            elif entry == 'newton':
                pass

            elif entry == 'adjust':
                pass

            elif entry == 'tysl':
                pass

            elif entry == 'rating':
                pass

            elif entry == 'bus':
                bus_dict, bus_area = parse_buses(circuit=circuit, block=block)

            elif entry == 'load':
                parse_loads(circuit=circuit, block=block, buses_dict=bus_dict)

            elif entry == 'fixshunt':
                parse_fixed_shunts(circuit=circuit, block=block, buses_dict=bus_dict)

            elif entry == 'generator':
                parse_generators(circuit=circuit, block=block, buses_dict=bus_dict)

            elif entry == 'acline':
                parse_ac_lines(circuit=circuit, block=block, buses_dict=bus_dict, logger=logger)

            elif entry == 'sysswd':
                pass

            elif entry == 'transformer':
                parse_transformers(circuit=circuit, block=block, buses_dict=bus_dict)

            elif entry == 'area':
                areas_dict = parse_areas(circuit=circuit, block=block)

            elif entry == 'twotermdc':
                parse_twotermdc_lines(circuit=circuit, block=block, buses_dict=bus_dict)

            elif entry == 'vscdc':
                pass

            elif entry == 'impcor':
                pass

            elif entry == 'ntermdc':
                pass

            elif entry == 'ntermdcconv':
                pass

            elif entry == 'ntermdcbus':
                pass

            elif entry == 'ntermdclink':
                pass

            elif entry == 'msline':
                pass

            elif entry == 'zone':
                zones_dict = parse_zones(circuit=circuit, block=block)

            elif entry == 'iatrans':
                pass

            elif entry == 'owner':
                pass

            elif entry == 'facts':
                pass

            elif entry == 'swshunt':
                parse_switched_shunts(circuit=circuit, block=block, buses_dict=bus_dict)

            elif entry == 'gne':
                pass

            elif entry == 'indmach':
                pass

            elif entry == 'sub':
                pass

            elif entry == 'subnode':
                pass

            elif entry == 'subswd':
                pass

            elif entry == 'subterm':
                pass

            else:
                logger.add_warning('Unkown rawx structure ' + entry)

        else:
            logger.add_warning(entry + " not found")

    # force the buses parsing
    # this piece is here to ensure that all the elements are already present
    for bus, (id_area, id_zone) in bus_area.items():
        bus.area = areas_dict[id_area]
        bus.zone = zones_dict[id_zone]

    return circuit, logger


def rawx_writer(file_name: str, circuit: MultiCircuit) -> Logger:
    """
    RAWx export
    :param file_name: file name to save to
    :param circuit: MultiCircuit instance
    :return: Logger instance
    """
    struct = get_rawx_structure()
    logger = Logger()

    data = dict()
    rev_bus_dict = dict()
    for entry, fields in struct.items():

        # default structure
        block = CompressedJsonStruct(fields=fields)

        # fill the structure accordingly
        if entry == 'caseid':
            block = get_circuit_block(circuit=circuit, fields=fields)

        elif entry == 'general':
            # this is fixed
            block.set_data([0.0001, 0.7, 5.0, 4, 20, 0])

        elif entry == 'gauss':
            # this is fixed
            block.set_data([100, 1.6, 1.6, 1.0, 0.0001])

        elif entry == 'newton':
            # this is fixed
            block.set_data([100, 0.25, 0.01, 0.1, 0.00001, 0.99, 0.99])

        elif entry == 'adjust':
            # this is fixed
            block.set_data([0.005, 1.0, 0.05, 100.0, 99, 10])

        elif entry == 'tysl':
            # this is fixed
            block.set_data([20, 1.0, 0.00001])

        elif entry == 'rating':

            # this is fixed
            block.set_data([[1, "RATE1", "RATING SET 1"],
                            [2, "RATE2", "RATING SET 2"],
                            [3, "RATE3", "RATING SET 3"],
                            [4, "RATE4", "RATING SET 4"],
                            [5, "RATE5", "RATING SET 5"],
                            [6, "RATE6", "RATING SET 6"],
                            [7, "RATE7", "RATING SET 7"],
                            [8, "RATE8", "RATING SET 8"],
                            [9, "RATE9", "RATING SET 9"],
                            [10, "RATE10", "RATING SET 10"],
                            [11, "RATE11", "RATING SET 11"],
                            [12, "RATE12", "RATING SET 12"]])

        elif entry == 'bus':
            block, rev_bus_dict = get_buses_block(circuit=circuit, fields=fields)

        elif entry == 'load':
            block = get_loads_block(circuit=circuit, fields=fields, rev_bus_dict=rev_bus_dict)

        elif entry == 'fixshunt':
            block = get_fixed_shunts_block(circuit=circuit, fields=fields, rev_bus_dict=rev_bus_dict)

        elif entry == 'generator':
            block = get_generators_block(circuit=circuit, fields=fields, rev_bus_dict=rev_bus_dict)

        elif entry == 'acline':
            block = get_ac_lines_block(circuit=circuit, fields=fields, rev_bus_dict=rev_bus_dict)

        elif entry == 'sysswd':
            pass

        elif entry == 'transformer':
            block = get_transformers_block(circuit=circuit, fields=fields, rev_bus_dict=rev_bus_dict)

        elif entry == 'area':
            block = get_areas_block(circuit=circuit, fields=fields)

        elif entry == 'twotermdc':
            block = get_twotermdc_block(circuit=circuit, fields=fields, rev_bus_dict=rev_bus_dict)

        elif entry == 'vscdc':
            pass

        elif entry == 'impcor':
            pass

        elif entry == 'ntermdc':
            pass

        elif entry == 'ntermdcconv':
            pass

        elif entry == 'ntermdcbus':
            pass

        elif entry == 'ntermdclink':
            pass

        elif entry == 'msline':
            pass

        elif entry == 'zone':
            block = get_zones_block(circuit=circuit, fields=fields)

        elif entry == 'iatrans':
            pass

        elif entry == 'owner':
            block.set_data([1, "Default"])

        elif entry == 'facts':
            pass

        elif entry == 'swshunt':
            pass

        elif entry == 'gne':
            pass

        elif entry == 'indmach':
            pass

        elif entry == 'sub':
            pass

        elif entry == 'subnode':
            pass

        elif entry == 'subswd':
            pass

        elif entry == 'subterm':
            pass

        else:
            logger.add_warning('Unknown rawx structure ' + entry)

        # get the dictionary
        data[entry] = block.get_final_dict()

    # save the data into a file
    rawx = {'network': data}
    with open(file_name, 'w') as fp:
        fp.write(json.dumps(rawx, indent=True))

    return logger
