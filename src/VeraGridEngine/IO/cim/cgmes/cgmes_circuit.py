# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Union, Tuple, Callable
from enum import Enum, EnumMeta
import pandas as pd
import VeraGridEngine.IO.cim.cgmes.cgmes_assets.cgmes_2_4_15_assets as cgmes24
import VeraGridEngine.IO.cim.cgmes.cgmes_assets.cgmes_3_0_0_assets as cgmes30
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.IO.cim.cgmes.cgmes_property import CgmesProperty
from VeraGridEngine.IO.base.base_circuit import BaseCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType
from VeraGridEngine.IO.cim.cgmes.cgmes_typing import CGMES_ASSETS
from VeraGridEngine.IO.cim.cgmes.cgmes_data_parser import CgmesDataParser
from VeraGridEngine.enumerations import CGMESVersions


def find_attribute(obj: CGMES_ASSETS,
                   property_name: str,
                   association_inverse_dict: Dict[Tuple[str, str], str]):
    return association_inverse_dict.get((obj.tpe, property_name))


def find_references(elements_by_type: Dict[str, List[CGMES_ASSETS]],
                    all_objects_dict: Dict[str, CGMES_ASSETS],
                    all_objects_dict_boundary: Union[Dict[str, CGMES_ASSETS], None],
                    association_inverse_dict: Dict[Tuple[str, str], str],
                    logger: DataLogger,
                    mark_used: bool) -> None:
    """
    Replaces the references in the "actual" properties of the objects
    :param elements_by_type: Dictionary of elements by type to fill in (same as all_objects_dict but by categories)
    :param all_objects_dict: dictionary of all model objects to add Parsed objects
    :param all_objects_dict_boundary: dictionary of all boundary set objects to
                                      add Parsed objects used to find references
    :param logger: DataLogger
    :param mark_used: mark objects as used?
    :return: Nothing, it is done in place
    :param association_inverse_dict: Containing the name of the attributes which associate with each other.
    """
    added_from_the_boundary_set = list()
    # Store dictionary values in local variables
    elements_by_type_items = elements_by_type.items()
    # find cross-references
    for class_name, elements in elements_by_type_items:
        for element in elements:  # for every element of the type
            if mark_used:
                element.used = True

            # check the declared properties
            for property_name, cim_prop in element.declared_properties.items():

                # try to get the property value, else, fill with None
                # at this point val is always the string that came in the XML
                value = getattr(element, property_name)
                if value is not None and isinstance(value, CGMES_ASSETS):
                    continue

                if value is not None:  # if the value is something...

                    if cim_prop.class_type in [str, float, int, bool]:
                        # set the referenced object in the property
                        try:
                            if isinstance(value, list):
                                setattr(element, property_name, value)
                            else:
                                setattr(element, property_name, cim_prop.class_type(value))

                        except ValueError:
                            logger.add_error(msg='Value error',
                                             device=element.rdfid,
                                             device_class=class_name,
                                             device_property=property_name,
                                             value=value,
                                             expected_value=str(cim_prop.class_type))

                    elif isinstance(cim_prop.class_type, Enum) or isinstance(cim_prop.class_type, EnumMeta):

                        if type(value) == str:
                            chunks = value.split('.')
                            value2 = chunks[-1]
                            try:
                                enum_val = cim_prop.class_type(value2)
                                setattr(element, property_name, enum_val)

                            except TypeError as e:
                                logger.add_error(msg='Could not convert Enum',
                                                 device=element.rdfid,
                                                 device_class=class_name,
                                                 device_property=property_name,
                                                 value=value2 + " (value)",
                                                 expected_value=str(cim_prop.class_type))

                    else:
                        # search for the reference, if not found -> return None
                        if not isinstance(value, list):
                            referenced_object = all_objects_dict.get(value, None)

                            if referenced_object is None and all_objects_dict_boundary:
                                # search for the reference in the boundary set
                                referenced_object = all_objects_dict_boundary.get(value, None)

                                # add to the normal data if it wasn't added before
                                if referenced_object is not None and referenced_object.rdfid not in all_objects_dict:
                                    all_objects_dict[referenced_object.rdfid] = referenced_object
                                    added_from_the_boundary_set.append(referenced_object)

                            # if the reference was found in the data of the boundary set ...
                            if referenced_object is not None:
                                if mark_used:
                                    referenced_object.used = True

                                # set the referenced object in the property
                                setattr(element, property_name, referenced_object)
                                # register the inverse reference
                                ref_attribute = find_attribute(obj=element,
                                                               property_name=property_name,
                                                               association_inverse_dict=association_inverse_dict)
                                if ref_attribute is not None:
                                    referenced_object.add_reference(element, ref_attribute, logger=logger)

                            else:

                                # I want to know that it was not found
                                element.missing_references[property_name] = value

                                if hasattr(element, 'rdfid'):
                                    logger.add_error(msg='Reference not found',
                                                     device=element.rdfid,
                                                     device_class=class_name,
                                                     device_property=property_name,
                                                     value='Not found',
                                                     expected_value=value)
                                else:
                                    logger.add_error(msg='Reference not found for (debugger error)',
                                                     device=element.rdfid,
                                                     device_class=class_name,
                                                     device_property=property_name,
                                                     value='Not found',
                                                     expected_value=value)
                        else:
                            referenced_object_list = set()
                            for v in value:
                                if isinstance(v, CGMES_ASSETS):
                                    continue

                                referenced_object = all_objects_dict.get(v, None)

                                if referenced_object is None and all_objects_dict_boundary:
                                    # search for the reference in the boundary set
                                    referenced_object = all_objects_dict_boundary.get(v, None)

                                    # add to the normal data if it wasn't added before
                                    if referenced_object is not None and referenced_object.rdfid not in all_objects_dict:
                                        all_objects_dict[referenced_object.rdfid] = referenced_object
                                        added_from_the_boundary_set.append(referenced_object)

                                # if the reference was found in the data of the boundary set ...
                                if referenced_object is not None:
                                    if mark_used:
                                        referenced_object.used = True

                                    # set the referenced object in the property
                                    referenced_object_list.add(referenced_object)
                                    # register the inverse reference
                                    ref_attribute = find_attribute(obj=element,
                                                                   property_name=property_name,
                                                                   association_inverse_dict=association_inverse_dict)
                                    if ref_attribute is not None:
                                        referenced_object.add_reference(element, ref_attribute, logger=logger)

                                else:

                                    # I want to know that it was not found
                                    element.missing_references[property_name] = v

                                    if hasattr(element, 'rdfid'):
                                        logger.add_error(msg='Reference not found',
                                                         device=element.rdfid,
                                                         device_class=class_name,
                                                         device_property=property_name,
                                                         value='Not found',
                                                         expected_value=v)
                                    else:
                                        logger.add_error(msg='Reference not found for (debugger error)',
                                                         device=element.rdfid,
                                                         device_class=class_name,
                                                         device_property=property_name,
                                                         value='Not found',
                                                         expected_value=v)
                            if len(referenced_object_list) > 1:
                                setattr(element, property_name, list(referenced_object_list))
                            elif len(referenced_object_list) == 1:
                                setattr(element, property_name, list(referenced_object_list)[0])

                    if cim_prop.out_of_the_standard:
                        logger.add_warning(msg='Property supported but out of the standard',
                                           device=element.rdfid,
                                           device_class=class_name,
                                           device_property=property_name,
                                           value=value,
                                           expected_value="")

                else:
                    if cim_prop.mandatory:
                        logger.add_error(msg='Required property not provided',
                                         device=element.rdfid,
                                         device_class=class_name,
                                         device_property=property_name,
                                         value='not provided',
                                         expected_value=property_name)
                    else:
                        pass

    # modify the elements_by_type here adding the elements from the boundary set
    # all_elements_dict was modified in the previous loop
    for referenced_object in added_from_the_boundary_set:
        objects_list_ = elements_by_type.get(referenced_object.tpe, None)
        if objects_list_:
            objects_list_.append(referenced_object)
        else:
            elements_by_type[referenced_object.tpe] = [referenced_object]


