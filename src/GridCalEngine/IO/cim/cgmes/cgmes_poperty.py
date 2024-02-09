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
