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
import chardet
import pandas as pd
from math import sqrt
from typing import Set, Dict, List, Tuple
from GridCal.Engine.IO.cim.cim_enums import *


def rfid2uuid(val):
    return val.replace('-', '').replace('_', '')


def index_find(string, start, end):
    """
    version of substring that matches
    :param string: string
    :param start: string to start splitting
    :param end: string to end splitting
    :return: string between start and end
    """
    return string.partition(start)[2].partition(end)[0]


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


class CimContainer:

    def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
        """
        General CIM object container
        :param rdfid: RFID
        :param tpe: type of the object (class)
        """

        # store the object type
        self.tpe = tpe

        # pick the object id
        self.rdfid = rdfid
        self.uuid = rfid2uuid(rdfid)

        self.class_replacements: Dict = class_replacements
        self.resources: List = resources

        # dictionary of properties read from the xml
        self.parsed_properties = dict()

        # dictionary of objects that reference this object
        self.references_to_me = dict()

        self.missing_references = dict()

        self.name = ''
        self.shortName = ''
        self.description = ''
        self.energyIdentCodeEic = ''

    def __repr__(self):
        return self.rdfid

    def __hash__(self):
        # alternatively, return hash(repr(self))
        return int(self.uuid, 16)  # hex string to int

    def __lt__(self, other):
        return self.__hash__() < other.__hash__()

    def __eq__(self, other):
        return self.rdfid == other.rdfid

    def add_reference(self, obj: "CimContainer"):
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
                self.parsed_properties[prop] = val

                if hasattr(self, prop):
                    setattr(self, prop, str2num(val))

    def merge(self, other: "CimContainer", overwrite=True):
        """
        Merge the properties of this object with another
        :param other: GeneralContainer instance
        :param overwrite: Overwrite existing values with new values
        """
        for prop, value in other.parsed_properties.items():
            if overwrite:
                self.parsed_properties[prop] = value
            else:
                if prop not in self.parsed_properties:
                    self.parsed_properties[prop] = value

    def print(self):
        print('Type:' + self.tpe)
        print('Id:' + self.rdfid)

        for key, val in self.parsed_properties.items():
            if type(val) == CimContainer:
                for key2, val2 in val.parsed_properties.items():
                    print(key, '->', key2, ':', val2)
            else:
                print(key, ':', val)

    def __str__(self):
        return self.tpe + ':' + self.rdfid

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
        xml = l1 + '<cim:' + self.tpe + ' rdf:ID="' + self.rdfid + '">\n'

        # properties
        for prop, value in self.parsed_properties.items():
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

    def get_dict(self) -> Dict[str, any]:
        """
        Get dictionary with the data
        :return: Dictionary
        """
        return {'rfid': self.rdfid,
                'uuid': self.uuid,
                'name': self.name}

    def get_all_properties(self) -> List[str]:
        """
        Get the list of properties of this object
        """
        res = list()
        for prop_name, value in vars(self).items():
            obj = getattr(self, prop_name)
            T = type(obj)
            if T not in [list, dict]:
                res.append(prop_name)
        return res

    def list_not_implemented_properties(self):
        """
        This function lists all the properties that have not been implemented for this object
        This is possible because self.parsed_properties stores whatever it was read for this object
        while this object may or may not have those properties implemented
        """
        lst = list()
        for prop, rea_value in self.parsed_properties.items():
            if not hasattr(self, prop):
                lst.append(prop)
        return lst

    def detect_circular_references(self, visited_ids=list()):

        visited = [i for i in visited_ids]
        visited.append(self.rdfid)

        for prop in self.get_all_properties():

            value = getattr(self, prop)

            if hasattr(value, 'rdfid'):
                if value.rdfid in visited:
                    return True, visited
                else:
                    value.detect_circular_references(visited_ids=visited)
            else:
                pass

        return False, visited


