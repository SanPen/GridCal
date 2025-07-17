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
from GridCalEngine.Devices import Bus, Generator, Load, Transformer2W, Line, Substation, VoltageLevel
import re

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

def find_id(child: ET.Element):
    """
    Try to find the ID of an element
    :param child: XML element
    :return: RDFID
    """
    obj_id = ''
    for attr, value in child.attrib.items():
        if 'about' in attr.lower() or 'resource' in attr.lower():
            if ':' in value:
                obj_id = value.split(':')[-1]
            else:
                obj_id = value
        elif 'id' in attr.lower():
            obj_id = value
        elif attr.strip().lower() == 'nom':
            obj_id = value
        elif attr.strip().lower() == 'num':
            obj_id = value
            break
        elif attr.strip().lower() == 'cote':
            obj_id = value
            break

    return obj_id.replace('_', '').replace('#', '')

def find_class_name(child: ET.Element):
    """
    Try to find the CIM class name
    :param child: XML element
    :return: class name
    """
    if '}' in child.tag:
        class_name = child.tag.split('}')[-1]
    else:
        class_name = child.tag

    if '.' in class_name:
        class_name = class_name.split('.')[-1]

    return class_name

def fix_child_result_datatype(child_result: Dict):
    for key, val in child_result.items():
        if val == "true":
            child_result[key] = True
        elif val == "false":
            child_result[key] = False
    return child_result

def parse_xml_to_dict(xml_element: ET.Element):
    """
    Parse element into dictionary
    :param xml_element: XML element
    :return: Dictionary representing the XML
    """
    result = dict()

    for child in xml_element:
        obj_id = find_id(child)
        class_name = find_class_name(child)

        if len(child) > 0:
            if class_name == 'reseau':
                grid_data= dict(child.attrib)
                grid_data.update(parse_xml_to_dict(child))
                return grid_data

            # 🔧 Light handling for 'postes'
            if class_name == 'postes':
                child_result = parse_xml_to_dict(child)
                if '' in child_result:
                    result[class_name] = child_result['']
                else:
                    result[class_name] = child_result
                continue

            # 🔧 Light handling for 'donneesQuadripoles'
            if class_name == 'donneesQuadripoles':
                child_result = parse_xml_to_dict(child)
                if '' in child_result:
                    result[class_name] = child_result['']
                else:
                    result[class_name] = child_result
                continue

            # 🔧 Flatten variables into quadripole
            if class_name == 'quadripole':
                quad_data = dict(child.attrib)
                child_result = parse_xml_to_dict(child)
                quad_data.update(child_result)
                result[obj_id] = quad_data
                continue

            if class_name == 'seuils':
                seuil_data = dict(child.attrib)
                cote = seuil_data.get('cote', '')
                child_result = parse_xml_to_dict(child)
                seuil_data.update(child_result)
                if class_name not in result:
                    result[class_name] = dict()
                result[class_name][cote] = seuil_data
                continue

        else: # leaf nodes
            if class_name == 'variables':
                result = child.attrib
                continue

            if class_name == 'seuil':
                obj_id = str(len(result))
                result[obj_id] = child.attrib
                continue

            if class_name == 'poste':
                result[obj_id] = child.attrib
                continue

    return result




def rte2gridcal(file_name: str, logger: Logger) -> (MultiCircuit, bool):
    """
    Read the RTE internal grid format
    :param file_name: xml file name
    :param logger: Logger
    :return: MultiCircuit
    """

    circuit = MultiCircuit()
    is_valid = True

    lines = None
    buses = None
    file_cgmes_data = {}

    # import the cim files' content into a dictionary
    data = read_cgmes_files(cim_files=file_name, logger=Logger)
    # Parse the files
    i = 0
    for file_name, file_data in data.items():
        name, file_extension = os.path.splitext(file_name)
        # self.emit_text('Parsing xml structure of ' + name)
        file_cgmes_data = parse_xml_text(file_data)

        buses = file_cgmes_data.get('postes', None)
        lines = file_cgmes_data.get('donneesQuadripoles', None)

    if "nom" not in file_cgmes_data.keys():
        is_valid = False
        return circuit, is_valid

    circuit.name = file_cgmes_data['nom']
    circuit.comments = "Grid from RTE model"


    bus_dict = dict()
    vl_dict = dict()
    substation_dict = dict()
    # reverse_map = dict()
    if buses is not None:
        for bus_id, bus_data in buses.items():
            matches = re.findall(r'[^\d\s]+', bus_data['nom'])
            substation_name = matches[0]
            voltage_level_name = substation_name + '_' + bus_data['unom']
            bus_name = bus_data['nom']
            if substation_name not in substation_dict.keys():
                substation_dict[substation_name] = Substation(name=substation_name)
                circuit.add_substation(substation_dict[substation_name])

            if voltage_level_name not in vl_dict:
                vl_dict[voltage_level_name] = VoltageLevel(name=voltage_level_name, substation=substation_dict[substation_name], Vnom=float(bus_data['unom']))
                circuit.add_voltage_level(vl_dict[voltage_level_name])

            bus = Bus(name=bus_name, voltage_level=vl_dict[voltage_level_name], Vnom=float(bus_data['unom']))
            bus_dict[bus_id] = bus
            circuit.add_bus(bus)

            # if substation_name not in reverse_map:
            #     reverse_map[substation_name] = dict()
            # if voltage_level_name not in reverse_map[substation_name]:
            #     reverse_map[substation_name][voltage_level_name] = dict()
            # if bus_name not in reverse_map[substation_name][voltage_level_name]:
            #     if reverse_map[substation_name][voltage_level_name] is None:
            #         reverse_map[substation_name][voltage_level_name] = dict()
            #         reverse_map[substation_name][voltage_level_name][bus_name] = bus
            #     else:
            #         reverse_map[substation_name][voltage_level_name][bus_name] = bus

    if lines is not None:
        for line_id, line_data in lines.items():
            # split_text = re.split(r'(?<=\d)\s+', line_data['nom'], maxsplit=1)
            # substation_from = re.findall(r'[^\d\s]+', split_text[0])[0]
            # substation_to = re.findall(r'[^\d\s]+', split_text[1])[0]
            #
            # vl_id = re.findall(r'\d+', line_data['nom'])[0] # the first digit in the name  tells us which vl
            # vl = voltage_levels[vl_id]
            # vl_from_name = substation_from + '_' + str(vl)
            # vl_to_name = substation_to + '_' + str(vl)
            name = line_data['nom']



            bus_id_from = line_data['postor']
            bus_id_to = line_data['postex']

            bus_f = bus_dict[bus_id_from]
            bus_t = bus_dict[bus_id_to]

            is_trafo = True if bus_f.voltage_level.substation == bus_t.voltage_level.substation else False

            r = line_data['resistance']
            x = line_data['reactance']
            rating = line_data['imap']

            if is_trafo:
                tr = Transformer2W(bus_from=bus_f,
                                   bus_to=bus_t,
                                   name=name,
                                   r=float(r),
                                   x=float(x),
                                   rate=float(rating))
                circuit.add_transformer2w(tr)
            else:
                br = Line(bus_from=bus_f,
                          bus_to=bus_t,
                          name=name,
                          r=float(r),
                          x=float(x),
                          rate=float(rating))

                circuit.add_line(br)

    # return the circuit
    return circuit, is_valid

