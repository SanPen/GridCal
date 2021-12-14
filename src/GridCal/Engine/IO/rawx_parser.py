# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from typing import List, Any, Dict
import json
from GridCal.Engine.basic_structures import Logger, CompressedJsonStruct
import GridCal.Engine.Devices as dev
from GridCal.Engine.Core.multi_circuit import MultiCircuit


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
    circuit.comments = data['title1'] + '\n' + data['title2']


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


def parse_buses(circuit: MultiCircuit, block: CompressedJsonStruct) -> Dict[int, Any]:
    """

    :param circuit:
    :param block:
    :return:
    """
    # ["ibus", "name", "baskv", "ide", "area", "zone", "owner", "vm", "va", "nvhi", "nvlo", "evhi", "evlo"]
    bus_dict = dict()

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

        circuit.add_bus(bus)

    return bus_dict


def get_buses_block(circuit: MultiCircuit, fields) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_bus_number())

    for i, bus in enumerate(circuit.get_buses()):
        # ["ibus", "name", "baskv", "ide", "area", "zone", "owner", "vm", "va", "nvhi", "nvlo", "evhi", "evlo"]

        bus_tpe = bus.determine_bus_type().value
        if not bus.active:
            bus_tpe = 4

        block.set_at(i, 'ibus', i + 1)
        block.set_at(i, 'ibus', i + 1)
        block.set_at(i, 'name', bus.name[:12])
        block.set_at(i, 'baskv', bus.Vnom)
        block.set_at(i, 'ide', bus_tpe)
        block.set_at(i, 'area', 0)
        block.set_at(i, 'zone', 0)
        block.set_at(i, 'owner', 0)

        block.set_at(i, 'vm', 1.0)
        block.set_at(i, 'va', 0)

        block.set_at(i, 'nvhi', 1.1)
        block.set_at(i, 'nvlo', 0.9)

        block.set_at(i, 'evhi', 1.1)
        block.set_at(i, 'evlo', 0.9)

    return block


def get_loads_block(circuit: MultiCircuit, fields, rev_bus_dict: Dict[Any, int]) -> CompressedJsonStruct:
    """

    :param circuit:
    :param fields:
    :param rev_bus_dict: dictionary of buses and their assigned psse number
    :return:
    """
    block = CompressedJsonStruct(fields=fields)
    block.declare_n_entries(circuit.get_bus_number())

    for k, bus in enumerate(circuit.get_buses()):

        i = 0
        for k2, elm in enumerate(bus.loads):
            # ["ibus", "loadid", "stat", "area", "zone", "pl", "ql", "ip", "iq", "yp", "yq",
            # "owner", "scale", "intrpt", "dgenp", "dgenq", "dgenm", "loadtype"]

            block.set_at(i, "ibus", rev_bus_dict[elm.bus])
            block.set_at(i,  "loadid", k2 + 1)
            block.set_at(i,  "stat", int(elm.active))
            block.set_at(i,  "area", 0)
            block.set_at(i,  "zone", 0)
            block.set_at(i,  "pl", elm.P)
            block.set_at(i,  "ql", elm.Q)
            block.set_at(i,  "ip", elm.Ir)
            block.set_at(i,  "iq", elm.Ii)
            block.set_at(i,  "yp", elm.G)
            block.set_at(i,  "yq", elm.B)
            block.set_at(i,  "owner", 0)
            block.set_at(i,  "scale", 1.0)
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
    # ["ibus", "loadid", "stat", "area", "zone", "pl", "ql", "ip", "iq", "yp", "yq", "owner", "scale", "intrpt", "dgenp", "dgenq", "dgenm", "loadtype"]

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
            machine_id = elm.code.split("-")[1]
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





def get_rawx_structure():

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


def rawx_parse(fname: str) -> [MultiCircuit, Logger]:
    """

    :param fname:
    :return:
    """
    # read json file into dictionary
    data = json.load(open(fname))

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
                bus_dict = parse_buses(circuit=circuit, block=block)

            elif entry == 'load':
                parse_loads(circuit=circuit, block=block, buses_dict=bus_dict)

            elif entry == 'fixshunt':
                pass

            elif entry == 'generator':
                parse_generators(circuit=circuit, block=block, buses_dict=bus_dict)

            elif entry == 'acline':
                pass
            elif entry == 'sysswd':
                pass
            elif entry == 'transformer':
                pass
            elif entry == 'area':
                pass
            elif entry == 'twotermdc':
                pass
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
                pass
            elif entry == 'iatrans':
                pass
            elif entry == 'owner':
                pass
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
                logger.add_warning('Unkown rawx structure ' + entry)

        else:
            logger.add_warning(entry + " not found")

    return circuit, logger


def rawx_writer(fname: str, circuit: MultiCircuit) -> Logger:
    """
    RAWx export
    :param fname: file name to save to
    :param circuit: MultiCircuit instance
    :return: Logger instance
    """
    struct = get_rawx_structure()
    logger = Logger()

    data = dict()
    rev_bus_dict = dict()
    for entry, fields in struct.items():

        # default structure
        data[entry] = CompressedJsonStruct(fields=fields)

        # fill the structure accordingly
        if entry == 'caseid':
            data[entry] = get_circuit_block(circuit=circuit, fields=fields).get_final_dict()

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

            # this is fixed
            data[entry].set_data([[1, "RATE1", "RATING SET 1"],
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
            data[entry] = block.get_final_dict()

        elif entry == 'load':
            data[entry] = get_loads_block(circuit=circuit, fields=fields, rev_bus_dict=rev_bus_dict).get_final_dict()

        elif entry == 'fixshunt':
            pass
        elif entry == 'generator':
            data[entry] = get_generators_block(circuit=circuit, fields=fields, rev_bus_dict=rev_bus_dict).get_final_dict()

        elif entry == 'acline':
            pass
        elif entry == 'sysswd':
            pass
        elif entry == 'transformer':
            pass
        elif entry == 'area':
            pass
        elif entry == 'twotermdc':
            pass
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
            pass
        elif entry == 'iatrans':
            pass
        elif entry == 'owner':
            pass
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
            logger.add_warning('Unkown rawx structure ' + entry)

    # save the data into a file
    rawx = {'network': data}
    with open(fname, 'w') as fp:
        fp.write(json.dumps(rawx, indent=True))

    return logger
