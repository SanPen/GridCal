from GridCal.Engine.CalculationEngine import MultiCircuit, Bus, ControlledGenerator, Branch, BranchType, Load, Shunt, StaticGenerator


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

    def __init__(self, id, tpe, resources=list()):
        """
        General CIM object container
        :param header: object xml header
        :param tpe: type of the object (class)
        """
        self.properties = dict()

        # store the object type
        self.tpe = tpe

        # pick the object id
        self.id = id

        # list of properties which are considered as resources
        self.resources = resources

        self.terminals = list()

        self.base_voltage = list()

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
            prop = index_find(line, L1[0], L1[1]).strip()

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

    def get_xml(self, level=0):

        """
        Returns an XML representation of the object
        Args:
            level:

        Returns:

        """

        """
        <cim:IEC61970CIMVersion rdf:ID="version">
            <cim:IEC61970CIMVersion.version>IEC61970CIM16v29a</cim:IEC61970CIMVersion.version>
            <cim:IEC61970CIMVersion.date>2015-07-15</cim:IEC61970CIMVersion.date>
        </cim:IEC61970CIMVersion>
        """

        l1 = '  ' * level  # start/end tabbing
        l2 = '  ' * (level + 1)  # middle tabbing

        # header
        xml = l1 + '<cim:' + self.tpe + ' rdf:ID="' + self.id + '">\n'

        # properties
        for prop, value in self.properties.items():
            v = str(value).replace(' ', '_')

            if prop in self.resources:
                xml += l2 + '<cim:' + self.tpe + '.' + prop + ' rdf:resource="#' + v + '" />\n'
            else:
                xml += l2 + '<cim:' + self.tpe + '.' + prop + '>' + v + '</cim:' + self.tpe + '.' + prop + '>\n'

        # closing
        xml += l1 + '</cim:' + self.tpe + '>\n'

        return xml


class ACLineSegment(GeneralContainer):

    def __init__(self, id, tpe):
        GeneralContainer.__init__(self, id, tpe)

        self.base_voltage = list()


class PowerTransformer(GeneralContainer):

    def __init__(self, id, tpe):
        GeneralContainer.__init__(self, id, tpe)

        self.windings = list()


class Winding(GeneralContainer):

    def __init__(self, id, tpe):
        GeneralContainer.__init__(self, id, tpe)

        self.tap_changers = list()


class ConformLoad(GeneralContainer):

    def __init__(self, id, tpe):
        GeneralContainer.__init__(self, id, tpe)

        self.load_response_characteristics = list()


class SynchronousMachine(GeneralContainer):

    def __init__(self, id, tpe):
        GeneralContainer.__init__(self, id, tpe)

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
        self.classes = ["ACLineSegment",
                        "Analog",
                        "BaseVoltage",
                        "Breaker",
                        "BusbarSection",
                        "ConformLoad",
                        "ConformLoadSchedule",
                        "ConnectivityNode",
                        "Control",
                        "DayType",
                        "Disconnector",
                        "Discrete",
                        "EnergyConsumer",
                        "EquivalentInjection",
                        "EquivalentNetwork",
                        "GeneratingUnit",
                        "GeographicalRegion",
                        "IEC61970CIMVersion",
                        "Line",
                        "LoadBreakSwitch",
                        "LoadResponseCharacteristic",
                        "Model",
                        "OperationalLimitSet",
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
                        "SynchronousMachine",
                        "Terminal",
                        "TopologicalNode",
                        "TransformerWinding",
                        "VoltageLevel",
                        "VoltageLimit"
                        ]

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

                    if prop in ['BaseVoltage']:
                        element.base_voltage.append(ref_obj)

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

                    # if element.tpe == 'ACLineSegment':
                    #     if prop in ['BaseVoltage']:
                    #         element.base_voltage.append(ref_obj)

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

        disabled = False

        # Read text file line by line
        with open(file_name, 'r') as file_pointer:

            for line in file_pointer:

                if '<!--' in line:
                    disabled = True

                if not disabled:

                    # determine if the line opens or closes and object
                    # and of which type of the ones pre-specified
                    start_rec, end_rec, tpe = self.check_type(line, classes)

                    if tpe is not "":
                        # a recognisable object was found

                        if start_rec:

                            id = index_find(line, '"', '">').replace('#', '')

                            # start recording object
                            if tpe == 'PowerTransformer':
                                element = PowerTransformer(id, tpe)

                            elif tpe == 'ACLineSegment':
                                element = ACLineSegment(id, tpe)

                            elif tpe == 'TransformerWinding':
                                element = Winding(id, tpe)

                            elif tpe == 'PowerTransformerEnd':
                                element = Winding(id, tpe)

                            elif tpe == 'ConformLoad':
                                element = ConformLoad(id, tpe)

                            elif tpe == 'SynchronousMachine':
                                element = SynchronousMachine(id, tpe)

                            else:
                                element = GeneralContainer(id, tpe)

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
                else:
                    # the line is a comment
                    # print('#', line.replace('\n', ''))

                    if '-->' in line:
                        disabled = False