def convert_data_to_objects(data: Dict[str, Dict[str, Dict[str, str]]],
                            all_objects_dict: Dict[str, CGMES_ASSETS],
                            all_objects_dict_boundary: Union[Dict[str, CGMES_ASSETS], None],
                            elements_by_type: Dict[str, List[CGMES_ASSETS]],
                            class_dict: Dict[str, CGMES_ASSETS],
                            association_inverse_dict,
                            logger: DataLogger) -> None:
    """
    Convert CGMES data dictionaries to proper CGMES objects
    :param data: source data to convert
    :param all_objects_dict: dictionary of all model objects to add Parsed objects
    :param all_objects_dict_boundary: dictionary of all boundary set objects to
                                      add Parsed objects used to find references
    :param elements_by_type: Dictionary of elements by type to fill in (same as all_objects_dict but by categories)
    :param class_dict: CgmesCircuit or None
    :param association_inverse_dict:
    :param logger:DataLogger
    :return: None
    """
    for class_name, objects_dict in data.items():

        objects_list = list()
        for rdfid, object_data in objects_dict.items():

            object_template = class_dict.get(class_name, None)

            if object_template is not None:

                parsed_object = object_template(rdfid=rdfid, tpe=class_name)

                if all_objects_dict_boundary is None:
                    parsed_object.boundary_set = True

                parsed_object.parse_dict(data=object_data, logger=logger)

                found = all_objects_dict.get(parsed_object.rdfid, None)

                if found is None:
                    all_objects_dict[parsed_object.rdfid] = parsed_object
                else:
                    if "Sv" not in class_name:
                        logger.add_error("Duplicated RDFID", device=class_name, value=parsed_object.rdfid)

                objects_list.append(parsed_object)

            else:
                logger.add_error("Class not recognized", device_class=class_name)

        elements_by_type[class_name] = objects_list

    # replace references by actual objects
    find_references(elements_by_type=elements_by_type,
                    all_objects_dict=all_objects_dict,
                    all_objects_dict_boundary=all_objects_dict_boundary,
                    association_inverse_dict=association_inverse_dict,
                    logger=logger,
                    mark_used=True)


