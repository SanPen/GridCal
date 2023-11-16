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
from enum import Enum, EnumMeta
import chardet
import pandas as pd
from GridCalEngine.basic_structures import Logger
import GridCalEngine.IO.cim.cim16.cim_devices as cimdev


class CIMCircuit:

    def __init__(self, text_func=None, progress_func=None, logger=Logger()):
        """
        CIM circuit constructor
        """
        self.elements = list()
        self.all_objects_dict = dict()
        self.elements_by_type = dict()

        self.logger = logger

        self.text_func = text_func
        self.progress_func = progress_func

        self.class_dict = {'GeneralContainer': cimdev.IdentifiedObject,
                           'Terminal': cimdev.Terminal,
                           'BaseVoltage': cimdev.BaseVoltage,
                           'TopologicalNode': cimdev.TopologicalNode,
                           'BusbarSection': cimdev.BusbarSection,
                           'BusNameMarker': cimdev.BusNameMarker,
                           'Substation': cimdev.Substation,
                           'ConnectivityNode': cimdev.ConnectivityNode,
                           'OperationalLimitSet': cimdev.OperationalLimitSet,
                           'OperationalLimitType': cimdev.OperationalLimitType,
                           'GeographicalRegion': cimdev.GeographicalRegion,
                           'SubGeographicalRegion': cimdev.SubGeographicalRegion,
                           'VoltageLevel': cimdev.VoltageLevel,
                           'CurrentLimit': cimdev.CurrentLimit,
                           'VoltageLimit': cimdev.VoltageLimit,
                           'EquivalentInjection': cimdev.EquivalentInjection,
                           'EquivalentNetwork': cimdev.EquivalentNetwork,
                           'ControlArea': cimdev.ControlArea,
                           'Breaker': cimdev.Breaker,
                           'Switch': cimdev.Switch,
                           "LoadBreakSwitch": cimdev.LoadBreakSwitch,
                           'Line': cimdev.Line,
                           'ACLineSegment': cimdev.ACLineSegment,
                           'PowerTransformerEnd': cimdev.PowerTransformerEnd,
                           'PowerTransformer': cimdev.PowerTransformer,
                           # 'Winding': cimdev.Winding,
                           'EnergyConsumer': cimdev.EnergyConsumer,
                           'EnergyArea': cimdev.EnergyArea,
                           'ConformLoad': cimdev.ConformLoad,
                           'NonConformLoad': cimdev.NonConformLoad,
                           'LoadResponseCharacteristic': cimdev.LoadResponseCharacteristic,
                           'LoadGroup': cimdev.LoadGroup,
                           'RegulatingControl': cimdev.RegulatingControl,
                           'RatioTapChanger': cimdev.RatioTapChanger,
                           'GeneratingUnit': cimdev.GeneratingUnit,
                           'SynchronousMachine': cimdev.SynchronousMachine,
                           'HydroPump': cimdev.HydroPump,
                           'RotatingMachine': cimdev.RotatingMachine,
                           'HydroGenerationUnit': cimdev.HydroGeneratingUnit,  # todo: should this exist?
                           'HydroGeneratingUnit': cimdev.HydroGeneratingUnit,
                           'HydroPowerPlant': cimdev.HydroPowerPlant,
                           'LinearShuntCompensator': cimdev.LinearShuntCompensator,
                           'NuclearGeneratingUnit': cimdev.NuclearGeneratingUnit,
                           'RatioTapChangerTable': cimdev.RatioTapChangerTable,
                           'RatioTapChangerTablePoint': cimdev.RatioTapChangerTablePoint,
                           'ReactiveCapabilityCurve': cimdev.ReactiveCapabilityCurve,
                           'StaticVarCompensator': cimdev.StaticVarCompensator,
                           'TapChangerControl': cimdev.TapChangerControl,
                           'ThermalGenerationUnit': cimdev.ThermalGeneratingUnit,  # todo: should this exist?
                           'ThermalGeneratingUnit': cimdev.ThermalGeneratingUnit,
                           'WindGenerationUnit': cimdev.WindGeneratingUnit,  # todo: should this exist?
                           'WindGeneratingUnit': cimdev.WindGeneratingUnit,
                           'FullModel': cimdev.FullModel,
                           'TieFlow': cimdev.TieFlow}

        # classes to read, theo others are ignored
        self.classes = [key for key, va in self.class_dict.items()]

    def emit_text(self, val):
        if self.text_func is not None:
            self.text_func(val)

    def emit_progress(self, val):
        if self.progress_func is not None:
            self.progress_func(val)

    def clear(self):
        """
        Clear the circuit
        """
        self.elements = list()
        self.all_objects_dict = dict()
        self.elements_by_type = dict()

    @staticmethod
    def check_type(xml, class_types, starter='<cim:', ender='</cim:'):
        """
        Checks if we are starting an object of the predefined types
        :param xml: some text
        :param class_types: list of CIM types
        :param starter string to add prior to the class when opening an object
        :param ender string to add prior to a class when closing an object
        :return: start_recording, end_recording, the found type or None if no one was found
        """

        # for each type
        for tpe in class_types:

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

    def find_references(self):
        """
        Replaces the references in the "actual" properties of the objects
        :return: Nothing, it is done in place
        """

        found_classes = list(self.elements_by_type.keys())

        # find cross-references
        for class_name, elements in self.elements_by_type.items():
            for element in elements:  # for every element of the type

                # check the declared properties
                for property_name, cim_prop in element.declared_properties.items():

                    # try to get the property value, else, fill with None
                    # at this point val is always the string that came in the XML
                    value = element.parsed_properties.get(property_name, None)

                    if value is not None:

                        if cim_prop.class_type in [str, float, int, bool]:
                            # set the referenced object in the property
                            setattr(element, property_name, cim_prop.class_type(value))

                        elif isinstance(cim_prop.class_type, Enum) or isinstance(cim_prop.class_type, EnumMeta):

                            chunks = value.split('.')
                            value2 = chunks[-1]
                            try:
                                enum_val = cim_prop.class_type(value2)
                                setattr(element, property_name, enum_val)
                            except TypeError as e:
                                self.logger.add_error(msg='Could not convert Enum',
                                                      device="{0}.{1}.{2}".format(element.rdfid, class_name, property_name),
                                                      value=value2 + " (value)",
                                                      expected_value=str(cim_prop.class_type))

                        else:
                            # search for the reference, if not found -> return None
                            referenced_object = self.all_objects_dict.get(value, None)

                            if referenced_object is not None:  # if the reference was found ...

                                # set the referenced object in the property
                                setattr(element, property_name, referenced_object)

                                # register the inverse reference
                                referenced_object.add_reference(element)

                                # check that the type matches the expected type
                                if cim_prop.class_type in [cimdev.ConnectivityNodeContainer, cimdev.IdentifiedObject]:
                                    # the container class is too generic...
                                    pass
                                else:
                                    if not isinstance(referenced_object, cim_prop.class_type) and \
                                            cim_prop.class_type != cimdev.EquipmentContainer:
                                        # if the class specification does not match but the
                                        # required type is also not a generic polymorphic object ...
                                        cls = str(cim_prop.class_type).split('.')[-1].replace("'", "").replace(">", "")
                                        self.logger.add_error(msg='Object type different from expected',
                                                              device="{0}.{1}.{2}".format(element.rdfid, class_name, property_name),
                                                              value=referenced_object.tpe,
                                                              expected_value=cls)
                            else:

                                # I want to know that it was not found
                                element.missing_references[property_name] = value

                                if hasattr(element, 'rdfid'):
                                    self.logger.add_error(msg='Reference not found',
                                                          device="{0}.{1}.{2}".format(element.rdfid, class_name, property_name),
                                                          value='Not found',
                                                          expected_value=value)
                                else:
                                    self.logger.add_error(msg='Reference not found for (debugger error)',
                                                          device="{0}.{1}.{2}".format(element.rdfid, class_name, property_name),
                                                          value='Not found',
                                                          expected_value=value)

                        if cim_prop.out_of_the_standard:
                            self.logger.add_warning(msg='Property supported but out of the standard',
                                                    device="{0}.{1}.{2}".format(element.rdfid, class_name, property_name),
                                                    value=value,
                                                    expected_value="")

                    else:
                        if cim_prop.mandatory:
                            self.logger.add_error(msg='Required property not provided',
                                                  device="{0}.{1}.{2}".format(element.rdfid, class_name, property_name),
                                                  value='not provided',
                                                  expected_value=property_name)
                        else:
                            pass
                            # if not cim_prop.out_of_the_standard:
                            #     self.logger.add_warning(msg='Optional property not provided',
                            #                             device=element.rdfid,
                            #                             device_class=class_name,
                            #                             device_property=property_name,
                            #                             value='not provided',
                            #                             expected_value=property_name)

                # check those properties that were parsed but are not recognised
                for property_name, value in element.parsed_properties.items():

                    if property_name not in element.declared_properties:
                        self.logger.add_warning(msg='Unsupported property provided',
                                                device="{0}.{1}.{2}".format(element.rdfid, class_name, property_name),
                                                value=value,
                                                expected_value="")

                # check the object rules
                element.check(logger=self.logger)

    def parse_xml_text(self, text_lines):
        """
        Fill the XML into the objects
        :param text_lines:
        :return:
        """

        classes = self.classes

        # add the classes that may be missing from the classes dict
        classes = set(classes)
        for cls in self.class_dict.keys():
            classes.add(cls)
        classes = list(classes)

        recording = False
        disabled = False

        n_lines = len(text_lines)

        for line_idx, xml_line in enumerate(text_lines):

            if '<!--' in xml_line:
                disabled = True

            if not disabled:

                # determine if the line opens or closes and object
                # and of which type of the ones pre-specified
                start_rec, end_rec, tpe = self.check_type(xml_line, classes)

                if tpe != "":
                    # a recognisable object was found

                    if start_rec:
                        id = cimdev.index_find(xml_line, '"', '">').replace('#', '')

                        # start recording object
                        CLS = self.class_dict.get(tpe, cimdev.IdentifiedObject)
                        # if tpe in class_dict.keys():
                        #     CLS = class_dict[tpe]
                        # else:
                        #     CLS = cimdev.GeneralContainer
                        element = CLS(id, tpe)

                        recording = True

                    if end_rec:
                        # stop recording object
                        if recording:

                            found_element = self.all_objects_dict.get(element.rdfid, None)

                            if found_element is not None:
                                found_element.merge(element)

                            else:
                                self.all_objects_dict[element.rdfid] = element
                                self.elements.append(element)

                                if tpe not in self.elements_by_type.keys():
                                    self.elements_by_type[tpe] = list()

                                self.elements_by_type[tpe].append(element)

                            recording = False

                else:
                    # process line
                    if recording:
                        element.parse_line(xml_line)
            else:
                # the line is a comment
                if '-->' in xml_line:
                    disabled = False

            self.emit_progress((line_idx + 1) / n_lines * 100.0)

    def parse_file(self, file_name):
        """
        Parse CIM file and add all the recognised objects
        :param file_name:  file name or path
        :return:
        """

        # make a guess of the file encoding
        detection = chardet.detect(open(file_name, "rb").read())

        # Read text file line by line
        with open(file_name, 'r', encoding=detection['encoding']) as file_pointer:
            text_lines = [l for l in file_pointer]

        self.parse_xml_text(text_lines)

    def get_data_frames_dictionary(self):
        """
        Get dictionary of DataFrames
        :return: dictionary of DataFrames
        """
        dfs = dict()
        for class_name, elements in self.elements_by_type.items():
            values = [element.get_dict() for element in elements]

            try:
                df = pd.DataFrame(values)
                dfs[class_name] = df
            except:
                print('Error making DataFrame out of', class_name)

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

        with pd.ExcelWriter(fname) as writer:  # pylint: disable=abstract-class-instantiated
            for class_name in keys:
                df = dfs[class_name]
                try:
                    df.to_excel(writer, sheet_name=class_name, index=False)
                except:
                    print('Error exporting', class_name)
