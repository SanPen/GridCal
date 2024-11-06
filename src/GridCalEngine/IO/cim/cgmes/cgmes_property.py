# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Dict
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol, Unit
from GridCalEngine.IO.base.base_property import BaseProperty
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class CgmesProperty(BaseProperty):
    """
    CgmesProperty
    """
    def __init__(self, property_name: str,
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
        CIM property for soft type checking
        :param property_name: name of the property
        :param class_type: class type (actual python object)
        :param multiplier: UnitMultiplier from CIM
        :param unit: UnitSymbol from CIM
        :param description: property description
        :param max_chars: maximum number of characters (only for strings)
        :param mandatory: is this property mandatory when parsing?
        :param comment: Extra comments
        :param out_of_the_standard: Is this property out of the standard?
        :param profiles: List of profiles where this property should appear
        """
        BaseProperty.__init__(self,
                              property_name=property_name,
                              class_type=class_type,
                              unit=Unit(multiplier, unit),
                              denominator_unit=None,
                              description=description,
                              max_chars=max_chars,
                              min_value=-1e20,
                              max_value=1e20)

        # for x in profiles:
        #     if not isinstance(x, cgmesProfile):
        #         raise Exception()

        self.mandatory = mandatory
        self.comment = comment
        self.out_of_the_standard = out_of_the_standard
        self.profiles = profiles

    def get_dict(self) -> Dict[str, str]:
        """
        Get dictionary of property values
        :return:
        """
        return {'name': self.property_name,
                'class_type': self.get_class_name(),
                'unit': self.get_unit(),
                'mandatory': self.mandatory,
                'max_chars': self.max_chars,
                'profiles': ', '.join([a.value for a in self.profiles]),
                "descriptions": self.description,
                'comment': self.comment}
