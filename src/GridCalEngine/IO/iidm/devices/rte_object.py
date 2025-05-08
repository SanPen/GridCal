# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import hashlib
import uuid as uuidlib
from typing import List, Dict, TypeVar, Any
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_property import PsseProperty

class RteObject:
    """
    RteObject
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
        Get the RAWX property dictionary
        :return: Dict[str, PsseProperty]
        """

        return {value.rawx_key: value
                for key, value in self.__registered_properties.items()}

    def register_property(self,
                          property_name: str,
                          rawx_key: str,
                          class_type: TypeVar | object,
                          unit: Unit = Unit(),
                          denominator_unit: Unit = Unit(),
                          description: str = '',
                          max_chars=None,
                          min_value=-1e20,
                          max_value=1e20,
                          format_rule=None):
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
        :param format_rule: some formatting rule
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
                                                                       max_value=max_value,
                                                                       format_rule=format_rule)
        else:
            raise Exception('Property not found when trying to declare it :(')