def is_valid_cgmes(cgmes_version) -> bool:
    """
    Check if the version is CGMES
    :param cgmes_version:
    :return:
    """
    if cgmes_version == CGMESVersions.v2_4_15:
        return True
    elif cgmes_version == CGMESVersions.v3_0_0:
        return True
    else:
        return False


class CgmesCircuit(BaseCircuit):
    """
    CgmesCircuit
    """

    def __init__(self,
                 cgmes_version: CGMESVersions = CGMESVersions.v2_4_15,
                 cgmes_map_areas_like_raw: bool = False,
                 text_func: Union[Callable, None] = None,
                 progress_func: Union[Callable, None] = None,
                 logger=DataLogger()):
        """
        CIM circuit constructor
        :param cgmes_version:
        :param cgmes_map_areas_like_raw:
        :param text_func:
        :param progress_func:
        :param logger:
        """
        BaseCircuit.__init__(self)

        self.cgmes_version: CGMESVersions = cgmes_version
        self.cgmes_map_areas_like_raw = cgmes_map_areas_like_raw
        self.logger: DataLogger = logger

        self.text_func = text_func
        self.progress_func = progress_func

        if cgmes_version == CGMESVersions.v2_4_15:
            self.cgmes_assets = cgmes24.Cgmes_2_4_15_Assets()
        elif cgmes_version == CGMESVersions.v3_0_0:
            self.cgmes_assets = cgmes30.Cgmes_3_0_0_Assets()
        else:
            logger.add_error(msg=f"Unrecognized CGMES version {cgmes_version}")
            raise NotImplemented(f"Unrecognized CGMES version {cgmes_version}")

            # classes to read, theo others are ignored
        self.classes = [key for key, _ in self.cgmes_assets.class_dict.items()]

        # dictionary with all objects, useful to find repeated ID's
        self.all_objects_dict: Dict[str, CGMES_ASSETS] = dict()
        self.all_objects_dict_boundary: Dict[str, CGMES_ASSETS] = dict()

        # dictionary with elements by type
        self.elements_by_type: Dict[str, List[CGMES_ASSETS]] = dict()
        self.elements_by_type_boundary: Dict[str, List[CGMES_ASSETS]] = dict()

        # dictionary representation of the xml data
        self.data: Dict[str, Dict[str, Dict[str, str]]] = dict()
        self.boundary_set: Dict[str, Dict[str, Dict[str, str]]] = dict()

    @property
    def assets(self):
        """

        :return:
        """
        if self.cgmes_version == CGMESVersions.v2_4_15:
            return cgmes24
        elif self.cgmes_version == CGMESVersions.v3_0_0:
            return cgmes30
        else:
            raise NotImplementedError()

    def parse_files(self, data_parser: CgmesDataParser, delete_unused=True, detect_circular_references=False):
        """
        Parse CGMES files into this class
        :param delete_unused: Delete the unused boundary set?
        :param data_parser: getting the read files
        :param detect_circular_references: report the circular references
        """

        # read the CGMES data as dictionaries
        # data_parser = CgmesDataParser(text_func=self.text_func,
        #                               progress_func=self.progress_func,
        #                               logger=self.logger)
        # data_parser.load_files(files=files)

        self.emit_text("Processing CGMES model")
        self.emit_progress(20)
        # set the data
        self.set_data(data=data_parser.data, boundary_set=data_parser.boundary_set)
        self.emit_progress(25)
        # convert the dictionaries to the internal class model for the boundary set
        # do not mark the boundary set objects as used
        convert_data_to_objects(data=self.boundary_set,
                                all_objects_dict=self.all_objects_dict_boundary,
                                all_objects_dict_boundary=None,
                                elements_by_type=self.elements_by_type_boundary,
                                class_dict=self.cgmes_assets.class_dict,
                                association_inverse_dict=self.cgmes_assets.association_inverse_dict,
                                logger=self.logger)

        self.emit_progress(33)
        # convert the dictionaries to the internal class model,
        # this marks as used only the boundary set objects that are referenced,
        # this allows to delete_with_dialogue the excess of boundary set objects later
        convert_data_to_objects(data=self.data,
                                all_objects_dict=self.all_objects_dict,
                                all_objects_dict_boundary=self.all_objects_dict_boundary,
                                elements_by_type=self.elements_by_type,
                                class_dict=self.cgmes_assets.class_dict,
                                association_inverse_dict=self.cgmes_assets.association_inverse_dict,
                                logger=self.logger)

        # Assign the data from all_objects_dict to the appropriate lists in the circuit
        self.emit_progress(42)
        self.assign_data_to_lists()

        if delete_unused:
            # delete_with_dialogue the unused objects from the boundary set
            self.delete_unused()

        if detect_circular_references:
            # for reporting porpuses, detect the circular references in the model due to polymorphism
            self.detect_circular_references()
        self.emit_progress(50)

    def assign_data_to_lists(self) -> None:
        """
        Assign the data from all_objects_dict to the appropriate lists in the circuit
        :return: Nothing
        """
        for object_id, parsed_object in self.all_objects_dict.items():

            # add to its list
            list_name = parsed_object.tpe + '_list'
            if hasattr(self.cgmes_assets, list_name):
                getattr(self.cgmes_assets, list_name).append(parsed_object)
            else:
                print('Missing list:', list_name)

    def set_data(self, data: Dict[str, Dict[str, Dict[str, str]]], boundary_set: Dict[str, Dict[str, Dict[str, str]]]):
        """

        :param data:
        :param boundary_set:
        :return:
        """
        self.data = data
        self.boundary_set = boundary_set

    def meta_programmer(self):
        """
        This function is here to help in the class programming by inverse engineering
        :return:
        """
        for key, obj_list in self.cgmes_assets.class_dict.items():

            if not hasattr(self, key + '_list'):
                print('self.{0}_list: List[{0}] = list()'.format(key))

    def add(self, elm: CGMES_ASSETS):
        """
        Add generic object to the circuit
        :param elm: any CGMES object
        :return: True if successful, False otherwise
        """
        """
        self.elements = list()
        self.all_objects_dict: Dict[str, cimdev.IdentifiedObject] = dict()
        self.elements_by_type: Dict[str, List[cimdev.IdentifiedObject]] = dict()
        """

        # find if the element was added before
        collided = self.all_objects_dict.get(elm.rdfid, None)

        if collided is not None:
            self.logger.add_error("RDFID collision, element not added",
                                  device_class=elm.tpe,
                                  device=elm.rdfid,
                                  comment="Collided object {0}:{1} ({2})".format(collided.tpe,
                                                                                 collided.rdfid,
                                                                                 collided.shortName))
            return False

        self.all_objects_dict[elm.rdfid] = elm

        if elm.tpe in self.elements_by_type:
            self.elements_by_type[elm.tpe].append(elm)
        else:
            self.elements_by_type[elm.tpe] = [elm]

        # add to its list
        list_name = elm.tpe + '_list'
        if hasattr(self.cgmes_assets, list_name):
            getattr(self.cgmes_assets, list_name).append(elm)
        else:
            print('Missing list:', list_name)

        return True

    def get_properties(self) -> List[CgmesProperty]:
        """
        Get list of CIM properties
        :return:
        """
        data = list()
        for name, cls in self.cgmes_assets.class_dict.items():
            data.append(CgmesProperty(property_name=name, class_type=cls))
        return data

    def get_class_properties(self) -> List[CgmesProperty]:
        """

        :return:
        """
        return [p for p in self.get_properties() if p.class_type not in [str, bool, int, float]]

    def get_objects_list(self, elm_type):
        """

        :param elm_type:
        :return:
        """
        return self.elements_by_type.get(elm_type, [])

    def emit_text(self, val):
        """

        :param val:
        """
        if self.text_func is not None:
            self.text_func(val)

    def emit_progress(self, val):
        """

        :param val:
        """
        if self.progress_func is not None:
            self.progress_func(val)

    def clear(self):
        """
        Clear the circuit
        """
        self.all_objects_dict = dict()
        self.elements_by_type = dict()

    @staticmethod
    def check_type(xml, class_types, starters=None, enders=None):
        """
        Checks if we are starting an object of the predefined types
        :param xml: some text
        :param class_types: list of CIM types
        :param starters list of possible string to add prior to the class when opening an object
        :param enders list of possible string to add prior to a class when closing an object
        :return: start_recording, end_recording, the found type or None if no one was found
        """

        # for each type
        if starters is None:
            starters = ['<cim:', '<md:']

        if enders is None:
            enders = ['</cim:', '</md:']

        for tpe in class_types:

            for starter, ender in zip(starters, enders):
                # if the starter token is found: this is the beginning of an object
                if starter + tpe + ' rdf:ID' in xml:
                    return True, False, tpe

                # if the starter token is found: this is the beginning of an object (only in the topology definition)
                elif starter + tpe + ' rdf:about' in xml:
                    return True, False, tpe

                # if the ender token is found: this is the end of an object
                elif ender + tpe + '>' in xml:
                    return False, True, tpe

        # otherwise, this is neither the beginning nor the end of an object
        return False, False, ""

    def delete_unused(self) -> None:
        """
        Delete elements that have no references to them
        """
        elements_by_type = dict()
        all_objects_dict = dict()

        # delete_with_dialogue elements without references
        for class_name, elements in self.elements_by_type.items():

            objects_list = list()

            for element in elements:  # for every element of the type

                if element.can_keep():
                    all_objects_dict[element.rdfid] = element
                    objects_list.append(element)
                else:
                    print('deleted', element)

            elements_by_type[class_name] = objects_list

        # replace
        self.elements_by_type = elements_by_type
        self.all_objects_dict = all_objects_dict

    def parse_xml_text(self, text_lines):
        """
        Fill the XML into the objects
        :param text_lines:
        :return:
        """

        xml_string = "".join(text_lines)

        import xml.etree.ElementTree as ET

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
                  B: Dict[str, Dict[str, Dict[str, str]]]):
            """
            Modify A using B
            :param A: CIM data dictionary to be modified in-place
            :param B: CIM data dictionary used to modify A
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
                                        self.logger.add_warning("Overwriting value",
                                                                device=str(obj_a),
                                                                device_class=class_name_b,
                                                                device_property=prop_name,
                                                                value=value_b,
                                                                expected_value=value_a)
                                    else:
                                        # the assigning value from B is the same as the already stored in A
                                        pass

        root = ET.fromstring(xml_string)
        new_cim_data = parse_xml_to_dict(root)
        merge(self.data, new_cim_data)

    def get_data_frames_dictionary(self):
        """
        Get dictionary of DataFrames
        :return: dictionary of DataFrames
        """
        dfs = dict()
        for class_name, elements in self.elements_by_type.items():
            values = [element.get_dict() for element in elements]
            dfs[class_name] = pd.DataFrame(values)

        return dfs

    def to_excel(self, fname):
        """

        :param fname:
        :return:
        """
        if self.text_func is not None:
            self.text_func('Saving to excel')

        dfs = self.get_data_frames_dictionary()

        keys = list(dfs.keys())
        keys.sort()

        n = len(keys)
        writer = pd.ExcelWriter(fname)
        for i, class_name in enumerate(keys):

            if self.progress_func is not None:
                self.progress_func((i + 1) / n * 100.0)

            if self.text_func is not None:
                self.text_func('Saving {} to excel'.format(class_name))

            df = dfs[class_name]
            df.to_excel(writer, sheet_name=class_name, index=True)
        writer._save()

    def detect_circular_references(self):
        """
        Detect circular references
        """
        for rdfid, elm in self.all_objects_dict.items():
            visited = list()
            is_loop = elm.detect_circular_references(visited)

            if is_loop:
                self.logger.add_warning(msg="Linking loop",
                                        device=elm.rdfid,
                                        device_class=elm.tpe,
                                        value=str(len(visited)))

    def get_circular_references(self) -> List[List[CGMES_ASSETS]]:
        """
        Detect circular references
        """
        res = list()
        for rdfid, elm in self.all_objects_dict.items():
            visited = list()
            is_loop = elm.detect_circular_references(visited)

            if is_loop:
                res.append([self.all_objects_dict[v] for v in visited])

        return res

    def get_model_xml(self, profiles=None) -> Dict[CgmesProfileType, str]:
        """
        Get a dictionary of xml per CGMES profile
        :param profiles: list of profiles to acquire
        :returns Dictionary  Dict[cgmesProfile, str]
        """
        if profiles is None:
            profiles = [CgmesProfileType.EQ]

        data = dict()
        for tpe, elm_list in self.elements_by_type.items():

            for elm in elm_list:

                elm_data = elm.get_xml(level=0, profiles=profiles)

                for profile, txt in elm_data.items():

                    if profile in data:
                        data[profile] += txt
                    else:
                        data[profile] = txt
        return data
