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

import os
from collections import defaultdict
from typing import Dict, List, Union, Callable, Tuple
import xml.etree.ElementTree as ET
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.IO.base.base_circuit import BaseCircuit
from GridCalEngine.IO.gridcal.zip_interface import get_xml_from_zip, get_xml_content


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


def merge(A: Dict[str, Dict[str, Dict[str, str]]],
          B: Dict[str, Dict[str, Dict[str, str]]],
          logger: DataLogger):
    """
    Modify A using B
    :param A: CIM data dictionary to be modified in-place
    :param B: CIM data dictionary used to modify A
    :param logger: DataLogger to fill in logs
    """
    # for each category in B
    for class_name_b, class_obj_dict_b in B.items():

        class_obj_dict_a = A.get(class_name_b, None)

        if class_obj_dict_a is None:
            # the category does not exist in A, just copy it from B
            A[class_name_b] = class_obj_dict_b

        else:

            # for every object in the category from B
            for rdfid, obj_b in class_obj_dict_b.items():

                obj_a = class_obj_dict_a.get(rdfid, None)

                if obj_a is None:
                    # the object in B does not exist in A, copy it
                    class_obj_dict_a[rdfid] = obj_b
                else:
                    # the object in B already has an entry in A, modify it

                    # for each property
                    for prop_name, value_b in obj_b.items():

                        value_a = obj_a.get(prop_name, None)

                        if value_a is None:
                            # the property does not exist in A, add it
                            obj_a[prop_name] = value_b
                        else:
                            if value_b != value_a:
                                # the value exists in A, and the value in B is not None, add it
                                obj_a[prop_name] = value_b
                                logger.add_warning("Overwriting value",
                                                   device=str(obj_a),
                                                   device_class=class_name_b,
                                                   device_property=prop_name,
                                                   value=value_b,
                                                   expected_value=value_a)
                            else:
                                # the assigning value from B is the same as the already stored in A
                                pass


