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
import datetime
import numpy as np
from typing import Dict, List, Tuple
from GridCalEngine.IO.cim.cim16.cim_enums import cgmesProfile
from GridCalEngine.IO.base.units import UnitSymbol, UnitMultiplier
import GridCalEngine.IO.cim.cim16.cim_enums as cim_enums
from GridCalEngine.basic_structures import Logger
from GridCalEngine.data_logger import DataLogger


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


class CimProperty:

    def __init__(self, name: str,
                 class_type: object,
                 multiplier: UnitMultiplier = UnitMultiplier.none,
                 unit: UnitSymbol = UnitSymbol.none,
                 description: str = '',
                 max_chars=65536,
                 mandatory=False,
                 comment='',
                 out_of_the_standard=False):
        """
        CIM property for soft type checking
        :param name: name of the property
        :param class_type: class type (actual python object)
        :param multiplier: UnitMultiplier from CIM
        :param unit: UnitSymbol from CIM
        :param description: property description
        :param max_chars: maximum number of characters (only for strings)
        :param mandatory: is this property mandatory when parsing?
        :param comment: Extra comments
        """
        self.property_name = name
        self.class_type = class_type
        self.multiplier = multiplier
        self.unit = unit
        self.description = description
        self.max_chars = max_chars
        self.mandatory = mandatory
        self.comment = comment
        self.out_of_the_standard = out_of_the_standard

    def get_unit(self):
        if self.multiplier == UnitMultiplier.none and self.unit == UnitSymbol.none:
            return ""
        elif self.multiplier == UnitMultiplier.none and self.unit != UnitSymbol.none:
            return self.unit.value
        elif self.multiplier != UnitMultiplier.none and self.unit == UnitSymbol.none:
            return self.multiplier.value  # this should be wrong...
        elif self.multiplier != UnitMultiplier.none and self.unit != UnitSymbol.none:
            return self.multiplier.value + self.unit.value
        else:
            return ""

    def get_class_name(self):
        tpe_name = str(self.class_type)
        if '.' in tpe_name:
            chunks = tpe_name.split('.')
            return chunks[-1].replace("'", "") \
                .replace("<", "") \
                .replace(">", "").strip()
        else:
            return tpe_name.replace('class', '') \
                .replace("'", "") \
                .replace("<", "") \
                .replace(">", "").strip()

    def get_dict(self):

        return {'name': self.property_name,
                'class_type': self.get_class_name(),
                'unit': self.get_unit(),
                'mandatory': self.mandatory,
                'max_chars': self.max_chars,
                "descriptions": self.description,
                'comment': self.comment}


class IdentifiedObject:

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

        """
        CGMES is split in several files, because why make it simple right?
        So, in each file type we put some of each object's properties.
        Hence this dictionary, that serves for the registration of the 
        different properties and where each one goes.
        """
        self.possibleProfileList = {'class': [cgmesProfile.TP_BD.value, cgmesProfile.EQ.value, cgmesProfile.TP.value,
                                              cgmesProfile.EQ_BD.value, ], }

        # dictionary of properties read from the xml
        self.parsed_properties = dict()

        # dictionary of objects that reference this object
        self.references_to_me = dict()

        # dictionary of missing references (those provided but not used)
        self.missing_references = dict()

        self.name = ''
        self.shortName = ''
        self.description = ''
        self.energyIdentCodeEic = ''
        self.aggregate: bool = False

        # document followed for the implementation
        self.standard_document = '57_1816e_DTS.pdf'

        # register the CIM properties
        self.declared_properties: Dict[str, CimProperty] = dict()
        self.register_property(name='rdfid',
                               class_type=str,
                               description="Master resource identifier issued by a model "
                                           "authority. The mRID is globally unique within an "
                                           "exchange context. Global uniqueness is easily "
                                           "achieved by using a UUID, as specified in RFC "
                                           "4122, for the mRID. The use of UUID is strongly "
                                           "recommended.", )

        self.register_property(name='name',
                               class_type=str,
                               description='The name is any free human readable and '
                                           'possibly non unique text naming the object.')

        self.register_property(name='shortName',
                               class_type=str,
                               description='The attribute is used for an exchange of a '
                                           'human readable short name with length of the '
                                           'string 12 characters maximum.', max_chars=12)

        self.register_property(name='description',
                               class_type=str,
                               description="The attribute is used for an exchange of the "
                                           "EIC code (Energy identification Code). "
                                           "The length of the string is 16 characters as "
                                           "defined by the EIC code.")

        self.register_property(name='energyIdentCodeEic',
                               class_type=str,
                               description='The attribute is used for an exchange '
                                           'of the EIC code (Energy identification '
                                           'Code). The length of the string is 16 '
                                           'characters as defined by the EIC code.',
                               max_chars=16)

        self.register_property(name='aggregate', class_type=bool, description='Agregate identifier')

    def __repr__(self):
        return self.rdfid

    def __hash__(self):
        # alternatively, return hash(repr(self))
        return int(self.uuid, 16)  # hex string to int

    def __lt__(self, other):
        return self.__hash__() < other.__hash__()

    def __eq__(self, other):
        return self.rdfid == other.rdfid

    def check(self, logger: Logger):
        """
        Check specific OCL rules
        :param logger: Logger instance
        :return: true is ok false otherwise
        """
        return True

    def register_property(self, name: str,
                          class_type: object,
                          multiplier: UnitMultiplier = UnitMultiplier.none,
                          unit: UnitSymbol = UnitSymbol.none,
                          description: str = '',
                          max_chars=65536,
                          mandatory=False,
                          comment='',
                          out_of_the_standard=False):
        """
        Shortcut to add properties
        :param name: name of the property
        :param class_type: class type (actual python object)
        :param multiplier: UnitMultiplier from CIM
        :param unit: UnitSymbol from CIM
        :param description: property description
        :param max_chars: maximum number of characters (only for strings)
        :param mandatory: is this property mandatory when parsing?
        :param comment: Extra comments
        """
        self.declared_properties[name] = CimProperty(
            name=name,
            class_type=class_type,
            multiplier=multiplier,
            unit=unit,
            description=description,
            max_chars=max_chars,
            mandatory=mandatory,
            comment=comment,
            out_of_the_standard=out_of_the_standard)

    def get_properties(self) -> List[CimProperty]:
        return [p for name, p in self.declared_properties.items()]

    def add_reference(self, obj: "IdentifiedObject"):
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

    def merge(self, other: "IdentifiedObject", overwrite=True):
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
            if type(val) == IdentifiedObject:
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
        res = dict()
        for property_name, cim_prop in self.declared_properties.items():
            res[property_name] = getattr(self, property_name)

        return res

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


