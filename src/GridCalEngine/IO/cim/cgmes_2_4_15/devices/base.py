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
from typing import Dict, List
from uuid import uuid4
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_poperty import CgmesProperty
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.data_logger import DataLogger


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


def index_find(string, start, end):
    """
    version of substring that matches
    :param string: string
    :param start: string to start splitting
    :param end: string to end splitting
    :return: string between start and end
    """
    return string.partition(start)[2].partition(end)[0]


def get_new_rfid():
    """

    :return:
    """
    return "_" + str(uuid4())


def rfid2uuid(val):
    """

    :param val:
    :return:
    """
    return val.replace('-', '').replace('_', '')


class Base:
    """
    Base
    """

    def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
        """
        General CIM object container
        :param rdfid:
        :param tpe: type of the object (class)
        :param resources:
        :param class_replacements:
        """

        # pick the object id
        rdfid = rdfid.strip()
        self.rdfid = rdfid if rdfid != '' else get_new_rfid()
        self.uuid = rfid2uuid(self.rdfid)

        # store the object type
        self.tpe = tpe

        self.class_replacements: Dict = class_replacements
        self.resources: List = resources

        # dictionary of objects that reference this object
        self.references_to_me = dict()

        # dictionary of missing references (those provided but not used)
        self.missing_references = dict()

        # register the CIM properties
        self.declared_properties: Dict[str, CgmesProperty] = dict()

        self.parsed_properties = dict()

        self.boundary_set = False

        self.used = False

    def can_keep(self):
        """
        Can I keep this object?
        :return:
        """
        return self.used # and not self.boundary_set

    def has_references(self) -> bool:
        """
        Determine if there are references to this object
        :return: Bool
        """
        return len(self.references_to_me) > 0

    def parse_dict(self, data: Dict[str, str], logger: DataLogger):

        self.parsed_properties = data

        for prop_name, prop_value in data.items():

            prop = self.declared_properties.get(prop_name, None)

            if prop is not None:
                setattr(self, prop_name, prop_value)
            else:
                logger.add_error("Missing object property", device_class=self.tpe, device_property=prop_name,
                                 device=self.rdfid)

    def __repr__(self):
        return self.rdfid

    def __str__(self):
        return self.tpe + ':' + self.rdfid

    def __hash__(self):
        # alternatively, return hash(repr(self))
        return int(self.uuid, 16)  # hex string to int

    def __lt__(self, other):
        return self.__hash__() < other.__hash__()

    def __eq__(self, other):
        return self.rdfid == other.rdfid

    def check(self, logger: DataLogger):
        """
        Check specific OCL rules
        :param logger: Logger instance
        :return: true is ok false otherwise
        """
        return True

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

    def register_property(self, name: str,
                          class_type: object,
                          multiplier: UnitMultiplier = UnitMultiplier.none,
                          unit: UnitSymbol = UnitSymbol.none,
                          description: str = '',
                          max_chars=65536,
                          mandatory=False,
                          comment='',
                          out_of_the_standard=False,
                          profiles: List[cgmesProfile] = ()):
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
        self.declared_properties[name] = CgmesProperty(
            property_name=name,
            class_type=class_type,
            multiplier=multiplier,
            unit=unit,
            description=description,
            max_chars=max_chars,
            mandatory=mandatory,
            comment=comment,
            out_of_the_standard=out_of_the_standard,
            profiles=profiles)

    def get_properties(self) -> List[CgmesProperty]:
        return [p for name, p in self.declared_properties.items()]

    def get_xml(self, level=0, profiles: List[cgmesProfile] = [cgmesProfile.EQ]) -> Dict[cgmesProfile, str]:

        """
        Returns an XML representation of the object
        Args:
            level:
            profiles
        Returns:

        """

        """
        <cim:IEC61970CIMVersion rdf:ID="version">
            <cim:IEC61970CIMVersion.version>IEC61970CIM16v29a</cim:IEC61970CIMVersion.version>
            <cim:IEC61970CIMVersion.date>2015-07-15</cim:IEC61970CIMVersion.date>
        </cim:IEC61970CIMVersion>
        """
        data = dict()
        for profile in profiles:
            l1 = '  ' * level  # start/end tabbing
            l2 = '  ' * (level + 1)  # middle tabbing

            # header
            xml = l1 + '<cim:' + self.tpe + ' rdf:ID="' + self.rdfid + '">\n'

            for prop_name, prop in self.declared_properties.items():

                if profile in prop.profiles:
                    value = getattr(self, prop_name)

                    v = str(value).replace(' ', '_')

                    # eventually replace the class of the property, because CIM is so well designed...
                    if prop in self.class_replacements.keys():
                        cls = self.class_replacements[prop]
                    else:
                        cls = self.tpe

                    if prop.class_type not in [bool, int, float, str]:
                        xml += l2 + '<cim:' + cls + '.' + prop_name + ' rdf:resource="#' + v + '" />\n'
                    else:
                        xml += l2 + '<cim:' + cls + '.' + prop_name + '>' + v + '</cim:' + cls + '.' + prop_name + '>\n'

            # closing
            xml += l1 + '</cim:' + self.tpe + '>\n'

            data[profile] = xml

        return data

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

    def detect_circular_references(self, visited):
        """
        Get path, leading to a circular refference
        :param visited: list of visited elements' rdfid (used for recursion)
        :return: path of circular refferences
        """
        visited.append(self.rdfid)

        for prop in self.get_all_properties():

            value = getattr(self, prop)

            if hasattr(value, 'rdfid'):
                if value.rdfid in visited:
                    visited.append(value.rdfid)
                    return True
                else:
                    is_loop = value.detect_circular_references(visited=visited)

                    if is_loop:
                        return True
            else:
                pass

        return False
