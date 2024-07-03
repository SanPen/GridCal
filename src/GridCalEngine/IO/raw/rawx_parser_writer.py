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

from typing import Any, Dict, Tuple, List
import json
import numpy as np

from GridCalEngine.IO.raw.raw_functions import get_psse_transformer_impedances
from GridCalEngine.basic_structures import CompressedJsonStruct, Logger
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit
from GridCalEngine.IO.raw.devices.psse_object import RawObject


def parse_rawx(file_name: str, logger: Logger = Logger()) -> PsseCircuit:
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


class NpEncoder(json.JSONEncoder):
    """

    """
    def default(self, obj):
        dtypes = (np.datetime64, np.complexfloating)
        if isinstance(obj, dtypes):
            return str(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            if any([np.issubdtype(obj.dtype, i) for i in dtypes]):
                return obj.astype(str).tolist()
            return obj.tolist()
        return super(NpEncoder, self).default(obj)


def write_rawx(file_name: str, circuit: PsseCircuit, logger: Logger = Logger()) -> Logger:
    """
    RAWx export
    :param file_name: file name to save to
    :param circuit: MultiCircuit instance
    :param logger: Logger instance
    """
    data = dict()

    for circuit_prop in circuit.get_properties():

        circuit_val: List[RawObject] = getattr(circuit, circuit_prop.property_name)

        elm_data = list()
        fields = list()
        if isinstance(circuit_val, list):

            for element in circuit_val:
                d = element.get_rawx_dict()
                elm_data.append([
                    element.get_prop_value(prop=psse_property) for psse_property in d.values()
                ])

                if len(fields) == 0:
                    fields = list(d.keys())

        data[circuit_prop.rawx_key] = {"fields": fields, "data": elm_data}

    # save the data into a file
    rawx = {'network': data}
    with open(file_name, 'w') as fp:
        fp.write(json.dumps(rawx, indent=True, cls=NpEncoder))

    return logger
