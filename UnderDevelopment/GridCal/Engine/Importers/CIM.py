# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.


def index_find(string, start, end):
    """
    version of substring that matches
    :param string: string
    :param start: string to start splitting
    :param end: string to end splitting
    :return: string between start and end
    """
    return string.partition(start)[2].partition(end)[0]


class GeneralContainer:

    def __init__(self, header, tpe):
        """
        General CIM object container
        :param header: object xml header
        :param tpe: type of the object (class)
        """
        self.properties = dict()

        # store the object type
        self.tpe = tpe

        # pick the object id
        self.id = index_find(header, '"', '">').replace('#', '')

        self.terminals = list()

    def parse_line(self, line):
        """
        Parse xml line that eligibly belongs to this object
        :param line: xml text line
        """

        # the parsers are lists of 2 sets of separators
        # the first separator tries to substring the property name
        # the second tries to substring the property value
        parsers = [[('.', '>'), ('>', '<')],
                   [('.', ' rdf:resource'), ('rdf:resource="', '"')]]

        for L1, L2 in parsers:
            # try to parse the property
            prop = index_find(line, L1[0], L1[1])

            # try to parse the value
            val = index_find(line, L2[0], L2[1])

            # remove the pound
            if len(val) > 0:
                if val[0] == '#':
                    val = val[1:]

            if prop is not "":
                if val not in ["", "\n"]:
                    self.properties[prop] = val

    def merge(self, other):
        """
        Merge the properties of this object with another
        :param other: GeneralContainer instance
        """
        self.properties = {**self.properties, **other.properties}

    def print(self):
        print('Type:' + self.tpe)
        print('Id:' + self.id)

        for key in self.properties.keys():
            val = self.properties[key]

            if type(val) == GeneralContainer:
                for key2 in val.properties.keys():
                    val2 = val.properties[key2]
                    print(key, '->', key2, ':', val2)
            else:
                print(key, ':', val)

    def __str__(self):
        return self.tpe + ':' + self.id


class ACLineSegment(GeneralContainer):

    def __init__(self, header, tpe):
        GeneralContainer.__init__(self, header, tpe)

        self.base_voltage = list()


class PowerTransformer(GeneralContainer):

    def __init__(self, header, tpe):
        GeneralContainer.__init__(self, header, tpe)

        self.windings = list()


class Winding(GeneralContainer):

    def __init__(self, header, tpe):
        GeneralContainer.__init__(self, header, tpe)

        self.tap_changers = list()


class ConformLoad(GeneralContainer):

    def __init__(self, header, tpe):
        GeneralContainer.__init__(self, header, tpe)

        self.load_response_characteristics = list()


class SynchronousMachine(GeneralContainer):

    def __init__(self, header, tpe):
        GeneralContainer.__init__(self, header, tpe)

        self.base_voltage = list()

        self.regulating_control = list()

        self.generating_unit = list()