class CIMExport:

    def __init__(self, circuit: MultiCircuit):

        self.circuit = circuit

        self.logger = list()

    def save(self, file_name):
        """
        Save XML CIM version of a grid
        Args:
            file_name: file path
        """

        # open CIM file for writing
        text_file = open(file_name, "w")

        # header
        text_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        text_file.write('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:cim="http://iec.ch/TC57/2009/CIM-schema-cim14#">\n')

        # Model
        model = GeneralContainer(id=self.circuit.name, tpe='Model')
        model.properties['name'] = self.circuit.name
        model.properties['version'] = 1
        text_file.write(model.get_xml(1))

        bus_id_dict = dict()
        base_voltages = set()
        base_voltages_dict = dict()

        # buses sweep to gather previous data (base voltages, etc..)
        for i, bus in enumerate(self.circuit.buses):
            base_voltages.add(int(bus.Vnom))

        # generate Base voltages
        for V in base_voltages:

            id = 'Base_voltage_' + str(V).replace('.', '_')

            base_voltages_dict[int(V)] = id

            model = GeneralContainer(id=id, tpe='BaseVoltage')
            model.properties['name'] = id
            model.properties['nominalVoltage'] = int(V)
            text_file.write(model.get_xml(1))

        # buses sweep to actually generate XML
        terminal_resources = ['TopologicalNode', 'ConductingEquipment']
        for i, bus in enumerate(self.circuit.buses):

            # make id
            id = 'BUS_' + str(i)

            # make dictionary entry
            bus_id_dict[bus] = id

            base_voltage = base_voltages_dict[int(bus.Vnom)]

            # generate model
            model = GeneralContainer(id=id, tpe='TopologicalNode', resources=['BaseVoltage'])
            model.properties['name'] = bus.name
            model.properties['aliasName'] = bus.name
            model.properties['BaseVoltage'] = base_voltage
            text_file.write(model.get_xml(1))

            for il, elm in enumerate(bus.loads):

                id2 = id + '_LOAD_' + str(il)
                id3 = id2 + '_LRC'

                model = GeneralContainer(id=id2, tpe='ConformLoad', resources=['BaseVoltage', 'LoadResponse'])
                model.properties['name'] = elm.name
                model.properties['aliasName'] = elm.name
                model.properties['BaseVoltage'] = base_voltage
                model.properties['LoadResponse'] = id3
                model.properties['pfixed'] = elm.S.real
                model.properties['qfixed'] = elm.S.imag
                model.properties['normallyInService'] = elm.active
                text_file.write(model.get_xml(1))

                model = GeneralContainer(id=id3, tpe='LoadResponseCharacteristic', resources=[])
                model.properties['name'] = elm.name
                model.properties['exponentModel'] = 'false'
                model.properties['pConstantCurrent'] = elm.I.real
                model.properties['pConstantImpedance'] = elm.Z.real
                model.properties['pConstantPower'] = elm.S.real
                model.properties['pVoltageExponent'] = 0.0
                model.properties['pFrequencyExponent'] = 0.0
                model.properties['qConstantCurrent'] = elm.I.imag
                model.properties['qConstantImpedance'] = elm.Z.imag
                model.properties['qConstantPower'] = elm.S.imag
                model.properties['qVoltageExponent'] = 0.0
                model.properties['qFrequencyExponent'] = 0.0
                text_file.write(model.get_xml(1))

                # Terminal 1 (from)
                model = GeneralContainer(id=id2 + '_T', tpe='Terminal', resources=terminal_resources)
                model.properties['name'] = elm.name
                model.properties['TopologicalNode'] = bus_id_dict[bus]
                model.properties['ConductingEquipment'] = id2
                model.properties['connected'] = 'true'
                model.properties['sequenceNumber'] = '1'
                text_file.write(model.get_xml(1))

            for il, elm in enumerate(bus.static_generators):

                id2 = id + '_StatGen_' + str(il)

                model = GeneralContainer(id=id2, tpe='ConformLoad', resources=['BaseVoltage', 'LoadResponse'])
                model.properties['name'] = elm.name
                model.properties['aliasName'] = elm.name
                model.properties['BaseVoltage'] = base_voltage
                model.properties['pfixed'] = -elm.S.real
                model.properties['qfixed'] = -elm.S.imag
                model.properties['normallyInService'] = elm.active
                text_file.write(model.get_xml(1))

                # Terminal 1 (from)
                model = GeneralContainer(id=id2 + '_T', tpe='Terminal', resources=terminal_resources)
                model.properties['name'] = elm.name
                model.properties['TopologicalNode'] = bus_id_dict[bus]
                model.properties['ConductingEquipment'] = id2
                model.properties['connected'] = 'true'
                model.properties['sequenceNumber'] = '1'
                text_file.write(model.get_xml(1))

            for il, elm in enumerate(bus.controlled_generators):

                id2 = id + '_SyncGen_' + str(il)
                id3 = id2 + '_GU'
                id4 = id2 + '_RC'

                model = GeneralContainer(id=id2, tpe='SynchronousMachine', resources=['BaseVoltage', 'RegulatingControl', 'GeneratingUnit'])
                model.properties['name'] = elm.name
                model.properties['aliasName'] = elm.name
                model.properties['BaseVoltage'] = base_voltage
                model.properties['RegulatingControl'] = id3
                model.properties['GeneratingUnit'] = id4
                model.properties['maxQ'] = elm.Qmax
                model.properties['minQ'] = elm.Qmin
                model.properties['ratedS'] = elm.Snom
                model.properties['normallyInService'] = elm.active
                text_file.write(model.get_xml(1))

                model = GeneralContainer(id=id3, tpe='RegulatingControl', resources=[])
                model.properties['name'] = elm.name
                model.properties['targetValue'] = elm.Vset * bus.Vnom
                text_file.write(model.get_xml(1))

                model = GeneralContainer(id=id4, tpe='GeneratingUnit', resources=[])
                model.properties['name'] = elm.name
                model.properties['initialP'] = elm.P
                text_file.write(model.get_xml(1))

                # Terminal 1 (from)
                model = GeneralContainer(id=id2 + '_T', tpe='Terminal', resources=terminal_resources)
                model.properties['name'] = elm.name
                model.properties['TopologicalNode'] = bus_id_dict[bus]
                model.properties['ConductingEquipment'] = id2
                model.properties['connected'] = 'true'
                model.properties['sequenceNumber'] = '1'
                text_file.write(model.get_xml(1))

            for il, elm in enumerate(bus.shunts):

                id2 = id + '_Shunt_' + str(il)

                model = GeneralContainer(id=id2, tpe='ShuntCompensator', resources=['BaseVoltage'])
                model.properties['name'] = elm.name
                model.properties['aliasName'] = elm.name
                model.properties['BaseVoltage'] = base_voltage
                model.properties['gPerSection'] = elm.Y.real
                model.properties['bPerSection'] = elm.Y.imag
                model.properties['g0PerSection'] = 0.0
                model.properties['b0PerSection'] = 0.0
                model.properties['normallyInService'] = elm.active
                text_file.write(model.get_xml(1))

                # Terminal 1 (from)
                model = GeneralContainer(id=id2 + '_T', tpe='Terminal', resources=terminal_resources)
                model.properties['name'] = elm.name
                model.properties['TopologicalNode'] = bus_id_dict[bus]
                model.properties['ConductingEquipment'] = id2
                model.properties['connected'] = 'true'
                model.properties['sequenceNumber'] = '1'
                text_file.write(model.get_xml(1))

            if bus.is_slack:
                id2 = id + '_EqNetwork'

                model = GeneralContainer(id=id2, tpe='EquivalentNetwork', resources=['BaseVoltage'])
                model.properties['name'] = bus.name + '_Slack'
                model.properties['aliasName'] = bus.name + '_Slack'
                model.properties['BaseVoltage'] = base_voltage
                text_file.write(model.get_xml(1))

                # Terminal 1 (from)
                model = GeneralContainer(id=id2 + '_T', tpe='Terminal', resources=terminal_resources)
                model.properties['name'] = id2 + '_T'
                model.properties['TopologicalNode'] = bus_id_dict[bus]
                model.properties['ConductingEquipment'] = id2
                model.properties['connected'] = 'true'
                model.properties['sequenceNumber'] = '1'
                text_file.write(model.get_xml(1))

        # Branches
        winding_resources = ['connectionType', 'windingType', 'PowerTransformer']
        for i, branch in enumerate(self.circuit.branches):

            if branch.branch_type == BranchType.Transformer:
                id = 'Transformer_' + str(i)

                model = GeneralContainer(id=id, tpe='PowerTransformer', resources=[])
                model.properties['name'] = branch.name
                model.properties['aliasName'] = branch.name
                text_file.write(model.get_xml(1))

                #  warnings
                if branch.rate <= 0.0:
                    self.logger.append(branch.name + ": The rate is 0, this will cause a problem when loading.")
                    raise Exception(branch.name + ": The rate is 0, this will cause a problem when loading.")

                if branch.bus_from.Vnom <= 0.0:
                    self.logger.append(branch.name + ": The voltage at the from side is 0, this will cause a problem when loading.")
                    raise Exception(branch.name + ": The voltage at the from side, this will cause a problem when loading.")

                if branch.bus_to.Vnom <= 0.0:
                    self.logger.append(branch.name + ": The voltage at the to side, this will cause a problem when loading.")
                    raise Exception(branch.name + ": The voltage at the to side, this will cause a problem when loading.")

                # W1 (from)
                winding_power_rate = branch.rate / 2
                Zbase = (branch.bus_from.Vnom ** 2) / winding_power_rate
                Ybase = 1 / Zbase
                model = GeneralContainer(id=id + "_W1", tpe='PowerTransformerEnd', resources=winding_resources)
                model.properties['name'] = branch.name
                model.properties['PowerTransformer'] = id
                model.properties['BaseVoltage'] = base_voltages_dict[int(branch.bus_from.Vnom)]
                model.properties['r'] = branch.R / 2 * Zbase
                model.properties['x'] = branch.X / 2 * Zbase
                model.properties['g'] = branch.G / 2 * Ybase
                model.properties['b'] = branch.B / 2 * Ybase
                model.properties['r0'] = 0.0
                model.properties['x0'] = 0.0
                model.properties['g0'] = 0.0
                model.properties['b0'] = 0.0
                model.properties['ratedS'] = winding_power_rate
                model.properties['ratedU'] = branch.bus_from.Vnom
                model.properties['rground'] = 0.0
                model.properties['xground'] = 0.0
                model.properties['connectionType'] = "http://iec.ch/TC57/2009/CIM-schema-cim14#WindingConnection.Y"
                model.properties['windingType'] = "http://iec.ch/TC57/2009/CIM-schema-cim14#WindingType.primary"
                text_file.write(model.get_xml(1))

                # W2 (To)
                Zbase = (branch.bus_to.Vnom ** 2) / winding_power_rate
                Ybase = 1 / Zbase
                model = GeneralContainer(id=id + "_W2", tpe='PowerTransformerEnd', resources=winding_resources)
                model.properties['name'] = branch.name
                model.properties['PowerTransformer'] = id
                model.properties['BaseVoltage'] = base_voltages_dict[int(branch.bus_to.Vnom)]
                model.properties['r'] = branch.R / 2 * Zbase
                model.properties['x'] = branch.X / 2 * Zbase
                model.properties['g'] = branch.G / 2 * Ybase
                model.properties['b'] = branch.B / 2 * Ybase
                model.properties['r0'] = 0.0
                model.properties['x0'] = 0.0
                model.properties['g0'] = 0.0
                model.properties['b0'] = 0.0
                model.properties['ratedS'] = winding_power_rate
                model.properties['ratedU'] = branch.bus_to.Vnom
                model.properties['rground'] = 0.0
                model.properties['xground'] = 0.0
                model.properties['connectionType'] = "http://iec.ch/TC57/2009/CIM-schema-cim14#WindingConnection.Y"
                model.properties['windingType'] = "http://iec.ch/TC57/2009/CIM-schema-cim14#WindingType.secondary"
                text_file.write(model.get_xml(1))

            elif branch.branch_type == BranchType.Line or branch.branch_type == BranchType.Branch:

                id = 'Branch_' + str(i)
                Zbase = (branch.bus_from.Vnom ** 2) / self.circuit.Sbase
                Ybase = 1 / Zbase
                model = GeneralContainer(id=id, tpe='ACLineSegment', resources=['BaseVoltage'])
                model.properties['name'] = branch.name
                model.properties['aliasName'] = branch.name
                model.properties['BaseVoltage'] = base_voltages_dict[int(branch.bus_from.Vnom)]
                model.properties['r'] = branch.R * Zbase
                model.properties['x'] = branch.X * Zbase
                model.properties['gch'] = branch.G * Ybase
                model.properties['bch'] = branch.B * Ybase
                model.properties['r0'] = 0.0
                model.properties['x0'] = 0.0
                model.properties['g0ch'] = 0.0
                model.properties['b0ch'] = 0.0
                model.properties['length'] = 1.0
                text_file.write(model.get_xml(1))

            elif branch.branch_type == BranchType.Switch:

                id = 'Switch_' + str(i)
                model = GeneralContainer(id=id, tpe='Switch', resources=['BaseVoltage'])
                model.properties['name'] = branch.name
                model.properties['aliasName'] = branch.name
                model.properties['BaseVoltage'] = base_voltages_dict[int(branch.bus_from.Vnom)]
                model.properties['normalOpen'] = False
                model.properties['open'] = not branch.active
                text_file.write(model.get_xml(1))

            elif branch.branch_type == BranchType.Reactance:

                self.logger.append('Reactance CIM export not implemented yet, exported as a branch')

                id = 'Reactance_' + str(i)
                Zbase = (branch.bus_from.Vnom ** 2) / self.circuit.Sbase
                Ybase = 1 / Zbase
                model = GeneralContainer(id=id, tpe='ACLineSegment', resources=['BaseVoltage'])
                model.properties['name'] = branch.name
                model.properties['aliasName'] = branch.name
                model.properties['BaseVoltage'] = base_voltages_dict[int(branch.bus_from.Vnom)]
                model.properties['r'] = branch.R * Zbase
                model.properties['x'] = branch.X * Zbase
                model.properties['gch'] = branch.G * Ybase
                model.properties['bch'] = branch.B * Ybase
                model.properties['r0'] = 0.0
                model.properties['x0'] = 0.0
                model.properties['g0ch'] = 0.0
                model.properties['b0ch'] = 0.0
                model.properties['length'] = 1.0
                text_file.write(model.get_xml(1))


            # Terminal 1 (from)
            model = GeneralContainer(id=id + '_T1', tpe='Terminal', resources=terminal_resources)
            model.properties['name'] = bus.name + '_' + branch.name + '_T1'
            model.properties['TopologicalNode'] = bus_id_dict[branch.bus_from]
            model.properties['ConductingEquipment'] = id
            model.properties['connected'] = 'true'
            model.properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

            # Terminal 2 (to)
            model = GeneralContainer(id=id + '_T2', tpe='Terminal', resources=terminal_resources)
            model.properties['name'] = bus.name + '_' + branch.name + '_T2'
            model.properties['TopologicalNode'] = bus_id_dict[branch.bus_to]
            model.properties['ConductingEquipment'] = id
            model.properties['connected'] = 'true'
            model.properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        # end
        text_file.write("</rdf:RDF>")

        text_file.close()


