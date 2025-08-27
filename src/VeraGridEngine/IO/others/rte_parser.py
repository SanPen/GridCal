# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Union, Callable, Tuple
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.veragrid.zip_interface import get_xml_from_zip, get_xml_content
from VeraGridEngine.Devices import Bus, Generator, Load, Transformer2W, Line, Substation, VoltageLevel, Country, Shunt
import re
import numpy as np


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

        generally_handled_classes_list = ['postes', 'donneesQuadripoles', 'listePays', 'donneesNoeuds',
                                          'donneesGroupes', 'donneesConsos', 'donneesShunts', 'donneesLois',
                                          'donneesRegleurs', 'donneesDephaseurs', 'donneesCsprs', 'donneesHvdcs',
                                          'stationsLcc', 'stationsVsc', 'lccs', 'vscs']
        classes_containing_variables_list = ['quadripole', 'noeud', 'groupe', 'conso', 'shunt', 'loi', 'regleur',
                                             'dephaseur', 'cspr', 'stationVsc', 'vsc']
        standard_leaf_list = ['variables', 'compens', 'homliaison', 'diagramme', 'repriseQ', 'seuil', 'poste', 'pays']
        if len(child) > 0:
            if class_name == 'reseau':
                grid_data = dict(child.attrib)
                grid_data.update(parse_xml_to_dict(child))
                return grid_data

            # 🔧 Light handling for 'postes'
            if class_name in generally_handled_classes_list:
                child_result = parse_xml_to_dict(child)
                if '' in child_result:
                    result[class_name] = child_result['']
                else:
                    result[class_name] = child_result
                continue

            # 🔧 Flatten variables into quadripole
            if class_name in classes_containing_variables_list:
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

        else:  # leaf nodes
            if class_name == 'variables':
                result.update(child.attrib)
                continue

            if class_name == 'compens':
                result.update(child.attrib)
                continue

            if class_name == 'homliaison':
                result.update(child.attrib)
                continue

            if class_name == 'diagramme':
                result.update(child.attrib)
                continue

            if class_name == 'repriseQ':
                result.update(child.attrib)
                continue

            if class_name == 'seuil':
                obj_id = str(len(result))
                result[obj_id] = child.attrib
                continue

            if class_name == 'poste':
                result[obj_id] = child.attrib
                continue

            if class_name == 'pays':
                result[obj_id] = child.attrib
                continue

    return result


