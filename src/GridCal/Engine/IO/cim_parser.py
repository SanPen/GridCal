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
import os
import chardet
import pandas as pd
from math import sqrt
from typing import Set, Dict, List, Tuple
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.IO.zip_interface import get_xml_from_zip, get_xml_content
from GridCal.Engine.Core.multi_circuit import MultiCircuit
import GridCal.Engine.Devices as gcdev


def index_find(string, start, end):
    """
    version of substring that matches
    :param string: string
    :param start: string to start splitting
    :param end: string to end splitting
    :return: string between start and end
    """
    return string.partition(start)[2].partition(end)[0]


def rfid2uuid(val):
    return val.replace('-', '').replace('_', '')


def read_cim_files(cim_files):
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


def get_elements(dict: Dict, keys):

    elm = list()

    for k in keys:
        try:
            lst = dict[k]
            elm += lst
        except KeyError:
            pass

    return elm


def any_in_dict(dict: Dict, keys):

    found = False

    for k in keys:
        try:
            lst = dict[k]
            found = True
        except KeyError:
            pass

    return found


def str2num(val: str):
    """
    Try to convert to number, else keep as string
    :param val: String value
    :return: int, float or string
    """
    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return val


class GeneralContainer:

    def __init__(self, rfid, tpe):
        """
        General CIM object container
        :param rfid: RFID
        :param tpe: type of the object (class)
        """

        # dictionary of properties read from the xml
        self.properties = dict()

        # dictionary of objects that reference this object
        self.references_to_me = dict()

        # store the object type
        self.tpe = tpe

        # pick the object id
        self.rfid = rfid
        self.uuid = rfid2uuid(rfid)

        self.name = ''

    def __repr__(self):
        return self.rfid

    def __hash__(self):
        # alternatively, return hash(repr(self))
        return int(self.uuid, 16)  # hex string to int

    def __lt__(self, other):
        return self.__hash__() < other.__hash__()

    def __eq__(self, other):
        return self.rfid == other.rfid

    def add_reference(self, obj: "GeneralContainer"):
        """
        Adds a categorized reference to this object
        :param obj:
        :return:
        """
        if obj.tpe in self.references_to_me.keys():
            self.references_to_me[obj.tpe].add(obj)
        else:
            self.references_to_me[obj.tpe] = {obj}

    def parse_line(self, xml_line):
        """
        Parse xml line that eligibly belongs to this object
        :param xml_line: xml text line
        """

        # the parsers are lists of 2 sets of separators
        # the first separator tries to substring the property name
        # the second tries to substring the property value
        parsers = [[('.', '>'), ('>', '<')],
                   [('.', ' rdf:resource'), ('rdf:resource="', '"')]]

        for L1, L2 in parsers:
            # try to parse the property
            prop = index_find(xml_line, L1[0], L1[1]).strip()

            # try to parse the value
            val = index_find(xml_line, L2[0], L2[1])

            # remove the pound
            if len(val) > 0:
                if val[0] == '#':
                    val = val[1:]

            val = val.replace('\n', '')

            if prop != "" and val != "":
                self.properties[prop] = val

                if hasattr(self, prop):
                    setattr(self, prop, str2num(val))

    def merge(self, other):
        """
        Merge the properties of this object with another
        :param other: GeneralContainer instance
        """
        self.properties = {**self.properties, **other.properties}

    def print(self):
        print('Type:' + self.tpe)
        print('Id:' + self.rfid)

        for key in self.properties.keys():
            val = self.properties[key]

            if type(val) == GeneralContainer:
                for key2 in val.properties.keys():
                    val2 = val.properties[key2]
                    print(key, '->', key2, ':', val2)
            else:
                print(key, ':', val)

    def __str__(self):
        return self.tpe + ':' + self.rfid

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
        xml = l1 + '<cim:' + self.tpe + ' rdf:ID="' + self.rfid + '">\n'

        # properties
        for prop, value in self.properties.items():
            v = str(value).replace(' ', '_')

            # eventually replace the class of the property, because CIM is so well designed...
            if prop in self.class_replacements.keys():
                cls = self.class_replacements[prop]
            else:
                cls = self.tpe

            if prop in self.resources:
                xml += l2 + '<cim:' + cls + '.' + prop + ' rdf:resource="#' + v + '" />\n'
            else:
                xml += l2 + '<cim:' + cls + '.' + prop + '>' + v + '</cim:' + cls + '.' + prop + '>\n'

        # closing
        xml += l1 + '</cim:' + self.tpe + '>\n'

        return xml

    def get_dict(self):
        """
        Get dictionary with the data
        :return: Dictionary
        """
        return {'rfid': self.rfid,
                'uuid': self.uuid,
                'name': self.name}