def read_cgmes_files(cim_files: Union[List[str], str]) -> Dict[str, List[str]]:
    """
    Reads a list of .zip or xml into a dictionary of file name -> list of text lines
    :param cim_files: list of file names
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
                for key, value in d.items():
                    data[key] = value
    else:
        name, file_extension = os.path.splitext(cim_files)

        if file_extension == '.xml':
            file_ptr = open(cim_files, 'rb')
            data[name] = get_xml_content(file_ptr)
            file_ptr.close()

        elif file_extension == '.zip':
            # read the content of a zip file
            d = get_xml_from_zip(file_name_zip=cim_files)
            for key, value in d.items():
                data[key] = value

    return data


def sort_cgmes_files(links: List[Tuple[str, str, str]]) -> List[str]:
    """
    Sorts the CIM files in the preferred reading order
    :param links: list of filename, model id, dependent on model id
    :return: sorted list of file names
    """

    file_name_model_dict = dict()
    for filename, model_id, dependent_id in links:
        file_name_model_dict[model_id] = filename

    deps = list()
    items = list()
    for filename, model_id, dependent_id in links:
        if dependent_id == '':
            deps.insert(0, model_id)
            items.insert(0, filename)
        else:
            found = False
            i = 0
            if len(deps) > 0:
                while not found and i < len(deps):
                    if deps[i] == dependent_id:
                        deps.insert(i + 1, model_id)
                        items.insert(i + 1, filename)
                        found = True
                    i += 1
                if not found:
                    deps.append(model_id)
                    items.append(filename)
            else:
                deps.append(model_id)
                items.append(filename)

    return items


def parse_xml_text(text_lines: List[str]) -> Dict:
    """
    Fill the XML into the objects
    :param text_lines: list of text lines
    :return Dictionary representing the XML
    """

    xml_string = "".join(text_lines)

    root = ET.fromstring(xml_string)
    return parse_xml_to_dict(root)


class CgmesDataParser(BaseCircuit):
    """
    Class to read any cgmes-like set of files
    """

    def __init__(self,
                 text_func: Union[Callable, None] = None,
                 progress_func: Union[Callable, None] = None,
                 logger=DataLogger()):
        """
        CIM circuit constructor
        :param text_func: text callback function (optional)
        :param progress_func: progress callback function (optional)
        :param logger: DataLogger
        """
        BaseCircuit.__init__(self)

        self.text_func = text_func
        self.progress_func = progress_func
        self.logger: DataLogger = logger

        # file: Cim data of the file
        self.parsed_data = dict()

        # merged CGMES data (dictionary representation of the xml data)
        self.data: Dict[str, Dict[str, Dict[str, str]]] = dict()

        # boundary set data
        self.boudary_set: Dict[str, Dict[str, Dict[str, str]]] = dict()

        # store the CGMES version from the data files
        self.cgmes_version = ""

    def emit_text(self, val: str) -> None:
        """
        Emit text via the callback
        :param val: text value
        """
        if self.text_func is not None:
            self.text_func(val)

    def emit_progress(self, val: float) -> None:
        """
        Emit floating point values via the callback
        :param val: numeric value
        """
        if self.progress_func is not None:
            self.progress_func(val)

    def load_files(self, files: List[str]) -> None:
        """
        Load CIM file
        :param files: list of CIM files (.xml or .zip)
        """

        cgmes2_4_15_uri = ["http://entsoe.eu/CIM/EquipmentCore/3/1",
                           "http://entsoe.eu/CIM/EquipmentOperation/3/1",
                           "http://entsoe.eu/CIM/EquipmentShortCircuit/3/1",
                           "http://entsoe.eu/CIM/Topology/4/1",
                           "http://entsoe.eu/CIM/SteadyStateHypothesis/1/1",
                           "http://entsoe.eu/CIM/StateVariables/4/1"]
        cgmes3_0_0_uri = ["http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0",
                          "http://iec.ch/TC57/ns/CIM/SteadyStateHypothesis-EU/3.0",
                          "http://iec.ch/TC57/ns/CIM/StateVariables-EU/3.0",
                          "http://iec.ch/TC57/ns/CIM/Topology-EU/3.0"]
        # import the cim files' content into a dictionary
        data = read_cgmes_files(files)
        # Parse the files
        i = 0
        for file_name, file_data in data.items():
            name, file_extension = os.path.splitext(file_name)
            self.emit_text('Parsing xml structure of ' + name)
            file_cgmes_data = parse_xml_text(file_data)

            full_models_dict = file_cgmes_data.get('FullModel', None)
            difference_full_models_dict = file_cgmes_data.get('DifferenceModel', None)

            if full_models_dict:

                # get all the FullModel id's (should only be one of these)
                model_keys = list(file_cgmes_data['FullModel'])

                if len(model_keys) == 1:  # there must be exacly one FullModel
                    model_info = file_cgmes_data['FullModel'][model_keys[0]]
                    self.parsed_data[file_name] = file_cgmes_data
                    profile = model_info.get('profile', '')

                    for prof in profile:
                        if prof in cgmes2_4_15_uri:
                            self.cgmes_version = "2.4.15"
                        elif prof in cgmes3_0_0_uri:
                            self.cgmes_version = "3.0.0"

                    if isinstance(profile, list):
                        if 'Boundary' in profile[0]:
                            merge(self.boudary_set, file_cgmes_data, self.logger)
                        else:
                            merge(self.data, file_cgmes_data, self.logger)
                    else:
                        if 'Boundary' in profile:
                            merge(self.boudary_set, file_cgmes_data, self.logger)
                        else:
                            merge(self.data, file_cgmes_data, self.logger)

                else:
                    self.logger.add_error("File does not contain exactly one FullModel",
                                          device=file_name,
                                          device_class="",
                                          device_property='FullModel', value="", expected_value="FullModel",
                                          comment="This is not a proper CGMES file")

            elif difference_full_models_dict:

                model_keys = list(file_cgmes_data['DifferenceModel'])
                if len(model_keys) == 1:  # there must be exacly one Ontology
                    model_info = file_cgmes_data['DifferenceModel'][model_keys[0]]
                    self.parsed_data[file_name] = file_cgmes_data
                    profile = model_info.get('priorVersion', '')
                    self.cgmes_version = model_info.get('versionInfo', '')

                    for prof in profile:
                        if prof in cgmes2_4_15_uri:
                            self.cgmes_version = "2.4.15"
                        elif prof in cgmes3_0_0_uri:
                            self.cgmes_version = "3.0.0"

                    if 'Boundary' in profile:
                        merge(self.boudary_set, file_cgmes_data, self.logger)
                    else:
                        merge(self.data, file_cgmes_data, self.logger)
                else:
                    self.logger.add_error("File does not contain exactly one DifferenceModel",
                                          device=file_name,
                                          device_class="",
                                          device_property='DifferenceModel', value="", expected_value="DifferenceModel",
                                          comment="This is not a proper CGMES file")

            else:
                self.logger.add_error("File does not contain any FullModel or DifferenceModel",
                                      device=file_name,
                                      device_class="",
                                      device_property='FullModel', value="", expected_value="FullModel",
                                      comment="This is not a proper CGMES file")

            # emit progress
            self.emit_progress((i + 1) / len(data) * 100)
            i += 1

        self.emit_text('Done!')

    # def set_cgmes_version(self, profile):
    #     if profile == "":
    #         pass
