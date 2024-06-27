# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
import hashlib
import uuid as uuidlib
from typing import List, Dict, Union
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_property import PsseProperty


def uuid_from_seed(seed: str):
    """

    :param seed:
    :return:
    """
    m = hashlib.md5()
    m.update(seed.encode('utf-8'))
    return uuidlib.UUID(m.hexdigest()).hex


class RawObject:
    """
    PSSeObject
    """

    def __init__(self, class_name):

        self.class_name = class_name

        self.version = 33

        self.idtag = uuidlib.uuid4().hex  # always initialize with random  uuid

        self.__registered_properties: Dict[str, PsseProperty] = dict()

        self.register_property(property_name="idtag",
                               rawx_key="uuid:string",
                               class_type=str,
                               description="Element UUID")

    def get_rdfid(self) -> str:
        """
        Convert the idtag to RDFID
        :return: UUID converted to RDFID
        """
        lenghts = [8, 4, 4, 4, 12]
        chunks = list()
        s = 0
        for l in lenghts:
            a = self.idtag[s:s + l]
            chunks.append(a)
            s += l
        return "-".join(chunks)

    def get_properties(self) -> List[PsseProperty]:
        """
        Get list of properties
        :return: List[PsseProperty]
        """
        return list(self.__registered_properties.values())

    def get_prop_value(self, prop: PsseProperty):
        """
        Get property value
        :param prop:
        :return:
        """
        return getattr(self, prop.property_name)

    def get_rawx_dict(self) -> Dict[str, PsseProperty]:
        """
        Get the RAWX property dictionsry
        :return: Dict[str, PsseProperty]
        """

        return {value.rawx_key: value
                for key, value in self.__registered_properties.items()}

    def register_property(self,
                          property_name: str,
                          rawx_key: str,
                          class_type: object,
                          unit: Unit = Unit(),
                          denominator_unit: Unit = Unit(),
                          description: str = '',
                          max_chars=65000,
                          min_value=-1e20,
                          max_value=1e20):
        """
        Register property of this object
        :param property_name:
        :param rawx_key:
        :param class_type:
        :param unit:
        :param denominator_unit:
        :param description:
        :param max_chars:
        :param min_value:
        :param max_value:
        """
        if hasattr(self, property_name):
            self.__registered_properties[property_name] = PsseProperty(property_name=property_name,
                                                                       rawx_key=rawx_key,
                                                                       class_type=class_type,
                                                                       unit=unit,
                                                                       denominator_unit=denominator_unit,
                                                                       description=description,
                                                                       max_chars=max_chars,
                                                                       min_value=min_value,
                                                                       max_value=max_value)
        else:
            raise Exception('Property not found when trying to declare it :(')

    def format_raw_line_prop(self, props: List[str]):
        """
        Format a list of property names
        :param props: list of property names
        :return:
        """
        lst = list()
        for p in props:
            if p in self.__registered_properties:
                prop = self.__registered_properties[p]
                val = getattr(self, p)
                if prop.class_type == str:
                    lst.append("'" + val + "'")
                else:
                    lst.append(str(val))
        return ", ".join(lst)

    @staticmethod
    def format_raw_line(props: List[Union[str, int, float]]) -> str:
        """
        Format a list of values
        :param props: list of values
        :return:
        """
        lst = list()
        for val in props:
            if type(val) == str:
                lst.append("'" + val + "'")
            else:
                lst.append(str(val))
        return ", ".join(lst)

    def get_raw_line(self, version: int) -> str:
        """
        Get raw line
        :param version: PSSe version
        :return: Raw string representing this object
        """
        return ""

    def get_id(self) -> str:
        """
        Get a PSSe ID
        Each device will implement its own way of generating this
        :return: id
        """
        return ""

    def __str__(self):
        return self.get_id()

    def get_seed(self) -> str:
        """
        Get seed ID
        :return: seed ID
        """
        return self.get_id()

    def get_uuid5(self):
        """
        Generate UUID with the seed given by get_id()
        :return: UUID based on the PSSe seed
        """
        return uuid_from_seed(seed=self.get_seed())