class MonoPole(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

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


class DiPole(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

    def get_topological_nodes(self) -> tuple[None, None]:
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

    def get_nodes(self) -> tuple[None, None]:
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


class BaseVoltage(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.nominalVoltage: float = 0.0

        self.register_property(name='nominalVoltage',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="The power system resource's base voltage.")

        self.possibleProfileList |= {'class': [cgmesProfile.TP_BD.value, cgmesProfile.EQ.value, cgmesProfile.TP.value,
                                               cgmesProfile.EQ_BD.value, ],
                                     'TopologicalNode': [cgmesProfile.TP_BD.value, cgmesProfile.TP.value, ],
                                     'nominalVoltage': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     'ConductingEquipment': [cgmesProfile.EQ.value, ],
                                     'VoltageLevel': [cgmesProfile.EQ.value, ],
                                     'TransformerEnds': [cgmesProfile.EQ.value, ]}


class EquipmentContainer(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)


class PowerSystemResource(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        # self.Controls = Controls
        # self.Measurements = Measurements
        # self.Location = Location


class Equipment(PowerSystemResource):

    def __init__(self, rdfid, tpe):
        PowerSystemResource.__init__(self, rdfid, tpe)

        self.aggregate: bool = False
        self.EquipmentContainer: EquipmentContainer = None
        self.OperationalLimitSet: OperationalLimitSet = None

        self.register_property(name='aggregate',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="aggregate")

        self.register_property(name='EquipmentContainer',
                               class_type=EquipmentContainer,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="EquipmentContainer")

        self.register_property(name='OperationalLimitSet',
                               class_type=OperationalLimitSet,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="OperationalLimitSet")

        self.possibleProfileList |= {
            'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.DY.value, cgmesProfile.EQ_BD.value, ],
            'aggregate': [cgmesProfile.EQ.value, ],
            'EquipmentContainer': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
            'OperationalLimitSet': [cgmesProfile.EQ.value, ],
        }


class ConductingEquipment(Equipment):

    def __init__(self, rdfid, tpe):
        Equipment.__init__(self, rdfid, tpe)

        self.BaseVoltage: BaseVoltage = None
        self.Terminals: List[Terminal] = list()
        # self.SvStatus = SvStatus

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="BaseVoltage")

        self.possibleProfileList |= {
            'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.DY.value, cgmesProfile.EQ_BD.value, ],
            'aggregate': [cgmesProfile.EQ.value, ],
            'EquipmentContainer': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
            'OperationalLimitSet': [cgmesProfile.EQ.value, ],
        }


class BusNameMarker(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.priority: int = 0

        self.register_property(name='priority',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Priority of bus name marker for use as "
                                           "topology bus name. Use 0 for don t care. Use "
                                           "1 for highest priority. Use 2 as priority is "
                                           "less than 1 and so on.")

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'priority': [cgmesProfile.EQ.value, ],
                                     'ReportingGroup': [cgmesProfile.EQ.value, ],
                                     'Terminal': [cgmesProfile.EQ.value, ],
                                     }


class ACDCTerminal(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.connected: bool = True
        self.BusNameMarker: BusNameMarker = None
        # self.Measurements = Measurements
        self.sequenceNumber = 0
        self.OperationalLimitSet: OperationalLimitSet = None

        self.possibleProfileList |= {
            'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.DY.value, cgmesProfile.TP.value,
                      cgmesProfile.SV.value, ],
            'connected': [cgmesProfile.SSH.value, ],
            'BusNameMarker': [cgmesProfile.EQ.value, ],
            'Measurements': [cgmesProfile.EQ.value, ],
            'sequenceNumber': [cgmesProfile.EQ.value, ],
            'OperationalLimitSet': [cgmesProfile.EQ.value, ],
        }

        self.register_property(name='connected',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        self.register_property(name='BusNameMarker',
                               class_type=BusNameMarker,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment="No explanation given by the standard")

        self.register_property(name='sequenceNumber',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        self.register_property(name='OperationalLimitSet',
                               class_type=OperationalLimitSet,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="OperationalLimitSet")


class Terminal(ACDCTerminal):

    def __init__(self, rdfid, tpe):
        ACDCTerminal.__init__(self, rdfid, tpe)

        self.phases: cim_enums.PhaseCode = cim_enums.PhaseCode.ABC
        self.sequenceNumber: int = 0

        # self.connected: bool = True
        self.TopologicalNode: TopologicalNode = None

        self.ConnectivityNode: ConnectivityNode = None
        self.ConductingEquipment: IdentifiedObject = None  # pointer to the Bus (use instead of TopologicalNode?)
        # self.BusNameMarker: BusNameMarker = None

        self.possibleProfileList |= {
            'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.DY.value, cgmesProfile.TP.value,
                      cgmesProfile.EQ_BD.value, cgmesProfile.SV.value, ],
            'ConverterDCSides': [cgmesProfile.EQ.value, ],
            'ConductingEquipment': [cgmesProfile.EQ.value, cgmesProfile.DY.value, cgmesProfile.EQ_BD.value, ],
            'ConnectivityNode': [cgmesProfile.EQ.value, ],
            'phases': [cgmesProfile.EQ.value, ],
            'HasFirstMutualCoupling': [cgmesProfile.EQ.value, ],
            'HasSecondMutualCoupling': [cgmesProfile.EQ.value, ],
            'RegulatingControl': [cgmesProfile.EQ.value, ],
            'TieFlow': [cgmesProfile.EQ.value, ],
            'TransformerEnd': [cgmesProfile.EQ.value, ],
            'RemoteInputSignal': [cgmesProfile.DY.value, ],
            'TopologicalNode': [cgmesProfile.TP.value, ],
            'SvPowerFlow': [cgmesProfile.SV.value, ],
        }

        self.register_property(name='phases',
                               class_type=cim_enums.PhaseCode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Represents the normal network phasing condition. "
                                           "If the attribute is missing three phases (ABC or "
                                           "ABCN) shall be assumed. Primarily used for the PetersonCoil model.")

        self.register_property(name='sequenceNumber',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The orientation of the terminal "
                                           "connections for a multiple terminal "
                                           "conducting equipment. The sequence "
                                           "numbering starts with 1 and additional "
                                           "terminals should follow in increasing "
                                           "order. The first terminal is the "
                                           "'starting point' for a two terminal "
                                           "branch.")

        self.register_property(name='TopologicalNode',
                               class_type=TopologicalNode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment="Out of the standard. "
                                       "Should use ConductingEquipment instead")

        self.register_property(name='ConnectivityNode',
                               class_type=ConnectivityNode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment="Terminals interconnected with zero "
                                       "impedance at a this connectivity node.",
                               mandatory=True)

        self.register_property(name='ConductingEquipment',
                               class_type=IdentifiedObject,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The conducting equipment of the "
                                           "terminal. Conducting equipment have "
                                           "terminals that may be connected to "
                                           "other conducting equipment terminals"
                                           " via connectivity nodes or "
                                           "topological nodes.",
                               mandatory=True)

    def get_voltage(self):
        """
        Get the voltage of this terminal
        :return: Voltage or None
        """
        if self.TopologicalNode is not None:
            return self.TopologicalNode.get_voltage()
        else:
            return None

    def check(self, logger: Logger):
        """

        :param logger:
        :return:
        """

        """
        OCL constraint:Sequence Number is required for EquivalentBranch and ACLineSegments with MutualCoupling
        """

        # TODO: exceedingly hard to check: must know the sequence of concatenated AcLineSegment that do not have branching
        pass


class ConnectivityNodeContainer(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.possibleProfileList |= {'class': [cgmesProfile.TP_BD.value, cgmesProfile.EQ.value, cgmesProfile.TP.value,
                                               cgmesProfile.EQ_BD.value, ],
                                     'TopologicalNode': [cgmesProfile.TP_BD.value, cgmesProfile.TP.value, ],
                                     'ConnectivityNodes': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     }


class ConnectivityNode(IdentifiedObject):
    """
    Connectivity nodes are points where terminals of AC conducting equipment are connected
    together with zero impedance. If the model is a TSO EQ, the ConnectivityNodes should be
    grouped under VoltageLevel; If the model is a Boundary EQ, the ConnectivityNodes should
    be grouped under Line; If the model is an assembled one, the ConnectivityNodes can be
    grouped under either VoltageLevel or Line. With this approach the Line is also in the
    Boundary set. Instances of ACLineSegment can be in the Boundary set instance of Line
    or in another instance of Line. Consequently there can be instances of Line that contain
    only ConnectivityNodes, but no ACLineSegments.
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.boundaryPoint: bool = False

        self.fromEndIsoCode: str = ''
        self.fromEndName: str = ''
        self.fromEndNameTso: str = ''

        self.toEndIsoCode: str = ''
        self.toEndName: str = ''
        self.toEndNameTso: str = ''

        self.TopologicalNode: TopologicalNode = None
        self.ConnectivityNodeContainer: ConnectivityNodeContainer = None  # use this instead of TopologicalNode?

        self.possibleProfileList |= {'class': [cgmesProfile.TP_BD.value, cgmesProfile.EQ.value, cgmesProfile.TP.value,
                                               cgmesProfile.EQ_BD.value, ],
                                     'TopologicalNode': [cgmesProfile.TP_BD.value, cgmesProfile.TP.value, ],
                                     'Terminals': [cgmesProfile.EQ.value, ],
                                     'ConnectivityNodeContainer': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     'boundaryPoint': [cgmesProfile.EQ_BD.value, ],
                                     'fromEndIsoCode': [cgmesProfile.EQ_BD.value, ],
                                     'fromEndName': [cgmesProfile.EQ_BD.value, ],
                                     'fromEndNameTso': [cgmesProfile.EQ_BD.value, ],
                                     'toEndIsoCode': [cgmesProfile.EQ_BD.value, ],
                                     'toEndName': [cgmesProfile.EQ_BD.value, ],
                                     'toEndNameTso': [cgmesProfile.EQ_BD.value, ],
                                     }

        self.register_property(name='boundaryPoint',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Identifies if a node is a BoundaryPoint. "
                                           "If boundaryPoint=true the ConnectivityNode"
                                           " or the TopologicalNode represents a "
                                           "BoundaryPoint",
                               mandatory=True
                               )

        self.register_property(name='fromEndIsoCode',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the ISO code of the region to which the "
                                           "'From' side of the Boundary point belongs"
                                           " to or it is connected to. The ISO code "
                                           "is two characters country code as "
                                           "defined by ISO 3166 "
                                           "(http://www.iso.org/iso/country_codes). "
                                           "The length of the string is 2 characters "
                                           "maximum.   The attribute is a required "
                                           "for the Boundary Model Authority Set "
                                           "where this attribute is used only for "
                                           "the TopologicalNode in the Boundary "
                                           "Topology profile and ConnectivityNode "
                                           "in the Boundary Equipment profile.",
                               max_chars=2,
                               mandatory=True
                               )

        self.register_property(name='fromEndName',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description='The attribute is used for an exchange of a '
                                           'human readable name with length of the '
                                           'string 32 characters maximum. The attribute '
                                           'covers two cases:  '
                                           'if the Boundary point is placed on a '
                                           'tie-line the attribute is used for exchange '
                                           'of the geographical name of the Substation '
                                           'to which the From side of the tie-line is '
                                           'connected to.  if the Boundary point is '
                                           'placed in a Substation the attribute is '
                                           'used for exchange of the name of the element'
                                           ' (e.g. PowerTransformer, ACLineSegment, '
                                           'Switch, etc) to which the From side of the '
                                           'Boundary point is connected to. The '
                                           'attribute is required for the Boundary '
                                           'Model Authority Set where it is used only '
                                           'for the TopologicalNode in the Boundary '
                                           'Topology profile and ConnectivityNode in '
                                           'the Boundary Equipment profile.',
                               max_chars=32,
                               mandatory=True
                               )

        self.register_property(name='fromEndNameTso',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the name of the TSO to which the “From” "
                                           "side of the Boundary point belongs to or "
                                           "it is connected to. The length of the "
                                           "string is 32 characters maximum.  The "
                                           "attribute is required for the Boundary "
                                           "Model Authority Set where it is used "
                                           "only for the TopologicalNode in the "
                                           "Boundary Topology profile and "
                                           "ConnectivityNode in the Boundary "
                                           "Equipment profile.",
                               max_chars=32,
                               mandatory=True
                               )

        self.register_property(name='toEndIsoCode',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the ISO code of the region to which the "
                                           "“To” side of the Boundary point belongs "
                                           "to or it is connected to. The ISO code is "
                                           "two characters country code as defined by "
                                           "ISO 3166 "
                                           "(http://www.iso.org/iso/country_codes). "
                                           "The length of the string is 2 characters "
                                           "maximum. The attribute is a required for "
                                           "the Boundary Model Authority Set where "
                                           "this attribute is used only for the "
                                           "TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the "
                                           "Boundary Equipment profile.",
                               max_chars=2,
                               mandatory=True)

        self.register_property(name='toEndName',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of a "
                                           "human readable name with length of the string "
                                           "32 characters maximum. The attribute covers "
                                           "two cases:  if the Boundary point is placed "
                                           "on a tie-line the attribute is used for "
                                           "exchange of the geographical name of the "
                                           "Substation to which the “To” side of the "
                                           "tie-line is connected to. if the Boundary "
                                           "point is placed in a Substation the attribute "
                                           "is used for exchange of the name of the "
                                           "element (e.g. PowerTransformer, "
                                           "ACLineSegment, Switch, etc) to which the “To” "
                                           "side of the Boundary point is connected to. "
                                           "The attribute is required for the Boundary "
                                           "Model Authority Set where it is used only for "
                                           "the TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the Boundary "
                                           "Equipment profile.",
                               max_chars=32,
                               mandatory=True
                               )

        self.register_property(name='toEndNameTso',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the name of the TSO to which the “To” side "
                                           "of the Boundary point belongs to or it is "
                                           "connected to. The length of the string is "
                                           "32 characters maximum. The attribute is "
                                           "required for the Boundary Model Authority "
                                           "Set where it is used only for the "
                                           "TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the "
                                           "Boundary Equipment profile.",
                               max_chars=32,
                               mandatory=True)

        self.register_property(name='TopologicalNode',
                               class_type=TopologicalNode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment="Out of the standard")

        self.register_property(name='ConnectivityNodeContainer',
                               class_type=ConnectivityNodeContainer,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Container of this connectivity node")


class TopologicalNode(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.boundaryPoint: bool = False
        self.fromEndIsoCode = ''
        self.fromEndName = ''
        self.fromEndNameTso = ''
        self.toEndIsoCode = ''
        self.toEndName = ''
        self.toEndNameTso = ''

        self.ResourceOwner: str = ''  # todo: out of the standard
        self.BaseVoltage: BaseVoltage = None
        self.ConnectivityNodeContainer: ConnectivityNode = None

        self.possibleProfileList |= {
            'class': [cgmesProfile.TP_BD.value, cgmesProfile.TP.value, cgmesProfile.SV.value, ],
            'BaseVoltage': [cgmesProfile.TP_BD.value, cgmesProfile.TP.value, ],
            'ConnectivityNodes': [cgmesProfile.TP_BD.value, cgmesProfile.TP.value, ],
            'ConnectivityNodeContainer': [cgmesProfile.TP_BD.value, cgmesProfile.TP.value, ],
            'boundaryPoint': [cgmesProfile.TP_BD.value, ],
            'fromEndIsoCode': [cgmesProfile.TP_BD.value, ],
            'fromEndName': [cgmesProfile.TP_BD.value, ],
            'fromEndNameTso': [cgmesProfile.TP_BD.value, ],
            'toEndIsoCode': [cgmesProfile.TP_BD.value, ],
            'toEndName': [cgmesProfile.TP_BD.value, ],
            'toEndNameTso': [cgmesProfile.TP_BD.value, ],
            'ReportingGroup': [cgmesProfile.TP.value, ],
            'Terminal': [cgmesProfile.TP.value, ],
            'SvInjection': [cgmesProfile.SV.value, ],
            'SvVoltage': [cgmesProfile.SV.value, ],
            'AngleRefTopologicalIsland': [cgmesProfile.SV.value, ],
            'TopologicalIsland': [cgmesProfile.SV.value, ],
            }

        self.register_property(name='boundaryPoint',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Identifies if a node is a BoundaryPoint. "
                                           "If boundaryPoint=true the ConnectivityNode"
                                           " or the TopologicalNode represents a "
                                           "BoundaryPoint"
                               )

        self.register_property(name='fromEndIsoCode',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the ISO code of the region to which the "
                                           "'From' side of the Boundary point belongs"
                                           " to or it is connected to. The ISO code "
                                           "is two characters country code as "
                                           "defined by ISO 3166 "
                                           "(http://www.iso.org/iso/country_codes). "
                                           "The length of the string is 2 characters "
                                           "maximum.   The attribute is a required "
                                           "for the Boundary Model Authority Set "
                                           "where this attribute is used only for "
                                           "the TopologicalNode in the Boundary "
                                           "Topology profile and ConnectivityNode "
                                           "in the Boundary Equipment profile.",
                               max_chars=2)

        self.register_property(name='fromEndName',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description='The attribute is used for an exchange of a '
                                           'human readable name with length of the '
                                           'string 32 characters maximum. The attribute '
                                           'covers two cases:  '
                                           'if the Boundary point is placed on a '
                                           'tie-line the attribute is used for exchange '
                                           'of the geographical name of the Substation '
                                           'to which the From side of the tie-line is '
                                           'connected to.  if the Boundary point is '
                                           'placed in a Substation the attribute is '
                                           'used for exchange of the name of the element'
                                           ' (e.g. PowerTransformer, ACLineSegment, '
                                           'Switch, etc) to which the From side of the '
                                           'Boundary point is connected to. The '
                                           'attribute is required for the Boundary '
                                           'Model Authority Set where it is used only '
                                           'for the TopologicalNode in the Boundary '
                                           'Topology profile and ConnectivityNode in '
                                           'the Boundary Equipment profile.',
                               max_chars=32)

        self.register_property(name='fromEndNameTso',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the name of the TSO to which the “From” "
                                           "side of the Boundary point belongs to or "
                                           "it is connected to. The length of the "
                                           "string is 32 characters maximum.  The "
                                           "attribute is required for the Boundary "
                                           "Model Authority Set where it is used "
                                           "only for the TopologicalNode in the "
                                           "Boundary Topology profile and "
                                           "ConnectivityNode in the Boundary "
                                           "Equipment profile.",
                               max_chars=32)

        self.register_property(name='toEndIsoCode',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the ISO code of the region to which the "
                                           "“To” side of the Boundary point belongs "
                                           "to or it is connected to. The ISO code is "
                                           "two characters country code as defined by "
                                           "ISO 3166 "
                                           "(http://www.iso.org/iso/country_codes). "
                                           "The length of the string is 2 characters "
                                           "maximum. The attribute is a required for "
                                           "the Boundary Model Authority Set where "
                                           "this attribute is used only for the "
                                           "TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the "
                                           "Boundary Equipment profile.",
                               max_chars=2)

        self.register_property(name='toEndName',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of a "
                                           "human readable name with length of the string "
                                           "32 characters maximum. The attribute covers "
                                           "two cases:  if the Boundary point is placed "
                                           "on a tie-line the attribute is used for "
                                           "exchange of the geographical name of the "
                                           "Substation to which the “To” side of the "
                                           "tie-line is connected to. if the Boundary "
                                           "point is placed in a Substation the attribute "
                                           "is used for exchange of the name of the "
                                           "element (e.g. PowerTransformer, "
                                           "ACLineSegment, Switch, etc) to which the “To” "
                                           "side of the Boundary point is connected to. "
                                           "The attribute is required for the Boundary "
                                           "Model Authority Set where it is used only for "
                                           "the TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the Boundary "
                                           "Equipment profile.",
                               max_chars=32)

        self.register_property(name='toEndNameTso',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the name of the TSO to which the “To” side "
                                           "of the Boundary point belongs to or it is "
                                           "connected to. The length of the string is "
                                           "32 characters maximum. The attribute is "
                                           "required for the Boundary Model Authority "
                                           "Set where it is used only for the "
                                           "TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the "
                                           "Boundary Equipment profile.",
                               max_chars=32)

        self.register_property(name='ResourceOwner',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Stuff for PSSe nodes EKG made up",
                               comment='Out of the standard',
                               out_of_the_standard=True)

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The base voltage of the topological node.")

        self.register_property(name='ConnectivityNodeContainer',
                               class_type=ConnectivityNodeContainer,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Container of this connectivity node")

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


class BusbarSection(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.ipMax: float = 0.0

        self.EquipmentContainer: IdentifiedObject = None
        self.BaseVoltage: BaseVoltage = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'ipMax': [cgmesProfile.EQ.value, ],
                                     }  # TODO should not contain more?

        self.register_property(name='ipMax',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.A,
                               description="Maximum allowable peak short-circuit current of "
                                           "busbar (Ipmax in the IEC 60909-0). Mechanical "
                                           "limit of the busbar in the Substation itself. "
                                           "Used for short circuit data exchange according "
                                           "to IEC 60909")

        self.register_property(name='EquipmentContainer',
                               class_type=IdentifiedObject,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

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


class Substation(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.Region: SubGeographicalRegion = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'DCConverterUnit': [cgmesProfile.EQ.value, ],
                                     'Region': [cgmesProfile.EQ.value, ],
                                     'VoltageLevels': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='Region',
                               class_type=SubGeographicalRegion,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The SubGeographicalRegion "
                                           "containing the Substation.")


class OperationalLimitSet(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.Terminal: Terminal = None
        self.Equipment: IdentifiedObject = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'Terminal': [cgmesProfile.EQ.value, ],
                                     'Equipment': [cgmesProfile.EQ.value, ],
                                     'OperationalLimitValue': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='Terminal',
                               class_type=Terminal,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        self.register_property(name='Equipment',
                               class_type=IdentifiedObject,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The equipment to which the "
                                           "limit set applies.")


class OperationalLimitType(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.limitType: cim_enums.LimitTypeKind = cim_enums.LimitTypeKind.patl
        self.direction: cim_enums.OperationalLimitDirectionKind = cim_enums.OperationalLimitDirectionKind.absoluteValue
        self.acceptableDuration: float = 0.0

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'OperationalLimit': [cgmesProfile.EQ.value, ],
                                     'acceptableDuration': [cgmesProfile.EQ.value, ],
                                     'limitType': [cgmesProfile.EQ.value, ],
                                     'direction': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='limitType',
                               class_type=cim_enums.LimitTypeKind,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Types of limits defined in the ENTSO-E "
                                           "Operational Handbook Policy 3.")

        self.register_property(name='direction',
                               class_type=cim_enums.OperationalLimitDirectionKind,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The direction of the limit.")

        self.register_property(name='acceptableDuration',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.s,
                               description="The nominal acceptable duration of "
                                           "the limit. Limits are commonly "
                                           "expressed in terms of the a time "
                                           "limit for which the limit is "
                                           "normally acceptable. The actual "
                                           "acceptable duration of a specific "
                                           "limit may depend on other local "
                                           "factors such as temperature or "
                                           "wind speed.")


class GeographicalRegion(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     'Regions': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     }


class SubGeographicalRegion(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.Region: GeographicalRegion = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     'DCLines': [cgmesProfile.EQ.value, ],
                                     'Region': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     'Lines': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     'Substations': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='Region',
                               class_type=GeographicalRegion,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The geographical region to which this "
                                           "sub-geographical region is within.")


class VoltageLevel(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.highVoltageLimit: float = 0.0
        self.lowVoltageLimit: float = 0.0

        self.Substation: Substation = None
        self.BaseVoltage: BaseVoltage = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'BaseVoltage': [cgmesProfile.EQ.value, ],
                                     'Bays': [cgmesProfile.EQ.value, ],
                                     'Substation': [cgmesProfile.EQ.value, ],
                                     'highVoltageLimit': [cgmesProfile.EQ.value, ],
                                     'lowVoltageLimit': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='highVoltageLimit',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="The bus bar's high voltage limit")

        self.register_property(name='lowVoltageLimit',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="The bus bar's low voltage limit")

        self.register_property(name='Substation',
                               class_type=Substation,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               mandatory=True)

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               mandatory=True)


class VoltageLimit(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.value: float = 0.0
        self.OperationalLimitSet: OperationalLimitSet = None
        self.OperationalLimitType: OperationalLimitType = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'value': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='value',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="Limit on voltage. High or low limit nature of "
                                           "the limit depends upon the properties of the "
                                           "operational limit type.")

        self.register_property(name='OperationalLimitSet',
                               class_type=OperationalLimitSet,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        self.register_property(name='OperationalLimitType',
                               class_type=OperationalLimitType,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")


class CurrentLimit(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.value: float = 0.0
        self.OperationalLimitSet: OperationalLimitSet = None
        self.OperationalLimitType: OperationalLimitType = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'value': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='value',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.A,
                               description="Limit on current flow.")

        self.register_property(name='OperationalLimitSet',
                               class_type=OperationalLimitSet,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        self.register_property(name='OperationalLimitType',
                               class_type=OperationalLimitType,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")


class EquivalentNetwork(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'EquivalentEquipments': [cgmesProfile.EQ.value, ],
                                     }


class EnergyArea(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'ControlArea': [cgmesProfile.EQ.value, ],
                                     }


class ControlArea(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.type: cim_enums.ControlAreaTypeKind = cim_enums.ControlAreaTypeKind.AGC
        self.netInterchange: float = 0.0
        self.pTolerance: float = 0.0

        self.EnergyArea: EnergyArea | None = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'netInterchange': [cgmesProfile.SSH.value, ],
                                     'pTolerance': [cgmesProfile.SSH.value, ],
                                     'EnergyArea': [cgmesProfile.EQ.value, ],
                                     'type': [cgmesProfile.EQ.value, ],
                                     'TieFlow': [cgmesProfile.EQ.value, ],
                                     'ControlAreaGeneratingUnit': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='type',
                               class_type=cim_enums.ControlAreaTypeKind,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The primary type of control area definition used "
                                           "to determine if this is used for automatic "
                                           "generation control, for planning interchange "
                                           "control, or other purposes. A control area "
                                           "specified with primary type of automatic "
                                           "generation control could still be forecast and "
                                           "used as an interchange area in power flow analysis."
                               )

        self.register_property(name='netInterchange',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='out of the standard')

        self.register_property(name='pTolerance',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='out of the standard')

        self.register_property(name='EnergyArea',
                               class_type=EnergyArea,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The energy area that is forecast from this "
                                           "control area specification.")


class EquivalentEquipment(ConductingEquipment):

    def __init__(self, rdfid, tpe):
        ConductingEquipment.__init__(self, rdfid, tpe)

        # self.EquivalentNetwork = EquivalentNetwork


class EquivalentInjection(EquivalentEquipment):

    def __init__(self, rdfid, tpe):
        EquivalentEquipment.__init__(self, rdfid, tpe)

        self.regulationStatus: bool = False
        self.regulationTarget: float = 0.0  # kV
        self.p: float = 0.0
        self.q: float = 0.0
        self.maxP: float = 0.0
        self.maxQ: float = 0.0
        self.minP: float = 0.0
        self.minQ: float = 0.0
        self.r: float = 0.0
        self.r0: float = 0.0
        self.r2: float = 0.0
        self.x: float = 0.0
        self.x0: float = 0.0
        self.x2: float = 0.0
        self.regulationCapability: bool = False
        self.ReactiveCapabilityCurve: ReactiveCapabilityCurve = None

        # self.BaseVoltage: BaseVoltage = None  # TODO: out of the standard
        # self.EquipmentContainer: EquipmentContainer = None  # TODO: out of the standard

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'regulationStatus': [cgmesProfile.SSH.value, ],
                                     'regulationTarget': [cgmesProfile.SSH.value, ],
                                     'p': [cgmesProfile.SSH.value, ],
                                     'q': [cgmesProfile.SSH.value, ],
                                     'ReactiveCapabilityCurve': [cgmesProfile.EQ.value, ],
                                     'maxP': [cgmesProfile.EQ.value, ],
                                     'maxQ': [cgmesProfile.EQ.value, ],
                                     'minP': [cgmesProfile.EQ.value, ],
                                     'minQ': [cgmesProfile.EQ.value, ],
                                     'r': [cgmesProfile.EQ.value, ],
                                     'r0': [cgmesProfile.EQ.value, ],
                                     'r2': [cgmesProfile.EQ.value, ],
                                     'regulationCapability': [cgmesProfile.EQ.value, ],
                                     'x': [cgmesProfile.EQ.value, ],
                                     'x0': [cgmesProfile.EQ.value, ],
                                     'x2': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='regulationStatus',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description='Specifies the default regulation '
                                           'status of the EquivalentInjection. '
                                           'True is regulating. False is not '
                                           'regulating.')

        self.register_property(name='regulationTarget',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="The target voltage for voltage "
                                           "regulation.",
                               comment='')

        self.register_property(name='p',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="Equivalent active power injection. Load sign "
                                           "convention is used, i.e. positive sign means flow "
                                           "out from a node. Starting value for steady state "
                                           "solutions.",
                               comment='')

        self.register_property(name='q',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="Equivalent reactive power injection. Load sign "
                                           "convention is used, i.e. positive sign means flow "
                                           "out from a node. Starting value for steady state "
                                           "solutions.",
                               comment='')

        self.register_property(name='maxP',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="",
                               comment='')

        self.register_property(name='minP',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="",
                               comment='')

        self.register_property(name='maxQ',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="",
                               comment='')

        self.register_property(name='minQ',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="",
                               comment='')

        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='')

        self.register_property(name='r0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='')

        self.register_property(name='r2',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='')

        self.register_property(name='x',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='')

        self.register_property(name='x0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='')

        self.register_property(name='x2',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='')

        self.register_property(name='regulationCapability',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='out of the standard')

        self.register_property(name='ReactiveCapabilityCurve',
                               class_type=ReactiveCapabilityCurve,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        # self.register_property(name='BaseVoltage',
        #                        class_type=BaseVoltage,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        out_of_the_standard=True)
        #
        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        out_of_the_standard=True)


class Switch(DiPole, ConductingEquipment):

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)
        ConductingEquipment.__init__(self, rdfid, tpe)

        self.open: bool = False
        self.normalOpen: bool = True
        self.ratedCurrent: float = 0.0
        self.retained: bool = False

        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'open': [cgmesProfile.SSH.value, ],
                                     'normalOpen': [cgmesProfile.EQ.value, ],
                                     'ratedCurrent': [cgmesProfile.EQ.value, ],
                                     'retained': [cgmesProfile.EQ.value, ],
                                     # 'SwitchSchedules': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='open',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='The standard does not provide a proper description')

        self.register_property(name='normalOpen',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used in cases when no "
                                           "Measurement for the status value is present. "
                                           "If the Switch has a status measurement the "
                                           "Discrete.normalValue is expected to match "
                                           "with the Switch.normalOpen.",
                               comment='')

        self.register_property(name='ratedCurrent',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.A,
                               description="The maximum continuous current carrying "
                                           "capacity in amps governed by the device "
                                           "material and construction.",
                               comment='')

        self.register_property(name='retained',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='Branch is retained in a bus branch model. '
                                       'The flow through retained switches will normally '
                                       'be calculated in power flow.')

        # self.register_property(name='BaseVoltage',
        #                        class_type=BaseVoltage,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        comment='')
        #
        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        comment='')

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


class Breaker(Switch):

    def __init__(self, rdfid, tpe):
        Switch.__init__(self, rdfid, tpe)

        self.open: bool = False

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'open': [cgmesProfile.SSH.value]}

        self.register_property(name='open',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='The standard does not provide a proper description')


class LoadBreakSwitch(Switch):

    def __init__(self, rdfid, tpe):
        Switch.__init__(self, rdfid, tpe)


class Line(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.Region: SubGeographicalRegion = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     'Region': [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
                                     }

        self.register_property(name='Region',
                               class_type=SubGeographicalRegion,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The SubGeographicalRegion containing the line.")


class ACLineSegment(DiPole):

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)

        self.bch: float = 0.0
        self.gch: float = 0.0
        self.r: float = 0.0
        self.x: float = 0.0

        self.bch0: float = 0.0
        self.gch0: float = 0.0
        self.r0: float = 0.0
        self.x0: float = 0.0

        self.shortCircuitEndTemperature: float = 0.0

        self.length: float = 0.0

        self.BaseVoltage: BaseVoltage = None
        # self.EquipmentContainer: EquipmentContainer = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'b0ch': [cgmesProfile.EQ.value, ],
                                     'bch': [cgmesProfile.EQ.value, ],
                                     'g0ch': [cgmesProfile.EQ.value, ],
                                     'gch': [cgmesProfile.EQ.value, ],
                                     'r': [cgmesProfile.EQ.value, ],
                                     'r0': [cgmesProfile.EQ.value, ],
                                     'shortCircuitEndTemperature': [cgmesProfile.EQ.value, ],
                                     'x': [cgmesProfile.EQ.value, ],
                                     'x0': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='bch',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Positive sequence shunt (charging) susceptance, "
                                           "uniformly distributed, of the entire line section. "
                                           "This value represents the full charging over the "
                                           "full length of the line.")
        self.register_property(name='gch',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Positive sequence shunt (charging) conductance, "
                                           "uniformly distributed, of the entire line section.")
        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Positive sequence series resistance of the entire "
                                           "line section.")
        self.register_property(name='x',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Positive sequence series reactance of the entire "
                                           "line section.")

        self.register_property(name='bch0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Zero sequence shunt (charging) susceptance, "
                                           "uniformly distributed, of the entire line section.")
        self.register_property(name='gch0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Zero sequence shunt (charging) conductance, "
                                           "uniformly distributed, of the entire line section.")
        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Zero sequence series resistance of the entire "
                                           "line section.")
        self.register_property(name='x0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Zero sequence series reactance of the entire "
                                           "line section.")

        self.register_property(name='length',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.m,
                               description="Segment length for calculating line "
                                           "section capabilities")

        self.register_property(name='shortCircuitEndTemperature',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.degC,
                               description="Maximum permitted temperature"
                                           " at the end of SC for the "
                                           "calculation of minimum "
                                           "short-circuit currents. "
                                           "Used for short circuit data "
                                           "exchange according to IEC "
                                           "60909")

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="")

    def get_voltage(self, logger: DataLogger):

        if self.BaseVoltage is not None:
            return self.BaseVoltage.nominalVoltage
        else:
            if 'Terminal' in self.references_to_me.keys():
                tps = list(self.references_to_me['Terminal'])

                if len(tps) > 0:
                    tp = tps[0]

                    return tp.get_voltage(logger=logger)
                else:
                    return None
            else:
                return None

    def get_pu_values(self, Sbase: float = 100.0, logger: DataLogger = DataLogger):
        """
        Get the per-unit values of the equivalent PI model
        :param Sbase: Sbase in MVA
        :param logger: DataLogger object
        :return: R, X, Gch, Bch
        """
        if self.BaseVoltage is not None:
            Vnom = self.get_voltage(logger=logger)

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


class PowerTransformerEnd(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.b: float = 0.0
        self.g: float = 0.0
        self.r: float = 0.0
        self.x: float = 0.0

        self.b0: float = 0.0
        self.g0: float = 0.0
        self.r0: float = 0.0
        self.x0: float = 0.0

        self.rground: float = 0.0
        self.xground: float = 0.0
        self.grounded: bool = False

        self.ratedS: float = 0
        self.ratedU: float = 0

        self.endNumber: int = 0

        self.connectionKind: cim_enums.WindingConnection = cim_enums.WindingConnection.D

        self.phaseAngleClock: int = 0

        self.Terminal: Terminal = None
        self.BaseVoltage: BaseVoltage = None
        self.PowerTransformer: PowerTransformer = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'PowerTransformer': [cgmesProfile.EQ.value, ],
                                     'b': [cgmesProfile.EQ.value, ],
                                     'connectionKind': [cgmesProfile.EQ.value, ],
                                     'b0': [cgmesProfile.EQ.value, ],
                                     'phaseAngleClock': [cgmesProfile.EQ.value, ],
                                     'ratedS': [cgmesProfile.EQ.value, ],
                                     'g': [cgmesProfile.EQ.value, ],
                                     'ratedU': [cgmesProfile.EQ.value, ],
                                     'g0': [cgmesProfile.EQ.value, ],
                                     'r': [cgmesProfile.EQ.value, ],
                                     'r0': [cgmesProfile.EQ.value, ],
                                     'x': [cgmesProfile.EQ.value, ],
                                     'x0': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='b',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Positive sequence shunt (charging) susceptance, "
                                           "uniformly distributed, of the entire line section. "
                                           "This value represents the full charging over the "
                                           "full length of the line.")
        self.register_property(name='g',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Positive sequence shunt (charging) conductance, "
                                           "uniformly distributed, of the entire line section.")
        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Positive sequence series resistance of the entire "
                                           "line section.")
        self.register_property(name='x',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Positive sequence series reactance of the entire "
                                           "line section.")

        self.register_property(name='b0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Zero sequence shunt (charging) susceptance, "
                                           "uniformly distributed, of the entire line section.")
        self.register_property(name='g0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Zero sequence shunt (charging) conductance, "
                                           "uniformly distributed, of the entire line section.")
        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Zero sequence series resistance of the entire "
                                           "line section.")
        self.register_property(name='x0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Zero sequence series reactance of the entire "
                                           "line section.")

        self.register_property(name='rground',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="(for Yn and Zn connections) Resistance part of "
                                           "neutral impedance where 'grounded' is true."
                               )

        self.register_property(name='xground',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="(for Yn and Zn connections) Reactance part of "
                                           "neutral impedance where 'grounded' is true."
                               )

        self.register_property(name='grounded',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="(for Yn and Zn connections) True if the "
                                           "neutral is solidly grounded."
                               )

        self.register_property(name='endNumber',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="(for Yn and Zn connections) True if the "
                                           "neutral is solidly grounded."
                               )

        self.register_property(name='ratedS',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VA,
                               description="Normal apparent power rating. "
                                           "The attribute shall be a positive value. "
                                           "For a two-winding transformer the values for "
                                           "the high and low voltage sides shall be "
                                           "identical."
                               )

        self.register_property(name='ratedU',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="Rated voltage: phase-phase for three-phase "
                                           "windings, and either phase-phase or "
                                           "phase-neutral for single-phase windings. A high "
                                           "voltage side, as given by "
                                           "TransformerEnd.endNumber, shall have a ratedU "
                                           "that is greater or equal than ratedU for the "
                                           "lower voltage sides."
                               )

        self.register_property(name='connectionKind',
                               class_type=cim_enums.WindingConnection,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Kind of connection.")

        self.register_property(name='phaseAngleClock',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Terminal voltage phase angle "
                                           "displacement where 360 degrees are "
                                           "represented with clock hours. The valid "
                                           "values are 0 to 11. For example, for "
                                           "the secondary side end of a transformer "
                                           "with vector group code of 'Dyn11', "
                                           "specify the connection kind as wye with "
                                           "neutral and specify the phase angle of "
                                           "the clock as 11. The clock value of the "
                                           "transformer end number specified as 1, "
                                           "is assumed to be zero. Note the "
                                           "transformer end number is not assumed "
                                           "to be the same as the terminal sequence "
                                           "number.")

        self.register_property(name='PowerTransformer',
                               class_type=PowerTransformer,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The ends of this power transformer.",
                               mandatory=True)

        self.register_property(name='Terminal',
                               class_type=Terminal,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               mandatory=True)

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               mandatory=True)

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


class PowerTransformer(DiPole, ConductingEquipment):

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)
        ConductingEquipment.__init__(self, rdfid, tpe)

        self.beforeShCircuitHighestOperatingCurrent: float = 0.0
        self.beforeShCircuitHighestOperatingVoltage: float = 0.0
        self.beforeShortCircuitAnglePf: float = 0.0
        self.highSideMinOperatingU: float = 0.0
        self.isPartOfGeneratorUnit: bool = False
        self.operationalValuesConsidered: bool = False

        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None  # TODO: This is VERY wrong. A transformer does not have an intrinsic voltage, however this comes in the CGMES standard

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'beforeShCircuitHighestOperatingCurrent': [cgmesProfile.EQ.value, ],
                                     'beforeShCircuitHighestOperatingVoltage': [cgmesProfile.EQ.value, ],
                                     'beforeShortCircuitAnglePf': [cgmesProfile.EQ.value, ],
                                     'highSideMinOperatingU': [cgmesProfile.EQ.value, ],
                                     'isPartOfGeneratorUnit': [cgmesProfile.EQ.value, ],
                                     'operationalValuesConsidered': [cgmesProfile.EQ.value, ],
                                     'PowerTransformerEnd': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='beforeShCircuitHighestOperatingCurrent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.A,
            description="The highest operating current (Ib in the IEC 60909-0) before short circuit "
                        "(depends on network configuration and relevant reliability philosophy). "
                        "It is used for calculation of the impedance correction factor KT defined in IEC 60909-0.")

        self.register_property(
            name='beforeShCircuitHighestOperatingVoltage',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="The highest operating voltage (Ub in the IEC 60909-0) before short circuit. "
                        "It is used for calculation of the impedance correction factor KT defined in IEC 60909-0. "
                        "This is worst case voltage on the low side winding (Section 3.7.1 in the standard). "
                        "Used to define operating conditions.")

        self.register_property(
            name='beforeShortCircuitAnglePf',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.deg,
            description="The angle of power factor before short circuit (phib in the IEC 60909-0). "
                        "It is used for calculation of the impedance correction factor KT defined in IEC 60909-0. "
                        "This is the worst case power factor. Used to define operating conditions.")

        self.register_property(
            name='highSideMinOperatingU',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="The minimum operating voltage (uQmin in the IEC 60909-0) at the high voltage side (Q side) "
                        "of the unit transformer of the power station unit. A value well established from long-term "
                        "operating experience of the system. It is used for calculation of the impedance correction "
                        "factor KG defined in IEC 60909-0")

        self.register_property(
            name='isPartOfGeneratorUnit',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Indicates whether the machine is part of a power station unit. "
                        "Used for short circuit data exchange according to IEC 60909")

        self.register_property(
            name='operationalValuesConsidered',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="It is used to define if the data (other attributes related to short circuit data exchange) "
                        "defines long term operational conditions or not. Used for short circuit data exchange "
                        "according to IEC 60909.")

        # self.register_property(name='BaseVoltage',
        #                        class_type=BaseVoltage,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="")
        #
        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="")

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

    def get_pu_values(self, System_Sbase):
        """
        Get the transformer p.u. values
        :return:
        """
        try:
            windings = self.get_windings()

            R, X, G, B = 0, 0, 0, 0
            R0, X0, G0, B0 = 0, 0, 0, 0
            if len(windings) == 2:
                for winding in windings:
                    r, x, g, b = winding.get_pu_values(System_Sbase)
                    R += r
                    X += x
                    G += g
                    B += b
                    R += r
                    X += x
                    G += g
                    B += b

        except KeyError:
            R, X, G, B = 0, 0, 0, 0
            R0, X0, G0, B0 = 0, 0, 0, 0

        return R, X, G, B, R0, X0, G0, B0

    def get_voltages(self, logger: DataLogger):
        """

        :return:
        """
        return [x.get_voltage(logger=logger) for x in self.get_windings()]

    def get_rate(self):

        rating = 0
        for winding in self.get_windings():
            if winding.ratedS > rating:
                rating = winding.ratedS

        return rating


class EnergyConsumer(MonoPole, ConductingEquipment):

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)
        ConductingEquipment.__init__(self, rdfid, tpe)

        self.pfixed: float = 0.0
        self.pfixedPct: float = 0.0
        self.qfixed: float = 0.0
        self.qfixedPct: float = 0.0

        self.p: float = 0.0
        self.q: float = 0.0

        self.LoadResponse: LoadResponseCharacteristic = None
        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.DY.value, ],
                                     'p': [cgmesProfile.SSH.value, ],
                                     'q': [cgmesProfile.SSH.value, ],
                                     'pfixed': [cgmesProfile.EQ.value, ],
                                     'pfixedPct': [cgmesProfile.EQ.value, ],
                                     'qfixed': [cgmesProfile.EQ.value, ],
                                     'qfixedPct': [cgmesProfile.EQ.value, ],
                                     'LoadResponse': [cgmesProfile.EQ.value, ],
                                     # 'LoadDynamics': [cgmesProfile.DY.value, ],
                                     }

        self.register_property(
            name='pfixed',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="Active power of the load that is a fixed quantity. Load sign convention is used, i.e. "
                        "positive sign means flow out from a node.")
        self.register_property(
            name='pfixedPct',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Fixed active power as per cent of load group fixed active power. "
                        "Load sign convention is used, i.e. positive sign means flow out from a node.")
        self.register_property(
            name='qfixed',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="Reactive power of the load that is a fixed quantity. Load sign convention is used, i.e. "
                        "positive sign means flow out from a node.")
        self.register_property(
            name='qfixedPct',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Fixed reactive power as per cent of load group fixed reactive power. "
                        "Load sign convention is used, i.e. positive sign means flow out from a node.")

        self.register_property(
            name='p',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="",
            comment='Out of the standard')

        self.register_property(
            name='q',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="",
            comment='Out of the standard')

        self.register_property(name='LoadResponse',
                               class_type=LoadResponseCharacteristic,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

        # self.register_property(name='BaseVoltage',
        #                        class_type=BaseVoltage,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="")
        #
        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="")


class ConformLoad(EnergyConsumer):

    def __init__(self, rdfid, tpe):
        EnergyConsumer.__init__(self, rdfid, tpe)

        self.LoadGroup: ConformLoadGroup = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'LoadGroup': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='LoadGroup',
                               class_type=ConformLoadGroup,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

    def get_pq(self):
        return self.p, self.q


class ConformLoadGroup(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.SubLoadArea: SubLoadArea = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'SubLoadArea': [cgmesProfile.EQ.value, ],
                                     # 'ConformLoadSchedules': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='SubLoadArea',
                               class_type=SubLoadArea,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")


class SubLoadArea(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.LoadArea: LoadArea = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'LoadArea': [cgmesProfile.EQ.value, ],
                                     # 'LoadGroups': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='LoadArea',
                               class_type=LoadArea,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")


class LoadArea(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)


class NonConformLoad(EnergyConsumer):

    def __init__(self, rdfid, tpe):
        EnergyConsumer.__init__(self, rdfid, tpe)

        self.LoadGroup: NonConformLoadGroup = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'LoadGroup': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='LoadGroup',
                               class_type=NonConformLoadGroup,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")

    def get_pq(self):
        return self.p, self.q


class NonConformLoadGroup(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.SubLoadArea: SubLoadArea = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'SubLoadArea': [cgmesProfile.EQ.value, ],
                                     # 'ConformLoadSchedules': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='SubLoadArea',
                               class_type=SubLoadArea,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="")


class LoadGroup(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)


class LoadResponseCharacteristic(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.exponentModel: bool = False
        self.pVoltageExponent: float = 0.0
        self.qVoltageExponent: float = 0.0
        self.pFrequencyExponent: float = 0.0
        self.qFrequencyExponent: float = 0.0

        self.pConstantCurrent: float = 0.0
        self.pConstantImpedance: float = 0.0
        self.pConstantPower: float = 0.0

        self.qConstantCurrent: float = 0.0
        self.qConstantImpedance: float = 0.0
        self.qConstantPower: float = 0.0

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'EnergyConsumer': [cgmesProfile.EQ.value, ],
                                     'exponentModel': [cgmesProfile.EQ.value, ],
                                     'pConstantCurrent': [cgmesProfile.EQ.value, ],
                                     'pConstantImpedance': [cgmesProfile.EQ.value, ],
                                     'pConstantPower': [cgmesProfile.EQ.value, ],
                                     'pFrequencyExponent': [cgmesProfile.EQ.value, ],
                                     'pVoltageExponent': [cgmesProfile.EQ.value, ],
                                     'qConstantCurrent': [cgmesProfile.EQ.value, ],
                                     'qConstantImpedance': [cgmesProfile.EQ.value, ],
                                     'qConstantPower': [cgmesProfile.EQ.value, ],
                                     'qFrequencyExponent': [cgmesProfile.EQ.value, ],
                                     'qVoltageExponent': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='exponentModel',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Indicates the exponential voltage dependency model is to be used. "
                        "If false, the coefficient model is to be used. "
                        "The exponential voltage dependency model consist of the attributes "
                        "- pVoltageExponent "
                        "- qVoltageExponent. "
                        "The coefficient model consist of the attributes "
                        "- pConstantImpedance "
                        "- pConstantCurrent "
                        "- pConstantPower "
                        "- qConstantImpedance "
                        "- qConstantCurrent "
                        "- qConstantPower."
                        "The sum of pConstantImpedance, pConstantCurrent and pConstantPower shall equal 1. "
                        "The sum of qConstantImpedance, qConstantCurrent and qConstantPower shall equal 1.",
            mandatory=True)

        self.register_property(
            name='pVoltageExponent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Exponent of per unit voltage effecting real power.")

        self.register_property(
            name='qVoltageExponent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Exponent of per unit voltage effecting reactive power.")

        self.register_property(
            name='pFrequencyExponent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Exponent of per unit frequency effecting active power.")

        self.register_property(
            name='qFrequencyExponent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Exponent of per unit frequency effecting reactive power.")

        self.register_property(
            name='pConstantImpedance',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of active power load modeled as constant impedance.")

        self.register_property(
            name='pConstantCurrent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of active power load modeled as constant current.")

        self.register_property(
            name='pConstantPower',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of active power load modeled as constant power.")

        self.register_property(
            name='qConstantImpedance',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of reactive power load modeled as constant impedance.")

        self.register_property(
            name='qConstantCurrent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of reactive power load modeled as constant current.")

        self.register_property(
            name='qConstantPower',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of reactive power load modeled as constant power.")

    def check(self, logger: Logger):
        """
        Check OCL rules
        :param logger:
        :return:
        """
        err_counter = 0
        if self.exponentModel:
            if self.pVoltageExponent not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: pVoltageExponent not specified",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="Existence of pVoltageExponent")

            if self.qVoltageExponent not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: qVoltageExponent not specified",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="Existence of qVoltageExponent")
        else:
            if self.pConstantCurrent not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: pConstantCurrent not specified",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="Existence of pConstantCurrent")

            if self.pConstantPower not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: pConstantPower not specified",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="Existence of pConstantPower")

            if self.pConstantImpedance not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: pConstantImpedance not specified",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="Existence of pConstantImpedance")

            if self.qConstantCurrent not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: qConstantCurrent not specified",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="Existence of qConstantCurrent")

            if self.qConstantPower not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: qConstantPower not specified",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="Existence of qConstantPower")

            if self.qConstantImpedance not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: qConstantImpedance not specified",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="Existence of qConstantImpedance")

            p_factor = self.pConstantImpedance + self.pConstantCurrent + self.pConstantPower
            q_factor = self.qConstantImpedance + self.qConstantCurrent + self.qConstantPower
            if not np.isclose(p_factor, 1):
                err_counter += 1
                logger.add_error(msg="pConstantImpedance + pConstantCurrent + pConstantPower different from 1",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="1.0")

            if not np.isclose(q_factor, 1):
                err_counter += 1
                logger.add_error(msg="qConstantImpedance + qConstantCurrent + qConstantPower different from 1",
                                 device=self.rdfid + "." + "LoadResponseCharacteristic",
                                 expected_value="1.0")

        return err_counter == 0


class RegulatingControl(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.mode: cim_enums.RegulatingControlModeKind = cim_enums.RegulatingControlModeKind.voltage

        self.discrete: bool = False
        self.enabled: bool = True
        self.targetDeadband: float = 0.0
        self.targetValue: float = 0.0
        self.targetValueUnitMultiplier: UnitMultiplier = UnitMultiplier.none

        self.Terminal: Terminal = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'discrete': [cgmesProfile.SSH.value, ],
                                     'enabled': [cgmesProfile.SSH.value, ],
                                     'targetDeadband': [cgmesProfile.SSH.value, ],
                                     'targetValue': [cgmesProfile.SSH.value, ],
                                     'targetValueUnitMultiplier': [cgmesProfile.SSH.value, ],
                                     'Terminal': [cgmesProfile.EQ.value, ],
                                     # 'RegulatingCondEq': [cgmesProfile.EQ.value, ],
                                     'mode': [cgmesProfile.EQ.value, ],
                                     # 'RegulationSchedule': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='mode',
            class_type=cim_enums.RegulatingControlModeKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The regulating control mode presently available. "
                        "This specification allows for determining the kind of regulation without need for "
                        "obtaining the units from a schedule.")

        self.register_property(
            name='discrete',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The regulation is performed in a discrete mode. "
                        "This applies to equipment with discrete controls, e.g. tap changers and shunt compensators.",
            mandatory=True)

        self.register_property(
            name='enabled',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The flag tells if regulation is enabled.",
            mandatory=True)

        self.register_property(
            name='targetDeadband',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="This is a deadband used with discrete control to avoid excessive update of "
                        "controls like tap changers and shunt compensator banks while regulating. "
                        "The units of those appropriate for the mode.")

        self.register_property(
            name='targetValue',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The target value specified for case input. "
                        "This value can be used for the target value without the use of schedules. "
                        "The value has the units appropriate to the mode attribute.")

        self.register_property(
            name='targetValueUnitMultiplier',
            class_type=UnitMultiplier,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Specify the multiplier for used for the targetValue.")

        self.register_property(
            name='Terminal',
            class_type=Terminal,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The controls regulating this terminal.")


class TapChanger(PowerSystemResource):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.controlEnabled: bool = False
        self.step = 0

        self.highStep: int = 0
        self.lowStep: int = 0
        self.ltcFlag: bool = False
        self.neutralStep: int = 0
        self.neutralU: float = 0
        self.normalStep: int = 0

        self.TapChangerControl: TapChangerControl = None

        # self.TapSchedules = TapSchedules
        # self.SvTapStep = SvTapStep

        self.possibleProfileList |= {
            'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.SV.value, ],
            'controlEnabled': [cgmesProfile.SSH.value, ],
            'step': [cgmesProfile.SSH.value, ],
            'highStep': [cgmesProfile.EQ.value, ],
            'lowStep': [cgmesProfile.EQ.value, ],
            'ltcFlag': [cgmesProfile.EQ.value, ],
            'neutralStep': [cgmesProfile.EQ.value, ],
            'neutralU': [cgmesProfile.EQ.value, ],
            'normalStep': [cgmesProfile.EQ.value, ],
            'TapChangerControl': [cgmesProfile.EQ.value, ],
            'TapSchedules': [cgmesProfile.EQ.value, ],
            'SvTapStep': [cgmesProfile.SV.value, ],
        }

        self.register_property(
            name='controlEnabled',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="controlEnabled.")

        self.register_property(
            name='step',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="step")

        self.register_property(
            name='highStep',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Highest possible tap step position, advance from neutral. "
                        "The attribute shall be greater than lowStep.")

        self.register_property(
            name='lowStep',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Lowest possible tap step position, retard from neutral.")

        self.register_property(
            name='ltcFlag',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Specifies whether or not a TapChanger has load tap changing capabilities.")

        self.register_property(
            name='neutralStep',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The neutral tap step position for this winding. "
                        "The attribute shall be equal or greater than lowStep and equal or less than highStep.")

        self.register_property(
            name='neutralU',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Voltage at which the winding operates at the neutral tap setting.")

        self.register_property(
            name='normalStep',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The tap step position used in 'normal' network operation for this winding. "
                        "For a 'Fixed' tap changer indicates the current physical tap setting. "
                        "The attribute shall be equal or greater than lowStep and equal or less than highStep.")

        self.register_property(
            name='TapChangerControl',
            class_type=TapChangerControl,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description=".")


class RatioTapChanger(TapChanger):

    def __init__(self, rdfid, tpe):
        TapChanger.__init__(self, rdfid, tpe)

        self.tculControlMode: cim_enums.TransformerControlMode = cim_enums.TransformerControlMode.volt
        self.stepVoltageIncrement: float = 0.0

        self.TransformerEnd: PowerTransformerEnd = None
        self.RatioTapChangerTable: RatioTapChangerTable = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'tculControlMode': [cgmesProfile.EQ.value, ],
                                     'stepVoltageIncrement': [cgmesProfile.EQ.value, ],
                                     'RatioTapChangerTable': [cgmesProfile.EQ.value, ],
                                     'TransformerEnd': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='tculControlMode',
            class_type=cim_enums.TransformerControlMode,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Specifies the regulation control mode (voltage or reactive) of the RatioTapChanger.")

        self.register_property(
            name='stepVoltageIncrement',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Tap step increment, in per cent of nominal voltage, per step position..")

        self.register_property(
            name='TransformerEnd',
            class_type=PowerTransformerEnd,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Ratio tap changer associated with this transformer end.",
            mandatory=True)

        self.register_property(
            name='RatioTapChangerTable',
            class_type=RatioTapChangerTable,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The ratio tap changer of this tap ratio table.")


class GeneratingUnit(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.genControlSource: cim_enums.GeneratorControlSource = None
        self.governorSCD: float = 0.0
        self.initialP: float = 0.0
        self.longPF: float = 0.0
        self.maximumAllowableSpinningReserve: float = 0.0

        self.maxOperatingP: float = 0.0
        self.minOperatingP: float = 0.0
        self.nominalP: float = 0.0

        self.ratedGrossMaxP: float = 0.0
        self.ratedGrossMinP: float = 0.0
        self.ratedNetMaxP: float = 0.0

        self.shortPF: float = 0.0
        self.startupCost: float = 0.0
        self.variableCost: float = 0.0
        self.totalEfficiency: float = 0.0

        self.normalPF: float = 0.0

        self.EquipmentContainer: IdentifiedObject = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'normalPF': [cgmesProfile.SSH.value, ],
                                     'genControlSource': [cgmesProfile.EQ.value, ],
                                     'governorSCD': [cgmesProfile.EQ.value, ],
                                     'initialP': [cgmesProfile.EQ.value, ],
                                     'longPF': [cgmesProfile.EQ.value, ],
                                     'maximumAllowableSpinningReserve': [cgmesProfile.EQ.value, ],
                                     'maxOperatingP': [cgmesProfile.EQ.value, ],
                                     'minOperatingP': [cgmesProfile.EQ.value, ],
                                     'nominalP': [cgmesProfile.EQ.value, ],
                                     'ratedGrossMaxP': [cgmesProfile.EQ.value, ],
                                     'ratedGrossMinP': [cgmesProfile.EQ.value, ],
                                     'ratedNetMaxP': [cgmesProfile.EQ.value, ],
                                     'shortPF': [cgmesProfile.EQ.value, ],
                                     'startupCost': [cgmesProfile.EQ.value, ],
                                     'variableCost': [cgmesProfile.EQ.value, ],
                                     'totalEfficiency': [cgmesProfile.EQ.value, ],
                                     'ControlAreaGeneratingUnit': [cgmesProfile.EQ.value, ],
                                     'RotatingMachine': [cgmesProfile.EQ.value, ],
                                     'GrossToNetActivePowerCurves': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='genControlSource',
            class_type=cim_enums.GeneratorControlSource,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The ratio tap changer of this tap ratio table.")

        self.register_property(
            name='governorSCD',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Governor Speed Changer Droop. "
                        "This is the change in generator power output divided by the change in frequency "
                        "normalized by the nominal power of the generator and the nominal frequency and "
                        "expressed in percent and negated. A positive value of speed change droop provides "
                        "additional generator output upon a drop in frequency.")

        self.register_property(
            name='initialP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="Default initial active power which is used to store a powerflow result for the initial "
                        "active power for this unit in this network configuration.",
            mandatory=True)

        self.register_property(
            name='longPF',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Generating unit long term economic participation factor.")

        self.register_property(
            name='maximumAllowableSpinningReserve',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="Maximum allowable spinning reserve. Spinning reserve will never be considered "
                        "greater than this value regardless of the current operating point.")

        self.register_property(
            name='maxOperatingP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="This is the maximum operating active power limit the dispatcher can enter for this unit.",
            mandatory=True
        )

        self.register_property(
            name='minOperatingP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="This is the minimum operating active power limit the dispatcher can enter for this unit.",
            mandatory=True)

        self.register_property(
            name='nominalP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="The nominal power of the generating unit. "
                        "Used to give precise meaning to percentage based attributes such as "
                        "the governor speed change droop (governorSCD attribute). The attribute shall be "
                        "a positive value equal or less than RotatingMachine.ratedS.")

        self.register_property(
            name='ratedGrossMaxP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="The unit's gross rated maximum capacity (book value).")

        self.register_property(
            name='ratedGrossMinP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="The gross rated minimum generation level which the unit can safely operate "
                        "at while delivering power to the transmission grid.")

        self.register_property(
            name='ratedNetMaxP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="The net rated maximum capacity determined by subtracting the auxiliary power used to "
                        "operate the internal plant machinery from the rated gross maximum capacity.")

        self.register_property(
            name='shortPF',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Generating unit short term economic participation factor.")

        self.register_property(
            name='startupCost',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.Money,
            description="The initial startup cost incurred for each start of the GeneratingUnit.")

        self.register_property(
            name='variableCost',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.Money,
            description="The variable cost component of production per unit of ActivePower.")

        self.register_property(
            name='totalEfficiency',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The efficiency of the unit in converting the fuel into electrical energy.")

        self.register_property(
            name='normalPF',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Generating unit economic participation factor..")

        self.register_property(
            name='EquipmentContainer',
            class_type=IdentifiedObject,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")


class HydroPump(Equipment):

    def __init__(self, rdfid, tpe):
        Equipment.__init__(self, rdfid, tpe)
        self.HydroPowerPlant: HydroPowerPlant = None
        self.RotatingMachine: RotatingMachine = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'HydroPowerPlant': [cgmesProfile.EQ.value, ],
                                     'RotatingMachine': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='HydroPowerPlant',
                               class_type=HydroPowerPlant,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="HydroPowerPlant", )

        self.register_property(name='RotatingMachine',
                               class_type=RotatingMachine,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="RotatingMachine", )


class RegulatingCondEq(ConductingEquipment):

    def __init__(self, rdfid, tpe):
        ConductingEquipment.__init__(self, rdfid, tpe)

        self.controlEnabled: bool = False
        self.RegulatingControl: RegulatingControl = None

        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.DY.value, ],
                                     'controlEnabled': [cgmesProfile.SSH.value, ],
                                     'RegulatingControl': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='controlEnabled',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="", )

        self.register_property(name='RegulatingControl',
                               class_type=RegulatingControl,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="RegulatingControl", )


class RotatingMachine(RegulatingCondEq):

    def __init__(self, rdfid, tpe):
        RegulatingCondEq.__init__(self, rdfid, tpe)

        self.p: float = 0
        self.q: float = 0
        self.GeneratingUnit: GeneratingUnit = None
        self.HydroPump: HydroPump = None
        self.ratedPowerFactor: float = 0.0
        self.ratedS: float = 0.0
        self.ratedU: float = 0.0

        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.DY.value, ],
                                     'p': [cgmesProfile.SSH.value, ],
                                     'q': [cgmesProfile.SSH.value, ],
                                     'GeneratingUnit': [cgmesProfile.EQ.value, ],
                                     'HydroPump': [cgmesProfile.EQ.value, ],
                                     'ratedPowerFactor': [cgmesProfile.EQ.value, ],
                                     'ratedS': [cgmesProfile.EQ.value, ],
                                     'ratedU': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(name='p',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="", )

        self.register_property(name='q',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="", )

        self.register_property(name='GeneratingUnit',
                               class_type=GeneratingUnit,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="GeneratingUnit", )

        self.register_property(name='HydroPump',
                               class_type=HydroPump,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="HydroPump", )

        self.register_property(name='ratedPowerFactor',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="ratedPowerFactor", )

        self.register_property(name='ratedS',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VA,
                               description="ratedS", )

        self.register_property(name='ratedU',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="ratedU", )


class SynchronousMachine(MonoPole, RotatingMachine):

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)
        RotatingMachine.__init__(self, rdfid, tpe)

        self.earthing: bool = False
        self.earthingStarPointR: float = 0.0
        self.earthingStarPointX: float = 0.0
        self.ikk: float = 0.0
        self.maxQ: float = 0
        self.minQ: float = 0
        self.mu: float = 0.0

        self.qPercent: float = 0
        self.r: float = 0.0
        self.r0: float = 0.0
        self.r2: float = 0.0

        # self.x: float = 0.0  # TODO: out of the standard...
        self.x0: float = 0.0
        self.x2: float = 0.0

        self.satDirectSubtransX: float = 0.0
        self.satDirectSyncX: float = 0.0
        self.satDirectTransX: float = 0.0
        self.shortCircuitRotorType: cim_enums.ShortCircuitRotorKind = cim_enums.ShortCircuitRotorKind.salientPole1

        self.type: cim_enums.SynchronousMachineKind = cim_enums.SynchronousMachineKind.generator

        self.voltageRegulationRange: float = 0.0

        self.ratedPowerFactor: float = 1.0
        self.ratedS: float = 0.0
        self.ratedU: float = 0.0

        self.operatingMode: cim_enums.SynchronousMachineOperatingMode = cim_enums.SynchronousMachineOperatingMode.generator
        self.referencePriority = 0

        self.InitialReactiveCapabilityCurve: ReactiveCapabilityCurve = None
        self.GeneratingUnit: GeneratingUnit = None
        self.RegulatingControl: RegulatingControl = None
        self.BaseVoltage: BaseVoltage = None
        self.EquipmentContainer: IdentifiedObject = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.DY.value, ],
                                     'operatingMode': [cgmesProfile.SSH.value, ],
                                     'referencePriority': [cgmesProfile.SSH.value, ],
                                     'InitialReactiveCapabilityCurve': [cgmesProfile.EQ.value, ],
                                     'earthing': [cgmesProfile.EQ.value, ],
                                     'earthingStarPointR': [cgmesProfile.EQ.value, ],
                                     'earthingStarPointX': [cgmesProfile.EQ.value, ],
                                     'ikk': [cgmesProfile.EQ.value, ],
                                     'maxQ': [cgmesProfile.EQ.value, ],
                                     'minQ': [cgmesProfile.EQ.value, ],
                                     'mu': [cgmesProfile.EQ.value, ],
                                     'qPercent': [cgmesProfile.EQ.value, ],
                                     'r0': [cgmesProfile.EQ.value, ],
                                     'r2': [cgmesProfile.EQ.value, ],
                                     'satDirectSubtransX': [cgmesProfile.EQ.value, ],
                                     'satDirectSyncX': [cgmesProfile.EQ.value, ],
                                     'satDirectTransX': [cgmesProfile.EQ.value, ],
                                     'shortCircuitRotorType': [cgmesProfile.EQ.value, ],
                                     'type': [cgmesProfile.EQ.value, ],
                                     'voltageRegulationRange': [cgmesProfile.EQ.value, ],
                                     'r': [cgmesProfile.EQ.value, ],
                                     'x0': [cgmesProfile.EQ.value, ],
                                     'x2': [cgmesProfile.EQ.value, ],
                                     'SynchronousMachineDynamics': [cgmesProfile.DY.value, ],
                                     }

        self.register_property(
            name='earthing',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Indicates whether or not the generator is earthed. "
                        "Used for short circuit data exchange according to IEC 60909")

        self.register_property(
            name='earthingStarPointR',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Generator star point earthing resistance (Re). "
                        "Used for short circuit data exchange according to IEC 60909")

        self.register_property(
            name='earthingStarPointX',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Generator star point earthing reactance (Xe). "
                        "Used for short circuit data exchange according to IEC 60909")

        self.register_property(
            name='ikk',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.A,
            description="Steady-state short-circuit current (in A for the profile) "
                        "of generator with compound excitation during 3-phase short circuit. "
                        "- Ikk=0: Generator with no compound excitation. "
                        "- Ikk?0: Generator with compound excitation. "
                        "Ikk is used to calculate the minimum steady-state short-circuit current for "
                        "generators with compound excitation (Section 4.6.1.2 in the IEC 60909-0) "
                        "Used only for single fed short circuit on a generator. (Section 4.3.4.2. in the IEC 60909-0)")

        self.register_property(
            name='maxQ',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="Maximum reactive power limit. This is the maximum (nameplate) limit for the unit.")

        self.register_property(
            name='minQ',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="Minimum reactive power limit for the unit.")

        self.register_property(
            name='mu',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Factor to calculate the breaking current (Section 4.5.2.1 in the IEC 60909-0). "
                        "Used only for single fed short circuit on a generator (Section 4.3.4.2. in the IEC 60909-0).")

        self.register_property(
            name='qPercent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Percent of the coordinated reactive control that comes from this machine.")

        self.register_property(
            name='r',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Equivalent resistance (RG) of generator. "
                        "RG is considered for the calculation of all currents, except for the "
                        "calculation of the peak current ip. Used for short circuit data exchange "
                        "according to IEC 60909")

        self.register_property(
            name='r0',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Zero sequence resistance of the synchronous machine.")

        self.register_property(
            name='r2',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Negative sequence resistance.")

        # self.register_property(
        #     name='x',
        #     class_type=float,
        #     multiplier=UnitMultiplier.none,
        #     unit=UnitSymbol.ohm,
        #     description="Equivalent reactance (RG) of generator. "
        #                 "RG is considered for the calculation of all currents, except for the "
        #                 "calculation of the peak current ip. Used for short circuit data exchange "
        #                 "according to IEC 60909")

        self.register_property(
            name='x0',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Zero sequence reactance of the synchronous machine.")

        self.register_property(
            name='x2',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Negative sequence reactance.")

        self.register_property(
            name='satDirectSubtransX',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Direct-axis subtransient reactance saturated, also known as Xd''sat.")

        self.register_property(
            name='satDirectSyncX',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Direct-axes saturated synchronous reactance (xdsat); reciprocal of short-circuit ration. "
                        "Used for short circuit data exchange, only for single fed short circuit on a generator. "
                        "(Section 4.3.4.2. in the IEC 60909-0).")

        self.register_property(
            name='satDirectTransX',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Saturated Direct-axis transient reactance. "
                        "The attribute is primarily used for short circuit calculations according to ANSI.")

        self.register_property(
            name='shortCircuitRotorType',
            class_type=cim_enums.ShortCircuitRotorKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Type of rotor, used by short circuit applications, "
                        "only for single fed short circuit according to IEC 60909.")

        self.register_property(
            name='type',
            class_type=cim_enums.SynchronousMachineKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Modes that this synchronous machine can operate in.")

        self.register_property(
            name='voltageRegulationRange',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Range of generator voltage regulation (PG in the IEC 60909-0) used for calculation "
                        "of the impedance correction factor KG defined in IEC 60909-0 This attribute is used "
                        "to describe the operating voltage of the generating unit.")

        self.register_property(
            name='ratedPowerFactor',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Power factor (nameplate data). "
                        "It is primarily used for short circuit data exchange according to IEC 60909.")

        self.register_property(
            name='ratedS',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VA,
            description="Nameplate apparent power rating for the unit. The attribute shall have a positive value.")

        self.register_property(
            name='ratedU',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="Rated voltage (nameplate data, Ur in IEC 60909-0). "
                        "It is primarily used for short circuit data exchange according to IEC 60909.")

        self.register_property(
            name='operatingMode',
            class_type=cim_enums.SynchronousMachineOperatingMode,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")

        self.register_property(
            name='referencePriority',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")
        #
        # self.register_property(
        #     name='EquipmentContainer',
        #     class_type=EquipmentContainer,
        #     multiplier=UnitMultiplier.none,
        #     unit=UnitSymbol.none,
        #     description="")
        #
        # self.register_property(
        #     name='EquipmentContainer',
        #     class_type=EquipmentContainer,
        #     multiplier=UnitMultiplier.none,
        #     unit=UnitSymbol.none,
        #     description="")
        #
        # self.register_property(
        #     name='EquipmentContainer',
        #     class_type=EquipmentContainer,
        #     multiplier=UnitMultiplier.none,
        #     unit=UnitSymbol.none,
        #     description="")

        self.register_property(
            name='InitialReactiveCapabilityCurve',
            class_type=ReactiveCapabilityCurve,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Synchronous machines using this curve as default.")

        self.register_property(
            name='GeneratingUnit',
            class_type=GeneratingUnit,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")

        self.register_property(
            name='RegulatingControl',
            class_type=RegulatingControl,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")

        self.register_property(
            name='BaseVoltage',
            class_type=BaseVoltage,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")

        self.register_property(
            name='EquipmentContainer',
            class_type=IdentifiedObject,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")


class HydroGeneratingUnit(GeneratingUnit):

    def __init__(self, rdfid, tpe):
        GeneratingUnit.__init__(self, rdfid, tpe)

        self.energyConversionCapability: cim_enums.HydroEnergyConversionKind = cim_enums.HydroEnergyConversionKind.generator

        self.HydroPowerPlant: HydroPowerPlant = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'energyConversionCapability': [cgmesProfile.EQ.value, ],
                                     'HydroPowerPlant': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='energyConversionCapability',
            class_type=cim_enums.HydroEnergyConversionKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Energy conversion capability for generating.")

        self.register_property(
            name='HydroPowerPlant',
            class_type=HydroPowerPlant,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The hydro generating unit belongs to a hydro power plant.")


class HydroPowerPlant(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.hydroPlantStorageType: cim_enums.HydroPlantStorageKind = cim_enums.HydroPlantStorageKind.storage

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     # 'HydroGeneratingUnits': [cgmesProfile.EQ.value, ],
                                     'hydroPlantStorageType': [cgmesProfile.EQ.value, ],
                                     # 'HydroPumps': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='hydroPlantStorageType',
            class_type=cim_enums.HydroPlantStorageKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The type of hydro power plant water storage.")


class LinearShuntCompensator(MonoPole):

    def __init__(self, rdfid, tpe):
        MonoPole.__init__(self, rdfid, tpe)

        self.bPerSection: float = 0
        self.gPerSection: float = 0

        self.b0PerSection: float = 0
        self.g0PerSection: float = 0

        self.aVRDelay: float = 0.0
        self.grounded: bool = False

        self.maximumSections: int = 0
        self.nomU: float = 0
        self.normalSections: int = 0

        self.switchOnCount: int = 0
        self.switchOnDate: datetime.datetime = None

        self.voltageSensitivity: float = 0.0  # kV/MVAr

        self.controlEnabled: bool = False
        self.sections: int = 0

        self.RegulatingControl: RegulatingControl = None
        self.EquipmentContainer: IdentifiedObject = None
        self.BaseVoltage: BaseVoltage = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, cgmesProfile.SV.value, ],
                                     'b0PerSection': [cgmesProfile.EQ.value, ],
                                     'bPerSection': [cgmesProfile.EQ.value, ],
                                     'g0PerSection': [cgmesProfile.EQ.value, ],
                                     'gPerSection': [cgmesProfile.EQ.value, ],
                                     'sections': [cgmesProfile.SSH.value, ],
                                     'controlEnabled': [cgmesProfile.SSH.value, ],
                                     'aVRDelay': [cgmesProfile.EQ.value, ],
                                     'grounded': [cgmesProfile.EQ.value, ],
                                     'maximumSections': [cgmesProfile.EQ.value, ],
                                     'nomU': [cgmesProfile.EQ.value, ],
                                     'normalSections': [cgmesProfile.EQ.value, ],
                                     'switchOnCount': [cgmesProfile.EQ.value, ],
                                     'switchOnDate': [cgmesProfile.EQ.value, ],
                                     'voltageSensitivity': [cgmesProfile.EQ.value, ],
                                     'SvShuntCompensatorSections': [cgmesProfile.SV.value, ],
                                     'RegulatingControl': [cgmesProfile.EQ.value, ],
                                     'BaseVoltage': [cgmesProfile.EQ.value, ],
                                     'Terminals': [cgmesProfile.EQ.value, cgmesProfile.DY.value,
                                                   cgmesProfile.EQ_BD.value, ],
                                     }

        self.register_property(
            name='b0PerSection',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.S,
            description="Zero sequence shunt (charging) susceptance per section."
        )

        self.register_property(
            name='bPerSection',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.S,
            description="Positive sequence shunt (charging) susceptance per section."
        )

        self.register_property(
            name='g0PerSection',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.S,
            description="Zero sequence shunt (charging) conductance per section."
        )

        self.register_property(
            name='gPerSection',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.S,
            description="Positive sequence shunt (charging) conductance per section."
        )

        self.register_property(
            name='aVRDelay',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.s,
            description="Time delay required for the device to be connected or "
                        "disconnected by automatic voltage regulation (AVR)."
        )

        self.register_property(
            name='grounded',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Used for Yn and Zn connections. True if the neutral is solidly grounded."
        )

        self.register_property(
            name='maximumSections',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The maximum number of sections that may be switched in."
        )

        self.register_property(
            name='nomU',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="The voltage at which the nominal reactive power may be calculated. This should "
                        "normally be within 10% of the voltage at which the capacitor is connected to the network."
        )

        self.register_property(
            name='normalSections',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The normal number of sections switched in."
        )

        self.register_property(
            name='switchOnCount',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The switch on count since the capacitor count was last reset or initialized."
        )

        self.register_property(
            name='switchOnDate',
            class_type=datetime.datetime,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The date and time when the capacitor bank was last switched on."
        )

        self.register_property(
            name='voltageSensitivity',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.kVperMVAr,
            description="Voltage sensitivity required for the device to regulate the bus "
                        "voltage, in voltage/reactive power."
        )

        self.register_property(
            name='sections',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description=""
        )

        self.register_property(
            name='controlEnabled',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description=""
        )

        self.register_property(
            name='RegulatingControl',
            class_type=RegulatingControl,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description=""
        )

        self.register_property(
            name='EquipmentContainer',
            class_type=IdentifiedObject,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description=""
        )

        self.register_property(
            name='BaseVoltage',
            class_type=BaseVoltage,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description=""
        )


class NuclearGeneratingUnit(GeneratingUnit):

    def __init__(self, rdfid, tpe):
        GeneratingUnit.__init__(self, rdfid, tpe)


class RatioTapChangerTable(IdentifiedObject):
    """
    Describes a curve for how the voltage magnitude and impedance varies with the tap step.
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)


class RatioTapChangerTablePoint(IdentifiedObject):
    """
    Describes each tap step in the ratio tap changer tabular curve.
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.ratio: float = 0.0
        self.step: int = 0

        self.r: float = 0.0
        self.x: float = 0.0
        self.b: float = 0.0
        self.g: float = 0.0

        self.RatioTapChangerTable: RatioTapChangerTable = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'b': [cgmesProfile.EQ.value, ],
                                     'g': [cgmesProfile.EQ.value, ],
                                     'r': [cgmesProfile.EQ.value, ],
                                     'ratio': [cgmesProfile.EQ.value, ],
                                     'step': [cgmesProfile.EQ.value, ],
                                     'x': [cgmesProfile.EQ.value, ],
                                     'RatioTapChangerTable': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='b',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The magnetizing branch susceptance deviation in percent of nominal value. "
                        "The actual susceptance is calculated as follows: calculated magnetizing "
                        "susceptance = b(nominal) * (1 + b(from this class)/100). The b(nominal) is "
                        "defined as the static magnetizing susceptance on the associated power "
                        "transformer end or ends. This model assumes the star impedance (pi model) form.")

        self.register_property(
            name='g',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The magnetizing branch conductance deviation in percent of nominal value. "
                        "The actual conductance is calculated as follows: calculated magnetizing "
                        "conductance = g(nominal) * (1 + g(from this class)/100). The g(nominal) is "
                        "defined as the static magnetizing conductance on the associated power "
                        "transformer end or ends. This model assumes the star impedance (pi model) form.")

        self.register_property(
            name='r',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The resistance deviation in percent of nominal value. "
                        "The actual reactance is calculated as follows: calculated "
                        "resistance = r(nominal) * (1 + r(from this class)/100). The r(nominal) is "
                        "defined as the static resistance on the associated power transformer end or ends. "
                        "This model assumes the star impedance (pi model) form.")

        self.register_property(
            name='x',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The series reactance deviation in percent of nominal value. "
                        "The actual reactance is calculated as follows: "
                        "calculated reactance = x(nominal) * (1 + x(from this class)/100). "
                        "The x(nominal) is defined as the static series reactance on the associated power "
                        "transformer end or ends. This model assumes the star impedance (pi model) form.")

        self.register_property(
            name='ratio',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The voltage ratio in per unit. Hence this is a value close to one.")

        self.register_property(
            name='step',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The tap step.")

        self.register_property(
            name='RatioTapChangerTable',
            class_type=RatioTapChangerTable,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")


class ReactiveCapabilityCurve(IdentifiedObject):
    """
    Reactive power rating envelope versus the synchronous machine's active power, in both the
    generating and motoring modes. For each active power value there is a corresponding high and
    low reactive power limit value. Typically there will be a separate curve for each coolant condition,
    such as hydrogen pressure. The Y1 axis values represent reactive minimum and the Y2 axis
    values represent reactive maximum.
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.curveStyle: cim_enums.CurveStyle = cim_enums.CurveStyle.straightLineYValues
        self.xUnit: UnitSymbol = UnitSymbol.none
        self.y1Unit: UnitSymbol = UnitSymbol.none
        self.y2Unit: UnitSymbol = UnitSymbol.none

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'curveStyle': [cgmesProfile.EQ.value, ],
                                     'xUnit': [cgmesProfile.EQ.value, ],
                                     'y1Unit': [cgmesProfile.EQ.value, ],
                                     'y2Unit': [cgmesProfile.EQ.value, ],
                                     # 'CurveDatas': [cgmesProfile.EQ.value, ],
                                     # 'EquivalentInjection': [cgmesProfile.EQ.value, ],
                                     # 'InitiallyUsedBySynchronousMachines': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='curveStyle',
            class_type=cim_enums.CurveStyle,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The style or shape of the curve.")

        self.register_property(
            name='xUnit',
            class_type=UnitSymbol,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The X-axis units of measure.")

        self.register_property(
            name='y1Unit',
            class_type=UnitSymbol,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The Y1-axis units of measure.")

        self.register_property(
            name='y2Unit',
            class_type=UnitSymbol,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The Y2-axis units of measure.")


class StaticVarCompensator(RegulatingCondEq):

    def __init__(self, rdfid, tpe):
        RegulatingCondEq.__init__(self, rdfid, tpe)

        self.q: float = 0.0
        self.capacitiveRating: float = 0.0  # S
        self.inductiveRating: float = 0.0  # S
        self.slope: float = 0.0  # kV/MVAr
        self.sVCControlMode: cim_enums.SVCControlMode = cim_enums.SVCControlMode.volt
        self.voltageSetPoint: float = 0.0

        self.RegulatingControl: RegulatingControl = None
        self.EquipmentContainer: IdentifiedObject = None
        self.BaseVoltage: BaseVoltage = None

        self.possibleProfileList |= {'class': [cgmesProfile.SSH.value, cgmesProfile.EQ.value, ],
                                     'q': [cgmesProfile.SSH.value, ],
                                     'capacitiveRating': [cgmesProfile.EQ.value, ],
                                     'inductiveRating': [cgmesProfile.EQ.value, ],
                                     'slope': [cgmesProfile.EQ.value, ],
                                     'sVCControlMode': [cgmesProfile.EQ.value, ],
                                     'voltageSetPoint': [cgmesProfile.EQ.value, ],
                                     'RegulatingControl': [cgmesProfile.EQ.value, ],
                                     'EquipmentContainer': [cgmesProfile.EQ.value, ],
                                     'BaseVoltage': [cgmesProfile.EQ.value, ],
                                     }
        self.register_property(
            name='q',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="")

        self.register_property(
            name='capacitiveRating',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Maximum available capacitive reactance.")

        self.register_property(
            name='inductiveRating',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Maximum available inductive reactance.")

        self.register_property(
            name='slope',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.kVperMVAr,
            description="The characteristics slope of an SVC defines how the reactive "
                        "power output changes in proportion to the difference between the "
                        "regulated bus voltage and the voltage setpoint.")

        self.register_property(
            name='sVCControlMode',
            class_type=cim_enums.SVCControlMode,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="SVC control mode.")

        self.register_property(
            name='voltageSetPoint',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="The reactive power output of the SVC is proportional to the difference between "
                        "the voltage at the regulated bus and the voltage setpoint. When the regulated bus "
                        "voltage is equal to the voltage setpoint, the reactive power output is zero.")

        self.register_property(
            name='RegulatingControl',
            class_type=RegulatingControl,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")

        self.register_property(
            name='BaseVoltage',
            class_type=BaseVoltage,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")

        self.register_property(
            name='EquipmentContainer',
            class_type=IdentifiedObject,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="")


class TapChangerControl(RegulatingControl):

    def __init__(self, rdfid, tpe):
        RegulatingControl.__init__(self, rdfid, tpe)


class ThermalGeneratingUnit(GeneratingUnit):

    def __init__(self, rdfid, tpe):
        GeneratingUnit.__init__(self, rdfid, tpe)


class WindGeneratingUnit(GeneratingUnit):

    def __init__(self, rdfid, tpe):
        GeneratingUnit.__init__(self, rdfid, tpe)

        self.windGenUnitType: cim_enums.WindGenUnitKind = cim_enums.WindGenUnitKind.onshore

        self.possibleProfileList |= {
            'windGenUnitType': [cgmesProfile.EQ.value, ],
        }

        self.register_property(
            name='windGenUnitType',
            class_type=cim_enums.WindGenUnitKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The kind of wind generating unit.")


class FullModel(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.scenarioTime = ''
        self.created = ''
        self.version = ''
        self.profile = ''
        self.modelingAuthoritySet = ''
        self.DependentOn = ''
        self.longDependentOnPF = ''


class TieFlow(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.positiveFlowIn: bool = True

        self.ControlArea: ControlArea = None
        self.Terminal: Terminal = None

        self.possibleProfileList |= {'class': [cgmesProfile.EQ.value, ],
                                     'Terminal': [cgmesProfile.EQ.value, ],
                                     'ControlArea': [cgmesProfile.EQ.value, ],
                                     'positiveFlowIn': [cgmesProfile.EQ.value, ],
                                     }

        self.register_property(
            name='positiveFlowIn',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="True if the flow into the terminal (load convention) is also flow into the control area. "
                        "For example, this attribute should be true if using the tie line terminal further away from "
                        "the control area. For example to represent a tie to a shunt component "
                        "(like a load or generator) in another area, this is the near end of a branch and this "
                        "attribute would be specified as false.")

        self.register_property(
            name='ControlArea',
            class_type=ControlArea,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The control area of the tie flows.")

        self.register_property(
            name='Terminal',
            class_type=Terminal,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The terminal to which this tie flow belongs.")
