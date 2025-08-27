# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import uuid as uuidlib
from typing import List, Dict, TypeVar
from VeraGridEngine.IO.base.units import Unit
from VeraGridEngine.IO.base.base_property import BaseProperty


class RteObject:
    """
    RteObject
    """

    def __init__(self, class_name):

        self.class_name = class_name

        self.idtag = uuidlib.uuid4().hex  # always initialize with random uuid

        self.__registered_properties: Dict[str, BaseProperty] = dict()

        self.register_property(property_name="idtag",
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

    def get_properties(self) -> List[BaseProperty]:
        """
        Get list of properties
        :return: List[BaseProperty]
        """
        return list(self.__registered_properties.values())

    def get_prop_value(self, prop: BaseProperty):
        """
        Get property value
        :param prop:
        :return:
        """
        return getattr(self, prop.property_name)

    def register_property(self,
                          property_name: str,
                          class_type: TypeVar | object,
                          unit: Unit = Unit(),
                          denominator_unit: Unit = Unit(),
                          description: str = '',
                          max_chars=None,
                          min_value=-1e20,
                          max_value=1e20):
        """
        Register property of this object
        :param property_name:
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
            self.__registered_properties[property_name] = BaseProperty(property_name=property_name,
                                                                       class_type=class_type,
                                                                       unit=unit,
                                                                       denominator_unit=denominator_unit,
                                                                       description=description,
                                                                       max_chars=max_chars,
                                                                       min_value=min_value,
                                                                       max_value=max_value)
        else:
            raise Exception('Property not found when trying to declare it :(')