class MonoPole(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

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


class DiPole(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.aggregate: bool = False

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


class BaseVoltage(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.nominalVoltage = 0


class Terminal(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.TopologicalNode: TopologicalNode = None
        self.ConductingEquipment = None  # pointer to the Bus
        self.name = ''
        self.phases = ''
        self.connected: bool = True

        self.sequenceNumber: int = 0

    def get_voltage(self):
        """
        Get the voltage of this terminal
        :return: Voltage or None
        """
        if self.TopologicalNode is not None:
            return self.TopologicalNode.get_voltage()
        else:
            return None


class ConnectivityNode(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.TopologicalNode = None
        self.ConnectivityNodeContainer = None
        self.name = ''
        self.shortName = ''
        self.description = ''
        self.fromEndName = ''
        self.fromEndNameTso = ''
        self.fromEndIsoCode = ''
        self.toEndName = ''
        self.toEndNameTso = ''
        self.toEndIsoCode = ''
        self.boundaryPoint = ''


class TopologicalNode(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.BaseVoltage = None
        self.ConnectivityNodeContainer = None
        self.description = ''
        self.shortName = ''
        self.boundaryPoint = ''
        self.fromEndIsoCode = ''
        self.fromEndName = ''
        self.fromEndNameTso = ''
        self.toEndIsoCode = ''
        self.toEndName = ''
        self.toEndNameTso = ''
        self.ConnectivityNodeContainer = ''
        self.BaseVoltage = None
        self.ResourceOwner = None

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


class BusbarSection(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.EquipmentContainer = None
        self.BaseVoltage: BaseVoltage = None

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


class Substation(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.name = ''
        self.Region = None


class OperationalLimitSet(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.name = ''
        self.Terminal: Terminal = None
        self.Equipment = None


class OperationalLimitType(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.name = ''
        self.limitType = ''
        self.direction = ''
        self.acceptableDuration: float = 0


class GeographicalRegion(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)



class SubGeographicalRegion(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.Region = None


class VoltageLevel(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.Substation = None
        self.BaseVoltage = None
        self.highVoltageLimit = 0
        self.lowVoltageLimit = 0


class VoltageLimit(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.OperationalLimitType: OperationalLimitType = None
        self.OperationalLimitSet: OperationalLimitSet = None
        self.value = 0


class CurrentLimit(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.OperationalLimitType = None
        self.OperationalLimitSet = None
        self.value = 0


class EquivalentNetwork(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)


class ControlArea(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.type: str = ''
        self.netInterchange: float = 0.0
        self.pTolerance: float = 0.0


class EquivalentInjection(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.regulationCapability = False
        self.BaseVoltage = None
        self.EquipmentContainer = None
        self.name = ''
        self.p = 0
        self.q = 0


class Breaker(DiPole):

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)

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

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)

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


class LoadBreakSwitch(DiPole):

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)

        self.normalOpen = True
        self.retained = True
        self.EquipmentContainer = None
        self.open = False
        self.description = ''
        self.aggregate = False
        self.name = ''

        self.aor = ''

        self.serviceState = ''
        self.PSRType = ''
        self.underground = True
        self.Circuit = ''
        self.costPerUnit = 0
        self.manufacturer = ''
        self.model = ''
        self.private = False
        self.failureRate = 0
        self.importance = ""
        self.ratedVoltage = 11000
        self.access = ""
        self.extendedStatus = ""
        self.isolating = True
        self.mechanism = ""
        self.normalOpen = True
        self.ratedCurrent = 0
        self.breakingCapacity = 0
        self.shortTermCurrent = 0

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


class Line(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)
        self.description = ''
        self.shortName = ''
        self.Region = None


class ACLineSegment(DiPole):

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)

        self.BaseVoltage: BaseVoltage = None
        self.current_limit = None
        self.bch = 0
        self.gch = 0
        self.r = 0
        self.x = 0
        self.aggregate: str = ''

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

    def get_rate(self):
        return 1e-20

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


class PowerTransformerEnd(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

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
        self.phaseAngleClock = ''

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

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)

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
            windings = self.get_windings()

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

    def get_rate(self):

        rating = 0
        for winding in self.get_windings():
            if winding.ratedS > rating:
                rating = winding.ratedS

        return rating

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


class Winding(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.tap_changers = list()


class EnergyConsumer(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.LoadResponse = None
        self.EquipmentContainer = None
        self.name = ''
        self.p = 0
        self.q = 0


class ConformLoad(MonoPole):

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

        self.LoadGroup: LoadGroup = None
        self.LoadResponse: LoadResponseCharacteristic = None
        self.EquipmentContainer = None
        self.p = 0
        self.q = 0

        self.BaseVoltage: BaseVoltage = None

    def get_dict(self):

        d = super().get_dict()
        d['p'] = self.p
        d['q'] = self.q

        return d

    def get_pq(self):
        return self.p, self.q


class NonConformLoad(MonoPole):

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

        self.name = ''
        self.EquipmentContainer = None
        self.LoadResponse = None
        self.LoadGroup = None

        self.BaseVoltage: BaseVoltage = None

        self.p: float = 0
        self.q: float = 0

    def get_pq(self):
        return 0, 0


class NonConformLoadGroup(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.name = ''


class LoadGroup(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.name = ''


class LoadResponseCharacteristic(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.exponentModel: bool = True
        self.pVoltageExponent: float = 0
        self.qVoltageExponent: float = 0

        self.pConstantCurrent: float = 0
        self.pConstantImpedance: float = 0
        self.pConstantPower: float = 0
        self.qConstantCurrent: float = 0
        self.qConstantImpedance: float = 0
        self.qConstantPower: float = 0


class RegulatingControl(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.mode: RegulatingControlModeKind = RegulatingControlModeKind.voltage
        self.Terminal = None
        self.discrete = False
        self.enabled = True
        self.targetDeadband = 0
        self.targetValue = 0
        self.targetValueUnitMultiplier = ''


class RatioTapChanger(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

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
        self.TapChangerControl: TapChangerControl = None
        self.name = ''
        self.controlEnabled = True
        self.step = 0


class GeneratingUnit(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

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

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

        self.aggregate: str = ''
        self.qPercent: float = 0
        self.type = ''
        self.InitialReactiveCapabilityCurve = None
        self.ratedS: float = 0
        self.ratedPowerFactor: float = 1
        self.GeneratingUnit = None
        self.RegulatingControl = None
        self.EquipmentContainer = None
        self.operatingMode = ''
        self.referencePriority = ''
        self.p = 0
        self.q = 0
        self.r = 0
        self.controlEnabled = True
        self.maxQ: float = 0
        self.minQ: float = 0

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


class HydroGenerationUnit(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

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


class HydroPowerPlant(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

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

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

        self.name = ''
        self.EquipmentContainer = None
        self.bPerSection: float = 0
        self.gPerSection: float = 0
        self.maximumSections: int = 0
        self.nomU: float = 0
        self.normalSections: int = 0
        self.controlEnabled: bool = False
        self.RegulatingControl = None
        self.sections: int = 0

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

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

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
        self.normalPF = 0

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


class RatioTapChangerTable(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.name = ''


class RatioTapChangerTablePoint(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

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


class ReactiveCapabilityCurve(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.name = ''
        self.curveStyle = ''
        self.xUnit = ''
        self.y1Unit = ''
        self.y2Unit = ''


class StaticVarCompensator(MonoPole):

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

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


class TapChangerControl(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.name = ''
        self.Terminal = None
        self.mode = ''

        self.discrete: bool = True
        self.enabled: bool = True

        self.targetDeadband: float = 0
        self.targetValue: float = 0
        self.targetValueUnitMultiplier = ''


class ThermalGenerationUnit(MonoPole):

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

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

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

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


class FullModel(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

        self.scenarioTime = ''
        self.created = ''
        self.version = ''
        self.profile = ''
        self.modelingAuthoritySet = ''
        self.DependentOn = ''
        self.longDependentOnPF = ''

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


class TieFlow(CimContainer):

    def __init__(self, rdfid, tpe):
        CimContainer.__init__(self, rdfid, tpe)

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