class MonoPole(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

    def get_topological_node(self):
        """
        Get the TopologyNodes of this branch
        :return: two TopologyNodes or nothing
        """
        try:
            terminals = list(self.references_to_me['Terminal'])

            if len(terminals) == 1:
                n1 = terminals[0].TopologicalNode
                return n1
            else:
                return None

        except KeyError:
            return None

    def get_bus(self):
        """
        Get the associated bus
        :return:
        """
        tp = self.get_topological_node()
        if tp is None:
            return None
        else:
            return tp.get_bus()

    def get_dict(self):
        """
        Get dictionary with the data
        :return: Dictionary
        """
        tp = self.get_topological_node()
        bus = tp.get_bus() if tp is not None else None

        d = super().get_dict()
        d['TopologicalNode'] = '' if tp is None else tp.uuid
        d['BusbarSection'] = '' if bus is None else bus.uuid
        return d


class DiPole(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

    def get_topological_nodes(self) -> Tuple["TopologicalNode", "TopologicalNode"]:
        """
        Get the TopologyNodes of this branch
        :return: (TopologyNodes, TopologyNodes) or (None, None)
        """
        try:
            terminals = list(self.references_to_me['Terminal'])

            if len(terminals) == 2:
                n1 = terminals[0].TopologicalNode
                n2 = terminals[1].TopologicalNode
                return n1, n2
            else:
                return None, None

        except KeyError:
            return None, None

    def get_buses(self) -> Tuple["BusbarSection", "BusbarSection"]:
        """
        Get the associated bus
        :return: (BusbarSection, BusbarSection) or (None, None)
        """
        t1, t2 = self.get_topological_nodes()
        b1 = t1.get_bus() if t1 is not None else None
        b2 = t2.get_bus() if t2 is not None else None
        return b1, b2

    def get_dict(self):
        """
        Get dictionary with the data
        :return: Dictionary
        """
        t1, t2 = self.get_topological_nodes()
        b1 = t1.get_bus() if t1 is not None else None
        b2 = t2.get_bus() if t2 is not None else None

        d = super().get_dict()
        d['TopologicalNode1'] = '' if t1 is None else t1.uuid
        d['TopologicalNode2'] = '' if t2 is None else t2.uuid
        d['BusbarSection1'] = '' if b1 is None else b1.uuid
        d['BusbarSection2'] = '' if b2 is None else b2.uuid
        return d


class BaseVoltage(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.nominalVoltage = 0


class Terminal(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.TopologicalNode = None
        self.ConductingEquipment = None  # pointer to the Bus
        self.name = ''
        self.connected = True

    def get_voltage(self):
        """
        Get the voltage of this terminal
        :return: Voltage or None
        """
        if self.TopologicalNode is not None:
            return self.TopologicalNode.get_voltage()
        else:
            return None


class ConnectivityNode(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.TopologicalNode = None
        self.ConnectivityNodeContainer = None
        self.name = ''
        self.shortName = ''
        self.description = ''
        self.fromEndName = ''
        self.fromEndNameTSO = ''
        self.fromEndIsoCode = ''
        self.toEndName = ''
        self.toEndNameTSO = ''
        self.toEndIsoCode = ''
        self.boundaryPoint = ''


class TopologicalNode(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.BaseVoltage = None
        self.ConnectivityNodeContainer = None

    def get_voltage(self):

        if self.BaseVoltage is not None:
            return self.BaseVoltage.nominalVoltage
        else:
            return None

    def get_bus(self):
        """
        Get an associated BusBar, if any
        :return: BusbarSection or None is not fond
        """
        try:
            terms = self.references_to_me['Terminal']
            for term in terms:
                if isinstance(term.ConductingEquipment, BusbarSection):
                    return term.ConductingEquipment

        except KeyError:
            return None

    def get_dict(self):

        d = super().get_dict()

        v = self.get_voltage()
        d['Vnom'] = v if v is not None else ''

        return d


class BusbarSection(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.EquipmentContainer = None

    def get_topological_nodes(self):
        """
        Get the associated TopologicalNode instances
        :return: list of TopologicalNode instances
        """
        try:
            terms = self.references_to_me['Terminal']
            return [term.TopologicalNode for term in terms]
        except KeyError:
            return list()

    def get_topological_node(self):
        """
        Get the first TopologicalNode found
        :return: first TopologicalNode found
        """
        try:
            terms = self.references_to_me['Terminal']
            for term in terms:
                return term.TopologicalNode
        except KeyError:
            return list()

    def get_dict(self):

        d = super().get_dict()

        voltage_level = self.EquipmentContainer

        if voltage_level is not None:
            d['Vnom'] = voltage_level.BaseVoltage.nominalVoltage
            d['VoltageLevel'] = voltage_level.uuid
            substation = voltage_level.Substation

            if substation is not None:
                d['Substation'] = substation.uuid
                province = substation.Region

                if province is not None:
                    d['SubGeographicalRegion'] = province.uuid
                    country = province.Region

                    if country is not None:
                        d['GeographicalRegion'] = country.uuid
                    else:
                        d['GeographicalRegion'] = ''

                else:
                    d['SubGeographicalRegion'] = ''
                    d['GeographicalRegion'] = ''

            else:
                d['Substation'] = ''
                d['SubGeographicalRegion'] = ''
                d['GeographicalRegion'] = ''

        else:
            d['VoltageLevel'] = ''
            d['Substation'] = ''
            d['SubGeographicalRegion'] = ''
            d['GeographicalRegion'] = ''

        return d


class Substation(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''
        self.Region = None


class OperationalLimitSet(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''
        self.Terminal = None


class OperationalLimitType(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''
        self.limitType = ''
        self.direction = ''


class GeographicalRegion(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)


class SubGeographicalRegion(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.Region = None


class VoltageLevel(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.Substation = None
        self.BaseVoltage = None
        self.highVoltageLimit = 0
        self.lowVoltageLimit = 0


class VoltageLimit(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.OperationalLimitType = None
        self.OperationalLimitSet = None
        self.value = 0


class CurrentLimit(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.OperationalLimitType = None
        self.OperationalLimitSet = None
        self.value = 0


class EquivalentNetwork(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)


class EquivalentInjection(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.regulationCapability = False
        self.BaseVoltage = None
        self.EquipmentContainer = None
        self.name = ''
        self.p = 0
        self.q = 0


class Breaker(DiPole):

    def __init__(self, rfid, tpe):
        DiPole.__init__(self, rfid, tpe)

        self.normalOpen = True
        self.retained = True
        self.EquipmentContainer = None
        self.open = False

    def get_nodes(self):
        """
        Get the TopologyNodes of this branch
        :return: two TopologyNodes or nothing
        """
        try:
            terminals = list(self.references_to_me['Terminal'])

            if len(terminals) == 2:
                n1 = terminals[0].TopologicalNode
                n2 = terminals[1].TopologicalNode
                return n1, n2
            else:
                return None, None

        except KeyError:
            return None, None


class Switch(DiPole):

    def __init__(self, rfid, tpe):
        DiPole.__init__(self, rfid, tpe)

        self.normalOpen = True
        self.retained = True
        self.EquipmentContainer = None
        self.open = False
        self.description = ''
        self.aggregate = False
        self.name = ''

    def get_nodes(self):
        """
        Get the TopologyNodes of this branch
        :return: two TopologyNodes or nothing
        """
        try:
            terminals = list(self.references_to_me['Terminal'])

            if len(terminals) == 2:
                n1 = terminals[0].TopologicalNode
                n2 = terminals[1].TopologicalNode
                return n1, n2
            else:
                return None, None

        except KeyError:
            return None, None


class Line(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)


class ACLineSegment(DiPole):

    def __init__(self, rfid, tpe):
        DiPole.__init__(self, rfid, tpe)

        self.BaseVoltage = None
        self.current_limit = None
        self.bch = 0
        self.gch = 0
        self.r = 0
        self.x = 0

    def get_voltage(self):

        if self.BaseVoltage is not None:
            return self.BaseVoltage.nominalVoltage
        else:
            if 'Terminal' in self.references_to_me.keys():
                tps = list(self.references_to_me['Terminal'])

                if len(tps) > 0:
                    tp = tps[0]

                    return tp.get_voltage()
                else:
                    return None
            else:
                return None

    def get_pu_values(self, Sbase=100):
        """
        Get the per-unit values of the equivalent PI model
        :param Sbase: Sbase in MVA
        :return: R, X, Gch, Bch
        """
        if self.BaseVoltage is not None:
            Vnom = self.get_voltage()

            if Vnom is not None:

                Zbase = (Vnom * Vnom) / Sbase
                Ybase = 1.0 / Zbase

                # at this point r, x, g, b are the complete values for all the line length
                R = self.r / Zbase
                X = self.x / Zbase
                G = self.gch / Ybase
                B = self.bch / Ybase
            else:
                R = 0
                X = 0
                G = 0
                B = 0
        else:
            R = 0
            X = 0
            G = 0
            B = 0

        return R, X, G, B

    def get_dict(self):
        d = super().get_dict()
        R, X, G, B = self.get_pu_values(Sbase=100)
        v = self.get_voltage()
        d['r'] = self.r
        d['x'] = self.x
        d['g'] = self.gch
        d['b'] = self.bch
        d['r_pu'] = R
        d['x_pu'] = X
        d['g_pu'] = G
        d['b_pu'] = B
        d['Vnom'] = v if v is not None else ''
        return d


class PowerTransformerEnd(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.BaseVoltage = None
        self.b = 0
        self.g = 0
        self.r = 0
        self.x = 0
        self.ratedS = 0
        self.ratedU = 0
        self.PowerTransformer = None
        self.endNumber = 0
        self.connectionKind = ""
        self.Terminal = None

    def get_voltage(self):

        if self.ratedU > 0:
            return self.ratedU
        else:
            if self.BaseVoltage is not None:
                return self.BaseVoltage.nominalVoltage
            else:
                return None

    def get_pu_values(self, Sbase_system=100):
        """
        Get the per-unit values of the equivalent PI model
        :return: R, X, Gch, Bch
        """
        if self.ratedS > 0 and self.ratedU > 0:
            Zbase = (self.ratedU * self.ratedU) / self.ratedS
            Ybase = 1.0 / Zbase
            machine_to_sys = Sbase_system / self.ratedS
            # at this point r, x, g, b are the complete values for all the line length
            R = self.r / Zbase * machine_to_sys
            X = self.x / Zbase * machine_to_sys
            G = self.g / Ybase * machine_to_sys
            B = self.b / Ybase * machine_to_sys
        else:
            R = 0
            X = 0
            G = 0
            B = 0

        return R, X, G, B

    def get_dict(self):
        d = super().get_dict()
        R, X, G, B = self.get_pu_values()

        d['ratedS'] = self.ratedS
        d['ratedU'] = self.ratedU
        d['endNumber'] = self.endNumber
        d['r'] = self.r
        d['x'] = self.x
        d['g'] = self.g
        d['b'] = self.b
        d['r_pu'] = R
        d['x_pu'] = X
        d['g_pu'] = G
        d['b_pu'] = B
        return d


class PowerTransformer(DiPole):

    def __init__(self, rfid, tpe):
        DiPole.__init__(self, rfid, tpe)

        self.EquipmentContainer = None

    def get_windings_number(self):
        """
        Get the number of windings
        :return: # number of associated windings
        """
        try:
            return len(self.references_to_me['PowerTransformerEnd'])
        except KeyError:
            return 0

    def get_windings(self):
        """
        Get list of windings
        :return: list of winding objects
        """
        try:
            return list(self.references_to_me['PowerTransformerEnd'])
        except KeyError:
            return list()

    def get_pu_values(self):
        """
        Get the transformer p.u. values
        :return:
        """
        try:
            windings = self.references_to_me['PowerTransformerEnd']

            if len(windings) == 2:
                R, X, G, B = 0, 0, 0, 0
                for winding in windings:
                    r, x, g, b = winding.get_pu_values()
                    R += r
                    X += x
                    G += g
                    B += b
            else:
                R, X, G, B = 0, 0, 0, 0

        except KeyError:
            R, X, G, B = 0, 0, 0, 0

        return R, X, G, B

    def get_voltages(self):
        """

        :return:
        """
        return [x.get_voltage() for x in self.get_windings()]

    def get_dict(self):
        d = super().get_dict()
        R, X, G, B = self.get_pu_values()
        voltages = self.get_voltages()
        n_windings = self.get_windings_number()
        d['r_pu'] = R
        d['x_pu'] = X
        d['g_pu'] = G
        d['b_pu'] = B
        d['windings_number'] = n_windings
        for i in range(n_windings):
            v = voltages[i]
            d['V' + str(i+1)] = v if v is not None else ''
        return d


class Winding(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.tap_changers = list()


class EnergyConsumer(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.LoadResponse = None
        self.EquipmentContainer = None
        self.name = ''
        self.p = 0
        self.q = 0


class ConformLoad(MonoPole):

    def __init__(self, rfid, tpe):
        MonoPole.__init__(self, rfid, tpe)

        self.LoadGroup = None
        self.LoadResponse = None
        self.EquipmentContainer = None
        self.p = 0
        self.q = 0

    def get_dict(self):

        d = super().get_dict()
        d['p'] = self.p
        d['q'] = self.q

        return d


class NonConformLoad(MonoPole):

    def __init__(self, rfid, tpe):
        MonoPole.__init__(self, rfid, tpe)

        self.name = ''
        self.EquipmentContainer = None
        self.LoadResponse = None
        self.LoadGroup = None


class NonConformLoadGroup(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''


class LoadResponseCharacteristic(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.exponentModel = True
        self.pVoltageExponent = 0
        self.qVoltageExponent = 0


class RegulatingControl(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.mode = ''
        self.Terminal = None
        self.discrete = False
        self.enabled = True
        self.targetDeadband = 0
        self.targetValue = 0
        self.targetValueUnitMultiplier = ''


class RatioTapChanger(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.stepVoltageIncrement = 0
        self.tculControlMode = ''
        self.TransformerEnd = None
        self.RatioTapChangerTable = None
        self.highStep = 0
        self.lowStep = 0
        self.ltcFlag = False
        self.neutralStep = 0
        self.neutralU = 0
        self.normalStep = 0
        self.TapChangerControl = None
        self.name = ''
        self.controlEnabled = True
        self.step = 0


class GeneratingUnit(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.initialP = 0
        self.longPF = 0
        self.maxOperatingP = 0
        self.minOperatingP = 0
        self.nominalP = 0
        self.shortPF = 0
        self.EquipmentContainer = None
        self.description = ''
        self.normalPF = 0


class SynchronousMachine(MonoPole):

    def __init__(self, rfid, tpe):
        MonoPole.__init__(self, rfid, tpe)

        self.qPercent = 0
        self.type = ''
        self.InitialReactiveCapabilityCurve = None
        self.ratedS = 0
        self.GeneratingUnit = None
        self.RegulatingControl = None
        self.EquipmentContainer = None
        self.operatingMode = ''
        self.referencePriority = ''
        self.p = 0
        self.q = 0
        self.controlEnabled = True

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['GeneratingUnit'] = self.GeneratingUnit.uuid if self.GeneratingUnit is not None else ''

        d['p'] = self.p
        d['q'] = self.q

        d['qPercent'] = self.qPercent
        d['ratedS'] = self.ratedS
        d['controlEnabled'] = self.controlEnabled
        d['type'] = self.type

        return d


class HydroGenerationUnit(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''
        self.description = ''
        self.maxOperatingP = 0
        self.minOperatingP = 0
        self.EquipmentContainer = None
        self.initialP = 0
        self.longPF = 0
        self.shortPF = 0
        self.nominalP = 0

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['EquipmentContainer'] = self.EquipmentContainer.uuid if self.EquipmentContainer is not None else ''
        d['maxOperatingP'] = self.maxOperatingP
        d['minOperatingP'] = self.minOperatingP
        d['initialP'] = self.initialP
        d['nominalP'] = self.nominalP
        d['longPF'] = self.longPF
        d['shortPF'] = self.shortPF

        return d


class HydroPowerPlant(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''
        self.hydroPlantStorageType = ''

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['hydroPlantStorageType'] = self.hydroPlantStorageType

        return d


class LinearShuntCompensator(MonoPole):

    def __init__(self, rfid, tpe):
        MonoPole.__init__(self, rfid, tpe)

        self.name = ''
        self.EquipmentContainer = None
        self.bPerSection = 0
        self.gPerSection = 0
        self.maximumSections = 0
        self.nomU = 0
        self.normalSections = 0

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['EquipmentContainer'] = self.EquipmentContainer.uuid if self.EquipmentContainer is not None else ''

        d['bPerSection'] = self.bPerSection
        d['gPerSection'] = self.gPerSection
        d['maximumSections'] = self.maximumSections
        d['nomU'] = self.nomU
        d['normalSections'] = self.normalSections

        return d


class NuclearGeneratingUnit(MonoPole):

    def __init__(self, rfid, tpe):
        MonoPole.__init__(self, rfid, tpe)

        self.name = ''
        self.description = ''
        self.maxOperatingP = 0
        self.minOperatingP = 0
        self.EquipmentContainer = None
        self.initialP = 0
        self.longPF = 0
        self.shortPF = 0
        self.nominalP = 0
        self.variableCost = 0

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['EquipmentContainer'] = self.EquipmentContainer.uuid if self.EquipmentContainer is not None else ''
        d['maxOperatingP'] = self.maxOperatingP
        d['minOperatingP'] = self.minOperatingP
        d['initialP'] = self.initialP
        d['nominalP'] = self.nominalP
        d['longPF'] = self.longPF
        d['shortPF'] = self.shortPF
        d['variableCost'] = self.variableCost

        return d


class RatioTapChangerTable(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''


class RatioTapChangerTablePoint(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.ratio = 0
        self.step = 0
        self.RatioTapChangerTable = None

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['RatioTapChangerTable'] = self.RatioTapChangerTable.uuid if self.RatioTapChangerTable is not None else ''
        d['ratio'] = self.ratio
        d['step'] = self.step

        return d


class ReactiveCapabilityCurve(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''
        self.curveStyle = ''
        self.xUnit = ''
        self.y1Unit = ''
        self.y2Unit = ''


class StaticVarCompensator(MonoPole):

    def __init__(self, rfid, tpe):
        MonoPole.__init__(self, rfid, tpe)

        self.name = ''
        self.EquipmentContainer = None
        self.slope = 0
        self.inductiveRating = 0
        self.capacitiveRating = 0
        self.voltageSetPoint = 0
        self.sVCControlMode = ''
        self.RegulatingControl = None

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['EquipmentContainer'] = self.EquipmentContainer.uuid if self.EquipmentContainer is not None else ''
        d['RegulatingControl'] = self.RegulatingControl.uuid if self.RegulatingControl is not None else ''
        d['slope'] = self.slope
        d['inductiveRating'] = self.inductiveRating
        d['capacitiveRating'] = self.capacitiveRating
        d['voltageSetPoint'] = self.voltageSetPoint
        d['sVCControlMode'] = self.sVCControlMode

        return d


class TapChangerControl(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.name = ''
        self.Terminal = None
        self.mode = ''


class ThermalGenerationUnit(MonoPole):

    def __init__(self, rfid, tpe):
        MonoPole.__init__(self, rfid, tpe)

        self.name = ''
        self.description = ''
        self.maxOperatingP = 0
        self.minOperatingP = 0
        self.EquipmentContainer = None
        self.initialP = 0
        self.longPF = 0
        self.shortPF = 0
        self.nominalP = 0

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['EquipmentContainer'] = self.EquipmentContainer.uuid if self.EquipmentContainer is not None else ''
        d['maxOperatingP'] = self.maxOperatingP
        d['minOperatingP'] = self.minOperatingP
        d['initialP'] = self.initialP
        d['nominalP'] = self.nominalP
        d['longPF'] = self.longPF
        d['shortPF'] = self.shortPF

        return d


class WindGenerationUnit(MonoPole):

    def __init__(self, rfid, tpe):
        MonoPole.__init__(self, rfid, tpe)

        self.name = ''
        self.description = ''
        self.maxOperatingP = 0
        self.minOperatingP = 0
        self.EquipmentContainer = None
        self.initialP = 0
        self.longPF = 0
        self.shortPF = 0
        self.nominalP = 0
        self.variableCost = 0
        self.windGenUnitType = ''

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['EquipmentContainer'] = self.EquipmentContainer.uuid if self.EquipmentContainer is not None else ''
        d['maxOperatingP'] = self.maxOperatingP
        d['minOperatingP'] = self.minOperatingP
        d['initialP'] = self.initialP
        d['nominalP'] = self.nominalP
        d['longPF'] = self.longPF
        d['shortPF'] = self.shortPF
        d['variableCost'] = self.variableCost
        d['windGenUnitType'] = self.windGenUnitType
        d['description'] = self.description

        return d


class FullModel(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.scenarioTime = ''
        self.created = ''
        self.version = ''
        self.profile = ''
        self.modelingAuthoritySet = ''
        self.DependentOn = ''

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['scenarioTime'] = self.scenarioTime
        d['created'] = self.created
        d['version'] = self.version
        d['profile'] = self.profile
        d['modelingAuthoritySet'] = self.modelingAuthoritySet
        d['DependentOn'] = self.longDependentOnPF

        return d


class TieFlow(GeneralContainer):

    def __init__(self, rfid, tpe):
        GeneralContainer.__init__(self, rfid, tpe)

        self.ControlArea = None
        self.Terminal = None
        self.positiveFlowIn = True

    def get_dict(self):
        """

        :return:
        """
        d = super().get_dict()

        d['ControlArea'] = self.ControlArea.uuid if self.ControlArea is not None else ''
        d['Terminal'] = self.Terminal.uuid if self.Terminal is not None else ''
        d['positiveFlowIn'] = self.positiveFlowIn

        return d


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

        class_dict = {'GeneralContainer': GeneralContainer,
                      'Terminal': Terminal,
                      'BaseVoltage': BaseVoltage,
                      'TopologicalNode': TopologicalNode,
                      'BusbarSection': BusbarSection,
                      'Substation': Substation,
                      'ConnectivityNode': ConnectivityNode,
                      'OperationalLimitSet': OperationalLimitSet,
                      'GeographicalRegion': GeographicalRegion,
                      'SubGeographicalRegion': SubGeographicalRegion,
                      'VoltageLevel': VoltageLevel,
                      'CurrentLimit': CurrentLimit,
                      'VoltageLimit': VoltageLimit,
                      'EquivalentInjection': EquivalentInjection,
                      'EquivalentNetwork': EquivalentNetwork,
                      'Breaker': Breaker,
                      'Switch': Switch,
                      'Line': Line,
                      'ACLineSegment': ACLineSegment,
                      'PowerTransformerEnd': PowerTransformerEnd,
                      'PowerTransformer': PowerTransformer,
                      'Winding': Winding,
                      'EnergyConsumer': EnergyConsumer,
                      'ConformLoad': ConformLoad,
                      'NonConformLoad': NonConformLoad,
                      'LoadResponseCharacteristic': LoadResponseCharacteristic,
                      'RegulatingControl': RegulatingControl,
                      'RatioTapChanger': RatioTapChanger,
                      'GeneratingUnit': GeneratingUnit,
                      'SynchronousMachine': SynchronousMachine,
                      'HydroGenerationUnit': HydroGenerationUnit,
                      'HydroPowerPlant': HydroPowerPlant,
                      'LinearShuntCompensator': LinearShuntCompensator,
                      'NuclearGeneratingUnit': NuclearGeneratingUnit,
                      'RatioTapChangerTable': RatioTapChangerTable,
                      'RatioTapChangerTablePoint': RatioTapChangerTablePoint,
                      'ReactiveCapabilityCurve': ReactiveCapabilityCurve,
                      'StaticVarCompensator': StaticVarCompensator,
                      'TapChangerControl': TapChangerControl,
                      'ThermalGenerationUnit': ThermalGenerationUnit,
                      'WindGenerationUnit': WindGenerationUnit,
                      'FullModel': FullModel,
                      'TieFlow': TieFlow}

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

                        id = index_find(xml_line, '"', '">').replace('#', '')

                        # start recording object
                        if tpe in class_dict.keys():
                            CLS = class_dict[tpe]
                        else:
                            CLS = GeneralContainer
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


class CIMExport:

    def __init__(self, circuit: MultiCircuit):

        self.circuit = circuit

        self.logger = Logger()

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
        model = GeneralContainer(rfid=self.circuit.name, tpe='Model')
        model.properties['name'] = self.circuit.name
        model.properties['version'] = 1
        model.properties['description'] = self.circuit.comments
        text_file.write(model.get_xml(1))

        bus_id_dict = dict()
        base_voltages = set()
        base_voltages_dict = dict()

        # dictionary of substation given a bus
        substation_bus = dict()

        # buses sweep to gather previous data (base voltages, etc..)
        for i, bus in enumerate(self.circuit.buses):

            Vnom = bus.Vnom

            # add the nominal voltage to the set of bus_voltages
            base_voltages.add(Vnom)

            # if the substation was not accounted for, create the list of voltage levels
            if bus.substation not in substation_bus.keys():
                substation_bus[bus.substation] = dict()

            if Vnom not in substation_bus[bus.substation].keys():
                substation_bus[bus.substation][Vnom] = list()

            # add bus to the categorization
            substation_bus[bus.substation][Vnom].append(bus)

        # generate Base voltages
        for V in base_voltages:

            conn_node_id = 'Base_voltage_' + str(V).replace('.', '_')

            base_voltages_dict[V] = conn_node_id

            model = GeneralContainer(rfid=conn_node_id, tpe='BaseVoltage')
            model.properties['name'] = conn_node_id
            model.properties['nominalVoltage'] = V
            text_file.write(model.get_xml(1))

        # generate voltage levels, substations and buses and their objects
        substation_idx = 0
        voltage_level_idx = 0
        bus_idx = 0
        terminal_resources = ['TopologicalNode', 'ConductingEquipment']

        for substation in substation_bus.keys():

            substation_id = substation + '_' + str(substation_idx)
            substation_idx += 1

            model = GeneralContainer(rfid=substation_id, tpe='Substation', resources=['Location', 'SubGeographicalRegion'])
            model.properties['name'] = substation
            model.properties['aliasName'] = substation
            model.properties['PSRType'] = ''
            model.properties['Location'] = ''
            model.properties['SubGeographicalRegion'] = ''
            text_file.write(model.get_xml(1))

            for voltage_level in substation_bus[substation].keys():

                voltage_level_id = 'VoltageLevel_' + str(voltage_level).replace('.', '_') + '_' + str(voltage_level_idx)
                voltage_level_idx += 1

                base_voltage = base_voltages_dict[voltage_level]

                model = GeneralContainer(rfid=voltage_level_id, tpe='VoltageLevel', resources=['BaseVoltage', 'Substation'])
                model.properties['name'] = substation
                model.properties['aliasName'] = substation
                model.properties['BaseVoltage'] = base_voltage
                model.properties['Substation'] = substation_id
                text_file.write(model.get_xml(1))

                # buses sweep to actually generate XML
                for bus in substation_bus[substation][voltage_level]:

                    # make id
                    conn_node_id = 'BUS_' + str(bus_idx)

                    Vnom = bus.Vnom

                    # make dictionary entry
                    bus_id_dict[bus] = conn_node_id

                    base_voltage = base_voltages_dict[Vnom]

                    if bus.Vnom <= 0.0:
                        self.logger.add_error('Zero nominal voltage', bus.name)

                    # generate model
                    model = GeneralContainer(rfid=conn_node_id, tpe='ConnectivityNode',
                                             resources=['BaseVoltage', 'VoltageLevel', 'ConnectivityNodeContainer'],
                                             class_replacements={'name': 'IdentifiedObject',
                                                                 'aliasName': 'IdentifiedObject'}
                                             )
                    model.properties['name'] = bus.name
                    model.properties['aliasName'] = bus.name
                    model.properties['BaseVoltage'] = base_voltage
                    # model.properties['VoltageLevel'] = voltage_level_id
                    model.properties['ConnectivityNodeContainer'] = voltage_level_id
                    text_file.write(model.get_xml(1))

                    for il, elm in enumerate(bus.loads):

                        id2 = conn_node_id + '_LOAD_' + str(il)
                        id3 = id2 + '_LRC'

                        model = GeneralContainer(rfid=id2, tpe='ConformLoad',
                                                 resources=['BaseVoltage', 'LoadResponse', 'VoltageLevel'],
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject',
                                                                     'EquipmentContainer': 'Equipment'}
                                                 )
                        model.properties['name'] = elm.name
                        model.properties['aliasName'] = elm.name
                        model.properties['BaseVoltage'] = base_voltage
                        model.properties['EquipmentContainer'] = voltage_level_id
                        model.properties['LoadResponse'] = id3
                        model.properties['pfixed'] = elm.P
                        model.properties['qfixed'] = elm.Q
                        model.properties['normallyInService'] = elm.active
                        text_file.write(model.get_xml(1))

                        model = GeneralContainer(rfid=id3, tpe='LoadResponseCharacteristic', resources=[])
                        model.properties['name'] = elm.name
                        model.properties['exponentModel'] = 'false'
                        model.properties['pConstantCurrent'] = elm.Ir
                        model.properties['pConstantImpedance'] = 1 / (elm.G + 1e-20)
                        model.properties['pConstantPower'] = elm.P
                        model.properties['pVoltageExponent'] = 0.0
                        model.properties['pFrequencyExponent'] = 0.0
                        model.properties['qConstantCurrent'] = elm.Ir
                        model.properties['qConstantImpedance'] = 1 / (elm.B + 1e-20)
                        model.properties['qConstantPower'] = elm.Q
                        model.properties['qVoltageExponent'] = 0.0
                        model.properties['qFrequencyExponent'] = 0.0
                        text_file.write(model.get_xml(1))

                        # Terminal 1 (from)
                        model = GeneralContainer(rfid=id2 + '_T', tpe='Terminal',
                                                 resources=terminal_resources,
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject'})
                        model.properties['name'] = elm.name
                        model.properties['TopologicalNode'] = bus_id_dict[bus]
                        model.properties['ConductingEquipment'] = id2
                        model.properties['connected'] = 'true'
                        model.properties['sequenceNumber'] = '1'
                        text_file.write(model.get_xml(1))

                    for il, elm in enumerate(bus.static_generators):

                        id2 = conn_node_id + '_StatGen_' + str(il)

                        model = GeneralContainer(rfid=id2, tpe='ConformLoad',
                                                 resources=['BaseVoltage', 'LoadResponse', 'VoltageLevel'],
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject',
                                                                     'EquipmentContainer': 'Equipment'}
                                                 )
                        model.properties['name'] = elm.name
                        model.properties['aliasName'] = elm.name
                        model.properties['BaseVoltage'] = base_voltage
                        model.properties['EquipmentContainer'] = voltage_level_id
                        model.properties['pfixed'] = -elm.P
                        model.properties['qfixed'] = -elm.Q
                        model.properties['normallyInService'] = elm.active
                        text_file.write(model.get_xml(1))

                        # Terminal 1 (from)
                        model = GeneralContainer(rfid=id2 + '_T', tpe='Terminal',
                                                 resources=terminal_resources,
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject'}
                                                 )
                        model.properties['name'] = elm.name
                        model.properties['TopologicalNode'] = bus_id_dict[bus]
                        model.properties['ConductingEquipment'] = id2
                        model.properties['connected'] = 'true'
                        model.properties['sequenceNumber'] = '1'
                        text_file.write(model.get_xml(1))

                    for il, elm in enumerate(bus.controlled_generators):

                        id2 = conn_node_id + '_SyncGen_' + str(il)
                        id3 = id2 + '_GU'
                        id4 = id2 + '_RC'

                        model = GeneralContainer(rfid=id2, tpe='SynchronousMachine',
                                                 resources=['BaseVoltage', 'RegulatingControl',
                                                            'GeneratingUnit', 'VoltageLevel'],
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject',
                                                                     'EquipmentContainer': 'Equipment'}
                                                 )
                        model.properties['name'] = elm.name
                        model.properties['aliasName'] = elm.name
                        model.properties['BaseVoltage'] = base_voltage
                        model.properties['EquipmentContainer'] = voltage_level_id
                        model.properties['RegulatingControl'] = id3
                        model.properties['GeneratingUnit'] = id4
                        model.properties['maxQ'] = elm.Qmax
                        model.properties['minQ'] = elm.Qmin
                        model.properties['ratedS'] = elm.Snom
                        model.properties['normallyInService'] = elm.active
                        text_file.write(model.get_xml(1))

                        model = GeneralContainer(rfid=id3, tpe='RegulatingControl', resources=[])
                        model.properties['name'] = elm.name
                        model.properties['targetValue'] = elm.Vset * bus.Vnom
                        text_file.write(model.get_xml(1))

                        model = GeneralContainer(rfid=id4, tpe='GeneratingUnit', resources=[])
                        model.properties['name'] = elm.name
                        model.properties['initialP'] = elm.P
                        text_file.write(model.get_xml(1))

                        # Terminal 1 (from)
                        model = GeneralContainer(rfid=id2 + '_T', tpe='Terminal',
                                                 resources=terminal_resources,
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject'}
                                                 )
                        model.properties['name'] = elm.name
                        model.properties['TopologicalNode'] = bus_id_dict[bus]
                        model.properties['ConductingEquipment'] = id2
                        model.properties['connected'] = 'true'
                        model.properties['sequenceNumber'] = '1'
                        text_file.write(model.get_xml(1))

                    for il, elm in enumerate(bus.shunts):

                        id2 = conn_node_id + '_Shunt_' + str(il)

                        model = GeneralContainer(rfid=id2, tpe='ShuntCompensator',
                                                 resources=['BaseVoltage', 'VoltageLevel'],
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject',
                                                                     'EquipmentContainer': 'Equipment'}
                                                 )
                        model.properties['name'] = elm.name
                        model.properties['aliasName'] = elm.name
                        model.properties['BaseVoltage'] = base_voltage
                        model.properties['EquipmentContainer'] = voltage_level_id
                        model.properties['gPerSection'] = elm.G
                        model.properties['bPerSection'] = elm.B
                        model.properties['g0PerSection'] = 0.0
                        model.properties['b0PerSection'] = 0.0
                        model.properties['normallyInService'] = elm.active
                        text_file.write(model.get_xml(1))

                        # Terminal 1 (from)
                        model = GeneralContainer(rfid=id2 + '_T', tpe='Terminal',
                                                 resources=terminal_resources,
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject'}
                                                 )
                        model.properties['name'] = elm.name
                        model.properties['TopologicalNode'] = bus_id_dict[bus]
                        model.properties['ConductingEquipment'] = id2
                        model.properties['connected'] = 'true'
                        model.properties['sequenceNumber'] = '1'
                        text_file.write(model.get_xml(1))

                    if bus.is_slack:
                        equivalent_network_id = conn_node_id + '_EqNetwork'

                        model = GeneralContainer(rfid=equivalent_network_id, tpe='EquivalentNetwork',
                                                 resources=['BaseVoltage', 'VoltageLevel'],
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject'})
                        model.properties['name'] = bus.name + '_Slack'
                        model.properties['aliasName'] = bus.name + '_Slack'
                        model.properties['BaseVoltage'] = base_voltage
                        model.properties['VoltageLevel'] = voltage_level_id
                        text_file.write(model.get_xml(1))

                        # Terminal 1 (from)
                        model = GeneralContainer(rfid=equivalent_network_id + '_T', tpe='Terminal',
                                                 resources=terminal_resources,
                                                 class_replacements={'name': 'IdentifiedObject',
                                                                     'aliasName': 'IdentifiedObject'}
                                                 )
                        model.properties['name'] = equivalent_network_id + '_T'
                        model.properties['TopologicalNode'] = bus_id_dict[bus]
                        model.properties['ConductingEquipment'] = equivalent_network_id
                        model.properties['connected'] = 'true'
                        model.properties['sequenceNumber'] = '1'
                        text_file.write(model.get_xml(1))

                    # increment the bus index
                    bus_idx += 1

        # Branches
        winding_resources = ['connectionType', 'windingType', 'PowerTransformer']
        tap_changer_resources = ['TransformerWinding']
        for i, branch in enumerate(self.circuit.transformers2w):

            conn_node_id = 'Transformer_' + str(i)

            model = GeneralContainer(rfid=conn_node_id, tpe='PowerTransformer',
                                     resources=[],
                                     class_replacements={'name': 'IdentifiedObject',
                                                         'aliasName': 'IdentifiedObject',
                                                         'EquipmentContainer': 'Equipment'}
                                     )
            model.properties['name'] = branch.name
            model.properties['aliasName'] = branch.name
            text_file.write(model.get_xml(1))

            #  warnings
            if branch.rate <= 0.0:
                self.logger.add_error('The rate is 0', branch.name)
                raise Exception(branch.name + ": The rate is 0, this will cause a problem when loading.")

            if branch.bus_from.Vnom <= 0.0:
                self.logger.add_error('Vfrom is zero', branch.name)
                raise Exception(branch.name + ": The voltage at the from side, this will cause a problem when loading.")

            if branch.bus_to.Vnom <= 0.0:
                self.logger.add_error('Vto is zero', branch.name)
                raise Exception(branch.name + ": The voltage at the to side, this will cause a problem when loading.")

            # W1 (from)
            winding_power_rate = branch.rate / 2
            Zbase = (branch.bus_from.Vnom ** 2) / winding_power_rate
            Ybase = 1 / Zbase
            model = GeneralContainer(rfid=conn_node_id + "_W1", tpe='PowerTransformerEnd',
                                     resources=winding_resources,
                                     class_replacements={'name': 'IdentifiedObject',
                                                         'aliasName': 'IdentifiedObject',
                                                         'BaseVoltage': 'ConductingEquipment'}
                                     )
            model.properties['name'] = branch.name
            model.properties['PowerTransformer'] = conn_node_id
            model.properties['BaseVoltage'] = base_voltages_dict[branch.bus_from.Vnom]
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
            model = GeneralContainer(rfid=conn_node_id + "_W2", tpe='PowerTransformerEnd',
                                     resources=winding_resources,
                                     class_replacements={'name': 'IdentifiedObject',
                                                         'aliasName': 'IdentifiedObject',
                                                         'BaseVoltage': 'ConductingEquipment'}
                                     )
            model.properties['name'] = branch.name
            model.properties['PowerTransformer'] = conn_node_id
            model.properties['BaseVoltage'] = base_voltages_dict[branch.bus_to.Vnom]
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

            # add tap changer at the "to" winding
            if branch.tap_module != 1.0 and branch.angle != 0.0:

                Vnom = branch.bus_to.Vnom
                SVI = (Vnom - Vnom * branch.tap_module) * 100.0 / Vnom

                model = GeneralContainer(rfid=conn_node_id + 'Tap_2', tpe='RatioTapChanger', resources=tap_changer_resources)
                model.properties['TransformerWinding'] = conn_node_id + "_W2"
                model.properties['name'] = branch.name + 'tap changer'
                model.properties['neutralU'] = Vnom
                model.properties['stepVoltageIncrement'] = SVI
                model.properties['step'] = 0
                model.properties['lowStep'] = -1
                model.properties['highStep'] = 1
                model.properties['subsequentDelay'] = branch.angle
                text_file.write(model.get_xml(1))



            # Terminal 1 (from)
            model = GeneralContainer(rfid=conn_node_id + '_T1', tpe='Terminal',
                                     resources=terminal_resources,
                                     class_replacements={'name': 'IdentifiedObject',
                                                         'aliasName': 'IdentifiedObject'}
                                     )
            model.properties['name'] = bus.name + '_' + branch.name + '_T1'
            model.properties['TopologicalNode'] = bus_id_dict[branch.bus_from]
            model.properties['ConductingEquipment'] = conn_node_id
            model.properties['connected'] = 'true'
            model.properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

            # Terminal 2 (to)
            model = GeneralContainer(rfid=conn_node_id + '_T2', tpe='Terminal',
                                     resources=terminal_resources,
                                     class_replacements={'name': 'IdentifiedObject',
                                                         'aliasName': 'IdentifiedObject'}
                                     )
            model.properties['name'] = bus.name + '_' + branch.name + '_T2'
            model.properties['TopologicalNode'] = bus_id_dict[branch.bus_to]
            model.properties['ConductingEquipment'] = conn_node_id
            model.properties['connected'] = 'true'
            model.properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        for i, branch in enumerate(self.circuit.lines):

            if branch.branch_type == gcdev.BranchType.Line or branch.branch_type == gcdev.BranchType.Branch:

                conn_node_id = 'Branch_' + str(i)
                Zbase = (branch.bus_from.Vnom ** 2) / self.circuit.Sbase

                if branch.bus_from.Vnom <= 0.0:
                    Ybase = 0
                else:
                    Ybase = 1 / Zbase

                model = GeneralContainer(rfid=conn_node_id, tpe='ACLineSegment',
                                         resources=['BaseVoltage'],
                                         class_replacements={'name': 'IdentifiedObject',
                                                             'aliasName': 'IdentifiedObject',
                                                             'BaseVoltage': 'ConductingEquipment',
                                                             'value': 'CurrentLimit'}
                                         )
                model.properties['name'] = branch.name
                model.properties['aliasName'] = branch.name
                model.properties['BaseVoltage'] = base_voltages_dict[branch.bus_from.Vnom]
                model.properties['r'] = branch.R * Zbase
                model.properties['x'] = branch.X * Zbase
                model.properties['gch'] = branch.G * Ybase
                model.properties['bch'] = branch.B * Ybase
                model.properties['r0'] = 0.0
                model.properties['x0'] = 0.0
                model.properties['g0ch'] = 0.0
                model.properties['b0ch'] = 0.0
                model.properties['length'] = 1.0
                model.properties['value'] = branch.rate / (branch.bus_from.Vnom * sqrt(3))  # kA
                text_file.write(model.get_xml(1))

            elif branch.branch_type == gcdev.BranchType.Switch:

                conn_node_id = 'Switch_' + str(i)
                model = GeneralContainer(rfid=conn_node_id, tpe='Switch', resources=['BaseVoltage'])
                model.properties['name'] = branch.name
                model.properties['aliasName'] = branch.name
                model.properties['BaseVoltage'] = base_voltages_dict[branch.bus_from.Vnom]
                model.properties['normalOpen'] = False
                model.properties['open'] = not branch.active
                text_file.write(model.get_xml(1))

            elif branch.branch_type == gcdev.BranchType.Reactance:
                self.logger.add_warning('Reactance CIM export not implemented yet, exported as a branch', branch.name)

                conn_node_id = 'Reactance_' + str(i)
                Zbase = (branch.bus_from.Vnom ** 2) / self.circuit.Sbase

                if branch.bus_from.Vnom <= 0.0:
                    Ybase = 0
                else:
                    Ybase = 1 / Zbase

                model = GeneralContainer(rfid=conn_node_id, tpe='ACLineSegment', resources=['BaseVoltage'])
                model.properties['name'] = branch.name
                model.properties['aliasName'] = branch.name
                model.properties['BaseVoltage'] = base_voltages_dict[branch.bus_from.Vnom]
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
            model = GeneralContainer(rfid=conn_node_id + '_T1', tpe='Terminal',
                                     resources=terminal_resources,
                                     class_replacements={'name': 'IdentifiedObject',
                                                         'aliasName': 'IdentifiedObject'}
                                     )
            model.properties['name'] = bus.name + '_' + branch.name + '_T1'
            model.properties['TopologicalNode'] = bus_id_dict[branch.bus_from]
            model.properties['ConductingEquipment'] = conn_node_id
            model.properties['connected'] = 'true'
            model.properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

            # Terminal 2 (to)
            model = GeneralContainer(rfid=conn_node_id + '_T2', tpe='Terminal',
                                     resources=terminal_resources,
                                     class_replacements={'name': 'IdentifiedObject',
                                                         'aliasName': 'IdentifiedObject'}
                                     )
            model.properties['name'] = bus.name + '_' + branch.name + '_T2'
            model.properties['TopologicalNode'] = bus_id_dict[branch.bus_to]
            model.properties['ConductingEquipment'] = conn_node_id
            model.properties['connected'] = 'true'
            model.properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        # end
        text_file.write("</rdf:RDF>")

        text_file.close()


class CIMImport:

    def __init__(self, text_func=None, progress_func=None):

        self.logger = Logger()

        self.cim = CIMCircuit(logger=self.logger)

        # relations between connectivity nodes and terminals
        # node_terminal[some_node] = list of terminals
        self.node_terminal = dict()
        self.terminal_node = dict()

        self.text_func = text_func
        self.progress_func = progress_func

        self.needs_compiling = True

        self.topology = None

    def emit_text(self, val):
        if self.text_func is not None:
            self.text_func(val)

    def emit_progress(self, val):
        if self.progress_func is not None:
            self.progress_func(val)

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

    def try_properties(self, dictionary, properties, defaults = None):
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
                except TypeError:
                    pass  # val is a string
            except KeyError:
                # property not found
                if defaults is None:
                    print(prop, 'not found')
                    val = None
                else:
                    val = defaults[i]

            res[i] = val

        return res

    def parse_model(self, cim: CIMCircuit, circuit: MultiCircuit, recognised: Set):
        """

        :param cim:
        :param circuit:
        :param recognised:
        :return:
        """
        if 'Model' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['Model']:
                if 'description' in elm.properties.keys():
                    circuit.comments = elm.properties['description']

                if 'name' in elm.properties.keys():
                    circuit.name = elm.properties['name']

                # add class to recognised objects
                recognised.add(elm.tpe)

    def parse_terminals(self, cim: CIMCircuit, T_dict: Dict, recognised: Set):

        if 'Terminal' in cim.elements_by_type.keys():

            for elm in cim.elements_by_type['Terminal']:
                # if 'name' in elm.properties:
                #     name = elm.properties['name']
                # else:
                #     name = elm.rfid
                # T = Bus(name=name)
                T_dict[elm.rfid] = elm
                # circuit.add_bus(T)

                # add class to recognised objects
                recognised.add(elm.tpe)

        else:
            self.logger.add_error('There are no Terminals!!!!!')

    def parse_connectivity_nodes(self, cim: CIMCircuit, circuit: MultiCircuit, CN_dict: Dict, T_dict: Dict,
                                 recognised: Set):
        """

        :param cim:
        :param circuit:
        :param CN_dict:
        :param T_dict:
        :param recognised:
        :return:
        """
        cim_nodes = ['TopologicalNode', 'ConnectivityNode']
        if any_in_dict(cim.elements_by_type, cim_nodes):
            for elm in get_elements(cim.elements_by_type, cim_nodes):
                try:
                    name = elm.properties['name']
                except KeyError:
                    name = ''

                if len(elm.BaseVoltage) > 0:
                    Vnom = float(elm.get_base_voltage().properties['nominalVoltage'])
                else:
                    Vnom = 0

                CN = gcdev.Bus(idtag=rfid2uuid(elm.rfid),
                               name=name,
                               vnom=Vnom)
                CN_dict[elm.rfid] = CN
                circuit.add_bus(CN)

                # add class to recognised objects
                recognised.add(elm.tpe)
        else:
            self.logger.add_error('There are no TopologicalNodes nor ConnectivityNodes!!!!!')

        # CN_T: build the connectivity nodes - terminals relations structure
        if any_in_dict(cim.elements_by_type, cim_nodes):
            for elm in get_elements(cim.elements_by_type, cim_nodes):

                # get the connectivity node
                CN = CN_dict[elm.rfid]

                # get the terminals associated to the connectivity node and register the associations
                for term in elm.get_terminals():
                    try:
                        self.add_node_terminal_relation(CN, T_dict[term.rfid])
                    except KeyError:
                        self.logger.add_error('Terminal ID not found', term.rfid)

                # add class to recognised objects
                recognised.add(elm.tpe)
        else:
            self.logger.add_error('No topological nodes: The grid MUST have topological Nodes')

    def parse_bus_bars(self, cim: CIMCircuit, T_dict: Dict, recognised: Set):
        """

        :param cim:
        :param T_dict:
        :param recognised:
        :return:
        """
        if 'BusbarSection' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['BusbarSection']:
                term = elm.get_terminals()
                T1 = T_dict[term[0].rfid]  # get the terminal of the bus bar section
                CN = self.terminal_node[T1][0]  # get the connectivity node of the terminal
                CN.is_bus = True  # the connectivity node has a BusbarSection attached, hence it is a real bus

                # add class to recognised objects
                recognised.add(elm.tpe)
        else:
            self.logger.add_error("No BusbarSections: There is no chance to reduce the grid")

    def parse_per_length_sequence_impedance(self, cim: CIMCircuit, circuit: MultiCircuit,
                                            PLSI_dict: Dict, recognised: Set):
        """

        :param cim:
        :param PLSI_dict:
        :param recognised:
        :return:
        """
        if 'PerLengthSequenceImpedance' in cim.elements_by_type.keys():
            prop_lst = ['r', 'x', 'r0', 'x0', 'gch', 'bch', 'g0ch', 'b0ch']
            prop_def = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            for elm in cim.elements_by_type['PerLengthSequenceImpedance']:
                r, x, r0, x0, g, b, g0, b0 = self.try_properties(elm.properties, prop_lst, prop_def)
                obj = gcdev.SequenceLineType(name=elm.rfid, R=r, X=x, G=g, B=b, R0=r0, X0=x0, G0=g0, B0=b0)
                circuit.add_sequence_line(obj)
                elm.template = obj

                PLSI_dict[elm.rfid] = elm

                # add class to recognised objects
                recognised.add(elm.tpe)
            sl = circuit.get_catalogue_dict_by_name('Sequence lines')

    def parse_ac_line_segment(self, cim: CIMCircuit, circuit: MultiCircuit, T_dict: Dict, PLSI_dict: Dict,
                              recognised: Set):
        """

        :param cim:
        :param circuit:
        :param T_dict:
        :param PLSI_dict:
        :param recognised:
        :return:
        """
        prop_lst = ['r', 'x', 'r0', 'x0', 'gch', 'bch', 'g0ch', 'b0ch']
        if 'ACLineSegment' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['ACLineSegment']:
                term = elm.get_terminals()
                if len(term) == 2:
                    T1 = T_dict[term[0].rfid]
                    T2 = T_dict[term[1].rfid]
                    B1 = self.terminal_node[T1][0]
                    B2 = self.terminal_node[T2][0]
                else:
                    self.logger.add_error('Number of terminals different of 2', elm.rfid, len(term))
                    continue

                try:
                    name = elm.properties['name']
                except KeyError:
                    name = ''

                prop_def = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                template = gcdev.BranchTemplate()
                if 'PerLengthImpedance' in elm.properties:

                    pli = elm.properties['PerLengthImpedance']

                    try:
                        l = float(elm.properties['length'])
                    except KeyError:
                        l = 0.0

                    if pli in PLSI_dict:
                        r, x, r0, x0, g, b, g0, b0 = self.try_properties(PLSI_dict[pli].properties, prop_lst, prop_def)
                        template = PLSI_dict[pli].template

                        r = r * l
                        x = x * l
                        g = g * l
                        b = b * l

                    else:
                        self.logger.add_error('Refers to missing PerLengthImpedance', elm.rfid)
                        continue
                else:
                    r, x, r0, x0, g, b, g0, b0 = self.try_properties(elm.properties, prop_lst, prop_def)

                    try:
                        l = float(elm.properties['length'])
                    except KeyError:
                        l = 0.0

                try:
                    Vnom = float(elm.get_base_voltage().properties['nominalVoltage'])
                except KeyError:
                    Vnom = 1.0
                    self.logger.add_error('No nominalVoltage property', elm.rfid)
                except IndexError:
                    Vnom = 1.0
                    self.logger.add_error('No BaseVoltage', elm.rfid)

                if Vnom <= 0:
                    self.logger.add_error('Zero base voltage. This causes a failure in the file loading', elm.rfid)
                    R = 1e-20
                    X = 1e-20
                    G = 1e-20
                    B = 1e-20
                    rate = 0
                else:
                    Sbase = circuit.Sbase

                    Zbase = (Vnom * Vnom) / Sbase
                    Ybase = 1.0 / Zbase

                    # at this point r, x, g, b are the complete values for all the line length
                    R = r / Zbase
                    X = x / Zbase
                    G = g / Ybase
                    B = b / Ybase

                    if len(elm.current_limit) > 0:
                        rate = float(elm.current_limit[0].properties['value']) * Vnom * sqrt(3)
                    else:
                        rate = 0

                # create AcLineSegment (Line)
                line = gcdev.Line(idtag=rfid2uuid(elm.rfid),
                                  bus_from=B1,
                                  bus_to=B2,
                                  name=name,
                                  r=R,
                                  x=X,
                                  b=B,
                                  rate=rate,
                                  active=True,
                                  mttf=0,
                                  mttr=0,
                                  template=template)

                circuit.add_line(line)

                # add class to recognised objects
                recognised.add(elm.tpe)

    def parse_power_transformer(self, cim: CIMCircuit, circuit: MultiCircuit, T_dict: Dict, recognised: Set):
        """

        :param cim:
        :param circuit:
        :param T_dict:
        :param recognised:
        :return:
        """
        if 'PowerTransformer' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['PowerTransformer']:

                name = elm.properties['name']

                if len(elm.windings) == 2:

                    if len(elm.windings[0].get_terminals()) > 0:
                        T1 = T_dict[elm.windings[0].get_terminals()[0].rfid]
                        T2 = T_dict[elm.windings[1].get_terminals()[0].rfid]
                    elif len(elm.get_terminals()) == 2:
                        term = elm.get_terminals()
                        T1 = T_dict[term[0].rfid]
                        T2 = T_dict[term[1].rfid]
                    else:
                        self.logger.add_error('Incorrect number of terminals', elm.rfid, len(elm.windings[0].get_terminals()))
                        continue

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
                        try:
                            r = float(elm.windings[i].properties['r'])
                            x = float(elm.windings[i].properties['x'])
                        except KeyError:
                            r = 0
                            x = 0
                            self.logger.add_error('No impedance components', elm.windings[i].rfid)

                        try:
                            g = float(elm.windings[i].properties['g'])
                            b = float(elm.windings[i].properties['b'])
                        except KeyError:
                            g = 0
                            b = 0
                            self.logger.add_error('No shunt components ', elm.windings[i].rfid)

                        try:
                            r0 = float(elm.windings[i].properties['r0'])
                            x0 = float(elm.windings[i].properties['x0'])
                            g0 = float(elm.windings[i].properties['g0'])
                            b0 = float(elm.windings[i].properties['b0'])
                        except KeyError:
                            r0 = 0
                            x0 = 0
                            g0 = 0
                            b0 = 0
                            self.logger.add_error('No zero sequence components', elm.rfid)

                        try:
                            S = float(elm.windings[i].properties['ratedS'])
                        except KeyError:
                            self.logger.add_error('No ratedS', elm.windings[i].rfid)
                            S = 1.0

                        RATE += S

                        try:
                            V = float(elm.windings[i].properties['ratedU'])
                        except KeyError:
                            self.logger.add_error('No ratedU', elm.windings[i].rfid)
                            try:
                                V = float(elm.windings[i].base_voltage[0].properties['nominalVoltage'])
                            except KeyError:
                                self.logger.add_error('No voltage', elm.windings[i].rfid)
                                V = 1.0

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

                    # sum the taps
                    tap_m = taps[0] * taps[1]

                    line = gcdev.Transformer2W(idtag=rfid2uuid(elm.rfid),
                                               bus_from=B1,
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
                                               mttr=0)

                    circuit.add_branch(line)
                else:
                    self.logger.add_error('Does not have 2 windings associated', elm.tpe + ':' + name)

                # add class to recognised objects
                recognised.add(elm.tpe)

    def parse_switches(self, cim: CIMCircuit, circuit: MultiCircuit, T_dict: Dict, recognised: Set, EPS):
        """

        :param cim:
        :param circuit:
        :param T_dict:
        :param recognised:
        :param EPS:
        :return:
        """
        cim_switches = ['Switch', 'Disconnector', 'Breaker', 'LoadBreakSwitch']
        if any_in_dict(cim.elements_by_type, cim_switches):
            for elm in get_elements(cim.elements_by_type, cim_switches):
                term = elm.get_terminals()
                if len(term) == 2:
                    T1 = T_dict[term[0].rfid]
                    T2 = T_dict[term[1].rfid]
                    B1 = self.terminal_node[T1][0]
                    B2 = self.terminal_node[T2][0]
                else:
                    self.logger.add_error('Incorrect number of terminals', elm.rfid, len(term))
                    continue

                if 'name' in elm.properties:
                    name = elm.properties['name']
                else:
                    name = 'Some switch'

                if 'open' in elm.properties:
                    state = not bool(elm.properties['open'])
                else:
                    state = True

                line = gcdev.Branch(idtag=rfid2uuid(elm.rfid),
                                    bus_from=B1,
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
                                    branch_type=gcdev.BranchType.Switch)

                circuit.add_branch(line)

                # add class to recognised objects
                recognised.add(elm.tpe)

    def parse_loads(self, cim: CIMCircuit, circuit: MultiCircuit, T_dict: Dict, recognised: Set):
        """

        :param cim:
        :param circuit:
        :param T_dict:
        :param recognised:
        :return:
        """
        cim_loads = ['ConformLoad', 'EnergyConsumer', 'NonConformLoad']
        if any_in_dict(cim.elements_by_type, cim_loads):
            for elm in get_elements(cim.elements_by_type, cim_loads):
                term = elm.get_terminals()
                if len(term) > 0:
                    T1 = T_dict[term[0].rfid]
                    B1 = self.terminal_node[T1][0]

                    # Active and reactive power values

                    if elm.tpe == 'ConformLoad':
                        if len(elm.load_response_characteristics) > 0:
                            p = float(elm.load_response_characteristics[0].properties['pConstantPower'])
                            q = float(elm.load_response_characteristics[0].properties['qConstantPower'])
                            name = elm.load_response_characteristics[0].properties['name']
                        else:
                            p, q = self.try_properties(elm.properties, ['pfixed', 'qfixed'])
                            try:
                                name = elm.properties['name']
                            except KeyError:
                                name = 'ConformLoad@{}'.format(B1.name)

                    elif elm.tpe == 'NonConformLoad':
                        if len(elm.load_response_characteristics) > 0:
                            p = float(elm.load_response_characteristics[0].properties['pConstantPower'])
                            q = float(elm.load_response_characteristics[0].properties['qConstantPower'])
                            name = elm.load_response_characteristics[0].properties['name']
                        else:
                            p, q = self.try_properties(elm.properties, ['pfixed', 'qfixed'])
                            try:
                                name = elm.properties['name']
                            except KeyError:
                                name = 'NonConformLoad@{}'.format(B1.name)

                    else:
                        p = self.try_properties(elm.properties, ['pfixed'])[0]
                        q = 0
                        name = 'Some load'

                    load = gcdev.Load(idtag=rfid2uuid(elm.rfid),
                                      name=name,
                                      G=0,
                                      B=0,
                                      Ir=0,
                                      Ii=0,
                                      P=p if p is not None else 0,
                                      Q=q if q is not None else 0)
                    circuit.add_load(B1, load)

                    # add class to recognised objects
                    recognised.add(elm.tpe)
                else:
                    self.logger.add_error('Incorrect number of terminals', elm.rfid, len(term))

    def parse_shunts(self, cim: CIMCircuit, circuit: MultiCircuit, T_dict: Dict, recognised: Set):
        """

        :param cim:
        :param circuit:
        :param T_dict:
        :param recognised:
        :return:
        """
        if 'ShuntCompensator' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['ShuntCompensator']:
                term = elm.get_terminals()
                if len(term) > 0:
                    T1 = T_dict[term[0].rfid]
                    B1 = self.terminal_node[T1][0]

                    prop_lst = ['gPerSection', 'bPerSection', 'g0PerSection', 'b0PerSection']
                    prop_def = [0.0, 0.0, 0.0, 0.0]
                    g, b, g0, b0 = self.try_properties(elm.properties, prop_lst, prop_def)

                    try:
                        name = elm.properties['name']
                    except KeyError:
                        name = 'ShuntCompensator@{}'.format(B1.name)

                    # self.add_shunt(Shunt(name, T1, g, b, g0, b0))

                    sh = gcdev.Shunt(idtag=rfid2uuid(elm.rfid),
                                     name=name,
                                     G=g,
                                     B=b)
                    circuit.add_shunt(B1, sh)

                    # add class to recognised objects
                    recognised.add(elm.tpe)
                else:
                    self.logger.add_error('Incorrect number of terminals', elm.rfid, len(term))

    def parse_generators(self, cim: CIMCircuit, circuit: MultiCircuit, T_dict: Dict, recognised: Set):
        """

        :param cim:
        :param circuit:
        :param T_dict:
        :param recognised:
        :return:
        """
        if 'SynchronousMachine' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['SynchronousMachine']:
                term = elm.get_terminals()
                if len(term) > 0:
                    T1 = T_dict[term[0].rfid]
                    B1 = self.terminal_node[T1][0]

                    # nominal voltage and set voltage
                    if len(elm.base_voltage) > 0:
                        try:
                            Vnom = float(elm.get_base_voltage().properties['nominalVoltage'])
                        except KeyError:
                            Vnom = 1.0
                            self.logger.add_error('no nominalVoltage property', elm.rfid)
                    else:
                        try:
                            Vnom = float(elm.properties['ratedU'])
                        except KeyError:
                            Vnom = 1.0
                            self.logger.add_error('no ratedU property', elm.rfid)

                    try:
                        Vset = float(elm.regulating_control[0].properties['targetValue'])
                    except KeyError:
                        Vset = Vnom
                    except IndexError:
                        Vset = Vnom

                    if Vnom <= 0:
                        # p.u. set voltage for the model
                        vset = 1.0
                    else:
                        # p.u. set voltage for the model
                        vset = Vset / Vnom

                    # active power
                    if len(elm.generating_unit) > 0:
                        try:
                            p = float(elm.generating_unit[0].properties['initialP'])
                        except KeyError:
                            self.logger.add_error('No active power initialP value', elm.rfid)
                            p = 0.0
                    else:
                        try:
                            p = float(elm.properties['p'])
                        except KeyError:
                            p = 0.0
                            self.logger.add_error('No active power p value', elm.rfid)

                    try:
                        name = elm.properties['name']
                    except KeyError:
                        name = 'Generator@{}'.format(B1.name)

                    gen = gcdev.Generator(idtag=rfid2uuid(elm.rfid),
                                          name=name,
                                          active_power=p,
                                          voltage_module=vset)
                    circuit.add_generator(B1, gen)

                    # add class to recognised objects
                    recognised.add(elm.tpe)
                else:
                    self.logger.add_error('Incorrect number of terminals', elm.rfid, len(term))

    def parse_slacks(self, cim: CIMCircuit, circuit: MultiCircuit, T_dict: Dict, recognised: Set):
        """

        :param cim:
        :param circuit:
        :param T_dict:
        :param recognised:
        :return:
        """
        cim_slack = ['EquivalentNetwork', 'EquivalentInjection']
        if any_in_dict(cim.elements_by_type, cim_slack):
            for elm in get_elements(cim.elements_by_type, cim_slack):
                term = elm.get_terminals()
                if len(term) > 0:
                    T1 = T_dict[term[0].rfid]
                    try:
                        B1 = self.terminal_node[T1][0]
                        B1.is_slack = True
                    except KeyError:
                        self.logger.add_error('Missing node from terminal', T1.rfid)
                else:
                    self.logger.add_error('Incorrect number of terminals', elm.rfid, len(term))

    def load_cim_file(self, cim_files):
        """
        Load CIM file
        :param cim_files: list of CIM files (.xml)
        """

        # declare GridCal circuit
        circuit = MultiCircuit()
        EPS = 1e-16

        # declare CIM circuit to process the file(s)
        self.cim = CIMCircuit(text_func=self.text_func, progress_func=self.progress_func, logger=self.logger)

        # import the cim files' content into a dictionary
        data = read_cim_files(cim_files)

        lst2 = sort_cim_files(list(data.keys()))
        # Parse the files
        for f in lst2:
            name, file_extension = os.path.splitext(f)
            self.emit_text('Parsing xml structure of ' + name)

            self.cim.parse_xml_text(text_lines=data[f])

        # replace CIM references in the CIM objects
        self.emit_text('Looking for references')
        self.cim.find_references()

        return circuit


if __name__ == '__main__':
    import os
    from GridCal.Engine import FileOpen, FileSave

    # folder = r'C:\Users\penversa\Documents\Grids\CGMES'
    # # folder = '/home/santi/Documentos/Private_Grids/CGMES'
    #
    # cimfiles = ['20210203T1830Z_2D_REN_EQ_001.xml',
    #             '20210203T1830Z_2D_REN_TP_001.xml',
    #             '20210203T1830Z_2D_REN_SV_001.xml']
    # cimfiles = [os.path.join(folder, f) for f in cimfiles]
    #
    # boundary_profiles = [
    #                      '20200301T0000Z__ENTSOE_EQBD_001.xml',
    #                      '20200301T0000Z__ENTSOE_TPBD_001.xml']
    # boundary_profiles = [os.path.join(folder, f) for f in boundary_profiles]
    #
    # fnames = cimfiles + boundary_profiles

    folder = r'C:\Users\penversa\Documents\Grids\CGMES\TYNDP_2025'

    files = [
             # '2025NT_FR_model_004.zip',
             '2025NT_ES_model_003.zip',
             # '2025NT_PT_model_003.zip',
             '20191017T0918Z_ENTSO-E_BD_1130.zip'
             ]
    fnames = [os.path.join(folder, f) for f in files]

    print('Reading...')
    # file_open = FileOpen(fnames)
    # grid = file_open.open()
    # FileSave(grid, os.path.join(folder, '20210203T1830Z_2D_REN.gridcal')).save()

    parser = CIMImport(text_func=print)
    parser.load_cim_file(fnames)
    parser.cim.to_excel('Spain_data.xlsx')
