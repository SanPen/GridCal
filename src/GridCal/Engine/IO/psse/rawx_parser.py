# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from GridCal.Engine.IO.psse.psse_functions import get_psse_transformer_impedances
from GridCal.Engine.basic_structures import CompressedJsonStruct, Logger
import GridCal.Engine.Core.Devices as dev
from GridCal.Engine.Core.Devices.multi_circuit import MultiCircuit
from GridCal.Engine.IO.psse.devices.psse_circuit import PsseCircuit





def rawx_parse(file_name: str, logger: Logger = Logger()) -> PsseCircuit:
    """
    Parse a rawx file from PSSe
    :param file_name: file name
    :param logger: Logger
    :return: PsseCircuit
    """

    # read json file into dictionary
    data = json.load(open(file_name))

    # get structures
    psse_grid = PsseCircuit()

    data_map = psse_grid.get_rawx_dict()

    # get the data
    if 'network' in data.keys():
        network_data = data['network']
    else:
        logger.add_error('This is not a rawx json file :(')
        return psse_grid

    for class_name, psse_property in data_map.items():

        type_data = network_data.get(class_name, None)

        if type_data is None:
            pass
        else:

            # get the list of elements where this element belongs
            elm_lst = getattr(psse_grid, psse_property.property_name)

            # get the attribute names
            property_names = type_data['fields']

            # get the attribute data (list of lists)
            elms_data = type_data['data']

            # for each data entry...
            for elm_data in elms_data:

                # declare a PSSe object
                elm = psse_property.class_type()
                elm_property_dict = elm.get_rawx_dict()

                # fill the psse object accordingly
                for rawx_property_name, value in zip(property_names, elm_data):
                    elm_prop = elm_property_dict.get(rawx_property_name, None)

                    if elm_prop:
                        setattr(elm, elm_prop.property_name, value)
                    else:
                        logger.add_error("PSSe attribute not found", device=class_name, value=rawx_property_name)

                # add the element to the PSSe circuit list
                elm_lst.append(elm)

    return psse_grid


def rawx_writer(file_name: str, circuit: PsseCircuit, logger: Logger = Logger()) -> Logger:
    """
    RAWx export
    :param file_name: file name to save to
    :param circuit: MultiCircuit instance
    :param logger: Logger instance
    """
    struct = get_rawx_structure()

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