def rte2veragrid(file_name: str, logger: Logger) -> (MultiCircuit, bool):
    """
    Read the RTE internal grid format
    :param file_name: xml file name
    :param logger: Logger
    :return: MultiCircuit
    """

    circuit = MultiCircuit()
    is_valid = True

    lines = None
    substations = None
    file_cgmes_data = {}

    # import the cim files' content into a dictionary
    data = read_cgmes_files(cim_files=file_name, logger=Logger)
    # Parse the files
    i = 0
    for file_name, file_data in data.items():
        name, file_extension = os.path.splitext(file_name)
        # self.emit_text('Parsing xml structure of ' + name)
        file_cgmes_data = parse_xml_text(file_data)

        substations = file_cgmes_data.get('postes', None)
        lines = file_cgmes_data.get('donneesQuadripoles', None)
        countries = file_cgmes_data.get('listePays', None)
        loads = file_cgmes_data.get('donneesConsos', None)
        buses = file_cgmes_data.get('donneesNoeuds', None)
        generators = file_cgmes_data.get('donneesGroupes', None)
        shunts = file_cgmes_data.get('donneesShunts', None)
        lois = file_cgmes_data.get('donneesLois', None)
        regleurs = file_cgmes_data.get('donneesRegleurs', None)
        dephaseurs = file_cgmes_data.get('donneesDephaseurs', None)
        csprs = file_cgmes_data.get('donneesCsprs', None)
        hvdcs = file_cgmes_data.get('donneesHvdcs', None)
        vsc_stations = file_cgmes_data.get('stationsVsc', None)
        vscs = file_cgmes_data.get('vscs', None)

    if "nom" not in file_cgmes_data.keys():
        is_valid = False
        return circuit, is_valid

    circuit.name = file_cgmes_data['nom']
    circuit.comments = "Grid from RTE model"

    country_dict_by_idx = dict()
    if countries is not None:
        for country_name, country in countries.items():
            if country['ind'] not in country_dict_by_idx.keys():
                country_dict_by_idx[country['ind']] = Country(name=country_name)
                circuit.add_country(country_dict_by_idx[country['ind']])

    bus_dict = dict()
    vl_dict_by_idx = dict()
    substation_dict = dict()
    if substations is not None:
        for substation_id, substation_data in substations.items():
            matches = re.findall(r'[^\d\s]+', substation_data['nom'])
            substation_name = matches[0]
            voltage_level_name = substation_name + ' ' + substation_data['unom']
            voltage_level_idx = substation_id
            if substation_name not in substation_dict.keys():
                substation = Substation(name=substation_name)
                substation_dict[substation_name] = substation
                circuit.add_substation(substation)

            if voltage_level_idx not in vl_dict_by_idx:
                vl = VoltageLevel(name=voltage_level_name, substation=substation_dict[substation_name],
                                  Vnom=float(substation_data['unom']))
                vl_dict_by_idx[voltage_level_idx] = vl
                circuit.add_voltage_level(vl)

    if buses is not None:
        for bus_id, bus_data in buses.items():
            bus_name = bus_data['nom']
            country_idx = bus_data['pays']
            country = country_dict_by_idx[country_idx]
            vl_idx = bus_data['poste']
            vl = vl_dict_by_idx[vl_idx]
            bus = Bus(name=bus_name, voltage_level=vl, Vnom=vl.Vnom)
            bus.voltage_level.substation.country = country
            bus_dict[bus_id] = bus
            circuit.add_bus(bus)

    if lines is not None:
        for line_id, line_data in lines.items():
            name = line_data['nom']

            bus_id_from = line_data['nor']
            bus_id_to = line_data['nex']

            if int(bus_id_from) < 0 or int(bus_id_to) < 0:
                # the line is disconnected
                continue

            bus_f = bus_dict[bus_id_from]
            bus_t = bus_dict[bus_id_to]

            z_base = bus_f.Vnom ** 2 / circuit.Sbase

            is_trafo = True if bus_f.voltage_level.substation == bus_t.voltage_level.substation else False

            r = float(line_data['resistance']) / z_base
            x = float(line_data['reactance']) / z_base
            rating = line_data['imap']

            if is_trafo:
                tr = Transformer2W(bus_from=bus_f,
                                   bus_to=bus_t,
                                   name=name,
                                   r=r,
                                   x=x)
                circuit.add_transformer2w(tr)
            else:
                br = Line(bus_from=bus_f,
                          bus_to=bus_t,
                          name=name,
                          r=r,
                          x=x)

                circuit.add_line(br)

    if generators is not None:
        for generator_id, generator_data in generators.items():
            bus_idx = generator_data['noeud']
            if bus_idx == '-1':
                continue
            bus = bus_dict[bus_idx]
            P = float(generator_data['pc'])
            vset = float(generator_data['vc']) / bus.Vnom
            Pmin = float(generator_data['pmin'])
            Pmax = float(generator_data['pmax'])
            Qmin = np.max([float(generator_data['qminPmax']), float(generator_data['qminPmin'])])
            Qmax = np.min([float(generator_data['qmaxPmin']), float(generator_data['qmaxPmax'])])

            generator = Generator(name=generator_data['nom'],
                                  P=P,
                                  vset=vset,
                                  Pmin=Pmin,
                                  Pmax=Pmax,
                                  Qmin=Qmin,
                                  Qmax=Qmax)

            circuit.add_generator(bus, generator)

    if shunts is not None:
        for shunt_id, shunt_data in shunts.items():
            bus_idx = generator_data['noeud']
            if bus_idx == '-1':
                continue
            bus = bus_dict[bus_idx]
            B = float(shunt_data['valnom'])
            shunt = Shunt(name=shunt_data['nom'],
                          B=B)
            circuit.add_shunt(bus, shunt)

    if loads is not None:
        for load_id, load_data in loads.items():
            bus_idx = generator_data['noeud']
            if bus_idx == '-1':
                continue
            bus = bus_dict[bus_idx]
            P_var = float(load_data['peAff']) / circuit.Sbase
            Q_var = float(load_data['qeAff']) / circuit.Sbase
            P_fixed = float(load_data['peFixe']) / circuit.Sbase
            Q_fixed = float(load_data['qeFixe']) / circuit.Sbase

            load = Load(name=load_data['nom'],
                        P=P_var,
                        Q=Q_var)
            circuit.add_load(bus, load)

    # return the circuit
    return circuit, is_valid