class CIMImport:

    def __init__(self):

        self.logger = list()

        # relations between connectivity nodes and terminals
        # node_terminal[some_node] = list of terminals
        self.node_terminal = dict()
        self.terminal_node = dict()

        self.needs_compiling = True

        self.topology = None

    def add_node_terminal_relation(self, connectivity_node, terminal):
        """
        Add the relation between a Connectivity Node and a Terminal
        :param terminal:
        :param connectivity_node:
        :return:
        """
        if connectivity_node in self.node_terminal.keys():
            self.node_terminal[connectivity_node].append(terminal)
        else:
            self.node_terminal[connectivity_node] = [terminal]

        if terminal in self.terminal_node.keys():
            self.terminal_node[terminal].append(connectivity_node)
        else:
            self.terminal_node[terminal] = [connectivity_node]

    def try_properties(self, dictionary, properties):
        """

        :param dictionary:
        :param properties:
        :return:
        """
        res = [None] * len(properties)

        for i in range(len(properties)):

            prop = properties[i]

            try:
                val = dictionary[prop]

                try:
                    val = float(val)
                except:
                    pass  # val is a string
            except:
                # property not found
                print(prop, 'not found')
                val = ""

            res[i] = val

        return res

    def get_elements(self, dict, keys):

        elm = list()

        for k in keys:
            try:
                lst = dict[k]
                elm += lst
            except:
                pass

        return elm

    def any_in_dict(self, dict, keys):

        found = False

        for k in keys:
            try:
                lst = dict[k]
                found = True
            except:
                pass

        return found

    def load_cim_file(self, equipment_file, topology_file=None):
        """
        Load CIM file
        :param equipment_file: Main CIM file
        :param topology_file: Secondary CIM file that may contain the terminals-connectivity node relations
        """
        # declare GridCal circuit
        circuit = MultiCircuit()
        EPS = 1e-16

        # declare CIM circuit to process the file(s)
        cim = CIMCircuit()

        # parse main file
        cim.parse_file(equipment_file)

        # if additionally there is a topology file, parse it as well
        if topology_file is not None:
            cim.parse_file(topology_file)

        # replace CIM references in the CIM objects
        cim.find_references()

        # Terminals
        T_dict = dict()
        if 'Terminal' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['Terminal']:
                if 'name' in elm.properties:
                    name = elm.properties['name']
                else:
                    name = elm.id

                # T = Bus(name=name)
                T_dict[elm.id] = elm
                # circuit.add_bus(T)

        else:
            self.logger.append('There are no Terminals!!!!!')

        # ConnectivityNodes
        CN_dict = dict()
        cim_nodes = ['TopologicalNode', 'ConnectivityNode']
        if self.any_in_dict(cim.elements_by_type, cim_nodes):
            for elm in self.get_elements(cim.elements_by_type, cim_nodes):
                name = elm.properties['name']

                Vnom = float(elm.base_voltage[0].properties['nominalVoltage'])

                CN = Bus(name=name, vnom=Vnom)
                CN_dict[elm.id] = CN
                circuit.add_bus(CN)
        else:
            self.logger.append('There are no TopologicalNodes nor ConnectivityNodes!!!!!')

        # CN_T: build the connectivity nodes - terminals relations structure
        if self.any_in_dict(cim.elements_by_type, cim_nodes):
            for elm in self.get_elements(cim.elements_by_type, cim_nodes):

                # get the connectivity node
                CN = CN_dict[elm.id]

                # get the terminals associated to the connectivity node and register the associations
                for term in elm.terminals:
                    T = T_dict[term.id]
                    self.add_node_terminal_relation(CN, T)
        else:
            self.logger.append('No topological nodes: The grid MUST have topological Nodes')

        # BusBarSections
        if 'BusbarSection' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['BusbarSection']:
                T1 = T_dict[elm.terminals[0].id]  # get the terminal of the bus bar section
                CN = self.terminal_node[T1][0]  # get the connectivity node of the terminal
                CN.is_bus = True  # the connectivity node has a BusbarSection attached, hence it is a real bus
        else:
            self.logger.append("No BusbarSections: There is no chance to reduce the grid")

        # Lines
        prop_lst = ['r', 'x', 'r0', 'x0', 'gch', 'bch', 'g0ch', 'b0ch', 'length']
        if 'ACLineSegment' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['ACLineSegment']:
                T1 = T_dict[elm.terminals[0].id]
                T2 = T_dict[elm.terminals[1].id]

                B1 = self.terminal_node[T1][0]
                B2 = self.terminal_node[T2][0]

                name = elm.properties['name']
                r, x, r0, x0, g, b, g0, b0, l = self.try_properties(elm.properties, prop_lst)

                Vnom = float(elm.base_voltage[0].properties['nominalVoltage'])
                Sbase = circuit.Sbase

                Zbase = (Vnom * Vnom) / Sbase
                Ybase = 1.0 / Zbase

                R = r * l / Zbase
                X = x * l / Zbase
                G = g * l / Ybase
                B = b * l / Ybase

                line = Branch(bus_from=B1,
                              bus_to=B2,
                              name=name,
                              r=R,
                              x=X,
                              g=G,
                              b=B,
                              rate=0,
                              tap=1,
                              shift_angle=0,
                              active=True,
                              mttf=0,
                              mttr=0,
                              branch_type=BranchType.Line)

                circuit.add_branch(line)

        # PowerTransformer
        if 'PowerTransformer' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['PowerTransformer']:

                assert(len(elm.windings) == 2)

                if len(elm.windings[0].terminals) > 0:
                    T1 = T_dict[elm.windings[0].terminals[0].id]
                    T2 = T_dict[elm.windings[1].terminals[0].id]
                elif len(elm.terminals) == 2:
                    T1 = T_dict[elm.terminals[0].id]
                    T2 = T_dict[elm.terminals[1].id]
                else:
                    raise Exception('Check element' + elm.id)

                B1 = self.terminal_node[T1][0]
                B2 = self.terminal_node[T2][0]

                # reset the values for the new object
                R = 0
                X = 0
                G = 0
                B = 0
                R0 = 0
                X0 = 0
                G0 = 0
                B0 = 0
                taps = [None] * 2
                RATE = 0
                # convert every winding to per unit and add it into a PI model
                for i in range(2):
                    r = float(elm.windings[i].properties['r'])
                    x = float(elm.windings[i].properties['x'])

                    try:
                        g = float(elm.windings[i].properties['g'])
                        b = float(elm.windings[i].properties['b'])
                    except Exception as e:
                        g = 0
                        b = 0
                        self.logger.append('No shunt components in ' + elm.windings[i].id)

                    try:
                        r0 = float(elm.windings[i].properties['r0'])
                        x0 = float(elm.windings[i].properties['x0'])
                        g0 = float(elm.windings[i].properties['g0'])
                        b0 = float(elm.windings[i].properties['b0'])
                    except Exception as e:
                        r0 = 0
                        x0 = 0
                        g0 = 0
                        b0 = 0
                        self.logger.append('No zero sequence components in ' + elm.id)

                    S = float(elm.windings[i].properties['ratedS'])
                    RATE += S

                    try:
                        V = float(elm.windings[i].properties['ratedU'])
                    except Exception as e:
                        self.logger.append('No ratedU in ' + elm.windings[i].id + ' this is mandatory')
                        try:
                            V = float(elm.windings[i].base_voltage[0].properties['nominalVoltage'])
                        except Exception as e2:
                            self.logger.append('No voltage in ' + elm.windings[i].id + 'whatsoever, this causes an error')

                    if len(elm.windings[i].tap_changers) > 0:
                        Vnom = float(elm.windings[i].tap_changers[0].properties['neutralU'])
                        tap_dir = float(elm.windings[i].tap_changers[0].properties['normalStep'])
                        Vinc = float(elm.windings[i].tap_changers[0].properties['stepVoltageIncrement'])
                        taps[i] = (Vnom + tap_dir * Vnom * (Vinc / 100.0)) / Vnom
                    else:
                        taps[i] = 1.0

                    Zbase = (V * V) / S
                    Ybase = 1.0 / Zbase

                    R += r / Zbase
                    R0 += r0 / Zbase
                    X += x / Zbase
                    X0 += x0 / Zbase

                    G += g / Ybase
                    G0 += g0 / Ybase
                    B += b / Ybase
                    B0 += b0 / Ybase

                name = elm.properties['name']

                tap_m = taps[0] * taps[1]

                line = Branch(bus_from=B1,
                              bus_to=B2,
                              name=name,
                              r=R,
                              x=X,
                              g=G,
                              b=B,
                              rate=RATE,
                              tap=tap_m,
                              shift_angle=0,
                              active=True,
                              mttf=0,
                              mttr=0,
                              branch_type=BranchType.Transformer)

                circuit.add_branch(line)

        # Switches
        cim_switches = ['Switch', 'Disconnector', 'Breaker', 'LoadBreakSwitch']
        if self.any_in_dict(cim.elements_by_type, cim_switches):
            for elm in self.get_elements(cim.elements_by_type, cim_switches):
                T1 = T_dict[elm.terminals[0].id]
                T2 = T_dict[elm.terminals[1].id]
                B1 = self.terminal_node[T1][0]
                B2 = self.terminal_node[T2][0]

                if 'name' in elm.properties:
                    name = elm.properties['name']
                else:
                    name = 'Some switch'

                if 'open' in elm.properties:
                    state = not bool(elm.properties['open'])
                else:
                    state = True

                line = Branch(bus_from=B1,
                              bus_to=B2,
                              name=name,
                              r=EPS,
                              x=EPS,
                              g=EPS,
                              b=EPS,
                              rate=EPS,
                              tap=0,
                              shift_angle=0,
                              active=state,
                              mttf=0,
                              mttr=0,
                              branch_type=BranchType.Transformer)

                circuit.add_branch(line)

        # Loads
        cim_loads = ['ConformLoad', 'EnergyConsumer']
        if self.any_in_dict(cim.elements_by_type, cim_loads):
            for elm in self.get_elements(cim.elements_by_type, cim_loads):
                T1 = T_dict[elm.terminals[0].id]
                B1 = self.terminal_node[T1][0]

                # Active and reactive power values

                if elm.tpe == 'ConformLoad':
                    if len(elm.load_response_characteristics) > 0:
                        p = float(elm.load_response_characteristics[0].properties['pConstantPower'])
                        q = float(elm.load_response_characteristics[0].properties['qConstantPower'])
                        name = elm.load_response_characteristics[0].properties['name']
                    else:
                        p, q = self.try_properties(elm.properties, ['pfixed', 'qfixed'])
                        name = elm.properties['name']

                else:
                    p = self.try_properties(elm.properties, ['pfixed'])[0]
                    q = 0
                    name = 'Some load'

                load = Load(name=name,
                            impedance=complex(0, 0),
                            current=complex(0, 0),
                            power=complex(p, q))
                circuit.add_load(B1, load)

        # shunts
        if 'ShuntCompensator' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['ShuntCompensator']:
                T1 = T_dict[elm.terminals[0].id]
                B1 = self.terminal_node[T1][0]

                g = float(elm.properties['gPerSection'])
                b = float(elm.properties['bPerSection'])
                g0 = float(elm.properties['g0PerSection'])
                b0 = float(elm.properties['b0PerSection'])
                name = elm.properties['name']

                # self.add_shunt(Shunt(name, T1, g, b, g0, b0))

                sh = Shunt(name=name, admittance=complex(g, b))
                circuit.add_shunt(B1, sh)

        # Generators
        if 'SynchronousMachine' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['SynchronousMachine']:
                T1 = T_dict[elm.terminals[0].id]
                B1 = self.terminal_node[T1][0]

                # nominal voltage and set voltage
                if len(elm.base_voltage) > 0:
                    Vnom = float(elm.base_voltage[0].properties['nominalVoltage'])
                else:
                    Vnom = float(elm.properties['ratedU'])

                if len(elm.regulating_control) > 0:
                    Vset = float(elm.regulating_control[0].properties['targetValue'])
                else:
                    Vset = Vnom

                # p.u. set voltage for the model
                vset = Vset / Vnom

                # active power
                if len(elm.generating_unit) > 0:
                    if 'initialP' in elm.generating_unit[0].properties.keys():
                        p = float(elm.generating_unit[0].properties['initialP'])
                    else:
                        self.logger.append('No active power initialP value for ' + elm.id)
                        p = 0.0
                else:
                    if 'p' in elm.properties.keys():
                        p = float(elm.properties('p'))
                    else:
                        p = 0.0
                        self.logger.append('No active power p value for ' + elm.id)

                name = elm.properties['name']
                # self.add_generator(Generator(name, T1, p, vset))

                gen = ControlledGenerator(name=name,
                                          active_power=p,
                                          voltage_module=vset)
                circuit.add_controlled_generator(B1, gen)

        return circuit


if __name__ == '__main__':

    grid = MultiCircuit()
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_300BUS.xls'
    # fname = 'Pegasus 89 Bus.xlsx'
    # fname = 'Illinois200Bus.xlsx'
    # fname = 'IEEE_30_new.xlsx'
    # fname = 'lynn5buspq.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE_30_new.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/UnderDevelopment/GridCal/IEEE30_new.xlsx'
    # fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\IEEE 30 Bus with storage.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE_14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.xlsx'
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_14.xls'
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_39Bus(Islands).xls'
    fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\IEEE_30_new.xlsx'

    print('Reading...')
    grid.load_file(fname)

    # grid.save_cim('/home/santi/Documentos/GitHub/GridCal/UnderDevelopment/GridCal/IEEE_14_GridCal.xml')
    grid.save_cim('C:\\Users\\spenate\\Documents\\PROYECTOS\\SCADA_microgrid\\CIM\\newton\\IEEE_30_Bus.xml')