class CIMCircuit:

    def __init__(self):
        """
        CIM circuit constructor
        """
        self.elements = list()
        self.elm_dict = dict()
        self.elements_by_type = dict()

        # classes to read, theo others are ignored
        self.classes = ['ACLineSegment',
                        'BaseVoltage',
                        'BusbarSection',
                        'ConformLoad',
                        'GeneratingUnit',
                        'LoadResponseCharacteristic',
                        'PowerTransformer',
                        'RatioTapChanger',
                        'RegulatingControl',
                        'ShuntCompensator',
                        'SynchronousMachine',
                        'Terminal',
                        'TransformerWinding',
                        'VoltageLimit',
                        'TopologicalNode',
                        'ConnectivityNode',
                        'Breaker',
                        'Disconnector',
                        'EnergyConsumer',
                        'PowerTransformerEnd',
                        'EquivalentNetwork',
                        'EquivalentInjection']

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
        Replaces the references of the classes given
        :return:
        """

        # for every element
        for element in self.elements:

            # for each property in the element
            # for prop in element.properties.keys():
            for prop, ref_code in element.properties.items():
                # if the property is in the selected classes
                # if prop in classes:

                # get the reference
                # ref_code = element.properties[prop]

                if ref_code in self.elm_dict.keys():
                    # replace the reference by the corresponding object properties
                    obj_idx = self.elm_dict[ref_code]
                    ref_obj = self.elements[obj_idx]
                    # element.properties[prop] = ref_obj

                    # A terminal points at an equipment with the property ConductingEquipment
                    # A terminal points at a bus (topological node) with the property TopologicalNode
                    if prop in ['ConductingEquipment', 'TopologicalNode', 'ConnectivityNode']:
                        ref_obj.terminals.append(element)

                    # the winding points at the transformer with the property PowerTransformer
                    if ref_obj.tpe == 'PowerTransformer':
                        if prop in ['PowerTransformer']:
                            ref_obj.windings.append(element)

                    # The tap changer points at the winding with the property TransformerWinding
                    if ref_obj.tpe in ['TransformerWinding', 'PowerTransformerEnd']:
                        if prop in ['TransformerWinding', 'PowerTransformerEnd']:
                            ref_obj.tap_changers.append(element)

                    # the synchronous generator references 3 types of objects
                    if element.tpe == 'SynchronousMachine':
                        if prop in ['BaseVoltage']:
                            element.base_voltage.append(ref_obj)
                        if prop in ['RegulatingControl']:
                            element.regulating_control.append(ref_obj)
                        if prop in ['GeneratingUnit']:
                            element.generating_unit.append(ref_obj)

                    # a Conform load points at LoadResponseCharacteristic with the property LoadResponse
                    if element.tpe == 'ConformLoad':
                        if prop in ['LoadResponse']:
                            element.load_response_characteristics.append(ref_obj)

                    if element.tpe == 'ACLineSegment':
                        if prop in ['BaseVoltage']:
                            element.base_voltage.append(ref_obj)

                else:
                    pass
                    # print('Not found ', prop, ref)

    def parse_file(self, file_name, classes_=None):
        """
        Parse CIM file and add all the recognised objects
        :param file_name:  file name or path
        :return:
        """
        if classes_ is None:
            classes = self.classes
        else:
            classes = classes_
        recording = False

        # Read text file line by line
        with open(file_name, 'r') as file_pointer:

            for line in file_pointer:

                # determine if the line opens or closes and object
                # and of which type of the ones pre-specified
                start_rec, end_rec, tpe = self.check_type(line, classes)

                if tpe is not "":
                    # a recognisable object was found

                    if start_rec:
                        # start recording object
                        if tpe == 'PowerTransformer':
                            element = PowerTransformer(line, tpe)

                        elif tpe == 'ACLineSegment':
                            element = ACLineSegment(line, tpe)

                        elif tpe == 'TransformerWinding':
                            element = Winding(line, tpe)

                        elif tpe == 'PowerTransformerEnd':
                            element = Winding(line, tpe)

                        elif tpe == 'ConformLoad':
                            element = ConformLoad(line, tpe)

                        elif tpe == 'SynchronousMachine':
                            element = SynchronousMachine(line, tpe)

                        else:
                            element = GeneralContainer(line, tpe)

                        recording = True

                    if end_rec:
                        # stop recording object
                        if recording:

                            if element.id in self.elm_dict.keys():
                                idx = self.elm_dict[element.id]
                                self.elements[idx].merge(element)
                                # print('Merging!')
                            else:
                                self.elm_dict[element.id] = len(self.elements)
                                self.elements.append(element)

                            if tpe not in self.elements_by_type.keys():
                                self.elements_by_type[tpe] = list()

                            self.elements_by_type[tpe].append(element)

                            recording = False

                else:
                    # process line
                    if recording:
                        element.parse_line(line)


if __name__ == '__main__':
    import os

    circuit = CIMCircuit()

    fname = './../../../../Grids_and_profiles/grids/IEEE14_equipment_v14.xml'
    if os.name == 'nt':
        fname.replace('/', '\\')

    circuit.parse_file(fname)

    fname = './../../../../Grids_and_profiles/grids/IEEE14_equipment_v16.xml'
    if os.name == 'nt':
        fname.replace('/', '\\')

    circuit.parse_file(fname)

    circuit.find_references()

    # print objects
    for elm in circuit.elements:
        print('\n')
        elm.print()

    pass
