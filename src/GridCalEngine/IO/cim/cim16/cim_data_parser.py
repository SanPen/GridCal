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
from collections.abc import Callable
from typing import Dict, List, Union
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

            objects_list = result.get(class_name, None)

            if objects_list is None:
                result[class_name] = {obj_id: child_result}
            else:
                objects_list[obj_id] = child_result
        else:
            if child.text is None:
                result[class_name] = obj_id  # it is a resource id
            else:
                result[class_name] = child.text

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


def read_cim_files(cim_files: Union[List[str], str]):
    """
    Reads a list of .zip or xml into a dictionary of file name -> list of text lines
    :param cim_files: list of file names
    :return: dictionary of file name -> list of text lines
    """
    # read files and sort them in the preferred reading order
    data = dict()

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


def sort_cim_files(file_names):
    """
    Sorts the CIM files in the preferred reading order
    :param file_names: lis of file names
    :return: sorted list of file names
    """
    # sort the files
    lst = list()
    nn = len(file_names)
    for i in range(nn - 1, -1, -1):
        f = file_names[i]
        if 'TP' in f or 'TPDB' in f:
            lst.append(file_names.pop(i))

    nn = len(file_names)
    for i in range(nn - 1, -1, -1):
        f = file_names[i]
        if 'EQ' in f or 'EQBD' in f:
            lst.append(file_names.pop(i))

    lst2 = lst + file_names

    return lst2


class CimDataParser(BaseCircuit):
    """
    Class to read any cim-like set of files
    """

    def __init__(self,
                 text_func: Union[Callable, None] = None,
                 progress_func: Union[Callable, None] = None,
                 logger=DataLogger()):
        """
        CIM circuit constructor
        """
        BaseCircuit.__init__(self)

        self.logger: DataLogger = logger

        self.text_func = text_func
        self.progress_func = progress_func

        # dictionary representation of the xml data
        self.cim_data: Dict[str, Dict[str, Dict[str, str]]] = dict()

    def emit_text(self, val: str) -> None:
        """

        :param val:
        """
        if self.text_func is not None:
            self.text_func(val)

    def emit_progress(self, val: float) -> None:
        """

        :param val:
        """
        if self.progress_func is not None:
            self.progress_func(val)

    def parse_xml_text(self, text_lines: List[str]) -> None:
        """
        Fill the XML into the objects
        :param text_lines:
        """

        xml_string = "".join(text_lines)

        root = ET.fromstring(xml_string)
        new_cim_data = parse_xml_to_dict(root)
        merge(self.cim_data, new_cim_data, self.logger)

    def load_cim_file(self, cim_files: List[str]) -> None:
        """
        Load CIM file
        :param cim_files: list of CIM files (.xml)
        """

        # import the cim files' content into a dictionary
        data = read_cim_files(cim_files)

        lst2 = sort_cim_files(list(data.keys()))

        # Parse the files
        for i, f in enumerate(lst2):
            name, file_extension = os.path.splitext(f)
            self.emit_text('Parsing xml structure of ' + name)
            self.parse_xml_text(text_lines=data[f])
            self.emit_progress((i + 1) / len(lst2) * 100)

        self.emit_text('Done!')
