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

import chardet
import pandas as pd
from typing import Set, Dict, List, Tuple
from GridCal.Engine.basic_structures import Logger
import GridCal.Engine.IO.cim.cim_devices as cimdev


class CIMCircuit:

    def __init__(self, text_func=None, progress_func=None, logger=Logger()):
        """
        CIM circuit constructor
        """
        self.elements = list()
        self.elm_dict = dict()
        self.elements_by_type = dict()

        self.logger = logger

        self.text_func = text_func
        self.progress_func = progress_func

        # classes to read, theo others are ignored
        self.classes = ["ACLineSegment",
                        "Analog",
                        "BaseVoltage",
                        "Breaker",
                        "BusbarSection",
                        "ConformLoad",
                        "ConformLoadSchedule",
                        "ConnectivityNode",
                        "Control",
                        "CurrentLimit",
                        "DayType",
                        "Disconnector",
                        "Discrete",
                        "EnergyConsumer",
                        "EquivalentInjection",
                        "EquivalentNetwork",
                        "EquipmentContainer",
                        "GeneratingUnit",
                        "GeographicalRegion",
                        "SubGeographicalRegion",
                        "IEC61970CIMVersion",
                        "Line",
                        "LoadBreakSwitch",
                        "LoadResponseCharacteristic",
                        "Location",
                        "Model",
                        "OperationalLimitSet",
                        "PerLengthSequenceImpedance",
                        "PositionPoint",
                        "PowerTransformer",
                        "PowerTransformerEnd",
                        "PSRType",
                        "RatioTapChanger",
                        "RegulatingControl",
                        "Season",
                        "SeriesCompensator",
                        "ShuntCompensator",
                        "Substation",
                        "Switch",
                        "SynchronousMachine",
                        "Terminal",
                        "TopologicalNode",
                        "TransformerWinding",
                        "VoltageLevel",
                        "VoltageLimit"
                        ]

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
        self.elm_dict = dict()
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

        # find cross references
        for class_name, elements in self.elements_by_type.items():
            for element in elements:  # for every element of the type
                for prop, value in element.properties.items():  # for every registered property
                    if len(value) > 0:  # if the property value is something
                        if value[0] == '_':  # the value is an RFID reference
                            if hasattr(element, prop):  # if the object has the property to cross reference
                                if value in self.elm_dict.keys():  # if the reference was found ...
                                    ref = self.elm_dict[value]
                                    setattr(element, prop, ref)  # set the referenced object in the property
                                    ref.add_reference(element)  # register the inverse reference
                                else:
                                    setattr(element, prop, None)  # I want to know that it was not found
                                    self.logger.add_error(prop + ' reference not found for ' + class_name,
                                                          element.rfid, '', value)

    def parse_xml_text(self, text_lines):
        """
        Fill the XML into the objects
        :param text_lines:
        :return:
        """

        class_dict = {'GeneralContainer': cimdev.GeneralContainer,
                      'Terminal': cimdev.Terminal,
                      'BaseVoltage': cimdev.BaseVoltage,
                      'TopologicalNode': cimdev.TopologicalNode,
                      'BusbarSection': cimdev.BusbarSection,
                      'Substation': cimdev.Substation,
                      'ConnectivityNode': cimdev.ConnectivityNode,
                      'OperationalLimitSet': cimdev.OperationalLimitSet,
                      'GeographicalRegion': cimdev.GeographicalRegion,
                      'SubGeographicalRegion': cimdev.SubGeographicalRegion,
                      'VoltageLevel': cimdev.VoltageLevel,
                      'CurrentLimit': cimdev.CurrentLimit,
                      'VoltageLimit': cimdev.VoltageLimit,
                      'EquivalentInjection': cimdev.EquivalentInjection,
                      'EquivalentNetwork': cimdev.EquivalentNetwork,
                      'Breaker': cimdev.Breaker,
                      'Switch': cimdev.Switch,
                      "LoadBreakSwitch": cimdev.LoadBreakSwitch,
                      'Line': cimdev.Line,
                      'ACLineSegment': cimdev.ACLineSegment,
                      'PowerTransformerEnd': cimdev.PowerTransformerEnd,
                      'PowerTransformer': cimdev.PowerTransformer,
                      'Winding': cimdev.Winding,
                      'EnergyConsumer': cimdev.EnergyConsumer,
                      'ConformLoad': cimdev.ConformLoad,
                      'NonConformLoad': cimdev.NonConformLoad,
                      'LoadResponseCharacteristic': cimdev.LoadResponseCharacteristic,
                      'RegulatingControl': cimdev.RegulatingControl,
                      'RatioTapChanger': cimdev.RatioTapChanger,
                      'GeneratingUnit': cimdev.GeneratingUnit,
                      'SynchronousMachine': cimdev.SynchronousMachine,
                      'HydroGenerationUnit': cimdev.HydroGenerationUnit,
                      'HydroPowerPlant': cimdev.HydroPowerPlant,
                      'LinearShuntCompensator': cimdev.LinearShuntCompensator,
                      'NuclearGeneratingUnit': cimdev.NuclearGeneratingUnit,
                      'RatioTapChangerTable': cimdev.RatioTapChangerTable,
                      'RatioTapChangerTablePoint': cimdev.RatioTapChangerTablePoint,
                      'ReactiveCapabilityCurve': cimdev.ReactiveCapabilityCurve,
                      'StaticVarCompensator': cimdev.StaticVarCompensator,
                      'TapChangerControl': cimdev.TapChangerControl,
                      'ThermalGenerationUnit': cimdev.ThermalGenerationUnit,
                      'WindGenerationUnit': cimdev.WindGenerationUnit,
                      'FullModel': cimdev.FullModel,
                      'TieFlow': cimdev.TieFlow}

        classes = self.classes

        # add the classes that may be missing from the classes dict
        classes = set(classes)
        for cls in class_dict.keys():
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
                        if tpe in class_dict.keys():
                            CLS = class_dict[tpe]
                        else:
                            CLS = cimdev.GeneralContainer
                        element = CLS(id, tpe)

                        recording = True

                    if end_rec:
                        # stop recording object
                        if recording:

                            if element.rfid in self.elm_dict.keys():
                                found_element = self.elm_dict[element.rfid]
                                found_element.merge(element)

                            else:
                                self.elm_dict[element.rfid] = element
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

        writer = pd.ExcelWriter(fname)
        for class_name in keys:
            df = dfs[class_name]
            try:
                df.to_excel(writer, sheet_name=class_name, index=False)
            except:
                print('Error exporting', class_name)
        writer.save()

