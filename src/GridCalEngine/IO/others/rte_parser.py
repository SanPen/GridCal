# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Union, Callable, Tuple
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as dev
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.zip_interface import get_xml_from_zip, get_xml_content

def read_cgmes_files(cim_files: Union[List[str], str], logger: DataLogger) -> Dict[str, List[str]]:
    """
    Reads a list of .zip or xml into a dictionary of file name -> list of text lines
    :param cim_files: list of file names
    :param logger: DataLogger instance
    :return: dictionary of file name -> list of text lines
    """
    # read files and sort them in the preferred reading order
    data: Dict[str, List[str]] = dict()

    if isinstance(cim_files, list):

        for f in cim_files:
            _, file_extension = os.path.splitext(f)
            name = os.path.basename(f)

            if file_extension == '.xml':
                file_ptr = open(f, 'rb')
                data[name] = get_xml_content(file_ptr)
                file_ptr.close()
            elif file_extension == '.zip':
                # read the content of a zip file
                d = get_xml_from_zip(file_name_zip=f)
                if d is not None:
                    for key, value in d.items():
                        data[key] = value
                else:
                    logger.add_error("BadZipFile", value=f)
                    print(f"BadZipFile {f}")
    else:
        name, file_extension = os.path.splitext(cim_files)

        if file_extension == '.xml':
            with open(cim_files, 'rb') as file_ptr:
                data[name] = get_xml_content(file_ptr=file_ptr)

        elif file_extension == '.zip':
            # read the content of a zip file
            d = get_xml_from_zip(file_name_zip=cim_files)
            if d is not None:
                for key, value in d.items():
                    data[key] = value
            else:
                logger.add_error("BadZipFile", value=cim_files)
                print(f"BadZipFile {cim_files}")

    return data

def parse_xml_text(text_lines: List[str]) -> Dict:
    """
    Fill the XML into the objects
    :param text_lines: list of text lines
    :return Dictionary representing the XML
    """

    xml_string = "".join(text_lines)

    root = ET.fromstring(xml_string)
    return parse_xml_to_dict(root)


def parse_xml_to_dict(xml_element: ET.Element):
    """
    Parse element into dictionary
    :param xml_element: XML element
    :return: Dictionary representing the XML
    """
    result = dict()

    for child in xml_element:
        # key = child.tag

        obj_id = find_id(child)
        class_name = find_class_name(child)

        if len(child) > 0:
            child_result = parse_xml_to_dict(child)
            child_result = fix_child_result_datatype(child_result)
            objects_list = result.get(class_name, None)

            if objects_list is None:
                result[class_name] = {obj_id: child_result}
            else:
                objects_list[obj_id] = child_result
        else:
            if class_name not in result:
                if child.text is None:
                    result[class_name] = obj_id  # it is a resource id
                else:
                    result[class_name] = child.text
            else:
                if child.text is None:
                    t_set = set()
                    if isinstance(result[class_name], list):
                        t_set.update(result[class_name])
                    else:
                        t_set.add(result[class_name])
                    t_set.update([obj_id])  # it is a resource id
                    if len(t_set) > 1:
                        result[class_name] = list(t_set)
                    else:
                        result[class_name] = list(t_set)[0]
                else:
                    t_set = {child.text}
                    if isinstance(result[class_name], list):
                        t_set.update(result[class_name])
                    else:
                        t_set.add(result[class_name])
                    if len(t_set) > 1:
                        result[class_name] = list(t_set)
                    else:
                        result[class_name] = list(t_set)[0]

    return result

def rte2gridcal(file_name: str, logger: Logger) -> MultiCircuit:
    """
    Read the RTE internal grid format
    :param file_name: json file name
    :param logger: Logger
    :return: MultiCircuit
    """

    circuit = MultiCircuit()
    is_valid = True

    with open(file_name) as json_file:
        data = json.load(json_file)

    # elements dictionaries
    xfrm_dict = {entry['IdEnRed']: entry for entry in data['Transformadores']}

    # nodes_dict = {entry['id']: entry for entry in data['Nudos']}
    nodes_dict = dict()
    buses_dict = dict()
    for entry in data['Nudos']:
        nodes_dict[entry['id']] = entry
        bus = dev.Bus(name=str(entry['id']))
        buses_dict[entry['id']] = bus
        if entry['id'] > 0:  # omit the node 0 because it is the "earth node"...
            circuit.add_bus(bus)

    gen_dict = {entry['IdEnRed']: entry for entry in data['Generadores']}

    load_dict = {entry['IdEnRed']: entry for entry in data['Consumos']}

    sw_dict = {entry['IdEnRed']: entry for entry in data['Interruptores']}

    # main grid
    vector_red = data['Red']

    """
    {'id': 0, 
    'Tipo': 1, 
    'E': 0, 
    'EFase': 0, 
    'Tomas': 0, 
    'R1': 1e-05, 
    'X1': 1e-05, 
    'R0': 1e-05, 
    'X0': 1e-05, 
    'RN': 1e-05, 
    'XN': 1e-05, 
    'P': 0, 
    'Q': 0, 
    'Nudo1': 2410, 
    'Nudo2': 2403, 
    'Carga_Max': -1, 
    'ClassID': 1090, 
    'ClassMEMBER': 98076366, 
    'Conf': 'abc', 
    'LineaMT': '2030:98075347', 
    'Unom': 15.0}
    """

    for entry in vector_red:

        # pick the general attributes
        identifier = entry['id']
        tpe = entry['Tipo']
        n1_id = entry['Nudo1']
        n2_id = entry['Nudo2']

        # get the Bus objects associated to the bus indices
        bus1 = buses_dict.get(n1_id, None)
        bus2 = buses_dict.get(n2_id, None)

        if tpe == 0:  # Fuente de  Tensión(elemento  Ptheta)

            # pick the bus that is not the earth bus...
            if n1_id == 0:
                bus = bus2
            else:
                bus = bus1

            bus.is_slack = True
            elm = dev.Generator(name='Slack')
            circuit.add_generator(bus, elm)

        elif tpe == 1:  # Elemento impedancia(lineas)

            V = entry['Unom']
            Zbase = V * V / circuit.Sbase

            if identifier in load_dict.keys():
                # load!!!
                print('Load found in lines: WTF?')
            else:
                # line!!!
                r = entry['R1'] / Zbase
                x = entry['X1'] / Zbase

                elm = dev.Line(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x)
                circuit.add_line(elm)

        elif tpe == 2:  # Elemento PQ

            # pick the bus that is not the earth bus...
            if n1_id == 0:
                bus = bus2
            else:
                bus = bus1

            p = entry['P']  # power in MW
            q = entry['Q']
            elm = dev.Load(name=str(identifier), P=p*1e-3, Q=q * 1e-3)
            circuit.add_load(bus, elm)

        elif tpe == 3:  # Elemento  PV
            pass

        elif tpe == 4:  # Reg  de  tensión

            V = entry['Unom']
            Zbase = V * V / circuit.Sbase

            r = entry['R1'] / Zbase
            x = entry['X1'] / Zbase
            elm = dev.Transformer2W(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x)
            circuit.add_transformer2w(elm)

        elif tpe == 5:  # Transformador

            V = entry['Unom']
            Zbase = V * V / circuit.Sbase

            r = entry['R1'] / Zbase
            x = entry['X1'] / Zbase
            elm = dev.Transformer2W(bus_from=bus1, bus_to=bus2, name=str(identifier), r=r, x=x)
            circuit.add_transformer2w(elm)

    # return the circuit
    return circuit, is_valid

